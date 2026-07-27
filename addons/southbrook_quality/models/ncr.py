# SPDX-License-Identifier: LGPL-3.0-only
"""Non-Conformance Report (NCR).

State machine (linear with terminal branches):

    draft -> quarantine -> { rework | scrap | released } -> cancelled? -> closed

Disposition reason is required on any move from quarantine to a terminal
state. closed_at + time_to_close_hours are populated when the record
reaches a terminal state.

NOTE on workorder_id:
    mrp_workorder is an Enterprise-only module on Odoo 19 and is not
    installable on this CE build. We therefore deliberately OMIT a
    workorder_id Many2one. The southbrook_premium_orchestration module
    references mrp.workorder but lives behind its own install gate; the
    quality module is meant to install cleanly on a CE-only stack with
    no Enterprise bridge.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


VALID_TRANSITIONS = {
    "draft": {"quarantine", "cancelled"},
    "quarantine": {"rework", "scrap", "released", "cancelled"},
    "rework": {"released", "cancelled"},
    "scrap": set(),
    "released": set(),
    "cancelled": set(),
}

TERMINAL_STATES = {"released", "scrap", "cancelled"}
DISPOSITION_REQUIRED_STATES = {"rework", "scrap", "released"}


class SouthbrookNcr(models.Model):
    _name = "southbrook.ncr"
    _description = "Southbrook Non-Conformance Report"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(
        string="NCR Reference",
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _("New"),
        tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("quarantine", "Quarantine"),
            ("rework", "Rework"),
            ("scrap", "Scrap"),
            ("released", "Released"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    production_id = fields.Many2one(
        "mrp.production",
        string="Manufacturing Order",
        tracking=True,
    )
    production_package_id = fields.Many2one(
        "sb.production.package",
        string="Production Package",
        tracking=True,
    )
    workcenter_id = fields.Many2one(
        "mrp.workcenter",
        string="Work Center",
        tracking=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        tracking=True,
    )
    lot_id = fields.Many2one(
        "stock.lot",
        string="Lot / Serial",
    )
    quantity = fields.Float(string="Quantity Affected", default=0.0)
    defect_type = fields.Selection(
        [
            ("dimension", "Dimensional"),
            ("surface", "Surface Defect"),
            ("hardware", "Hardware"),
            ("finish", "Finish"),
            ("assembly", "Assembly"),
            ("material", "Material"),
            ("other", "Other"),
        ],
        required=True,
        default="other",
        tracking=True,
    )
    severity = fields.Selection(
        [
            ("minor", "Minor"),
            ("major", "Major"),
            ("critical", "Critical"),
        ],
        required=True,
        default="minor",
        tracking=True,
    )
    description = fields.Text(string="Description")
    responsible_user_id = fields.Many2one(
        "res.users",
        string="Responsible",
        default=lambda self: self.env.user,
        tracking=True,
    )
    disposition_reason = fields.Text(string="Disposition Reason", tracking=True)
    opened_at = fields.Datetime(
        string="Opened At",
        default=fields.Datetime.now,
        readonly=True,
        tracking=True,
        help="When the NCR was raised — the SLA start for time-to-close. A "
             "writable field rather than the magic create_date (which v19 "
             "silently refuses to overwrite and is a DB-transaction timestamp).",
    )
    closed_at = fields.Datetime(string="Closed At", readonly=True, tracking=True)
    time_to_close_hours = fields.Float(
        string="Time to Close (h)",
        compute="_compute_time_to_close_hours",
        store=True,
    )

    # Many2many to ir.attachment for photos; cleaner than a computed reverse
    # by res_model/res_id pair on the chatter attachments.
    photo_ids = fields.Many2many(
        "ir.attachment",
        "southbrook_ncr_photo_rel",
        "ncr_id",
        "attachment_id",
        string="Photos",
    )

    spc_sample_id = fields.Many2one(
        "southbrook.quality.spc_sample",
        string="Triggering SPC Sample",
        ondelete="set null",
    )

    # ---------------------------------------------------------------------
    # Create / compute
    # ---------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                seq = self.env["ir.sequence"].next_by_code("southbrook.ncr")
                vals["name"] = seq or _("New")
            # Default responsible to workcenter supervisor when available.
            if not vals.get("responsible_user_id") and vals.get("workcenter_id"):
                wc = self.env["mrp.workcenter"].browse(vals["workcenter_id"])
                # mrp.workcenter has no canonical "supervisor" field across
                # versions; fall back to the current user.
                vals["responsible_user_id"] = self.env.user.id
        return super().create(vals_list)

    @api.depends("opened_at", "closed_at")
    def _compute_time_to_close_hours(self):
        for rec in self:
            start = rec.opened_at or rec.create_date
            if start and rec.closed_at:
                delta = rec.closed_at - start
                # Clamp: app-server (closed_at) vs DB-server (create_date
                # fallback) clock skew can otherwise yield a small negative.
                rec.time_to_close_hours = max(0.0, delta.total_seconds() / 3600.0)
            else:
                rec.time_to_close_hours = 0.0

    # ---------------------------------------------------------------------
    # State machine helpers
    # ---------------------------------------------------------------------
    def _ensure_transition(self, target_state):
        for rec in self:
            allowed = VALID_TRANSITIONS.get(rec.state, set())
            if target_state not in allowed:
                raise UserError(
                    _(
                        "Cannot move NCR %(name)s from %(src)s to %(dst)s.",
                        name=rec.name,
                        src=rec.state,
                        dst=target_state,
                    )
                )
            if target_state in DISPOSITION_REQUIRED_STATES and not (
                rec.disposition_reason and rec.disposition_reason.strip()
            ):
                raise UserError(
                    _(
                        "A disposition reason is required to set NCR %(name)s to %(dst)s.",
                        name=rec.name,
                        dst=target_state,
                    )
                )

    def write(self, vals):
        # Governance: the transition graph + mandatory-disposition gate live
        # in _ensure_transition, which is only called from the action buttons.
        # Without this, a user with write access could raw-write
        # state='released' via call_kw — skipping quarantine, the disposition
        # reason, and closed_at (no audit trail). Route every state change
        # through the guard; the guarded actions set _ncr_state_ok to bypass
        # the re-check (they already validated).
        if "state" in vals and not self.env.context.get("_ncr_state_ok"):
            for rec in self:
                if vals["state"] != rec.state:
                    rec._ensure_transition(vals["state"])
        return super().write(vals)

    def _apply_state(self, target_state, message):
        self._ensure_transition(target_state)
        vals = {"state": target_state}
        if target_state in TERMINAL_STATES:
            vals["closed_at"] = fields.Datetime.now()
        self.with_context(_ncr_state_ok=True).write(vals)
        for rec in self:
            rec.message_post(body=message)

    # ---------------------------------------------------------------------
    # Public actions
    # ---------------------------------------------------------------------
    def action_quarantine(self):
        self._apply_state("quarantine", _("NCR moved to Quarantine."))

    def action_rework(self):
        self._apply_state("rework", _("NCR routed to Rework."))

    def action_scrap(self):
        self._apply_state("scrap", _("NCR disposition: Scrap."))

    def action_release(self):
        # A "use-as-is" release ships a known-defective part. For a CRITICAL
        # (potentially safety-relevant) NCR, require Quality-Manager sign-off.
        mgr = "southbrook_quality.group_southbrook_quality_manager"
        for rec in self:
            if rec.severity == "critical" and not self.env.user.has_group(mgr):
                raise UserError(_(
                    "Use-as-is release of a CRITICAL NCR (%s) requires a "
                    "Quality Manager sign-off.", rec.name))
        self._apply_state("released", _("NCR Released (use-as-is)."))

    def action_cancel(self):
        self._apply_state("cancelled", _("NCR Cancelled."))
