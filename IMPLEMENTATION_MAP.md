# IMPLEMENTATION_MAP.md
## Orientation for the "Close the Configurator → Particle Intelligence Loop" audit (P1–P8)

> Source brief: `~/Downloads/southbrook_claude_code_prompt_close_the_loop_P1-P8.md`
> Branch: `feature/configurator-loop-p1-p8` (off `feature/premium-orchestration-only`)
> Repo root: `~/southbrook-v19cr/`
> Author note: orientation done before any P-task code, per the brief §1.

---

## 1. Configurator UX — OWL component, QWeb entry, serialization

| Item | Location | Notes |
|---|---|---|
| OWL root component | `addons/southbrook_configurator_ux/static/src/js/configurator.esm.js` → `ConfiguratorV2` (lines 101–1247) | Mounts client-side; template is inline `xml{...}` (no separate QWeb template id for the component itself) |
| QWeb entry-point template | `addons/southbrook_configurator_ux/views/configurator_template.xml` template id `southbrook_configurator_ux.product_configurator_v2_body` (line 45) | Inherits OCA `website_product_configurator.product_configurator`; mount-point `<div id="sb_cfg_v2_main_mount">` (line 90) under `#sb_cfg_v2_root` (line 58) carrying `data-product-tmpl-id` |
| Route | `/shop/<slug>` (inherited from OCA `website_product_configurator`) | Southbrook overrides the template body only |
| Config session model | OCA `product.config.session` | Southbrook does **not** introduce a custom session model |
| "Add to Quote" client handler | `static/src/js/configurator.esm.js` `onAddToQuote()` (789–841) | POSTs `{session_id, order_id?}` to `/southbrook/api/configurator/commit` |
| Commit endpoint | `controllers/main.py` → `SouthbrookConfiguratorAPI.configurator_commit` (561–774) | Materializes variant via `session.create_get_variant()`, writes `product.product.default_code` (the SKU), creates/reuses a draft `sale.order`, appends a `sale.order.line` qty=1, locks the session via `session.action_confirm()` |
| State endpoint | `controllers/main.py` `/southbrook/api/configurator/state` (147–305) | Returns attribute groups + picks + completion + price + weight + SKU JSON |
| Select endpoint | `controllers/main.py` `/southbrook/api/configurator/select` (418) | Mutates `session.value_ids` via OCA `update_config()` |
| Current section grouping | `controllers/main.py` `ATTRIBUTE_GROUPS` (126–131) | 4 named groups + a dynamic "Other" sink (261–263) |
| "Your build" summary | `configurator.esm.js` (169–197) — rendered as a completion ring + `completionText` (529–538) | Shows `"N of M options chosen"`; does **NOT** enumerate chosen options as chips today |
| Server-side SKU generator | `controllers/main.py` `_compute_sku_from_session(session)` (537–556) | Grammar today: `SB-{Width3}-{Series3}-{Finish3}` |
| Client-side SKU mirror | `configurator.esm.js` (446–458) | `SKU_ATTR_NAMES` list drives client preview; must stay in sync with server |
| Soft-Close +$15 hardcode | `models/tactical_price_seed.py` line 75 — `("Accessories", "Soft-Close"): (15.0, 0.0)` | Demo-grade price_extra; replaced by P2 |

**Attribute model used:** native Odoo `product.attribute` / `product.attribute.value` / `product.template.attribute.line` (via OCA `product.config.session`). No custom `southbrook.config.*` attribute model exists. Good — P2 and P4 stay within stock Odoo + OCA primitives.

---

## 2. Premium Orchestration — `action_confirm` hook point for P1

| Item | Location |
|---|---|
| Override | `addons/southbrook_premium_orchestration/models/sale_order.py` `SaleOrder.action_confirm()` (83–96) |
| Spine creation | `_create_kitchen_project_task()` (115–146) — creates `project.task`, writes `x_southbrook_sale_order_id` and `x_southbrook_project_task_id`, resolves project + design-quote stage, infers cabinet specs |
| MO backlink | `_backlink_orphan_mos()` (317–337) — searches `mrp.production` where `project_task_id=False` and `(sale_line_id.order_id=order OR origin=order.name)`, writes `project_task_id=task.id` |
| Order field | `x_premium_orchestration_managed` bool on `sale.order` (stamps post-spine) |
| Manifest version | `19.0.1.0.0` |
| Manifest depends | mail, sale_management, project, mrp, southbrook_estimating, southbrook_project, southbrook_project_mrp, southbrook_mrp_pm, southbrook_manufacturing_intelligence, southbrook_mrp_kitchen_tools, southbrook_mrp_kitchen_workcenters, southbrook_plm, southbrook_ai_design, southbrook_freecad_bridge |
| Existing feature flags (`ir.config_parameter`) | `southbrook_premium.default_kitchen_project_id`, `gemini.api_key`, `gemini.use_mock`, `freecad_bridge.url`, `freecad_bridge.enabled` |

