# SPDX-License-Identifier: LGPL-3.0-only
from odoo import api, fields, models


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    southbrook_not_scheduled = fields.Boolean(
        string="Not Scheduled",
        compute="_compute_southbrook_not_scheduled",
        help="True when this work order has no planned/actual start date.")
    southbrook_can_start_today = fields.Boolean(
        string="Can Start Today",
        compute="_compute_southbrook_can_start_today",
        search="_search_southbrook_can_start_today",
        help="True when the WO is scheduled for today/past, components are "
             "available, crew is assigned, equipment is clear, and upstream "
             "work is not blocking it.")
    southbrook_start_blocker = fields.Char(
        string="Start Blocker",
        compute="_compute_southbrook_can_start_today")

    @api.depends("date_start")
    def _compute_southbrook_not_scheduled(self):
        for workorder in self:
            workorder.southbrook_not_scheduled = not bool(workorder.date_start)

    @api.depends(
        "date_start",
        "state",
        "production_id.reservation_state",
        "production_id.components_availability_state",
        "production_id.user_id",
        "working_user_ids",
        "last_working_user_id",
        "workcenter_id.equipment_ids.maintenance_ids.stage_id.done",
    )
    def _compute_southbrook_can_start_today(self):
        today = fields.Date.context_today(self)
        for workorder in self:
            blocker = workorder._southbrook_start_blocker(today)
            workorder.southbrook_start_blocker = blocker
            workorder.southbrook_can_start_today = not bool(blocker)

    def _southbrook_start_blocker(self, today):
        self.ensure_one()
        production = self.production_id
        if self.state in ("done", "cancel"):
            return "Work order is already %s." % self.state
        if self.state == "waiting":
            return "Upstream operation is not complete."
        if not self.date_start:
            return "Work order is not scheduled."
        if self.date_start.date() > today:
            return "Work order is scheduled for a future date."

        component_state = (
            getattr(production, "components_availability_state", False)
            or getattr(production, "reservation_state", False)
            or ""
        )
        if component_state not in ("available", "assigned"):
            return "Components are not available."

        crew = (
            production.user_id
            or self.working_user_ids
            or self.last_working_user_id
        )
        if not crew:
            return "Crew is not assigned."

        requests = self.workcenter_id.equipment_ids.mapped(
            "maintenance_ids").filtered(lambda request: not request.stage_id.done)
        if requests:
            return "Equipment has open maintenance."

        return ""

    def _search_southbrook_can_start_today(self, operator, value):
        if operator not in ("=", "!="):
            return [("id", "=", 0)]
        desired = bool(value)
        if value in (False, 0, "0", "false", "False"):
            desired = False
        if operator == "!=":
            desired = not desired
        workorders = self.with_context(active_test=False).search([]).filtered(
            lambda workorder: bool(workorder.southbrook_can_start_today) == desired)
        return [("id", "in", workorders.ids)]
