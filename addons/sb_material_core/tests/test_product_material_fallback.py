# SPDX-License-Identifier: LGPL-3.0-only
"""Repair Wave 3 — product.template.material_id fallback for
`product.product._resolve_material()`.

BoM component products (e.g. sheet goods) are plain products with no
attributes, so before this wave `_resolve_material()` had no way to
resolve a material for them at all — it only ever walked the 'Material'
attribute value. These tests cover the three resolution states plus the
precedence rule (attribute path still wins when both are present).
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_material")
class TestProductMaterialFallback(TransactionCase):
    def _material(self, code, **vals):
        return self.env["southbrook.kitchen.material"].create(
            {"name": code, "code": code, **vals})

    def test_template_material_id_resolves_when_no_attributes(self):
        # A plain component product (no attributes at all) — the exact
        # shape of the 6 live BoM sheet-good components this wave fixes.
        mat = self._material("MEL34-FALLBACK", density=0.68)
        tmpl = self.env["product.template"].create({
            "name": "Melamine 3/4 Sheet", "type": "consu",
            "material_id": mat.id,
        })
        variant = tmpl.product_variant_ids[:1]
        self.assertEqual(variant._resolve_material(), mat)

    def test_attribute_value_path_wins_when_both_present(self):
        # Precedence must be unchanged: the attribute-value path resolves
        # FIRST even when the template also carries a (different)
        # fallback material_id.
        attr_mat = self._material("ATTR-MAT")
        tmpl_mat = self._material("TMPL-MAT")
        attr = self.env["product.attribute"].create({"name": "Material-Precedence"})
        val = self.env["product.attribute.value"].create(
            {"name": "Attr Value", "attribute_id": attr.id,
             "material_id": attr_mat.id})
        tmpl = self.env["product.template"].create({
            "name": "Both Paths Set", "type": "consu",
            "material_id": tmpl_mat.id,
            "attribute_line_ids": [(0, 0, {
                "attribute_id": attr.id, "value_ids": [(6, 0, [val.id])]})],
        })
        variant = tmpl.product_variant_ids[:1]
        self.assertEqual(variant._resolve_material(), attr_mat)
        self.assertNotEqual(variant._resolve_material(), tmpl_mat)

    def test_neither_set_returns_empty_recordset(self):
        # Honesty contract: no attribute-value material, no template
        # fallback -> empty recordset, never fabricated.
        tmpl = self.env["product.template"].create(
            {"name": "No Material At All", "type": "consu"})
        variant = tmpl.product_variant_ids[:1]
        resolved = variant._resolve_material()
        self.assertFalse(resolved)
        self.assertEqual(resolved._name, "southbrook.kitchen.material")
