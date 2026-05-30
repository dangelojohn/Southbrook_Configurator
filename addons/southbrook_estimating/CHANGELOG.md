# Changelog

All notable changes to the Southbrook Estimating addon are documented here.
Format inspired by [Keep a Changelog](https://keepachangelog.com/).

## [19.0.1.0.0] — 2026-05-30

### Phase 1 — Initial Release

The first public version of Southbrook Estimating, the sales-rep-facing
Order Builder for Southbrook Kitchens on Odoo 19.0 Community Edition.

#### Added

- 11 configurator attributes + 3 sub-attributes (50 values) covering family,
  width, series, box material, door style, finish, hinge side, finished
  sides, gables, handle, accessories, plus `accessory_type`, `door_count`,
  and `family_subtype` for the 12 cabinet templates
- 12 cabinet templates (wall_1dr, wall_2dr, base_1dr, base_2dr,
  drawer_bank, sink_base, tall_pantry, tall_oven, corner, vanity,
  accessory, worktop) with 132 attribute lines bound across them
- 4 declarative configurator rules in `data/config_rules.xml` (65 records):
  Rule 1 (Series → door style), Rule 2 (Box material → series),
  Rule 3 (Width → door count), Rule 4 (Family → soft-close)
- 6 channel pricelists + 3 tradesperson sub-tiers: Retail, Dealer,
  Tradesperson (with tier 1/2/3), Central KD, Big-Box, Refacing CTHS
- `_resolve_channel_pricelist` dispatcher and `_resolve_tradesperson_pricelist`
  sub-dispatcher (table-driven via class-level constants)
- Parametric panel-cut math via `_compute_panel_dimensions` (frameless euro
  construction; assumptions documented in NF14)
- `southbrook.order.analytics` companion model + `action_confirm` capture
  hook for the AI data spine
- NF6 schema: `sale.order.parent_order_id` self-ref + `version` integer
  + `action_duplicate_as_draft` server action (Image Floor pattern)
- NF7/NF8 schema: per-user `southbrook_default_series` and
  `southbrook_order_entry_mode` preferences
- Q21 zone schema: `sale.order.line.zone` 6-value selection +
  `zone_label` free-text + zone visual grouping in the Order Builder
- 3 QWeb reports: Signature Spec Sheet (sale.order), Shop Copy
  (mrp.production), Door Order (sale.order); styles share named CSS
  variables for the eventual SIGNATURE_SERIES_TOKENS swap
- Demo data (loaded with `--demo` flag): 5 partners, 6 open quotes,
  5 confirmed orders, 6 crm.leads, with `noupdate="1"` so demo
  modifications during review survive subsequent upgrades
- 95 test methods across 13 test files including a 10-step Phase-1
  smoke test gated by the `southbrook.seed_mode` config parameter

#### Known limitations

- Seed data is **illustrative**; canonical pricing requires parsing
  the source workbook
- Drawer-bank uses Phase-1 simplification (width-derived count); real
  drawer banks have fixed 3-drawer or 4-drawer variants
- Three.js procedural carcass (Phase 3) and Accucutt nest hand-off
  (Phase 4) are not yet shipped
- Signature Series typography + palette tokens are TBD pending the
  spec book PDF

See `PUNCHLIST.md` "Phase 2+ deferred items inventory" for the full
deferred-items list.

### Dependencies

This addon depends on the OCA `product_configurator` suite (modules
`product_configurator`, `product_configurator_mrp`, `product_configurator_sale`)
which are **not** on the Odoo Apps Store. Install them from the OCA
GitHub before installing this addon:

    https://github.com/OCA/product-configurator
