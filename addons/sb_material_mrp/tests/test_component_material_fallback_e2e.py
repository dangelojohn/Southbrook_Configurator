# SPDX-License-Identifier: LGPL-3.0-only
"""Repair Wave 3 — THE MONEY TEST.

The full chain: a cabinet variant with real geometry + a BoM component
product that resolves its material via the NEW `product.template.
material_id` fallback (sb_material_core), not an attribute value — the
exact shape of the 6 live sheet-good components this wave fixes (plain
products, no attributes). Before this wave, `_resolve_material()`
returned an empty recordset for such a component, so
`component_weight_kg` / `material_weight_total` multiplied to 0.00
despite geometry (Repair Wave 1) and density (Repair Wave 2) both being
live.

Mirrors `sb_material_mrp/tests/test_panel_volume.py`'s
`_cabinet_bom`/`_density_volume_component` pattern, swapping the
attribute-value component wiring for the template material_id fallback.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_material")
class TestComponentMaterialFallbackEndToEnd(TransactionCase):
    def _cabinet_bom(self):
        cab = self.env["product.product"].create({
            "name": "Cab (Wave 3 money test)", "type": "consu",
            "sb_width_mm": 600, "sb_height_mm": 762, "sb_depth_mm": 600,
            "sb_panel_family": "base", "sb_door_count": 1,
        })
        return self.env["mrp.bom"].create({
            "product_tmpl_id": cab.product_tmpl_id.id,
            "product_id": cab.id,
        })

    def _fallback_linked_component(self):
        """A plain component product (no attributes) that resolves its
        material ONLY via the Wave-3 product.template.material_id
        fallback — melamine 3/4in with real thickness + density."""
        mat = self.env["southbrook.kitchen.material"].create({
            "name": "Melamine 3/4 (Wave 3)", "code": "MEL34-W3",
            "density": 0.65, "weight_source": "density_volume",
            "thickness_mm": 19.05,
        })
        tmpl = self.env["product.template"].create({
            "name": "Melamine 3/4 Sheet (Wave 3)", "type": "consu",
            "material_id": mat.id,
        })
        variant = tmpl.product_variant_ids[:1]
        # Sanity: this component genuinely has no attributes -> the
        # fallback path, not the attribute-value path, is what resolves it.
        self.assertFalse(variant.product_template_attribute_value_ids)
        self.assertEqual(variant._resolve_material(), mat)
        return variant

    def test_money_geometry_times_thickness_times_density(self):
        bom = self._cabinet_bom()
        component = self._fallback_linked_component()
        line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": component.id, "product_qty": 1,
        })

        self.assertGreater(
            line.component_weight_kg, 0.0,
            "geometry x thickness x density must produce a non-zero "
            "line weight for a component linked only via the "
            "product.template.material_id fallback",
        )

        bom.invalidate_recordset()
        self.assertGreater(
            bom.material_weight_total, 0.0,
            "the BoM-level rollup must also be non-zero end-to-end",
        )
