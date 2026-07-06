# Estimator Module E2E Punch List — 2026-07-06
Source: full manual E2E pass by John (Order Builder, Configurable Templates catalog, Kitchen
Designs, Rooms, standalone 3D Room Configurator). Tested on seed order **S01381** + a fresh
order. Status column filled as each is root-caused / fixed.

**Test-artifact note (John):** S01381 gained 2 lines during testing (B24 Base Cabinet;
reconfigured SB-BASE-1DR → new variant SB-BASE-1DR-248E84 + Config Session CS1162) and a
Filler Panel line from "Generate Layout". S01385 created then cancelled. Non-destructive; may
want S01381 reset to its original single line if it's a reference fixture. **[decision pending]**

---

## CRITICAL / blocking

| # | Item | Root cause | Status |
|---|------|-----------|--------|
| C1 | **FIXED (commit aa8de60).** Reproduced on dev stack: picker is fine at ORM level (visible/editable/46 templates); fault is purely the v19 client greying the delegated `product_tmpl_id` on the virtual (`res_id:None`) record, and a template-less wizard can't be pre-created (config.session NOT NULL). Fix: `action_config_start` now opens a plain-Many2one template picker (`southbrook.config.template.picker`) that hands off to the proven `create_config_wizard` path → real persisted record, no delegation to grey. Tests now DRIVE the flow (picker→Configure→real wizard→advance step). 8/8 pass. Deploy: batched. | ✅ FIXED (dev-verified) | deploy pending |
| C2 | **CONFIRMED (two compounding code defects).** (a) OCA `fields_get` (`product_configurator.py:520-522`) computes a step-filtered attribute set then **unconditionally overwrites it** — dead code; "steps" have never actually gated which fields render. (b) Southbrook's `add_dynamic_fields` (`southbrook_estimating/models/product_configurator.py:97-121`) hides any field whose attribute line has one value + a backfilled `default_val`; `catalog_expansion.py` now stamps `default_val` on many lines (incl. Soft-Close on Accessories for 34 SKUs), so for sparse catalog-expansion SKUs **every field on a step can be hidden at once** → empty screen showing only the unconditional 3D viewport widget. Defaults auto-apply at session create → Confirm silently commits them ($295→$310). Fix (a) first (restore real step-scoping), then guard (b) to never hide 100% of a step's fields. | CONFIRMED | OPEN |
| C3 | **Likely NOT source.** Only ONE `reconfigure_product` button in source (`product_configurator_sale/views/sale_view.xml:26-42`), but it carries redundant `help="Reconfigure"` AND `title="Reconfigure"` (doubled tooltip, not a two-row menu). A genuine two-row dropdown would be a **stale/duplicate `ir.ui.view` on the live QNAP** (cf. orphan-Studio-view / COW-lock traps). Fix: check live `ir.ui.view` for a duplicate inherited view of the SO form; drop redundant `title=` via an override (keep OCA clean, don't patch in place). | CONFIRMED (live check needed) | OPEN |

## HIGH — data integrity

| # | Item | Root cause | Status |
|---|------|-----------|--------|
| H1 | Catalog has **52 templates**, 6 genuinely duplicated. **CONFIRMED root cause:** TWO seed passes. Original 12 "locked" templates = ids **36–47** (Q8). A later expanded ~40-cabinet catalog = ids **212–251** re-created 6 products that already existed, by name, under new ids WITHOUT dedup. The 6 dup pairs (keep / delete): Base·2DR keep 39 / del 213; Base·1DR **both blank-ref** 38 & 212 (pick one); Oven Tower keep 43 / del 239; Tall Pantry keep 42 / del 237; **Wall·2DR both ref SB-WALL-2DR** 37 & 230; Wall·1DR keep 36 / del 229. **Delete is destructive — must check each dup id for existing order-line/variant references first.** | CONFIRMED | OPEN |
| H2 | **Re-diagnosed — NOT a data duplicate.** There is only ONE `SB-BASE-2DR` template (id 39). The "$395 vs $560 same SKU" seen in the 3D inventory are **different variants of that one template** (`lst_price` = base 395 + attribute `price_extra`, ranging 395→705 across 10 variants). Expected variant pricing. The REAL issue: variants share the base `default_code` with no config suffix, so the 3D inventory list shows them as look-alike rows at different prices. → a 3D-inventory display/labeling fix (show the distinguishing config, or suffix variant codes), NOT a dedup. | RE-DIAGNOSED | OPEN |
| H3 | **CONFIRMED: 52/52 templates have standard_price = $0.00.** Margin = (price−cost)/price = 100% when cost=0. Seed loaded `list_price` only, never `standard_price`. Fix = backfill cost — but the actual cost figures are business data (Price Master "cost" column / Cost×1.05 basis); **need the source cost numbers from you.** | CONFIRMED (needs cost data) | OPEN |
| H4 | **Re-scoped — NOT all 52.** Data shows **46/52 templates DO have a `default_code`; only 6 are blank — and those 6 are exactly the duplicate records from H1.** So "blank for all 52 in the list" is a **list-view column issue** (column bound to a field that doesn't render the template ref), not missing data. Fixing H1 removes the blank-ref dup records; the list-view column is a separate small view fix. | RE-SCOPED | OPEN |
| H5 | Customer picker surfaces **four contacts all named "C"** — test/junk partners. Data cleanup (archive/merge/rename). | CONFIRMED (data) | OPEN |

## MEDIUM — sync / workflow

| # | Item | Root cause | Status |
|---|------|-----------|--------|
| M1 | **CONFIRMED (architecture gap).** `kitchen.design` cabinet totals compute from its own `cabinet_line_ids` (model `southbrook.kitchen.design.line`), never from `sale.order.line`. Sync is one-way (design→SO); the reverse ("Rec D Sprint 2") cron was documented but never built (`reconcile.py:1-17`). Adding SO lines directly can't reach the design. Fix options: (a) make design a read-projection over SO lines, (b) build the reverse cron, or (c) minimal — have `_compute_totals` also sum cabinet products from `sale_order_id.order_line` so the card is never simply wrong. Team must pick the authoritative model. | CONFIRMED | OPEN |
| M2 | **CONFIRMED (missing idempotency + data cleanup).** Two room-creators race with no "does this order already have a room?" check: the reconcile cron (`reconcile.py:129-150`, gated only on `design.room_id`) creates a ~12in placeholder from a stray design's default `room_width_in=12`; the room wizard (`room_api.py:299-311`) creates "Main Kitchen". The wizard-built room (real walls) is authoritative for Layout/3D/print; the cron placeholder is inert clutter. Fix: cron checks `design.sale_order_id.room_ids` first; add one-active-room constraint or `is_primary`. Existing S01334/S01331 need data cleanup. | CONFIRMED | OPEN |
| M3 | **CONFIRMED (missing enforcement + backfill).** `wall.used_mm` sums only `sale.order.line` rows whose optional `wall_id` is set — and `wall_id` is only assigned by the Room Layout drag UI, never when a cabinet is typed into Order Lines. The `has_base/upper/tall_cabinets` flags are independent MANUAL booleans with no link to placed lines, so "flagged true / 0 used" isn't a detectable contradiction. Fix: surface unplaced lines (model already has `is_positioned`), force wall assignment, and/or compute the `has_*` flags from actual lines. | CONFIRMED | OPEN |
| M4 | **CONFIRMED (no catalog-wide generator + backfill).** No blanket BoM seeding. Only two narrow opt-in paths create BoMs (3D-configurator "Create Quotation" autoseed — which leaves `bom_line_ids` EMPTY; and the Hermes wizard on explicit Apply). Fillers/accessories (FP3) get neither. Fix: extract a catalog-wide generator that materializes real `bom_line_ids` from `_compute_panel_dimensions` (currently computed then discarded), run once over all `southbrook_is_cabinet` templates incl. accessories. | CONFIRMED | OPEN |
| M5 | **Send-quote composer doesn't auto-populate "To"** despite order having a Customer. (not yet code-traced) | OPEN |

## LOW — UX polish

| # | Item | Status |
|---|------|--------|
| L1 | 3D "Realistic view" renders cabinets as plain solid boxes — no door lines/hardware/panel detail. | OPEN |
| L2 | "Top"/"Front" camera presets still show perspective distortion + crossed bounding-box wireframe, not clean orthographic/blueprint geometry. | OPEN |
| L3 | **FIXED (code + data).** Two-layer code fix: `_DEMO_CONFIDENCE` 0.9→0.3 (mock output now correctly low-confidence, so the overwrite guard protects non-empty fields) + `_apply_enrichment` now NEVER writes customer-visible fields (`name`, `description_sale`) in demo mode even if empty. Tests added (green). **Data scrubbed on prod:** 1 product (id 38 — also an H1 dup) had 3 fields cleared; 1 draft order-line name reset. Post-scrub verify = 0 polluted records. Deploy: batched. | ✅ FIXED (dev-verified, data scrubbed) | deploy pending |
| L4 | "Preview" button flashes a blank dark "Website Preview" screen before redirecting to the portal quote page. | OPEN |

## Fix order (John's stated priority)
1. C1 Configure Product template-selection (full blocker)
2. C2 real per-stage input UI (currently placeholder graphic; silent apply)
3. H1/H2 catalog de-duplication (esp. SB-BASE-2DR)
4. H3 backfill cost data → real margins
5. M1 Kitchen Design ↔ Order Lines sync
6. M2 duplicate-Room-per-order
7. M4 audit all 52 templates for missing BoMs
