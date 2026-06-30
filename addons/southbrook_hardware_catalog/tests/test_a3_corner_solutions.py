# SPDX-License-Identifier: LGPL-3.0-only
"""A3 — Corner-solution catalogue (LAVA / Vauth-Sagel / Häfele).

10 specialty corner mechanisms: BCO, Planero BCO, CPOS, LAVA CPOS,
Magic Corner, Planero Swing, plus 4 tall Planero variants.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "hardware_catalog",
        "a3", "corner_solutions")
class TestA3CornerSolutions(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Product = cls.env["product.product"]
        cls.Brand = cls.env["southbrook.hardware.brand"]

    # ------------------------------------------------------------------
    # Acceptance — brand records exist
    # ------------------------------------------------------------------
    def test_lava_and_vauth_sagel_brands_exist(self):
        lava = self.env.ref("southbrook_hardware_catalog.brand_lava",
                            raise_if_not_found=False)
        vs = self.env.ref(
            "southbrook_hardware_catalog.brand_vauth_sagel",
            raise_if_not_found=False)
        self.assertTrue(lava and lava.code == "lava")
        self.assertTrue(vs and vs.code == "vauth_sagel")

    # ------------------------------------------------------------------
    # Acceptance — exactly 10 corner mechanisms seeded
    # ------------------------------------------------------------------
    def test_10_corner_mechanisms(self):
        mechs = self.Product.search(
            [("x_hardware_category", "=", "corner_mech")])
        self.assertEqual(
            len(mechs), 10,
            "expected exactly 10 specialty corner mechanisms")

    # ------------------------------------------------------------------
    # Acceptance — Vauth-Sagel records carry the Planero brand
    # ------------------------------------------------------------------
    def test_planero_records_branded_vauth_sagel(self):
        vs = self.env.ref("southbrook_hardware_catalog.brand_vauth_sagel")
        vs_mechs = self.Product.search([
            ("x_hardware_category", "=", "corner_mech"),
            ("x_hardware_brand_id", "=", vs.id),
        ])
        # 1 base BCO + 1 swing + 4 tall larder = 6 Planero variants
        self.assertEqual(
            len(vs_mechs), 6,
            "expected 6 Planero (Vauth-Sagel) corner mechanisms")

    # ------------------------------------------------------------------
    # Acceptance — LAVA CPOS carries the LAVA brand
    # ------------------------------------------------------------------
    def test_lava_cpos_records(self):
        lava = self.env.ref("southbrook_hardware_catalog.brand_lava")
        lava_mechs = self.Product.search([
            ("x_hardware_category", "=", "corner_mech"),
            ("x_hardware_brand_id", "=", lava.id),
        ])
        self.assertEqual(len(lava_mechs), 1)
        self.assertEqual(lava_mechs.default_code, "SB-CM-LCPOS")

    # ------------------------------------------------------------------
    # Acceptance — every record has pricing pending
    # ------------------------------------------------------------------
    def test_pricing_pending(self):
        mechs = self.Product.search(
            [("x_hardware_category", "=", "corner_mech")])
        for m in mechs:
            self.assertTrue(
                m.x_pricing_pending,
                f"{m.default_code} should be x_pricing_pending=True")
