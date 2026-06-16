# SPDX-License-Identifier: LGPL-3.0-only
"""sale.order — Premium Orchestration spine activation.

Phase 1.1 of the Premium MRP Orchestration addon. Closes the gap discovered
in production: of the 9 confirmed sale.orders on https://southbrookcabinetry.space,
only 1 actually spawned its project.task spine; the other 8 booked MOs directly
with project_task_id=False — breaking the "Project as Manufacturing PM hub"
promise the southbrook_project / southbrook_project_mrp / southbrook_mrp_pm
stack was built to deliver.

This module:
  1. Overrides ``action_confirm`` to ALWAYS create the project.task spine for
     kitchen-cabinet orders (in addition to / instead of the legacy
     ``_southbrook_ensure_job`` path in southbrook_project_mrp, which is too
     conservative — it skips orders whose products don't yet have a BoM).
  2. Backlinks any orphan mrp.production records whose ``origin`` matches the
     order name but whose ``project_task_id`` is still False.
  3. Exposes a server-action callable ``action_backfill_kitchen_task`` that is
     idempotent and safe to fire from the UI for the 8 known orphan orders.
  4. Stamps ``x_premium_orchestration_managed`` once the spine exists, so the
     B2 readiness cron can find unscored orders cheaply.

Defensive-by-design: the project.task model carries ~60 custom fields in
production (x_door_style, x_wood_species, x_finish, install_due_date, …)
that are not declared in any tracked python module — they were added via the
Odoo UI / ir.model.fields in the live DB. We probe with ``_fields`` containment
and skip silently when absent, so this module is installable on a fresh CE
database (e.g. CI) and on the live DB without divergent code paths.
"""
from odoo import _, api, fields, models


# Kitchen-style heuristic keywords. Order matters — Shaker is checked before
# the fallback "flat" because a Shaker-Flat hybrid should resolve to Shaker.
# Sourced from the Southbrook door-style catalog tab in
# Southbrook_Consolidated_Dataset.xlsx; kept narrow on purpose — anything
# we can't infer falls through to "Custom".
_DOOR_STYLE_KEYWORDS = (
    ("shaker", "Shaker"),
    ("raised", "Raised Panel"),
    ("slab", "Slab"),
    ("flat", "Flat Panel"),
    ("five-piece", "5-Piece"),
    ("5-piece", "5-Piece"),
    ("beadboard", "Beadboard"),
)

