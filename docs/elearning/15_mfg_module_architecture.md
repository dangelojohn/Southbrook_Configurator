---
course: 15 — Manufacturing Module Deep Dive
chapter: 15.1
title: Manufacturing Module Architecture — What Southbrook Layers on Native MRP
duration: 35 minutes
audience: Production Manager + developer reading the platform for the first time
prereqs: Course 1 lesson 1.1 (workcenter orientation), Course 2 lesson 2.3 (bottleneck scheduling), Course 3 lesson 3.1 (MI dashboards), Course 7 lesson 7.1 (orchestration), comfortable with native Odoo MRP vocabulary
custom_modules: southbrook_mrp_pm, southbrook_mrp_kitchen_workcenters, southbrook_mrp_kitchen_tools, southbrook_kitchen_mrp, southbrook_manufacturing_intelligence
---

# Manufacturing Module Architecture — What Southbrook Layers on Native MRP

## Who this lesson is for

You're a production manager or developer who just got handed
`southbrookcabinetry.space/odoo/manufacturing` and is trying to figure
out **what's Southbrook vs what's stock Odoo**. Course 1, 2 and 3
covered the daily flows; this lesson is the map underneath them — the
five addons that touch the Manufacturing surface, what each one owns,
and how a click on the MO form fans out across the database. If you've
ever had to debug "why does this field show on the MO form?" or "which
addon do I patch to add a new MI check?", start here.

## Where this lives on the site

> **/odoo/manufacturing** — Odoo native MRP module, but everything
> Southbrook layers on top is wired through five addons under
> `addons/` in `~/southbrook-v19cr/`.

The Manufacturing app menu structure once everything's installed:

> **Manufacturing → Operations → Manufacturing Orders**
> **Manufacturing → Operations → Work Orders**
> **Manufacturing → Configuration → Work Centers**
> **Manufacturing → Configuration → Bills of Materials**

Southbrook adds two top-level menu roots alongside these:

> **Southbrook PM** (`menu_southbrook_pm_root`, sequence 70) — the
> production manager's surface (Dashboard, Family Throughput, Capacity,
> Ready Queue, In Production, Late, Floor Load, Equipment)
> **Southbrook PM → MI Checks** (grafted under PM root by the
> Manufacturing Intelligence addon)

Plus two grafted branches under the native Manufacturing menu tree:

> **Manufacturing → Configuration → Southbrook Kitchen** (Materials,
> Finishes, Operation Templates)
> **Manufacturing → Operations → Southbrook Kitchen → Work Center
> Downtime**

There is **no separate "Kitchen Ops" root menu** despite that name
appearing in older brief docs — the Southbrook-custom surface lives
under two roots: **Southbrook PM** (its own root) and **Manufacturing
→ Southbrook Kitchen** (grafted into native MRP).

## What your screen shows — the five-addon stack

| Layer | Addon | What it owns |
|---|---|---|
| Foundation | `southbrook_mrp_pm` | 8 + 10 seeded workcenters, equipment, cabinet families, PM menu root, KPI dashboards, capacity pivot/graph, Floor Manager portal |
| Vocabulary | `southbrook_mrp_kitchen_workcenters` | Station type taxonomy, material/finish catalogs, 15 operation templates, downtime model, MO project linkage |
| Tool gating | `southbrook_mrp_kitchen_tools` | Tool assets/cribs/kits, workcenter+operation tool requirements, workorder readiness state machine, tool consumption log |
| Package model | `southbrook_kitchen_mrp` | `sb.cutlist`, `sb.hardware.package`, `sb.production.package` (the per-MO artefact triple) |
| Intelligence | `southbrook_manufacturing_intelligence` | `southbrook.mi.engine`, `southbrook.mi.check` rows, the MI badge + counts + next_action on MO and on production package |

The dependency graph is bottom-up: PM is the foundation. Kitchen
Workcenters depends on PM + MI + Kitchen MRP + Workspace. Kitchen
Tools depends on PM + Kitchen MRP. MI depends on PM + Kitchen MRP +
Estimating + Dealer Portal + FreeCAD Bridge.

## What native MRP gives you (and what stays untouched)

Native Odoo 19 CE provides:

