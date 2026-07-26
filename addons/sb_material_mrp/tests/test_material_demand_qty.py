# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestMaterialDemandQty(TransactionCase):
    def _make_cabinet_bom(self, weight_source, thickness_mm):
        # NOTE: code suffixed with thickness_mm — the brief's original test
        # calls this helper twice in test_density_volume_demand_is_area_m2
        # (19.05 then 12.70) within the SAME TransactionCase test method, so
        # a fixed "ew_dq"/"sheet_dq" code collided with sb_material_core's
        # unique(code) constraint on material.family/southbrook.kitchen.
        # material. Suffixing keeps both calls unique without changing the
        # test's intent (compare demand across two distinct thicknesses).
        suffix = str(thickness_mm).replace(".", "_")
        fam = self.env["material.family"].create({"name": "EW", "code": f"ew_dq_{suffix}"})
        mat = self.env["southbrook.kitchen.material"].create({
            "name": f"Sheet {suffix}", "code": f"sheet_dq_{suffix}", "family_id": fam.id,
            "density": 0.68, "weight_source": weight_source,
            "thickness_mm": thickness_mm,
        })
        # a cabinet variant carrying real geometry
        tmpl = self.env["product.template"].create({"name": "Cab DQ"})
        variant = tmpl.product_variant_id
        variant.write({
            "sb_width_mm": 600, "sb_height_mm": 720, "sb_depth_mm": 580,
            "sb_panel_family": "base", "sb_door_count": 1, "sb_drawer_count": 0,
            "sb_finished_sides": "none",
        })
        comp = self.env["product.product"].create({"name": "Comp DQ"})
        comp.product_tmpl_id.material_id = mat.id
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": tmpl.id, "product_id": variant.id, "product_qty": 1.0,
        })
        line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": comp.id, "product_qty": 1.0,
        })
        return mat, line

    def test_density_volume_demand_is_area_m2(self):
        mat, line = self._make_cabinet_bom("density_volume", 19.05)
        # area = carcass volume / thickness / 1e6, and must be > 0
        self.assertGreater(line.material_demand_qty, 0.0)
        # thinner sheet, same geometry -> larger area for the same volume share
        mat2, line2 = self._make_cabinet_bom("density_volume", 12.70)
        self.assertGreater(line2.material_demand_qty, line.material_demand_qty)

    def test_per_unit_demand_equals_product_qty(self):
        fam = self.env["material.family"].create({"name": "HW", "code": "hw_dq"})
        mat = self.env["southbrook.kitchen.material"].create({
            "name": "Hinge", "code": "hinge_dq", "family_id": fam.id,
            "weight_source": "per_unit", "weight_per_unit": 0.05,
        })
        tmpl = self.env["product.template"].create({"name": "Cab HW"})
        comp = self.env["product.product"].create({"name": "Comp HW"})
        comp.product_tmpl_id.material_id = mat.id
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": tmpl.id, "product_id": tmpl.product_variant_id.id,
        })
        line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": comp.id, "product_qty": 4.0,
        })
        self.assertEqual(line.material_demand_qty, 4.0)

    def test_no_geometry_is_zero(self):
        mat, line = self._make_cabinet_bom("density_volume", 19.05)
        line.bom_id.product_id.write({"sb_width_mm": 0, "sb_height_mm": 0, "sb_depth_mm": 0})
        line.invalidate_recordset(["material_demand_qty"])
        # recompute
        line._compute_material_demand_qty()
        self.assertEqual(line.material_demand_qty, 0.0)

    def test_mixed_qty_density_demand_scales_with_product_qty(self):
        """Locks C-1: the density_volume/area branch must multiply the
        per-unit sibling SHARE by `line.product_qty`, exactly like the
        weight path and the linear branch already do. Before the fix, both
        lines below got the identical un-multiplied share (line B was NOT
        3x line A, and the BoM's total demand came out to HALF a carcass
        instead of one whole carcass) — this test fails on the pre-fix
        formula and passes once `vol * line.product_qty` is applied.
        """
        # Baseline: a single density_volume line at qty=1 (sibling total=1,
        # so its share IS the full carcass) — this is the reference "one
        # carcass area" the two-line BoM below must sum back up to.
        _mat_single, line_single = self._make_cabinet_bom("density_volume", 19.05)
        baseline_full_carcass_demand = line_single.material_demand_qty
        self.assertGreater(baseline_full_carcass_demand, 0.0)

        # Two density_volume lines on ONE BoM, same sheet material, sharing
        # the SAME cabinet geometry, with product_qty 1 and 3 (sibling
        # total_qty = 4) — the hand-built/imported-BoM class the
        # sibling-share attribution logic was written for.
        fam = self.env["material.family"].create({"name": "EW", "code": "ew_dq_mix"})
        mat = self.env["southbrook.kitchen.material"].create({
            "name": "Sheet Mix", "code": "sheet_dq_mix", "family_id": fam.id,
            "density": 0.68, "weight_source": "density_volume",
            "thickness_mm": 19.05,
        })
        tmpl = self.env["product.template"].create({"name": "Cab DQ Mix"})
        variant = tmpl.product_variant_id
        variant.write({
            "sb_width_mm": 600, "sb_height_mm": 720, "sb_depth_mm": 580,
            "sb_panel_family": "base", "sb_door_count": 1, "sb_drawer_count": 0,
            "sb_finished_sides": "none",
        })
        comp_a = self.env["product.product"].create({"name": "Comp DQ Mix A"})
        comp_a.product_tmpl_id.material_id = mat.id
        comp_b = self.env["product.product"].create({"name": "Comp DQ Mix B"})
        comp_b.product_tmpl_id.material_id = mat.id
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": tmpl.id, "product_id": variant.id, "product_qty": 1.0,
        })
        line_a = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": comp_a.id, "product_qty": 1.0,
        })
        line_b = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": comp_b.id, "product_qty": 3.0,
        })

        # Line B (qty=3) must demand 3x line A (qty=1) — pre-fix they were
        # equal (both got the raw un-multiplied share). Tolerance matches
        # the field's own stored precision (digits=(12, 4) — each line's
        # value is HALF-UP rounded to 4dp before this comparison, so a
        # tighter delta would just be asserting on rounding noise).
        self.assertAlmostEqual(
            line_b.material_demand_qty, 3.0 * line_a.material_demand_qty, delta=0.0005
        )
        # The BoM's total demand across both sibling lines must equal one
        # whole carcass area — pre-fix it summed to half a carcass.
        self.assertAlmostEqual(
            line_a.material_demand_qty + line_b.material_demand_qty,
            baseline_full_carcass_demand,
            delta=0.0005,
        )

    def test_linear_density_demand_scales_with_product_qty(self):
        """Cheap linear_density (edgebanding) demand sanity check: demand
        must be > 0 with real geometry, and scale with product_qty exactly
        like the density branch (both call the same *product_qty pattern).
        """
        fam = self.env["material.family"].create({"name": "EB", "code": "eb_dq"})
        mat = self.env["southbrook.kitchen.material"].create({
            "name": "Edgeband", "code": "edgeband_dq", "family_id": fam.id,
            "weight_source": "linear_density", "linear_density": 0.01,
        })
        tmpl = self.env["product.template"].create({"name": "Cab EB"})
        variant = tmpl.product_variant_id
        variant.write({
            "sb_width_mm": 600, "sb_height_mm": 720, "sb_depth_mm": 580,
            "sb_panel_family": "base", "sb_door_count": 1, "sb_drawer_count": 0,
            "sb_finished_sides": "front",
        })
        comp = self.env["product.product"].create({"name": "Comp EB"})
        comp.product_tmpl_id.material_id = mat.id
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": tmpl.id, "product_id": variant.id, "product_qty": 1.0,
        })
        line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": comp.id, "product_qty": 2.0,
        })
        self.assertGreater(line.material_demand_qty, 0.0)
        line2 = line.copy({"product_qty": 4.0})
        self.assertAlmostEqual(
            line2.material_demand_qty, 2.0 * line.material_demand_qty, places=6
        )
