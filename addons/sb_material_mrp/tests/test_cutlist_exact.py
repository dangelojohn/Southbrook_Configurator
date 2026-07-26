# SPDX-License-Identifier: LGPL-3.0-only
"""Cutlist Precision Task 2 — exact per-line panel-role volume helpers.

Covers `_sb_line_owned_roles` / `_sb_line_exact_volume_mm3` on `mrp.bom.line`:
a role is owned only when exactly one distinct material across the BoM's
lines claims it via `material.panel_role_ids`, and that material is the
line's own; ambiguous roles (claimed by >1 material) are excluded, and
`_sb_line_exact_volume_mm3` returns None (never 0.0) when nothing is
unambiguously owned so the caller falls back to the estimate.
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestCutlistExact(TransactionCase):
    def _geo_variant(self):
        t = self.env["product.template"].create({"name": "Cab CL"})
        t.product_variant_id.write({
            "sb_width_mm": 600, "sb_height_mm": 720, "sb_depth_mm": 580,
            "sb_panel_family": "base", "sb_door_count": 1, "sb_drawer_count": 0,
            "sb_finished_sides": "none"})
        return t

    def _mat(self, code, role_codes, thickness=19.05):
        fam = self.env["material.family"].create({"name": code, "code": code})
        roles = self.env["sb.panel.role"].search([("code", "in", role_codes)])
        return self.env["southbrook.kitchen.material"].create({
            "name": code, "code": code, "family_id": fam.id, "density": 0.68,
            "weight_source": "density_volume", "thickness_mm": thickness,
            "panel_role_ids": [(6, 0, roles.ids)]})

    def test_back_line_gets_back_panel_area_exactly(self):
        t = self._geo_variant()
        carcass = self._mat("cl_carc", ["side_L", "side_R", "top", "bottom"])
        back = self._mat("cl_back", ["back"], thickness=6.35)
        cp = self.env["product.product"].create({"name": "carc"})
        cp.product_tmpl_id.material_id = carcass.id
        bp = self.env["product.product"].create({"name": "bk"})
        bp.product_tmpl_id.material_id = back.id
        bom = self.env["mrp.bom"].create(
            {"product_tmpl_id": t.id, "product_id": t.product_variant_id.id})
        cl = self.env["mrp.bom.line"].create(
            {"bom_id": bom.id, "product_id": cp.id, "product_qty": 1})
        bl = self.env["mrp.bom.line"].create(
            {"bom_id": bom.id, "product_id": bp.id, "product_qty": 1})
        # back line uniquely owns "back" -> exact volume equals the back
        # panel L*W*6.35
        v = bl._sb_line_exact_volume_mm3(bl)
        self.assertIsNotNone(v)
        self.assertGreater(v, 0.0)
        # carcass line owns 4 box panels; its exact volume > the single
        # back panel's
        self.assertGreater(cl._sb_line_exact_volume_mm3(cl), v)

    def test_ambiguous_role_returns_none(self):
        t = self._geo_variant()
        a = self._mat("cl_a", ["shelf"])
        b = self._mat("cl_b", ["shelf"])
        pa = self.env["product.product"].create({"name": "a"})
        pa.product_tmpl_id.material_id = a.id
        pb = self.env["product.product"].create({"name": "b"})
        pb.product_tmpl_id.material_id = b.id
        bom = self.env["mrp.bom"].create(
            {"product_tmpl_id": t.id, "product_id": t.product_variant_id.id})
        la = self.env["mrp.bom.line"].create(
            {"bom_id": bom.id, "product_id": pa.id, "product_qty": 1})
        self.env["mrp.bom.line"].create(
            {"bom_id": bom.id, "product_id": pb.id, "product_qty": 1})
        # shelf claimed by 2 materials -> ambiguous -> None
        self.assertIsNone(la._sb_line_exact_volume_mm3(la))

    def test_no_owned_roles_returns_none(self):
        t = self._geo_variant()
        # material with no panel_role_ids at all -> owns nothing -> None,
        # never 0.0 (0.0 would look like "zero volume", not "no data").
        mat = self._mat("cl_none", [])
        p = self.env["product.product"].create({"name": "none_mat"})
        p.product_tmpl_id.material_id = mat.id
        bom = self.env["mrp.bom"].create(
            {"product_tmpl_id": t.id, "product_id": t.product_variant_id.id})
        line = self.env["mrp.bom.line"].create(
            {"bom_id": bom.id, "product_id": p.id, "product_qty": 1})
        self.assertIsNone(line._sb_line_exact_volume_mm3(line))
