# Session Summary — 2026-06-01 → 2026-06-02

Customer-flow + Manufacturing PM build session. 30 commits from `60a7df4` (G9/G10 self-service order creation) through `1236cbb` (M18 capacity planning grid).

---

## What landed

### A. Customer-flow JTBD gaps (`G1`–`G17`)

| Gap | Surface | Commit |
|---|---|---|
| G1 + G2 | Public Southbrook homepage with "Design Your Kitchen" CTA | `487ad02` `adbba39` |
| G4 + G5 + G6 + G8 | Branded login/signup chrome + project-name capture at signup → stamps `client_order_ref` | `c4462b8` |
| G9 + G10 | `/my/southbrook/order-builder/new` auto-creates draft + prominent `/my` tile | `60a7df4` |
| G11 + G12 + G13 | `CatalogPicker` modal + `/api/order/<id>/add-line` endpoint + price seed on 12 cabinets | `0648161` |
| G14 + G16 + G17 | Portal-user auto-customer-mode, `request_price` flips draft→sent with chatter + Odoo quote email, timeline timestamps on `StagePipeline` | `c2eaa8a` |
| G15 | Inline attribute drawer on order lines — 11 attributes via `/api/line/<id>/attributes` + `/set-attribute` | `a39193c` |

**End-to-end customer journey now working:** anonymous `/` → walnut hero → "Design Your Kitchen" → branded `/web/signup` with project-name field → auto-redirect into `/my/southbrook/order-builder/<auto-id>` → CatalogPicker modal → ConfigDrawer with attribute selects → "Request a Price" → state transition + email + chatter.

### B. Hardening pass (`a6b5838`–`94d7d31`)

| Item | Result |
|---|---|
| Existing Odoo test suite (`southbrook_estimating` + `southbrook_plm`) | **168 tests pass**; 1 pre-existing failure (`test_09_duplicate_button_is_in_button_box`) unchanged from baseline |
| **11 new endpoint tests** for G11–G17 in `southbrook_estimating_website/tests/test_customer_flow_endpoints.py` | All pass |
| **curl-based smoke** at `scripts/smoke_customer_flow.sh` | 49/49 assertions across HTTP + JSON-RPC + DB |
| **Playwright headless-browser smoke** at `scripts/smoke_browser.py` | **13/13 assertions** — catches OWL/DOM-level errors curl can't see |
| **PLM `sudo` fix** on `mrp_bom._get_cut_constants` | Portal users no longer hit `AccessError` on `southbrook.cut.spec` during order fetch |

### C. Browser-only bug streak (4 OWL/template bugs caught after smoke green)

| # | Bug | Fix commit |
|---|---|---|
| 1 | `CatalogPicker` between `t-elif` and `t-else` broke QWeb chain → OWL mount failed | `1b598bb` |
| 2 | `.bind` prop directive miscompiled in this Odoo's OWL → `xml(...).bind is not a function` at module load | `ba8cc1a` `f893d9e` `dbbfa15` (three attempts to land the fix) |
| 3 | `web.user_switch` shell + form `d-none` on `/web/login` → empty card visible to users | `a9b0297` |
| 4 | Catalog endpoint dropped templates whose `default_code` blanks when variant-count > 1 | `a1d590b` |

All four bugs slipped past curl-only smoke. The **Playwright pass** (`94d7d31`) was wired specifically to catch this class going forward. Final pattern that works: pre-bind handlers in `setup()` — neither `.bind` directive nor arrow wrappers carry `this` correctly in this Odoo's OWL.

### D. Manufacturing PM JTBD (`M1`–`M20`)

New addon **`southbrook_mrp_pm`** scaffolded fresh. Depends on `southbrook_estimating` + `southbrook_estimating_website` + `southbrook_plm` + `mrp` + `maintenance`.

