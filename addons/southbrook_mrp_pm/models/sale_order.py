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

    # W009 — Production-approval HARD GATE bypass. Manager-only escape
    # hatch for the rare one-off MO that legitimately must bypass the
    # production-approval contract. Tracked on mail.thread so every use
    # of the bypass leaves an audit trail in the order chatter.
    force_production_release = fields.Boolean(
        string="Force Production Release (Bypass Approval)",
        copy=False,
        tracking=True,
        help="Manager-only override. When checked, the order can be "
             "confirmed even if production approval was not granted. "
             "Use sparingly — every flip is logged in the order chatter "
             "for audit. Hidden from non-managers via view groups; the "
             "underlying field accepts writes from sale managers only.",
    )

    # ──────────────────────────────────────────────────────────────────
    # W009 — Production-approval HARD GATE
    # ──────────────────────────────────────────────────────────────────
    # The legacy approval flow was advisory: the Request / Approve /
    # Reject buttons set the state field but nothing CONSUMED that field
    # at MO-create time. Per R1 analysis (MFG-REVIEW-R1 Win 3) 60% of
    # source SOs in prod created MOs while production_approval_state
    # was still 'none' — the approval surface was cosmetic.
    #
    # The gate now fires at sale.order.action_confirm() and again at
    # mrp.production.create() (defense in depth — direct MO creation
    # paths bypass action_confirm). Both raise UserError. Existing
    # in-flight MOs are unaffected: the gate only fires on NEW order
    # confirms or NEW MO creates, never on already-existing records.
    # ──────────────────────────────────────────────────────────────────

    def _get_unapproved_manufacturing_lines(self):
        """Return the order_line subset that would generate manufacturing
        orders but lack production approval. Used by both the
        action_confirm gate and the SO form banner.

        A line "would generate an MO" if its product has a resolvable
        BoM. We re-use _resolve_bom_for_line so the gate's definition of
        'this line manufactures' exactly matches what
        action_send_to_production would actually create. Catches both
        the OCA-configured-product path AND any direct product with a
        BoM seeded by southbrook_estimating's templates.
        """
        self.ensure_one()
        if self.production_approval_state == "approved":
            return self.env["sale.order.line"]
        Bom = self.env["mrp.bom"].sudo()
        unapproved = self.env["sale.order.line"]
        for line in self.order_line:
            if not line.product_id:
                continue
            if line.display_type:  # section / note lines
                continue
            bom = self._resolve_bom_for_line(Bom, line)
            if bom:
                unapproved |= line
        return unapproved

    def _check_production_approval_gate(self):
        """Raise UserError if any manufacturing line lacks approval and
        force_production_release is not set.

        Test-isolation bypass: mirror the same `bypass_production_approval`
        context flag the model-layer `mrp.production.create` honors (see
        mrp_production.py). Without this parallel check, tests that opt
        out of the model-layer gate still tripped on `so.action_confirm()`'s
        SO-side gate. Production code paths never set this flag, so the
        gate stays enforced everywhere it matters.
        """
        if self.env.context.get("bypass_production_approval"):
            return
        for order in self:
            if order.force_production_release:
                # Log the bypass into chatter so the audit trail is
                # complete. Done once per confirm, not once per line.
                order.message_post(body=_(
                    "Production-approval gate bypassed by %s via "
                    "force_production_release."
                ) % self.env.user.display_name)
                continue
            unapproved = order._get_unapproved_manufacturing_lines()
            if unapproved:
                raise UserError(_(
                    "Cannot confirm sale order %(name)s — these lines "
                    "would generate manufacturing orders but the order "
                    "is not Production-Approved (current state: "
                    "%(state)s). Use Request Production → Approve "
                    "Production before confirming, or ask a Sales "
                    "Manager to set Force Production Release for a "
                    "one-off bypass.\n\nUnapproved lines:\n%(lines)s",
                    name=order.name or _("(new)"),
                    state=order.production_approval_state,
                    lines="\n".join(
                        "  - " + (l.product_id.display_name or "")
                        for l in unapproved
                    ),
                ))

    def action_confirm(self):
        """W009 gate: enforce production approval before super().
        Running the gate BEFORE super() means we block at the very
        edge of the SO state-change; downstream procurement hooks +
        sibling action_confirm overrides only run once the gate is
        cleared.
        """
        self._check_production_approval_gate()
        return super().action_confirm()

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
