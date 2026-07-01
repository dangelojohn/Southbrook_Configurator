# Rec D Sprint 2d Postmortem — 2026-07-01

**Failure:** `KeyNotFoundError: Cannot find key "southbrook_kitchen_configurator" in the "actions" registry` at 2026-07-01 20:45 GMT.
**Impact:** Client action `southbrook_kitchen_configurator` unreachable after any WebClient boot. Every existing "Open in 3D" button on kitchen designs / rooms / sale orders lands on a 404-shape error page.
**Duration on prod:** ~10 minutes between deploy at 20:34 (5.4.13) and rollback at 20:44 (5.4.14).
**Blast radius:** Backend 3D configurator only. Sprint 1 backend + Sprint 2a-c UI surfaces unaffected. `/kitchen-planner`, `/shop/<slug>`, and `/my/southbrook/order-builder` all continued to render normally.

---

## Timeline

| Time (GMT) | Version | Event |
|---|---|---|
| ~17:15 | 5.4.1 | Sprint 2d step 1 (`constants.esm.js`) — deploy clean, tripwire green |
| 17:20-17:40 | 5.4.2 → 5.4.5 | Steps 2-5 (three_loader, pointer_helpers, view_specs, mesh_factory) — clean |
| ~17:50 | 5.4.6 | Steps 6-8 (packRow, easing, ortho_frustum) — clean |
| ~18:00 | 5.4.7 | Steps 9-10 (selection, drop_raycaster) — clean |
| ~18:15 | 5.4.8 → 5.4.10 | Steps 11-14 (room_shell, drag_handle, drop_lanes, pbr_env_map) — clean |
| ~18:30 | 5.4.11 | Step 15 (base_cabinet) — clean |
| ~18:40 | 5.4.12 | Step 16 (wall_cabinet) — clean |
| ~18:45 | 5.4.13 | Steps 17-19 (other_cabinets — tall/corner/panel/filler/endcap) — clean |
| 20:34 | 5.4.13 | Bundle regenerated on first authenticated hit (lazy compile) |
| 20:45 | 5.4.13 | User navigates to `/odoo/...` → `KeyNotFoundError` surfaces |
| 20:47 | 5.4.13 | Second identical error reported |
| 20:47 | 5.4.14 | Rollback deployed — `git checkout b471034 -- addons/southbrook_kitchen_3d_configurator/` |
| 20:49 | 5.4.14 | Rollback verified — bundle 11.9MB, action-registration marker present |

---

## Root cause

**Winner:** Sprint 2d step 1 (`canvas/constants.esm.js` import). Set the wrong pattern for all 19 imports that followed.

**Failure mode:** Odoo's asset bundler registers `foo.esm.js` as module id `@addon/path/foo.esm`, NOT `@addon/path/foo`. Every Sprint 2d import wrote the bare form. Odoo compiled the bundle fine (strings all present — which is why the string-tripwire passed), but at the first authenticated hit the module registry couldn't resolve any of the imports. `kitchen_configurator.js` threw at module-load time BEFORE reaching its `actionRegistry.add("southbrook_kitchen_configurator", …)` call at the end of the file.

**The exact code that threw:**
```js
import { IN, BW, BH, BD, WW, WH, WD, CTR, GAP, WBY, P }
    from "@southbrook_kitchen_3d_configurator/js/canvas/constants";
```
against a file registered as `@southbrook_kitchen_3d_configurator/js/canvas/constants.esm`. All 19 imports had this defect (14 in the main file + 5 cross-imports inside `canvas/`).

---

## Why the tripwire missed it

The `rec_d_sprint2d_tripwire.sh` script compiles the backend bundle in-process via `odoo shell` and greps the resulting JS for extraction markers. Every deploy in Sprint 2d passed this check because:

1. The bundle **did** compile — no SCSS/JS parse error would have raised in `ir.qweb._get_asset_bundle`.
2. The string `"southbrook_kitchen_configurator"` **was** in the bundle — it's the literal first argument to `registry.category("actions").add(...)`.

But the bundle-compile path does not **execute** the JS. The failure was at runtime: the file body threw at module init, so `registry.add()` never ran, so the string was in the bundle but the actual registration didn't happen.

**String presence in the bundle ≠ successful module execution.**