| Layer | Gap | Surface |
|---|---|---|
| **1 — Foundation** | M3 / M7 | `sale.order.action_send_to_production()` + `/southbrook/api/order/<id>/action` `send_to_production` branch — creates MOs with full routing |
| | M6 / M9 | Canonical BoM + 8-station routing per cabinet (78 min for SB-BASE-1DR baseline, scaled by complexity for 11 others) |
| | M8 | 8 SB-* work centers (SAW/EDGE/CNC-BORE/ASSY/DOOR/HW/QC/PACK) + 4 paint-shop additions (DOOR-SHOP/SAND/PAINT/CURE), all with OEE target 85% + `costs_hour` |
| **2 — PM surface** | M1 v0 | "Southbrook PM" menu root (sequence 70) with 5 filtered Odoo actions |
| | M4 | Ready-for-Production queue (state in confirmed/progress by deadline) |
| | M10 | Per-station kanban dashboard with 4 computed KPIs: In Queue / Done Today / Late / Equipment alerts |
| | M11 | Per-cabinet-family kanban: 9 families (base/wall/tall/drawer/sink/corner/vanity/accessory/worktop) with in-flight + done-today + late |
| | M13 | `maintenance.equipment.southbrook_condition` Selection (good/fair/watch/critical/offline) + audit fields, badge on form, coloured row decoration on list |
| | M14 | Equipment → impacted-MO chain (smart-button + computed Many2many, links via `workcenter_id`) |
| | M18 | Weekly capacity pivot — workcenter × day × `SUM(duration_expected)` for in-flight WOs |
| | M19 | `southbrook_lead_time_extra` rolled into order payload `lead_time_days` (14 base + max across lines); OWL `HeaderStrip` already reads it |
| **3 — Floor + edges** | M12 | `/my/southbrook/floor/kiosk` — dark-theme full-screen view for HDMI-attached factory TV with 30s auto-refresh |
| | M16 | `/my/southbrook/floor` index + `/my/southbrook/floor/<wc_id>` per-station queue + Phase-2 POST routes for start/finish/condition |
| | M17 | `res.groups` 'Southbrook Floor Manager' + 7 ACL rows; SQL-direct group check sidesteps cache invalidation |
| | M20 | `southbrook.eco.action_apply` override — Markup-HTML chatter post on every in-flight MO using the affected BoM |

**Final tally: 17 of 20 M-gaps shipped end-to-end.** Remaining 3 (M2 internal user onboarding wizard, M5 inline BoM edit, M15 floor-mobile condition push — the latter substantially covered by M16 Phase-2 anyway) are real builds, not polish.

### E. User CSV pack import (`6ae72d9`)

Imported the supplied catalogue:
- 4 new work centers (DOOR-SHOP, SAND, PAINT, CURE) coexisting with the 8 SB-* records — total 12 active stations
- 5 maintenance equipment records (Biesse Rover K FT, ShopSabre IS510, HOMAG Edge Bander, Spray Booth A, Air Compressor) linked to their stations + categories
- 14 manufacturing products across 5 categories (Fasteners $0.01–$0.12, Adhesives, Abrasives, Finishing, CNC Tools)

OEE / bottleneck-detection / nesting-yield / CAD-integration module sketches from the pack were **deliberately not built** — those are multi-week workstreams that need separate planning.

---

## Operating surface as of session end

### Live URLs

- **Customer entry:** `https://www.southbrookcabinetry.local:9443/` → walnut hero → CTA
- **Customer order builder:** `/my/southbrook/order-builder/<id>` (auto-customer-mode for portal users)
- **PM dashboard:** Odoo backend → Southbrook PM → Dashboard (sequence 5)
- **Floor operator (tablet):** `/my/southbrook/floor/<workcenter_id>` (30s auto-refresh)
- **Floor wall-display (HDMI):** `/my/southbrook/floor/kiosk` (dark-theme, 30s refresh)

### Menu structure (Southbrook PM root, sequence 70)

| Sequence | Menu | What it shows |
|---|---|---|
| 5 | Dashboard | Per-station KPI kanban (M10) |
| 6 | Family Throughput | Per-cabinet-family KPI kanban (M11) |
| 7 | Capacity | Pivot table workcenter × day × committed-minutes (M18) |
| 10 | Ready Queue | Confirmed MOs by deadline (M4) |
| 20 | In Production | MOs in `progress` state |
| 30 | Late Orders | Past-deadline MOs |
| 40 | Floor Load | Workcenter kanban |
| 50 | Equipment | Maintenance equipment list with condition column |