The P1 hook point is **after** `_create_kitchen_project_task()` in `action_confirm` — same per-order loop, append new call. Existing error envelope ("Backfill Kitchen Task" recovery) is preserved.

### 5 crons (`data/ir_cron.xml`)

| # | Name | Schedule | Function |
|---|---|---|---|
| 1 | Recompute Project Readiness | every 30 min | `project.task._cron_recompute_readiness_all` |
| 2 | Refire MI Stage-Gate Checks | hourly | `southbrook.mi.engine.state._cron_refire_gates` |
| 3 | Backfill Order Analytics | every 6 h | `southbrook.order.analytics._cron_backfill_unscored` |
| 4 | Weekly Planning Baseline | weekly Sun 02:00 | `mrp.planning.run._cron_baseline` |
| 5 | Quality Dry-Run Nightly | daily ~03:00 | `southbrook.project.data.quality.report._cron_nightly_dry_run` |

(Plus a sixth cron in `data/eco_proposal_cron.xml` — ECO proposal, daily ~04:00.)

### Tool telemetry (relevant for P8)

| Item | Location |
|---|---|
| Model | `southbrook.tool.asset` — defined in `southbrook_mrp_kitchen_tools` (dep), **not** this addon |
| Seeded data | `data/tool_asset_seed.xml` — 30 assets across 5 groups (panel-saw blades, CNC router bits, boring bits, edge-bander heads, sanding belts) |
| `mrp.workorder.button_finish` override | `models/mrp_workorder.py` (75–86) → `_sbk_debit_tool_lifecycle()` (114–176) |
| Idempotency | `sbk_lifecycle_processed` latch (124–125, 176) prevents re-debit on re-finish |

P8 must call the *existing* `button_finish` path so the existing debit fires exactly once.

---

## 3. `sb.cutlist`, `sb.cutlist.line`, `sb.production.package`, `sb.hardware.package(.line)`

### `sb.cutlist` — `addons/southbrook_kitchen_mrp/models/sb_cutlist.py` (70–112)

| Field | Type | Notes |
|---|---|---|
| `name` | Char, required | Sequence `sb.cutlist` (create() override at 105–112) |
| `mo_id` | M2O `mrp.production` | ondelete=cascade, indexed |
| `state` | Selection [draft, exported, nested, done] | default draft, tracked |
| `line_ids` | O2M `sb.cutlist.line` (`cutlist_id`) | — |
| `line_count` | Integer, computed/stored | — |
| `nesting_result_json` | Text | JSON stash |

### `sb.cutlist.line` — same file (241–267)

Fields: `cutlist_id` (M2O parent), `sequence` (default 10), `panel_name` (Selection, 7 values), `qty` (Integer default 1), `length_mm`/`width_mm`/`thickness_mm` (Float (8,3)), `substrate` (Selection, 5 values), `grain_dir` (Selection, 3 values), `edge_banding_config` (Text JSON).

### `sb.production.package` — `addons/southbrook_kitchen_mrp/models/sb_production_package.py` (26–52)

| Field | Type | Notes |
|---|---|---|
| `cutlist_id` | M2O `sb.cutlist` ondelete=restrict | — |
| `hardware_package_id` | M2O `sb.hardware.package` ondelete=restrict | — |
| `mo_id` | M2O `mrp.production` ondelete=cascade, required, indexed | **One package per MO** — `_check_unique_mo()` (54–71) raises ValidationError on duplicate |

**No `task_id` or `sale_order_line_id` fields today.** ⇒ P1 will likely need to add a back-ref `sale_order_line_id` (M2O `sale.order.line`, indexed, nullable for legacy rows) for the idempotency key. That stays additive.

**Existing factory:** `generate_from_mo()` at line 86 — takes `(mrp.production, width_mm, height_mm, depth_mm, cabinet_family, door_count, drawer_count, soft_close)`. **No `from_order_line(order_line)` factory exists** — P1 will add it.

### `sb.hardware.package` — `models/sb_hardware_package.py` (20–64)

Fields: `name` (sequence `sb.hardware.package`), `mo_id` (M2O, required), `state` (draft/picked/delivered), `line_ids` (O2M lines), `line_count` (computed), `has_pricing_pending` (Boolean computed from line products).

### `sb.hardware.package.line` (86–114)

Fields: `package_id` (M2O parent), `sequence`, `product_id` (M2O `product.product` domain `x_hardware_category != False`), `qty`, `pricing_pending`/`hardware_category`/`brand_id` (related/stored).

