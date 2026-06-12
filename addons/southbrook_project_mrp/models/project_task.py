# SPDX-License-Identifier: LGPL-3.0-only
from collections import Counter

from odoo import api, fields, models

# project.task.stage names (lowercased) that imply production has begun / finished.
_STARTED_STAGE_HINTS = ("cutting", "machining", "assembly", "finishing")
_DELIVERY_STAGE_HINTS = ("delivery", "install")
# mrp.production states that mean the MO has actually started.
_MO_STARTED_STATES = ("progress", "to_close", "done")


class ProjectTask(models.Model):
    _inherit = "project.task"

    # --- B1: a real person owns the job -------------------------------------
    pm_id = fields.Many2one(
        "res.users", string="Responsible PM", tracking=True,
        help="The production manager / PM accountable for this customer job. "
             "Distinct from per-task assignees; this is who the MRP manager "
             "holds responsible.")

    # --- T1.1: the job's Manufacturing Orders -------------------------------
    production_ids = fields.One2many(
        "mrp.production", "project_task_id", string="Manufacturing Orders",
        help="Every MO that makes up this customer job (base, worktop, …).")
    production_count = fields.Integer(
        string="MO Count", compute="_compute_mrp_status")

    # --- T1.2 / B3: read-only build status, sourced from mrp/stock ----------
    mo_reference = fields.Char(
        string="MO Reference(s)", compute="_compute_mrp_status")
    mo_product_summary = fields.Char(
        string="Products / SKUs", compute="_compute_mrp_status")
    mo_state_summary = fields.Char(
        string="MO Status", compute="_compute_mrp_status",
        help="Aggregate of the linked MOs' states, e.g. '4 confirmed / 2 in progress'.")
    components_available = fields.Selection(
        [("none", "No MOs"),
         ("ready", "All components available"),
         ("partial", "Partially available"),
         ("waiting", "Waiting on components")],
        string="Components", compute="_compute_mrp_status",
        help="'All available' only when EVERY linked MO is fully reserved.")
    job_at_risk = fields.Boolean(
        string="At Risk", compute="_compute_mrp_status",
        help="Job is behind or blocked (components waiting on a started MO, "
             "or an MO past its deadline).")
    job_risk_reason = fields.Char(
        string="Risk Reason", compute="_compute_mrp_status")

    # --- B2: cost roll-ups (actual + estimated), shown with currency --------
    job_industrial_cost = fields.Monetary(
        string="Job Cost (Actual, from MOs)", compute="_compute_mrp_status",
        currency_field="company_currency_id",
        help="Sum of the linked MOs' actual industrial cost (Production Costs "
             "tab). Zero until the MOs are costed.")
    job_estimated_cost = fields.Monetary(
        string="Job Cost (Estimated)", compute="_compute_mrp_status",
        currency_field="company_currency_id",
        help="Estimated cost = sum of each MO's product standard cost × qty — "
             "meaningful even before the MOs are costed.")
    company_currency_id = fields.Many2one(
        related="company_id.currency_id", string="Company Currency")

    # --- T1.2 polish: surfaced from the MO's other tabs ---------------------
    job_install_due = fields.Date(
        string="Earliest Install Due", compute="_compute_mrp_status")
    job_cad_status = fields.Char(
        string="CAD Status", compute="_compute_mrp_status")
    job_next_action = fields.Char(
        string="Next Action", compute="_compute_mrp_status")

    # --- B4: ECO visibility -------------------------------------------------
    eco_count = fields.Integer(
        string="ECO Count", compute="_compute_eco",
        help="Engineering changes touching this job's MO BoMs.")
    eco_pending_count = fields.Integer(
        string="Pending ECOs", compute="_compute_eco",
        help="ECOs not yet applied (state=open) — a spec change in flight.")

    # --- B5: stage <-> MO coherence -----------------------------------------
    stage_mo_divergence = fields.Boolean(
        string="Stage/MO Mismatch", compute="_compute_stage_coherence",
        help="The project stage and the MOs' production states disagree "
             "(e.g. stage says Finishing but no MO has started).")
    stage_mo_note = fields.Char(
        string="Stage/MO Note", compute="_compute_stage_coherence")

    # --- TASK 5: Waste / variance rollup -----------------------------------
    # All sums read from the existing x_sbk_* Kitchen Metrics fields on
    # mrp.workorder. No costing engine — just aggregation across the
    # job's WOs.
    job_expected_min = fields.Float(
        string="Expected (min)", compute="_compute_kitchen_metrics_rollup")
    job_variance_min = fields.Float(
        string="Duration Variance (min)",
        compute="_compute_kitchen_metrics_rollup",
        help="Σ x_sbk_variance_min across the job's work orders.")
    job_actual_cost = fields.Monetary(
        string="Actual Cost (from WOs)",
        compute="_compute_kitchen_metrics_rollup",
        currency_field="company_currency_id")
    job_cost_variance = fields.Monetary(
        string="Cost Variance",
        compute="_compute_kitchen_metrics_rollup",
        currency_field="company_currency_id")
    job_rework_count = fields.Integer(
        string="Rework Count",
        compute="_compute_kitchen_metrics_rollup")
    job_rework_cost = fields.Monetary(
        string="Rework Cost",
        compute="_compute_kitchen_metrics_rollup",
        currency_field="company_currency_id")
    job_downtime_min = fields.Float(
        string="Downtime (min)",
        compute="_compute_kitchen_metrics_rollup")
    job_downtime_cost = fields.Monetary(
        string="Downtime Cost",
        compute="_compute_kitchen_metrics_rollup",
        currency_field="company_currency_id")

    # --- TASK 4: Crew indicator --------------------------------------------
    crew_summary = fields.Char(
        string="Crew (from MOs + WOs)",
        compute="_compute_crew",
        help="Unique users assigned across the job's MOs (Responsible) "
             "and work orders (working_user_ids / last_working_user_id). "
             "Read-only; no auto-assignment.")
    unassigned_mo_count = fields.Integer(
        string="# Unassigned MOs", compute="_compute_crew",
        help="MOs whose user_id (Responsible) is blank.")
    unassigned_workorder_count = fields.Integer(
        string="# Unassigned WOs", compute="_compute_crew",
        help="Work orders with no working_user_ids AND no "
             "last_working_user_id — i.e. nobody has ever touched them.")
    crew_gap = fields.Boolean(
        string="Crew Gap", compute="_compute_crew",
        help="At least one MO or WO has no operator assigned.")

    # --- TASK 3: Work-center load summary ----------------------------------
    workcenter_load_summary = fields.Text(
        string="Workcenter Load",
        compute="_compute_workcenter_load",
        help="Per-work-center booked minutes across the job's work orders, "
             "compared against the work center's daily capacity proxy "
             "(resource_calendar hours/day × 60). Operators read this to "
             "spot bottlenecks without opening a Gantt.")
    workcenter_over_capacity = fields.Boolean(
        string="WC Over Capacity",
        compute="_compute_workcenter_load",
        help="True when any work center's booked minutes exceed its "
             "daily capacity proxy.")

    # --- TASK 2: Work-order rollup -----------------------------------------
    workorder_ids = fields.Many2many(
        "mrp.workorder",
        compute="_compute_workorder_rollup",
        string="Work Orders",
        help="Every work order across the job's linked MOs.")
    workorder_count = fields.Integer(
        string="# Work Orders", compute="_compute_workorder_rollup")
    unscheduled_workorder_count = fields.Integer(
        string="# Not Scheduled", compute="_compute_workorder_rollup",
        help="Work orders with no planned start date — the MRP scheduler "
             "needs to set these in the Work Orders view.")
    workorder_summary = fields.Char(
        string="Work Orders Summary", compute="_compute_workorder_rollup",
        help="One-line summary, e.g. '47 WOs / 47 not scheduled'.")

    # --- TASK 6: Material / procurement readiness ----------------------------
    material_ready_count = fields.Integer(
        string="# MOs Available", compute="_compute_material_readiness")
    material_partial_count = fields.Integer(
        string="# MOs Partially Available",
        compute="_compute_material_readiness")
    material_unavailable_count = fields.Integer(
        string="# MOs Unavailable", compute="_compute_material_readiness")
    material_at_risk = fields.Boolean(
        string="Material At Risk", compute="_compute_material_readiness",
        help="At least one linked MO is not fully component-available.")
    material_readiness_summary = fields.Text(
        string="Material Readiness", compute="_compute_material_readiness")
    procurement_order_ids = fields.Many2many(
        "purchase.order",
        compute="_compute_material_readiness",
        string="Related Procurement",
        help="Purchase orders linked to this job's MOs or component moves.")
    procurement_count = fields.Integer(
        string="# Procurement Orders", compute="_compute_material_readiness")
    procurement_summary = fields.Text(
        string="Procurement Coverage", compute="_compute_material_readiness")

    # --- TASK 7: Tooling / equipment readiness -------------------------------
    maintenance_request_ids = fields.Many2many(
        "maintenance.request",
        compute="_compute_equipment_readiness",
        string="Open Maintenance Requests",
        help="Open maintenance requests on equipment attached to this job's "
             "work centers.")
    maintenance_request_count = fields.Integer(
        string="# Open Maintenance", compute="_compute_equipment_readiness")
    equipment_blocked = fields.Boolean(
        string="Equipment Blocked", compute="_compute_equipment_readiness")
    equipment_readiness_summary = fields.Text(
        string="Equipment Readiness", compute="_compute_equipment_readiness")

    # ------------------------------------------------------------------------
    @api.depends("production_ids", "production_ids.state",
                 "production_ids.reservation_state", "production_ids.date_deadline")
    def _compute_mrp_status(self):
        today = fields.Date.context_today(self)
        for task in self:
            mos = task.production_ids
            task.production_count = len(mos)
            if not mos:
                task.mo_reference = ""
                task.mo_product_summary = ""
                task.mo_state_summary = ""
                task.components_available = "none"
                task.job_industrial_cost = 0.0
                task.job_estimated_cost = 0.0
                task.job_install_due = False
                task.job_cad_status = ""
                task.job_next_action = ""
                task.job_at_risk = False
                task.job_risk_reason = ""
                continue

            task.mo_reference = ", ".join(mos.mapped("name"))
            task.mo_product_summary = ", ".join(
                m.product_id.default_code or m.product_id.display_name
                for m in mos)

            # Readable state roll-up: "4 confirmed / 2 in progress".
            labels = dict(mos._fields["state"]._description_selection(self.env))
            states = Counter(mos.mapped("state"))
            task.mo_state_summary = " / ".join(
                "%d %s" % (n, labels.get(s, s)) for s, n in states.items())

            res = set(mos.mapped("reservation_state"))
            if res == {"assigned"}:
                task.components_available = "ready"
            elif "assigned" in res:
                task.components_available = "partial"
            else:
                task.components_available = "waiting"

            # Cost: actual (industrial) + estimated (standard cost × qty).
            # B2 fix (2026-06-11): industrial_cost reads 0.0 across all MOs
            # on Odoo 19 CE; the field carrying the "Full Direct" total the
            # operator sees on the Production Costs tab is planned_direct_cost
            # (e.g. $80.17 on WH/MO/00085, $674.42 across task #182's 6 MOs).
            # Prefer it; fall back to industrial_cost so any future costing
            # module that populates it isn't ignored.
            task.job_industrial_cost = sum(
                (getattr(m, "planned_direct_cost", 0.0)
                 or getattr(m, "industrial_cost", 0.0)
                 or 0.0)
                for m in mos)
            task.job_estimated_cost = sum(
                (m.product_id.standard_price or 0.0) * (m.product_qty or 0.0)
                for m in mos)

            # Soft pulls from CAD / Intelligence / Shop-Floor tabs.
            install = [d for d in
                       (getattr(m, "x_sbk_install_due_date", False) for m in mos)
                       if d]
            task.job_install_due = min(install) if install else False
            cad = {getattr(m, "x_cad_status", False) for m in mos} - {False, ""}
            task.job_cad_status = ", ".join(sorted(str(c) for c in cad))
            actions = [a for a in
                       (getattr(m, "x_mi_next_action", False) for m in mos) if a]
            task.job_next_action = actions[0] if actions else ""

            # At-risk: a STARTED MO that isn't fully reserved, or any MO late.
            reasons = []
            waiting = mos.filtered(
                lambda m: m.state in ("confirmed", "progress")
                and m.reservation_state != "assigned")
            if waiting:
                reasons.append("%d MO(s) waiting on components" % len(waiting))
            # FIX 1 (2026-06-11): mrp.production.date_deadline is a Datetime;
            # `today` is a Date — the bare `<` raised TypeError and broke
            # the WHOLE form (task #182 returned Odoo Server Error and
            # wouldn't open). Convert datetime → date before comparing, and
            # null-guard against MOs with no deadline set.
            late = mos.filtered(
                lambda m: m.state not in ("done", "cancel")
                and m.date_deadline
                and m.date_deadline.date() < today)
            if late:
                reasons.append("%d MO(s) past deadline" % len(late))
            task.job_risk_reason = "; ".join(reasons)
            task.job_at_risk = bool(reasons)

    @api.depends("production_ids", "production_ids.bom_id")
    def _compute_eco(self):
        has_eco = "southbrook.eco" in self.env
        Eco = self.env["southbrook.eco"] if has_eco else None
        for task in self:
            boms = task.production_ids.mapped("bom_id") if task.production_ids else None
            if not has_eco or not boms:
                task.eco_count = 0
                task.eco_pending_count = 0
                continue
            ecos = Eco.search([("bom_id", "in", boms.ids)])
            task.eco_count = len(ecos)
            task.eco_pending_count = len(ecos.filtered(lambda e: e.state == "open"))

    @api.depends("stage_id", "production_ids.state")
    def _compute_stage_coherence(self):
        for task in self:
            task.stage_mo_divergence = False
            task.stage_mo_note = ""
            mos = task.production_ids
            stage = (task.stage_id.name or "").lower()
            if not mos or not stage:
                continue
            if any(h in stage for h in _DELIVERY_STAGE_HINTS):
                if any(m.state != "done" for m in mos):
                    task.stage_mo_divergence = True
                    task.stage_mo_note = (
                        "Stage '%s' but not all MOs are done." % task.stage_id.name)
            elif any(h in stage for h in _STARTED_STAGE_HINTS):
                if not any(m.state in _MO_STARTED_STATES for m in mos):
                    task.stage_mo_divergence = True
                    task.stage_mo_note = (
                        "Stage '%s' but no MO has started production."
                        % task.stage_id.name)

    # --- TASK 2: Work-order rollup compute ---------------------------------
    @api.depends("production_ids", "production_ids.workorder_ids",
                 "production_ids.workorder_ids.date_start",
                 "production_ids.workorder_ids.state")
    def _compute_workorder_rollup(self):
        for task in self:
            wos = task.production_ids.mapped("workorder_ids")
            task.workorder_ids = wos
            task.workorder_count = len(wos)
            # "Not scheduled" = no planned/actual start date set yet. The
            # scheduler needs to set these in the Work Orders view.
            unscheduled = wos.filtered(lambda w: not w.date_start)
            task.unscheduled_workorder_count = len(unscheduled)
            if not wos:
                task.workorder_summary = ""
            elif not unscheduled:
                task.workorder_summary = "%d WOs all scheduled" % len(wos)
            else:
                task.workorder_summary = (
                    "%d WOs / %d not scheduled" % (len(wos), len(unscheduled)))

    # --- TASK 5: Kitchen Metrics rollup compute ----------------------------
    # NB: The x_sbk_* Kitchen Metrics fields are added by a downstream
    # module (southbrook_kitchen_workspace), which this bridge does NOT
    # hard-depend on. @api.depends can only reference fields that exist
    # at registry-build time; listing them here would fail to upgrade
    # this bridge alone. Depend only on the workorder relation + state
    # — the metrics get written when WOs finish, which also flips state,
    # so the rollup re-fires at the right moments without a direct dep.
    @api.depends("production_ids.workorder_ids",
                 "production_ids.workorder_ids.state",
                 "production_ids.workorder_ids.duration")
    def _compute_kitchen_metrics_rollup(self):
        for task in self:
            wos = task.production_ids.mapped("workorder_ids")
            # Defensive sums using getattr — the x_sbk_* metric fields are
            # added by southbrook_kitchen_workspace; if uninstalled, the
            # rollup degrades cleanly to 0 rather than crashing the form.
            def _sum(field):
                return sum(
                    (getattr(w, field, 0.0) or 0.0) for w in wos)
            task.job_expected_min = _sum("x_sbk_kitchen_expected_min")
            task.job_variance_min = _sum("x_sbk_variance_min")
            task.job_actual_cost = _sum("x_sbk_actual_cost")
            task.job_cost_variance = _sum("x_sbk_cost_variance")
            task.job_rework_count = int(_sum("x_sbk_rework_count"))
            task.job_rework_cost = _sum("x_sbk_rework_cost")
            task.job_downtime_min = _sum("x_sbk_downtime_min")
            task.job_downtime_cost = _sum("x_sbk_downtime_cost")

    # --- TASK 4: Crew compute ----------------------------------------------
    @api.depends("production_ids", "production_ids.user_id",
                 "production_ids.workorder_ids",
                 "production_ids.workorder_ids.working_user_ids",
                 "production_ids.workorder_ids.last_working_user_id")
    def _compute_crew(self):
        for task in self:
            mos = task.production_ids
            wos = mos.mapped("workorder_ids")
            crew = self.env["res.users"]
            crew |= mos.mapped("user_id")
            crew |= wos.mapped("working_user_ids")
            crew |= wos.mapped("last_working_user_id")
            # Filter to active internal users only (no bots / no portal).
            crew = crew.filtered(
                lambda u: u and not u.share and u.active)
            unassigned_mos = mos.filtered(lambda m: not m.user_id)
            unassigned_wos = wos.filtered(
                lambda w: not w.working_user_ids
                and not w.last_working_user_id)
            task.unassigned_mo_count = len(unassigned_mos)
            task.unassigned_workorder_count = len(unassigned_wos)
            task.crew_gap = bool(unassigned_mos or unassigned_wos)
            if not crew:
                task.crew_summary = "" if not mos else "(no crew assigned)"
            else:
                task.crew_summary = ", ".join(
                    sorted(crew.mapped("name")))

    # --- TASK 3: Work-center load compute ----------------------------------
    @api.depends("production_ids.workorder_ids.workcenter_id",
                 "production_ids.workorder_ids.duration_expected")
    def _compute_workcenter_load(self):
        for task in self:
            wos = task.production_ids.mapped("workorder_ids")
            if not wos:
                task.workcenter_load_summary = ""
                task.workcenter_over_capacity = False
                continue
            # Aggregate booked minutes per workcenter.
            booked = {}
            for wo in wos:
                wc = wo.workcenter_id
                if not wc:
                    continue
                booked.setdefault(wc, 0.0)
                booked[wc] += wo.duration_expected or 0.0
            lines = []
            any_over = False
            for wc, minutes in sorted(
                    booked.items(), key=lambda kv: -kv[1]):
                # Daily capacity proxy: resource_calendar hours/day × 60
                # multiplied by time_efficiency (stock Odoo's standard
                # capacity model — both are already on mrp.workcenter,
                # no rebuild). Fall back gracefully if absent.
                cap_min = 0.0
                cal = wc.resource_calendar_id
                hpd = getattr(cal, "hours_per_day", 0.0) or 0.0
                eff = (wc.time_efficiency or 100.0) / 100.0
                cap_min = hpd * 60.0 * eff
                if cap_min and minutes > cap_min:
                    any_over = True
                    flag = " ⚠ OVER"
                elif cap_min:
                    flag = " (%d min cap)" % int(cap_min)
                else:
                    flag = ""
                lines.append("%s: %d min booked%s" % (
                    wc.name, int(minutes), flag))
            task.workcenter_load_summary = "\n".join(lines)
            task.workcenter_over_capacity = any_over

    @api.depends("production_ids",
                 "production_ids.components_availability_state",
                 "production_ids.reservation_state",
                 "production_ids.purchase_order_count")
    def _compute_material_readiness(self):
        PurchaseLine = self.env["purchase.order.line"]
        StockMove = self.env["stock.move"]
        for task in self:
            mos = task.production_ids
            ready = partial = unavailable = 0
            lines = []
            for mo in mos.sorted("name"):
                state = (
                    getattr(mo, "components_availability_state", False)
                    or getattr(mo, "reservation_state", False)
                    or "unknown"
                )
                label = getattr(mo, "components_availability", False) or state
                if state in ("available", "assigned"):
                    ready += 1
                elif state in ("partially_available", "partial", "waiting"):
                    partial += 1
                else:
                    unavailable += 1
                lines.append("%s: %s" % (mo.name, label))

            po_lines = PurchaseLine.search([("production_id", "in", mos.ids)])
            raw_moves = mos.mapped("move_raw_ids")
            if raw_moves:
                po_lines |= raw_moves.mapped("created_purchase_line_ids")
                po_lines |= raw_moves.mapped("purchase_line_id")
                move_po_lines = PurchaseLine.search(
                    [("move_dest_ids", "in", raw_moves.ids)])
                po_lines |= move_po_lines
                related_moves = StockMove.search([
                    ("id", "in", raw_moves.mapped("move_orig_ids").ids),
                    ("purchase_line_id", "!=", False),
                ])
                po_lines |= related_moves.mapped("purchase_line_id")
            open_pos = po_lines.mapped("order_id").filtered(
                lambda po: po.state not in ("cancel", "done"))

            task.material_ready_count = ready
            task.material_partial_count = partial
            task.material_unavailable_count = unavailable
            task.material_at_risk = bool(partial or unavailable)
            task.material_readiness_summary = "\n".join(lines)
            task.procurement_order_ids = open_pos
            task.procurement_count = len(open_pos)
            if open_pos:
                task.procurement_summary = "\n".join(
                    "%s: %s" % (po.name, po.state) for po in open_pos.sorted("name"))
            else:
                task.procurement_summary = "No open linked procurement."

    @api.depends("production_ids.workorder_ids.workcenter_id")
    def _compute_equipment_readiness(self):
        Request = self.env["maintenance.request"]
        for task in self:
            workcenters = task.production_ids.mapped(
                "workorder_ids.workcenter_id")
            requests = Request
            lines = []
            for wc in workcenters.sorted("name"):
                equipment = wc.equipment_ids
                wc_requests = equipment.mapped("maintenance_ids").filtered(
                    lambda req: not req.stage_id.done)
                requests |= wc_requests
                if wc_requests:
                    lines.append("%s: BLOCKED - %d open maintenance request(s)" %
                                 (wc.name, len(wc_requests)))
                else:
                    lines.append("%s: Ready" % wc.name)
            task.maintenance_request_ids = requests
            task.maintenance_request_count = len(requests)
            task.equipment_blocked = bool(requests)
            task.equipment_readiness_summary = "\n".join(lines)

    # --- actions ------------------------------------------------------------
    def action_view_workorders(self):
        """Open the Work Orders list filtered to this job's WOs so the
        MRP scheduler can set planned start dates in the native view."""
        self.ensure_one()
        wos = self.production_ids.mapped("workorder_ids")
        return {
            "type": "ir.actions.act_window",
            "name": "Work Orders — %s" % (self.name or self.display_name),
            "res_model": "mrp.workorder",
            "domain": [("id", "in", wos.ids)],
            "view_mode": "list,form,gantt,calendar",
            "context": {"create": False},
        }

    def action_view_procurement_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Procurement — %s" % (self.name or self.display_name),
            "res_model": "purchase.order",
            "domain": [("id", "in", self.procurement_order_ids.ids)],
            "view_mode": "list,form",
            "context": {"create": False},
        }

    def action_view_maintenance_requests(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Maintenance — %s" % (self.name or self.display_name),
            "res_model": "maintenance.request",
            "domain": [("id", "in", self.maintenance_request_ids.ids)],
            "view_mode": "list,form",
            "context": {"create": False},
        }

    def action_view_productions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": "Manufacturing Orders",
            "res_model": "mrp.production",
            "domain": [("id", "in", self.production_ids.ids)],
            "view_mode": "list,form", "context": {"create": False},
        }

    def action_view_ecos(self):
        self.ensure_one()
        boms = self.production_ids.mapped("bom_id")
        return {
            "type": "ir.actions.act_window", "name": "Engineering Changes",
            "res_model": "southbrook.eco",
            "domain": [("bom_id", "in", boms.ids)],
            "view_mode": "list,form", "context": {"create": False},
        }

    def action_link_productions_from_sale(self):
        Production = self.env["mrp.production"]
        for task in self:
            order = task.x_southbrook_sale_order_id
            if not order:
                continue
            mos = Production.search([
                ("sale_line_id.order_id", "=", order.id),
                ("project_task_id", "=", False)])
            mos.write({"project_task_id": task.id})
        return True
