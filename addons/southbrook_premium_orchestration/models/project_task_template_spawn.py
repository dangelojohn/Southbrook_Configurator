# SPDX-License-Identifier: LGPL-3.0-only
"""project.task — Phase 3.3 generative job templates.

Activates ``southbrook.project.job.template`` so it actually spawns the
subtask lines it has been carrying as schema-only bookmarks since
southbrook_project_mrp v19.0.1.0.0. Production showed 7 templates × 15
template lines but ``template_id`` False on every project.task — the
bookmarks were never being applied.

This module closes that loop with three pieces:

1. ``x_kitchen_job_template_id`` — the m2o that points a task at one of
   the seeded templates. Writing this field is what "applies" the
   template: subtasks for every line are spawned underneath.
2. ``template_line_id`` — back-link on each spawned subtask so we can
   compute "has this template already been applied?" cheaply (and
   idempotently — a second apply must not double the subtasks).
3. ``_resolve_template_for_sale_order`` — the heuristic that maps a
   sale.order to the correct template based on its product lines / total.
   Called automatically from ``create()`` whenever the spine task is born
   without an explicit template.

Defensive throughout: every field we touch is probed via ``_fields``
containment so this module installs cleanly on a fresh CE database that
hasn't yet loaded southbrook_project_mrp (the test runner setup).
"""
from odoo import _, api, fields, models


# Template-name keywords used by the SO resolver. Order matters; the
# first match wins so place narrower keywords first. "vanity" must be
# checked before "kitchen" because a Vanity-only order should resolve
# to the Vanity template, not the catch-all Full Kitchen one.
_TEMPLATE_NAME_KEYWORDS = (
    ("vanity", "Vanity"),
    ("pantry", "Pantry"),
    ("worktop", "Worktop"),
    ("repair", "Repair"),
    ("warranty", "Warranty / Remake"),
)

# When the order total exceeds this floor we always fall through to the
# Full Kitchen template, even if no individual line matched a keyword.
# 5,000 mirrors the Phase 1 manifest threshold for "this is not a
# single-cabinet ad-hoc order".
_FULL_KITCHEN_AMOUNT_FLOOR = 5000.0


