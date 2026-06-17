---
course: 12 — Kitchen Ops Deep Dive
chapter: 12.1
title: The Kitchen Ops Menu — Architecture, Ownership, Security
duration: 35 minutes
audience: Ops Lead + Developer (the two people who answer "why is this menu here and what owns it?")
prereqs: Course 2 (2.1 Kitchen Projects, 2.2 Release Gate, 2.4 Crons). Basic Odoo menu + action mechanics assumed.
custom_modules: southbrook_premium_orchestration, southbrook_kitchen_workspace, southbrook_kitchen_mrp, southbrook_mrp_pm, southbrook_manufacturing_intelligence
---

# The Kitchen Ops Menu — Architecture, Ownership, Security

## Who this lesson is for

You're the ops lead who has to answer "where do I find X?" all day, or
you're the developer who has to answer "if I rip out
`southbrook_premium_orchestration` does Kitchen Ops still work?" Both
of you need to know that Kitchen Ops is **not one addon's menu** — it's
a parent menuitem owned by `southbrook_premium_orchestration` with
seven submenus, each pointing at an action defined either in the same
addon or in a sibling. Get the ownership map wrong and you'll spend
hours hunting a missing menu after a partial install.

Course 2 lessons gave you the planner's-eye view of the screens
themselves. This lesson is the architecture map: which submenu lives
where, what action it triggers, which security group can see it, and
what happens to the menu when you uninstall an upstream addon.

## Where this lives on the site

Sign in as a planner or sysadmin at **southbrookcabinetry.space/odoo**.
The Kitchen Ops menu lives in the top app bar:

> **Kitchen Ops**

It's the second app entry after Sales (sequence 20 — see "behind the
scenes"). Click it to expand the eight submenus.

For the underlying menuitem records:

> **Settings → Technical → User Interface → Menu Items**

Filter by name containing `Kitchen Ops` to see all nine records (the
parent + eight children). Each one has an XML id you can use to trace
the seed file that defined it.

## What your screen shows

The Kitchen Ops parent menu carries eight children in this order
(sequence numbers in parens, all seeded in
`southbrook_premium_orchestration/views/menus.xml`):

| Seq | Label | Action | Underlying model | Owning addon |
|---:|---|---|---|---|
| 10 | Kitchen Jobs | `action_kitchen_jobs_board` | `project.task` (kanban + list) | `southbrook_premium_orchestration` |
| 20 | Production Release Queue | `action_production_release_queue` | `project.task` (filtered list) | `southbrook_premium_orchestration` |
| 30 | Install Risk | `action_install_risk_board` | `project.task` (risk-filtered) | `southbrook_premium_orchestration` |
| 40 | Workcenter Bottlenecks | `action_workcenter_bottleneck_board` | `mrp.workcenter` (kanban) | `southbrook_premium_orchestration` |
| 50 | MI Engine Status | `action_mi_engine_status` | `southbrook.mi.engine.state` (singleton form) | `southbrook_premium_orchestration` |
| 60 | Tool Lifecycle Board | `action_tool_lifecycle_board` | `southbrook.tool.asset` (kanban) | `southbrook_premium_orchestration` |
| 70 | Cut-Spec Overrides | `action_cut_spec_override_list` | `southbrook.cut.spec.override` (list) | `southbrook_premium_orchestration` |
| 80 | Archive Test Users | `action_test_user_archive_wizard` | wizard transient | `southbrook_premium_orchestration` |

The parent menu (`menu_kitchen_ops_root`) has no action of its own —
clicking the bare "Kitchen Ops" label does nothing useful in Odoo 19;
you have to click a child.

**Sequence numbers matter.** The 10-20-30 pattern leaves room for
later addons to insert their own children between existing ones
without renumbering. If you build a new Kitchen Ops submenu, pick a
sequence like 35 (between Install Risk and Workcenter Bottlenecks) so
the visual order matches the daily workflow.

## The addon ownership map

This is the question that comes up every time someone uninstalls
something:

- **`southbrook_premium_orchestration`** owns:
  - The parent menu (`menu_kitchen_ops_root`).
  - **All eight submenus** (every `menuitem` is in `menus.xml`).
  - The actions for Kitchen Jobs, Production Release Queue, Install
    Risk, Workcenter Bottlenecks, MI Engine Status, Tool Lifecycle
    Board, Cut-Spec Overrides.
  - The Archive Test Users wizard.
  - The `southbrook.mi.engine.state` singleton model (the State sibling
    of the abstract parent `southbrook.mi.engine` — see lesson 12.6 and
    Course 2 lesson 2.4's "behind the scenes" for the Odoo-19
    AbstractModel-inherit trap that forced this split).

