# Southbrook Kitchen Module — End-to-End Audit
**Date:** 2026-07-01 · **Scope:** `southbrook_kitchen_3d_configurator` and its integration surface (`southbrook_estimating`, `southbrook_estimating_website`, `southbrook_kitchen_mrp`, `southbrook_mrp_kitchen_workcenters`, OCA `product_configurator` suite).
**Prod state at audit:** `southbrook_kitchen_3d_configurator` 19.0.4.20.2 live on southbrookcabinetry.space.

---

## 0 · Executive summary

The module works: install-state clean, no failed factories, no error log noise, RPC surface responds, kanban + form + client action all mount correctly (verified live during the audit). But the module is running as a **thin scratchpad** with three structural gaps that will hurt as soon as it's used for real deals:

1. **Two configurators, not one.** CLAUDE.md §2.3 explicitly forbids this. The 3D configurator (`southbrook.kitchen.design`) and the customer-facing `/kitchen-planner` (`product.config.session`) share zero data models. This is the single biggest architectural violation surfaced by the audit.
2. **Two disconnected product catalogs.** The 12 canonical templates locked in CLAUDE.md §3 (base_1dr, base_2dr, drawer_bank, sink_base, wall_1dr, wall_2dr, tall_pantry, tall_oven, corner, vanity, accessory, worktop) are defined in `southbrook_estimating/data/product_templates.xml` but **none** are tagged `southbrook_is_cabinet=True` — so the 3D configurator ignores them and only sees the 7 demo cabinets in its own file. Live DB confirms: exactly 7 saleable Southbrook cabinets.
3. **No design → SO handoff in production.** Live DB: 18 designs exist, all `state=configured`, all with `partner_id=NULL`, and **zero** have ever been converted to a sale.order. The `action_create_quotation` code path is wired but has never fired in prod. The configurator is being used as a scratchpad and stops there.

Also: security ACL is a single row granting full CRUD to every internal user, and a `sudo()` call in `_browse_partner` lets any authenticated user leak partner data (name, channel, tradesperson tier) for arbitrary partner IDs.

Corrections applied inline this session are in §5. Everything else is a specific remediation in §6.

---

## 1 · Live production state (2026-07-01)

Queried against the running southbrook DB via the tunnel:

