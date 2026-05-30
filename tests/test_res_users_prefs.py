# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for NF7 + NF8 res.users Order Builder preferences."""
from odoo.tests.common import tagged

from .common import SouthbrookTestCase


@tagged("post_install", "-at_install", "southbrook", "nf7", "nf8")
class TestResUsersPrefs(SouthbrookTestCase):

    def test_01_default_series_is_contractor(self):
        """NF7 — Amazing Window default: every new user starts on Contractor."""
        user = self.env["res.users"].create({
            "name": "NF7 User",
            "login": "nf7_test",
        })
        self.assertEqual(user.southbrook_default_series, "contractor")

    def test_02_default_entry_mode_is_family_first(self):
        """NF8 — default mode is family_first; width_first is opt-in."""
        user = self.env["res.users"].create({
            "name": "NF8 User",
            "login": "nf8_test",
        })
        self.assertEqual(user.southbrook_order_entry_mode, "family_first")

    def test_03_user_can_set_default_series_to_signature(self):
        user = self.env["res.users"].create({
            "name": "NF7 Sig User",
            "login": "nf7_sig",
            "southbrook_default_series": "signature",
        })
        self.assertEqual(user.southbrook_default_series, "signature")

    def test_04_user_can_opt_into_width_first(self):
        """NF8 — Pro Finish rep opts into width-first."""
        user = self.env["res.users"].create({
            "name": "Pro Finish Rep",
            "login": "pro_finish",
            "southbrook_order_entry_mode": "width_first",
        })
        self.assertEqual(user.southbrook_order_entry_mode, "width_first")
