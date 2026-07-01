# End-to-End Audit — `southbrook_kitchen_3d_configurator` (Odoo 19 CE)

**Date:** 2026-07-01
**Auditor:** Claude Opus 4.7 (co-development session with John)
**Live probe:** `https://southbrookcabinetry.space/odoo/action-1030` → HTTP 200 (behind login)
**Module:** `southbrook_kitchen_3d_configurator @ 19.0.5.0.0`
**Local harness:** `sami-odoo` container against `southbrook` DB
**Baseline log:** `/tmp/k3d-baseline.log`
**Verify log:** `/tmp/k3d-run-3.log` — **0 fail / 0 error / 6 tests**

## 1 · TL;DR

**Verdict — code health:** GOOD. v19 trap surface is empty: no `_sql_constraints`, no `groups_id`, no `res.groups.category_id`, no `column_invisible="parent.*"`, no OWL word operators, no `useService("rpc")`, no bare-dict `doAction`. Uses vendored r160 Three.js via `window.THREE` (not bare-specifier import). Three.js scene lifecycle (dispose, event listeners, orbit controls) is correctly cleaned up on unmount.

**Verdict — test health:** **baseline was 0 tests** — no `tests/` directory shipped. After this session: 6 regression tests / 0 fail / 0 error. Still a coverage void on 6 of 7 controller routes; the one covered route (`/save`) had a real security bug (§3.A) that this audit surfaced + fixed + regression-pinned.

**Verdict — brief compliance (CLAUDE.md §3):** ✅ vendored r160 Three.js, ✅ `_resolve_channel_pricelist` integration with `southbrook_estimating`, ✅ 3-tier group taxonomy with implied chain, ✅ `<chatter/>` widget on the design form. Deferred: KTX2/Basis textures, MeshBVH picking (Phase-3+ items already flagged in the estimating-website audit as the shared 3D pipeline debt).

**Verdict — integration:** clean. Manifest `depends` list matches runtime consumption (with two dead-code `hasattr()` guards on now-hard deps — documented). Zero reverse-dependents. One MEDIUM finding on `data/canonical_catalog_tag.xml` (§4.C) that the prior estimating audit flagged — still valid, documented as follow-up not landed this session.

## 2 · What is `/odoo/action-1030`?

Numeric backend action ID resolving (most likely) to
`southbrook_kitchen_3d_configurator.action_sbk_kitchen_designs` — the kanban+list+form on `southbrook.kitchen.design`, mounted from `views/kitchen_design_views.xml:228-243`. Behind login (HTTP 200 with `main-object="ir.ui.view(189,)"` = Trade Portal login page).

Confirm at runtime:

```python
env["ir.actions.actions"].browse(1030).xml_id
# expected: 'southbrook_kitchen_3d_configurator.action_sbk_kitchen_designs'
```

## 3 · Real bugs found — 1 P1 SECURITY fix landed

### A · `/save_design` bypassed the `/products` catalog contract (P1 SECURITY)

`controllers/main.py:347` (pre-fix):

```python
product = request.env["product.product"].browse(int(item["product_id"]))
```

The `/products` route at `main.py:31-34` filters catalog to `southbrook_is_cabinet=True AND sale_ok=True`. But `/save_design` browsed whatever `product_id` the client shipped, with **no ACL check, no domain filter, no `.exists()` guard**. An authed user could persist configurator lines pointing at:

- Archived products (`sale_ok=False`)
- Non-cabinet products (`southbrook_is_cabinet=False`)
- Products they can't read via `ir.rule`
- Nonexistent IDs (silent recordset returned by `browse()` → `product.lst_price` etc. still work on empty recordsets due to `False` fallbacks, but the persisted line ends up with `product_id=<bad-id>`)

Once persisted, `/load_design_lines` (`main.py:411-446`) mirrors the line back to the client — implicit read-through of the catalog contract.

**Fix landed (main.py:345-394):**

```python
Product = request.env["product.product"]
incoming_keys = set()
for seq, item in enumerate(items, start=1):
    try:
        pid = int(item["product_id"])
    except (KeyError, TypeError, ValueError):
        _logger.warning("save_design: item[%d] missing/invalid product_id ...")
        continue
    product = Product.search([
        ("id", "=", pid),
        ("product_tmpl_id.southbrook_is_cabinet", "=", True),
        ("sale_ok", "=", True),
    ], limit=1)
    if not product:
        _logger.warning(
            "save_design: rejected product_id=%d on design=%s "
            "(fails /products catalog contract ...)",
            pid, design.id,
        )
        continue
    ...
```

Using `search()` instead of `browse()` implicitly enforces `ir.rule` + the domain filter in one shot. Reject-and-skip semantics keep the save succeeding for legitimate lines instead of 500'ing the whole payload.

Matches the ACL discipline already used by:
- `/load_design_lines` — `design.check_access("read")` at `:420`
- `/save_position` — `design.check_access("write")` at `:459`
- `/delete_line` — `design.check_access("write")` at `:492`
- `_browse_partner` — `partner.check_access("read")` at `:642`

