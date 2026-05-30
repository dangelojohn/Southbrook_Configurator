# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for the NF6 Image Floor iterative-design pattern:
sale.order.parent_order_id + version + action_duplicate_as_draft.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "nf6")
class TestSaleOrderVersioning(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "NF6 Image Floor Partner",
            "channel": "dealer",
        })

    def test_01_fresh_order_version_is_1(self):
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.assertEqual(order.version, 1)
        self.assertFalse(order.parent_order_id)

    def test_02_duplicate_as_draft_creates_v2_with_parent_link(self):
        v1 = self.env["sale.order"].create({"partner_id": self.partner.id})
        action = v1.action_duplicate_as_draft()
        v2 = self.env["sale.order"].browse(action["res_id"])
        self.assertEqual(v2.version, 2)
        self.assertEqual(v2.parent_order_id, v1)
        self.assertEqual(v2.state, "draft")
        # v1 unaffected.
        self.assertEqual(v1.version, 1)
        self.assertFalse(v1.parent_order_id)

    def test_03_duplicate_chain_v1_v2_v3(self):
        v1 = self.env["sale.order"].create({"partner_id": self.partner.id})
        v2 = self.env["sale.order"].browse(
            v1.action_duplicate_as_draft()["res_id"]
        )
        v3 = self.env["sale.order"].browse(
            v2.action_duplicate_as_draft()["res_id"]
        )
        self.assertEqual(v3.version, 3)
        self.assertEqual(v3.parent_order_id, v2)
        self.assertEqual(v2.parent_order_id, v1)
        self.assertFalse(v1.parent_order_id)

    def test_04_duplicate_preserves_partner_and_pricelist(self):
        v1 = self.env["sale.order"].create({"partner_id": self.partner.id})
        v2 = self.env["sale.order"].browse(
            v1.action_duplicate_as_draft()["res_id"]
        )
        self.assertEqual(v2.partner_id, v1.partner_id)
        # Pricelist was resolved by the channel dispatcher on v1; v2 inherits.
        self.assertEqual(v2.pricelist_id, v1.pricelist_id)

    def test_05_action_returns_form_action_descriptor(self):
        v1 = self.env["sale.order"].create({"partner_id": self.partner.id})
        action = v1.action_duplicate_as_draft()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "sale.order")
        self.assertEqual(action["view_mode"], "form")
        self.assertIn("v2", action["name"])
