# SPDX-License-Identifier: LGPL-3.0-only
from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("southbrook", "exec_dashboard", "post_install", "-at_install")
class TestRevenueLast30dSumsOutInvoices(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create({"name": "Exec Test Co"})
        product = self.env["product.product"].search(
            [("sale_ok", "=", True)], limit=1
        )
        if not product:
            product = self.env["product.product"].create({
                "name": "Exec Test Product",
                "sale_ok": True,
                "type": "service",
                "list_price": 100.0,
            })
        self.product = product

    def _make_posted_invoice(self, amount, days_ago=5):
        invoice_date = fields.Date.context_today(self.env.user) - timedelta(
            days=days_ago
        )
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "invoice_date": invoice_date,
            "invoice_line_ids": [
                (0, 0, {
                    "product_id": self.product.id,
                    "quantity": 1.0,
                    "price_unit": amount,
                    "name": "test line",
                }),
            ],
        })
        invoice.action_post()
        return invoice

    def test_revenue_last_30d_sums_out_invoices(self):
        # Baseline: existing snapshot (so we measure delta from our writes)
        baseline = self.env["southbrook.exec_dashboard.snapshot"].create({})
        baseline_revenue = baseline.revenue_last_30d

        self._make_posted_invoice(500.0, days_ago=5)
        self._make_posted_invoice(750.0, days_ago=10)

        snapshot = self.env["southbrook.exec_dashboard.snapshot"].create({})
        delta = snapshot.revenue_last_30d - baseline_revenue
        # untaxed totals should equal $1250 from the 2 invoices we created
        self.assertAlmostEqual(
            delta, 1250.0, places=2,
            msg=(
                f"Revenue delta should be 1250.0, got {delta} "
                f"(baseline={baseline_revenue}, snapshot={snapshot.revenue_last_30d})"
            ),
        )
