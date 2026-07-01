# Recommendation D — "Living Kitchen" · Master Spec
**Date:** 2026-07-01 · **Owner:** Rec D unification workstream · **Baseline:** `southbrook_kitchen_3d_configurator` 19.0.5.0.2 live.

**Backup snapshots:**
- Module directory: `~/southbrook-v19cr-backups/kitchen_3d_configurator_2026-07-01_pre-recD/` (312K)
- Git tag: `pre-rec-d-2026-07-01` on commit `f44eff9`

---

## 0 · One-paragraph brief

Unify the two configurator surfaces (`southbrook.kitchen.design` + `/kitchen-planner`'s `product.config.session`) into a single 3D-first canvas with role-shaped chrome per persona (Customer / Dealer / Sales Rep / Manager). The 3D configurator becomes the primary Odoo app tile ("main upfront visual surface" per the user's ask). Data model: `sale.order.line` IS the slot (already has `wall_id + position_from_left_mm` from `southbrook_estimating`), extended with 7 `sb_layout_*` fields; `southbrook.room` extended with 6 fields mirroring today's design-level room-behaviour settings. Zero new tables. CLAUDE.md §2.3 "there must not be two configurators" satisfied by making `product.config.session` the sole engine per the brief's explicit mandate.

## 1 · Why D beats A, B, C

| From... | What it kept | What D adds |
|---|---|---|
| **A** — unified links | One session graph; direct `sale.order.line ← config_session_id` chain | **No new model** — `sale.order.line` IS the slot; 12 fewer joins than A. |
| **C** — phased 3D-first | 3-sprint progressive migration; each sprint ships value; no cutover flag day | **Bus-notified real-time cross-persona events**; **role-shaped chrome on ONE canvas** (Customer/Dealer/Rep/Manager see different toolbars, same scene, same data) |
| **UX creativity** | — | Solid ↔ Blueline ↔ **Cutlist overlay** (third view highlights BOM contribution); shift-click multi-select + bulk edit; numeric type-to-jump (`W600<Enter>`); undo history slider with named snapshots; `[Tab]` toggles Room mode ↔ Cabinet mode; comment pins feed Approval stage; assembly presets skip empty-canvas fear |
| **Safety** | — | Reconciliation cron is one-way (design → room) for Sprint 1 — zero regression risk on `/kitchen-planner`, `/shop/<slug>`, or `/my/southbrook/order-builder` |

## 2 · Data model (final shape)

### 2.1 `sale.order.line` — extended (Sprint 1 landed)

7 new fields, all `sb_layout_*` prefixed:

| Field | Type | Purpose |
|---|---|---|
| `sb_layout_x_mm` | Float(10,2) | World X (authoritative when `wall_id` null) |
| `sb_layout_y_mm` | Float(10,2) | World Y (depth into room) |
| `sb_layout_z_mm` | Float(10,2) | World Z (vertical offset from floor) |
| `sb_layout_rotation_deg` | Float(6,2) | Y-axis rotation |
| `sb_layout_pinned` | Boolean | Flip True on first user drag |
| `sb_layout_key` | Char (indexed) | 3D scene node stable id |
| `sb_layout_origin` | Selection [configurator, manual] | Reconciliation guard |

Reused verbatim (no re-declare):
- `wall_id` (M2O `southbrook.room.wall`) — set for wall-anchored cabinets
- `position_from_left_mm` (Integer) — authoritative offset when `wall_id` set
- `is_positioned` (Boolean, computed) — includes free-floor via updated compute
- `sb_width_mm` (Float) — attribute-derived width
- `zone` / `zone_label` (Q21)
- `config_session_id` (M2O `product.config.session`) — from OCA `product_configurator_sale`

**Coordinate reconciliation rule** — `wall_id` set: `position_from_left_mm` authoritative, world coords derived at read; `wall_id` null: world coords authoritative (islands, peninsulas).

### 2.2 `southbrook.room` — extended (Sprint 1 landed)

6 new fields:

| Field | Type | Purpose |
|---|---|---|
| `sb_soffit_height_mm` | Integer (default 2134) | 84″ standard |
| `sb_wall_cab_top_alignment` | Selection | fixed_gap / to_ceiling / to_soffit |
| `sb_filler_strategy` | Selection | split / left / right / scribe |
| `x_kitchen_image` | Image (attachment) | Preview thumbnail |
| `sb_design_state` | Selection | draft / configured / quoted / ordered |
| `sb_design_ids` | One2many → design | Reverse pointer during Sprint 1-2 window |

Room continues to own: `wall_ids`, `constraint_ids` (windows/doors/appliances), `layout_shape`, `ceiling_height_mm`, `unit_preference`, `room_type`.

### 2.3 Bridge fields (Sprint 1 landed)

`southbrook.kitchen.design.room_id` → `southbrook.room` (nullable, ondelete=set null)
`southbrook.kitchen.design.line.sale_order_line_id` → `sale.order.line` (nullable, ondelete=set null)

Reconciled by `southbrook.design.reconcile` cron (every 5 min).

