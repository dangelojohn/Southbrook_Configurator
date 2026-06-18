# Southbrook Hardware Catalog

Marathon Hardware catalog + the per-carcass `resolve(...)` method the
FreeCAD bridge calls post-render and the kitchen MRP module calls
during cutlist emission.

## Models

- `southbrook.hardware.catalog` — exposes `resolve(...)`. The
  rules table is `data/hardware_map.json`.
- `southbrook.hardware.brand` — 19 brand records.
- Extensions on `product.product`: `x_hardware_category`,
  `x_hardware_brand_id`, `x_marathon_sku`, `x_pricing_pending`.

## Audit P-task owned here

### P2 — Brand-aware slide override

`Catalog.resolve(...)` accepts a new `slide_sku` kwarg (default `None`,
backwards-compatible). When supplied AND a per_drawer rule entry is a
known slide SKU (`BLM-MOV-450 / KS-K2832-21 / KS-3032-18 /
HET-ACTRO-500 / PR-602728`), the resolver swaps in the requested SKU.
Non-slide per_drawer entries (handles) flow through unchanged.

The set of known slide SKUs is the class constant
`_DRAWER_SLIDE_SKUS`.

## Tests

The existing resolution tests cover the legacy default-slide path
unchanged; P2 acceptance is asserted from `southbrook_kitchen_mrp`'s
`test_p2_drawer_slide` (which exercises the integrated resolver →
build_from_order_line → hardware package chain).

## Rollback

P2 → always-on at the resolver layer; rollback is "stop passing
`slide_sku`". No data migration to undo.
