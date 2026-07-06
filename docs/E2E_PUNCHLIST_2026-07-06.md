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
| C2 | **RE-DIAGNOSED via dev-stack reproduction — server side is CORRECT; both agent theories refuted.** Direct measurement on SB-BASE-1DR's reconfigure wizard: 19 dynamic attribute fields ARE generated and correctly step-scoped — states 9/10/11/12 show 5/5/5/4 real input fields respectively (`invisible="state not in ['N']"`). The single-value hide heuristic removes ≤1 field (not "all"). The 3D viewport is placed BELOW the fields (not overlaying). So no server-side fix is warranted — applying the proposed one would have broken working step-scoping without fixing the symptom (the exact recurrence trap). **The "placeholder-only, no controls" symptom is CLIENT-SIDE:** a runtime JS error in the `cabinet_viewport` widget (syntax-valid, 1391 lines) OR stale prod backend assets. Silent-default apply follows: Confirm commits auto-applied session defaults because the user never reached the (present but unrendered) controls. **BLOCKED on browser diagnosis** (extension not connected). The batched `-u` regenerates southbrook_estimating assets → may resolve if staleness; else check the reconfigure wizard's browser console. | ⚠️ SERVER OK; client-side, needs browser | BLOCKED |
| C3 | **Live-checked: NO duplicate `ir.ui.view`** — exactly one view inherits the SO form with the reconfigure button. So the "twice" is the redundant `help="Reconfigure"` + `title="Reconfigure"` double-tooltip on the single OCA button (cosmetic). Low value; minor override to drop `title=` deferred. | ⚠️ cosmetic, deferred | OPEN |

## HIGH — data integrity

| # | Item | Root cause | Status |
|---|------|-----------|--------|
| H1 | **FIXED (data, reversible).** Reference-checked all 6 dup templates: **0 order lines, 0 BoMs, no xml_id** each (runtime-created orphans, not seed). `catalog_expansion.build_catalog` is idempotent-by-name so it binds to the active keeper — archiving won't re-create. **Archived** ids 213/212/239/237/230/229 (active=False). Catalog now 46 configurable templates, **zero duplicate names**. Reversible (un-archive to restore). | ✅ FIXED (archived on prod) | live |
| H2 | **Re-diagnosed — NOT a data duplicate.** There is only ONE `SB-BASE-2DR` template (id 39). The "$395 vs $560 same SKU" seen in the 3D inventory are **different variants of that one template** (`lst_price` = base 395 + attribute `price_extra`, ranging 395→705 across 10 variants). Expected variant pricing. The REAL issue: variants share the base `default_code` with no config suffix, so the 3D inventory list shows them as look-alike rows at different prices. → a 3D-inventory display/labeling fix (show the distinguishing config, or suffix variant codes), NOT a dedup. | RE-DIAGNOSED | OPEN |
| H3 | **CONFIRMED: 52/52 templates have standard_price = $0.00.** Margin = (price−cost)/price = 100% when cost=0. Seed loaded `list_price` only, never `standard_price`. Fix = backfill cost — but the actual cost figures are business data (Price Master "cost" column / Cost×1.05 basis); **need the source cost numbers from you.** | CONFIRMED (needs cost data) | OPEN |
| H4 | **✅ RESOLVED by H1.** After archiving the 6 blank-ref duplicates, **0 active config_ok templates lack a default_code** (verified on prod). The blank-SKU records were exactly the H1 dups. No separate fix needed. | ✅ RESOLVED (via H1) | live |
| H5 | **✅ DONE (data, reversible).** 4 test portal accounts (`.test` emails, 0 orders): archived users 177/179/181/182 then partners 537/539/541/542. 0 active 'C' contacts remain; no orders touched. | ✅ FIXED (archived on prod) | live |

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

## PIN gate removal (added 2026-07-06 — not on original list)
Operator PIN modal (`southbrook_qr_kit/operator_pin_modal.js`) auto-mounted on every
backend+frontend page and hijacked the sales-order Customer field with a "No operator — tap
to PIN in" full-page lock. Config kill-switch was already "0" but a stale bundle kept showing
it. **Per decision: PIN system will NOT be implemented.** Removed the modal from both asset
bundles + deleted the files (qr_kit 19.0.0.14.0), deployed → bundles regenerated, source file
404s on prod. Dormant server route + param kept (harmless, test-covered). ✅ DONE + deployed.

## Fix order (John's stated priority)
1. C1 Configure Product template-selection (full blocker)
2. C2 real per-stage input UI (currently placeholder graphic; silent apply)
3. H1/H2 catalog de-duplication (esp. SB-BASE-2DR)
4. H3 backfill cost data → real margins
5. M1 Kitchen Design ↔ Order Lines sync
6. M2 duplicate-Room-per-order
7. M4 audit all 52 templates for missing BoMs
