# SPDX-License-Identifier: LGPL-3.0-only
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged
from psycopg2 import IntegrityError
from odoo.tools import mute_logger


@tagged("post_install", "-at_install", "southbrook", "sbk_mathw")
class TestDeclarations(TransactionCase):
    def setUp(self):
        super().setUp()
        self.cat = self.env.ref("southbrook_mrp_kitchen_tools.cat_screws")

    def test_facet_created(self):
        facet = self.env["materials.catalog.facet"].create({
            "name": "Thread type",
            "category_id": self.cat.id,
            "field_name": "x_southbrook_thread_type",
            "facet_type": "enum",
        })
        self.assertEqual(facet.sequence, 10)
        self.assertTrue(facet.active)

    def test_column_created(self):
        col = self.env["materials.catalog.column"].create({
            "name": "Length (mm)",
            "category_id": self.cat.id,
            "field_name": "x_southbrook_screw_length_mm",
            "align": "right",
        })
        self.assertTrue(col.sortable)

    @mute_logger("odoo.sql_db")
    def test_facet_unique_per_category(self):
        vals = {
            "name": "Thread type",
            "category_id": self.cat.id,
            "field_name": "x_southbrook_thread_type",
            "facet_type": "enum",
        }
        self.env["materials.catalog.facet"].create(vals)
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["materials.catalog.facet"].create(dict(vals))

    def test_field_name_must_exist_on_product_template(self):
        with self.assertRaises(ValidationError):
            self.env["materials.catalog.facet"].create({
                "name": "Nonsense",
                "category_id": self.cat.id,
                "field_name": "x_southbrook_not_a_real_field",
                "facet_type": "enum",
            })