## 3 · UX by persona (Tier 1 / 2 / 3)

### Tier 1 · Customer at `/kitchen-planner`
- Default 3.6 × 3.0 m room + "Start with U-shape" preset chip
- Left rail: 5 verbs (Add / Move / Rotate / Delete / Measure)
- Right drawer: 4 attribute cards (Family / Width / Colour / Handle) as chips — not sliders
- Rule violation → inline banner + "Talk to a dealer" CTA
- Save button: **"Request a Price"** → draft SO + dealer bus notification

### Tier 2 · Dealer / Sales Rep
- Same canvas; `[Tab]` swaps Room mode ↔ Cabinet mode
- Right drawer: all 11 attributes with sliders (envelope min/max unlocked), rule reasons visible
- `Q/E` rotate, `G` drag, `W600<Enter>` set exact width
- Shift-click multi-select + bulk edit
- BoM preview drawer via right-side tab
- Bottom strip: multi-zone grid (Q21) with per-zone subtotals, channel badge, savings vs retail, margin %
- Save button: **"Send for Estimating"**

### Tier 3 · Manager (approval)
- Read-only canvas
- Approval sidebar replaces the right drawer: change-log diff, cost/margin, threshold flag
- Comment pins on canvas → `mail.message` per session line → feeds Approval stage
- Undo/history slider shows named snapshots
- Buttons: **Approve** / **Bounce with note** / **Reject**

### Mobile fallback (any persona)
- `<KitchenCanvas>` refuses to mount unless desktop + WebGL2
- ≤900 px: `<MobileCardStack>` (customer, 2D) or `<MobileReadOnly>` (internal, kanban + PDF preview)
- 901–1199 px: drawers become tabs, 3D on, compressed
- ≥1200 px: full three-pane

## 4 · Frontend architecture

```
<KitchenConfiguratorRoot>                     // resolves persona; owns single OWL store
 └─ <ConfiguratorFrame persona="…">
     ├─ <TopBar>                              // CustomerTopBar | DealerTopBar | ManagerTopBar
     ├─ <StageColumn>
     │   ├─ <LeftInventory>                   // authoring only
     │   ├─ <StageCanvas>
     │   │   ├─ <KitchenCanvas mode=…>        // SHARED — pure Three.js wrapper
     │   │   ├─ <CanvasHUD>                   // Q/E hint, dims, camera picker
     │   │   └─ <DropShadowLanes>             // authoring only
     │   └─ <RightConfigDrawer>               // <CustomerWizard> | <DealerAttributeEditor>
     │       │                                //   | <ManagerApprovalSidebar>
     │       ├─ <SelectionSummary>
     │       ├─ <AttributePicker>             // OCA config.session driver
     │       └─ <PriceBreakdown>              // redacted per persona
     ├─ <Toolbar>                             // gated per persona
     └─ <BottomStrip>                         // CustomerLineStrip | DealerZoneGrid | ManagerDiffView
```

**Single OWL reactive store** — no Vuex. Optimistic mutations. 2s debounced auto-save. Client-only undo/redo stack up to 50. Scene-diff updater (no full rebuild). Non-reactive `dragState` ref → imperative `scene.updateSlot(id, x)` during drag; reactive mutate on drag-commit only.

**Bus subscription** `sale.order,<orderId>` — server posts `{payload_version: N}` on any write. Manager approves → customer view refreshes in <1s. Portal-anon falls back to 15s polling.

## 5 · RPC consolidation: 31 → 6

| Route | Verb | Replaces |
|---|---|---|
| `/configurator/state` | POST | `/products`, `/layout`, `/kitchen-planner/state`, `/order/<id>`, `/order/<id>/kitchen-3d`, `/load_design_lines`, `/user_defaults` |
| `/configurator/mutate` | POST | `/save`, `/save_position`, `/delete_line`, `/line/*/*`, `/order/*/add-line`, `/lines/bulk-*`, `/session/*/set-value` |
| `/configurator/session` | POST | `/session/create`, `/session/*/cancel`, `/line/*/attributes` |
| `/configurator/pricing` | POST | Hypothetical partner/pricelist re-price |
| `/configurator/transition` | POST | `/order/*/action`, `/preflight-confirm`, `/request-production-approval` |
| `/configurator/room` | POST | 5 room_api.py routes |

## 6 · Migration path

### Sprint 1 · Bridge (SHIPPED, 2026-07-01)
✅ 7 fields on `sale.order.line`, 6 fields on `southbrook.room`, bridge M2Os on design(.line)
✅ Reconciliation cron `southbrook.design.reconcile` fires every 5 min
✅ Per-design SAVEPOINT so failures don't poison batch
✅ Graceful skip for partner-less designs (all 18 current prod designs)
✅ Divergence log-only, no auto-heal — build confidence for Sprint 2

**What ships to users**: nothing visible. Backend infrastructure only. Existing 18 designs stay authoring source. Once any user assigns a partner_id to a design (via the existing kanban), the cron picks it up on the next 5-min tick and creates the mirror.

