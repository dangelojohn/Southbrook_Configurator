# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for channel -> pricelist resolution (custom routine #3) and the
refacing margin-target computation (custom routine #2)."""
from odoo.tests.common import tagged

from .common import SouthbrookTestCase


@tagged("post_install", "-at_install", "southbrook")
class TestPricelistResolution(SouthbrookTestCase):

    # --- Channel resolution ---------------------------------------

    def test_01_retail_partner_resolves_to_retail_pricelist(self):
        p = self.Partner.create({"name": "Retail Walk-in", "channel": "retail"})
        resolved = self.Order._resolve_channel_pricelist(p)
        self.assertEqual(resolved, self._ref("pricelist_retail"))

    def test_02_dealer_partner_resolves_to_dealer_pricelist(self):
        p = self.Partner.create({"name": "Richwood", "channel": "dealer"})
        resolved = self.Order._resolve_channel_pricelist(p)
        self.assertEqual(resolved, self._ref("pricelist_dealer"))

    def test_03_tradesperson_tier_3_resolves_to_tier_3_pricelist(self):
        """Q7 smoke-test target."""
        p = self.Partner.create({
            "name": "Demo Tradesperson",
            "channel": "tradesperson",
            "tradesperson_tier": "3",
        })
        resolved = self.Order._resolve_channel_pricelist(p)
        self.assertEqual(resolved, self._ref("pricelist_tradesperson_tier_3"))

    def test_04_tradesperson_no_tier_resolves_to_base_with_warning(self):
        """NF5 — fallback path. Warning logged but resolution still succeeds."""
        p = self.Partner.create({
            "name": "Untiered Tradesperson",
            "channel": "tradesperson",
        })
        with self.assertLogs(
            "odoo.addons.southbrook_estimating.models.sale_order",
            level="WARNING",
        ) as log:
            resolved = self.Order._resolve_channel_pricelist(p)
        self.assertEqual(resolved, self._ref("pricelist_tradesperson"))
        self.assertTrue(any("no tradesperson_tier" in m for m in log.output))

    def test_05_each_tier_resolves_to_its_pricelist(self):
        for tier_str, xml_id in [
            ("1", "pricelist_tradesperson_tier_1"),
            ("2", "pricelist_tradesperson_tier_2"),
            ("3", "pricelist_tradesperson_tier_3"),
        ]:
            p = self.Partner.create({
                "name": f"Tier {tier_str}",
                "channel": "tradesperson",
                "tradesperson_tier": tier_str,
            })
            self.assertEqual(
                self.Order._resolve_channel_pricelist(p),
                self._ref(xml_id),
            )

    def test_06_kd_bigbox_refacing_resolve(self):
        for ch, xml_id in [
            ("kd", "pricelist_kd"),
            ("bigbox", "pricelist_bigbox"),
            ("refacing", "pricelist_refacing"),
        ]:
            p = self.Partner.create({"name": f"P-{ch}", "channel": ch})
            self.assertEqual(
                self.Order._resolve_channel_pricelist(p),
                self._ref(xml_id),
            )

    def test_07_no_partner_falls_back_to_retail(self):
        self.assertEqual(
            self.Order._resolve_channel_pricelist(False),
            self._ref("pricelist_retail"),
        )

    # --- Refacing margin-target -----------------------------------

    def test_08_refacing_price_hits_35pct_margin(self):
        """Custom routine #2 — refacing price = cost / (1 - 0.35)."""
        product = self.Product.create({
            "name": "Test Door",
            "standard_price": 65.0,
            "list_price": 100.0,
        })
        item = self.env["product.pricelist.item"].create({
            "pricelist_id": self._ref("pricelist_refacing").id,
            "is_refacing_margin_target": True,
        })
        price = item._compute_refacing_price(product, 1)
        expected = round(65.0 / 0.65, 2)
        self.assertEqual(price, expected)
        # And the margin really IS 35%.
        margin = (price - 65.0) / price
        self.assertAlmostEqual(margin, 0.35, places=4)

    def test_09_refacing_zero_cost_falls_back_to_list(self):
        product = self.Product.create({
            "name": "No-cost Door",
            "standard_price": 0.0,
            "list_price": 200.0,
        })
        item = self.env["product.pricelist.item"].create({
            "pricelist_id": self._ref("pricelist_refacing").id,
            "is_refacing_margin_target": True,
        })
        self.assertEqual(item._compute_refacing_price(product, 1), 200.0)

    # --- NF13 regression: onchange must actually assign pricelist_id ---

    def test_10_onchange_partner_id_resolves_pricelist(self):
        """NF13 regression — direct behavioural assertion that
        _onchange_partner_id_southbrook_pricelist actually does its job.

        The reported "bug" in this method on 2026-05-30 turned out to be a
        paste-rendering artifact in review, not a real truncation. But the
        class of slip is real: py_compile and ET.parse don't catch method
        bodies that lose statements between commits. This test asserts
        observable behaviour (pricelist_id changes), not just callability.
        """
        from odoo.tests.common import Form
        partner = self.Partner.create({
            "name": "NF13 Test Partner",
            "channel": "tradesperson",
            "tradesperson_tier": "3",
        })
        with Form(self.Order) as f:
            f.partner_id = partner
            # After onchange fires, the Form's pricelist_id reflects the resolver.
            # Cannot read pricelist_id directly from Form harness (it's a hidden
            # default field in many configurations) — assert via the saved record.
        saved = f.save()
        self.assertEqual(
            saved.pricelist_id,
            self._ref("pricelist_tradesperson_tier_3"),
            "NF13 regression: onchange must assign Tier-3 pricelist when "
            "partner.channel=tradesperson + tier=3",
        )

    def test_11_onchange_no_partner_no_op(self):
        """NF13 companion: onchange logic with null partner must not crash.

        NF24 (caught at live test run 2026-05-30): the original Form-based
        approach tried to exit the `with` block without ever assigning
        partner_id — but Form auto-saves on exit, and sale.order.partner_id
        is required, so the save aborts before our onchange logic runs.
        That defeats the purpose: we want to exercise the no-partner
        branch of _onchange_partner_id_resolve_pricelist, not test that
        sale.order requires partner_id.

        Fix: instantiate an in-memory order (new() — no save) and call
        the onchange method directly (sale_order.py:_onchange_partner_id_southbrook_pricelist).
        assertRaises-no-exception is the contract.
        """
        # NewId record — exists in memory only; never saved, so the
        # required-partner_id check never triggers.
        new_order = self.Order.new({})
        self.assertFalse(new_order.partner_id, "fixture: no partner set")
        # If our resolver has an unguarded `partner.channel` access, this
        # call raises AttributeError. The test passes only when the
        # no-partner branch returns cleanly.
        try:
            new_order._onchange_partner_id_southbrook_pricelist()
        except AttributeError as exc:
            self.fail(
                f"NF13 regression: onchange with null partner crashed: {exc}"
            )