class ProjectTask(models.Model):
    _inherit = "project.task"

    # ------------------------------------------------------------------
    # Template wiring
    # ------------------------------------------------------------------
    x_kitchen_job_template_id = fields.Many2one(
        "southbrook.project.job.template",
        string="Kitchen Job Template",
        copy=False,
        help="Selecting a template here will spawn one subtask per "
             "template line under this task. Idempotent — re-selecting "
             "the same template will not double-create subtasks.",
    )
    template_line_id = fields.Many2one(
        "southbrook.project.job.template.line",
        string="Source Template Line",
        readonly=True,
        copy=False,
        index=True,
        help="Back-link populated on subtasks spawned by "
             "_apply_job_template. Used to enforce idempotency and to "
             "surface the source milestone on the kitchen ops queue.",
    )

    # ------------------------------------------------------------------
    # create() override — auto-resolve template for spine tasks
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        tasks = super().create(vals_list)
        for task in tasks:
            try:
                if task.x_kitchen_job_template_id:
                    # A template set explicitly at create time must spawn its
                    # subtasks — write() already does this, so create was
                    # asymmetric (a task imported/created WITH a template got no
                    # subtasks). _apply_job_template is idempotent.
                    task._apply_job_template()
                else:
                    task._auto_resolve_and_apply_template()
            except Exception:  # noqa: BLE001
                # Never block task creation on template resolution
                # failure — the readiness recompute cron will sweep
                # any partial state on the next tick.
                continue
        return tasks

    # ------------------------------------------------------------------
    # write() override — apply template when assigned post-creation
    # ------------------------------------------------------------------
    def write(self, vals):
        result = super().write(vals)
        if "x_kitchen_job_template_id" in vals and vals.get(
                "x_kitchen_job_template_id"):
            for task in self:
                if task.x_kitchen_job_template_id:
                    task._apply_job_template()
        return result

    # ------------------------------------------------------------------
    # Auto-resolution hook
    # ------------------------------------------------------------------
    def _auto_resolve_and_apply_template(self):
        """If this is a spine task with no template yet, resolve + apply.

        Only fires when:
            * the task carries an x_southbrook_sale_order_id linkage
              (otherwise it's not an orchestration spine), AND
            * no template has been explicitly set yet.

        Idempotent: a second call is a no-op because x_kitchen_job_template_id
        will be populated by the first."""
        self.ensure_one()
        if "x_southbrook_sale_order_id" not in self._fields:
            return False
        if self.x_kitchen_job_template_id:
            return False
        sale_order = self.x_southbrook_sale_order_id
        if not sale_order:
            return False
        template = self._resolve_template_for_sale_order(sale_order)
        if not template:
            return False
        # Bypass write() override re-entry by going through the column
        # directly — _apply_job_template is called explicitly below.
        self.x_kitchen_job_template_id = template.id
        self._apply_job_template()
        return True

    # ------------------------------------------------------------------
    # Resolution heuristic
    # ------------------------------------------------------------------
    @api.model
    def _resolve_template_for_sale_order(self, sale_order):
        """Return the southbrook.project.job.template that fits this order.

        Decision tree (first match wins):
          1. Any order line whose product name contains a template-name
             keyword (vanity, pantry, worktop, repair, warranty) →
             matching template.
          2. Order total > 5000 OR any line flagged as a full-kitchen
             configurator session → Full Kitchen template.
          3. No match → empty recordset.

        Returns the template recordset (potentially empty); never raises."""
        Template = self.env["southbrook.project.job.template"]
        if not sale_order:
            return Template.browse()

        haystack = []
        for line in sale_order.order_line:
            if line.display_type:
                continue
            if line.product_id:
                haystack.append(line.product_id.display_name or "")
                tmpl = line.product_id.product_tmpl_id
                if tmpl:
                    haystack.append(tmpl.name or "")
            if line.name:
                haystack.append(line.name)
        haystack_str = " ".join(haystack).lower()

        # Step 1 — keyword match against the seeded template names.
        for needle, template_name in _TEMPLATE_NAME_KEYWORDS:
            if needle in haystack_str:
                tpl = Template.search(
                    [("name", "=ilike", template_name)], limit=1)
                if tpl:
                    return tpl

        # Step 2 — total-amount or "full kitchen" / "kitchen" fallback.
        order_total = getattr(sale_order, "amount_total", 0.0) or 0.0
        if (
            order_total > _FULL_KITCHEN_AMOUNT_FLOOR
            or "full kitchen" in haystack_str
            or "kitchen" in haystack_str
        ):
            tpl = Template.search(
                [("name", "=ilike", "Full Kitchen")], limit=1)
            if tpl:
                return tpl

        # Step 3 — no match.
        return Template.browse()

    # ------------------------------------------------------------------
    # Application — spawn subtasks from template lines
    # ------------------------------------------------------------------
    def _apply_job_template(self):
        """Spawn one subtask per template line under this task.

        Idempotent across repeated calls — uses ``template_line_id`` on
        existing subtasks to skip lines whose subtask already exists.
        Safe to call from write(), from a server action, or from the
        Kitchen Jobs dashboard."""
        self.ensure_one()
        if not self.x_kitchen_job_template_id:
            return self.env["project.task"]

        Task = self.env["project.task"]
        template = self.x_kitchen_job_template_id
        existing_lines = self.child_ids.mapped("template_line_id")
        existing_line_ids = set(existing_lines.ids)

        spawned = Task.browse()
        for line in template.line_ids.sorted(lambda l: (l.sequence, l.id)):
            if line.id in existing_line_ids:
                # Already spawned — skip to keep this idempotent.
                continue
            vals = self._kitchen_template_line_task_vals(line)
            spawned |= Task.with_context(
                southbrook_template_spawn=True).create(vals)
        return spawned

    def _kitchen_template_line_task_vals(self, line):
        """Compose the create() payload for a single template-line subtask.

        Carries forward project_id + stage_id from the parent so the
        spawned subtasks land in the same column / project view. The
        sale.order linkage is intentionally NOT copied — the parent owns
        that relationship; subtasks are pure execution checkpoints."""
        self.ensure_one()
        Task = self.env["project.task"]
        vals = {
            "name": line.name,
            "sequence": line.sequence,
            "parent_id": self.id,
            "project_id": self.project_id.id,
            "template_line_id": line.id,
        }
        # Carry forward the description from the template line where
        # the task model supports it.
        if "description" in Task._fields and line.description:
            vals["description"] = line.description
        # Inherit the parent's stage so the subtask shows in the
        # expected Kanban column rather than the project default.
        if self.stage_id and "stage_id" in Task._fields:
            vals["stage_id"] = self.stage_id.id
        return vals
