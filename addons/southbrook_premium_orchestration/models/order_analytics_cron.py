# SPDX-License-Identifier: LGPL-3.0-only
"""
southbrook.order.analytics cron extension — unscored-order backfill.

Phase 1.2 of Southbrook Premium MRP Orchestration. Closes the
~10%-coverage gap (9 records on 92 sale orders at time of writing) by
sweeping confirmed sale orders that don't yet have an analytics row
and invoking the model's existing idempotent ``capture()`` method on
each.

NF1 carve-out: this file does NOT count against the 7-routine custom
register. There is no new business math — capture() already exists in
``southbrook_estimating/models/southbrook_order_analytics.py`` and
encapsulates the rollup. This cron is a thin discovery + dispatch
loop with defensive per-order error isolation.
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class SouthbrookOrderAnalytics(models.Model):
    _inherit = "southbrook.order.analytics"

    @api.model
    def _cron_backfill_unscored(self):
        """Backfill analytics rows for confirmed sale orders missing them.

        Selects ``sale.order`` records in state ``sale`` (confirmed)
        that don't yet appear in ``southbrook_order_analytics`` and
        captures each one. Per-order failures are logged but never
        re-raised so a single bad order can't poison the whole sweep.

        Returns the number of orders successfully captured.
        """
        # NOT IN via raw subquery on the m2o column; cheap and avoids
        # pulling the full analytics table into Python.
        self.env.cr.execute(
            """
            SELECT so.id
              FROM sale_order so
         LEFT JOIN southbrook_order_analytics soa
                ON soa.sale_order_id = so.id
             WHERE so.state = 'sale'
               AND soa.id IS NULL
          ORDER BY so.id
            """
        )
        order_ids = [row[0] for row in self.env.cr.fetchall()]
        if not order_ids:
            _logger.info(
                "Southbrook analytics backfill: no unscored orders, "
                "all confirmed orders already captured."
            )
            return 0

        _logger.info(
            "Southbrook analytics backfill: %d unscored confirmed "
            "orders found, capturing…",
            len(order_ids),
        )
        captured = 0
        SaleOrder = self.env["sale.order"]
        for order_id in order_ids:
            order = SaleOrder.browse(order_id)
            try:
                self.capture(order)
                captured += 1
            except Exception as exc:  # noqa: BLE001 — cron must stay green
                _logger.warning(
                    "Southbrook analytics backfill: capture failed "
                    "for sale.order %s (%s) — skipping.",
                    order_id,
                    exc,
                )
        _logger.info(
            "Southbrook analytics backfill: captured %d / %d unscored "
            "orders.",
            captured,
            len(order_ids),
        )
        return captured
