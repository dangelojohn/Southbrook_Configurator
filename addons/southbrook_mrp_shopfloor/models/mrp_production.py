# SPDX-License-Identifier: LGPL-3.0-only
"""Manufacturing-order scheduling state and the completion gate."""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    date_planned_start_wo = fields.Datetime(
        "Shop Start", compute="_compute_wo_bounds", store=True)
    date_planned_finished_wo = fields.Datetime(
        "Shop Finish", compute="_compute_wo_bounds", store=True)
    date_actual_start_wo = fields.Datetime(
        "Actual Start", compute="_compute_wo_bounds", store=True)
    date_actual_finished_wo = fields.Datetime(
        "Actual Finish", compute="_compute_wo_bounds", store=True)
    is_scheduled = fields.Boolean(
        "Operations Scheduled", compute="_compute_is_scheduled", store=True)

    @api.depends("workorder_ids.date_planned_start_wo",
                 "workorder_ids.date_planned_finished_wo",
                 "workorder_ids.date_actual_start_wo",
                 "workorder_ids.date_actual_finished_wo")
    def _compute_wo_bounds(self):
        for mo in self:
            wos = mo.workorder_ids
            starts = wos.filtered("date_planned_start_wo").mapped(
                "date_planned_start_wo")
            finishes = wos.filtered("date_planned_finished_wo").mapped(
                "date_planned_finished_wo")
            a_starts = wos.filtered("date_actual_start_wo").mapped(
                "date_actual_start_wo")
            a_ends = wos.filtered("date_actual_finished_wo").mapped(
                "date_actual_finished_wo")
            mo.date_planned_start_wo = min(starts) if starts else False
            mo.date_planned_finished_wo = max(finishes) if finishes else False
            mo.date_actual_start_wo = min(a_starts) if a_starts else False
            mo.date_actual_finished_wo = max(a_ends) if a_ends else False

    @api.depends("workorder_ids.date_planned_start_wo",
                 "workorder_ids.state")
    def _compute_is_scheduled(self):
        """An order is scheduled when every operation is planned or closed.

        Uses all() over every work order rather than any() over the open
        ones. That matters: once production finishes, the work orders are
        done and carry no forward plan, and an any()-style test would flip
        is_scheduled back to False — making the completion gate below
        unreachable for the very orders that have already satisfied it.
        """
        for mo in self:
            wos = mo.workorder_ids
            if not wos:
                mo.is_scheduled = True
                continue
            mo.is_scheduled = all(
                wo.date_planned_start_wo or wo.state in ("done", "cancel")
                for wo in wos)

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------
    def schedule_workorders(self):
        """Chain this order's work orders forward from its planned start.

        Each operation starts when its predecessor finishes, walked across
        the workcenter calendar. Sequencing follows ``sfc_sequence``.
        """
        for mo in self:
            warehouse = mo.picking_type_id.warehouse_id
            if not warehouse:
                warehouse = self.env["stock.warehouse"].search(
                    [("company_id", "=", mo.company_id.id)], limit=1)
            floating = self.env["mrp.floating.times"]._get_for_warehouse(
                warehouse)
            cursor = mo.date_start or fields.Datetime.now()
            if floating and floating.mrp_ftbp_time:
                cursor = fields.Datetime.add(
                    cursor, hours=floating.mrp_ftbp_time)
            pending = mo.workorder_ids.filtered(
                lambda w: w.state not in ("done", "cancel")
            ).sorted(lambda w: (w.sfc_sequence, w.id))
            for wo in pending:
                finish = wo._sfc_plan_from(cursor)
                wo.write({
                    "date_planned_start_wo": cursor,
                    "date_planned_finished_wo": finish,
                })
                cursor = finish
            pending._rebuild_capacity_load()
        return True

    def button_plan(self):
        res = super().button_plan()
        self.schedule_workorders()
        return res

    def button_unplan(self):
        res = super().button_unplan()
        wos = self.workorder_ids
        wos.write({
            "date_planned_start_wo": False,
            "date_planned_finished_wo": False,
        })
        wos._rebuild_capacity_load()
        return res

    # ------------------------------------------------------------------
    # Completion gate
    # ------------------------------------------------------------------
    def button_mark_done(self):
        """Refuse to close an order whose operations were never planned.

        Behaviourally compatible with the module this replaces, which is the
        point — swapping it out must not quietly relax shop discipline. The
        message is more actionable than the original, which said only that
        work orders were not scheduled and left the reader to discover that
        the fix is Plan (or a scheduling run).

        Note for whoever hits this: this gate is why no manufacturing order
        in this database reached 'done' before 2026-07-26. It is doing its
        job, not malfunctioning.
        """
        for mo in self:
            if not mo.workorder_ids:
                continue
            if mo.is_scheduled:
                continue
            unplanned = mo.workorder_ids.filtered(
                lambda w: not w.date_planned_start_wo
                and w.state not in ("done", "cancel"))
            raise UserError(_(
                "%(mo)s cannot be closed: %(count)s of its operations have "
                "never been scheduled (%(names)s).\n\n"
                "Use Plan on this order, or run a scheduling run, then close "
                "it.",
                mo=mo.name, count=len(unplanned),
                names=", ".join(unplanned.mapped("name")[:5]) or "-"))
        return super().button_mark_done()