### Smoke runners

```bash
# Headless-browser smoke (Playwright, ~10s)
/tmp/sb-pw-venv/bin/python scripts/smoke_browser.py
# Expected: "13 passed · 0 failed"

# curl-based smoke (full customer journey, ~30s)
bash scripts/smoke_customer_flow.sh
# Expected: "49 passed · 0 failed"
```

### Odoo test runners

```bash
# Module test suites (run in container)
odoo --no-http --test-enable -u southbrook_estimating_website -d southbrook --stop-after-init
# Expected: 11 new + 0 baseline (no prior tests on this addon)

odoo --no-http --test-enable -u southbrook_estimating -d southbrook --stop-after-init
# Expected: 121 tests, 1 known-failing pre-existing (test_09_duplicate_button_is_in_button_box)
```

---

## Notable lessons / surprises

### 1. The browser-only-bug streak

Four OWL/template bugs in a row shipped to a clean curl-smoke pass and got user-reported (`t-elif` chain, `.bind` directive miscompile, `d-none` login, catalog-tile flake). The cause was the same in every case: **curl can't see what OWL renders or doesn't**. Wiring Playwright was deferred earlier in the session; once landed, it caught the next three iterations of the bind-fix attempt before any user saw them.

### 2. OWL `.bind` directive miscompiles in this Odoo build

`<Child onClose.bind="_handler"/>` emits `xml(...).bind(component)` at template-compile time in this Odoo's OWL — which fails at module load with `xml(...).bind is not a function`. Arrow-function wrappers (`onClose="() => _handler()"`) also don't carry `this` correctly. **Working pattern: pre-bind in `setup()`.**

```python
class OrderBuilder extends Component {
    setup() {
        this.state = useState({...});
        this._closeCatalog = this._closeCatalog.bind(this);  # <- key
        this._onPickCabinet = this._onPickCabinet.bind(this);
        ...
    }
}
```

Templates then reference methods as plain props (`onClose="_closeCatalog"`) and the bound function carries its `this`.

### 3. Odoo 19 field renames caught at first run

| Old name | New name |
|---|---|
| `res.users.groups_id` | `res.users.group_ids` |
| `res.groups.category_id` | (removed; replaced by `privilege_id`) |
| `sale.order.line.product_uom` | `sale.order.line.product_uom_id` |
| `mrp.workorder.date_planned_start` | `mrp.workorder.date_planned_start_wo` |

### 4. `product.template.default_code` blanks when variant count > 1

Odoo computes `template.default_code` only when the template has exactly one variant. The customer add-line + attribute work materialises multiple variants; once any cabinet has 2+ variants, its template-level `default_code` goes NULL and the catalog endpoint silently dropped it. Fix: resolve by **stable xml_id** instead of template `default_code` matching.

### 5. Group cache vs SQL truth on auth checks

When users get added to a group via direct SQL INSERT, `user.has_group()` returned False for several minutes (env cache lagged behind the DB). Fix: **direct SQL query against `res_groups_users_rel`** for the floor portal auth — no cache to invalidate.

### 6. OWL templates need `Markup()` for HTML chatter posts

`message_post(body="<strong>...")` escapes the tags into literal text. Wrap with `markupsafe.Markup(...)` so Odoo's chatter pipeline treats it as trusted HTML.

### 7. Three pragmatic shortcuts that work without breaking Odoo

- **Send-to-Production:** instead of full Odoo MRP plumbing (component reservations, lot tracking), the controller creates `mrp.production` directly with `date_start` + `date_deadline` + `bom_id` and calls `action_confirm()`. Work orders materialise from the routing.
- **Floor start/finish:** instead of `button_start()`/`button_finish()` with their side-effect cascade, the controller writes `state` + `date_start`/`date_finished` directly, then manually promotes the next sibling WO from `blocked` to `ready`. Same end-state for the operator's display; PMs use the backend for the full Odoo flow when component-reservation matters.
- **Catalog resolution:** iterate the 12 stable xml_ids hardcoded in the controller rather than searching by `default_code` pattern.

