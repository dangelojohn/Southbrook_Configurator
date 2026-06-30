# SPDX-License-Identifier: LGPL-3.0-only
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class OsRevision(models.Model):
    _name = "southbrook.os.revision"
    _description = "Southbrook OS — Revision Order (OSRO)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(default=lambda self: _("New"), tracking=True)
    target_slug = fields.Char(required=True, tracking=True)
    change_summary = fields.Char(required=True, tracking=True)
    proposed_body = fields.Text(required=True)
    state = fields.Selection(
        [("draft", "Draft"),
         ("review", "Under Review"),
         ("approved", "Approved"),
         ("applied", "Applied"),
         ("rejected", "Rejected")],
        default="draft", required=True, tracking=True,
    )
    reviewer_ids = fields.Many2many("res.users")
    applied_at = fields.Datetime(readonly=True)
    applied_by = fields.Many2one("res.users", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "southbrook.os.revision") or _("OSRO/draft")
        return super().create(vals_list)

    def action_submit_for_review(self):
        for rev in self:
            if rev.state != "draft":
                raise UserError(_("Only draft OSROs can be submitted for review."))
            rev.state = "review"

    def action_approve(self):
        for rev in self:
            if rev.state != "review":
                raise UserError(_("Only OSROs under review can be approved."))
            rev.state = "approved"

    def action_reject(self):
        for rev in self:
            if rev.state not in ("review", "draft"):
                raise UserError(_("Cannot reject from %s.") % rev.state)
            rev.state = "rejected"

    def action_apply(self):
        for rev in self:
            if rev.state != "approved":
                raise UserError(
                    _("Only approved OSROs can be applied. Current state: %s.")
                    % rev.state)
            section = self.env["southbrook.os.section"].search(
                [("slug", "=", rev.target_slug)], limit=1)
            if not section:
                raise UserError(
                    _("No OS section with slug '%s' exists to apply this OSRO against.")
                    % rev.target_slug)
            section.bump_version(body=rev.proposed_body)
            rev.write({
                "state": "applied",
                "applied_at": fields.Datetime.now(),
                "applied_by": self.env.user.id,
            })
