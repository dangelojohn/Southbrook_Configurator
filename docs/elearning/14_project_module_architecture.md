---
course: 14 — Project Module Deep Dive
chapter: 14.1
title: Project Module Architecture — What Southbrook Layers on Stock Odoo Project
duration: 30 minutes
audience: Project Manager + Developer (anyone who maintains, customises, or deeply uses /odoo/project)
prereqs: Course 2 (lessons 2.1 + 2.2 — Kitchen Projects vs Sale Orders, Release Gate), Course 12 (12.4 — Production Release Queue); basic Odoo navigation
custom_modules: southbrook_project, southbrook_project_mrp, southbrook_kitchen_workspace (cross-ref only)
---

# Project Module Architecture — What Southbrook Layers on Stock Odoo Project

## Who this lesson is for

You're a project manager who has used `/odoo/project` for a year and finally
wants to know *why* the form looks the way it does — which fields are
Southbrook custom and which are stock, which tab is doing what, and what
breaks if you uninstall a module. Or you're a developer about to touch the
Project surface and you don't want to step on cabinetry-specific compute
logic by accident. This lesson maps the *whole* customization at module
granularity so you can answer "where does this field come from" without
grepping.

Earlier lessons (2.1, 2.2, 12.4) describe what the project surface does
*for the planner*. This one describes what it *is*, structurally.

## Where this lives on the site

Sign in at **southbrookcabinetry.space/odoo** with any internal user account.

> **/odoo/project** — the stock Odoo Project app entry. Lands you on the
> project list (kanban by default).

> **/odoo/project/<id>** — opens one project's task board (kanban grouped
> by `stage_id`).

> **/odoo/project/<id>/tasks/<task_id>** — opens one task's form view.

The Southbrook customization does **not** add a top-level menu of its own
under Project — every screen reuses the stock entry. The Kitchen-Ops side
of the surface (lesson 12.4's Production Release Queue, lesson 2.x's
Kitchen Jobs board) is registered under **Kitchen Ops** by
`southbrook_premium_orchestration` and `southbrook_kitchen_workspace`, and
those views render against the *same* `project.task` records, just with
different domains + view IDs. So a task you open from
**Kitchen Ops → Kitchen Jobs** and a task you open from
**/odoo/project → some project → some task** are the same database row
viewed through different lenses.

## What your screen shows

There are two Southbrook addons doing the heavy lifting on this surface,
plus two adjacent ones you'll see fields from. Knowing which is which
saves an hour next time something breaks.

**`southbrook_project` (LGPL-3, v19.0.0.1.0)** — the "cabinetry-shop
polish" tier. Owns:

- Responsive Kanban SCSS
  (`southbrook_project/static/src/scss/kanban_responsive.scss`) — at
  ≥1280 px the 5 stage columns render side-by-side instead of horizontal-
  scrolling. Scoped to `[data-model="project.task"]` so other kanbans
  aren't touched.
- 6 seeded `project.tags` (Rush, Custom, Warranty, Repair, Kitchen,
  Vanity) — see `data/project_tags.xml`.
- Project ID 1 defaults — description, planned start/end, feature toggles
  (`allow_task_dependencies`, `allow_milestones`) flipped on. Applied via
  the `post_init_backfill_project_1` post-init hook (`hooks.py`).
