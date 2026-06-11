# Southbrook Kitchen Tool Control

Real-life tool, consumable, maintenance-supply, and tool-crib control
for the Southbrook kitchen / cabinet shop floor on top of Odoo 19
Community Edition.

## What ships in commit 1 (Foundation)

* `southbrook.tool.category` — hierarchical category model with 32
  `tool_family` values, 7 `directness` values, and 11 policy flags
  (`reusable`, `consumable`, `requires_sharpening`,
  `requires_calibration`, `requires_cleaning`, `requires_lot_tracking`,
  `requires_serial_tracking`, `requires_maintenance`,
  `has_expiry_date`, `hazardous`, `msds_required`) plus replenishment
  + work-center linkage defaults.
* Seed data for the 11-section A..K category tree from the build
  brief — ~110 categories arranged in 3-level parent / child trees
  covering cutting tools, fasteners + assembly, adhesives + glues,
  abrasives, finishing + paint, measuring + layout, clamps + jigs,
  hand / power / pneumatic, machine maintenance, safety + PPE, and
  packing + dispatch.
* `product.template` extensions with ~40 `x_southbrook_*` fields
  organised into six tabs (Classification / Cutting Geometry /
  Fastener Geometry / Chemical / Linkage / Replenishment & Life).
  Picking a tool category auto-seeds the product's policy flags,
  UoMs, and replenishment defaults.
* 3 security groups (Tool Operator, Tool Crib Manager, Maintenance
  Technician) wired into a new "Southbrook Tool Control" Settings
  module category.
* Sequences for assets, issues, checkouts, maintenance requests,
  usage logs, and consumption — referenced by commits 2-5.
* Menu entries: Manufacturing → Configuration → Southbrook Kitchen →
  Tool Categories, and Inventory → Products → Southbrook Tools &
  Consumables.
* 2 test modules with 17 tests covering seed integrity, product
  extension fields, category onchange seeding, and constraint
  enforcement.

## What ships in commit 2 (Assets & Cribs)

* `southbrook.tool.crib` — physical / organisational tool storage
  location, m2m to `mrp.workcenter`, optional `stock.location` link.
* `southbrook.tool.asset` — per-instance reusable tool record with
  11-state lifecycle, 6-grade condition, life tracking, maintenance
  dates, mail.thread chatter, and 9 `action_mark_*` state-machine
  helpers.
* `maintenance.equipment` back-link via `southbrook_tool_asset_ids`.
* 12 demo cribs + 12 demo assets (3 saw blades, 2 CNC bits, 1 hinge
  bit, 2 spray guns, caliper, torque driver, jig).

## What ships in commit 3 (Requirements & Kits)

* `southbrook.workcenter.tool.requirement` — what a work center needs
  in its serving cribs (category or specific product, quantity,
  mandatory/optional).
* `southbrook.operation.tool.requirement` — what a specific BoM
  operation needs (with `consume_qty_per_unit` for consumption math).
* `southbrook.tool.kit` + `southbrook.tool.kit.line` — named sets
  of tools issued together.
* `mrp.workcenter` extension — back-refs for requirements, cribs,
  assets, with smart-button actions.
* `mrp.routing.workcenter` extension — back-ref for operation
  requirements.

## What ships in commit 4 (Workorder Readiness Gate)

* `mrp.workorder` extension with `southbrook_tool_readiness_state`
  (4-state: `not_checked` / `ready` / `warning` / `blocked`) and
  `southbrook_tool_readiness_msg`.
* `action_check_tool_readiness` — button that enumerates the WO's
  op + WC requirements, counts available assets per requirement, and
  computes the readiness state.
* `button_start` override — raises `UserError` when readiness is
  blocked, with the failure detail naming each unmet requirement.
* Form view inherit adds the statusbar, button, and readiness-detail
  group.

## What ships in commit 5 (Consumption, Cost, Usage)

* `southbrook.workorder.tool.consumption` — one row per (workorder,
  asset OR product) with quantity, unit_cost, computed total_cost,
  and operator attribution.
* On create, the row applies asset-life side-effects: reduces
  `remaining_life_qty`, bumps `total_usage_qty`, stamps
  `last_used_date`/`last_used_workorder_id`, and auto-flips
  `lifecycle_state` to `needs_sharpening` when life crosses zero.
* List + form + search views, menu under Manufacturing > Operations.

## What ships in commit 6 (Production rollup, cron, demo)

* `mrp.production` extension with `southbrook_tool_consumption_ids`
  one2many, count, and stored `southbrook_tool_consumption_cost`
  rolled up from the consumption rows.
* `_cron_maintenance_sweep()` — daily ir.cron that flips
  `available`/`in_use` assets to `needs_sharpening` /
  `needs_calibration` when their due date is on or before today.
  Conservative: doesn't stomp manual states like `under_maintenance`.
* Demo: 5 workcenter requirements (saw, CNC bore, QC, hardware) +
  3 tool kits (Door Hardware Kit, Cutting Setup Kit, QC Kit).

## Install

Requires Odoo 19 Community Edition with the following modules
installed first: `mrp`, `stock`, `purchase`, `purchase_requisition`,
`maintenance`, `hr`, plus the Southbrook foundation modules
`southbrook_mrp_pm` and `southbrook_kitchen_mrp`.

```bash
odoo -d <db> -i southbrook_mrp_kitchen_tools
```

The QNAP southbrook-odoo container needs 6 GB memory limit for a
fresh `-i` install (was 4 GB before). For updates only,
`--workers=0 --max-cron-threads=0` keeps RSS under 300 MB and the
4 GB limit is fine.

## Tests

```bash
odoo -d <db> -u southbrook_mrp_kitchen_tools --test-enable \
    --test-tags /southbrook_mrp_kitchen_tools
```

Final tally: **63 tests pass, 0 failed, 0 errors** on Odoo 19 CE
(`--without-demo=all` skips 20 demo-presence tests that auto-skip
when demo data isn't loaded).

Tagged subsets:

* `--test-tags southbrook,kitchen_tools,categories` — seed integrity
* `--test-tags southbrook,kitchen_tools,product_ext` — product
  field surface
* `--test-tags southbrook,kitchen_tools,tool_crib` — crib model
* `--test-tags southbrook,kitchen_tools,tool_asset` — asset model
  + lifecycle
* `--test-tags southbrook,kitchen_tools,requirements` — WC + kit
* `--test-tags southbrook,kitchen_tools,readiness` — readiness gate
* `--test-tags southbrook,kitchen_tools,consumption` — consumption
  side-effects on asset life
* `--test-tags southbrook,kitchen_tools,cost_rollup` — MO cost
  aggregation
* `--test-tags southbrook,kitchen_tools,cron_sweep` — maintenance
  sweep cron

## Naming conventions

* Models: `southbrook.tool.*` / `southbrook.workcenter.tool.*` /
  `southbrook.workorder.tool.*`.
* Fields on `product.template` / `product.product`: prefixed
  `x_southbrook_*` (matches `southbrook_hardware_catalog`'s
  `x_hardware_*` pattern).
* Fields on `mrp.*` / `maintenance.*` (commits 4+): prefixed
  `southbrook_*` (matches `southbrook_mrp_pm`'s `southbrook_*`
  pattern).
* XML IDs: snake_case (`cat_blade_panel`, `seq_tool_asset`).
* Test tags: `@tagged("post_install", "-at_install", "southbrook",
  "kitchen_tools", "<feature>")`.

## License

LGPL-3.0.
