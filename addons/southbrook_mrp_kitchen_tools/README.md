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

## Commits 2-6 (planned)

| # | What lands |
|---|---|
| 2 | `southbrook.tool.asset` + `southbrook.tool.crib`, demo assets, kanban + form |
| 3 | Work-center + operation requirement models, `southbrook.tool.kit`, per-WC requirement demo |
| 4 | mrp.workorder readiness fields + buttons, `southbrook.tool.issue` / `.checkout` / `.maintenance.request`, availability check |
| 5 | `southbrook.tool.usage.log` + `southbrook.workorder.tool.consumption`, formula evaluator, cost rollup |
| 6 | QC root cause, downtime reasons, 12 dashboards, full demo scenarios, cron, docs |

## Install

Requires Odoo 19 Community Edition with the following modules
installed first: `mrp`, `stock`, `purchase`, `purchase_requisition`,
`maintenance`, `hr`, plus the Southbrook foundation modules
`southbrook_mrp_pm` and `southbrook_kitchen_mrp`.

```bash
odoo -d <db> -i southbrook_mrp_kitchen_tools
```

## Tests

```bash
odoo -d <db> -u southbrook_mrp_kitchen_tools --test-enable \
    --test-tags /southbrook_mrp_kitchen_tools
```

Tagged subsets:

* `--test-tags southbrook,kitchen_tools,categories` — seed integrity
* `--test-tags southbrook,kitchen_tools,product_ext` — product field
  surface

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
