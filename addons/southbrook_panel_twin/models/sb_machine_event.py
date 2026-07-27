# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields, models


class SbMachineEvent(models.Model):
    _name = "sb.machine.event"
    _description = "Machine Event Stream"
    _order = "timestamp desc, id desc"

    panel_id = fields.Many2one("sb.panel", string="Panel", ondelete="set null",
                               index=True)
    workorder_id = fields.Many2one("mrp.workorder", string="Work Order")
    workcenter_id = fields.Many2one("mrp.workcenter", string="Work Center")
    machine_code = fields.Char(string="Machine")
    event_type = fields.Selection(
        [("scan", "Scan"), ("cycle_start", "Cycle Start"),
         ("cycle_end", "Cycle End"), ("tool_change", "Tool Change"),
         ("alarm", "Alarm")],
        string="Event Type", required=True,
    )
    timestamp = fields.Datetime(string="Timestamp")
    payload = fields.Text(string="Raw Payload")