- `mrp.production` — the MO. State machine `draft → confirmed → progress → to_close → done` (plus `cancel`). Southbrook does **not** override this state machine.
- `mrp.workorder` — the WO. State `pending → waiting → ready → progress → done`. Southbrook hooks `button_start` only.
- `mrp.bom` + `mrp.bom.line` — BoM definition. Southbrook adds compute fields + cut-spec methods on top; native lines stay.
- `mrp.routing.workcenter` — operation steps in a BoM. Southbrook adds `x_sbk_operation_template_id` and `x_sbk_driver_override`.
- `mrp.workcenter` — station. Southbrook adds **35+ extension fields** across four addons (see lesson 15.5).

You can use stock MRP forms, lists, and reports unchanged. The
Southbrook layer is additive — every custom field is prefixed
(`x_sbk_*`, `southbrook_*`, `x_mi_*`) so you can grep your way back
to the owner addon.

## The model topology

```
mrp.production  ─── x_sbk_kitchen_project_id ──→ sb.kitchen.project
       │
       ├── x_mi_check_ids (one2many) ──────────→ southbrook.mi.check
       ├── southbrook_tool_consumption_ids ────→ southbrook.workorder.tool.consumption
       │
       └── workorder_ids (native, one2many) ───→ mrp.workorder
                                                      │
                                                      ├── workcenter_id ──→ mrp.workcenter
                                                      │                           │
                                                      │                           └── x_sbk_*, southbrook_pm_*, x_mi_*, southbrook_tool_*
                                                      │
                                                      ├── operation_id ──→ mrp.routing.workcenter
                                                      │                           │
                                                      │                           └── x_sbk_operation_template_id ──→ southbrook.kitchen.operation.template
                                                      │
                                                      └── southbrook_tool_readiness_state, x_sbk_kitchen_expected_min, ...

sb.production.package ── mo_id (M2O, required, unique-per-MO) ──→ mrp.production
       │
       ├── cutlist_id ─────────→ sb.cutlist
       ├── hardware_package_id ─→ sb.hardware.package
       └── x_mi_status, x_mi_blocker_count, x_mi_next_action, ...
```

The **MO is the join hub**. Every Southbrook artefact eventually
back-references `mrp.production.id`. The `sb.production.package` is
the per-MO bundle that carries the cutlist + hardware pack + MI
verdict; lesson 15.7 unpacks that triple.

## The view inheritance graph

| View | Inherits | Owner addon | Adds |
|---|---|---|---|
| `view_mrp_production_form_sbk_kitchen` | `mrp.mrp_production_form_view` | kitchen_workcenters | Kitchen notebook page (project, room, cabinet code, install due, priority, complexity, totals) |
| `view_mrp_production_form_mi` | `mrp.mrp_production_form_view` | manufacturing_intelligence | Intelligence notebook page (recompute button, badge, checks list, blocker/warning counts, yield, waste) |
| `view_mrp_production_tree_sbk_kitchen` | `mrp.mrp_production_tree_view` | kitchen_workcenters | Columns: install_due, project, cabinet_code, priority_level |
| `view_mrp_workorder_form_inherit_kt` | `mrp.mrp_production_workorder_form_view_inherit` | kitchen_tools | Tool readiness header button + statusbar |
| `view_southbrook_pm_kanban_mi` | `southbrook_mrp_pm.view_southbrook_pm_kanban` | manufacturing_intelligence | MI chips on workcenter dashboard kanban |
| `view_sb_production_package_form_mi` | `southbrook_kitchen_mrp.view_sb_production_package_form` | manufacturing_intelligence | MI status badge + check list on production package form |

Notice no view rewrites the MO list-view colour rules or the kanban
swimlanes. Lesson 15.6 explains why — the MO Kanban swimlanes story
is mostly **not present**, and what fills the gap.

## The menu surface

Two roots own everything Southbrook-custom on the manufacturing surface:

**Southbrook PM** (root `menu_southbrook_pm_root`, sequence 70):

| Sub-menu | Action | Model |
|---|---|---|
| Dashboard | `action_pm_dashboard` | `mrp.workcenter` (kanban, active=True) |
| Family Throughput | `action_pm_family_throughput` | `southbrook.cabinet.family` |
| Capacity | `action_pm_capacity` | `mrp.workorder` (pivot+graph) |
| Ready Queue | `action_pm_ready_queue` | `mrp.production` (state in confirmed/progress) |
| In Production | `action_pm_in_production` | `mrp.production` (state=progress) |
| Late Orders | `action_pm_late` | `mrp.production` (date_deadline < now) |
| Floor Load | `action_pm_floor_load` | `mrp.workcenter` |
| Equipment | `action_pm_equipment` | `maintenance.equipment` |
| **MI Checks** | `action_southbrook_mi_checks` | `southbrook.mi.check` |
| **MI Packages** | `action_southbrook_mi_packages` | `sb.production.package` |

