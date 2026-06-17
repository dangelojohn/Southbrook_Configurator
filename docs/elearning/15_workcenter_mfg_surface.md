---
course: 15 — Manufacturing Module Deep Dive
chapter: 15.5
title: Workcenter on the Manufacturing Surface — Form, Alternatives, Operation Templates, Load
duration: 30 minutes
audience: Production Manager + Developer maintaining workcenter configuration
prereqs: Lesson 15.1, Course 1 lesson 1.1 (workcenter orientation), Course 2 lesson 2.3 (bottleneck scheduling), comfortable with native Odoo workcenter form
custom_modules: southbrook_mrp_pm, southbrook_mrp_kitchen_workcenters, southbrook_mrp_kitchen_tools, southbrook_manufacturing_intelligence
---

# Workcenter on the Manufacturing Surface — Form, Alternatives, Operation Templates, Load

## Who this lesson is for

You're the production manager (or the developer who supports them)
maintaining the workcenter configuration on the Manufacturing surface.
Course 1 lesson 1.1 introduced the 14 seeded workcenters; this lesson
goes deeper on what the **workcenter form view itself** carries — the
notebook page added by `southbrook_mrp_kitchen_workcenters`, the four
non-stored KPI tiles added by `southbrook_mrp_pm`, the MI chip
overlay, the tool-control fields, the alternative-workcenter chain
(`alternative_workcenter_ids` for CNC swap), how operation templates
attach to BoM routings, and the capacity pivot you use to plan the
next 5 days.

## Where this lives on the site

> **/odoo/manufacturing → Configuration → Work Centers → <station>**

This is the canonical workcenter form. Don't confuse it with the
**shop-floor view** that the operator uses (touch buttons, big
queue) — the shop-floor view reads the same workcenter record but
renders a different OWL component.

Also relevant:

> **Southbrook PM → Dashboard** — workcenter kanban, KPI tiles
> **Southbrook PM → Floor Load** — same workcenter list, planner framing
> **Southbrook PM → Capacity** — pivot + graph on `mrp.workorder`
> **Manufacturing → Configuration → Southbrook Kitchen → Kitchen Operation Templates** — 15 seeded templates

## What your screen shows — the workcenter form

Native Odoo gives you Name, Code, Working Hours, Time Efficiency,
Costs/Hour, OEE Target, Alternative Workcenters, Equipment, Maintenance
sub-tabs. Southbrook layers in:

### Kitchen Configuration notebook page (kitchen_workcenters)

Added by `view_mrp_workcenter_view_inherit_kitchen` (file:
`southbrook_mrp_kitchen_workcenters/views/mrp_workcenter_views.xml`).
Tab name `sbk_kitchen`. Four groups:

**Identity + Capability:**

| Label | Field (model.field, owner) | Type | What it carries |
|---|---|---|---|
| Station Type | `x_sbk_station_type` (`mrp.workcenter`, kitchen_workcenters) | Selection (14 values) | engineering / cutting / cnc / edge_banding / drilling / sanding / finishing / countertop / assembly / hardware / quality / packing / subcontract / other |
| Machine Brand | `x_sbk_machine_brand` (`mrp.workcenter`, kitchen_workcenters) | Char | "SCM" / "Biesse" / "Holz-Her" / "Felder" / "Festool" |
| Machine Code | `x_sbk_machine_code` (`mrp.workcenter`, kitchen_workcenters) | Char | Vendor model number (e.g. "SCM Olimpic K560") |
| Active for Kitchen | `x_sbk_active_for_kitchen` (`mrp.workcenter`, kitchen_workcenters) | Boolean (default True) | Hides from kitchen menus without deactivating in core MRP |

**Constraint Posture:**

