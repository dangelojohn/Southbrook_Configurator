# SPDX-License-Identifier: LGPL-3.0-only
from collections import Counter

from odoo import api, fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    # --- T1.1: the job's Manufacturing Orders ---------------------------------
    production_ids = fields.One2many(
        "mrp.production", "project_task_id",
        string="Manufacturing Orders",
        help="Every MO that makes up this customer job (base, worktop, …).",
    )
    production_count = fields.Integer(
        string="MO Count", compute="_compute_mrp_status")

    # --- T1.2: read-only build status, sourced from mrp/stock -----------------
    mo_reference = fields.Char(
        string="MO Reference(s)", compute="_compute_mrp_status")
    mo_product_summary = fields.Char(
        string="Products / SKUs", compute="_compute_mrp_status")
    mo_state_summary = fields.Char(
        string="MO Status", compute="_compute_mrp_status",
        help="Roll-up of the linked MOs' states.")
    components_available = fields.Selection(
        [("none", "No MOs"),
         ("ready", "All components available"),
         ("partial", "Partially available"),
         ("waiting", "Waiting on components")],
        string="Components", compute="_compute_mrp_status",
        help="Can we build this? Derived from each MO's reservation state.")
    job_industrial_cost = fields.Monetary(
        string="Job Cost (from MOs)", compute="_compute_mrp_status",
        currency_field="company_currency_id",
        help="Roll-up of the linked MOs' industrial cost (pulled from the "
             "costing module when installed; never re-entered here).")
    company_currency_id = fields.Many2one(
        related="company_id.currency_id", string="Company Currency")
    # Surfaced read-only from the MO's other custom tabs (CAD / Intelligence /
    # Shop-Floor) when those modules are installed — soft-referenced, never a
    # hard dependency, so the bridge cold-installs standalone.
    job_install_due = fields.Date(
        string="Earliest Install Due", compute="_compute_mrp_status",
        help="Soonest install date across the job's MOs (install/site info "
             "lives on the MO; surfaced here so the PM sees it on the job).")
    job_cad_status = fields.Char(
        string="CAD Status", compute="_compute_mrp_status",
        help="CAD-artifact status across the job's MOs (CAD Artifacts tab).")
    job_next_action = fields.Char(
        string="Next Action", compute="_compute_mrp_status",
        help="Next manufacturing-intelligence action on a job MO, if any.")

    @api.depends("production_ids",
                 "production_ids.state",
                 "production_ids.reservation_state")
    def _compute_mrp_status(self):
        for task in self:
            mos = task.production_ids
            task.production_count = len(mos)
            if not mos:
                task.mo_reference = ""
                task.mo_product_summary = ""
                task.mo_state_summary = ""
                task.components_available = "none"
                task.job_industrial_cost = 0.0
                task.job_install_due = False
                task.job_cad_status = ""
                task.job_next_action = ""
                continue

            task.mo_reference = ", ".join(mos.mapped("name"))
            task.mo_product_summary = ", ".join(
                m.product_id.default_code or m.product_id.display_name
                for m in mos)
            states = Counter(mos.mapped("state"))
            task.mo_state_summary = ", ".join(
                "%d %s" % (count, state) for state, count in states.items())

            res = set(mos.mapped("reservation_state"))
            if res == {"assigned"}:
                task.components_available = "ready"
            elif "assigned" in res:
                task.components_available = "partial"
            else:
                task.components_available = "waiting"

            # Cost roll-up — pull from the costing module's field if present.
            task.job_industrial_cost = sum(
                (getattr(m, "industrial_cost", 0.0) or 0.0) for m in mos)

            # Soft pulls from the MO's CAD / Intelligence / Shop-Floor tabs.
            install = [d for d in
                       (getattr(m, "x_sbk_install_due_date", False) for m in mos)
                       if d]
            task.job_install_due = min(install) if install else False
            cad = {getattr(m, "x_cad_status", False) for m in mos} - {False, ""}
            task.job_cad_status = ", ".join(sorted(str(c) for c in cad))
            actions = [a for a in
                       (getattr(m, "x_mi_next_action", False) for m in mos) if a]
            task.job_next_action = actions[0] if actions else ""

    # --- actions --------------------------------------------------------------
    def action_view_productions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Manufacturing Orders",
            "res_model": "mrp.production",
            "domain": [("id", "in", self.production_ids.ids)],
            "view_mode": "list,form",
            "context": {"create": False},
        }

    def action_link_productions_from_sale(self):
        """Attach MOs that trace to this job's sale order(s) but aren't linked
        yet — the manual/reliable counterpart to the auto-flow."""
        Production = self.env["mrp.production"]
        for task in self:
            order = task.x_southbrook_sale_order_id
            if not order:
                continue
            mos = Production.search([
                ("sale_line_id.order_id", "=", order.id),
                ("project_task_id", "=", False),
            ])
            mos.write({"project_task_id": task.id})
        return True
