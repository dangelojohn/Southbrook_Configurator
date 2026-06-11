# SPDX-License-Identifier: LGPL-3.0-only
"""project.task extension — Southbrook cabinetry-specific fields.

Adds the four fields the manual-QA report asked for, plus a child-task
count that does NOT inflate the parent's task count (the QA report
flagged a job with three production steps showing as "4 Tasks" because
subtasks counted as full tasks).

Priority widget: stock Odoo's priority is a single-star toggle that
logs "Medium priority". We extend the selection so an operator picks
between Standard / Rush / Urgent, which logs clear labels into the
chatter.
"""
from odoo import _, api, fields, models


# Material/species the cabinet shop uses most often. Keep this as a
# Selection (controlled vocabulary) rather than free text so the
# Tasks Analysis report can group by it.
MATERIAL_SPECIES_SELECTION = [
    ("maple", "Hard Maple"),
    ("oak_red", "Red Oak"),
    ("oak_white", "White Oak"),
    ("cherry", "Cherry"),
    ("walnut", "Walnut"),
    ("hickory", "Hickory"),
    ("mdf", "MDF Painted"),
    ("melamine_white", "White Melamine"),
    ("melamine_woodgrain", "Woodgrain Melamine"),
    ("thermofoil_white", "White Thermofoil"),
    ("plywood_birch", "Birch Plywood"),
    ("other", "Other"),
]


# Standalone priority field — clearer than stock's single-star toggle.
# Kept separate from project.task.priority so stock integrations
# (search filters, automations) keep working against the original
# field. Form view in views/project_task_views.xml surfaces this
# field next to the stock star widget.
SOUTHBROOK_PRIORITY_SELECTION = [
    ("standard", "Standard"),
    ("rush", "Rush"),
    ("urgent", "Urgent"),
]


class ProjectTask(models.Model):
    _inherit = "project.task"

    # ─── Cabinetry specs ────────────────────────────────────────────
    x_southbrook_material_species = fields.Selection(
        MATERIAL_SPECIES_SELECTION,
        string="Material / Species",
        index=True,
        help="Primary species or substrate for this cabinet job. Used "
             "by the Tasks Analysis report to group queue by material.",
    )
    x_southbrook_unit_count = fields.Integer(
        string="Unit Count",
        default=0,
        help="Number of cabinet units this task represents. 0 means "
             "not yet quoted; the planner reports surface incomplete "
             "tasks via this field.",
    )
    x_southbrook_hardware_specs = fields.Text(
        string="Hardware Specs",
        help="Hinge / handle / drawer-slide selections for this job. "
             "Free-text until the hardware catalog picker lands; "
             "operators paste from the existing quote here.",
    )
    x_southbrook_sale_order_id = fields.Many2one(
        "sale.order",
        string="Originating Quote / Sales Order",
        ondelete="set null",
        index=True,
        help="Link back to the sale.order that originated this job. "
             "Click-through opens the order in a new tab.",
    )

    # ─── Clear rush/urgent indicator (Tier 4.4) ─────────────────────
    x_southbrook_priority = fields.Selection(
        SOUTHBROOK_PRIORITY_SELECTION,
        string="Southbrook Priority",
        default="standard",
        index=True,
        tracking=True,
        help="Standard = normal queue. Rush = move ahead of standard. "
             "Urgent = drop everything else. Logs explicit labels to "
             "the chatter (the stock single-star priority logged only "
             "'Medium priority', which the QA pass flagged as unclear).",
    )

    # ─── Subtask-aware count (Tier 4.2) ─────────────────────────────
    # Stock Odoo's open_task_count on project.project sums every
    # task INCLUDING subtasks, which inflated the project overview
    # ("4 Tasks" for one job with three production sub-steps). The
    # fix is on the parent record's compute, not on project.task —
    # see the project_project_inherit class below.

    @api.depends("name", "x_southbrook_sale_order_id")
    def _compute_display_name(self):
        # Inherit stock compute, then suffix the SO ref when present
        # so the kanban card surfaces the quote at a glance.
        super()._compute_display_name()
        for rec in self:
            if rec.x_southbrook_sale_order_id and rec.display_name:
                rec.display_name = "%s [%s]" % (
                    rec.display_name,
                    rec.x_southbrook_sale_order_id.name,
                )


class ProjectProject(models.Model):
    _inherit = "project.project"

    southbrook_top_level_task_count = fields.Integer(
        compute="_compute_southbrook_top_level_task_count",
        string="# Top-Level Tasks",
        help="Count of tasks WITHOUT a parent — i.e. the actual "
             "production jobs, not the sub-steps inside them. The "
             "project overview should read against this rather than "
             "open_task_count to avoid double-counting production "
             "steps as full tasks.",
    )

    def _compute_southbrook_top_level_task_count(self):
        # Open = anything not done or cancelled. Listing closed states
        # rather than open ones keeps this resilient to upstream
        # additions of new in-progress sub-states.
        closed_states = ("1_done", "1_canceled")
        Task = self.env["project.task"]
        for rec in self:
            rec.southbrook_top_level_task_count = Task.search_count([
                ("project_id", "=", rec.id),
                ("parent_id", "=", False),
                ("state", "not in", closed_states),
            ])