| Label | Field (model.field, owner) | Type | What it carries |
|---|---|---|---|
| Is Bottleneck | `x_sbk_is_bottleneck` (`mrp.workcenter`, kitchen_workcenters) | Boolean | ToC configuration flag (distinct from MO-live `x_mi_bottleneck_workcenter_id`) |
| Allows Parallel Jobs | `x_sbk_allows_parallel_jobs` (`mrp.workcenter`, kitchen_workcenters) | Boolean | True for stations that can run multiple WOs concurrently |
| OEE Target | `x_sbk_oee_target` (`mrp.workcenter`, kitchen_workcenters) | Float (default 0.85), widget=percentage | KPI tile benchmark |

**Capacity Envelope:**

| Label | Field (model.field, owner) | Type | What it carries |
|---|---|---|---|
| Max Panel Length (mm) | `x_sbk_max_panel_length_mm` (`mrp.workcenter`, kitchen_workcenters) | Float | In-feed length limit |
| Max Panel Width (mm) | `x_sbk_max_panel_width_mm` (`mrp.workcenter`, kitchen_workcenters) | Float | In-feed width limit |
| Default Setup Time (min) | `x_sbk_default_setup_time_min` (`mrp.workcenter`, kitchen_workcenters) | Float | Per-WO setup minutes; templates override |
| Changeover Time (min) | `x_sbk_changeover_time_min` (`mrp.workcenter`, kitchen_workcenters) | Float | Material/finish/tool swap minutes |

**Capability Sets** (many2many_tags widget):

| Label | Field (model.field, owner) | Target | What it carries |
|---|---|---|---|
| Supported Materials | `x_sbk_supported_material_ids` (`mrp.workcenter`, kitchen_workcenters) | M2M → `southbrook.kitchen.material` | Op templates gate routing against this |
| Supported Finishes | `x_sbk_supported_finish_ids` (`mrp.workcenter`, kitchen_workcenters) | M2M → `southbrook.kitchen.finish` | Finish gating |
| Required Skills | `x_sbk_required_skill_ids` (`mrp.workcenter`, kitchen_workcenters) | M2M → `hr.skill` | Operator-skill cross-reference |

**Notes blocks** (3 free-text fields, nolabel):
- `x_sbk_planning_notes` — scheduler-facing
- `x_sbk_shop_floor_notes` — operator-facing (renders on traveler)
- `x_sbk_quality_notes` — QC-facing; wired to mi.check

### Tool Control fields (kitchen_tools, smart buttons / inline)

| Label | Field (model.field, owner) | Type | What it carries |
|---|---|---|---|
| Tool Requirements | `southbrook_tool_requirement_ids` (`mrp.workcenter`, tools) | O2M → `southbrook.workcenter.tool.requirement` | Required tools at the WC |
| Tool Requirement Count | `southbrook_tool_requirement_count` (`mrp.workcenter`, tools) | Integer, compute | Smart button count |
| Tool Cribs | `southbrook_tool_crib_ids` (`mrp.workcenter`, tools) | M2M → `southbrook.tool.crib` (rel `southbrook_tool_crib_wc_rel`) | Cribs serving this WC |
| Tool Assets | `southbrook_tool_asset_ids` (`mrp.workcenter`, tools) | O2M → `southbrook.tool.asset` | Asset back-refs |
| Tool Asset Count | `southbrook_tool_asset_count` (`mrp.workcenter`, tools) | Integer, compute | Smart button count |

### PM KPI tiles (mrp_pm — only shown on the dashboard kanban)

These four are non-stored Integer computes (deps_context `uid`), so
they recompute on every page-load. They don't show on the form by
default — they're for the **Southbrook PM Dashboard** kanban cards.

