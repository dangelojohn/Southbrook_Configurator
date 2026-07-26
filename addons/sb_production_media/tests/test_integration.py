# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
"""Task E1: end-to-end integration test for the sb_production_media bridge.

Exercises the whole flow through the real models / RPC surface
(``production.media``) rather than unit-testing any single piece in
isolation -- product -> variant -> MO -> upload -> QC/annotate -> chatter
audit, plus the picking-shipping path and the required-media gate.
"""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sb_media_integration")
class TestProductionMediaIntegration(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # dms_field's create() gates its auto-directory creation off during
        # --test-enable runs unless this context flag is set. See
        # dms_field/models/dms_field_mixin.py and sb_production_media's
        # other test modules for the same setup.
        cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))

    def test_full_bridge_flow(self):
        pm = self.env["production.media"]

        # -- 1. product -> variant -> MO -----------------------------------
        product_tmpl = self.env["product.template"].create({"name": "E1 Cabinet"})
        variant = product_tmpl.product_variant_id
        mo = self.env["mrp.production"].create({"product_id": variant.id})

        # LANDMINE (dms_directory_ids cache): invalidate before reading, the
        # ORM does not auto-invalidate the plain (res_model, res_id)-keyed
        # One2many after dms.field.mixin.create() links a directory in the
        # same transaction.
        product_tmpl.invalidate_recordset(["dms_directory_ids"])
        mo.invalidate_recordset(["dms_directory_ids"])
        product_dir = product_tmpl.dms_directory_ids[:1]
        self.assertTrue(product_dir, "product should have an auto-created DMS directory")

        # -- 2. upload_media on the MO, assert directory nesting (C4) ------
        fid = pm.upload_media("mrp.production", mo.id, "shot.jpg", "eA==", "image/jpeg")
        dms_file = self.env["dms.file"].browse(fid)
        self.assertTrue(dms_file.exists(), "uploaded file should exist")
        self.assertEqual(dms_file.name, "shot.jpg")

        mo_dir = dms_file.directory_id
        self.assertEqual(mo_dir.sb_dir_kind, "mo")
        orders_dir = mo_dir.parent_id
        self.assertEqual(orders_dir.name, "Orders")
        self.assertEqual(orders_dir.sb_dir_kind, "structural")
        self.assertEqual(
            orders_dir.parent_id,
            product_dir,
            "MO directory must nest under the product's 'Orders' structural subfolder",
        )

        # -- 3. set_qc_status + save_annotation -> C7 audit trail -----------
        before = len(mo.message_ids)
        pm.set_qc_status(fid, "flag")
        pm.save_annotation(fid, '[{"type":"circle","x":0.1,"y":0.1}]')
        dms_file.invalidate_recordset(["qc_status", "annotation_data"])
        self.assertEqual(dms_file.qc_status, "flag")
        self.assertEqual(dms_file.annotation_data, '[{"type":"circle","x":0.1,"y":0.1}]')
        after = len(mo.message_ids)
        self.assertEqual(
            after - before,
            2,
            "set_qc_status + save_annotation should each post one chatter audit note on the MO",
        )

        # -- 4. picking / shipping path (C4) --------------------------------
        partner = self.env["res.partner"].create({"name": "E1 Customer"})
        picking_type = self.env.ref("stock.picking_type_out")
        picking = self.env["stock.picking"].create(
            {
                "partner_id": partner.id,
                "picking_type_id": picking_type.id,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": picking_type.default_location_dest_id.id,
            }
        )
        picking_fid = pm.upload_media("stock.picking", picking.id, "pack.jpg", "eA==", "image/jpeg")
        picking_file = self.env["dms.file"].browse(picking_fid)
        picking_dir = picking_file.directory_id
        self.assertEqual(picking_dir.sb_dir_kind, "shipping")
        shipping_root = self.env.ref("sb_production_media.dir_root_shipping")
        self.assertEqual(
            picking_dir.parent_id,
            shipping_root,
            "picking directory must sit under the Shipping root",
        )

        # -- 5. media_required gate (C8) -------------------------------------
        gated_mo = self.env["mrp.production"].create(
            {"product_id": variant.id, "media_required": True}
        )
        with self.assertRaises(UserError):
            gated_mo.button_mark_done()
