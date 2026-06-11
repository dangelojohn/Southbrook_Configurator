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
            task.job_industrial_cost = sum(
                (getattr(m, "industrial_cost", 0.0) or 0.0) for m in mos)
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
            late = mos.filtered(
                lambda m: m.state not in ("done", "cancel")
                and getattr(m, "date_deadline", False)
                and m.date_deadline < today)
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

    # --- actions ------------------------------------------------------------
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
