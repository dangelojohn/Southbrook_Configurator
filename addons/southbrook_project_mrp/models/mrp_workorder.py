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
        # Odoo 19 removed mrp.workcenter.equipment_ids (the reverse
        # of maintenance.equipment.workcenter_id). The maintenance-
        # request check inside _southbrook_start_blocker now searches
        # maintenance.request directly; depending on workcenter_id
        # alone re-fires when the WC link changes. Maintenance state
        # changes won't auto-invalidate this unstored computed field,
        # but every read re-runs the compute so the next view refresh
        # picks them up.
        "workcenter_id",
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

        # Odoo 19: mrp.workcenter.equipment_ids no longer exists. Walk
        # the forward path maintenance.equipment.workcenter_id instead,
        # filtered to open requests (stage_id.done == False). Single
        # search rather than the old equipment-iteration + filter.
        MaintenanceRequest = self.env["maintenance.request"].sudo()
        if self.workcenter_id and MaintenanceRequest._fields.get("equipment_id"):
            open_count = MaintenanceRequest.search_count([
                ("equipment_id.workcenter_id", "=", self.workcenter_id.id),
                ("stage_id.done", "=", False),
            ])
            if open_count:
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
