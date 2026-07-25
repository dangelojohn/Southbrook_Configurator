from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sb_media")
class TestBridge(TransactionCase):
    def test_storage_and_roots_exist(self):
        """Test that storage and root directories are created correctly."""
        st = self.env.ref("sb_production_media.storage_production_media")
        self.assertEqual(st.save_type, "file")
        self.assertTrue(self.env.ref("sb_production_media.dir_root_products"))
        self.assertTrue(self.env.ref("sb_production_media.dir_root_shipping"))
