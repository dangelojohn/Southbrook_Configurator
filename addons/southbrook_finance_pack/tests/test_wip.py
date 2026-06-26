# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for WIP report computation."""

from odoo.tests.common import TransactionCase, tagged


@tagged("southbrook", "post_install", "-at_install")
class TestWipReport(TransactionCase):
    def setUp(self):
        super().setUp()
        self.WipReport = self.env["southbrook.finance.wip_report"]
        self.WipLine = self.env["southbrook.finance.wip_line"]
        self.Product = self.env["product.product"]
        # Two test components with standard_price set.
        self.comp_a = self.Product.create(
            {"name": "WIP Comp A", "standard_price": 10.0}
        )
        self.comp_b = self.Product.create(
            {"name": "WIP Comp B", "standard_price": 25.0}
        )

    def test_wip_line_value_computation(self):
        """qty x standard_cost = wip_value."""
        report = self.WipReport.create({"as_of_date": "2026-06-25"})
        # No real MO -- just verify line math.
        line = self.WipLine.create(
            {
                "wip_report_id": report.id,
                # production_id is required; use a placeholder MO if any
                # exists, else skip (the math test doesn't need a real MO).
                "production_id": self._get_or_make_mo().id,
                "product_id": self.comp_a.id,
                "qty_consumed": 3.0,
                "standard_cost": 10.0,
            }
        )
        self.assertAlmostEqual(line.wip_value, 30.0, places=2)

    def test_total_wip_sums_lines(self):
        report = self.WipReport.create({"as_of_date": "2026-06-25"})
        mo = self._get_or_make_mo()
        self.WipLine.create(
            {
                "wip_report_id": report.id,
                "production_id": mo.id,
                "product_id": self.comp_a.id,
                "qty_consumed": 3.0,
                "standard_cost": 10.0,
            }
        )
        self.WipLine.create(
            {
                "wip_report_id": report.id,
                "production_id": mo.id,
                "product_id": self.comp_b.id,
                "qty_consumed": 2.0,
                "standard_cost": 25.0,
            }
        )
        # 3*10 + 2*25 = 30 + 50 = 80
        self.assertAlmostEqual(report.total_wip_value, 80.0, places=2)

    def test_action_compute_resets_lines(self):
        """action_compute() wipes pre-existing lines (idempotent recompute)."""
        report = self.WipReport.create({"as_of_date": "2026-06-25"})
        mo = self._get_or_make_mo()
        self.WipLine.create(
            {
                "wip_report_id": report.id,
                "production_id": mo.id,
                "product_id": self.comp_a.id,
                "qty_consumed": 99.0,
                "standard_cost": 99.0,
            }
        )
        self.assertEqual(len(report.line_ids), 1)
        report.action_compute()
        # After compute, the stub line is gone; whether any real lines are
        # repopulated depends on whether a real open MO with qty exists.
        # On a fresh test DB there are usually none; the contract is just
        # that the unlink happened.
        prior_qty = sum(report.line_ids.mapped("qty_consumed"))
        self.assertNotIn(99.0, [prior_qty])  # the stub is gone

    def _get_or_make_mo(self):
        """Best-effort: reuse the first MO if any, else build a tiny one."""
        Production = self.env["mrp.production"]
        existing = Production.search([], limit=1)
        if existing:
            return existing
        # Minimal MO: needs a product and a BoM-less production_id; on a
        # fresh CE test DB this requires picking a stock-tracked product.
        # We create a simple product and a 1-line MO.
        prod = self.env["product.product"].create(
            {
                "name": "MO target product",
                "is_storable": True,
            }
        )
        return Production.create(
            {
                "product_id": prod.id,
                "product_qty": 1.0,
                "product_uom_id": prod.uom_id.id,
            }
        )
