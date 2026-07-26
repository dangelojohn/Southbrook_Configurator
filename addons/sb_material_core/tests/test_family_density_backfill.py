# SPDX-License-Identifier: LGPL-3.0-only
"""Repair Wave 2, Upgrade 1 — `_sb_backfill_family_density()`.

The 10 pre-existing `southbrook.kitchen.material` records seeded by
southbrook_mrp_kitchen_workcenters predate this module's `family_id`
field, so on the live DB they sit at family_id=False ->
effective_density=0. This is a unit test of the migration's mapping
function (called by sb_material_core/migrations/19.0.1.2.0/post-migrate.py),
exercised directly against the real seeded 'mdf' record rather than a
freshly-created one — `code` carries a unique constraint, and 'mdf' is
already taken by southbrook_mrp_kitchen_workcenters.material_mdf.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_material")
class TestFamilyDensityBackfill(TransactionCase):

    def test_material_with_no_family_gets_mapped(self):
        """code='mdf', family_id=False -> after the backfill, family_id
        is set and effective_density > 0."""
        mdf = self.env.ref("southbrook_mrp_kitchen_workcenters.material_mdf")
        mdf.family_id = False
        mdf.invalidate_recordset()
        self.assertFalse(mdf.family_id)

        self.env["southbrook.kitchen.material"]._sb_backfill_family_density()
        mdf.invalidate_recordset()

        self.assertEqual(mdf.family_id, self.env.ref("sb_material_core.fam_ewood"))
        self.assertGreater(mdf.effective_density, 0.0)

    def test_material_level_density_row_written_only_when_zero(self):
        """laminate maps to a material-level density override (1.35,
        density_source='material') per the CONFIRMED mapping — but only
        when the record's own density is currently 0 (never clobber a
        real value)."""
        laminate = self.env.ref("southbrook_mrp_kitchen_workcenters.material_laminate")
        laminate.write({"family_id": False, "density": 0.0})
        laminate.invalidate_recordset()

        self.env["southbrook.kitchen.material"]._sb_backfill_family_density()
        laminate.invalidate_recordset()

        self.assertEqual(laminate.family_id, self.env.ref("sb_material_core.fam_lam"))
        self.assertEqual(laminate.density, 1.35)
        self.assertEqual(laminate.density_source, "material")
        self.assertAlmostEqual(laminate.effective_density, 1.35)

    def test_material_that_already_has_a_family_is_untouched(self):
        """Idempotency / never clobbers a user's later family choice: a
        material with family_id already set is left exactly as-is, even
        if its code appears in the mapping table."""
        mdf = self.env.ref("southbrook_mrp_kitchen_workcenters.material_mdf")
        other_family = self.env.ref("sb_material_core.fam_swood")
        mdf.family_id = other_family
        mdf.invalidate_recordset()

        self.env["southbrook.kitchen.material"]._sb_backfill_family_density()
        mdf.invalidate_recordset()

        self.assertEqual(mdf.family_id, other_family)

    def test_rerun_is_a_noop_second_time(self):
        """Running the backfill twice must not error and must not
        change anything the second time (idempotent re-run, as the
        migration itself may execute more than once across DR /
        staging replays)."""
        mdf = self.env.ref("southbrook_mrp_kitchen_workcenters.material_mdf")
        mdf.family_id = False
        mdf.invalidate_recordset()

        Material = self.env["southbrook.kitchen.material"]
        first = Material._sb_backfill_family_density()
        mdf.invalidate_recordset()
        family_after_first = mdf.family_id

        second = Material._sb_backfill_family_density()
        mdf.invalidate_recordset()

        self.assertGreater(first, 0)
        self.assertEqual(second, 0)
        self.assertEqual(mdf.family_id, family_after_first)
