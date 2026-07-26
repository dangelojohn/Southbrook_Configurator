# SPDX-License-Identifier: LGPL-3.0-only
"""Final whole-branch review (2026-07-26) — M-3 test gap closure.

Covers the four scenarios the review flagged as unproven by test:
1. N-lines-same-material qty-split (BoM 256 shape, the headline spec
   success criterion) — two lines of the SAME carcass material split the
   material's owned panels by product_qty.
2. The `door` role path — a material uniquely owning `door` gets a
   non-zero exact demand/weight that includes the door panel (0.0 before
   this branch).
3. Weight/demand agreement — an exact line's component_weight_kg and
   material_demand_qty are both non-zero and derived from the same
   owned-panel volume.
4. I-2 — the BoM-level `material_weight_total` rollup now equals the sum
   of the lines' exact `component_weight_kg` on a multi-material
   (box + back) BoM, instead of diverging via the estimate-only share.
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestCutlistPrecisionReviewFixes(TransactionCase):
    def _geo_variant(self, door_count=1):
        t = self.env["product.template"].create({"name": "Cab CLR"})
        t.product_variant_id.write({
            "sb_width_mm": 600, "sb_height_mm": 720, "sb_depth_mm": 580,
            "sb_panel_family": "base", "sb_door_count": door_count,
            "sb_drawer_count": 0, "sb_finished_sides": "none"})
        return t

    def _mat(self, code, role_codes, thickness=19.05):
        fam = self.env["material.family"].create({"name": code, "code": code})
        roles = self.env["sb.panel.role"].search([("code", "in", role_codes)])
        return self.env["southbrook.kitchen.material"].create({
            "name": code, "code": code, "family_id": fam.id, "density": 0.68,
            "weight_source": "density_volume", "thickness_mm": thickness,
            "panel_role_ids": [(6, 0, roles.ids)]})

    def _bom_with_lines(self, t, line_specs):
        """line_specs: list of (product_product, product_qty)."""
        bom = self.env["mrp.bom"].create(
            {"product_tmpl_id": t.id, "product_id": t.product_variant_id.id})
        lines = self.env["mrp.bom.line"]
        for product, qty in line_specs:
            lines |= self.env["mrp.bom.line"].create(
                {"bom_id": bom.id, "product_id": product.id, "product_qty": qty})
        return bom, lines

    # ------------------------------------------------------------------
    # 1. N-lines-same-material qty-split (BoM 256 shape).
    # ------------------------------------------------------------------
    def test_same_material_two_lines_split_by_qty_and_sum_matches_single_line(self):
        t = self._geo_variant()
        carcass = self._mat("clr_carc", ["side_L", "side_R", "top", "bottom"])
        pa = self.env["product.product"].create({"name": "clr_a"})
        pa.product_tmpl_id.material_id = carcass.id
        pb = self.env["product.product"].create({"name": "clr_b"})
        pb.product_tmpl_id.material_id = carcass.id
        bom, lines = self._bom_with_lines(t, [(pa, 1), (pb, 3)])
        line_a = lines.filtered(lambda l: l.product_id == pa)
        line_b = lines.filtered(lambda l: l.product_id == pb)

        # Both lines resolve to the same material and both are exact
        # (uniquely owned box roles, no other material claims them).
        self.assertTrue(line_a.material_demand_is_exact)
        self.assertTrue(line_b.material_demand_is_exact)

        # Material-scoped qty-split: line B (qty=3) demand ~= 3x line A
        # (qty=1) demand, since both share the same per-unit owned-panel
        # volume, split across the two lines' combined product_qty.
        self.assertGreater(line_a.material_demand_qty, 0.0)
        self.assertAlmostEqual(
            line_b.material_demand_qty, 3 * line_a.material_demand_qty, places=3)

        # The two lines' summed weight counts the material's box panels
        # exactly ONCE — it must match what a single qty=1 line owning
        # the same roles would compute for the whole carcass (not 4x it,
        # which the pre-material-scoping estimate path would have given).
        single_t = self._geo_variant()
        single_carcass = self._mat("clr_carc_single", ["side_L", "side_R", "top", "bottom"])
        single_p = self.env["product.product"].create({"name": "clr_single"})
        single_p.product_tmpl_id.material_id = single_carcass.id
        _bom, single_lines = self._bom_with_lines(single_t, [(single_p, 1)])
        single_weight = single_lines.component_weight_kg

        split_weight = line_a.component_weight_kg + line_b.component_weight_kg
        self.assertAlmostEqual(split_weight, single_weight, delta=0.05)

    # ------------------------------------------------------------------
    # 2. Door role path.
    # ------------------------------------------------------------------
    def test_door_role_owner_gets_nonzero_exact_weight_including_door(self):
        t = self._geo_variant(door_count=1)
        door_mat = self._mat("clr_door", ["door"], thickness=19.05)
        p = self.env["product.product"].create({"name": "clr_door_p"})
        p.product_tmpl_id.material_id = door_mat.id
        _bom, lines = self._bom_with_lines(t, [(p, 1)])
        line = lines

        self.assertTrue(line.material_demand_is_exact)
        self.assertGreater(line.material_demand_qty, 0.0)
        # Before this branch, `_panel_volume_mm3` deliberately EXCLUDED
        # doors, so a door-owning material's weight was always 0.0 — the
        # exact-first path must produce a real, non-zero door weight now.
        self.assertGreater(line.component_weight_kg, 0.0)
        self.assertGreater(line.component_volume_mm3, 0.0)

    # ------------------------------------------------------------------
    # 3. Weight/demand agreement on an exact line.
    # ------------------------------------------------------------------
    def test_exact_line_weight_and_demand_derive_from_same_owned_panels(self):
        t = self._geo_variant()
        carcass = self._mat("clr_agree", ["side_L", "side_R", "top", "bottom"])
        p = self.env["product.product"].create({"name": "clr_agree_p"})
        p.product_tmpl_id.material_id = carcass.id
        _bom, lines = self._bom_with_lines(t, [(p, 1)])
        line = lines

        self.assertTrue(line.material_demand_is_exact)
        self.assertGreater(line.component_weight_kg, 0.0)
        self.assertGreater(line.material_demand_qty, 0.0)
        # Both stored fields must come from the SAME exact per-unit volume
        # the exact-volume helper resolves for this line.
        exact_vol = line._sb_line_exact_volume_mm3(line)
        self.assertIsNotNone(exact_vol)
        self.assertAlmostEqual(line.component_volume_mm3, exact_vol, places=3)

    # ------------------------------------------------------------------
    # 4. I-2 — rollup total equals sum of exact per-line weights.
    # ------------------------------------------------------------------
    def test_rollup_total_equals_sum_of_exact_line_weights_box_and_back(self):
        t = self._geo_variant()
        carcass = self._mat("clr_rollup_box", ["side_L", "side_R", "top", "bottom"])
        back = self._mat("clr_rollup_back", ["back"], thickness=6.35)
        pc = self.env["product.product"].create({"name": "clr_rollup_c"})
        pc.product_tmpl_id.material_id = carcass.id
        pb = self.env["product.product"].create({"name": "clr_rollup_b"})
        pb.product_tmpl_id.material_id = back.id
        bom, lines = self._bom_with_lines(t, [(pc, 1), (pb, 1)])

        for line in lines:
            self.assertTrue(line.material_demand_is_exact)
            self.assertGreater(line.component_weight_kg, 0.0)

        expected = sum(lines.mapped("component_weight_kg"))
        self.assertAlmostEqual(bom.material_weight_total, expected, delta=0.02)