The runtime tripwire designed post-failure (see §Follow-ups) closes this gap by using a headless Playwright + service-account cookie to actually boot the WebClient and probe the OWL actions registry after the bundle executes.

---

## Corrections applied

- **5.4.14** — full rollback to commit `b471034` (Sprint 2c end-state, last known-good). Every Sprint 2d extraction removed from the manifest's asset bundle; the 17 `canvas/*.esm.js` files stay on disk but are inert until re-added.
- **`docs/southbrook_recommendation_d_2026-07-01.md`** — needs Sprint 2d "in flight" status changed to "rolled back pending runtime tripwire" (follow-up).

---

## Follow-ups (before Sprint 2d resumes)

1. **Stand up the Playwright runtime tripwire.**
   - One-time container prereq: `pip install playwright httpx && playwright install --with-deps chromium` into the Odoo container. ~170 MB image layer.
   - Stash a service-account credential at `/etc/odoo/tripwire.json` on the QNAP host (mode 0600, mounted read-only into the container). User-owned; I cannot handle credentials.
   - Ship `scripts/rec_d_runtime_tripwire.sh` per the runtime-tripwire agent's design.
   - Integrate into `deploy_to_qnap.sh` as step 3 after cold-upgrade and bundle-marker tripwire.

2. **Codify the module-scope-safe rule** — see below.

3. **Restart Sprint 2d one micro-step at a time with the runtime tripwire in the loop.** Every deploy blocks on Playwright verifying the action registered before promotion. Any regression triggers automatic rollback prompt.

4. **Delete the dormant canvas/*.esm.js files** if the winning suspect is a structural pattern that applies to all of them (e.g. "any module doing THREE at module scope"). Otherwise keep them for re-application after the identified fix.

---

## The rule for future Sprint 2d attempts

*(From the bisect agent's §4 "applies-broadly principle" — to be filled in.)*

_tbd_

---

## Files modified during rollback

- `addons/southbrook_kitchen_3d_configurator/__manifest__.py` — asset bundle reset, version 19.0.5.4.14
- `addons/southbrook_kitchen_3d_configurator/static/src/js/kitchen_configurator.js` — restored to `b471034` state (no canvas imports, all 19 pre-Sprint-2d closures back inline)

## Files still on disk but inert

- `addons/southbrook_kitchen_3d_configurator/static/src/js/canvas/constants.esm.js`
- `addons/southbrook_kitchen_3d_configurator/static/src/js/canvas/three_loader.esm.js`
- `addons/southbrook_kitchen_3d_configurator/static/src/js/canvas/pointer_helpers.esm.js`
- `addons/southbrook_kitchen_3d_configurator/static/src/js/canvas/view_specs.esm.js`
- `addons/southbrook_kitchen_3d_configurator/static/src/js/canvas/mesh_factory.esm.js`
- `addons/southbrook_kitchen_3d_configurator/static/src/js/canvas/pack_row.esm.js`
- `addons/southbrook_kitchen_3d_configurator/static/src/js/canvas/easing.esm.js`
- `addons/southbrook_kitchen_3d_configurator/static/src/js/canvas/ortho_frustum.esm.js`
- `addons/southbrook_kitchen_3d_configurator/static/src/js/canvas/selection.esm.js`
- `addons/southbrook_kitchen_3d_configurator/static/src/js/canvas/drop_raycaster.esm.js`
- `addons/southbrook_kitchen_3d_configurator/static/src/js/canvas/room_shell.esm.js`
- `addons/southbrook_kitchen_3d_configurator/static/src/js/canvas/drag_handle.esm.js`
- `addons/southbrook_kitchen_3d_configurator/static/src/js/canvas/drop_lanes.esm.js`
- `addons/southbrook_kitchen_3d_configurator/static/src/js/canvas/pbr_env_map.esm.js`
- `addons/southbrook_kitchen_3d_configurator/static/src/js/canvas/base_cabinet.esm.js`
- `addons/southbrook_kitchen_3d_configurator/static/src/js/canvas/wall_cabinet.esm.js`
- `addons/southbrook_kitchen_3d_configurator/static/src/js/canvas/other_cabinets.esm.js`

These are safe to leave in place. They do not appear in the `web.assets_backend` manifest list, so Odoo does not include them in any compiled bundle. Only referenced code executes.
