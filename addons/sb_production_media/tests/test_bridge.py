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