**Manufacturing → Configuration → Southbrook Kitchen** (grafted):

| Sub-menu | Action | Model |
|---|---|---|
| Kitchen Materials | `action_sbk_material` | `southbrook.kitchen.material` |
| Kitchen Finishes | `action_sbk_finish` | `southbrook.kitchen.finish` |
| Kitchen Operation Templates | `action_sbk_operation_template` | `southbrook.kitchen.operation.template` |

**Manufacturing → Operations → Southbrook Kitchen → Work Center
Downtime** (grafted): `action_sbk_downtime` on
`southbrook.kitchen.workcenter.downtime`.

## Security groups added

| Group | Owner addon | Inherits | Purpose |
|---|---|---|---|
| `southbrook_mrp_pm.group_floor_manager` | mrp_pm | `base.group_portal` | Tablet portal `/my/southbrook/floor` access |
| `southbrook_mrp_pm.group_southbrook_production_approver` | mrp_pm | `base.group_user` | Sale → MO approve/reject gate |
| `southbrook_mrp_kitchen_tools.group_tool_operator` | tools | `mrp.group_mrp_user` | Read tool requirements, log usage |
| `southbrook_mrp_kitchen_tools.group_tool_crib_manager` | tools | `group_tool_operator + stock.group_stock_user` | CRUD on assets, kits, cribs |
| `southbrook_mrp_kitchen_tools.group_maintenance_technician` | tools | (none documented) | CRUD on maintenance requests + usage |

There are **no Manufacturing Intelligence-specific groups**; MI rights
follow native MRP user/manager rights and the engine runs as
`base.user_root`.

## Your daily flow (as the production manager)

**1. Morning (10 min):**

- Open **Southbrook PM → Dashboard**. Glance the 8 + 10 workcenter
  tiles for `southbrook_pm_late_count > 0` and
  `southbrook_pm_equipment_alerts > 0`. The MI inherit also chips any
  tile whose `x_mi_workcenter_warning_count > 0` (the chip CSS is
  `o_sb_mi_chip_warning`).
- Open **Southbrook PM → Ready Queue**. Group-by state shows
  `confirmed` first; this is the planner's responsibility but you
  watch for backlog.
- Open **Southbrook PM → MI Checks**, default-grouped by category
  (cut / production / assembly / install), default-filtered to
  `blockers`. Anything here is what the MI engine flagged last night
  or last hour as needing your attention.

**2. Per-MO dive (the loop):**

- Open the MO. Two notebook pages were added by the Southbrook stack:
  **Kitchen** (project linkage, complexity, totals) and
  **Intelligence** (MI badge, checks list, next action).
- The MI badge colour comes from `x_mi_status`: `ok` (green),
  `review` (amber), `blocked` (red). Click the badge → opens the MI
  checks for this MO.
- Hit **Recompute MI** if you've manually corrected data (e.g.
  changed an attribute on a configured product) and want the engine
  to re-run the gates immediately. The action dispatches to
  `southbrook.mi.engine._recompute_production(self)`.

**3. End of day (5 min):**

- Open **Southbrook PM → Capacity**. The pivot shows
  `duration_expected` per workcenter per day. Anything above 480 min
  on a single bottleneck is tomorrow's slip risk.
- Update equipment conditions if anything broke. The condition flips
  immediately into the workcenter tile's
  `southbrook_pm_equipment_alerts` count next page-load.

## Common mistakes + how to recover

**"I added a custom field to mrp.production but it's not showing on
the form."**

There are TWO inherited form views (`view_mrp_production_form_sbk_kitchen`
and `view_mrp_production_form_mi`). Your new field needs an inheriting
view that loads AFTER both. Check `__manifest__.py` `data` order: the
inheriting addon must depend on both `southbrook_mrp_kitchen_workcenters`
and `southbrook_manufacturing_intelligence` so the load order is
deterministic.

**"The MI badge is stuck on `ok` but I know there's a blocker."**

The engine is idempotent but it's NOT triggered on every save. It's
triggered (a) by the explicit "Recompute" button on the MO,
(b) overnight by `southbrook_premium_orchestration` crons (lesson 2.4),
(c) by the `action_recompute_manufacturing_intelligence` action on
the production package. If the badge is stale, hit the button
manually; it writes `x_mi_status`, `x_mi_blocker_count`,
`x_mi_warning_count`, `x_mi_next_action` synchronously.

