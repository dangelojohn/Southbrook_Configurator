# Southbrook Kitchen MRP

Cut lists, hardware packages, and production packages — the structured-
data backbone the rest of the platform writes to when a cabinet enters
manufacturing.

## Models

| Model | Purpose |
|---|---|
| `sb.cutlist` + `sb.cutlist.line` | Per-MO panel cut list. Geometry comes from `shared/southbrook_dims.panel_cut_list`. Toe-kick is integrated into the side panels and is NOT emitted as a line. |
| `sb.hardware.package` + `sb.hardware.package.line` | Per-MO resolved hardware pick list. Built by `southbrook.hardware.catalog.resolve(...)`. |
| `sb.production.package` | Bundles a cutlist + hardware package + state machine. Optional `sale_order_line_id` back-ref (P1) is the idempotency key for auto-emit. |

## Audit P-tasks owned here

### P1 — Configurator → Cutlist + Production Package on confirm

`sb.production.package.build_from_order_line(order_line, mo=None)` is
the public service. Idempotent per `sale.order.line` via the
`sale_order_line_id` back-reference. Resolves dimensions
(`_resolve_dims_from_order_line`) from the variant's
`product_template_attribute_value_ids`, then delegates panel geometry
to the existing `generate_from_mo()` so the math stays shared with the
FreeCAD bridge and the G1 gate.

Invoked from `sale_order.action_confirm` in
`southbrook_premium_orchestration` behind `ir.config_parameter`
`southbrook_premium_orchestration.auto_emit_cutlist` (default OFF).

### P2 — Brand-aware Drawer Slide binding

`build_from_order_line` extracts the configurator's "Drawer Slide" pick
and threads it through to `southbrook.hardware.catalog.resolve(...,
slide_sku=...)`. Local 5-row `_SLIDE_VALUE_TO_SKU` table maps configurator
value names → Marathon SKU + `is_soft_close`. Duplicated from
`southbrook_configurator_ux` to avoid a manifest dep on a UX addon.

## Tests

```
TransactionCase, all rollback-only:
  test_cutlist_generation
  test_hardware_package
  test_nesting_io
  test_production_package
  test_build_from_order_line  (P1)
  test_p2_drawer_slide        (P2)
```

## Rollback

P1 → set `southbrook_premium_orchestration.auto_emit_cutlist=False`.
P2 → always-on; the resolver's `slide_sku` defaults `None`, so callers
that don't pass it see no change. `sale_order_line_id` is nullable;
legacy packages without it work unchanged.
