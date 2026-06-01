# SPDX-License-Identifier: LGPL-3.0-only
"""sale.order extension — Send-to-Production action.

M3 + M7 of the Manufacturing PM JTBD gap analysis (2026-06-01):

  Pre-fix: the customer-facing OrderBuilder shows a 'Send to
  Production' button in dealer mode (FooterActions component),
  but the underlying action_code='send_to_production' is not yet
  wired. Clicking it returns 'unknown_action' from the dispatcher.

  Wire shape (this commit):
    sale.order.action_send_to_production() — for each confirmed line
      with a resolvable BoM, creates one mrp.production carrying the
      M6 routing, confirms it, and returns the MO ids. Returns a
      list of MO records for the controller to translate into a
      JSON-RPC payload.

  Send-to-Production is idempotent on the sale.order — if MOs
  already exist with origin=order.name, the call is a no-op that
  returns the existing MO ids.

  Out of scope for this commit:
    - The other 11 SB-* SKUs need parallel BoM + routing seeds
      (their lines will skip MO creation until that lands).
    - Scheduling logic: today date_start=now(), date_deadline=
      now()+SUM(routing minutes). Realistic capacity-aware
      scheduling lives in M18.
    - ECO → in-flight MO notification (M20).
"""
from datetime import timedelta

from odoo import _, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_send_to_production(self):
        """Create one mrp.production per order line that has a
        resolvable BoM. Idempotent on the sale.order: existing
        MOs with origin matching this order's name are returned
        unchanged.

        Returns:
            recordset of mrp.production created OR already-existing
            for this order.

        Raises:
            UserError if the order is not in 'sale' state.
        """
        self.ensure_one()
        if self.state != "sale":
            raise UserError(_(
                "Order %(name)s must be confirmed (sale state) before "
                "sending to production. Current state: %(state)s."
            ) % {"name": self.name, "state": self.state})

        MO = self.env["mrp.production"].sudo()
        Bom = self.env["mrp.bom"].sudo()

        # Idempotency: short-circuit if MOs already exist for this SO.
        existing = MO.search([("origin", "=", self.name)])
        if existing:
            return existing

        created = MO.browse()
        for line in self.order_line:
            if not line.product_id:
                continue
            # Resolve the BoM applicable to this variant. _bom_find
            # signature varies across Odoo versions; cover both.
            bom = self._resolve_bom_for_line(Bom, line)
            if not bom:
                continue

            # Schedule: start now, finish at now + total routing time.
            total_minutes = sum(
                w.time_cycle_manual for w in bom.operation_ids
            )
            start = fields.Datetime.now()
            deadline = start + timedelta(minutes=total_minutes)

            # Odoo 19 renamed sale.order.line.product_uom → product_uom_id.
            line_uom = (
                line.product_uom_id
                if hasattr(line, "product_uom_id")
                else line.product_uom
            )
            mo = MO.create({
                "product_id": line.product_id.id,
                "product_uom_id": line_uom.id,
                "product_qty": line.product_uom_qty,
                "bom_id": bom.id,
                "origin": self.name,
                "date_start": start,
                "date_deadline": deadline,
            })
            # Confirm the MO so work orders materialise from the
            # routing. The standard flow is create → confirm →
            # plan → start. Confirm gives Floor Manager visibility
            # in the kanban board; planning + start happens on the
            # floor.
            mo.action_confirm()
            created |= mo

        return created

    @staticmethod
    def _resolve_bom_for_line(Bom, line):
        """Find the lowest-sequence normal BoM for the line's variant
        or template. Falls back to a plain search if _bom_find is
        unavailable / signature mismatched."""
        # Modern Odoo (16+) — _bom_find takes a recordset and returns
        # a dict keyed by product.
        if hasattr(Bom, "_bom_find"):
            try:
                result = Bom._bom_find(
                    products=line.product_id,
                    company_id=line.company_id.id,
                    bom_type="normal",
                )
                if isinstance(result, dict):
                    bom = result.get(line.product_id)
                    if bom:
                        return bom
            except TypeError:
                # Older signature — fall through to search.
                pass

        # Fallback search: lowest-sequence normal BoM matching the
        # variant or the variant's template.
        return Bom.search(
            [
                "|",
                ("product_id", "=", line.product_id.id),
                "&",
                ("product_id", "=", False),
                (
                    "product_tmpl_id",
                    "=",
                    line.product_id.product_tmpl_id.id,
                ),
                ("type", "=", "normal"),
            ],
            order="sequence, id",
            limit=1,
        )
