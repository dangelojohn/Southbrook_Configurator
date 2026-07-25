from odoo.tests import TransactionCase, tagged
from psycopg2 import IntegrityError
from odoo.tools import mute_logger


@tagged("post_install", "-at_install", "dms_port")
class TestPortConstraints(TransactionCase):
    def test_access_group_name_unique(self):
        self.env["dms.access.group"].create({"name": "dup"})
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["dms.access.group"].create({"name": "dup"})

    def test_category_name_unique(self):
        self.env["dms.category"].create({"name": "dupcat"})
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["dms.category"].create({"name": "dupcat"})

    def test_tag_name_category_unique(self):
        cat = self.env["dms.category"].create({"name": "cat1"})
        self.env["dms.tag"].create({"name": "tag1", "category_id": cat.id})
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["dms.tag"].create({"name": "tag1", "category_id": cat.id})
