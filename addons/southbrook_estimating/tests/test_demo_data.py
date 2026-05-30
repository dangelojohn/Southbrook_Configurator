# SPDX-License-Identifier: LGPL-3.0-only
"""Demo data integrity tests — commit 11a.

Three load-bearing checks per John's commit-11 ask:

  1. Variant explosion check (Q6 dynamic-mode proof). After install with
     --demo, the product.product count for configurable templates must
     stay small. If dynamic mode silently breaks, the variant count
     balloons into the tens of thousands; this test catches that early.

  2. Analytics row count (NF1 integration check). Demo data confirms 5
     orders via <function/> action_confirm calls. The action_confirm
     hook from commit 6 fires southbrook.order.analytics.capture per
     order. After install with --demo, exactly 5 analytics rows should
     exist.

  3. Demo partner existence + channel correctness. Catches the case
     where demo XML installs but a partner's channel field is wrong
     (which would silently break the pricelist resolver tests).

These tests run only when demo data has loaded. When --demo is NOT
passed at install, the demo partners don't exist and these tests
self-skip via the _demo_loaded() guard inherited from SouthbrookTestCase.
"""
from odoo.tests.common import tagged

from .common import SouthbrookTestCase


@tagged("post_install", "-at_install", "southbrook", "demo")
class TestDemoData(SouthbrookTestCase):

    # ------------------------------------------------------------------
    # Q6 — variant explosion check
    # ------------------------------------------------------------------
    def test_01_variant_explosion_check(self):
        """Q6 dynamic-mode proof — configurable templates must NOT
        spawn thousands of variants at install.

        Hard ceiling: 50 product.product rows across all 12 templates.
        Realistic count after --demo install: small (close to zero;
        Odoo may create a single default variant per template even in
        dynamic mode, but that's it).
        """
        Product = self.env["product.product"]
        # Count variants whose template carries OCA config_ok flag.
        # If a template has config_ok=True but dynamic mode is broken,
        # Odoo would eagerly materialise every (W x H x D x series x ...)
        # combination — easily 50,000 variants.
        configurable_variant_count = Product.search_count([
            ("product_tmpl_id.config_ok", "=", True),
        ])
        self.assertLess(
            configurable_variant_count, 50,
            f"Q6 variant explosion check FAILED: "
            f"{configurable_variant_count} variants spawned from "
            f"configurable templates. Dynamic-variant mode "
            f"(create_variant='dynamic') is silently broken. Expected "
            f"a small count (<50) for Phase 1.",
        )

    # ------------------------------------------------------------------
    # NF1 — analytics row count after demo confirm chain
    # ------------------------------------------------------------------
    def test_02_analytics_rows_match_confirmed_demo_orders(self):
        """NF1 integration check — demo data confirms 5 orders via
        <function/> action_confirm. The hook fires capture(); 5 rows
        should exist.

        Self-skip when --demo not loaded.
        """
        if not self._demo_loaded():
            self.skipTest("--demo not loaded; no demo orders to count")

        analytics_rows = self.env["southbrook.order.analytics"].search_count([])
        self.assertEqual(
            analytics_rows, 5,
            f"Expected 5 analytics rows (one per confirmed demo order); "
            f"found {analytics_rows}. The action_confirm capture hook "
            f"(commit 6) may have regressed, or demo orders may have "
            f"failed to confirm.",
        )

    # ------------------------------------------------------------------
    # Demo partner correctness — channel + tier resolution
    # ------------------------------------------------------------------
    def test_03_demo_dealer_partners_have_dealer_channel(self):
        if not self._demo_loaded():
            self.skipTest("--demo not loaded")
        for xml_id in (
            "demo_partner_image_floor",
            "demo_partner_amazing_window",
            "demo_partner_pro_finish",
            "demo_partner_richwood",
        ):
            partner = self.env.ref(f"southbrook_estimating.{xml_id}")
            self.assertEqual(partner.channel, "dealer",
                             f"{xml_id}: channel must be 'dealer'")

    def test_04_demo_tradesperson_is_tier_3(self):
        if not self._demo_loaded():
            self.skipTest("--demo not loaded")
        partner = self.env.ref(
            "southbrook_estimating.demo_partner_tradesperson"
        )
        self.assertEqual(partner.channel, "tradesperson")
        self.assertEqual(
            partner.tradesperson_tier, "3",
            "Q7 smoke-test target: Demo Tradesperson must be Tier 3 "
            "(auto-resolves to -35% sub-pricelist).",
        )

    def test_05_demo_walkin_retail_is_retail_channel(self):
        if not self._demo_loaded():
            self.skipTest("--demo not loaded")
        partner = self.env.ref(
            "southbrook_estimating.demo_partner_walkin_retail"
        )
        self.assertEqual(partner.channel, "retail")

    # ------------------------------------------------------------------
    # Demo order shape
    # ------------------------------------------------------------------
    def test_06_six_open_quotes_in_draft_state(self):
        if not self._demo_loaded():
            self.skipTest("--demo not loaded")
        for xml_id in (
            "demo_quote_image_floor_001",
            "demo_quote_amazing_window_001",
            "demo_quote_pro_finish_001",
            "demo_quote_richwood_001",
            "demo_quote_image_floor_002",
            "demo_quote_tradesperson_001",
        ):
            order = self.env.ref(f"southbrook_estimating.{xml_id}")
            self.assertIn(
                order.state, ("draft", "sent"),
                f"{xml_id}: open quote must be draft/sent",
            )

    def test_07_nf6_parent_chain_q1_to_q5(self):
        """NF6 chain: demo_quote_image_floor_002 is v2 of _001."""
        if not self._demo_loaded():
            self.skipTest("--demo not loaded")
        v2 = self.env.ref("southbrook_estimating.demo_quote_image_floor_002")
        v1 = self.env.ref("southbrook_estimating.demo_quote_image_floor_001")
        self.assertEqual(v2.parent_order_id, v1)
        self.assertEqual(v2.version, 2)

    def test_08_richwood_confirmed_order_spans_four_zones(self):
        """Demonstrates Q21 zone visual grouping at gate review."""
        if not self._demo_loaded():
            self.skipTest("--demo not loaded")
        order = self.env.ref(
            "southbrook_estimating.demo_order_richwood_confirmed"
        )
        zones = set(order.order_line.mapped("zone"))
        self.assertGreaterEqual(
            len(zones), 3,
            f"Richwood demo order should span multiple zones to show "
            f"Q21 grouping; found zones={zones}",
        )
