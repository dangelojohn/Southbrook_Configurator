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

from odoo import _, api, fields, models
from odoo.exceptions import UserError


PRODUCTION_APPROVAL_SELECTION = [
    ("none", "Not Requested"),
    ("pending", "Pending Approval"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
]


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # ──────────────────────────────────────────────────────────────────
    # Production approval state machine
    # (referenced by views/order_form.xml via the
    #  view_order_form_production_approval inheritance, which has been
    #  live in the DB for some time without backing fields — Tier 0
    #  blocker fix.)
    # ──────────────────────────────────────────────────────────────────
    production_approval_state = fields.Selection(
        PRODUCTION_APPROVAL_SELECTION,
        string="Production Approval",
        default="none",
        required=True,
        copy=False,
        tracking=True,
        help="Gate between a confirmed sale order and the manufacturing "
             "queue. The sales rep requests production; a Production "
             "Approver reviews and approves (which fires "
             "action_send_to_production) or rejects (with a reason). "
             "Idempotent — re-confirming or re-quoting doesn't reset.",
    )
    production_requested_by = fields.Many2one(
        "res.users",
        string="Production Requested By",
        readonly=True, copy=False,
    )
    production_requested_date = fields.Datetime(
        string="Production Requested On",
        readonly=True, copy=False,
    )
    production_approved_by = fields.Many2one(
        "res.users",
        string="Production Approved By",
        readonly=True, copy=False,
        help="The user who approved or rejected — populated for both "
             "approve and reject paths so the audit trail is complete.",
    )
    production_approved_date = fields.Datetime(
        string="Production Decision Date",
        readonly=True, copy=False,
    )
    production_reject_reason = fields.Text(
        string="Rejection Reason",
        copy=False,
        help="Required when rejecting; surfaces back to the requester "
             "in the production-approval tab on the sale order.",
    )

    # ──────────────────────────────────────────────────────────────────
    # State-transition actions (referenced by the order form view's
    # Request / Approve / Reject buttons).
    # ──────────────────────────────────────────────────────────────────
    def action_request_production(self):
        """Move the order's approval state to 'pending'. Allowed from
        'none' or 'rejected' (re-request after a fix)."""
        for so in self:
            if so.state != "sale":
                raise UserError(_(
                    "Order %s must be confirmed (sale state) before "
                    "requesting production. Current state: %s."
                ) % (so.name, so.state))
            if so.production_approval_state not in ("none", "rejected"):
                raise UserError(_(
                    "Order %s is already %s — cannot re-request."
                ) % (so.name, so.production_approval_state))
            so.write({
                "production_approval_state": "pending",
                "production_requested_by": self.env.user.id,
                "production_requested_date": fields.Datetime.now(),
                # Clear prior rejection trail when re-requesting.
                "production_reject_reason": False,
            })
            so.message_post(body=_(
                "Production requested by %s."
            ) % self.env.user.display_name)
        return True

    def action_approve_production(self):
        """Move 'pending' → 'approved' AND fire MO creation. The two
        side-effects are bundled because the original view exposed
        only an Approve button — the operator's mental model is
        'approve = manufacture starts'."""
        created = self.env["mrp.production"]
        for so in self:
            if so.production_approval_state != "pending":
                raise UserError(_(
                    "Order %s is not pending approval (state: %s)."
                ) % (so.name, so.production_approval_state))
            so.write({
                "production_approval_state": "approved",
                "production_approved_by": self.env.user.id,
                "production_approved_date": fields.Datetime.now(),
            })
            mos = so.action_send_to_production()
            created |= mos
            mo_names = ", ".join(mos.mapped("name")) or _("none — no "
                "lines had a matching BoM")
            so.message_post(body=_(
                "Production approved by %s. Manufacturing orders: %s."
            ) % (self.env.user.display_name, mo_names))
        return created

    def action_reject_production(self):
        """Move 'pending' → 'rejected'. production_reject_reason must
        be set before calling this — surfaced as a UserError if blank
        so the requester always gets context."""
        for so in self:
            if so.production_approval_state != "pending":
                raise UserError(_(
                    "Order %s is not pending approval (state: %s)."
                ) % (so.name, so.production_approval_state))
            if not (so.production_reject_reason or "").strip():
                raise UserError(_(
                    "Provide a rejection reason in the Production "
                    "Approval tab before rejecting %s."
                ) % so.name)
            so.write({
                "production_approval_state": "rejected",
                "production_approved_by": self.env.user.id,
                "production_approved_date": fields.Datetime.now(),
            })
            so.message_post(body=_(
                "Production rejected by %s: %s"
            ) % (self.env.user.display_name, so.production_reject_reason))
        return True

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
                # Canonical sale→MRP backlink from sale_mrp. The
                # project readiness engine uses this to attach the MO
                # to the existing Kitchen Job task at create time.
                "sale_line_id": line.id,
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
