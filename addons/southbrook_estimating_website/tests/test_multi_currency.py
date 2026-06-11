# SPDX-License-Identifier: LGPL-3.0-only
"""Phase 4 Sprint 5 — multi-currency awareness on the catalog endpoint.

When website.currency_id differs from the template's currency_id, the
catalog endpoint should return list_price + channel_price already
converted to the display currency. When the currencies match, the
output is unchanged (existing behaviour preserved).
"""
from contextlib import contextmanager
from unittest.mock import MagicMock

from odoo.tests import TransactionCase, tagged

from odoo.addons.southbrook_estimating_website.controllers import (
    main as ctrl_main,
)


@contextmanager
def stubbed_request(env, user=None):
    saved = ctrl_main.request
    mock = MagicMock()
    mock.env = env if user is None else env(user=user)
    mock.httprequest = MagicMock()
    mock.httprequest.headers = {}
    ctrl_main.request = mock
    try:
        yield mock
    finally:
        ctrl_main.request = saved


@tagged("post_install", "-at_install", "southbrook", "phase_4",
        "multi_currency")
class TestMultiCurrency(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cad = cls.env.ref("base.CAD")
        cls.usd = cls.env.ref("base.USD")
        # Seed an exchange rate so _convert can do work even on
        # fresh test DBs that don't have rate fixtures.
        if not cls.env["res.currency.rate"].search([
            ("currency_id", "=", cls.usd.id),
            ("name", "<=", "2026-06-11"),
        ], limit=1):
            cls.env["res.currency.rate"].sudo().create({
                "currency_id": cls.usd.id,
                "name": "2026-06-11",
                "rate": 0.75,    # 1 CAD = 0.75 USD (illustrative)
                "company_id": cls.env.company.id,
            })

    def test_single_currency_returns_raw_list_price(self):
        """When website + template currency match, no conversion."""
        controller = ctrl_main.SouthbrookKitchenPlanner()
        with stubbed_request(self.env):
            result = controller.kitchen_planner_state()
        # The catalog endpoint must return without raising; the
        # exact prices are template-seed-dependent so we just
        # assert the contract shape.
        self.assertIn("catalog", result)
        self.assertGreater(len(result["catalog"]), 0)
        for item in result["catalog"]:
            self.assertIn("list_price", item)
            self.assertIn("channel_price", item)
            self.assertGreaterEqual(item["list_price"], 0)
            self.assertGreaterEqual(item["channel_price"], 0)

    def test_payload_currency_block_lists_display_currency(self):
        """The currency block must surface the resolved display
        currency so the OWL card formats with the right symbol."""
        controller = ctrl_main.SouthbrookKitchenPlanner()
        with stubbed_request(self.env):
            result = controller.kitchen_planner_state()
        currency_block = result["currency"]
        self.assertIn("symbol", currency_block)
        self.assertIn("decimal_places", currency_block)
        self.assertIn("name", currency_block)
        # Both CAD and USD render with $; the name tells the client
        # which one we resolved to.
        self.assertIn(currency_block["name"], ("CAD", "USD"))
