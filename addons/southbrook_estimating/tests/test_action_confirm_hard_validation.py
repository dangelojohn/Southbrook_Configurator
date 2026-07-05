# SPDX-License-Identifier: LGPL-3.0-only
"""QA follow-up (2026-07-05): action_confirm() must enforce the same
hard config-rule checks (Rule 1 series/door, Rule 2 Maple/Contractor)
that the customer portal's preflight check already enforced client-side
for its own "Send to Manufacturing" button. Before this fix, the
standard backend Sales Order "Confirm" button had no equivalent guard —
a rep could push an invalid line combination straight into a real
Manufacturing Order.

sale.order.line.name is user-editable free text (matches how the
portal's own validator reads it) — the simplest way to simulate an
already-invalid line without needing a real dynamic-variant product
carrying both attribute values is to write the offending description
directly onto the line, exactly as southbrook_hard_validation_issues()
scans it.
"""
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common import SouthbrookTestCase


@tagged("post_install", "-at_install", "southbrook", "rule_enforcement")
class TestActionConfirmHardValidation(SouthbrookTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmpl = cls.env.ref("southbrook_estimating.base_1dr")
        cls.partner = cls.Partner.create({"name": "Confirm Guard Test Customer"})
        cls.variant = cls.Product.create({"product_tmpl_id": cls.tmpl.id})

    def _make_order(self, line_name):
        order = self.Order.create({
            "partner_id": self.partner.id,
            # southbrook_mrp_pm gates action_confirm on production
            # approval for any order with cabinet lines — pre-approve so
            # these tests exercise OUR hard-validation guard specifically,
            # not that unrelated (and already-tested) approval gate.
            "production_approval_state": "approved",
        })
        self.env["sale.order.line"].create({
            "order_id": order.id,
            "product_id": self.variant.id,
            "name": line_name,
            "product_uom_qty": 1,
        })
        return order

    def test_confirm_blocked_on_maple_contractor_line(self):
        order = self._make_order(
            "Base Cabinet - Contractor Series, Maple Box")
        with self.assertRaises(
            UserError,
            msg="action_confirm must block a Maple + Contractor line, "
                "same as the portal's Send-to-Manufacturing preflight",
        ) as ctx:
            order.action_confirm()
        msg = str(ctx.exception)
        self.assertIn("Maple", msg)
        self.assertIn("Contractor", msg)
        self.assertNotEqual(
            order.state, "sale",
            "order must NOT have been confirmed when a hard rule fires",
        )

    def test_confirm_blocked_on_contractor_five_piece_line(self):
        order = self._make_order(
            "Wall Cabinet - Contractor Series, Five-Piece Door")
        with self.assertRaises(UserError) as ctx:
            order.action_confirm()
        self.assertIn("slab", str(ctx.exception).lower())
        self.assertNotEqual(order.state, "sale")

    def test_confirm_succeeds_on_clean_line(self):
        """Regression companion: a line with no rule violation must
        still confirm normally — the guard must not over-block."""
        order = self._make_order(
            "Base Cabinet - Contractor Series, White Melamine Box")
        order.action_confirm()
        self.assertEqual(order.state, "sale")

    def test_hard_validation_issues_method_shape(self):
        order = self._make_order(
            "Base Cabinet - Contractor Series, Maple Box")
        issues = order.southbrook_hard_validation_issues()
        self.assertEqual(len(issues), 1)
        issue = issues[0]
        self.assertEqual(issue["code"], "box_series_incompatible")
        self.assertEqual(issue["line_id"], order.order_line.id)
        self.assertIn("Maple", issue["message"])

    def test_hard_validation_issues_empty_for_clean_order(self):
        order = self._make_order("Base Cabinet - Standard")
        self.assertEqual(order.southbrook_hard_validation_issues(), [])
