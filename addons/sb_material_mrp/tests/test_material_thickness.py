# SPDX-License-Identifier: LGPL-3.0-only
"""Task C1 (weight-accuracy refinement): carcass panel weight must depend
on the resolved MATERIAL's actual sheet thickness
(`southbrook.kitchen.material.thickness_mm`, sb_material_core) rather than
always using the fixed cut constant (`box_th`) baked into
`mrp.bom._compute_panel_dimensions()`'s returned panel tuples.

Fixture/wiring pattern mirrors test_panel_volume.py's
`_density_volume_component` / `_cabinet_bom` helpers: a `product.attribute.
value` carries `material_id`; a component variant with that attribute value
in its `product_template_attribute_value_ids` resolves to the material via
`_resolve_material()` (sb_material_core).
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_material")
class TestMaterialThickness(TransactionCase):

    def _density_volume_component(self, name, thickness_mm=0.0):
        """A generic component product whose variant resolves to a
        density_volume material carrying the given thickness_mm (0.0 =
        unset -> falls back to the cut-constant thickness)."""
        mat = self.env["southbrook.kitchen.material"].create({
            "name": name, "code": name, "density": 0.65,
            "weight_source": "density_volume", "thickness_mm": thickness_mm,
        })
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

    def _cabinet_bom(self):
        """A cabinet variant (with real, non-fabricated stored geometry)
        plus its BoM."""
        cab = self.env["product.product"].create({
            "name": "Cab-Thickness", "type": "consu",
            "sb_width_mm": 600, "sb_height_mm": 762, "sb_depth_mm": 600,
            "sb_panel_family": "base", "sb_door_count": 1,
        })
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": cab.product_tmpl_id.id,
            "product_id": cab.id,
        })
        return bom

    def _line_for(self, thickness_mm, name):
        bom = self._cabinet_bom()
        component = self._density_volume_component(name, thickness_mm)
        return self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": component.id, "product_qty": 1,
        })

    def test_half_inch_carcass_weighs_less_than_three_quarter(self):
        """1/2\" (12.70mm) vs 3/4\" (19.05mm) sheet on the SAME cabinet
        geometry must yield strictly less volume/weight for the thinner
        material."""
        half_line = self._line_for(12.70, "Melamine 1/2 (C1)")
        three_qtr_line = self._line_for(19.05, "Melamine 3/4 (C1)")

        half_vol = half_line._panel_volume_mm3(half_line)
        three_qtr_vol = three_qtr_line._panel_volume_mm3(three_qtr_line)

        self.assertGreater(half_vol, 0.0)
        self.assertGreater(three_qtr_vol, 0.0)
        self.assertLess(half_vol, three_qtr_vol)
        self.assertLess(half_line.component_weight_kg,
                         three_qtr_line.component_weight_kg)

    def test_both_differ_from_cut_constant_unset_case(self):
        """When thickness_mm is 0.0/unset, the box panels fall back to the
        cut-constant thickness (p[2], A4 behavior) — a value distinct from
        both the 1/2\" and 3/4\" material-driven cases (cut constant is
        neither 12.70 nor 19.05 in the shipped defaults)."""
        half_line = self._line_for(12.70, "Melamine 1/2 (C1-b)")
        three_qtr_line = self._line_for(19.05, "Melamine 3/4 (C1-b)")
        unset_line = self._line_for(0.0, "Melamine unset (C1-b)")

        half_vol = half_line._panel_volume_mm3(half_line)
        three_qtr_vol = three_qtr_line._panel_volume_mm3(three_qtr_line)
        unset_vol = unset_line._panel_volume_mm3(unset_line)

        self.assertGreater(unset_vol, 0.0)
        self.assertNotEqual(unset_vol, half_vol)
        self.assertNotEqual(unset_vol, three_qtr_vol)

    def test_box_panel_ratio_matches_thickness_ratio(self):
        """The BOX panels (side_L, side_R, top, bottom, shelf) scale
        linearly with thickness since volume = l*w*th for each and l/w are
        identical between the two lines (same cabinet geometry). The BACK
        panel is excluded from the override (stays at its own cut-constant
        thickness) and is IDENTICAL between the two lines, so it must be
        subtracted out before checking the ratio on the box-only portion.
        """
        half_line = self._line_for(12.70, "Melamine 1/2 (C1-ratio)")
        three_qtr_line = self._line_for(19.05, "Melamine 3/4 (C1-ratio)")

        # Isolate the BACK panel volume (identical, cut-constant-driven,
        # for both lines) using the shared geometry helper directly.
        Bom = self.env["mrp.bom"]
        cab = half_line.bom_id.product_id
        geo = cab._sb_geometry_inputs()
        dims = Bom._compute_panel_dimensions(**geo)
        back = dims.get("back")
        back_vol = back[0] * back[1] * back[2] if back else 0.0

        half_box_vol = half_line._panel_volume_mm3(half_line) - back_vol
        three_qtr_box_vol = (
            three_qtr_line._panel_volume_mm3(three_qtr_line) - back_vol
        )

        self.assertGreater(half_box_vol, 0.0)
        self.assertGreater(three_qtr_box_vol, 0.0)

        expected_ratio = 19.05 / 12.70
        actual_ratio = three_qtr_box_vol / half_box_vol
        self.assertAlmostEqual(actual_ratio, expected_ratio, places=3)
