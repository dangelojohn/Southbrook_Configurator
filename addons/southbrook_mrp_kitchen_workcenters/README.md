# Southbrook Kitchen Work Centers

CE-safe enhancement layer on top of Odoo 19 MRP that gives the
Southbrook kitchen-cabinet shop a vocabulary the planner actually
uses: station types, materials, finishes, operation templates with
real duration formulas, downtime tracking, and rolled-up
kitchen-specific costing.

Built strictly on Community Edition. No Enterprise dependencies.

## Module scope

Four layers, four phases, four commits on `feature/mrp-kitchen-workcenters`.

### M1 — master data + station taxonomy

* `southbrook.kitchen.material` — 10 seeded (MDF, plywood, particle
  board, melamine, laminate, veneer, solid wood, quartz, stone,
  solid surface). Fields cover finishing requirements, edge-banding
  support, and subcontract defaults.
* `southbrook.kitchen.finish` — 9 seeded with sanding / paint-booth
  / cure-time / complexity factors.
* `mrp.workcenter` — `x_sbk_*` extension covering station type
  (14-value enum), machine code/brand, supported materials/finishes,
  required hr_skills, panel envelope (max length/width mm), setup +
  changeover times, parallel-jobs flag, bottleneck flag, OEE target,
  three notes columns, active-for-kitchen toggle.
* 2 new work centers seeded — `wc_engineering` (ENG01) and `wc_cnc02`
  (CNC02). Station type applied to the 12 existing southbrook_mrp_pm
  work centers via no-noupdate post-load applies.

### M2 — operation templates with duration formulas

* `southbrook.kitchen.operation.template` — 15 seeded: DESIGN_REVIEW,
  CUT_LIST, CUT_PANELS, CNC_ROUTING, EDGE_BANDING, DRILLING, SANDING,
  PAINT_LACQUER, COUNTERTOP_FAB, CARCASS_ASSEMBLY, DRAWER_ASSEMBLY,
  DOOR_FITTING, HARDWARE_FITTING, FINAL_QC, PACKING.
* `compute_expected_duration()` — the formula:

      total_min = setup + changeover                                  if fixed-mode
                = setup + changeover                                  per-unit-mode
                  + driver × minutes_per_unit
                    × material_factor
                    × finish_factor
                    × complexity_factor

  Negative drivers clamp to zero. Result is `math.ceil`-rounded.
  Setup / changeover defaults come from the template; callers can
  override per-call.

### M3 — quality + downtime + costing

* `southbrook.mi.check` extension — adds 9 check stages, 14 defect
  types, minor/major/critical defect severity (parallel to the
  upstream info/warning/blocker severity — never collapsed),
  pass/fail/rework/hold result, computed `x_sbk_rework_required`,
  rework workcenter + workorder back-link for routing the redo.
* `southbrook.kitchen.workcenter.downtime` — first-class log model
  with start/end timestamps, 13 reason codes, draft→active→closed
  state machine, computed duration_min, computed downtime_cost
  (duration × workcenter.costs_hour).
* `mrp.workorder` extension — `x_sbk_kitchen_expected_min` (parallel
  to native duration_expected for engine auditability),
  `x_sbk_variance_min`, estimated / actual / variance cost (Float,
  digits="Product Price" — workorder has no currency field in v19 CE),
  rework count + cost rolled up via the mi.check back-link, downtime
  min + cost aggregates, `action_sbk_recalc_kitchen_duration` button.

### M4 — production / routing wire-up + views + demo

* `mrp.production` extension — `x_sbk_kitchen_project_id` (Many2one
  to `sb.kitchen.project` from southbrook_kitchen_workspace —
  reused, never parallelled), kitchen_room, cabinet_code,
  install_due_date, complexity_factor, priority_level,
  rolled-up total estimated / actual / variance minutes,
  `action_sbk_recalc_all_workorder_durations` bulk button.
* `mrp.routing.workcenter` extension —
  `x_sbk_operation_template_id` binding,
  `x_sbk_driver_override`. The M3 stub helper on mrp.workorder
  reads these.
* Views — Kitchen tab on production form, costing + Recalc button
  on workorder form, template binding on routing list+form,
  install due + kitchen project on production list.
* Demo data — 1 `sb.kitchen.project` ("Demo - Smith Residence Kitchen").

## Field-prefix convention

* `x_mi_*` — upstream live MI state (not ours, don't touch).
* `southbrook_pm_*` — PM KPI fields (not ours, don't touch).
* `x_sbk_*` — this module's additions. Distinct so a `grep
  '^\s*x_sbk_' -rn addons/southbrook_mrp_kitchen_workcenters/` cleanly
  lists everything this layer owns.

## Dependencies

```
mrp
mrp_account
stock
hr_skills
southbrook_mrp_pm                  (existing 12 work centers)
southbrook_manufacturing_intelligence   (southbrook.mi.check)
southbrook_kitchen_mrp                  (existing cutlist + production package)
southbrook_kitchen_workspace            (sb.kitchen.project)
```

## Install / upgrade recipe (QNAP southbrook stack)

```
rsync -az --exclude=__pycache__/ --exclude='*.pyc' \
  addons/southbrook_mrp_kitchen_workcenters/ \
  admin@192.168.68.108:/share/CACHEDEV3_DATA/Container/southbrook/addons/southbrook_mrp_kitchen_workcenters/

ssh admin@192.168.68.108 \
  '/share/CACHEDEV3_DATA/.qpkg/container-station/bin/system-docker exec southbrook-odoo \
   odoo --workers=0 --http-port=18069 \
        -u southbrook_mrp_kitchen_workcenters \
        -d southbrook --stop-after-init --no-http'
```

Why `--workers=0`: Odoo emits the test runner only in single-process
mode. Use the default port (8069) only when no HTTP server is
running; otherwise `--http-port=18069` (or any free port) so the
ephemeral install doesn't collide with the long-running container.

After install, `docker restart southbrook-odoo` — registry signal
alone leaves worker ormcache poisoned and `/web/login` 500s with a
"Circular assets bundle" error. See
`memory/qnap_odoo_upgrade_cache_reset.md`.

## Running tests

```
odoo --workers=0 --http-port=18069 \
     --test-tags=sbk_kitchen --test-enable \
     -u southbrook_mrp_kitchen_workcenters \
     -d southbrook --stop-after-init --no-http
```

Subset tags: `m1`, `m2`, `m3`, `m4` (the phase tags), or `southbrook`
(everything Southbrook-tagged in the DB). All M1-M4 tests carry
`post_install` + `-at_install` so they run against an actual loaded
registry — many fields and seed templates need to exist before the
assertions are meaningful.

Suite size: 46 tests as of the M4 commit. 0 failures on live southbrook DB.

## License

LGPL-3. See `__manifest__.py`.
