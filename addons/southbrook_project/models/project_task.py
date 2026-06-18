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

    # ─── P7 — Single source of truth for material/hardware/qty ─────
    # The audit found that material species, hardware specs, and unit
    # count were keyed in the configurator AND on project.task AND on
    # the BoM — triple entry that drifts silently.
    #
    # We keep the three columns plain (so existing views, reports, and
    # third-party Studio fields keep working) and add an explicit
    # override boolean. The sync method below is called from the
    # action_confirm path in southbrook_premium_orchestration after
    # the task is created — it pulls the canonical values from the
    # originating sale.order and writes them to the task, unless
    # x_southbrook_specs_override is True (rare manual cases).
    x_southbrook_specs_override = fields.Boolean(
        string="Specs Manually Overridden",
        default=False,
        help="When set, the P7 auto-sync skips this task even when the "
             "originating sale.order's configuration changes. Use only "
             "for genuine deviations from the quote; the default "
             "behaviour is to keep the three Cabinetry Specs fields in "
             "lockstep with the configured order line.",
    )

    def _southbrook_p7_sync_from_so(self):
        """Pull material species / unit count / hardware specs from
        the originating sale.order. No-op when no SO is linked or
        when the manual-override flag is set.

        Idempotent + write-only-on-change so chatter spam is minimal.
        """
        for task in self:
            if task.x_southbrook_specs_override:
                continue
            so = task.x_southbrook_sale_order_id
            if not so:
                continue
            vals = {}

            species = task._southbrook_p7_resolve_material_species(so)
            if species and species != task.x_southbrook_material_species:
                vals["x_southbrook_material_species"] = species

            unit_count = task._southbrook_p7_resolve_unit_count(so)
            if unit_count is not None and unit_count != task.x_southbrook_unit_count:
                vals["x_southbrook_unit_count"] = unit_count

            hw_specs = task._southbrook_p7_resolve_hardware_specs(so)
            if hw_specs and hw_specs != task.x_southbrook_hardware_specs:
                vals["x_southbrook_hardware_specs"] = hw_specs

            if vals:
                task.write(vals)

    def _southbrook_p7_resolve_material_species(self, so):
        """Most-common Wood Species / Box Material value across the
        order's configured kitchen lines, mapped to the Selection's
        keys."""
        from collections import Counter
        votes = Counter()
        for line in so.order_line:
            if line.display_type or not line.product_id:
                continue
            for ptav in line.product_id.product_template_attribute_value_ids:
                attr_name = (ptav.attribute_id.name or "").lower()
                if "wood species" in attr_name or "box material" in attr_name:
                    votes[(ptav.product_attribute_value_id.name or "").lower()] += 1
        if not votes:
            return None
        winner_name = votes.most_common(1)[0][0]
        # Map free-text vote -> Selection key.
        haystack = winner_name
        for key, _label in MATERIAL_SPECIES_SELECTION:
            # Key tokens to look for in the haystack.
            token = key.split("_", 1)[1] if "_" in key else key
            token = token.replace("_", " ")
            if token in haystack:
                return key
        if "maple" in haystack:
            return "maple"
        if "oak" in haystack:
            return "oak_red"
        if "thermofoil" in haystack:
            return "thermofoil_white"
        if "melamine" in haystack:
            return "melamine_white"
        return None

    def _southbrook_p7_resolve_unit_count(self, so):
        """Sum of product_uom_qty across configurable cabinet lines."""
        total = 0
        for line in so.order_line:
            if line.display_type:
                continue
            if not line.product_id:
                continue
            # Count any product with attribute lines as a configurable
            # cabinet; accessories / services with no attributes are
            # not "units" in the cabinetry sense.
            attrs = line.product_id.product_template_attribute_value_ids
            if not attrs:
                continue
            try:
                total += int(round(line.product_uom_qty or 0))
            except (TypeError, ValueError):
                pass
        return total

    def _southbrook_p7_resolve_hardware_specs(self, so):
        """One-line summary of resolved hardware packages bound to this
        order's manufacturing orders. Falls back to None when no
        packages have been emitted yet (e.g. P1 flag off)."""
        if "sb.production.package" not in self.env:
            # southbrook_kitchen_mrp not installed — return None so the
            # legacy Hardware Specs free-text behaviour stands. (Avoids
            # making this addon hard-depend on kitchen_mrp.)
            return None
        Package = self.env["sb.production.package"]
        packages = Package.search([
            ("sale_order_line_id", "in", so.order_line.ids),
        ])
        if not packages:
            return None
        bits = []
        for pkg in packages:
            hp = pkg.hardware_package_id
            if not hp:
                continue
            for ln in hp.line_ids:
                sku = ln.product_id.x_marathon_sku or ln.product_id.default_code
                if sku:
                    bits.append(f"{sku}x{ln.qty}")
        if not bits:
            return None
        # Dedup while preserving order.
        seen = set()
        ordered = []
        for b in bits:
            if b not in seen:
                seen.add(b)
                ordered.append(b)
        return ", ".join(ordered)

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