| Signal | Value |
|---|---|
| Modules — `southbrook_*` installed | 36 (only `southbrook_plm_productgraph` uninstalled) |
| `southbrook_kitchen_3d_configurator.latest_version` | `19.0.4.20.2` (after this session's fixes) |
| `southbrook.kitchen.design` records | **18** |
| Designs with `partner_id IS NULL` | **18 / 18** |
| Designs with `state='configured'` | **18 / 18** |
| Designs with `sale_order_id IS NOT NULL` | **0** |
| `southbrook.kitchen.design.line` records | 96 (avg 5.3/design) |
| Lines with `pinned=TRUE` | 0 (v20 field, unused) |
| Lines with `rotation_deg > 0` | 0 (same) |
| Line type mix | `base:34, wall:30, filler:30, tall:2` |
| Products with `southbrook_is_cabinet=TRUE` | **7** (`base:3, wall:2, filler:1, tall:1`) |
| Sale orders with `origin ILIKE '%kitchen%'` | 0 |
| Error log tail (last 200 lines, filtered) | empty |

**Observations:**
- 100% partner-null designs → the "customer selection" step in the workflow has never been used.
- Zero designs promoted → the "Create Quotation" button on the form works in code but has never been clicked.
- Filler ratio 30/96 (31%) is very high; one filler SKU carries every gap in every design.
- `pinned` + `rotation_deg` fields exist post-4.20.1 but no records use them.

---

## 2 · Backend integration

### 2.1 Cross-module dependencies — OK
Manifest declares `web, product, sale_management, stock, mrp, mail, southbrook_estimating`. All required deps present.

### 2.2 Model wiring — mostly OK, two minor
- `_compute_totals` (models/kitchen_design.py:140) declares `@api.depends("cabinet_line_ids.quantity", ".price_unit", ".cabinet_type", "room_width_in")` but computes `remainder_in` from a live `_find_cabinet_product("base")` search. If the base product changes, `remainder_in` goes stale until the next design write. **Minor.**
- `x_kitchen_image` is a stored `fields.Image` piggybacking on a pre-migrate to reclaim the pre-existing manual column. Depends on `migrations/19.0.4.19.0/pre-migrate.py` running successfully. Currently fine, but the manual→code takeover path is brittle if a fresh install skips migrations. **Cosmetic.**
- No `_sql_constraints` in this module — good (v19 ignores them silently per `[[odoo19_sql_constraints_deprecated]]`).

### 2.3 Security surface — WEAK
- **`security/ir.model.access.csv` grants full CRUD (`1,1,1,1`) to `base.group_user`** on both `southbrook.kitchen.design` and `.line`. No Southbrook Kitchen group exists. **Every internal user can read, edit, and delete every other rep's designs.** No `ir.rule` records.
- **`_browse_partner` (controllers/main.py:623) uses `res.partner.sudo().browse(pid).exists()`** — bypasses partner ACL. Any authenticated internal user can enumerate every partner in the DB by POSTing arbitrary `partner_id` values to `/products` or `/layout`. The response includes `channel`, `tradesperson_tier`, `pricelist_name`, and `partner_name` — a full pricing-tier leak.
- **`/save` writes `partner_id` freely** without verifying the caller has access to that partner. Combined with the sudo above, a user can attach any design to any partner (silent data pollution).
- **`/user_defaults` writes `ir.config_parameter.sudo()`** keyed by uid — each user can spam system params. Low risk but should live on `res.users` or a dedicated preferences model.

### 2.4 RPC surface — correctness OK
Seven json/auth=user routes: `/products, /layout, /save, /load_design_lines, /save_position, /delete_line, /user_defaults`. All properly authed. No user-controlled model/field names. Only one `search_count` and it correctly caps at `limit=1`.

### 2.5 Cross-module bridge to MRP — GAP
`southbrook_kitchen_mrp` (which handles cutlist / hardware package flow) does **not** list `southbrook_kitchen_3d_configurator` in its `depends`, and vice versa. The design → cutlist bridge is missing — designs quote via `sale.order` but the `sb.production.package` records are never populated from a design. Integration gap, not a runtime bug.

### 2.6 Deprecated / removed v19 patterns — none found
No `numbercall`/`doall` on any cron. No `res.groups.category_id` refs. No `<group string=` inside `<search>`. No `column_invisible="parent.*"`. Clean.

---

## 3 · Frontend surface

### 3.1 Menu structure & action wiring — OK
Three menus, three actions, all resolve. Confirmed by live DB: root menu id 962 ("Southbrook Kitchen") → children Kitchen Designs / 3D Configurator / Cabinet Products, each terminates at a working action.

### 3.2 OWL client action registration — OK
`registry.category("actions").add("southbrook_kitchen_configurator", ...)` at `static/src/js/kitchen_configurator.js:2360`. Single registration. Matches the tag in `views/kitchen_configurator_views.xml:7` and `models/kitchen_design.py:181`.

### 3.3 XML templates — OK
Kanban card template well-formed (`t-name="card"`, no word operators). Configurator component uses inline `xml\`...\`` template — no external xmlid mismatch risk. **No OWL tokenizer traps** (`[[owl_tokenizer_constraints]]`) present in this addon.

### 3.4 JS bundle — passes `node --check`
No syntax errors.

### 3.5 v19 view traps — clean after this session's fix
- **FIXED** (this session): Kitchen Designs list view was missing `<field name="currency_id" column_invisible="1"/>` alongside the monetary `estimated_price`. Added at line 22. Prevents the console warning + potential missing-currency-symbol render.
- No `<search>` views declared, so `<group string=>` trap is n/a.
- No manual `x_*` fields in view arch (except the now-code-managed `x_kitchen_image`).
- No `context="{active_id}"` on One2many embeds.

### 3.6 Reports / QWeb — n/a
No `<report>` records in this addon.

### 3.7 UX gaps
- **FIXED** (this session): "Cabinet Products" action had no `<field name="help">` empty-state panel. Added at `views/product_template_views.xml:56` — first-time users now see instructions when the filter returns zero cabinets.
- Kitchen Design kanban `<field name="state" widget="badge"/>` renders neutral gray (no `decoration-*`). **Cosmetic.**
- SCSS uses `font-family: 'Space Mono'` throughout the configurator — monospace for a customer-facing sales tool is unusual. **Branding call.**
- The client-action menu opens the configurator standalone with no `design_id` — new users may wonder why nothing appears in Kitchen Designs until they hit Save. First-run hint would help.

---

## 4 · JTBD / workflow alignment vs CLAUDE.md

CLAUDE.md §2 locks two personas sharing one engine. Actual state:

| CLAUDE.md ask | Actual | Grade |
|---|---|---|
| §2.1 Customer /kitchen-planner one-page SPA | `southbrook_estimating_website/controllers/main.py:132` — exists as three-pane OWL SPA driving `product.config.session` | Present but on the wrong data model |
| §2.2 Sales-Rep Order Builder — multi-zone, BoM tab, validation tab, stage pipeline | Not built. `southbrook_kitchen_3d_configurator` is a single-room drag-drop tool with none of the zone/BoM/validation UI CLAUDE.md scopes | Not implemented |
| §2.3 One engine, one data model, both personas | **Violated.** Customer uses `product.config.session`, rep uses `southbrook.kitchen.design`. Zero cross-links | **Major** |
| §3 12 locked cabinet templates | Defined in `southbrook_estimating/data/product_templates.xml` but **NOT tagged `southbrook_is_cabinet=True`** — invisible to the configurator | **Major** |
| §3 Six pricelists (retail/dealer/tradesperson/kd/bigbox/refacing) | All 6 present in `southbrook_estimating/data/pricelists.xml`, tradesperson dispatched to tier1/2/3 | OK |
| §5 Four declarative config rules (series→door, box→series, width→door, family→soft-close) | Declared in `southbrook_estimating/data/config_rules.xml` (verified separately) — but they operate on `product.config.line`, so they never fire on the 3D configurator's flow | Half-wired |
| Save-design → sale.order handoff | Wired at `models/kitchen_design.py:392-441`; **never fired in prod (0 orders)** | Present, unused |
| BOM auto-generation from a design | Missing entirely. `_check_production_ready` warns if BOM absent but never creates one | Not implemented |
| MO auto-creation on quote confirm | Missing. `action_create_quotation` stops at draft sale.order | Not implemented |
| Zone selection on lines (BASE_RUN/WALL/TALL/ISLAND/ACCESSORY/OTHER per Q21) | No zone field on `southbrook.kitchen.design.line` | Not implemented |

### 4.1 `_check_production_ready` coverage
Present checks: empty design ✓, missing customer ✓, x-axis cabinet collision ✓, missing BOM ✓, non-standard width ✓, wall-cab-over-ceiling ✓.
Missing: hinge-side mismatch, orphan filler, unrealistic dimensions (200"-wide passes), y-axis + z-axis collision (wall clashes with tall get silently through), panel end-cap adjacency (only warned, never blocked).

### 4.2 Double-discount risk in `action_create_quotation`
`models/kitchen_design.py:392-441` sets BOTH `price_unit` (from `line.price_unit`, already channel-priced) AND `pricelist_id` on the created `sale.order`. If ANY downstream code path calls `sale.order.action_update_prices()` or an onchange fires that re-runs pricelist resolution against the products, the pricelist will apply its discount AGAIN on the already-discounted price. Dealer −50% could become −75%. This risk hasn't hit prod because zero designs have been quoted — but it's a landmine.

### 4.3 Auto-save — OK
`_queueAutoSave` at `kitchen_configurator.js:1789`. 3000ms debounce. Fires on every drag / resize / edit / delete. Silent-on-error with console log. Manual save also on Cmd/Ctrl+S. Trigger fan-out is good (12+ call sites).

---

## 5 · Corrections applied this session

Deployed live at 19.0.4.20.2 on `southbrookcabinetry.space`:

1. **`views/kitchen_design_views.xml`** — added `<field name="currency_id" column_invisible="1"/>` alongside monetary `estimated_price` in the list view. Silences the v19 "monetary field without currency companion" warning.
2. **`views/product_template_views.xml`** — added a `<field name="help">` html empty-state panel to `action_southbrook_cabinet_products` explaining how to tag a product as a Southbrook cabinet. Prevents the confusing bare grid on first-time open.
3. **Reverted `static/src/js/kitchen_configurator.js`** to commit `037a2a5` (4.19.1 state). An earlier attempt at 4.20.0 introduced group-wrapping for cabinet meshes plus rotation + smart-pinning hooks; that JS broke the WebClient shell mount and left the configurator page blank. The revert restores full functionality. Backend additions (pin/rotation fields, new RPC routes) are retained; only the client-side wiring was rolled back.

Backend scaffolding for the smart-pinning UX is committed at `49eba2e` and remains live:
- `southbrook.kitchen.design.line.pinned` (Boolean, copy=True)
- `southbrook.kitchen.design.line.rotation_deg` (Float(6,2), copy=True)
- Three new controller routes: `/load_design_lines`, `/save_position`, `/delete_line`
- `save_design` now persists `pinned` + `rotation_deg` per line

The UI wiring for these is a follow-up (§6.1).

---

## 6 · Recommendations forward

Ordered by severity + effort. Each item is a specific remediation with file pointers.

### 6.1 [P0] Re-approach the smart-pinning UI safely
The failed 4.20.0 attempt group-wrapped cabinet meshes into `THREE.Group` and applied `rotation.y` on the group. The mesh math itself was correct; the failure mode was that the client action mount broke on the /odoo/action-1460 route (silent). Suspected causes:
- The `disposeNode` traverse loop may have been triggered on a mesh already detached, throwing during onWillUnmount.
- The `xml\`\`\`` inline template's `t-if="record.x_kitchen_image.raw_value"` chain (unrelated code path) might interact with an OWL cache that gets invalidated by the group refactor.
- A specific opts-spread ordering issue in `mk(..., {..., ...pg })` where a later property clobbered an earlier `parent` key.

**Recommended approach:** land the pinning + rotation UI in three separate deploys (4.21, 4.22, 4.23), each with a browser smoke test between them:
- 4.21 — pin-only, no visual rotation. Drag commits `pinned=true`, saves via `/save_position`, prevents `_recomputeLayoutFromItems` from moving pinned items. Ship + verify.
- 4.22 — visual pin indicator (small teal sphere above pinned cabinets), no mesh grouping yet.
- 4.23 — mesh group refactor + Q/E rotation + `mesh.rotation.y` from `rotation_deg`. Isolate the mesh-wrap change so any regression is scoped to one deploy.

### 6.2 [P0] Tag the 12 canonical templates as `southbrook_is_cabinet=True`
`southbrook_estimating/data/product_templates.xml` defines the 12 canonical templates but leaves the tag off. Add `<field name="southbrook_is_cabinet" eval="True"/>` to each. Companion tags: `southbrook_cabinet_type`, `southbrook_width_in`, `southbrook_height_in`, `southbrook_depth_in`. This makes the CLAUDE.md-locked catalog visible to the 3D configurator and immediately grows the inventory from 7 → 19 products. Verify no name/xmlid collision with the 7 demo cabinets before shipping — if collisions exist, drop the demo file's records in favour of the canonical.

### 6.3 [P0] Unify the two configurators (CLAUDE.md §2.3)
Two options:
- **A. Migrate the 3D configurator onto `product.config.session`.** Retire `southbrook.kitchen.design` in a data-preserving migration. Longest path, closest to CLAUDE.md's intent, biggest ROI on the OCA modules already ported.
- **B. Absorb `/kitchen-planner`'s SPA onto `southbrook.kitchen.design`.** Faster, but throws away most of the OCA `product_configurator_sale`/`_mrp` value.

Recommend A. It's a 3-week sprint. Interim: get the two models to bridge via a M2O `product.config.session_id` on `southbrook.kitchen.design.line` and a nightly reconciliation cron.

### 6.4 [P1] Fix the double-discount risk in `action_create_quotation`
`models/kitchen_design.py:409-431`. Choice:
- Set `pricelist_id` on the `sale.order` and let it derive prices — remove `price_unit` from the order_line vals. Cleanest.
- OR keep `price_unit` and pass `context={"lock_price_unit": True}` on line create, and don't set `pricelist_id`. Simpler but leaks the channel logic into `origin` string only.

Recommend the first. Also add a unit test that flips the customer and asserts prices update cleanly.

### 6.5 [P1] Lock down `_browse_partner` sudo
`controllers/main.py:614-623`. Replace with:
```python
partner = request.env["res.partner"].browse(pid).exists()
try:
    partner.check_access("read")
except AccessError:
    return request.env["res.partner"]
return partner
```
Then verify the JS gracefully handles an empty partner (falls back to retail pricelist — already does). This removes the enumeration leak.

### 6.6 [P1] Introduce a Southbrook Kitchen security group taxonomy
Current: single ACL row, everyone can do everything. Recommend three groups in `security/groups.xml`:
- `group_kitchen_designer` (create/edit own designs, no delete)
- `group_kitchen_manager` (all designs, all rights)
- `group_kitchen_readonly` (customer service, read-only)

Ship with an `ir.rule` that gates `southbrook.kitchen.design` to `create_uid = user.id OR group = manager` so reps only see their own designs by default.

### 6.7 [P2] Extend `_check_production_ready`
Add checks for:
- **Y-axis depth collision.** Bases at the same x with different `depth_in` will overlap.
- **Z-axis collision.** Wall cab clashing with tall cabinet's top.
- **Orphan filler.** A `cabinet_type="filler"` line with no adjacent base or wall in ±0.5" on either side.
- **Unrealistic dimensions.** Width > 60" on a single base is likely a data-entry typo; hard-cap at model or config-param level.
- **Panel end-cap adjacency BLOCKING (not just warning).** Server-side `_validate_end_cap_panel_placement` already logs; promote to a blocking issue in `_check_production_ready`.

### 6.8 [P2] Wire the BOM + MO auto-generation
`action_create_quotation` should optionally call `sale.order._action_confirm()` when `context={"confirm_immediately": True}` is set, and the order-lines' products should have `mrp.bom` records seeded from the design's cabinet spec (via `product_configurator_mrp`). Currently the rep has to click "Confirm" manually AND the MO won't spawn unless a BOM exists. Both need to be wired for the CLAUDE.md §2.2 flow.

### 6.9 [P2] Add zone selection on lines
CLAUDE.md Q21 zones (BASE_RUN, WALL, TALL, ISLAND, ACCESSORY, OTHER) don't exist on `southbrook.kitchen.design.line`. Add `zone = fields.Selection(...)` with `default` inferred from `cabinet_type`. This unlocks the multi-zone Order Builder view CLAUDE.md §2.2 wants.

### 6.10 [P3] Data cleanup — orphan designs
18 designs, all `partner_id=NULL`. Either assign them to a "Test Customer" partner and delete the ones that are clearly playground records, or add a database constraint that requires partner_id at `state='configured'`.

### 6.11 [P3] `southbrook_kitchen_mrp` bridge
The design → cutlist package flow (`sb.production.package`) is not wired to the configurator. Add an `action_generate_cut_package` button to the design form that calls `southbrook_kitchen_mrp` to create the cut spec directly from the design's dimensions. Requires the two addons to add each other to `depends`.

### 6.12 [P3] Deduplicate menu labels
Live DB shows multiple menus named "Southbrook Kitchen" at different parents (ids 962, 847, 841, 849). Not broken but confusing in the app selector. Rename to distinct labels ("Southbrook Kitchen Design", "Southbrook Kitchen Ops", etc.).

---

## 7 · What NOT to change

- **The RPC surface** (7 auth=user routes). Signatures are consistent, security posture correct at the route level. Don't add auth=public routes without deep review — the module doesn't need any.
- **The demo cabinet file** (`data/demo_cabinets.xml`). Once §6.2 lands and the canonical 12 are visible, the demo file can be retired in a future deploy, but until then it's the only functional cabinet catalog.
- **The `_queueAutoSave` cadence** (3000ms). Trigger points are comprehensive; the debounce is right for kitchen-design edit rates.
- **The pre-migrate at `migrations/19.0.4.19.0/pre-migrate.py`**. Removing it would break a future fresh install / migrate against a DB that still has the manual `x_kitchen_image` field row.

---

## 8 · Files modified this session

- `addons/southbrook_kitchen_3d_configurator/__manifest__.py` — version 19.0.4.19.1 → 19.0.4.20.2
- `addons/southbrook_kitchen_3d_configurator/models/kitchen_design.py` — added `pinned` + `rotation_deg` on `southbrook.kitchen.design.line`
- `addons/southbrook_kitchen_3d_configurator/controllers/main.py` — added `/load_design_lines`, `/save_position`, `/delete_line`; extended `save_design` to persist pin + rotation
- `addons/southbrook_kitchen_3d_configurator/views/kitchen_design_views.xml` — added `currency_id column_invisible="1"` companion
- `addons/southbrook_kitchen_3d_configurator/views/product_template_views.xml` — added empty-state help panel on Cabinet Products action
- `addons/southbrook_kitchen_3d_configurator/static/src/js/kitchen_configurator.js` — reverted to `037a2a5` (last known-good)

Commits: `49eba2e` (backend for smart-pinning), 4.20.2 fixes pending commit.

---

*Generated 2026-07-01 during the E2E audit + fix session.*
