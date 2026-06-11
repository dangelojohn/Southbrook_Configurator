# SPDX-License-Identifier: LGPL-3.0-only
"""Phase 4 Sprint 3 — per-line BoM fields in the order payload."""
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
        "bom_per_line")
class TestBomPayloadPerLine(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "BoM payload test",
            "email": "bom.payload.test@southbrook.test",
        })
        cls.product = cls.env["product.product"].create({
            "name": "BoM payload cabinet",
            "type": "consu", "is_storable": True,
        })
        cls.order = cls.env["sale.order"].create({
            "partner_id": cls.partner.id,
            "order_line": [(0, 0, {
                "product_id": cls.product.id,
                "name": "Base 2-Door · 30\" · Maple",
                "product_uom_qty": 1,
            })],
        })

    def test_payload_includes_sb_panel_count(self):
        """Per-line payload must include sb_panel_count from B2."""
        controller = ctrl_main.SouthbrookOrderBuilderPortal()
        with stubbed_request(self.env):
            payload = controller._build_southbrook_order_payload(
                self.order)
        self.assertEqual(len(payload["lines"]), 1)
        line = payload["lines"][0]
        self.assertIn("sb_panel_count", line)
        self.assertIn("sb_door_count", line)
        self.assertIn("sb_width_mm", line)

    def test_panel_count_positive_for_seeded_line(self):
        """The 30\" 2-door demo line must produce a positive panel
        count via B2 live-compute even without a config session."""
        controller = ctrl_main.SouthbrookOrderBuilderPortal()
        with stubbed_request(self.env):
            payload = controller._build_southbrook_order_payload(
                self.order)
        line = payload["lines"][0]
        self.assertGreater(line["sb_panel_count"], 0)
        self.assertEqual(line["sb_door_count"], 2)
        # 30 in -> 762 mm
        self.assertAlmostEqual(line["sb_width_mm"], 762.0, places=1)