| Tile | Field (model.field, owner) | Source query |
|---|---|---|
| In-flight WOs | `southbrook_pm_inflight_count` (`mrp.workcenter`, mrp_pm) | `mrp.workorder` where state in (pending, waiting, ready, progress) and `workcenter_id == self.id` |
| Done Today | `southbrook_pm_throughput_today` (`mrp.workcenter`, mrp_pm) | `mrp.workorder` state=done AND date_finished ≥ today 00:00 |
| Late MOs | `southbrook_pm_late_count` (`mrp.workcenter`, mrp_pm) | `mrp.production` not done/cancel, date_deadline < now, WO touches this WC |
| Equipment Alerts | `southbrook_pm_equipment_alerts` (`mrp.workcenter`, mrp_pm) | `maintenance.equipment` where `southbrook_condition` in (fair, watch, critical, offline) |

### MI chips (manufacturing_intelligence overlay)

Two more non-stored Integers added by MI, NOT shown on the form but
shown as chips on the dashboard kanban:

| Field (model.field, owner) | Type | What it carries |
|---|---|---|
| `x_mi_workcenter_blocker_count` (`mrp.workcenter`, MI) | Integer, NOT stored | MOs not done/cancel touching WC with `x_mi_blocker_count > 0` |
| `x_mi_workcenter_warning_count` (`mrp.workcenter`, MI) | Integer, NOT stored | Sum of `x_mi_warning_count` on those MOs |

A code-comment warns: "do NOT add store=True (would deadlock the MO
save path)" — the MO save touches MI counts, which would touch the
workcenter, which would touch all MOs again.

## The alternative-workcenter chain

Native Odoo gives `mrp.workcenter.alternative_workcenter_ids` (M2M to
itself). Southbrook seeds the pairing **at the operation-template
level, not at the workcenter level**.

The only configured pair in
`southbrook_mrp_kitchen_workcenters/data/mrp_workcenter_seed.xml`:

| Primary | Backup | Where wired |
|---|---|---|
| `SB-CNC-BORE` (xml_id `southbrook_mrp_pm.workcenter_cnc_bore`) | `CNC02` (xml_id `wc_cnc_router_02`) | Reciprocal `alternative_workcenter_ids` on each |

The seed file sets the reciprocity convention: A lists B → B lists A.
The test asserts the round-trip.

For routing-time alternatives, the operation templates carry their
own `alternative_workcenter_ids` M2M. Two templates use it:

| Template code | Default WC | Alternative |
|---|---|---|
| `CNC_ROUTING` (seq 40) | `SB-CNC-BORE` | `wc_cnc_router_02` (= CNC02) |
| `DRILLING` (seq 60) | `SB-CNC-BORE` | `wc_cnc_router_02` (= CNC02) |

The other 13 templates have no alternative — they're tied to one
workcenter and if it goes down, MOs slip (lesson 2.3 covers the
recovery options).