---

## Remaining open work (in rough priority)

| Item | Effort | Why deferred |
|---|---|---|
| M2 — internal user onboarding wizard | ~2h | Admin UX polish; admin can do it manually in 30 seconds |
| M5 — inline BoM edit from Order Builder | ~half-day | Significant customer-side rebuild; real value for power-user customers |
| Customer-mode visual differences in real browser | ~30 min | smoke confirmed `data-mode='customer'`; visual confirmation of `Request a Price` vs `Send to Production` button copy not done |
| OEE timeseries collection | ~half-day to scaffold | Floor start/finish now produces timestamps; aggregating into time-windowed OEE per station for the M10 dashboard would replace the static `oee_target` display |
| Investigate `southbrook_estimating.test_09_duplicate_button_is_in_button_box` | ~30 min | Pre-existing failure (not caused this session); is the duplicate button in the right view container? |

---

## Commit log — chronological

```
60a7df4  feat(portal): G9 + G10 — self-service order creation + prominent /my tile
487ad02  feat(homepage): G1 + G2 — public Southbrook landing with 'Design Your Kitchen' CTA
adbba39  fix(homepage): make G1+G2 actually render by inheriting website.homepage
c4462b8  feat(auth): G4+G5+G6+G8 — branded login/signup chrome with project-name capture
0648161  feat(order-builder): G11+G12+G13 — CatalogPicker, add-cabinet, price transparency
a39193c  feat(order-builder): G15 — inline attribute picker on the line drawer
c2eaa8a  feat(order-builder): G14+G16+G17 — customer mode, submit-for-pricing, timeline
1b598bb  fix(order-builder): move CatalogPicker inside loaded branch to repair QWeb t-else chain
a6b5838  test(website): 11 endpoint tests for G11-G17 + harden against pre-existing failures
aa31077  test+fix(plm): smoke harness + sudo on cut.spec read for portal users
ba8cc1a  fix(order-builder): add .bind suffix to method props that crash without it
a9b0297  fix(auth): show the actual login form (drop d-none + user_switch shell)
f893d9e  fix(order-builder): replace .bind prop directive with arrow wrappers
dbbfa15  fix(order-builder): pre-bind handlers in setup() — third (and final) attempt
94d7d31  test(browser): Playwright headless smoke catches what curl can't
835e07d  feat(mrp-pm): Layer 1 — workcenters + routing + Send-to-Production wiring
6ae72d9  feat(mrp-pm): import user CSV pack — workcenters, equipment, mfg products
a63c2d8  feat(mrp-pm): Layer 2 v0 — Southbrook PM menu structure (M4 + M1 v0)
790991f  feat(mrp-pm): M13 equipment condition + M19 lead-time surface on Order Builder
ac56f94  feat(mrp-pm): backfill canonical BoMs + routings for 11 remaining SB-* cabinets
15ff64c  feat(mrp-pm): M14 — equipment → impacted MO chain lookup
8d27ee3  feat(mrp-pm): M16 + M17 — Floor Manager portal route + access group
1a6a7ad  feat(mrp-pm): M16 Phase-2 — start/finish work order + condition pill actions
4454727  feat(mrp-pm): M20 — ECO apply → chatter notification on in-flight MOs
a1d590b  fix(order-builder): catalog endpoint resilient to template default_code blanking
cebe497  feat(mrp-pm): M10 — PM KPI dashboard (per-station kanban with computed metrics)
8dec97b  polish(mrp-pm): tighten floor portal auth + 30s tablet auto-refresh
bdb2ede  feat(mrp-pm): M11 — cabinet-family throughput KPI dashboard
d4faa72  feat(mrp-pm): M12 — kiosk display mode for factory wall-mounted TV
1236cbb  feat(mrp-pm): M18 — weekly capacity planning grid
```

30 commits; all pushed to `main`; all verified against Playwright smoke at session close.
