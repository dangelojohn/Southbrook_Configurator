# SPDX-License-Identifier: LGPL-3.0-only
"""Hygiene A2 — thickness-specific materials for the 2 live legacy
sheet components (`RM-MELAMINE_WHITE_5_8`, `RM-HARDBOARD_1_4`) that
previously resolved to the GENERIC `melamine`/`mdf` materials, which
carry no `thickness_mm` and so silently fell back to the 3/4"=19.05mm
cut constant in `material_demand_qty`'s area calc -- under-stating the
true panel area for these thinner sheets.

Part 1 proves the new seed materials (`mat_mel_58`, `mat_hardboard_14`)
exist with the correct thickness_mm and a positive effective_density.

Part 2 proves thickness now actually DRIVES the computed area: a
component resolving to the 1/4"=6.35mm material must yield a strictly
LARGER `material_demand_qty` than the identical cabinet geometry
resolved through a 3/4"=19.05mm material -- i.e. the old fallback was
genuinely under-stating area, and setting the correct thickness fixes
it. `material_demand_qty` lives on `mrp.bom.line` (sb_material_mrp),
which is NOT a manifest dependency of sb_material_core (the reverse is
true) -- Part 2 soft-skips when that field is not present in the
registry (module installed standalone), mirroring the soft-guard
pattern in migrations/19.0.1.5.0/post-migrate.py.

Fixture/wiring pattern mirrors sb_material_mrp's
tests/test_material_thickness.py `_density_volume_component` /
`_cabinet_bom` helpers exactly.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_material")
class TestThicknessSpecificMaterials(TransactionCase):

    def setUp(self):
        super().setUp()
        self.mat_mel_58 = self.env.ref("sb_material_core.mat_mel_58")
        self.mat_hardboard_14 = self.env.ref("sb_material_core.mat_hardboard_14")

    # -- Part 1: the seed materials themselves -----------------------

    def test_mat_mel_58_thickness_and_density(self):
        m = self.mat_mel_58
        self.assertEqual(m.code, "MEL58")
        self.assertTrue(m.family_id)
        self.assertEqual(m.thickness_mm, 15.875)
        self.assertAlmostEqual(m.thickness_in, 15.875 / 25.4, delta=0.001)
        self.assertGreater(m.effective_density, 0.0)

    def test_mat_hardboard_14_thickness_and_density(self):
        m = self.mat_hardboard_14
        self.assertEqual(m.code, "HB14")
        self.assertTrue(m.family_id)
        self.assertEqual(m.thickness_mm, 6.35)
        self.assertAlmostEqual(m.thickness_in, 6.35 / 25.4, delta=0.001)
        self.assertGreater(m.effective_density, 0.0)

    def test_material_codes_are_unique_and_distinct(self):
        # sb_material_core enforces unique(code) -- assert the two new
        # codes are distinct from each other and from the generic
        # materials they are replacing for these 2 components.
        self.assertNotEqual(self.mat_mel_58.code, self.mat_hardboard_14.code)
        self.assertNotIn(self.mat_mel_58.code, ("melamine", "mdf"))
        self.assertNotIn(self.mat_hardboard_14.code, ("melamine", "mdf"))

    # -- Part 2: thickness now drives the computed area ---------------

    def _cabinet_bom(self, name):
        """A cabinet variant (real, non-fabricated stored geometry)
        plus its BoM -- mirrors test_material_thickness.py exactly."""
        cab = self.env["product.product"].create({
            "name": name, "type": "consu",
            "sb_width_mm": 600, "sb_height_mm": 762, "sb_depth_mm": 600,
            "sb_panel_family": "base", "sb_door_count": 1,
        })
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": cab.product_tmpl_id.id,
            "product_id": cab.id,
        })
        return bom

    def _line_for_material(self, material, name):
        bom = self._cabinet_bom(name)
        attr = self.env["product.attribute"].create({"name": "Material-%s" % name})
        val = self.env["product.attribute.value"].create(
            {"name": name, "attribute_id": attr.id, "material_id": material.id})
        tmpl = self.env["product.template"].create({
            "name": name, "type": "consu",
            "attribute_line_ids": [(0, 0, {
                "attribute_id": attr.id, "value_ids": [(6, 0, [val.id])]})],
        })
        component = tmpl.product_variant_ids[:1]
        self.assertEqual(component._resolve_material(), material)
        return self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": component.id, "product_qty": 1,
        })

    def test_hardboard_14mm_yields_larger_demand_qty_than_34in(self):
        BomLine = self.env["mrp.bom.line"]
        if "material_demand_qty" not in BomLine._fields:
            self.skipTest(
                "sb_material_mrp not installed -- material_demand_qty "
                "field absent (sb_material_core standalone install).")
        if not hasattr(self.env["mrp.bom"], "_compute_panel_dimensions"):
            self.skipTest(
                "southbrook_estimating not installed -- no geometry "
                "source for _panel_volume_mm3.")

        # Cutlist Precision Task 4 seeded mat_hardboard_14.panel_role_ids
        # = ['back']. On THIS test's synthetic single-line BoM that role
        # is uniquely owned (only material on the BoM), which activates
        # Task 2/3's exact-panel-volume path -- a pure area calc that is
        # thickness-INDEPENDENT by design (`vol / th` cancels `th`), so
        # it can no longer demonstrate the thickness-driven area
        # difference this test exists to prove (Hygiene A2's fix to the
        # ESTIMATE path's cut-constant fallback). Clear the role for the
        # duration of this test only (TransactionCase rolls it back) to
        # keep this test isolated to the estimate-path math it targets;
        # the exact-path behavior itself is covered by
        # sb_material_mrp/tests/test_cutlist_exact.py.
        self.mat_hardboard_14.write({"panel_role_ids": [(5, 0, 0)]})

        # Control: identical cabinet geometry, but resolved through a
        # 3/4"=19.05mm material (the OLD fallback thickness both
        # RM-MELAMINE_WHITE_5_8 and RM-HARDBOARD_1_4 used to get from
        # the generic melamine/mdf material's unset thickness_mm).
        control_mat = self.env["southbrook.kitchen.material"].create({
            "name": "Control 3/4 (A2)", "code": "A2-CTRL-34",
            "density": 0.68, "weight_source": "density_volume",
            "thickness_mm": 19.05,
        })
        control_line = self._line_for_material(control_mat, "A2-Control-34")
        hardboard_line = self._line_for_material(
            self.mat_hardboard_14, "A2-Hardboard-14")

        self.assertGreater(control_line.material_demand_qty, 0.0)
        self.assertGreater(hardboard_line.material_demand_qty, 0.0)
        self.assertGreater(
            hardboard_line.material_demand_qty,
            control_line.material_demand_qty,
            "the 1/4\"=6.35mm material must yield a LARGER "
            "material_demand_qty (area) than the same cabinet geometry "
            "resolved through a 3/4\"=19.05mm material -- proving the "
            "old cut-constant fallback was under-stating area for the "
            "thinner sheet, and the thickness-specific material now "
            "drives the correct, larger figure.",
        )
