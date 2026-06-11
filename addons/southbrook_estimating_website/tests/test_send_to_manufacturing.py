# SPDX-License-Identifier: LGPL-3.0-only
"""Phase 4 Sprint 2 — send_to_manufacturing action tests.

Asserts the new action_code on /southbrook/api/order/<id>/action:
  - state-guarded: rejects orders not in 'sale' state
  - creates an mrp.production for each line with a BoM
  - reuses existing MOs on a re-fire (idempotent re-Send)
  - posts a chatter message with the MO count
"""
from contextlib import contextmanager
from unittest.mock import MagicMock

from odoo.tests import TransactionCase, tagged

from odoo.addons.southbrook_estimating_website.controllers import (
    main as ctrl_main,
)


@contextmanager
def stubbed_request(env, user=None):
    """Swap controllers.main.request for a MagicMock — copy of the
    pattern from test_customer_flow_endpoints."""
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
        "send_to_mfg")
class TestSendToManufacturing(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "Dealer Mfg Test",
            "email": "dealer.mfg.test@southbrook.test",
        })
        cls.product = cls.env["product.product"].create({
            "name": "Mfg test cabinet",
            "type": "consu",
            "is_storable": True,
        })
        # Give the product a BoM so the action can create an MO.
        cls.env["mrp.bom"].create({
            "product_tmpl_id": cls.product.product_tmpl_id.id,
            "product_qty": 1.0,
        })
        cls.order = cls.env["sale.order"].create({
            "partner_id": cls.partner.id,
            "order_line": [(0, 0, {
                "product_id": cls.product.id,
                "name": "Mfg test cabinet",
                "product_uom_qty": 2.0,
            })],
        })

    def _fire(self):
        controller = ctrl_main.SouthbrookOrderBuilderPortal()
        controller._southbrook_resolve_order = lambda _id: self.order
        with stubbed_request(self.env):
            return controller.southbrook_api_order_action(
                self.order.id, action_code="send_to_manufacturing",
            )

    # ------------------------------------------------------------------
    # State gating
    # ------------------------------------------------------------------
    def test_rejects_draft_order_with_wrong_state(self):
        # New order is in 'draft' state — can't send to mfg.
        self.assertEqual(self.order.state, "draft")
        result = self._fire()
        self.assertEqual(result.get("error"), "wrong_state")
        # No MOs should have been created.
        self.assertFalse(self.env["mrp.production"].search([
            ("origin", "=", self.order.name),
        ]))

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------
    def test_creates_one_mo_per_line_in_sale_state(self):
        self.order.action_confirm()
        self.assertEqual(self.order.state, "sale")
        # Action_confirm in Odoo with a Storable+BoM product MAY
        # already create MOs via stock_account routing; tolerate both
        # paths (0 or 1 existing). The action should at minimum END
        # with one MO tied to the order's name.
        pre = self.env["mrp.production"].search([
            ("origin", "=", self.order.name),
        ])
        result = self._fire()
        self.assertTrue(result.get("ok"))
        self.assertGreaterEqual(result.get("mo_count"), 1)
        post = self.env["mrp.production"].search([
            ("origin", "=", self.order.name),
        ])
        self.assertGreaterEqual(len(post), 1)
        # Either we created a new one, or we reused an existing one.
        # 'existing_count' + 'new_count' should equal mo_count.
        self.assertEqual(
            result["mo_count"],
            result["new_count"] + result["existing_count"],
        )

    def test_re_fire_reuses_existing_mo(self):
        self.order.action_confirm()
        first = self._fire()
        self.assertTrue(first.get("ok"))
        second = self._fire()
        self.assertTrue(second.get("ok"))
        # Same MO id returned both times.
        self.assertEqual(first["mo_ids"], second["mo_ids"])
        # On the re-fire the existing_count should equal the total
        # mo_count (nothing new should be created).
        self.assertEqual(second["new_count"], 0)
        self.assertEqual(second["existing_count"], second["mo_count"])

    def test_chatter_message_posted(self):
        self.order.action_confirm()
        before = len(self.order.message_ids)
        self._fire()
        after = len(self.env["sale.order"].browse(self.order.id).message_ids)
        self.assertGreater(after, before)
