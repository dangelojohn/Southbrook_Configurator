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

    def test_mo_material_weight_total_nonzero_end_to_end(self):
        """Task A5 (Increment-A gate): the geometry-driven rollup must reach
        `mrp.production.material_weight_total` (sb_material_mrp's Task 9
        field), not just the line-level `_panel_volume_mm3` helper (Task A4)
        or the BoM-level `material_weight_total` (Task 7). A configured
        cabinet's Manufacturing Order is the thing the brief asks to prove
        non-zero.
        """
        bom = self._cabinet_bom(with_geometry=True)
        component = self._density_volume_component("Melamine 5/8 (MO)")
        self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": component.id, "product_qty": 1,
        })
        bom.invalidate_recordset()
        self.assertGreater(bom.material_weight_total, 0.0)

        cab = bom.product_id
        cab.write({"is_storable": True})  # mrp.production wants a storable product
        mo = self.env["mrp.production"].create({
            "product_id": cab.id,
            "product_qty": 1.0,
            "bom_id": bom.id,
        })
        self.assertGreater(mo.material_weight_total, 0.0)

    def test_line_geometry_override_fields_exist_and_default_to_zero(self):
        """Task B1 (Increment B): verify that mrp.bom.line has the three
        per-line geometry override fields (sb_line_width_mm, sb_line_height_mm,
        sb_line_depth_mm) and that they all default to 0 (meaning "use variant
        geometry").
        """
        bom = self._cabinet_bom(with_geometry=True)
        component = self._density_volume_component("Melamine 5/8 (B1)")
        line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": component.id, "product_qty": 1,
        })

        # Verify all three fields exist
        self.assertTrue(hasattr(line, "sb_line_width_mm"))
        self.assertTrue(hasattr(line, "sb_line_height_mm"))
        self.assertTrue(hasattr(line, "sb_line_depth_mm"))

        # Verify all three fields default to 0
        self.assertEqual(line.sb_line_width_mm, 0)
        self.assertEqual(line.sb_line_height_mm, 0)
        self.assertEqual(line.sb_line_depth_mm, 0)

    def test_line_geometry_override_fields_can_be_set(self):
        """Task B1 (Increment B): verify that the per-line geometry override
        fields can be explicitly set to non-zero values (for drag-resized/
        filler placements, future use).
        """
        bom = self._cabinet_bom(with_geometry=True)
        component = self._density_volume_component("Melamine 5/8 (B1-set)")
        line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id,
            "product_id": component.id,
            "product_qty": 1,
            "sb_line_width_mm": 500,
            "sb_line_height_mm": 750,
            "sb_line_depth_mm": 600,
        })

        self.assertEqual(line.sb_line_width_mm, 500)
        self.assertEqual(line.sb_line_height_mm, 750)
        self.assertEqual(line.sb_line_depth_mm, 600)

    def test_panel_volume_prefers_line_override_over_variant(self):
        """Task B2: when all three sb_line_* overrides are set (>0) on the
        line, `_panel_volume_mm3` must build geometry from the LINE's own
        dims, not the variant's — proven by a bigger override (900x762x600)
        on a variant whose own geometry is smaller (600x762x600) yielding a
        strictly larger volume than the variant-only case.
        """
        bom = self._cabinet_bom(with_geometry=True)  # variant is 600x762x600
        component = self._density_volume_component("Melamine 5/8 (B2-override)")
        baseline_line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": component.id, "product_qty": 1,
        })
        baseline_volume = baseline_line._panel_volume_mm3(baseline_line)
        self.assertGreater(baseline_volume, 0.0)

        override_line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": component.id, "product_qty": 1,
            "sb_line_width_mm": 900, "sb_line_height_mm": 762,
            "sb_line_depth_mm": 600,
        })
        override_volume = override_line._panel_volume_mm3(override_line)
        self.assertGreater(override_volume, baseline_volume)

    def test_panel_volume_falls_back_to_variant_when_override_incomplete(self):
        """Task B2 regression: a line with the override left at the default
        0 (or only partially set) must still use the variant's own geometry
        (A4 behavior) — the merge only kicks in when ALL THREE line dims are
        set (>0).
        """
        bom = self._cabinet_bom(with_geometry=True)
        component = self._density_volume_component("Melamine 5/8 (B2-fallback)")
        baseline_line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": component.id, "product_qty": 1,
        })
        baseline_volume = baseline_line._panel_volume_mm3(baseline_line)

        zero_override_line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": component.id, "product_qty": 1,
            "sb_line_width_mm": 0, "sb_line_height_mm": 0,
            "sb_line_depth_mm": 0,
        })
        self.assertEqual(
            zero_override_line._panel_volume_mm3(zero_override_line),
            baseline_volume,
        )

        partial_override_line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": component.id, "product_qty": 1,
            "sb_line_width_mm": 900, "sb_line_height_mm": 0,
            "sb_line_depth_mm": 600,
        })
        self.assertEqual(
            partial_override_line._panel_volume_mm3(partial_override_line),
            baseline_volume,
        )