- **`southbrook_kitchen_workspace`** owns:
  - The **Sales → Kitchen Workspace → Projects** menu (NOT under Kitchen
    Ops — see "design intent" below).
  - The `sb.kitchen.project` / `sb.kitchen.design.option` /
    `sb.kitchen.ai.analysis` / `sb.kitchen.appliance` /
    `sb.kitchen.approval` models.
  - The project state machine (`VALID_TRANSITIONS` in
    `models/sb_kitchen_project.py`) covered in lesson 12.2.

- **`southbrook_kitchen_mrp`** owns:
  - The `sb.cutlist` / `sb.hardware.package` / `sb.production.package`
    models surfaced by Kitchen Ops dashboards.
  - The `generate_from_mo` orchestrator (lesson 12.7).
  - The **Southbrook Kitchen → Production Packages** menu — NOT under
    Kitchen Ops.

- **`southbrook_mrp_pm`** owns:
  - The eight base `mrp.workcenter` records (SB-SAW, SB-EDGE,
    SB-CNC-BORE, SB-ASSY, SB-DOOR, SB-HW, SB-QC, SB-PACK) plus the
    extended 10 (CNC, EB, DOOR, SAND, PAINT, CURE, ASM, HW, QC, PACK).
  - The four PM KPI computes on `mrp.workcenter`
    (`southbrook_pm_inflight_count`, `southbrook_pm_throughput_today`,
    `southbrook_pm_late_count`, `southbrook_pm_equipment_alerts`) that
    the Workcenter Bottlenecks board reads.
  - The `southbrook_condition` enum on `maintenance.equipment`.
  - The **Southbrook PM** top-level menu (parallel to Kitchen Ops —
    different framing of overlapping data).

- **`southbrook_manufacturing_intelligence`** owns:
  - The abstract `southbrook.mi.engine` parent (the singleton State
    lives in `southbrook_premium_orchestration` because of the v19
    inherit trap).
  - The `southbrook.mi.check` model (`is_gate`, `severity`, `category`,
    `production_id`, `production_package_id`).
  - The `x_mi_*` extension fields on `sb.production.package` and
    `mrp.production` (`x_mi_status`, `x_mi_check_ids`,
    `x_mi_blocker_count`, `x_mi_warning_count`, `x_mi_next_action`,
    `x_mi_yield_pct`, `x_mi_waste_area_m2`, `x_mi_edge_band_m`).

## Design intent — why Kitchen Ops vs Sales vs Southbrook PM

There are three top-level menus that all surface kitchen-related data:

1. **Sales → Kitchen Workspace** — designer / salesperson view. Owns
   the **pre-sale** records (`sb.kitchen.project`). Lesson 12.2.
2. **Kitchen Ops** — planner / project manager view. Owns the
   **production lifecycle** records (`project.task` spines,
   release queue, MI status). Most of this Course 12.
3. **Southbrook PM** — production manager view. Owns the
   **operations** records (`mrp.workcenter` floor load, equipment,
   capacity planning). Lesson 12.5.

The same workcenter record (`mrp.workcenter` for SB-CNC-BORE) is read
from three menus: Manufacturing → Configuration → Work Centers (Odoo
native), Southbrook PM → Floor Load, and Kitchen Ops → Workcenter
Bottlenecks. **Different framing of the same data.** Choose the menu
that matches your role; don't try to do release-queue work from the
PM dashboard.

## Security — who can see Kitchen Ops?

The Kitchen Ops parent menu has **no `groups` attribute**. Anyone with
the default Odoo user role can see the label in the top bar. The
gating happens at the action level — each submenu's action carries
its own model-level ACL.

Two exceptions live on the parent's children:

- **Archive Test Users** (sequence 80) — `groups="base.group_system"`.
  Only the System user sees this entry, because it's a destructive
  wizard.
- **Tool Lifecycle Board** and **Cut-Spec Overrides** are visible to
  everyone but read-locked for non-MRP users via the standard
  `ir.model.access.csv` ACLs in
  `southbrook_premium_orchestration/security/`.

For a planner role to use all Kitchen Ops surfaces, they need
membership in:

- `mrp.group_mrp_user` (read on `mrp.production`, `mrp.workcenter`,
  `mrp.workorder`).
- `project.group_project_user` (read/write on `project.task`).
- `southbrook_mrp_pm.group_floor_manager` (floor-portal access — only
  needed for the portal templates in lesson 12.5).

Without `project.group_project_user`, the Kitchen Jobs board renders
an empty kanban — the action runs, but every record fails the
record-rule check. This is the most common "menu shows but board is
empty" failure mode for fresh user accounts.

## What changes when you uninstall an addon

The dependency chain matters when you're debugging a missing menu:

- **Uninstall `southbrook_premium_orchestration`** — Kitchen Ops menu
  disappears entirely. Sales → Kitchen Workspace stays. Southbrook PM
  stays. The MI Engine State singleton record is deleted; readiness
  flips silently stop happening because the six crons are gone.