**Why two layers?** The workcenter-level pair is a *configuration*
("these two stations are functionally equivalent"). The
operation-template-level pair is a *routing decision* ("THIS step in
the cabinet routing can run on either"). They're independent; you
could have an alternative chain at the WC level that isn't used at
template level.

## The operation-template relationship

Model `southbrook.kitchen.operation.template` (owned by
`southbrook_mrp_kitchen_workcenters`). Full schema:

| Field | Type | Default | Notes |
|---|---|---|---|
| `name` | Char | — | Required, indexed, translate |
| `code` | Char | — | Required, indexed, unique |
| `sequence` | Integer | 10 | |
| `active` | Boolean | True | |
| `operation_category` | Selection (14, same as STATION_TYPES) | — | Required, indexed |
| `default_workcenter_id` | M2O → `mrp.workcenter` | — | Primary WC |
| `alternative_workcenter_ids` | M2M → `mrp.workcenter` | — | Overflow targets |
| `default_setup_time_min` | Float | 0.0 | |
| `default_changeover_time_min` | Float | 0.0 | |
| `quantity_driver_type` | Selection (12: fixed / panel_count / sheet_count / edge_meters / surface_area_m2 / hole_count / hinge_count / drawer_count / hardware_count / cabinet_count / product_qty / custom) | product_qty | Required |
| `minutes_per_unit` | Float | 0.0 | |
| `material_adjustment_factor` | Float | 1.0 | Must be > 0 |
| `finish_adjustment_factor` | Float | 1.0 | Must be > 0 |
| `complexity_factor` | Float | 1.0 | Must be > 0 |
| `required_skill_ids` | M2M → `hr.skill` | — | |
| `supported_material_ids` | M2M → `southbrook.kitchen.material` | — | |
| `supported_finish_ids` | M2M → `southbrook.kitchen.finish` | — | |
| `requires_qc` | Boolean | False | Gates next op on mi.check record |
| `qc_checklist` | Text | — | Renders on traveler when requires_qc |
| `required_documents` | Text | — | |
| `shop_floor_instruction` | Text | — | |
| `creates_rework_allowed` | Boolean | False | |
| `blocks_next_operation` | Boolean | True | |
| `notes` | Text | — | |

**The duration formula** — `compute_expected_duration(driver_value,
material_factor, finish_factor, complexity_factor, setup_time_min,
changeover_time_min)`:

```
if fixed:
    total = setup + changeover
else:
    total = setup + changeover
          + driver_value * minutes_per_unit
            * material_factor * finish_factor * complexity_factor
return max(int(math.ceil(total)), 0)
```

All factor args fall back via `_safe_factor()` (None/0/negative →
template default). Always rounded up via `math.ceil`. Constraints
enforce non-negative times and strictly-positive factors.

**The flow into workorders**:

1. BoM has a `mrp.routing.workcenter` row.
2. The routing row carries `x_sbk_operation_template_id` (M2O →
   operation template, added by kitchen_workcenters).
3. At MO confirmation, native Odoo generates `mrp.workorder` rows
   from the routing.
4. The WO's `action_sbk_recalc_kitchen_duration` button calls
   `template.compute_expected_duration(driver, material_factor,
   finish_factor, complexity_factor=production_id.x_sbk_complexity_factor)`
   and writes the result to `x_sbk_kitchen_expected_min`.
5. From there, variance and cost (lesson 15.3) follow.

Native `time_cycle` on the routing row stays untouched for A/B
comparison.

## The capacity report

`southbrook_mrp_pm/views/pm_capacity.xml` defines `action_pm_capacity`
on `mrp.workorder`, view_mode `pivot,graph,list,form`:

- **Pivot** (`view_pm_capacity_pivot`): rows = `workcenter_id`,
  columns = `date_start` (interval=day), measure = `duration_expected`
- **Graph** (`view_pm_capacity_graph`): bar chart, stacked,
  `date_start × workcenter_id`, measure = `duration_expected`
- Default domain: state in pending / waiting / ready / progress
- Context: `search_default_group_by_workcenter: 1`

Menu entry `menu_pm_capacity` under `menu_southbrook_pm_root`,
sequence 7.

A 480-min shift is the implicit ceiling per WC per day. There's no
explicit "remaining hours" computed field yet (Phase 2 enhancement,
flagged as TBD).

## Your daily flow

**1. PM weekly setup (Monday morning, 20 min):**

- **Southbrook PM → Capacity**, pivot view, time range = current
  week. Look at the pivot row for each bottleneck WC. If any cell
  > 480 min, that day is over-committed — push lower-priority MOs
  to a quieter day.
- **Southbrook PM → Dashboard**, scan KPI tiles. Equipment Alerts
  > 0 on a bottleneck = check the equipment record before any work
  starts.
- Open each workcenter you'll lean on this week. Read
  `x_sbk_planning_notes` for the prior-week handoff.

**2. WC config change (rare, ~monthly):**

- New machine arrives → add a workcenter, set
  `x_sbk_station_type`, `x_sbk_machine_brand`, capability sets.
- Bottleneck flag change → update `x_sbk_is_bottleneck` ONLY after
  a documented capacity analysis. This flag is a Theory-of-Constraints
  call, not a "currently busy" signal. See lesson 2.3 for the
  recovery story when you get it wrong.
- New alternative pair → update BOTH workcenter records'
  `alternative_workcenter_ids` (Southbrook's reciprocity convention)
  AND update any operation template that should fall back.

**3. Op template change (when operator feedback says estimates are
off):**

- Open **Manufacturing → Configuration → Southbrook Kitchen → Kitchen
  Operation Templates → <code>**.
- Adjust `minutes_per_unit` based on the actual variance data
  (lesson 15.3 explains how to read variance).
- Save. New MOs created after the change pick up the new formula
  automatically.
- For in-flight MOs, hit the **Recalc All Workorder Durations**
  button on each affected MO (lesson 15.2) to re-derive expected
  minutes.

## Common mistakes + how to recover

**"I added a new workcenter but the dashboard tile doesn't show
KPIs."**

The four `southbrook_pm_*` fields are computes that depend on
`uid` (page-load context), not on workcenter creation. The first
page-load after the WC is added populates the tile. If still blank,
check that the WC has `active=True` (the dashboard's domain
filters `active=True`).

**"I flipped `x_sbk_is_bottleneck = False` on SB-EDGE because we
got a second bander, and now the planner is overloading both."**

The flag is a Theory-of-Constraints structural decision — "never
schedule more than this station can deliver." Flipping it False
removes the planning safety rail. Recovery: flip it back to True.
The right model for the second bander is ONE workcenter with
`x_sbk_allows_parallel_jobs = True`, not two records with the
bottleneck flag off.

**"I changed an operation template's `minutes_per_unit` and the
in-flight MOs didn't update."**

Templates feed `x_sbk_kitchen_expected_min` ONLY when the recalc
button fires. In-flight MOs keep their original estimates until you
hit **Recalc All Workorder Durations** on the MO. New MOs after the
template change pick up the new formula at confirmation time.

**"`alternative_workcenter_ids` on SB-CNC-BORE shows CNC02 but
CNC02's `alternative_workcenter_ids` is empty."**

Reciprocity broke. The seed file sets both sides; if a manual edit
removed one, the planner's reroute logic won't find the backup from
CNC02's side. Re-add CNC02 → SB-CNC-BORE on CNC02's m2m. Test
`test_m1_workcenter_fields.py` asserts the round-trip, so if
you've broken it, the next CI run flags it.

**"The Capacity pivot is empty for a workcenter that I know has
work scheduled."**

Domain filter is `state in pending / waiting / ready / progress`.
Done or cancelled WOs don't show. Also, the `date_start` field
must be populated — if your WOs are `confirmed` but unscheduled,
they won't appear. Plan the MOs to populate `date_start`.

## What the system is doing behind the scenes

Workcenter is the **fattest extension surface** in the platform —
35+ fields across four addons. Each addon writes to its own
namespace (`x_sbk_*`, `southbrook_pm_*`, `southbrook_tool_*`,
`x_mi_*`) so a `grep x_sbk_ addons/` immediately tells you which
fields are owned by which addon.

The KPI computes on `mrp.workcenter` are **non-stored on purpose**:
storing them would mean every WO save, every equipment condition
flip, every MO update triggers a write on the workcenter row, which
in turn would cascade through other computes. Non-stored = read on
demand; the underlying queries are cheap (one indexed FK lookup
each).

The operation-template formula is the only place math lives.
Everything else (variance, cost, total minutes on the MO) is a
downstream compute that depends on per-WO `x_sbk_kitchen_expected_min`.
This is why one click on Recalc fans out cleanly: change the
template, recalc the WO, the MO totals re-aggregate, the variance
re-derives, the cost re-prices.

**v19 gotcha** — the operation template uses `_sql_constraints` for
unique `name` and unique `code`. Per session memory, Odoo 19
silently ignores legacy `_sql_constraints` lists; the constraints
may not be reaching Postgres. There's a planned migration to
`models.Constraint`. Until then, application-layer code is the
guarantee — don't create two templates with the same code.

## Quiz (5 questions, applied)

**1.** SB-CNC-BORE goes down. The operator pages. You open the
workcenter's `alternative_workcenter_ids` and see CNC02. Is that
enough to reroute, or do you also need to check the operation
template?

> Both. The workcenter pairing makes CNC02 a recognized
> alternative; the operation template's
> `alternative_workcenter_ids` controls whether the SPECIFIC
> routing step can run on CNC02. The CNC_ROUTING and DRILLING
> templates both list CNC02; other templates (e.g. HARDWARE_FITTING)
> don't, so those steps can't run on CNC02 even though the
> workcenters are paired. Check both layers before rerouting.

**2.** A developer asks "I want to add a 'noise level' field for
ear-protection compliance. Where should it live and what prefix?"

> `mrp.workcenter` is the right model. Prefix `x_sbk_*` (it's
> kitchen-shop config, not a PM KPI or MI metric). Add it to
> `southbrook_mrp_kitchen_workcenters/models/mrp_workcenter.py` as
> `x_sbk_noise_level_db` (Float). If it should drive UI behaviour
> (e.g. require a PPE check), wire it through the operation-template
> formula or a separate readiness gate — DON'T overload the
> existing tool readiness state machine.

**3.** The Capacity pivot shows SB-PAINT at 720 min on Thursday.
A shift is 480 min. What does this mean and what do you do?

> The paint booth is over-committed by 240 min (4 hours).
> Since `x_sbk_allows_parallel_jobs = False` on PAINT (it can
> only spray one job at a time), you can't fix this by parallelism.
> Options: (a) overtime tonight or Wednesday, (b) push lowest-priority
> MO to Friday (look at the workorders touching PAINT on Thursday,
> sort by MO `x_sbk_priority_level`, shift the `low` ones),
> (c) subcontract door finishing for some MOs if a partner is
> approved. The MI engine will catch this and flag the affected
> MOs with a `capacity_blocker` if untouched.

**4.** You see the workcenter dashboard kanban tile for SB-EDGE
with a red MI chip (`o_sb_mi_chip_blocker`) and the number 3.
What's it telling you?

> 3 MOs touch SB-EDGE that the MI engine has flagged with
> `x_mi_blocker_count > 0`. Click the chip → opens the filtered MO
> list. Each MO's Intelligence tab will explain the specific
> blocker (most likely "panel exceeds max length", "edge band
> meters exceed capacity", or a material mismatch). The chip is
> from the `view_southbrook_pm_kanban_mi` view inheriting the PM
> dashboard kanban.

**5.** Operation template CARCASS_ASSEMBLY has
`minutes_per_unit = 3.5` and `quantity_driver_type = panel_count`.
A WO has 12 panels, complexity factor 1.0, no setup or changeover.
What's the expected duration?

> `total = 0 (setup) + 0 (changeover) + 12 (driver) * 3.5
> (min/unit) * 1.0 * 1.0 * 1.0 = 42 min`. Always rounded up by
> `math.ceil`, so 42 min exactly. If complexity factor were 1.2,
> total would be `12 * 3.5 * 1.2 = 50.4` rounded up to **51 min**.

---

## What this lesson does NOT cover

- MO-side fields (Kitchen tab, Intelligence tab) → lesson 15.2.
- Workorder-side fields (variance, tool readiness, downtime) → lesson 15.3.
- BoM extensions + cut constants → lesson 15.4.
- MO Kanban + search filters → lesson 15.6.
- MO ↔ cutlist / hardware / production package → lesson 15.7.
- Workcenter orientation (the 14 seeded codes) → Course 1 lesson 1.1.
- Bottleneck-aware scheduling daily flow → Course 2 lesson 2.3.
- Native Odoo workcenter + routing → Odoo native training.
