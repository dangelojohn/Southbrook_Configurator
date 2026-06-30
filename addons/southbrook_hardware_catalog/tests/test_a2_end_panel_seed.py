# SPDX-License-Identifier: LGPL-3.0-only
"""A2 — End-Panel mini-catalogue (5 styles × 3 classes + 3 fillers).

Asserts the seed creates 15 end-panel records + 3 filler records,
all in the Southbrook in-house brand, with the expected dimension
spread and the new HARDWARE_CATEGORIES values (end_panel / filler)
present on the variant SKUs.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "hardware_catalog",
        "a2", "end_panel_seed")
class TestA2EndPanelSeed(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Product = cls.env["product.product"]
        cls.Brand = cls.env["southbrook.hardware.brand"]

    # ------------------------------------------------------------------
    # Acceptance — Southbrook in-house brand exists
    # ------------------------------------------------------------------
    def test_southbrook_inhouse_brand_exists(self):
        brand = self.env.ref("southbrook_hardware_catalog.brand_southbrook_inhouse",
                             raise_if_not_found=False)
        self.assertTrue(brand, "brand_southbrook_inhouse must be seeded")
        self.assertEqual(brand.code, "southbrook")
        self.assertEqual(brand.name, "Southbrook (In-House)")

    # ------------------------------------------------------------------
    # Acceptance — 15 end panels + 3 fillers seeded
    # ------------------------------------------------------------------
    def test_15_end_panels_plus_3_fillers(self):
        brand = self.env.ref("southbrook_hardware_catalog.brand_southbrook_inhouse")
        end_panels = self.Product.search([
            ("x_hardware_category", "=", "end_panel"),
            ("x_hardware_brand_id", "=", brand.id),
        ])
        self.assertEqual(
            len(end_panels), 15,
            "exactly 5 styles × 3 classes = 15 end-panel records expected")
        fillers = self.Product.search([
            ("x_hardware_category", "=", "filler"),
            ("x_hardware_brand_id", "=", brand.id),
        ])
        self.assertEqual(len(fillers), 3,
                         "3 filler classes (Base / Tall / Wall) expected")

    # ------------------------------------------------------------------
    # Acceptance — each (style, class) pair exists
    # ------------------------------------------------------------------
    def test_each_style_class_pair_present(self):
        styles = ("STD", "INL", "TG", "RAD", "SQ")
        classes = ("BASE", "TALL", "WALL")
        for klass in classes:
            for style in styles:
                code = f"SB-EP-{klass}-{style}"
                hits = self.Product.search([("default_code", "=", code)])
                self.assertEqual(
                    len(hits), 1,
                    f"expected exactly one record with default_code={code}")

    # ------------------------------------------------------------------
    # Acceptance — class dimensions match Prodboard standard
    # ------------------------------------------------------------------
    def test_class_dimensions(self):
        # Base end panel: 720 × 600 × 18
        base = self.Product.search(
            [("default_code", "=", "SB-EP-BASE-STD")], limit=1)
        self.assertEqual(int(base.x_length_mm), 720)
        self.assertEqual(int(base.x_width_mm), 600)
        # Tall end panel: 1970 × 570
        tall = self.Product.search(
            [("default_code", "=", "SB-EP-TALL-STD")], limit=1)
        self.assertEqual(int(tall.x_length_mm), 1970)
        self.assertEqual(int(tall.x_width_mm), 570)
        # Wall end panel: 720 × 330
        wall = self.Product.search(
            [("default_code", "=", "SB-EP-WALL-STD")], limit=1)
        self.assertEqual(int(wall.x_length_mm), 720)
        self.assertEqual(int(wall.x_width_mm), 330)
        # Filler width is always 50mm
        for cls_key in ("BASE", "TALL", "WALL"):
            f = self.Product.search(
                [("default_code", "=", f"SB-FILLER-{cls_key}")], limit=1)
            self.assertEqual(
                int(f.x_width_mm), 50,
                f"SB-FILLER-{cls_key} width should be 50mm")

    # ------------------------------------------------------------------
    # Acceptance — pricing is intentionally pending
    # ------------------------------------------------------------------
    def test_pricing_pending_on_every_panel(self):
        brand = self.env.ref("southbrook_hardware_catalog.brand_southbrook_inhouse")
        records = self.Product.search([
            ("x_hardware_brand_id", "=", brand.id),
            ("x_hardware_category", "in", ("end_panel", "filler")),
        ])
        for r in records:
            self.assertTrue(
                r.x_pricing_pending,
                f"{r.default_code} should have x_pricing_pending=True until "
                "Peter signs off per-style pricing")
