# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for the res.partner channel + tradesperson_tier extension."""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook")
class TestResPartnerChannel(TransactionCase):
    """Q1 + Q5 + NF5: the channel field + tier-defaulting behaviour."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]

    def test_01_default_channel_is_retail(self):
        """New partners default to channel=retail per the field default."""
        partner = self.Partner.create({"name": "Plain Partner"})
        self.assertEqual(partner.channel, "retail")
        self.assertFalse(partner.tradesperson_tier)

    def test_02_all_six_channel_values_accepted(self):
        """Q1 — the 6 channels (retail / dealer / tradesperson / kd / bigbox / refacing)."""
        for ch in ("retail", "dealer", "tradesperson", "kd", "bigbox", "refacing"):
            partner = self.Partner.create({"name": f"P-{ch}", "channel": ch})
            self.assertEqual(partner.channel, ch)

    def test_03_tradesperson_onchange_defaults_tier_to_3(self):
        """NF5 — switching channel to tradesperson via the form defaults tier=3.

        Uses the Form harness to exercise the onchange handler the way the
        UI does. Direct .create() with channel='tradesperson' does NOT
        trigger onchange — that's expected; only UI / Form interactions do.
        """
        from odoo.tests.common import Form

        with Form(self.Partner) as f:
            f.name = "Demo Tradesperson"
            f.channel = "tradesperson"
            # tier should auto-populate to '3' via the onchange handler.
            self.assertEqual(f.tradesperson_tier, "3")
        # And the saved record carries the same value.
        partner = self.Partner.search([("name", "=", "Demo Tradesperson")], limit=1)
        self.assertEqual(partner.tradesperson_tier, "3")

    def test_04_tier_clears_when_channel_leaves_tradesperson(self):
        """NF5 — tier is meaningless off-channel; onchange clears it."""
        from odoo.tests.common import Form

        with Form(self.Partner) as f:
            f.name = "Switchy Partner"
            f.channel = "tradesperson"
            self.assertEqual(f.tradesperson_tier, "3")
            f.channel = "dealer"
            self.assertFalse(f.tradesperson_tier)

    def test_05_tier_can_be_explicitly_set_via_create(self):
        """Direct create() bypasses onchange, allowing explicit tier values."""
        partner = self.Partner.create({
            "name": "Direct Tier 2 Partner",
            "channel": "tradesperson",
            "tradesperson_tier": "2",
        })
        self.assertEqual(partner.tradesperson_tier, "2")

    def test_06_seed_mode_flag_present(self):
        """OQ2 — the southbrook.seed_mode config parameter must exist
        and default to 'illustrative'."""
        param = self.env["ir.config_parameter"].sudo().get_param(
            "southbrook.seed_mode"
        )
        self.assertEqual(param, "illustrative")
