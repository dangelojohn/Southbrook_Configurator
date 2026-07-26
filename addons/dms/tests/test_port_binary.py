# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "dms_port")
class TestPortBinary(TransactionCase):
    def test_can_return_content_with_token(self):
        storage = self.env["dms.storage"].search([], limit=1) or self.env[
            "dms.storage"
        ].create({"name": "t", "save_type": "database"})
        directory = self.env["dms.directory"].create(
            {"name": "d", "is_root_directory": True, "storage_id": storage.id}
        )
        f = self.env["dms.file"].create(
            {"name": "a.txt", "directory_id": directory.id, "content": "eA=="}
        )
        token = f.access_token or f._portal_ensure_token()
        # A user without direct rights, presenting the token, may read content:
        self.assertTrue(f._can_return_content(access_token=token))
