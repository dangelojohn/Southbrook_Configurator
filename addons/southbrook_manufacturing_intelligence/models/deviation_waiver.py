# SPDX-License-Identifier: LGPL-3.0-only
"""W012 — Engineering Deviation Waiver.

Source-of-truth doc: docs/MFG-REVIEW-R5-quality-ncr-rework.md § R5.4.

JTBD:
  "When a unit fails final QC but the cabinet is still installable with a
   customer waiver, I want a one-tap path to 'ship with deviation —
   engineering approved' instead of scrap or rework, so 18 months later
   in warranty we know exactly what we knew and when."

This module owns the WAIVER record (the audit-bearing object). The
mi.check side adds a thin state hook + a smart button (see mi_check.py).

Design notes:
  * `_inherit = ["mail.thread", "mail.activity.mixin"]` so the chatter
    captures every state transition + every customer-ack attachment.
    Per R5.4 the warranty trace 3 years out is the whole point of this
    record.
  * SoD: the engineering approver must NOT equal the mi.check creator
    (the QC who flagged the defect). Enforced in action_approve.
  * Customer acknowledgement is captured as `(method, ref,
    attachment_ids)`. attachment_ids hangs off the chatter pipeline
    (mail.thread message attachments are the v19 file-storage-strategy
    surface). NEVER add raw Binary — gets stuck in the DB.
  * Approval is ALWAYS manual. No auto-approve cron, no auto-ship.
  * Per CLAUDE.md no group_pg_eng exists in MI; the engineering role
    is proxied by `mrp.group_mrp_manager` (matches R5.4 line 109).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, AccessError


WAIVER_STATES = [
    ("draft", "Draft"),
    ("eng_review", "Engineering Review"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
]


CUSTOMER_ACK_METHODS = [
    ("email", "Customer email"),
    ("phone", "Phone call (logged)"),
    ("in_person", "In-person"),
    ("po_amendment", "Customer PO amendment"),
]


class DeviationWaiver(models.Model):
    _name = "southbrook.deviation.waiver"
    _description = (
        "Engineering Deviation Waiver — ship-with-defect approval record"
    )
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    name = fields.Char(
        string="Waiver",
        required=True, copy=False, readonly=True, index=True,
        default=lambda self: _("New"),
        help="Auto-sequenced WV-YYYY-NNNN.",
    )
    active = fields.Boolean(default=True)

    # ------------------------------------------------------------------
    # Source NCR + traceability chain
    # ------------------------------------------------------------------
    mi_check_id = fields.Many2one(
        "southbrook.mi.check",
        string="NCR / MI Check",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        help="The non-conformance the customer is being asked to "
             "accept. Restricted ondelete so warranty trace stays intact "
             "even if QC tries to scrub the NCR.",
    )
    production_id = fields.Many2one(
        "mrp.production",
        string="Manufacturing Order",
        related="mi_check_id.production_id",
        store=True, index=True, readonly=True,
    )
    cabinet_serial = fields.Char(
        string="Cabinet Serial",
        compute="_compute_cabinet_serial",
        store=True, readonly=True, index=True,
        help="Snapshot of MO.lot_producing_id.name at compute time — "
             "the field-tech-facing identifier 3 years out.",
    )
    customer_id = fields.Many2one(
        "res.partner",
        string="Customer",
        compute="_compute_customer_id",
        store=True, readonly=False, tracking=True,
        help="Resolved from MO.sale_line_id.order_id.partner_id when "
             "the MO has a sale-order origin. Editable so the waiver "
             "still works for stock-build / dealer-channel MOs.",
    )

    # ------------------------------------------------------------------
    # Deviation details
    # ------------------------------------------------------------------
    defect_summary = fields.Text(
        string="Defect Summary",
        required=True, tracking=True,
        help="Human-readable description of what the customer is being "
             "asked to accept. Quoted in any future warranty claim.",
    )
    engineering_rationale = fields.Text(
        string="Engineering Rationale",
        tracking=True,
        help="Engineering's call on why this is acceptable to ship — "
             "structural integrity argument, aesthetic-only argument, "
             "etc. Read 3 years later by warranty.",
    )

    # ------------------------------------------------------------------
    # Customer acknowledgement
    # ------------------------------------------------------------------
    customer_acknowledged = fields.Boolean(
        string="Customer Acknowledged",
        tracking=True,
        help="QC ticks this after capturing acknowledgement — required "
             "before engineering can approve.",
    )
    customer_acknowledgment_method = fields.Selection(
        CUSTOMER_ACK_METHODS,
        string="Acknowledgement Method",
        tracking=True,
    )
    customer_acknowledgment_ref = fields.Char(
        string="Acknowledgement Reference",
        tracking=True,
        help="Email subject, call note ID, PO amendment number — any "
             "external pointer that lets us find the artefact later.",
    )

    # ------------------------------------------------------------------
    # Engineering approval
    # ------------------------------------------------------------------
    engineering_approver_id = fields.Many2one(
        "res.users",
        string="Engineering Approver",
        tracking=True, readonly=True, copy=False,
        help="The user who approved (or rejected) the waiver. Stamped "
             "by action_approve / action_reject; never user-editable.",
    )
    engineering_approved_at = fields.Datetime(
        string="Approved At",
        readonly=True, copy=False, tracking=True,
    )
    engineering_notes = fields.Text(
        string="Engineering Notes",
        tracking=True,
        help="Engineering's notes captured at approve/reject time.",
    )

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------
    state = fields.Selection(
        WAIVER_STATES,
        string="Status",
        default="draft", required=True, tracking=True, index=True, copy=False,
    )

    # ------------------------------------------------------------------
    # C1 — the 'approved' transition is governance-critical (it lets an
    # out-of-spec cabinet ship). Every gate — engineering-group check, SoD,
    # customer-acknowledgement, terminal-state block — lives in action_approve.
    # The QC group has ORM write on this model, so a raw
    # write({"state": "approved"}) would bypass ALL of it (forged approver, no
    # sign-off). Block the direct transition; it may only be reached through
    # action_approve (which sets the private context flag below).
    # ------------------------------------------------------------------
    def write(self, vals):
        if (not self.env.su
                and vals.get("state") == "approved"
                and not self.env.context.get("_sbk_waiver_approve_action")):
            raise AccessError(_(
                "A deviation waiver can only be approved via the Approve "
                "action, which enforces engineering sign-off, segregation of "
                "duties, and customer acknowledgement."))
        return super().write(vals)

    # ------------------------------------------------------------------
    # Computed fields
    # ------------------------------------------------------------------
    @api.depends("production_id", "production_id.lot_producing_ids")
    def _compute_cabinet_serial(self):
        for rec in self:
            mo = rec.production_id
            lots = mo.lot_producing_ids if mo else False
            rec.cabinet_serial = lots[:1].name if lots else False

    @api.depends("production_id")
    def _compute_customer_id(self):
        for rec in self:
            if rec.customer_id:
                # Respect a manually-set customer — don't clobber.
                continue
            mo = rec.production_id
            order_line = getattr(mo, "sale_line_id", False) if mo else False
            so = order_line.order_id if order_line else False
            rec.customer_id = (so.partner_id.id if so and so.partner_id
                               else False)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = (
                    seq.next_by_code("southbrook.deviation.waiver")
                    or _("WV/New")
                )
        records = super().create(vals_list)
        for rec in records:
            rec.message_post(
                body=_(
                    "Deviation waiver drafted against NCR %(ncr)s "
                    "(MO %(mo)s).",
                    ncr=rec.mi_check_id.display_name or "?",
                    mo=(rec.production_id.name if rec.production_id
                        else "—"),
                )
            )
        return records

    # ------------------------------------------------------------------
    # Workflow actions
    # ------------------------------------------------------------------
    def action_submit_for_eng_review(self):
        """QC submits the draft waiver for engineering's call."""
        for rec in self:
            if rec.state != "draft":
                raise UserError(_(
                    "Only draft waivers can be submitted for review "
                    "(this one is %(state)s).",
                    state=dict(WAIVER_STATES).get(rec.state, rec.state),
                ))
            if not rec.defect_summary:
                raise UserError(_(
                    "Defect summary is required before submitting for "
                    "engineering review."))
            rec.state = "eng_review"
            rec.message_post(body=_(
                "Submitted for engineering review by %(user)s.",
                user=self.env.user.display_name,
            ))
            # Also flip the source NCR so the floor knows the deviation
            # path is in flight (don't auto-ship — that's still a
            # manual call gated on action_approve below).
            if rec.mi_check_id:
                rec.mi_check_id.sudo().write({
                    "state": "pending_deviation_approval",
                    "deviation_waiver_id": rec.id,
                })
        return True

    def action_approve(self):
        """Engineering approves the waiver.

        Enforces:
          * Caller is in mrp.group_mrp_manager (or admin)
          * Caller is NOT the mi.check creator (SoD)
          * Customer acknowledgement is captured
        """
        eng_group = self.env.ref(
            "mrp.group_mrp_manager", raise_if_not_found=False)
        for rec in self:
            if rec.state not in ("draft", "eng_review"):
                raise UserError(_(
                    "Only draft or eng-review waivers can be approved "
                    "(this one is %(state)s).",
                    state=dict(WAIVER_STATES).get(rec.state, rec.state),
                ))
            if eng_group and eng_group not in self.env.user.group_ids \
                    and not self.env.user.has_group("base.group_system"):
                raise AccessError(_(
                    "Only Manufacturing Managers (engineering) can "
                    "approve a deviation waiver."))
            # SoD — the approver must not be the person who REQUESTED the
            # waiver (rec.create_uid). The old check compared the underlying
            # NCR's create_uid, but engine-generated NCRs (the majority) are
            # created via sudo → create_uid = OdooBot, so it NEVER tripped: the
            # same manager could raise the waiver via the wizard and approve it.
            requester = rec.create_uid
            if requester and requester == self.env.user \
                    and not self.env.user.has_group("base.group_system"):
                raise AccessError(_(
                    "Segregation of Duties: the engineer approving the "
                    "waiver cannot be the one who requested it. Have a "
                    "second engineer approve."))
            if not rec.customer_acknowledged:
                raise UserError(_(
                    "Cannot approve until customer acknowledgement is "
                    "captured (tick the box + record the method + ref)."))
            rec.with_context(_sbk_waiver_approve_action=True).write({
                "state": "approved",
                "engineering_approver_id": self.env.user.id,
                "engineering_approved_at": fields.Datetime.now(),
            })
            rec.message_post(body=_(
                "Waiver APPROVED by %(user)s. Cabinet may ship with "
                "deviation; engineering rationale + customer ack on "
                "file.",
                user=self.env.user.display_name,
            ))
            # Flip the source NCR — but do NOT auto-complete the MO.
            # Closing the MO is still a manual planner action.
            if rec.mi_check_id:
                rec.mi_check_id.sudo().write({
                    "state": "ship_with_deviation",
                })
        return True

    def action_reject(self):
        """Engineering rejects — cabinet must be reworked or scrapped."""
        for rec in self:
            if rec.state not in ("draft", "eng_review"):
                raise UserError(_(
                    "Only draft or eng-review waivers can be rejected "
                    "(this one is %(state)s)."))
            rec.write({
                "state": "rejected",
                "engineering_approver_id": self.env.user.id,
                "engineering_approved_at": fields.Datetime.now(),
            })
            rec.message_post(body=_(
                "Waiver REJECTED by %(user)s. Cabinet must be reworked "
                "or scrapped — not shipped.",
                user=self.env.user.display_name,
            ))
            if rec.mi_check_id:
                # Reset the NCR state — the planner now has to choose
                # rework or scrap manually.
                rec.mi_check_id.sudo().write({
                    "state": "draft",
                })
        return True

    def action_open_mi_check(self):
        """Smart button — jump to the source NCR."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "southbrook.mi.check",
            "res_id": self.mi_check_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_production(self):
        """Smart button — jump to the MO."""
        self.ensure_one()
        if not self.production_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "mrp.production",
            "res_id": self.production_id.id,
            "view_mode": "form",
            "target": "current",
        }