- **Uninstall `southbrook_manufacturing_intelligence`** — the parent
  abstract MI engine model is removed, which breaks
  `southbrook_premium_orchestration` (it depends on it). Odoo refuses
  the uninstall unless you cascade. Kitchen Ops → MI Engine Status
  starts throwing `KeyError: southbrook.mi.check` on open.

- **Uninstall `southbrook_kitchen_workspace`** — Sales → Kitchen
  Workspace disappears. The `sb.kitchen.project` records are deleted.
  Kitchen Ops → Kitchen Jobs CONTINUES TO WORK because it reads from
  `project.task` (not `sb.kitchen.project`). But the design-options
  flow that creates the order in the first place is gone, so you'll
  stop seeing new spine tasks land on the board.

- **Uninstall `southbrook_kitchen_mrp`** — the cut/hardware/production
  package models are gone. Kitchen Ops menu still loads, but every
  `x_mi_*` field on `sb.production.package` cascades to `False` and
  the MI Production Board (Course 2 lesson 2.5) is empty.

Don't uninstall ad-hoc — these are tight coupling boundaries. The
ProductGraph-style "you can take a module out" promise does NOT apply
inside the Kitchen Ops stack.

## Your daily flow

**The ops lead (start of day, 5 min):**

- Open the top bar, click **Kitchen Ops**. All eight children must
  appear. If one is missing, the action it references couldn't be
  resolved at install time — check that addon's status under
  Settings → Apps.
- Click **Kitchen Jobs** first; this is your home screen. Lesson 12.3
  goes deep.
- The ordering is the workflow: Jobs (look at today) → Release Queue
  (clear blockers) → Install Risk (deliveries this week) →
  Workcenter Bottlenecks (mid-day load) → MI Engine Status (is the
  cron running?) → Tool Lifecycle (rare check) → Cut-Spec Overrides
  (PLM signals).

**The developer (when a menu is missing):**

1. Open **Settings → Technical → User Interface → Menu Items**.
2. Filter by `Kitchen Ops`. Confirm all 9 records present.
3. For each child, click in. The **Action** field MUST resolve. If
   it's empty, the action XML id was not seeded — most often because
   the owning addon was uninstalled or never installed.
4. If the action resolves but clicking the menu errors, the model the
   action references is the problem — check the model exists with
   `env['southbrook.mi.engine.state']` in a shell.

## Common mistakes + how to recover

**"I added a new MRP user and they can see Kitchen Ops but the Jobs
board is empty."**

Missing `project.group_project_user`. Add them to the Project / User
group under Settings → Users → Permissions. The action runs (which is
why the menu lights up), but the record rule on `project.task` filters
every row to zero.

**"After upgrading premium_orchestration, MI Engine Status is gone."**

Two failures look the same. (a) The action record was archived during
upgrade — check
`env.ref('southbrook_premium_orchestration.action_mi_engine_status')`
in a shell. If it returns nothing, re-run `-u
southbrook_premium_orchestration` to re-seed. (b) The singleton model
`southbrook.mi.engine.state` failed to register — check the upgrade log
for `Cannot inherit AbstractModel`. The fix is the sibling-stored-model
pattern documented in the cog comments.

**"Archive Test Users is greyed out / hidden for me."**

It's `groups="base.group_system"` only. Members of Project / Manager
or MRP / Manager don't see it. Either escalate to a sysadmin or get
added to the System group temporarily (and remove yourself when done).

**"I uninstalled `southbrook_kitchen_workspace` and now nothing
confirms a kitchen project."**

Workspace is the pre-sale layer. Without it, customers/designers
can't create design options, can't approve, and can't push a
configurator session into a sale.order. The Kitchen Ops board still
LOADS but it's read-only and nothing new lands. Reinstall workspace.

## What the system is doing behind the scenes

The Kitchen Ops parent menu is one `ir.ui.menu` record:

```xml
<menuitem id="menu_kitchen_ops_root"
          name="Kitchen Ops"
          sequence="20"
          web_icon="southbrook_premium_orchestration,static/description/icon.png"/>
```

No `action`, no `parent`. The eight children each have
`parent="menu_kitchen_ops_root"`, an `action=` referencing a sibling
action record, and a `sequence` controlling order. Odoo's menu loader
resolves each `action=` at install time and silently skips the menu
if the action can't be found (Odoo 19 emits a `ParseError` to the
log but the upgrade keeps going). This is why a missing menu is
almost always a missing action, not a missing menu record.

The action references are split across six XML files in the same
addon:

- `kitchen_jobs_views.xml` — `action_kitchen_jobs_board`.
- `production_release_views.xml` — `action_production_release_queue`.
- `install_risk_views.xml` — `action_install_risk_board`.
- `workcenter_bottleneck_views.xml` — `action_workcenter_bottleneck_board`.
- `mi_engine_views.xml` — `action_mi_engine_status`.
- `tool_lifecycle_views.xml` — `action_tool_lifecycle_board`.
- `cut_spec_override_views.xml` — `action_cut_spec_override_list`.
- `wizards/test_user_archive_views.xml` — `action_test_user_archive_wizard`.

The manifest's `data:` list loads these IN ORDER, with `menus.xml`
LAST so all action records exist by the time the menuitems try to
bind. Reorder the list and the install breaks — keep `menus.xml` last.

For multi-addon menus (none of Kitchen Ops's children come from
sibling addons, but the design pattern allows it), Odoo resolves the
`action=` via the global xml-id registry. As long as the foreign addon
loads BEFORE the menu file that references it, the reference
resolves. This is enforced via the `depends:` list in the manifest.

## Quiz (5 questions, applied)

**1.** A user reports "I can't see the MI Engine Status item under
Kitchen Ops." You check their groups and they're in MRP / User. What's
the most likely cause?

> Not a groups issue — MI Engine Status has no group restriction. The
> most likely cause is that the action record
> `action_mi_engine_status` failed to load (premium_orchestration was
> upgraded with an error, or the addon is partially installed). Check
> `env.ref('southbrook_premium_orchestration.action_mi_engine_status')`
> in a shell. If it's None, re-run `-u
> southbrook_premium_orchestration` to re-seed.

**2.** You're adding a new submenu "Kitchen Ops → Daily Briefing" that
shows yesterday's MO summary. What sequence number do you pick, and
which addon should own it?

> Pick something like 5 (above Kitchen Jobs) or 15 (between Jobs and
> Release Queue) so it appears in the visual order matching the
> workflow. Owning addon: add it to
> `southbrook_premium_orchestration/views/menus.xml` ONLY if the action
> + model also live in that addon. If the briefing model is a new
> standalone addon, the menuitem lives in that new addon, parented to
> `southbrook_premium_orchestration.menu_kitchen_ops_root` via xml-id
> reference.

**3.** A planner asks "why is the Kitchen Workspace under Sales but
Kitchen Jobs under Kitchen Ops?" Walk through the answer.

> Kitchen Workspace owns the pre-sale lifecycle — designers and
> customers work it before money changes hands. It belongs under Sales
> because the salesperson and designer live there. Kitchen Ops owns
> the post-sale production lifecycle — planners and PMs work it after
> confirmation. Different teams, different menus, same underlying
> kitchen. The `project.task` spine is the bridge — Kitchen Workspace
> creates the customer agreement, Kitchen Ops manages turning it into
> manufactured cabinets.

**4.** You uninstall `southbrook_kitchen_mrp` for a refactor. The
Kitchen Ops menu still loads but the Workcenter Bottlenecks dashboard
shows empty tiles. Why?

> The Workcenter Bottlenecks board reads from `mrp.workcenter` and the
> four `southbrook_pm_*` KPI fields — those live in
> `southbrook_mrp_pm`, not `southbrook_kitchen_mrp`. So the workcenter
> records and KPIs survive the uninstall. But the
> `x_mi_yield_pct` / `x_mi_waste_area_m2` rollups depend on
> `sb.cutlist` (which IS in kitchen_mrp) — the MI rollups fall to zero
> because there's no cutlist data to compute against. Tiles render but
> with stale/zero data.

**5.** A developer wants to add `groups="southbrook_mrp_pm.group_floor_manager"`
to the Workcenter Bottlenecks submenu so only floor managers see it.
What's the right call?

> Don't gate at the menu level for this — it overscopes. The same
> board is useful to the planner (lesson 12.5 audience) who isn't a
> floor manager. Gate at the **record-rule level** instead: floor
> managers see only their assigned stations; planners see all. The
> menu stays visible to everyone, and the data scoping happens at
> the model layer. Menu-level groups are for destructive admin
> actions (e.g. Archive Test Users), not for role-specific views.

---

## What this lesson does NOT cover

- The detailed shape of the Kitchen Jobs board itself → lesson 12.3.
- The state machine on `sb.kitchen.project` and how Workspace records
  bridge into the Kitchen Ops board → lesson 12.2.
- What the five release booleans mean and how the engineer flips them
  → lesson 12.4 + Course 2 lesson 2.2.
- The Workcenter Bottleneck dashboard internals → lesson 12.5 +
  Course 2 lesson 2.3.
- MI Engine Status from the sysadmin's perspective → lesson 12.6 +
  Course 7 lesson 7.1.
- Cut + hardware + production packages → lesson 12.7.
- Native Odoo `ir.ui.menu` mechanics, group inheritance, and menu
  resolution → Odoo's own developer documentation.
