# SPDX-License-Identifier: LGPL-3.0-only
"""Repair Wave 2, Upgrade 2 — the 7 live shorthand SKUs added to
`_SKU_DEFAULTS` (B24, DB24, SB-BASE-3DRW, SB30, T24, W24, W24-2), plus
FP3's deliberate exclusion (honesty contract: a filler panel has no
carcass, so it must stay at 0/0/0).

Mirrors the style of `TestGeometryBackfill` in test_geometry_writeback.py
— these are new rows in the SAME table that method already reads, so
no new machinery is needed, just coverage that the new codes resolve
(and FP3 still doesn't).
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "sb_geo")
class TestSkuDefaultsWave2(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Product = cls.env["product.product"]

    def test_db24_resolves_via_backfill_with_drawer_count_3(self):
        p = self.Product.create({
            "name": "DB24 3-Drawer Base", "default_code": "DB24",
        })
        self.assertFalse(p.sb_width_mm)
        self.env["product.product"]._sb_backfill_geometry()
        p.invalidate_recordset()

        expected = self.env["product.config.session"]._SKU_DEFAULTS["DB24"]
        fam, doors, drawers, w, h, d = expected
        self.assertTrue(p.sb_width_mm and p.sb_height_mm and p.sb_depth_mm)
        self.assertEqual(p.sb_width_mm, w)
        self.assertEqual(p.sb_height_mm, h)
        self.assertEqual(p.sb_depth_mm, d)
        self.assertEqual(p.sb_panel_family, fam)
        self.assertEqual(p.sb_door_count, doors)
        self.assertEqual(p.sb_drawer_count, 3)
        self.assertEqual(p.sb_drawer_count, drawers)

    def test_fp3_filler_panel_stays_honestly_at_zero(self):
        """FP3 is deliberately excluded from _SKU_DEFAULTS (a filler
        panel has no carcass) -- the backfill must not fabricate
        dimensions for it."""
        Session = self.env["product.config.session"]
        self.assertNotIn("FP3", Session._SKU_DEFAULTS)

        p = self.Product.create({
            "name": "FP3 Filler Panel 3in", "default_code": "FP3",
        })
        self.env["product.product"]._sb_backfill_geometry()
        p.invalidate_recordset()

        self.assertEqual(p.sb_width_mm, 0)
        self.assertEqual(p.sb_height_mm, 0)
        self.assertEqual(p.sb_depth_mm, 0)

    def test_all_seven_new_shorthand_codes_resolve_nonzero(self):
        """B24, SB-BASE-3DRW, SB30, T24, W24, W24-2 (DB24 covered in
        its own test above) all resolve to non-zero geometry now that
        they have rows in `_SKU_DEFAULTS`."""
        codes = ["B24", "SB-BASE-3DRW", "SB30", "T24", "W24", "W24-2"]
        products = self.Product.create([
            {"name": f"Wave2 {code}", "default_code": code} for code in codes
        ])
        self.env["product.product"]._sb_backfill_geometry()
        products.invalidate_recordset()

        Session = self.env["product.config.session"]
        for p, code in zip(products, codes):
            expected = Session._SKU_DEFAULTS[code]
            fam, doors, drawers, w, h, d = expected
            self.assertTrue(
                p.sb_width_mm and p.sb_height_mm and p.sb_depth_mm,
                f"{code} did not resolve to non-zero geometry",
            )
            self.assertEqual(p.sb_width_mm, w, code)
            self.assertEqual(p.sb_height_mm, h, code)
            self.assertEqual(p.sb_depth_mm, d, code)
            self.assertEqual(p.sb_panel_family, fam, code)
            self.assertEqual(p.sb_door_count, doors, code)
            self.assertEqual(p.sb_drawer_count, drawers, code)

    def test_b24_and_w24_use_24in_width_convention(self):
        """The mapped rows' own width (762 for SB-BASE-2DR/SB-WALL-2DR)
        is overridden to the table's 24in convention (609mm), matching
        attr_width's value_mm for 24in and the door-count rule comment
        in product_product.py."""
        Session = self.env["product.config.session"]
        self.assertEqual(Session._SKU_DEFAULTS["B24"][3], 609)
        self.assertEqual(Session._SKU_DEFAULTS["W24"][3], 609)
        self.assertEqual(Session._SKU_DEFAULTS["W24-2"][3], 609)
        self.assertEqual(Session._SKU_DEFAULTS["T24"][3], 609)

    def test_sb30_uses_30in_width_convention(self):
        Session = self.env["product.config.session"]
        self.assertEqual(Session._SKU_DEFAULTS["SB30"][3], 762)
