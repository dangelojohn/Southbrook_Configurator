# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_material", "sb_geo")
class TestMaterialGeometryDualUnit(TransactionCase):
    """Task C2: canonical mm + bidirectionally-editable Imperial companions.

    thickness_mm is canonical (feeds the weight calc); thickness_in,
    sheet_width_in, sheet_height_in are computed-with-inverse so a Canadian
    shop can enter/read either unit on any record.
    """

    def setUp(self):
        super().setUp()
        self.Mat = self.env["southbrook.kitchen.material"]

    def test_thickness_in_write_updates_mm(self):
        # 3/4" = 19.05mm exactly.
        m = self.Mat.create({"name": "3/4in Ply", "code": "TQ34",
                             "thickness_in": 0.75})
        self.assertAlmostEqual(m.thickness_mm, 19.05, delta=0.01)

    def test_thickness_mm_write_updates_in(self):
        # 12.70mm = 1/2" exactly.
        m = self.Mat.create({"name": "Half Inch Ply", "code": "TQ12",
                             "thickness_mm": 12.70})
        self.assertAlmostEqual(m.thickness_in, 0.5, delta=0.01)

    def test_sheet_width_round_trip_in_to_mm_to_in(self):
        # 48in sheet width -> mm -> back to in, stable, no drift.
        m = self.Mat.create({"name": "4x8 Sheet", "code": "SHT48",
                             "sheet_width_in": 48.0})
        self.assertAlmostEqual(m.sheet_width_mm, 1219.20, delta=0.01)
        # re-read (simulates recompute trigger) — value must be stable.
        m.invalidate_recordset(["sheet_width_in"])
        self.assertAlmostEqual(m.sheet_width_in, 48.0, delta=0.01)

    def test_sheet_height_round_trip_mm_to_in_to_mm(self):
        # 2440mm (standard sheet length) -> in -> back to mm, stable.
        m = self.Mat.create({"name": "8ft Sheet", "code": "SHT8FT",
                             "sheet_height_mm": 2440.0})
        self.assertAlmostEqual(m.sheet_height_in, 96.06, delta=0.01)
        m.write({"sheet_height_mm": 2440.0})
        self.assertAlmostEqual(m.sheet_height_mm, 2440.0, delta=0.01)
        self.assertAlmostEqual(m.sheet_height_in, 96.06, delta=0.01)

    def test_no_infinite_recompute_values_stable_after_write(self):
        # Write thickness_in, then re-write thickness_mm derived from it —
        # values must settle, not drift further with each write (loop guard).
        m = self.Mat.create({"name": "Stability Check", "code": "STAB",
                             "thickness_in": 0.75})
        mm_1 = m.thickness_mm
        in_1 = m.thickness_in
        m.write({"thickness_mm": mm_1})
        self.assertAlmostEqual(m.thickness_mm, mm_1, delta=0.0001)
        self.assertAlmostEqual(m.thickness_in, in_1, delta=0.0001)

    def test_thickness_mm_defaults_and_zero_in_stays_zero_mm(self):
        # Zero must round-trip to zero, not divide-by-zero or NaN.
        m = self.Mat.create({"name": "No Dims", "code": "NODIMS"})
        self.assertEqual(m.thickness_mm, 0.0)
        self.assertEqual(m.thickness_in, 0.0)
        self.assertEqual(m.sheet_width_mm, 0.0)
        self.assertEqual(m.sheet_width_in, 0.0)

    def test_thickness_in_five_eighth_preserves_3dp_precision(self):
        # Regression: _in_to_mm used to hardcode round(inch*25.4, 2), which
        # collapses 5/8" (0.625in) to 15.88mm instead of the exact 15.875mm
        # that thickness_mm's digits=(6,3) precision exists to hold. Sheet
        # dims stay at 2dp; only the thickness inverse needs 3dp.
        m = self.Mat.create({"name": "5/8in Ply", "code": "TQ58",
                             "thickness_in": 0.625})
        self.assertAlmostEqual(m.thickness_mm, 15.875, delta=0.0005)
        m.invalidate_recordset(["thickness_in"])
        self.assertAlmostEqual(m.thickness_in, 0.625, delta=0.0005)

    def test_standard_thickness_quickpick_sets_thickness_mm(self):
        m = self.Mat.create({"name": "Quickpick 3/4", "code": "QP34"})
        m.standard_thickness = "three_quarter"
        m._onchange_standard_thickness()
        self.assertEqual(m.thickness_mm, 19.05)
