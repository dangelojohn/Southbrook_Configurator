# SPDX-License-Identifier: LGPL-3.0-only
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


SEVERITY_TO_PRIORITY = {
    "low": "0",
    "medium": "1",
    "high": "2",
    "critical": "3",
}


class SouthbrookCmmsBreakdownAlert(models.Model):
    _name = "southbrook.cmms.breakdown_alert"
    _description = "CMMS Breakdown Alert"
    _inherit = ["mail.thread"]
    _order = "reported_at desc, id desc"

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        default=lambda self: self.env["ir.sequence"].next_by_code(
            "southbrook.cmms.breakdown") or "BRK/NEW",
        tracking=True,
    )
    equipment_id = fields.Many2one(
        "maintenance.equipment",
        string="Equipment",
        required=True,
        ondelete="cascade",
        tracking=True,
    )
    workcenter_id = fields.Many2one(
        "mrp.workcenter",
        string="Work Center",
        tracking=True,
        help="Optional work center association. If the equipment record carries "
             "a workcenter_id, set it manually or via business logic.",
    )
    severity = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        default="medium",
        required=True,
        tracking=True,
    )
    reported_at = fields.Datetime(
        string="Reported At",
        default=fields.Datetime.now,
        tracking=True,
    )
    reported_by = fields.Many2one(
        "res.users",
        string="Reported By",
        default=lambda self: self.env.user,
        tracking=True,
    )
    description = fields.Text(string="Description")
    affected_production_ids = fields.Many2many(
        "mrp.production",
        relation="southbrook_cmms_brk_mo_rel",
        column1="alert_id",
        column2="production_id",
        compute="_compute_affected_mos",
        string="Affected MOs",
    )
    state = fields.Selection(
        [
            ("open", "Open"),
            ("dispatched", "Dispatched"),
            ("fixed", "Fixed"),
        ],
        default="open",
        required=True,
        tracking=True,
    )
    maintenance_request_id = fields.Many2one(
        "maintenance.request",
        string="Maintenance Request",
        readonly=True,
    )

    @api.depends("workcenter_id")
    def _compute_affected_mos(self):
        Production = self.env["mrp.production"]
        in_progress_states = ("confirmed", "progress", "to_close")
        for rec in self:
            if not rec.workcenter_id:
                rec.affected_production_ids = [(5, 0, 0)]
                continue
            mos = Production.search([
                ("state", "in", list(in_progress_states)),
                ("bom_id.operation_ids.workcenter_id", "=", rec.workcenter_id.id),
            ])
            rec.affected_production_ids = [(6, 0, mos.ids)]

    def action_dispatch(self):
        Request = self.env["maintenance.request"]
        for rec in self:
            if rec.maintenance_request_id:
                rec.state = "dispatched"
                continue
            priority = SEVERITY_TO_PRIORITY.get(rec.severity, "1")
            req = Request.create({
                "name": "Breakdown: %s" % (rec.name,),
                "equipment_id": rec.equipment_id.id,
                "description": rec.description or rec.name,
                "priority": priority,
                "maintenance_type": "corrective",
            })
            rec.maintenance_request_id = req.id
            rec.state = "dispatched"
            rec.message_post(body="Dispatched maintenance request %s" % req.name)
        return True

    def action_block_affected_mos(self):
        Activity = self.env["mail.activity"]
        try:
            warning_act_type = self.env.ref("mail.mail_activity_data_warning")
        except ValueError:
            warning_act_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        mo_model = self.env["ir.model"]._get("mrp.production")
        # NOTE: this is an ADVISORY flag — it posts a warning + activity on each
        # affected MO but does NOT hard-stop the MO/workorder (imposing a real
        # production block is a policy decision, see REVIEW_REPORT). The user-
        # facing copy says "flagged", not "blocked", so it doesn't overstate.
        for rec in self:
            for mo in rec.affected_production_ids:
                mo.message_post(
                    body="Flagged by breakdown <b>%s</b> on equipment <b>%s</b> "
                         "— do not run production on this equipment until the "
                         "breakdown is cleared." % (
                             rec.name, rec.equipment_id.display_name))
                vals = {
                    "res_model_id": mo_model.id,
                    "res_id": mo.id,
                    "summary": "Breakdown blocking MO (%s)" % rec.name,
                    "user_id": (mo.user_id.id or self.env.user.id),
                    "note": rec.description or rec.name,
                }
                if warning_act_type:
                    vals["activity_type_id"] = warning_act_type.id
                Activity.sudo().create(vals)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Breakdown alert dispatched",
                "message": "Flagged %d MO(s) on the affected equipment." % sum(
                    len(r.affected_production_ids) for r in self),
                "type": "warning",
                "sticky": False,
            },
        }
