# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields, models


class SbPanelCycle(models.Model):
    _name = "sb.panel.cycle"
    _description = "Panel Operation Cycle"
    _order = "timestamp, id"

    panel_id = fields.Many2one("sb.panel", string="Panel", required=True,
                               ondelete="cascade", index=True)
    workorder_id = fields.Many2one("mrp.workorder", string="Work Order")
    workcenter_id = fields.Many2one("mrp.workcenter", string="Work Center")
    operation = fields.Char(string="Operation")
    program = fields.Char(string="Program")
    tool_ref = fields.Char(string="Tool")
    operator_id = fields.Many2one("res.users", string="Operator")
    duration_s = fields.Float(string="Cycle Time (s)")
    qc_result = fields.Selection(
        [("pass", "Pass"), ("fail", "Fail"), ("na", "N/A")],
        string="QC", default="na", required=True,
    )
    timestamp = fields.Datetime(string="Timestamp")
