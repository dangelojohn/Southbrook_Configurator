# SPDX-License-Identifier: LGPL-3.0-only
from odoo import _, api, fields, models
from odoo.exceptions import UserError


SEVERITY_RANK = {"blocker": 0, "warning": 1, "info": 2}


# W012 — base-level lifecycle state on mi.check.
#
# This is distinct from the inspector-extension `x_sbk_result`
# (pass/fail/rework/hold) added by southbrook_mrp_kitchen_workcenters.
# This `state` field tracks the DEVIATION-WAIVER lifecycle specifically
# so warranty-trace queries can filter on a single canonical column
# without depending on the inspector addon being installed.
#
#   draft                          : default — no deviation in flight
#   pending_deviation_approval     : QC submitted a waiver, eng to review
#   ship_with_deviation            : eng approved — cabinet ships
#
# The state never moves to a terminal "scrap" or "rework" — those flows
# are owned by the inspector extension's x_sbk_result. This Selection
# only models the eng-deviation path so it stays self-contained.
MI_CHECK_STATES = [
    ("draft", "Draft"),
    ("pending_deviation_approval", "Pending Deviation Approval"),
    ("ship_with_deviation", "Ship with Deviation"),
]


class SouthbrookMiCheck(models.Model):
    _name = "southbrook.mi.check"
    _description = "Southbrook Manufacturing Intelligence Check"
    # mail.thread + mail.activity.mixin (W001) give the NCR record
    # chatter, follower-routing, and activity scheduling — required for
    # the 4-tap photo-+-tag-+-route shop-floor workflow. The image
    # widget posts attachments via the chatter pipeline.
    _inherit = ["mail.thread", "mail.activity.mixin"]
    # Order by severity rank then category. Selection values sort by
    # stored string, so 'blocker'/'info'/'warning' alphabetical-DESC
    # produces warning > info > blocker — semantically wrong. We
    # store a numeric rank in `severity_rank` (compute below) and sort
    # by that, then by category for sibling-grouping.
    _order = "severity_rank asc, category, id"

    name = fields.Char(required=True)
    severity = fields.Selection(
        [
            ("info", "Info"),
            ("warning", "Warning"),
            ("blocker", "Blocker"),
        ],
        required=True,
        default="info",
        index=True,
    )
    category = fields.Selection(
        [
            ("cut", "Cut"),
            ("production", "Production"),
            ("assembly", "Assembly"),
            ("install", "Install"),
            ("cad", "CAD"),
            ("hardware", "Hardware"),
        ],
        required=True,
        default="production",
        index=True,
    )
    message = fields.Text(required=True)
    recommendation = fields.Text()
    # W001 — defect photo captured from the shop floor. fields.Image
    # caps in-DB storage at max_width/max_height (resized server-side
    # on upload) so a 4032x3024 phone capture doesn't bloat the row.
    # 1920x1920 is enough resolution for QA review while staying under
    # ~400 KB per record. The 1st photo lives here; additional photos
    # go to chatter attachments (free via mail.thread inherit above).
    image = fields.Image(
        string="Defect Photo",
        max_width=1920,
        max_height=1920,
        help="Primary defect photo. Attach additional photos via the "
             "chatter below.",
    )
    production_id = fields.Many2one(
        "mrp.production", string="Manufacturing Order", ondelete="cascade", index=True
    )
    production_package_id = fields.Many2one(
        "sb.production.package", string="Production Package", ondelete="cascade", index=True
    )
    active = fields.Boolean(default=True)
    severity_rank = fields.Integer(
        compute="_compute_severity_rank", store=True, index=True,
        help="0 = blocker, 1 = warning, 2 = info. Used to drive _order so "
             "the list view shows the most urgent rows first.",
    )

    @api.depends("severity")
    def _compute_severity_rank(self):
        for rec in self:
            rec.severity_rank = SEVERITY_RANK.get(rec.severity, 99)

    # ------------------------------------------------------------------
    # W012 — engineering deviation approval flow
    # ------------------------------------------------------------------
    state = fields.Selection(
        MI_CHECK_STATES,
        string="Deviation State",
        default="draft", required=True, tracking=True, index=True, copy=False,
        help="Lifecycle of the engineering-deviation path for this "
             "NCR. Draft = nothing in flight. pending_deviation_approval = "
             "QC submitted a waiver and eng is reviewing. "
             "ship_with_deviation = eng approved; cabinet ships with "
             "the recorded defect. See southbrook.deviation.waiver.",
    )
    deviation_waiver_id = fields.Many2one(
        "southbrook.deviation.waiver",
        string="Deviation Waiver",
        copy=False, readonly=True, index=True, tracking=True,
        help="Set by the deviation-approval wizard when QC submits a "
             "waiver against this NCR. One waiver per NCR — re-opening "
             "the same NCR for a second waiver requires the first to "
             "be rejected (state→draft).",
    )
    deviation_waiver_count = fields.Integer(
        compute="_compute_deviation_waiver_count",
        help="Smart-button counter — 0 or 1 (one waiver per NCR).",
    )

    @api.depends("deviation_waiver_id")
    def _compute_deviation_waiver_count(self):
        for rec in self:
            rec.deviation_waiver_count = 1 if rec.deviation_waiver_id else 0

    def action_approve_deviation(self):
        """Open the QC-side wizard to draft a deviation waiver.

        Per spec the inspector clicks this from the mi.check form,
        captures the defect summary + customer-ack details, and the
        wizard creates the southbrook.deviation.waiver in draft +
        flips this NCR to pending_deviation_approval on submit.
        """
        self.ensure_one()
        if self.deviation_waiver_id and \
                self.deviation_waiver_id.state in ("eng_review", "approved"):
            raise UserError(_(
                "This NCR already has an active waiver (%(name)s, "
                "state=%(state)s). Reject the existing waiver first if "
                "you need to start over.",
                name=self.deviation_waiver_id.name,
                state=self.deviation_waiver_id.state,
            ))
        Wizard = self.env["southbrook.deviation.approval.wizard"]
        wizard = Wizard.create({
            "mi_check_id": self.id,
            "defect_summary": (
                (self.message or "")
                + (("\n\nRecommendation:\n" + self.recommendation)
                   if self.recommendation else "")
            ).strip() or False,
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Request Deviation Approval"),
            "res_model": "southbrook.deviation.approval.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_open_deviation_waiver(self):
        """Smart button — open the waiver record from the NCR form."""
        self.ensure_one()
        if not self.deviation_waiver_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "southbrook.deviation.waiver",
            "res_id": self.deviation_waiver_id.id,
            "view_mode": "form",
            "target": "current",
        }
