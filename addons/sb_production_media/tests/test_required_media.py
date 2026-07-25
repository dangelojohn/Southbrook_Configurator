# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sb_media")
class TestRequiredMedia(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # dms_field's create() gates its auto-directory creation off during
        # --test-enable runs unless this context flag is set. See
        # dms_field/models/dms_field_mixin.py and sb_production_media's
        # tests/test_bridge.py for the same setup.
        cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))

    def _add_file(self, record):
        record.invalidate_recordset(["dms_directory_ids"])
        directory = record.dms_directory_ids[:1]
        return self.env["dms.file"].create(
            {"name": "shot.jpg", "directory_id": directory.id, "content": "eA=="}
        )

    # -- mrp.production ----------------------------------------------

    def test_mo_blocked_without_media(self):
        mo = self.env["mrp.production"].create(
            {
                "product_id": self.env["product.product"].create({"name": "Y"}).id,
                "media_required": True,
            }
        )
        with self.assertRaises(UserError):
            mo._sb_check_required_media()

    def test_mo_passes_once_media_exists(self):
        mo = self.env["mrp.production"].create(
            {
                "product_id": self.env["product.product"].create({"name": "Y2"}).id,
                "media_required": True,
            }
        )
        self._add_file(mo)
        mo._sb_check_required_media()  # should not raise

    def test_mo_not_required_no_block(self):
        mo = self.env["mrp.production"].create(
            {
                "product_id": self.env["product.product"].create({"name": "Y3"}).id,
                "media_required": False,
            }
        )
        mo._sb_check_required_media()  # should not raise

    def test_mo_button_mark_done_blocked(self):
        """The guard fires before super(), so an otherwise-invalid draft MO
        still raises UserError from the media gate rather than any other
        mark-done precondition error."""
        mo = self.env["mrp.production"].create(
            {
                "product_id": self.env["product.product"].create({"name": "Y4"}).id,
                "media_required": True,
            }
        )
        with self.assertRaises(UserError):
            mo.button_mark_done()

    # -- stock.picking -------------------------------------------------

    def _make_picking(self):
        partner = self.env["res.partner"].create({"name": "Media Gate Customer"})
        picking_type = self.env.ref("stock.picking_type_out")
        return self.env["stock.picking"].create(
            {
                "partner_id": partner.id,
                "picking_type_id": picking_type.id,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": picking_type.default_location_dest_id.id,
                "media_required": True,
            }
        )

    def test_picking_blocked_without_media(self):
        picking = self._make_picking()
        with self.assertRaises(UserError):
            picking._sb_check_required_media()

    def test_picking_passes_once_media_exists(self):
        picking = self._make_picking()
        self._add_file(picking)
        picking._sb_check_required_media()  # should not raise

    def test_picking_button_validate_blocked(self):
        picking = self._make_picking()
        with self.assertRaises(UserError):
            picking.button_validate()