### Drawer-slide products — XML data, `addons/southbrook_hardware_catalog/data/southbrook_hardware_seed.xml`

| External id | default_code | Description | Line |
|---|---|---|---|
| `hw_king_slide_k2832_21` | KS-K2832-21 | King Slide 21″ Soft-Close Undermount | ~144 |
| `hw_king_slide_3032_18` | KS-3032-18 | King Slide 18″ Ball-Bearing | ~134 |
| `hw_blum_movento_450` | BLM-MOV-450 | Blum MOVENTO 450 mm | ~101 |
| `hw_hettich_actro_500` | HET-ACTRO-500 | Hettich Actro 5D 500 mm | ~154 |
| `tmpl_marathon_pr_602728` | PR-602728 | Salice Progressa+ Undermount | `data/marathon_browser20_seed.xml` ~1890 |

These are `product.product` (or `product.template` for PR-602728) — **stable xml_ids** to bind to in P2 without hardcoding integer ids.

---

## 4. MI rule implementation — `Missing cutlist` and `CAD not complete`

| Item | Location |
|---|---|
| Engine (AbstractModel) | `addons/southbrook_manufacturing_intelligence/models/mi_engine.py` `southbrook.mi.engine` (line 8) |
| Check (transactional model) | `models/mi_check.py` `southbrook.mi.check` (8–61) — fields: `name`, `severity`(blocker/warning/info), `category`(cut/production/assembly/install/cad/hardware), `message`, `recommendation`, `production_id`, `production_package_id`, `active`, `severity_rank`(stored compute) |
| `Missing cutlist` detection | `mi_engine.py` `_recompute_production()` (312–325): `cutlist = self._production_cutlist(production); if not cutlist: self._create_check({...severity:blocker, category:cut...})` |
| `_production_cutlist()` helper | (190–192): searches `sb.production.package` linked to MO, returns `package.cutlist_id` |
| `CAD not complete` detection | Same method (342–352): `if "x_cad_status" in production._fields and production.x_cad_status != "done": _create_check(...severity:warning, category:cad...)` |
| Entry points | `mrp.production.action_recompute_manufacturing_intelligence()` (per-record) and `sb.production.package.action_recompute_manufacturing_intelligence()` |
| Sheet-size flags | `ir.config_parameter` `southbrook_mi.sheet_width_mm` (2440), `southbrook_mi.sheet_height_mm` (1220) |
| Manifest | version `19.0.1.1.0`, depends mrp + southbrook_estimating + southbrook_mrp_pm + southbrook_kitchen_mrp + southbrook_dealer_portal + southbrook_freecad_bridge |

P3 will hook **`_recompute_production()`** right before the `Missing cutlist` create, calling the P1 service if the source order line's config is complete.

---

## 5. Configurator attribute model — confirms P2/P4 substrate

Attributes are **stock Odoo + OCA**:
- `product.attribute` records (the 11+ canonical attributes Width, Box Material, Drawer Construction, Door Style, Wood Species, Frame Style, Door Overlay, Pull Finish, Door Edge Profile, Lighting, Interior Storage, Family, Accessories, …).
- `product.attribute.value` records per option.
- `product.template.attribute.line` couples a template to a subset of attribute values with optional `price_extra`.
- `product.config.session` (OCA) is the in-flight basket; `value_ids` (M2M `product.attribute.value`) is the picked set.

⇒ P2 ("Drawer Slide" attribute) and P4 (re-shard sections) are both **data + presentation** changes; no schema work required on the configurator side.

---

## 6. Discrepancies against the brief — surfaced per §1's "STOP and surface" rule

The brief stated several facts about the codebase; orientation found these **mismatches**. None blocks P1–P8 but each shapes the implementation. Documented here, then proceeded with the noted interpretation.

