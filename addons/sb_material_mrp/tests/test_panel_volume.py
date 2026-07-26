# SPDX-License-Identifier: LGPL-3.0-only
"""Task A4 — `_panel_volume_mm3` reads the cabinet variant's geometry
(southbrook_estimating.product.product._sb_geometry_inputs(), Task A1)
and returns the real carcass-panel volume via
`mrp.bom._compute_panel_dimensions()`, instead of the honest-0.0 stub.

Wiring pattern for material -> component product mirrors
test_weight_rollup_multilevel.py's `_material_product` helper: a
`product.attribute.value` carries `material_id`; a variant that has that
attribute value in its `product_template_attribute_value_ids` resolves to
the material via `_resolve_material()` (sb_material_core).
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_material")
class TestPanelVolume(TransactionCase):

    def _density_volume_component(self, name="Melamine 5/8"):
        """A generic component product whose variant resolves to a
        density_volume material via the real attribute->material link."""
        mat = self.env["southbrook.kitchen.material"].create(
            {"name": name, "code": name, "density": 0.65,
             "weight_source": "density_volume"})
        attr = self.env["product.attribute"].create(
            {"name": "Material-%s" % name})
        val = self.env["product.attribute.value"].create(
            {"name": name, "attribute_id": attr.id, "material_id": mat.id})
        tmpl = self.env["product.template"].create({
            "name": name, "type": "consu",
            "attribute_line_ids": [(0, 0, {
                "attribute_id": attr.id, "value_ids": [(6, 0, [val.id])]})],
        })
        variant = tmpl.product_variant_ids[:1]
        self.assertEqual(variant._resolve_material(), mat)  # link works
        return variant

    def _cabinet_bom(self, with_geometry):
        """A cabinet variant (+ its BoM) with or without stored geometry."""
        vals = {"name": "Cab", "type": "consu"}
        if with_geometry:
            vals.update({
                "sb_width_mm": 600, "sb_height_mm": 762, "sb_depth_mm": 600,
                "sb_panel_family": "base", "sb_door_count": 1,
            })
        cab = self.env["product.product"].create(vals)
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": cab.product_tmpl_id.id,
            "product_id": cab.id,
        })
        return bom

    def test_panel_volume_nonzero_with_geometry(self):
        bom = self._cabinet_bom(with_geometry=True)
        component = self._density_volume_component()
        line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": component.id, "product_qty": 1,
        })
        self.assertGreater(line._panel_volume_mm3(line), 0.0)
        # end-to-end through the compute chain too
        self.assertGreater(line.component_weight_kg, 0.0)

    def test_panel_volume_zero_without_geometry(self):
        bom = self._cabinet_bom(with_geometry=False)
        component = self._density_volume_component("Melamine 5/8 (no-geo)")
        line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": component.id, "product_qty": 1,
        })
        self.assertEqual(line._panel_volume_mm3(line), 0.0)
        self.assertEqual(line.component_weight_kg, 0.0)
