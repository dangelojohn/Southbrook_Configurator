# SPDX-License-Identifier: LGPL-3.0-only
"""Per-channel pricelist MATH tests — 2026-07-01 E2E audit follow-up.

Coverage gap from docs/E2E_AUDIT_SOUTHBROOK_ESTIMATING_2026-07-01.md §6.2:

    "Per-channel price math tests for retail base list, dealer -50%,
     tradesperson tier -25/-30/-35%, KD ~46%, bigbox fixed $65/$98.
     Currently only refacing 35% margin math is exercised end-to-end."

`test_pricelist_resolution.py` already covers CHANNEL → PRICELIST binding.
This file exercises the price DELTAS: given a product with a known
`list_price` (retail) + `standard_price` (cost), each pricelist must land
the line at the seeded contract price.

Contract targets (from data/pricelists.xml + Q1 + NF5):
  * retail          → base list_price
  * dealer          → list × 0.50
  * tradesperson    → cost × 1.05 (floor; a real tier is expected in practice)
  * tier_1          → tradesperson × 0.75 (-25%)
  * tier_2          → tradesperson × 0.70 (-30%)
  * tier_3          → tradesperson × 0.65 (-35%)  (Q7 smoke target)
  * kd              → list × 0.46 (=1 − 0.54 discount)
  * bigbox          → fixed $98.00

We route through `pricelist._get_product_price(product, qty, partner=…)` —
the standard Odoo API. That funnels through `_compute_price_unit` which is
the same path the sale.order.line onchange uses in real order builder
flows, so this is a fair proxy for the customer-facing price.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "pricelist_math")
class TestPerChannelPriceMath(TransactionCase):
    """Verify each of the 8 shipped pricelists lands on the contract price."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.Product = cls.env["product.product"]
        cls.Pricelist = cls.env["product.pricelist"]

        # Anchor prices — chosen to exercise the math without landing on
        # awkward floats:
        #     retail  = $500.00
        #     cost    = $200.00
        # Tradesperson floor = cost * 1.05 = $210.00
        cls.product = cls.Product.create({
            "name": "Test Cabinet SB-PRICE-A",
            "default_code": "SB-PRICE-A",
            "type": "consu",
            "list_price": 500.0,
            "standard_price": 200.0,
        })

        cls.pl = {
            "retail":       cls.env.ref("southbrook_estimating.pricelist_retail"),
            "dealer":       cls.env.ref("southbrook_estimating.pricelist_dealer"),
            "tradesperson": cls.env.ref(
                "southbrook_estimating.pricelist_tradesperson"),
            "tier_1":       cls.env.ref(
                "southbrook_estimating.pricelist_tradesperson_tier_1"),
            "tier_2":       cls.env.ref(
                "southbrook_estimating.pricelist_tradesperson_tier_2"),
            "tier_3":       cls.env.ref(
                "southbrook_estimating.pricelist_tradesperson_tier_3"),
            "kd":           cls.env.ref("southbrook_estimating.pricelist_kd"),
            "bigbox":       cls.env.ref("southbrook_estimating.pricelist_bigbox"),
        }

    # ------------------------------------------------------------------
    # helper — resolve the effective per-unit price the Order Builder
    # would apply if this product were added to a sale.order under this
    # pricelist. Uses the same `_get_product_price` seam as the SO
    # onchange chain.
    # ------------------------------------------------------------------
    def _price(self, pricelist_key, qty=1):
        return self.pl[pricelist_key]._get_product_price(
            self.product, qty, partner=None)

    # ------------------------------------------------------------------
    # Retail — base list price, no discount, no items.
    # ------------------------------------------------------------------
    def test_01_retail_price_is_list_price(self):
        self.assertAlmostEqual(
            self._price("retail"), 500.0, places=2,
            msg="Retail pricelist should pass through list_price unchanged")

    # ------------------------------------------------------------------
    # Dealer — 50% off retail.
    # ------------------------------------------------------------------
    def test_02_dealer_price_is_50pct_off_list(self):
        self.assertAlmostEqual(
            self._price("dealer"), 250.0, places=2,
            msg="Dealer pricelist should land at retail × 0.50 = $250.00")

    # ------------------------------------------------------------------
    # Tradesperson base — cost × 1.05 = $210 (floor pricelist).
    # This is what the tier pricelists inherit from via base_pricelist_id.
    # ------------------------------------------------------------------
    def test_03_tradesperson_base_is_cost_times_1_05(self):
        self.assertAlmostEqual(
            self._price("tradesperson"), 210.0, places=2,
            msg="Tradesperson base pricelist should land at "
                "cost × 1.05 = $210.00")

    # ------------------------------------------------------------------
    # Tradesperson tiers — -25% / -30% / -35% off the $210 floor.
    # ------------------------------------------------------------------
    def test_04_tier_1_is_25pct_off_tradesperson(self):
        # 210.00 * 0.75 = 157.50
        self.assertAlmostEqual(
            self._price("tier_1"), 157.50, places=2,
            msg="Tier-1 (-25%) should land at $157.50")

    def test_05_tier_2_is_30pct_off_tradesperson(self):
        # 210.00 * 0.70 = 147.00
        self.assertAlmostEqual(
            self._price("tier_2"), 147.00, places=2,
            msg="Tier-2 (-30%) should land at $147.00")

    def test_06_tier_3_is_35pct_off_tradesperson(self):
        # 210.00 * 0.65 = 136.50 — Q7 acceptance target.
        self.assertAlmostEqual(
            self._price("tier_3"), 136.50, places=2,
            msg="Tier-3 (-35%) should land at $136.50 — this is the "
                "Q7 acceptance smoke target price")

    # ------------------------------------------------------------------
    # KD (Central) — ~46% of retail (54% discount).
    # ------------------------------------------------------------------
    def test_07_kd_price_is_46pct_of_retail(self):
        # 500.00 * (1 − 0.54) = 500 * 0.46 = 230.00
        self.assertAlmostEqual(
            self._price("kd"), 230.0, places=2,
            msg="KD pricelist should land at retail × 0.46 = $230.00")

    # ------------------------------------------------------------------
    # Big-Box wholesale — fixed price per SKU regardless of list_price.
    # ------------------------------------------------------------------
    def test_08_bigbox_price_is_fixed_98(self):
        self.assertAlmostEqual(
            self._price("bigbox"), 98.0, places=2,
            msg="Big-Box pricelist should land at fixed $98.00 "
                "regardless of list_price")

    # ------------------------------------------------------------------
    # Cross-channel invariants — cheap-to-check business-rule
    # relationships that guard against a future pricelist edit accidentally
    # inverting the ordering.
    # ------------------------------------------------------------------
    def test_09_retail_is_always_the_dearest_channel(self):
        retail = self._price("retail")
        for key in ("dealer", "tradesperson", "tier_1", "tier_2", "tier_3",
                    "kd", "bigbox"):
            self.assertGreater(
                retail, self._price(key),
                "Retail (%s) should be strictly greater than %s price (%s)"
                % (retail, key, self._price(key)))

    def test_10_tier_3_is_the_cheapest_tradesperson_tier(self):
        self.assertLess(
            self._price("tier_3"), self._price("tier_2"),
            "Tier-3 should undercut Tier-2 (deeper discount)")
        self.assertLess(
            self._price("tier_2"), self._price("tier_1"),
            "Tier-2 should undercut Tier-1 (deeper discount)")