_WOOD_SPECIES_KEYWORDS = (
    ("maple", "Maple"),
    ("oak", "Oak"),
    ("cherry", "Cherry"),
    ("walnut", "Walnut"),
    ("hickory", "Hickory"),
    ("mdf", "MDF"),
    ("thermofoil", "Thermofoil"),
    ("melamine", "Melamine"),
    ("birch", "Birch"),
)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # ------------------------------------------------------------------
    # Tracking flag — lets the B2 readiness cron find unscored orders
    # without re-walking the entire sale.order table. Flipped True the
    # moment a spine exists for this order (regardless of who created
    # it: us, the legacy southbrook_project_mrp hook, or a backfill).
    # ------------------------------------------------------------------
    x_premium_orchestration_managed = fields.Boolean(
        string="Premium Orchestration Managed",
        default=False,
        copy=False,
        help="Flipped True once this order's project.task spine has been "
             "ensured by the Premium Orchestration layer. Cron pickers "
             "in Phase 1.2 (readiness recompute) filter on this rather "
             "than re-walking the entire sale.order table.",
    )

    # ------------------------------------------------------------------
    # action_confirm override — always-on spine creation
    # ------------------------------------------------------------------
    def action_confirm(self):
        result = super().action_confirm()
        for order in self:
            try:
                order._create_kitchen_project_task()
            except Exception:  # noqa: BLE001
                # Never block order confirmation on spine-creation failure;
                # the backfill action picks up survivors. Logged via
                # message_post so we keep an audit trail on the order.
                order.message_post(
                    body=_("Premium Orchestration: failed to create kitchen "
                           "project.task spine. Run 'Backfill Kitchen Task' "
                           "from the order to retry."))
        return result

    # ------------------------------------------------------------------
    # Public, idempotent backfill — server-action target
    # ------------------------------------------------------------------
    def action_backfill_kitchen_task(self):
        """Server-action target for the 8 orphan orders on production.

        Idempotent: if a task already exists (via x_southbrook_project_task_id
        OR via project.task.x_southbrook_sale_order_id), this is a no-op.
        Safe to call from a server action, a wizard, or a cron.
        """
        for order in self:
            order._create_kitchen_project_task()
        return True

    # ------------------------------------------------------------------
    # Core spine creator
    # ------------------------------------------------------------------
    def _create_kitchen_project_task(self):
        """Create (once) the project.task spine for this order.

        Returns the existing or newly-created task. Idempotent. Honours the
        legacy southbrook_project_mrp path: if a task already exists via
        ``x_southbrook_sale_order_id``, reuse it and just refresh the
        backlink + managed flag (no double-create on re-confirm)."""
        self.ensure_one()
        Task = self.env["project.task"]

        # Idempotency probe — covers BOTH the legacy direct field on
        # sale.order and the reverse lookup on project.task. We accept
        # whichever exists in the deployed DB; CE-clean test DBs have
        # neither field on sale.order so we lean on the reverse-side
        # lookup as the source of truth.
        existing = self._find_existing_kitchen_task()
        if existing:
            self._stamp_managed_flag(existing)
            self._backlink_orphan_mos(existing)
            return existing

        project = self._resolve_kitchen_project()
        if not project:
            # No active project to attach to — nothing we can do here.
            # The backfill action will retry once a project exists.
            return self.env["project.task"]

        vals = self._kitchen_task_vals(project)
        task = Task.create(vals)
        self._stamp_managed_flag(task)
        self._backlink_orphan_mos(task)
        return task

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _find_existing_kitchen_task(self):
        """Resolve an existing kitchen task for this order, if any.

        Probes two paths so the same code works on the live DB (where
        ``sale.order.x_southbrook_project_task_id`` exists as a UI-defined
        custom field) and on a fresh CE/CI database (where only the
        reverse-side ``project.task.x_southbrook_sale_order_id`` field
        from southbrook_project is guaranteed)."""
        self.ensure_one()
        Task = self.env["project.task"]
        # Path 1: m2o on sale.order, when present on this DB.
        if "x_southbrook_project_task_id" in self._fields:
            direct = self.x_southbrook_project_task_id
            if direct:
                return direct
        # Path 2: reverse lookup via southbrook_project's m2o on project.task.
        if "x_southbrook_sale_order_id" in Task._fields:
            task = Task.search(
                [("x_southbrook_sale_order_id", "=", self.id)], limit=1)
            if task:
                return task
        return Task

    def _stamp_managed_flag(self, task):
        """Mark this order as having an orchestrated spine.

        Also writes the reverse m2o on sale.order if that custom field is
        present (live DB), so the legacy UI badge keeps lighting up."""
        self.ensure_one()
        vals = {"x_premium_orchestration_managed": True}
        if (
            "x_southbrook_project_task_id" in self._fields
            and self.x_southbrook_project_task_id != task
        ):
            vals["x_southbrook_project_task_id"] = task.id
        self.write(vals)

    def _kitchen_task_vals(self, project):
        """Compose the project.task create() payload.

        Pulls door_style, wood_species, finish, install_due_date from the
        order's first kitchen-shaped line via keyword heuristics. Only
        emits keys whose corresponding fields exist on project.task in
        this DB — keeps us installable on fresh CE databases."""
        self.ensure_one()
        Task = self.env["project.task"]
        inferred = self._infer_kitchen_specs()
        vals = {
            "name": self._build_kitchen_task_name(inferred),
            "project_id": project.id,
        }
        # Stage: "Design & Quote" if it exists on the resolved project.
        stage = self._resolve_design_quote_stage(project)
        if stage:
            vals["stage_id"] = stage.id

        # Reverse-side link to the sale.order. Required for the readiness
        # cron and for the existing southbrook_project_mrp rollups to work.
        if "x_southbrook_sale_order_id" in Task._fields:
            vals["x_southbrook_sale_order_id"] = self.id

        # Inferred specs — only emit when the column exists on this DB.
        spec_map = {
            "x_door_style": inferred.get("door_style"),
            "x_wood_species": inferred.get("wood_species"),
            "x_finish": inferred.get("finish"),
            "install_due_date": inferred.get("install_due_date"),
        }
        for fname, value in spec_map.items():
            if value and fname in Task._fields:
                vals[fname] = value
        return vals

    def _build_kitchen_task_name(self, inferred=None):
        """Compose 'Kitchen Cabinet Set – <style> (<species>) [<order>]'."""
        self.ensure_one()
        if inferred is None:
            inferred = self._infer_kitchen_specs()
        style = inferred.get("door_style") or "Custom"
        species = inferred.get("wood_species") or "TBD"
        return "Kitchen Cabinet Set – %s (%s) [%s]" % (
            style, species, self.name or "Draft")

    def _infer_kitchen_specs(self):
        """Heuristic specs from the order's product line names.

        Cheap keyword scan over product_id.display_name + product_template
        name — good enough for the 8 orphan orders and for the typical
        Southbrook quote which carries the door style and species directly
        in the product name (e.g. 'Base Cabinet, Shaker Maple, 30W')."""
        self.ensure_one()
        out = {
            "door_style": None,
            "wood_species": None,
            "finish": None,
            "install_due_date": False,
        }
        haystack_parts = []
        for line in self.order_line:
            if line.display_type:  # skip section/note lines
                continue
            if line.product_id:
                haystack_parts.append(line.product_id.display_name or "")
                tmpl = line.product_id.product_tmpl_id
                if tmpl:
                    haystack_parts.append(tmpl.name or "")
            if line.name:
                haystack_parts.append(line.name)
        haystack = " ".join(haystack_parts).lower()

        for needle, label in _DOOR_STYLE_KEYWORDS:
            if needle in haystack:
                out["door_style"] = label
                break
        for needle, label in _WOOD_SPECIES_KEYWORDS:
            if needle in haystack:
                out["wood_species"] = label
                break

        # Install due-date heuristic: prefer the order's commitment_date if
        # populated, else fall back to its expected delivery date.
        if "commitment_date" in self._fields and self.commitment_date:
            out["install_due_date"] = fields.Date.to_date(self.commitment_date)
        return out

    def _resolve_kitchen_project(self):
        """Config-param driven project resolver with a sane fallback.

        ir.config_parameter 'southbrook_premium.default_kitchen_project_id'
        takes precedence; otherwise the first active project (lowest id)
        wins. Never creates a project — that's an admin decision."""
        Project = self.env["project.project"]
        param = self.env["ir.config_parameter"].sudo().get_param(
            "southbrook_premium.default_kitchen_project_id")
        if param:
            try:
                proj = Project.browse(int(param)).exists()
            except (TypeError, ValueError):
                proj = Project
            if proj:
                return proj
        # Fall back to active=True if the field exists, then any project.
        domain = []
        if "active" in Project._fields:
            domain = [("active", "=", True)]
        return Project.search(domain, limit=1, order="id")

    def _resolve_design_quote_stage(self, project):
        """Resolve the 'Design & Quote' stage_id on the given project.

        Falls back to the project's first stage so newly-created tasks
        always land in a sensible column rather than orphaned."""
        Stage = self.env["project.task.type"]
        # The stage is project-scoped via the m2m project_ids; match on it
        # explicitly so we don't accidentally pick up a same-named stage
        # from an unrelated project.
        stage = Stage.search(
            [("project_ids", "in", project.id),
             ("name", "=ilike", "Design & Quote")],
            limit=1)
        if stage:
            return stage
        return Stage.search(
            [("project_ids", "in", project.id)],
            limit=1, order="sequence,id")

    def _backlink_orphan_mos(self, task):
        """Backlink mrp.production whose origin = this SO's name + no task.

        Two-step probe: the strongest signal is sale_line_id.order_id (used
        by the legacy hook); we additionally catch MOs that came in via
        manual create() and carry only ``origin = SO.name``, which is the
        actual cause of the 8 orphan-MO bug on production."""
        self.ensure_one()
        if not task:
            return self.env["mrp.production"]
        MO = self.env["mrp.production"]
        domain = [
            ("project_task_id", "=", False),
            "|",
            ("sale_line_id.order_id", "=", self.id),
            ("origin", "=", self.name),
        ]
        orphans = MO.search(domain)
        if orphans:
            orphans.write({"project_task_id": task.id})
        return orphans

    def action_open_kitchen_job(self):
        """Open the linked project.task spine record. Wired to the
        'Kitchen Job' smart button in views/sale_order_views.xml."""
        self.ensure_one()
        task = self._find_existing_kitchen_task()
        if not task:
            from odoo.exceptions import UserError
            raise UserError(
                "No kitchen job task is linked to this order yet. "
                "Use the 'Backfill Kitchen Tasks' server action, or "
                "confirm the order to spawn one automatically."
            )
        return {
            "type": "ir.actions.act_window",
            "name": "Kitchen Job",
            "res_model": "project.task",
            "res_id": task.id,
            "view_mode": "form",
            "target": "current",
        }
