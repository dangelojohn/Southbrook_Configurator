# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.sb_material_core.models.southbrook_kitchen_material import (
    FAMILY_DEFAULT_DENSITY,
)


@tagged("post_install", "-at_install", "southbrook", "sbk_material")
class TestMaterialFields(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Mat = self.env["southbrook.kitchen.material"]
        self.Fam = self.env["material.family"]
        self.fam_ply = self.env.ref("sb_material_core.fam_ewood_ply")
        self.fam_ewood = self.env.ref("sb_material_core.fam_ewood")

    def test_effective_density_uses_own_value(self):
        m = self.Mat.create({"name": "Walnut Ply 18", "code": "WPL18",
                             "family_id": self.fam_ply.id, "density": 0.65,
                             "density_source": "material"})
        self.assertEqual(m.effective_density, 0.65)

    def test_effective_density_falls_back_to_family_default(self):
        # family default density lives on family via a fallback map; when the
        # material has none and density_source=family_default, effective!=0
        #
        # FIX-E (repair wave 1, finding #14) — this test implicitly relies
        # on the seeded `sb_material_core.fam_ewood_ply` family's `code`
        # ("ewood_ply") being a key in `FAMILY_DEFAULT_DENSITY`
        # (models/southbrook_kitchen_material.py). If that seed data or
        # the dict ever drifted out of sync, `effective_density` would
        # silently fall through to 0.0 for an unrelated reason (no
        # matching code anywhere up the parent chain) and this assertion
        # would fail with no clue why. Make the assumption explicit and
        # self-diagnosing instead of discovering it via a confusing
        # downstream failure.
        self.assertIn(
            self.fam_ply.code, FAMILY_DEFAULT_DENSITY,
            "test setup assumption: sb_material_core.fam_ewood_ply's own "
            "code must be a FAMILY_DEFAULT_DENSITY key for this test to "
            "exercise the direct-family fallback (not the parent walk-up, "
            "which is covered separately below)",
        )
        m = self.Mat.create({"name": "Generic Ply", "code": "GPL",
                             "family_id": self.fam_ply.id, "density": 0.0,
                             "density_source": "family_default"})
        self.assertEqual(
            m.effective_density, FAMILY_DEFAULT_DENSITY[self.fam_ply.code],
        )

    def test_thickness_mm_defaults_to_zero(self):
        # Task C1: thickness_mm defaults to 0.0 (= "use the cut-constant
        # thickness in the weight calc", never fabricated).
        m = self.Mat.create({"name": "No Thickness Set", "code": "NTS"})
        self.assertEqual(m.thickness_mm, 0.0)

    def test_thickness_mm_can_be_set_to_real_sheet_thickness(self):
        # 1/2" = 12.70mm, 5/8" = 15.875mm, 3/4" = 19.05mm.
        m = self.Mat.create({"name": "Half Inch Ply", "code": "HIP",
                             "thickness_mm": 12.70})
        self.assertEqual(m.thickness_mm, 12.70)

    def test_effective_density_walks_up_to_grandparent_default(self):
        # child family's own code is NOT in FAMILY_DEFAULT_DENSITY, only its
        # parent (fam_ewood, code "ewood" -> 0.68) is; effective_density must
        # walk up the parent chain rather than stopping at the direct family.
        fam_child = self.Fam.create({
            "name": "Exotic Ewood Sub-Grade",
            "code": "ewood_exotic_subgrade",
            "parent_id": self.fam_ewood.id,
        })
        m = self.Mat.create({"name": "Exotic Ewood Panel", "code": "EEP",
                             "family_id": fam_child.id, "density": 0.0,
                             "density_source": "family_default"})
        self.assertEqual(m.effective_density, 0.68)
