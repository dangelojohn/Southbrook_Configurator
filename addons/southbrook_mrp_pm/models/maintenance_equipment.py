# SPDX-License-Identifier: LGPL-3.0-only
"""maintenance.equipment extension — Southbrook condition flag.

M13 (Manufacturing PM JTBD 2026-06-01): maintenance.equipment
already exposes MTBF / MTTR / estimated_next_failure (out of the
box), but it has no real-time 'Condition' field. The PM gap
analysis called this out — the PM can't see at a glance which
machines are at risk vs healthy, and the Floor Manager has no
quick toggle to flag a developing issue.

This commit adds:

    southbrook_condition              Selection: good / fair /
                                       watch / critical / offline
    southbrook_condition_note         freeform notes
    southbrook_condition_last_updated readonly stamp
    southbrook_condition_updated_by   readonly user reference

Tracking is enabled on condition + note so the maintenance.equipment
chatter records every change in the audit trail.

Phase 2 polish (out of scope for this commit):

  - M14: equipment → impacted MO chain. Lookup view that takes a
         condition='critical' or 'offline' equipment and surfaces
         every MO whose routing uses the equipment's work center
         + the affected sale.orders + delivery dates.
  - Floor Manager portal route exposing the condition pill +
         a single-tap upgrade/downgrade widget so the operator
         can flag without leaving the station (M16/M17).
  - Automation rule: condition transitions to 'critical' or
         'offline' fire a chatter post on every in-flight MO
         that depends on the equipment's work center.
"""
from odoo import _, api, fields, models


# In-flight MO states for the M14 impacted-MO lookup. Drops 'done'
# (already shipped) and 'cancel' (terminated). 'draft' and 'confirmed'
# both surface so the PM sees both queued + currently-running orders.
IN_FLIGHT_STATES = ("draft", "confirmed", "progress", "to_close")


CONDITION_SELECTION = [
    ("good", "Good"),
    ("fair", "Fair"),
    ("watch", "Watch"),
    ("critical", "Critical"),
    ("offline", "Offline"),
]


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    southbrook_condition = fields.Selection(
        CONDITION_SELECTION,
        string="Condition",
        default="good",
        tracking=True,
        help=(
            "Floor-Manager-set health snapshot of this equipment.\n"
            " good     — running normally\n"
            " fair     — running, watching\n"
            " watch    — issues observed, schedule attention\n"
            " critical — degraded; affecting throughput\n"
            " offline  — out of service"
        ),
    )
    southbrook_condition_note = fields.Text(
        string="Condition Notes",
        tracking=True,
        help=(
            "Brief context for the current condition state — e.g. "
            "'edge bander hot-melt blocked, scheduled service Friday'."
        ),
    )
    southbrook_condition_last_updated = fields.Datetime(
        string="Condition Last Updated",
        readonly=True,
        copy=False,
        help="Set automatically when southbrook_condition changes.",
    )
    southbrook_condition_updated_by = fields.Many2one(
        "res.users",
        string="Condition Updated By",
        readonly=True,
        copy=False,
        help="User who set the current condition.",
    )

    def write(self, vals):
        if "southbrook_condition" in vals:
            vals["southbrook_condition_last_updated"] = fields.Datetime.now()
            vals["southbrook_condition_updated_by"] = self.env.user.id
        return super().write(vals)

    # ==================================================================
    # M14 — Equipment → impacted MO chain
    # ==================================================================
    #
    # Pre-fix: if the CNC Boring machine goes down, the PM has no way
    # to see which orders are about to slip. The cascade
    #     equipment → workcenter → routing.workcenter → bom → MO
    # exists in the data but no view stitches it.
    #
    # This commit adds:
    #   workcenter_id  Many2one link from equipment to its station
    #   southbrook_impacted_production_ids  computed Many2many of
    #     in-flight MOs whose work orders use this equipment's
    #     workcenter
    #   southbrook_impacted_production_count  integer for the
    #     stat-button badge
    #   action_view_impacted_productions  smart-button handler that
    #     opens the filtered MO list

    workcenter_id = fields.Many2one(
        "mrp.workcenter",
        string="Work Center",
        help=(
            "The shop-floor station this equipment sits at. "
            "Used to derive impacted manufacturing orders via the "
            "equipment → workcenter → routing → MO chain."
        ),
    )

    southbrook_impacted_production_ids = fields.Many2many(
        "mrp.production",
        string="Impacted MOs",
        compute="_compute_southbrook_impacted_productions",
        help=(
            "In-flight manufacturing orders whose routing operations "
            "use this equipment's work center. Computed live — no "
            "stored cache."
        ),
    )

    southbrook_impacted_production_count = fields.Integer(
        string="Impacted MO Count",
        compute="_compute_southbrook_impacted_productions",
    )

    @api.depends("workcenter_id")
    def _compute_southbrook_impacted_productions(self):
        MO = self.env["mrp.production"].sudo()
        for eq in self:
            if not eq.workcenter_id:
                eq.southbrook_impacted_production_ids = MO
                eq.southbrook_impacted_production_count = 0
                continue
            prods = MO.search([
                ("state", "in", list(IN_FLIGHT_STATES)),
                ("workorder_ids.workcenter_id", "=", eq.workcenter_id.id),
            ])
            eq.southbrook_impacted_production_ids = prods
            eq.southbrook_impacted_production_count = len(prods)

    def action_view_impacted_productions(self):
        """Open the mrp.production list filtered to in-flight MOs that
        use this equipment's workcenter. Same lookup the smart-button
        badge counts, but as a real list view the PM can drill into.
        """
        self.ensure_one()
        ids = self.southbrook_impacted_production_ids.ids
        return {
            "type": "ir.actions.act_window",
            "name": _("MOs Impacted by %s") % self.name,
            "res_model": "mrp.production",
            "view_mode": "list,form,kanban",
            "domain": [("id", "in", ids)],
            "context": {
                "search_default_group_by_state": 1,
            },
        }