**"My production manager can't see the MI menu items."**

MI menus graft onto `menu_southbrook_pm_root`. If the user lacks
`mrp.group_mrp_user`, the root menu doesn't show. Add MRP User
access at minimum.

## What the system is doing behind the scenes

The Manufacturing surface is **five addons cooperating through
ir.model inheritance**, not one monolithic module. When you click
"Recompute MI" on an MO:

1. Native `mrp.production.write({...})` is NOT called — the action
   is a manual button.
2. The button calls
   `self.env['southbrook.mi.engine']._recompute_production(self)`.
3. The engine deletes existing `southbrook.mi.check` rows for this
   MO, replays each check definition (defined in
   `southbrook_manufacturing_intelligence/models/mi_check.py`), and
   inserts fresh rows.
4. Each check writes severity (`blocker`/`warning`/`info`) and a
   `next_action` string. The engine then aggregates counts onto the
   MO: `x_mi_blocker_count`, `x_mi_warning_count`, `x_mi_status`.
5. The form view's reactive widgets re-paint without a page reload.

The crons in `southbrook_premium_orchestration` (lesson 2.4) run this
same flow nightly across every in-flight MO so dashboards are honest
in the morning.

## Quiz (5 questions, applied)

**1.** You're looking at the MO form and see TWO notebook pages
("Kitchen" and "Intelligence") in addition to the stock Odoo tabs.
Which addons added each?

> "Kitchen" is added by `southbrook_mrp_kitchen_workcenters` via
> `view_mrp_production_form_sbk_kitchen` (project linkage, room,
> cabinet code, install due, priority, complexity, totals).
> "Intelligence" is added by `southbrook_manufacturing_intelligence`
> via `view_mrp_production_form_mi` (badge, checks list,
> recompute button, blocker/warning counts, yield, waste).

**2.** A developer asks "where does `x_sbk_kitchen_project_id` come
from?" What addon and what model?

> Field name prefix is `x_sbk_*` → owner is
> `southbrook_mrp_kitchen_workcenters`. The field is declared on
> `mrp.production` at
> `southbrook_mrp_kitchen_workcenters/models/mrp_production.py` and
> targets `sb.kitchen.project` (owned by the same addon's upstream
> dependency `southbrook_kitchen_workspace`).

**3.** Your sysadmin says "we want to remove Manufacturing
Intelligence to simplify the stack." What breaks?

> The MO form loses the Intelligence notebook page. The PM kanban
> tile loses its MI chip. `sb.production.package` loses
> `x_mi_status`, `x_mi_blocker_count`, `x_mi_warning_count`,
> `x_mi_next_action`. The PM menu loses MI Checks + MI Packages.
> But the rest of the stack — PM, kitchen workcenters, kitchen
> tools, kitchen MRP — continues to work because none of them
> depend on MI.

**4.** A trainee says "I can't find a Kitchen Ops menu in the
production-manager nav." Why not?

> "Kitchen Ops" is a phrase from older briefs; the actual menu
> roots are **Southbrook PM** (`menu_southbrook_pm_root`) and the
> grafted **Manufacturing → Southbrook Kitchen** branches. Operator
> daily work happens under the native **Manufacturing → Operations**
> tree filtered by their workcenter; planners and managers use the
> Southbrook PM root.

**5.** The MI engine writes to `x_mi_check_ids` on `mrp.production`
AND to `x_mi_check_ids` on `sb.production.package`. Are these the
same rows?

> No — they're TWO different one2many declarations targeting the
> same model (`southbrook.mi.check`) with different inverse FKs
> (`production_id` vs `production_package_id`). One check row is
> associated to either an MO or a package, not both. The engine
> writes them as separate cohorts; the same rule can fire against
> the MO directly (production / install checks) or against the
> package (cut / assembly checks via the cutlist + hardware refs).

---

## What this lesson does NOT cover

- The mrp.production field-by-field walkthrough → lesson 15.2.
- The mrp.workorder + tool readiness + downtime walkthrough → lesson 15.3.
- BoM extensions + cut-spec seam + lead-time bumps → lesson 15.4.
- Workcenter form surface and alternative chain → lesson 15.5.
- Kanban, swimlanes, search filters → lesson 15.6.
- MO ↔ cutlist ↔ hardware ↔ production package linkage → lesson 15.7.
- The MI engine's check rules themselves → Course 3 lesson 3.1.
- The premium orchestration crons that fire the engine nightly → Course 2 lesson 2.4.