- Custom fields on `project.task` (all 5 owned by this addon):
  `x_southbrook_material_species` (Selection, 12 species),
  `x_southbrook_unit_count` (Integer),
  `x_southbrook_hardware_specs` (Text),
  `x_southbrook_sale_order_id` (Many2one to `sale.order`),
  `x_southbrook_priority` (Selection: standard / rush / urgent — clearer
  than stock's single-star toggle).
- `display_name` override on `project.task` — suffixes `[SO0042]` when an
  originating SO is linked, so kanban cards surface the quote at a
  glance.
- `southbrook_top_level_task_count` field on `project.project` — sums
  only tasks with `parent_id IS NULL`, fixing the "4 Tasks" inflation
  the manual-QA report flagged.

**`southbrook_project_mrp` (LGPL-3, v19.0.1.0.0)** — the "coordination
layer above MRP." Depends on `southbrook_project` + `sale_mrp` +
`purchase_mrp` + `maintenance`. Owns:

- 80+ additional fields on `project.task` — production_ids (One2many to
  `mrp.production`), mo_state_summary, components_available, job_at_risk,
  job_risk_reason, job_industrial_cost, job_estimated_cost, plus the
  entire readiness + release + install checklist. Documented field-by-
  field in lessons 14.3 and 14.4.
- 5 production-release sign-off booleans on `project.task`:
  `southbrook_release_cad_approved`, `southbrook_release_cutlist_approved`,
  `southbrook_release_bom_verified`, `southbrook_release_crew_reserved`,
  `southbrook_release_equipment_available`. Detailed in lesson 14.4.
- The `southbrook_production_release_state` computed enum
  (ready / review / blocked / info) and its `_reason` companion.
- Production-job mission-control fields on `project.project` —
  `southbrook_job_count`, `_at_risk_job_count`, `_ready_job_count`, etc.
  Plus the matching action methods that drill into each queue.
- 4 new models — `southbrook.project.job.template`,
  `southbrook.project.job.template.line`,
  `southbrook.project.readiness.line`, and the data-quality report
  pair (`southbrook.project.data.quality.report` +
  `.line`).
- The `project_task_id` Many2one on `mrp.production` and the
  `_action_confirm` override on `sale.order` that auto-creates the task
  spine. Detailed in lesson 14.5.
- View inheritance: 5 records on `project.task` (form, list, kanban,
  search) extending stock IDs (`project.view_task_form2`,
  `project.view_task_tree2`, `project.view_task_kanban`,
  `project.view_task_search_form`); 1 on `project.project` (kanban —
  inactive by default, ref id `project_project_kanban_mission_control`,
  surfaces mission-control badges); plus full-form/list/kanban views
  for the 4 new models. Detailed in lesson 14.6.

**`southbrook_premium_orchestration` (cross-ref)** — adds 1 field +
1 cron entry point relevant here:

- `readiness_last_recomputed_at` (Datetime) on `project.task` — stamped
  each cron tick so dashboards can sort "most stale" first.
- `_cron_recompute_readiness_all` (model method on `project.task`) —
  driven by the seeded cron *Southbrook: Recompute Project Readiness*
  (xml_id `southbrook_premium_orchestration.cron_recompute_readiness_all`),
  every **30 minutes**, runs as root, calls
  `action_recompute_readiness_lines` on every open kitchen task.

**`southbrook_kitchen_workspace` (cross-ref)** — owns the `sb.kitchen.project`
model, which is *not* a flavour of `project.project` — it's an entirely
separate `mail.thread`-inheriting model representing the *design* stage
before a quote exists. Lesson 14.2 explains why both records exist and
how they relate.

## Your daily flow

(Architecture lesson — there isn't a daily flow. Instead, here's the
**read order** when you're about to touch this surface.)

**1. Identify which field you're looking at.** Open the task form,
right-click the field label, choose *View Metadata* (developer mode on).
The popup shows the model + field name. If the prefix is:

- `x_southbrook_*` → owned by `southbrook_project`. Cabinetry-shop polish.
- `southbrook_*` → owned by `southbrook_project_mrp`. Coordination layer.
- `readiness_last_recomputed_at` → owned by
  `southbrook_premium_orchestration`. Telemetry only.
- no prefix → stock Odoo `project` field. Don't extend it without a
  reason; chances are an existing custom layer already wraps it.

**2. Identify which view is rendering it.** Same right-click menu →
*Edit View: Form* (or List / Kanban / Search). The *Inherit From* shows
which xml_id the view extends; the *Inherits* list shows everything
extending it. The order matters — `southbrook_project`'s extensions land
before `southbrook_project_mrp`'s, so an xpath in the MRP layer can
reference a field the polish layer added.

**3. Identify which compute fires when.** Most Southbrook fields on
`project.task` are *computed, non-stored* — they re-evaluate on every
read of the record. The expensive ones (readiness, mission-control,
material readiness) are gated by `@api.depends` triggers; if those
triggers don't fire, the field shows stale values. Lesson 14.3
catalogues every compute and its dependencies.

**4. Check the cron.** If a value isn't refreshing, check the cron
*Southbrook: Recompute Project Readiness* under
**Settings → Technical → Scheduled Actions**. Last-Run time tells you
whether the 30-minute sweep is actually firing. The stamp it leaves on
each task is `readiness_last_recomputed_at`.

## Common mistakes + how to recover

**"I uninstalled `southbrook_project_mrp` and now /odoo/project tasks
won't open."**

You probably didn't uninstall `southbrook_premium_orchestration` first.
The orchestration layer's cron calls `action_recompute_readiness_lines`,
which is defined in `_project_mrp`; if the cron fires after the MRP
layer is gone, you get a `KeyError` 500 on every form open because the
readiness fields are still being looked up by view inheritance. Order
of uninstall: orchestration → project_mrp → project. Same order, in
reverse, for install.

**"A field is missing on the form but I know it's in the addon."**

Likely a view-inheritance order problem. Check the *Inherit* graph in
the View Metadata. If the xpath targets a field that another addon
added later, the xpath misses on cold install. The fix is to bump the
`sequence` on the offending `ir.ui.view` record (lower = earlier).

**"`southbrook_top_level_task_count` shows the right number on the
project but `open_task_count` still shows the inflated one in some
report."**

Stock `open_task_count` is intact — we don't remove it, because the
native Burndown + Tasks Analysis reports read it directly. The
Southbrook polish field is what the *kanban tile* + *form smart button*
read. Reports left untouched per the manifest's guardrail (no ACL/share/
view-removal changes).

**"I added a new custom field on `project.task` and it doesn't show in
the search filters."**

The search view inherit is in `southbrook_project/views/project_task_views.xml`
(`view_project_task_search_inherit_southbrook`). Add an xpath to the
inside-of-`//group` block to surface a Group-By filter; add another to
the position-`before` of `filter[@name='message_needaction']` for a
quick-filter chip. The pattern is copy-paste of the existing
`southbrook_rush` / `southbrook_urgent` filters.

**"Project ID 1 got renamed by someone and the post-init hook
re-applied defaults."**

The hook only fires on *install* of `southbrook_project`, not on every
upgrade — so a rename is safe. If you reinstall the addon (drop + add
back), the hook will re-fire and overwrite description + dates on
whatever record currently has ID 1. Mitigation: keep the
`post_init_backfill_project_1` hook idempotent (it already checks before
overwriting), and don't reinstall in production without dumping first.

## What the system is doing behind the scenes

`southbrook_project` is **strictly view + data + thin model
inheritance**. No new models. No cron. No security changes. It exists
because the manual-QA report against the live instance flagged five
things (no responsive kanban, no tags, no project-1 defaults, no
dependency/milestone toggles, no cabinetry fields on tasks) — each
gets one tier in the addon, each tier is one commit, each tier is
independently shippable.

`southbrook_project_mrp` is **the bridge that turns Project into the
shop-floor coordination layer.** It declares
`mrp.production.project_task_id` as the canonical link (FK on the MO
side; reverse-One2many `production_ids` on the task side). On
`sale.order._action_confirm` it auto-creates the task spine via
`_southbrook_ensure_job`, then writes `project_task_id` onto every
existing + future MO tied to that SO (`mrp.production.create` override
back-links MOs that procurement adds later). Everything downstream
(readiness, release state, mission control) is *computed* from this
graph — there is no separate "kitchen job" model in this addon. The
canonical job IS the `project.task`.

The orchestration cron lives in
`southbrook_premium_orchestration/data/ir_cron.xml` and its code body
is `model._cron_recompute_readiness_all()`. The method (in
`southbrook_premium_orchestration/models/project_task.py`) searches for
`project.task` records with `x_southbrook_sale_order_id != False` AND
`state not in (1_done, 1_canceled)`, snapshots their
`readiness_decision` + `southbrook_production_release_state`, calls the
recompute, stamps `readiness_last_recomputed_at = now`, and — if the
decision flipped — posts a chatter note. The method is defensively
written to probe three candidate recompute names
(`action_recompute_readiness_lines`, `action_recompute_readiness`,
`_recompute_readiness`) via `getattr`, so a rename in
`southbrook_project_mrp` won't break the cron silently.

## Quiz (5 questions, applied)

**1.** A field on `project.task` is showing the wrong value, but only
after the morning sale-order confirmations. Where do you look first?

> The Southbrook readiness cron is *Southbrook: Recompute Project
> Readiness*, every 30 min. If it last fired at 09:30 and the order
> confirmed at 09:31, the task's readiness/release fields stay stale
> until ~10:00. Force a refresh by opening the task and clicking the
> *Readiness* smart button — that calls `action_recompute_readiness_lines`
> directly. Don't blame the field's `@api.depends`; the compute fires
> on read, but the chatter notification you'd expect about a state flip
> only fires when the cron runs.

**2.** You want to add a new cabinetry custom field to `project.task`
that shows up in the Cabinetry Specs tab on the form. Which addon do
you put it in, and why?

> `southbrook_project` — that's where the existing 4 `x_southbrook_*`
> cabinetry custom fields live and where the "Cabinetry Specs" notebook
> page is xpath-inserted (`views/project_task_views.xml`,
> `view_project_task_form_inherit_southbrook`). Putting it in
> `_project_mrp` would land it on a different tab and force every other
> install of `southbrook_project` to depend on the MRP bridge.

**3.** A developer asks "is `sb.kitchen.project` the same model as
`project.project`?" What do you tell them?

> No. `sb.kitchen.project` lives in `southbrook_kitchen_workspace` and
> is its own `models.Model` (mail.thread-inheriting) with its own
> state machine (draft → designing → awaiting_customer → approved →
> in_production → done / cancelled). `project.project` is the stock
> Odoo container. The two link through `sb.kitchen.project.sale_order_id`
> → `sale.order` → (auto-confirm) → `project.task.x_southbrook_sale_order_id`,
> which is on a `project.project` record. Lesson 14.2 covers the
> handoff in detail.

**4.** You see a custom field `southbrook_release_bom_verified` on a
task form. Which module owns it, and how do you confirm?

> `southbrook_project_mrp`. Confirm by opening developer mode →
> right-click the field label → *View Metadata* → look at the *Module*
> field. Or grep: `grep -rn "southbrook_release_bom_verified"
> addons/southbrook_project_mrp/models/` lands you in `project_task.py`
> line ~306 (a `fields.Boolean(... tracking=True)`).

**5.** The `southbrook_top_level_task_count` button on a project's form
shows "4 Customer Jobs" but the kanban tile on /odoo/project still
shows "8 Tasks". Why?

> Two views, two different fields. The project *form* smart-button is
> wired to `southbrook_top_level_task_count` (sums only `parent_id IS
> NULL` tasks). The /odoo/project *kanban tile* is rendered by the
> stock `project.view_project_kanban` and reads `open_task_count`,
> which includes subtasks. The Southbrook override of the kanban view
> (`project_project_kanban_mission_control`, line ~856 of
> `project_task_views.xml` in `southbrook_project_mrp`) is shipped with
> `<field name="active" eval="False"/>` — it's an opt-in mission-
> control kanban, not the default. Operators who want the corrected
> count on the kanban tile must activate that view manually.

---

## What this lesson does NOT cover

- The kanban swimlanes, list filters, and calendar views in detail →
  lesson 14.6 (task views + dashboards).
- The readiness compute algorithm + cron internals → lesson 14.3.
- The 5 release sign-off booleans + state transitions → lesson 14.4.
- The `project.task` ↔ `mrp.production` linkage → lesson 14.5.
- `sb.kitchen.project` vs `project.project` — when each is used →
  lesson 14.2.
- Project-level reporting + dashboards → lesson 14.7.
- The Hermes/Fabio recommendation flow that reads from this surface
  → Course 3 + Course 7 (Floor Mgmt + Sysadmin).
