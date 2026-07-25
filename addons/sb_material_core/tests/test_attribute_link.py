# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_material")
class TestAttributeLink(TransactionCase):
    def test_value_carries_material(self):
        mat = self.env["southbrook.kitchen.material"].create(
            {"name": "Maple Ply 18", "code": "MPL18", "density": 0.62})
        attr = self.env["product.attribute"].create({"name": "Material"})
        val = self.env["product.attribute.value"].create(
            {"name": "Maple Ply 18", "attribute_id": attr.id, "material_id": mat.id})
        self.assertEqual(val.material_id, mat)