| # | Brief assertion | Actual | Resolution |
|---|---|---|---|
| D1 | "models `southbrook.mi.engine`, `southbrook.mi.engine.state`, `southbrook.mi.check`" | Only `southbrook.mi.engine` (AbstractModel) and `southbrook.mi.check` exist. There is **no** `southbrook.mi.engine.state` Python model — but a `_cron_refire_gates` cron references it (likely a model declared in a sibling addon, or stale data). | P3 hooks `southbrook.mi.engine._recompute_production` (the real detection site). No `engine.state` work needed. Cron mismatch is **out of scope** for P3 and called out here. |
| D2 | "A reference BoM `Base-Cab-3DRW-v1.0` already exists (17 component lines + 8 operations)" | No XML data record by that name in `southbrook_kitchen_mrp` or `southbrook_hardware_catalog`. Likely a live demo record (or planned). | P1 will resolve a BoM by `product_tmpl_id` + name match if present, else **skip BoM-binding** (cutlist still emits). P2's BoM mutation gracefully no-ops if no BoM resolves. |
| D3 | "Drawer Slide products … = `product.product` id **458** / id **457**" | DB-runtime ids — not stable across environments. Stable xml_ids are `hardware_hw_king_slide_k2832_21` etc. | P2 binds via **xml_id ref()** (`self.env.ref('southbrook_hardware_catalog.hw_king_slide_k2832_21')`), never by integer id. The acceptance criterion's "product 458" is interpreted as "the King Slide K2832 21" record". |
| D4 | "`x_southbrook_material_species` / `_hardware_specs` / `_unit_count` … and belong on the BoM — triple entry" — implied as living in `southbrook_project_mrp` | They are declared in `southbrook_project/models/project_task.py` (52–71) as proper Python fields, then surfaced in views by both `southbrook_project` and `southbrook_project_mrp`. | P7 implements `compute=`/`related=` **in `southbrook_project`** (where the field lives) and bumps `southbrook_project` to depend on the production-package model. `southbrook_project_mrp` is the dep gateway that wires the override boolean's UI. |
| D5 | "five `sale.order.action_confirm` override" implied to handle MO backlink directly | Backlink happens via `_backlink_orphan_mos()` called from `_create_kitchen_project_task()`; itself called from `action_confirm`. | P1's call site is the same `action_confirm` loop, append `_create_cutlist_and_package_from_order(order)` after `_create_kitchen_project_task()` (matches brief intent). |
| D6 | "`engine.run()`" entry point implied | No `run()` method; the two entry points are `action_recompute_manufacturing_intelligence` on `mrp.production` and on `sb.production.package` | P3 hooks `_recompute_production` (the inner workhorse); both action_recompute wrappers transit through it. |

---

## 7. Sequenced commit plan — per §10 ship order

1. **P1** — `southbrook_kitchen_mrp` adds `_southbrook_build_production_package_from_order_line` service + `sale_order_line_id` back-ref on `sb.production.package`; `southbrook_premium_orchestration` calls it from `action_confirm`; flag `southbrook_premium_orchestration.auto_emit_cutlist`. Tests: TransactionCase asserts 1 package, ≥10 cutlist lines, idempotency, MI cutlist blocker absent.
2. **P2** — `southbrook_configurator_ux` adds "Drawer Slide" `product.attribute` data record + 5 values bound to hardware xml_ids; price/weight live recompute via existing `price_extra`; suppress Soft-Close +$15 when a slide is chosen; BoM resolver binds chosen slide at qty=drawer_count. Tests: resolved BoM contains King Slide K2832 21 ×3 when configured.
3. **P4** — `southbrook_configurator_ux` `ATTRIBUTE_GROUPS` regrouped (Construction / Materials & Finish / Add-ons; Family moves to Size & Layout). Pure presentation; regression test asserts sample build still resolves to $680 / 6.5 kg / SB-… at 18/18.
4. **P6** — `southbrook_configurator_ux` summary panel renders all chips by group + names the specific missing attributes; "Add to Quote" disabled until required satisfied.
5. **P3** — `southbrook_manufacturing_intelligence` `_recompute_production` calls P1 service before firing Missing cutlist blocker (config-complete path); ambiguous configs (e.g. Door Style="Custom (Signature)") still produce blocker; flag `southbrook_manufacturing_intelligence.auto_remediate_cutlist`. Never touches CAD gate.
6. **P5** — extend `_compute_sku_from_session` + client mirror with drawer_count + drawer_construction + slide tokens; backward-compat prefix; 0-collision matrix unit test.
7. **P7** — `x_southbrook_material_species/_hardware_specs/_unit_count` become computed/related from sale order config / production package; explicit override boolean for manual rows; views/reports stay intact.
8. **P8** — new addon `southbrook_floor_traveler` (depends premium_orchestration + mrp_pm + a Python `qrcode` lib already pulled in via Odoo): QWeb PDF traveler per `sb.production.package` with QR encoding the package id; scan action calls existing `mrp.workorder.button_finish`; MI dashboard shows scan timestamps.

Each P-task ships as one commit `feat(<module>): Pn — <summary>` with: code + tests + flag (where applicable) + README note + a clean `odoo -u <module>` upgrade path.

---

## 8. Cross-cutting commitments (per §10)

- **Tests:** every P-task ships `TransactionCase`-only (transactional rollback). Combined golden-path test asserts P1+P2+P3+P5 acceptance end-to-end with all flags ON.
- **Flags default OFF** ⇒ baseline behavior is byte-identical until enabled per environment. Per-module README + `docs/FEATURE_FLAGS.md` index.
- **No deletions**, no widened permissions, no live customer records, no destructive migrations.
- **Rollback path** (stated in each PR description): turn the flag off, or `git revert` the per-task commit.

— end orientation —