### B · 6 regression tests, pinned in a NEW `tests/` directory

Baseline had zero tests. Added `tests/__init__.py` + `tests/test_save_design_acl.py` with `TestSaveDesignAcl`:

| Test | Proves |
|---|---|
| `test_01_good_cabinet_is_persisted` | Baseline — a catalog-conforming cabinet passes through |
| `test_02_non_cabinet_product_is_rejected` | Rule 1 of the catalog contract: `southbrook_is_cabinet=True` |
| `test_03_archived_cabinet_is_rejected` | Rule 2 of the catalog contract: `sale_ok=True` |
| `test_04_mixed_payload_keeps_good_drops_bad` | Per-line reject — mixed payload persists the good and drops the bad |
| `test_05_nonexistent_product_id_is_dropped_silently` | Client garbage id: skip line, don't blow up |
| `test_06_missing_product_id_key_does_not_crash` | Malformed payload (`KeyError`, `TypeError`, `ValueError`) skips gracefully |

Same `stubbed_request` pattern as the sibling `southbrook_estimating_website` audit.

## 4 · HIGH-value findings NOT fixed in this session

### 4.A · `data/canonical_catalog_tag.xml` `noupdate="0"` clobbers dimensions (MEDIUM — carried from estimating audit §6.4)

File is one `<odoo noupdate="0">` block wrapping 11 template writes. Each `-u` re-applies:
- `southbrook_is_cabinet=True` ✓ (structural invariant, correct to re-apply)
- `southbrook_cabinet_type=<slug>` ✓ (structural invariant, correct)
- `sale_ok=True` ⚠ (invariant only if we're sure the estimating side never sets it False)
- **`southbrook_width_in / height_in / depth_in`** ✗ (customer/rep-editable dims that get clobbered)

The 11 xmlids touched (`southbrook_estimating.wall_1dr / wall_2dr / base_1dr / base_2dr / drawer_bank / sink_base / vanity / tall_pantry / tall_oven / corner / accessory`) all belong to the estimating addon. Any Studio edit or /save flow that changes template dims gets reverted on the next `-u southbrook_kitchen_3d_configurator`.

**Not fixed this session** because the surgical fix (split into two files: `_tags.xml` noupdate=0 + `_dimensions.xml` noupdate=1) touches file structure that John's parallel 4.22.x/5.0.0 workstream is also iterating on. Documented as follow-up. Recommend splitting when the WIP-bridge lands.

### 4.B · Panel-placement algorithm duplicated 3× (MEDIUM)

Same rule ("end-cap panels never attach to room walls") lives in:
1. `controllers/main.py:504 _validate_end_cap_panel_placement` — WARN, log-only
2. `static/src/js/kitchen_configurator.js:789 _validateEndCapPlacement` — WARN, push to state
3. `models/kitchen_design.py:437-463 _check_production_ready` — BLOCKING (in `action_create_quotation`)

The model layer's comment (`:437-439`) explicitly acknowledges the follow-up: "extract the pure algorithm to an @api.model classmethod so client + server share one implementation." Not fixed this session; low-risk mechanical refactor for a future branch.

### 4.C · Dead-code `hasattr()` guards on now-hard deps (LOW)

`controllers/main.py:655` — `hasattr(SaleOrder, "_resolve_channel_pricelist")`
`controllers/main.py:596` — `hasattr(tmpl, "x_prodboard_archetype_id")`
`models/reconcile.py:99` — `hasattr(SaleOrder, "_resolve_channel_pricelist")`

Both attributes are defined in `southbrook_estimating`, which is a hard dep since 2026-06-28 (`__manifest__.py:22-26`). The guards were defensive before the manifest hardened; now dead. Non-harmful, mildly misleading.

### 4.D · Designer group can't delete their own designs (LOW — behavior clarification needed)

`security/ir.model.access.csv` grants Designer `perm_unlink=0` on `southbrook.kitchen.design`, but `security/kitchen_design_rules.xml:19-27 rule_kitchen_design_designer_own` sets `perm_unlink="True"`. Odoo intersects CSV ∩ rule = AND, so CSV wins → Designers cannot delete their own drafts.

The rule's `perm_unlink="True"` and its header comment "Designer sees only their own designs" suggest the ACL was intended to allow self-deletes but the CSV was left at 0. Product-behavior clarification needed: is this "no self-deletes" a designed policy or an oversight?

### 4.E · Minor 3D scene lifecycle leaks (LOW)

Two items not disposed explicitly on unmount:
1. `scene.environment` PMREM texture (`kitchen_configurator.js:984`) — a fresh render target every mount
2. The 4 lights themselves stay on the scene when unmount clears refs

Both get GC'd eventually via `renderer.dispose()` at `:1324`. Acceptable for a single-session client action; would matter more for a re-mount-heavy dev flow.

### 4.F · Zero HttpCase coverage (P2)

Only 1 of 7 controller routes has any test (`/save_design`, added this session). No `HttpCase.url_open` anywhere. Every werkzeug HTTP dispatch layer (session, cookies, CSRF, `type="json"` envelope handling) is untested.

## 5 · False-positive from the audit agent

**AbstractModel cron reference (`data/rec_d_reconcile_cron.xml:21`)** — Agent A flagged that referencing an AbstractModel via `model_id ref="model_southbrook_design_reconcile"` might fail at install because v19 could skip `ir.model` creation for AbstractModels. Agent C verified: **Odoo v19 DOES create `ir.model` rows for AbstractModels** (base module's `ir.model._reflect_models` covers all registry-loaded models). The cron loads and runs. False positive; noted for reference.

Sibling pattern for reference: `southbrook_manufacturing_intelligence/data/mi_recompute_cron.xml:24` attaches its cron code onto a concrete host (`mrp.production`) instead — the more defensive convention worth adopting in a future refactor.

## 6 · Compliance with `CLAUDE.md` §3 ("Southbrook Kitchen 3D Configurator")

| Criterion | Status | Evidence |
|---|---|---|
| Vendored r160 Three.js (no CDN) | ✅ | `southbrook_estimating/static/lib/three/three.min.js` consumed via `window.THREE` |
| ACES Filmic tone mapping + sRGB output | ✅ (via shared pipeline w/ estimating_website) | Set up in `kitchen_configurator.js` scene init |
| 3-tier group taxonomy (Readonly < Designer < Manager) | ✅ | `security/groups.xml:26-42` with correct `implied_ids` chain |
| Chatter widget on design form | ✅ | `views/kitchen_design_views.xml:200` + `_inherit=["mail.thread","mail.activity.mixin"]` |
| Integration with `southbrook_estimating` channel pricelists | ✅ | `_resolve_channel_pricelist` consumed in controller + reconcile |
| Smart-pinning (pinned + rotation_deg per line) | ✅ | Added in v19.0.4.20.0 per manifest changelog |
| Canonical catalog tagging | ✅ but with §4.A caveat | 11 templates tagged; noupdate="0" mid-blast-radius |
| Kanban preview thumbnail | ✅ | `views/kitchen_design_views.xml:37-86` with `x_kitchen_image` fields.Image |
| Zero customer data in demo | ✅ | `data/demo_cabinets.xml` — 7 fake templates only |

## 7 · Files changed this session

```
addons/southbrook_kitchen_3d_configurator/controllers/main.py                   +42 / -1 (P1 SECURITY — /save catalog-contract enforcement)
addons/southbrook_kitchen_3d_configurator/tests/__init__.py                     NEW (was 0 tests / no directory)
addons/southbrook_kitchen_3d_configurator/tests/test_save_design_acl.py         NEW +200 lines / 6 regression tests
docs/E2E_AUDIT_KITCHEN_3D_CONFIGURATOR_2026-07-01.md                            THIS FILE
```

**NOT committed this session:** John's in-progress `models/kitchen_design.py` (M), `models/sale_order_line.py` (new), `models/southbrook_room.py` (new), `models/reconcile.py` (new). Those belong to the Rec-D Sprint 1 bridge workstream and are left for him to land.

## 8 · Recommendations going forward

### 8.1 Immediate (this branch)

- [x] Land the ACL fix on `save_design`
- [x] Add 6 regression tests in a new `tests/` directory
- [x] Re-run tests — **0 fail / 0 error / 6 tests** (run 3)

### 8.2 Next branch (P1)

- [ ] Split `data/canonical_catalog_tag.xml` into `_tags.xml` (noupdate=0, structural) + `_dimensions.xml` (noupdate=1, one-time seed) — §4.A
- [ ] Add HttpCase coverage for the other 6 controller routes — §4.F
- [ ] Extract the panel-placement rule into an `@api.model` classmethod so client + server share one implementation — §4.B

### 8.3 Cleanup (P2)

- [ ] Remove the 3 dead-code `hasattr()` guards on `_resolve_channel_pricelist` and `x_prodboard_archetype_id` — §4.C
- [ ] Clarify + fix the Designer group's self-delete policy (CSV `perm_unlink=0` vs rule `perm_unlink="True"`) — §4.D
- [ ] Add explicit `dispose()` on `scene.environment` PMREM texture — §4.E

### 8.4 Convention alignment

- [ ] Consider migrating `data/rec_d_reconcile_cron.xml` to the sibling MI-engine pattern (cron code hosted on a concrete model) — §5. Not urgent; the AbstractModel ref works.

## 9 · Session methodology

- Three parallel `Explore` agents fanned out to enumerate models, views/JS, and tests. Agent A over-flagged the AbstractModel cron ref as a likely install-time crash; Agent C verified it was a false positive.
- One baseline + 2 iteration test runs (~1 min wall clock each).
- Live prod URL was probed at HTTP surface only (behind login).
- Direct prod DB access was **not** attempted (classifier gate on unlabeled prod DB access).

Co-Authored-By: Claude Opus 4.7 &lt;noreply@anthropic.com&gt;
