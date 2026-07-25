from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sb_media")
class TestBridge(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # dms_field's create() gates its auto-directory creation off during
        # --test-enable runs (to avoid noise in unrelated module tests)
        # unless this context flag is set. See dms_field/models/dms_field_mixin.py.
        cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))

    def test_storage_and_roots_exist(self):
        """Test that storage and root directories are created correctly."""
        st = self.env.ref("sb_production_media.storage_production_media")
        self.assertEqual(st.save_type, "file")
        self.assertTrue(self.env.ref("sb_production_media.dir_root_products"))
        self.assertTrue(self.env.ref("sb_production_media.dir_root_shipping"))

    def test_auto_directory_per_record(self):
        """Creating a product.template / mrp.production auto-creates a DMS directory."""
        p = self.env["product.template"].create({"name": "Widget"})
        # dms_field's One2many is keyed on a plain (res_model, res_id) domain rather
        # than a true inverse Many2one, so the ORM doesn't auto-invalidate it when
        # dms_field_mixin.create() creates the linked dms.directory after the record
        # insert. dms_field's own test suite invalidates for the same reason
        # (see dms_field/tests/test_dms_field.py).
        p.invalidate_recordset()
        self.assertTrue(p.dms_directory_ids, "product should auto-create a DMS directory")
        mo = self.env["mrp.production"].create({"product_id": p.product_variant_id.id})
        mo.invalidate_recordset()
        self.assertTrue(mo.dms_directory_ids, "MO should auto-create a DMS directory")

    def test_mo_dir_nested_under_product(self):
        """MO directory is classified sb_dir_kind='mo' and re-parented under a
        get-or-created "Orders" subdirectory of its product's directory."""
        p = self.env["product.template"].create({"name": "Cab"})
        mo = self.env["mrp.production"].create({"product_id": p.product_variant_id.id})
        # invalidate: dms_directory_ids is a plain-Integer-keyed One2many that
        # the ORM doesn't auto-invalidate after the mixin's post-create directory
        # insert (see class docstring / dms_field_bridge.py landmine notes).
        p.invalidate_recordset()
        mo.invalidate_recordset()
        product_dir = p.dms_directory_ids[:1]
        mo_dir = mo.dms_directory_ids[:1]
        self.assertEqual(mo_dir.sb_dir_kind, "mo")
        # nested: MO dir's parent is an "Orders" subdir, whose parent is the
        # product's own directory.
        orders_dir = mo_dir.parent_id
        self.assertEqual(orders_dir.name, "Orders")
        self.assertEqual(orders_dir.sb_dir_kind, "structural")
        self.assertEqual(orders_dir.parent_id, product_dir)

    def test_picking_dir_classified_shipping(self):
        """Picking directory is classified sb_dir_kind='shipping' and sits
        under the Shipping root (closes the C3 picking-coverage gap)."""
        partner = self.env["res.partner"].create({"name": "Cab Customer"})
        picking_type = self.env.ref("stock.picking_type_out")
        picking = self.env["stock.picking"].create(
            {
                "partner_id": partner.id,
                "picking_type_id": picking_type.id,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": picking_type.default_location_dest_id.id,
            }
        )
        picking.invalidate_recordset()
        picking_dir = picking.dms_directory_ids[:1]
        self.assertTrue(picking_dir, "picking should auto-create a DMS directory")
        self.assertEqual(picking_dir.sb_dir_kind, "shipping")
        shipping_root = self.env.ref("sb_production_media.dir_root_shipping")
        self.assertEqual(picking_dir.parent_id, shipping_root)

    def test_flat_listings(self):
        """Test that flat MO and Shipping QC listings are exposed via actions."""
        # Test Manufacturing Orders Media action
        mo_action = self.env.ref("sb_production_media.action_mo_media")
        self.assertEqual(eval(mo_action.domain), [("sb_dir_kind", "=", "mo")])
        self.assertEqual(mo_action.res_model, "dms.directory")
        self.assertEqual(mo_action.view_mode, "list,form")

        # Test Shipping QC action
        shipping_action = self.env.ref("sb_production_media.action_shipping_media")
        self.assertEqual(eval(shipping_action.domain), [("sb_dir_kind", "=", "shipping")])
        self.assertEqual(shipping_action.res_model, "dms.directory")
        self.assertEqual(shipping_action.view_mode, "list,form")
