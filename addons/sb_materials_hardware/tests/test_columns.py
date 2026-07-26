# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_mathw")
class TestColumns(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Provider = self.env["materials.catalog.provider"]
        self.Column = self.env["materials.catalog.column"]
        self.parent = self.env.ref("southbrook_mrp_kitchen_tools.cat_screws")
        self.child = self.env.ref(
            "southbrook_mrp_kitchen_tools.cat_screw_confirmat")

    def _keys(self, category):
        payload = self.Provider.get_catalog(
            scope="tools", category_id=category.id)
        return [c["key"] for c in payload["columns"]]

    def test_generic_columns_always_present(self):
        keys = self._keys(self.child)
        self.assertEqual(keys[0], "name")
        self.assertIn("default_code", keys)

    def test_declared_column_appears(self):
        self.Column.create({
            "name": "Length (mm)", "category_id": self.parent.id,
            "field_name": "x_southbrook_screw_length_mm", "align": "right",
        })
        self.assertIn("x_southbrook_screw_length_mm", self._keys(self.parent))

    def test_ancestor_columns_inherited_by_child(self):
        self.Column.create({
            "name": "Length (mm)", "category_id": self.parent.id,
            "field_name": "x_southbrook_screw_length_mm",
        })
        self.assertIn("x_southbrook_screw_length_mm", self._keys(self.child))

    def test_child_declaration_overrides_ancestor_label(self):
        self.Column.create({
            "name": "Length (mm)", "category_id": self.parent.id,
            "field_name": "x_southbrook_screw_length_mm",
        })
        self.Column.create({
            "name": "Screw length", "category_id": self.child.id,
            "field_name": "x_southbrook_screw_length_mm",
        })
        payload = self.Provider.get_catalog(
            scope="tools", category_id=self.child.id)
        labels = {c["key"]: c["label"] for c in payload["columns"]}
        self.assertEqual(labels["x_southbrook_screw_length_mm"], "Screw length")
