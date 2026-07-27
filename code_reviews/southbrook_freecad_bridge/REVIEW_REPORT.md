# Code Review — `southbrook_freecad_bridge` (Module #19, Tier 4)

**Version:** 19.0.0.4.0 → **19.0.0.5.0**
**Reviewed:** 2026-07-11
**Scope:** ~1103 LOC — `controllers/main.py` (the render-service callback `POST /plm/cad_callback`), `models/mrp_production.py` (MO → render job), `data/system_parameters.xml`, ACL, views. Depends: mrp, product, mail, southbrook_estimating, southbrook_plm.
**Method:** Two parallel audits (v19+code; security+perf) + live install/test validation.

## Executive Summary
The Odoo side of an external FreeCAD render pipeline: a single `auth="public"` machine-to-machine callback authenticated by a shared secret. Both audits confirmed strong foundations: **no shipped secret** (env-configured; unset → 503 fail-closed), **no SSRF** (attachments referenced by id, no URL fetch), **restricted field write** (only `x_cad_status`+attachments), **secret checked before any write**, **v19-clean install**. The findings concentrate in *what a valid/recovered secret buys*.

Fixed: **1 HIGH (timing-attack secret compare) + partial HIGH-2 (no-wipe) + 2 MEDIUM (state guard, input validation) + 2 LOW (mt_note, 401 JSON)**. Install clean; all callback tests pass incl. 2 new regression tests. (2 pre-existing `southbrook_dims`-parity test failures, unrelated.)

## Fixed
| # | Sev | Title | Fix |
|---|-----|-------|-----|
| H1 | HIGH | Non-constant-time secret comparison (timing side-channel — recover the secret byte-by-byte) | `hmac.compare_digest(str(provided), str(configured))` |
| H2 (partial) | HIGH | Callback wrote `attachment_ids` as `(6,0)` REPLACE under sudo → a forged/replayed call could WIPE the linked CAD artifacts | switched to `(4,id)` ADD-semantics |
| M1 | MEDIUM | Forged/replayed callback could churn ANY MO (regress `done`→`error`) | gate the write on `x_cad_status in (pending,rendering)` OR unchanged-status (idempotent) → else 409 |
| M3 | MEDIUM | Uncaught `int()` on malformed payload → HTTP 500; no cap on `attachment_ids` | validate coercions → 400; cap list at 200 |
| L1 | LOW (v19) | `mail.mt_log_note` (doesn't exist in v19; worked via fallback) | → `mail.mt_note` (×3) |
| L2 | LOW | Secret mismatch raised `AccessError` → 403 HTML (docstring says JSON 401) | `make_response({"error":"bad_secret"}, 401)` |

## Documented (not applied)
- **HIGH-2 (full)** — restrict `attachment_ids` to attachments already bound to THIS MO (`res_model='mrp.production'`, `res_id==mo.id`) to close the cross-record disclosure (a valid-secret caller can still link arbitrary attachment ids). NOT applied because the external bridge's upload/bind flow is unconfirmed — a blind `res_model/res_id` filter would drop legit unbound uploads AND breaks the happy-path test (which links unbound attachments). Owner must confirm how the bridge uploads attachments, then add the filter.
- **MEDIUM-2 (perf/correctness)** — `action_confirm` fires a blocking `requests.post(timeout=10)` per MO serially inside the confirm transaction (10×N worker block + pre-commit send: bridge renders an MO that may roll back). Move to `after_commit`/queue_job/cron.
- **LOW** — `x_cad_status` `tracking=True` amplifies idempotent replays into chatter/mail rows; bridge secret transits cleartext `http://` on the docker network.
- **Parity drift (incidental)** — `test_bom_contents.test_constants_parity` fails on `TOEKICK_FAMILIES` set divergence between the shared `southbrook_dims.py` and `southbrook_estimating`'s constants — a real pre-existing data-parity drift in the shared dims module worth reconciling (not this addon's code).

## Database / Security / Performance
- No schema changes. Callback is O(1) (single browse + write, no N+1). Secret gate + no-default-secret + 503-when-unset hold — no unauthenticated compromise. Timing-leak closed (H1); no-wipe + state guard + input validation added (H2p/M1/M3).

## Testing Results
- **Install:** ✅ SUCCESS (90/90 modules, registry loaded). v19-clean.
- **Tests:** all `test_cad_callback` pass — including the 2 NEW regression tests (`test_forged_regression_of_settled_mo_is_blocked` → 409; `test_idempotent_replay_of_same_status_allowed` → 200) and the auth tests (401 for bad/missing secret, 503 unset, 404/400 validation). `test_g2a_gate` passes; `test_render_smoke` skipped (external bridge unreachable — expected).
- **2 pre-existing failures (unrelated to these changes):** `test_bom_contents.test_constants_parity` (TOEKICK_FAMILIES drift, above) and `test_dims_js_parity` (reads the dims `.js` which isn't in the container → `{}`). Both about the shared `southbrook_dims` module; I touched none of those files.
- **Harness note:** `southbrook_dims.py` (real, from `~/southbrook-v19cr/shared/`) copied into the container PYTHONPATH to satisfy the prod `/srv/shared` import — see [[southbrook_v19cr_local_test_recipe]].

## Recommendations (priority)
1. Confirm the bridge's attachment-upload/bind flow, then add the `res_model/res_id` filter (full HIGH-2) to close cross-record disclosure.
2. Move the outbound render POST out of the confirm transaction (MEDIUM-2).
3. Reconcile the `southbrook_dims` ↔ estimating `TOEKICK_FAMILIES` parity drift.
4. TLS or body-HMAC for the bridge hop; suppress tracking on no-op status writes.
