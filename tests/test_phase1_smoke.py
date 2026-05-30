# SPDX-License-Identifier: LGPL-3.0-only
"""Phase 1 gate smoke test — Mapping section 6 step 1-10.

Discipline-B (acked 2026-05-30): write the smoke test as a stub now, promote
each step from self.skipTest("waiting for commit N") to a real assertion as
the dependency commits land. By commit 10 the test is fully exercising; by
commit 11 the demo data + canonical partner are present and the test runs
green against the live build.

Two-mode assertion gating per OQ2: when southbrook.seed_mode='illustrative',
$-value assertions use shape predicates (Tier 3 total is between 60-70% of
retail total, etc.) rather than exact equality. When the mode flips to
'canonical' after #8 lands, the same test re-enables exact-equality
assertions. The seed_mode is read at setUp and stored on the test class.

Phase 1 gate (Brief section 8 / Mapping section 6) is reached when all 10
steps below pass on John's live Odoo 19 CE instance.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "phase1_smoke")
class TestPhase1Smoke(TransactionCase):
    """The 10-step Phase 1 gate test from Mapping section 6.

    Each step is currently skipTest'd; promote to a real assertion as the
    upstream commit lands.

    Promotion map:
      Steps 1, 2     → commit 11 (demo data: Demo Tradesperson + Richwood)
      Steps 3, 4, 5  → commit 11 (9 demo lines with the rule mix)
      Step 6         → commit 8  (parametric BoM rollup with maple +2wk lead-time)
      Step 7         → commit 11 (full smoke order with Richwood -35% expected total)
      Step 8         → commit 11 (customer switch re-prices)
      Step 9         → commit 11 (MO emission per cabinet)
      Step 10        → Phase 1 (commits ~10, QWeb report)
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.seed_mode = cls.env["ir.config_parameter"].sudo().get_param(
            "southbrook.seed_mode", default="illustrative"
        )

    # ------------------------------------------------------------------
    # Step 1 — Create a res.partner Richwood Renovations, channel=dealer
    # ------------------------------------------------------------------
    def test_step_01_richwood_demo_partner_exists(self):
        self.skipTest("waiting for commit 11 (demo data — Richwood partner)")

    # ------------------------------------------------------------------
    # Step 2 — Open Sales > Order Builder, create order, customer=Richwood
    # ------------------------------------------------------------------
    def test_step_02_order_builder_form_creates_order(self):
        self.skipTest("waiting for commit 9 (Order Builder view) + commit 11")

    # ------------------------------------------------------------------
    # Step 3 — Configure 9 lines (base 1dr 18, base 2dr 24, drawer 18,
    #          sink 33, wall 1dr 15 x2, wall 2dr 30, tall_pantry 24, end panel)
    # ------------------------------------------------------------------
    def test_step_03_nine_demo_lines_configurable(self):
        self.skipTest("waiting for commit 11 (9 demo lines)")

    # ------------------------------------------------------------------
    # Step 4 — Each line uses Contemporary series, maple box (+10%),
    #          thermofoil_slab door, white finish, soft_close on
    # ------------------------------------------------------------------
    def test_step_04_attribute_mix_applied(self):
        self.skipTest("waiting for commit 11 (configured demo lines)")

    # ------------------------------------------------------------------
    # Step 5 — Rule engine asserts:
    #    Contractor on any line → hide maple box (Rule 2)
    #    Contractor + 5-piece door → unselectable (Rule 1)
    #    21 → 24 width → door_count flips 1 → 2 (Rule 3)
    # ------------------------------------------------------------------
    def test_step_05_rules_fire_correctly(self):
        self.skipTest("waiting for commit 11 — but rules themselves live "
                      "in data/config_rules.xml as of commit 7")

    # ------------------------------------------------------------------
    # Step 6 — BoM preview shows parametric BoM per line; maple lines
    #          carry +2 weeks lead time
    # ------------------------------------------------------------------
    # PARTIALLY PROMOTED at commit 8: asserts the panel-dim function is
    # reachable and returns the expected key set for the smoke-test
    # canonical cabinet (18in base 1-door, Contemporary, maple box).
    # End-to-end SO -> MO -> BoM materialisation still waits for
    # commit 11 (demo data + full lifecycle exercise).
    def test_step_06_bom_preview_with_maple_lead_time(self):
        # The smoke test's canonical 18" base 1-door entry: line 1 of the
        # 9-line Mapping section 6 step 3.
        result = self.env["mrp.bom"]._compute_panel_dimensions(
            width_mm=457, height_mm=762, depth_mm=609,  # 18 x 30 x 24 in
            family="base", door_count=1,
        )
        # The smoke test asserts the BoM has panel + door + hardware lines.
        # At the function level: all panel slots populated, door populated,
        # hardware counts > 0.
        for required_panel in ("side_L", "side_R", "top", "bottom", "back"):
            self.assertIsNotNone(result[required_panel],
                                 f"smoke step 6: {required_panel} must be in BoM")
        self.assertIsNotNone(result["door"], "smoke step 6: door must be in BoM")
        self.assertEqual(result["hinge_pair_count"], 1)
        self.assertEqual(result["handle_count"], 1)

        # Note: the maple +2wk lead-time bump is exercised at the
        # variant-level rollup (mrp.bom._compute_southbrook_lead_time_extra,
        # commit 5). End-to-end maple→BoM lead-time materialisation lives
        # in the full lifecycle test (commit 11).

    # ------------------------------------------------------------------
    # Step 7 — Total at footer matches Richwood -35% Contractor pricelist
    #          applied to Contemporary list prices + 10% maple uplift
    # ------------------------------------------------------------------
    def test_step_07_total_matches_richwood_dash_35(self):
        if self.seed_mode == "illustrative":
            self.skipTest("waiting for commit 11 — illustrative mode uses "
                          "shape assertions (Tier 3 total in 60-70% of retail)")
        else:
            self.skipTest("waiting for commit 11 — canonical mode exact-equality")

    # ------------------------------------------------------------------
    # Step 8 — Switch customer to Walk-in Retail; all lines re-price
    # ------------------------------------------------------------------
    def test_step_08_customer_switch_reprices(self):
        self.skipTest("waiting for commit 11 (demo order with both partners)")

    # ------------------------------------------------------------------
    # Step 9 — Hit Confirm; mrp.production created per cabinet
    # ------------------------------------------------------------------
    def test_step_09_confirm_creates_mo_per_cabinet(self):
        self.skipTest("waiting for commit 11 (full lifecycle)")

    # ------------------------------------------------------------------
    # Step 10 — Shop Copy QWeb report renders correctly
    # ------------------------------------------------------------------
    def test_step_10_shop_copy_renders(self):
        self.skipTest("waiting for commits ~10 (QWeb reports — custom routine #6)")