### Sprint 2 · KitchenCanvas + persona chrome (planned, ~2 weeks)
1. Extract shared `<KitchenCanvas>` OWL component from `kitchen_configurator.js` (2400 LoC internal) + `kitchen_viewport.esm.js` (1200 LoC portal)
2. `<KitchenConfiguratorRoot>` + persona-shaped chrome (`<ConfiguratorFrame>`, `<TopBar>`, `<RightConfigDrawer>`, `<BottomStrip>`)
3. `/kitchen-planner` becomes thin controller mounting `<KitchenConfiguratorRoot persona="customer">`
4. `/my/southbrook/order-builder` + backend Order Builder gain "Room Layout" tab
5. Reconciliation cron reverses direction (room → design read-mirror; design becomes read-only)
6. Solid ↔ Blueline ↔ **Cutlist** view toggle
7. Numeric type-to-jump (`W600<Enter>`), shift-click multi-select, `[Tab]` Room/Cabinet mode, undo history slider

### Sprint 3 · Retirement + approval workflow + bus events (planned, ~2 weeks)
1. Deprecate `southbrook.kitchen.design(.line)` — mark readonly, 30-day grace banner
2. Rewrite `action_create_quotation` as `/configurator/transition`
3. Bus notifications wired end-to-end (Customer → Dealer → Manager events)
4. Comment pins on canvas → `mail.message` per session, feed Approval stage change-log
5. Threshold-gated approval — `southbrook.config.approval_threshold` blocks `action_confirm` above limit
6. Drop `southbrook.kitchen.design` + `.line` tables after grace window
7. Rebrand `southbrook_kitchen_3d_configurator` as the front-door module

## 7 · JTBD gaps from the 2026-06-29 boutique-mfg / ERP-benchmark research

The Rec D scope covers **unification** but the JTBD study identified critical adjacent gaps to schedule separately:

1. **PTAV `price_extra` backfill** — customer sees $0 prices until real data lands (RM roadmap §92, §251)
2. **Sales-rep override audit trail** — `southbrook.config.override` table (highest-signal CPQ data no competitor collects)
3. **As-built snapshot at SO confirm** — warranty contract (SAP charges 6 figures for iPPE equivalent) (RM §90, §264)
4. **Tablet operator UI** — the "load-bearing tentpole" of Phase 2 (RM §74, §444)
5. **Adjacency-aware placement validation** — server-side, or two-cabinet overlap silently ships
6. **ETO escape hatch** — `is_custom_eto` boolean pegging to project.project for the 10-20% custom tail
7. **Dealer cross-tenant ACL fix** — currently controller "accepts any package the dealer can name" (RM §788) — live security hole
8. **E-signature hook** — Docusign/Vercel-side; the one BM 659 point Southbrook loses vs SAP
9. **4-eyes SoD on price master / ECO / JE** — Phase 5 P0 (RM §133); Rec D's threshold gate alone doesn't satisfy SOC-2

These are separate initiatives. Rec D unlocks the platform they run on top of.

## 8 · Rollback

- Any Sprint 1 field addition: `git checkout pre-rec-d-2026-07-01 -- addons/southbrook_kitchen_3d_configurator/ && bump version && deploy`. Fields stay in the schema (harmless orphan columns) but code stops writing to them.
- Reconciliation cron: `active=False` via UI or ir.cron write. Idempotent — turning back on picks up from watermark.
- Any Sprint 2 JS regression: `git checkout <known-good-commit> -- .../static/src/js/` per the well-worn recovery recipe from the 4.20.0 / 4.23.0 episodes.

## 9 · What survives / changes / new (final)

| Surface | Today | After Rec D |
|---|---|---|
| Kitchen 3D Configurator (backend) | Drag-drop 3D scene, own model, no attributes/rules | **Same UI + rule enforcement + channel pricing + attribute drawer + BoM preview + Q/E visual rotate**; opens on any sale.order |
| `/kitchen-planner` (customer portal) | 2D catalog SPA, 11 attributes | **3D-first**, same 3-pane; canvas is shared `<KitchenCanvas>`; Tier 1 chrome |
| `/shop/<slug>` (public product) | OCA + `southbrook_configurator_ux` chips | **Unchanged** |
| `/my/southbrook/order-builder` | Multi-zone grid | **Same grid + new "Room Layout" tab** |
| Sales → Order Builder (backend) | Multi-zone grid | **Same grid + new "Room Layout" tab** |
| `southbrook.kitchen.design` | 18 rows, own schema | Deprecated Sprint 3; 30-day grace; dropped after |
| `product.config.session` | 95 rows, load-bearing | **Unchanged** — remains sole engine per CLAUDE.md §2.3 |
| `sale.order.line` + `southbrook.room` | Existing | **+7 + 6 fields — no new tables** |
| Real-time cross-persona bus events | None | New (Sprint 3) |

---

**Sprint 1 status: SHIPPED live at 19.0.5.0.2. Commit `3aab52e` on `origin/main`.**
