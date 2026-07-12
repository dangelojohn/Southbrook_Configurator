# Code Review — `southbrook_premium_orchestration`

**Module #43 of 46 · Odoo 19.0 CE · 4928 LOC**
**Version:** 19.0.4.7.0 → **19.0.4.8.0**
**Reviewed:** 2026-07-11
**Method:** 2 parallel audit agents (security+governance; v19+install) → independent
source verification incl. reading `wall.py` + both AI activators + the sibling gate
chain → HEAD baseline → real fixes + test-gate repairs → live `-i`+`-u`+tests on
isolated DB (`ci_prem43`, full 15-module southbrook dep chain staged).

## What the module does
The "close-the-loop" orchestration layer: a `sale.order.action_confirm` override that
always builds the **project.task spine** + backlinks MOs; **6 crons** (readiness, MI
gate-refire, order analytics, data-quality, ECO proposer); an **MO availability gate**
on `mrp.production.action_confirm`; **AI activators** (Gemini + FreeCAD go-live
consoles); and a public **shop-floor "wall" JSON feed**.

## Verdict
**v19-clean** (v19 agent: installs/upgrades clean, registry-safe, correct AbstractModel
activation, correct cron schema — a genuinely disciplined large module). **Two strong
security positives**: no auto-release-to-production cron (the ECO cron only *proposes*),
and no delete-all-recreate / `cr.commit()` in any cron. But the **AI activators leaked
the Gemini key and exposed admin-only config to any employee**, and the **public wall
feed leaks customer PII**. Fixed **2 HIGH (AI) + the wall exposure + 2 cron-governance +
a real create() bug**; cleared **all 14 test ERRORs** (sibling governance gates the tests
predate). Baseline **2 fail + 14 err → 8 fail + 0 err** (8 residuals pre-existing,
documented).

## Findings

### Fixed — security
| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **3a** | **HIGH** | **Gemini API key leaked to log + a `base.group_user`-readable field.** The 200-path redacted the key, but the **exception** path (`requests.RequestException`) logged and stored `str(exc)`, which embeds the request URL — and the key was a `?key=` query param. | Send the key in the **`x-goog-api-key` header** (never in the URL), and redact defensively on both the non-200 and exception paths. |
| **3b** | **HIGH** | **Public sudo-mutators = privilege escalation.** `action_set_api_key` / `action_enable_real_calls` / `action_health_check` (Gemini) and the FreeCAD url/enable/health/render setters are public (RPC-reachable), sudo system config internally, and the models grant `base.group_user` read — so **any employee could overwrite the Gemini key, switch on live billing, or repoint the CAD bridge**. | Added an `env.is_system()` guard (`_check_admin`) to every mutator on both activators. |
| **1** | **HIGH** | **Public wall feed leaks customer PII.** `/southbrook/wall/<station>.json` is `auth="public"` + `stock.picking.sudo()`; it returns up to 50 outbound rows with **customer name, SO ref, carrier, tracking #, delivery schedule** to any unauthenticated caller. The module's own docstring flags this as "effectively public … an open privacy question … before production," with the intended mitigation (a Caddy IP allowlist) not yet in place. (`station` is dict-allowlisted — no injection. Good.) | Added an **optional code-side token gate**: if `ir.config_parameter southbrook_premium_orchestration.wall_token` is set, require it via `?token=`/`X-Wall-Token` (constant-time); if unset, behaves exactly as before (documented POC) — so the owner can lock down without a network or logic change. |
| **3c** | MED | SSRF — a low-priv user could repoint `freecad_bridge.url` and use the server-side health GET to probe internal hosts. | Folded into 3b (all FreeCAD setters admin-gated). |

### Fixed — cron governance / correctness
| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **2a** | MED | ECO-proposal cron not pinned to a `user_id` (inconsistent with the 4 root crons). | `user_id ref="base.user_root"`. |
| **2b** | MED | Readiness cron had no per-row `try/except` — one bad task aborts the whole root-run sweep (the analytics + DQ crons already isolate). | Per-task `try/except` + `_logger.exception`. |
| **create-sym** | MED | **`project.task.create` didn't apply an explicitly-set job template** — `write()` did, so a task created *with* a template (import / server action) never spawned its subtasks. (Real asymmetry; the phase3 idempotency test caught it.) | `create` now applies an explicit template (idempotent `_apply_job_template`), symmetric with `write`. |

### Documented (business-policy / cross-module / verify — not changed)
| # | Sev | Finding | Note |
|---|-----|---------|------|
| 2c | MED | ECO `description_html` built from unescaped operator free-text. | Safe **iff** `southbrook.eco.description` is a sanitizing `Html` field (verify in southbrook_plm); if `Text`/raw, escape. |
| 3d | MED | No daily cost cap / budget on the AI path (only `use_mock`). | The billed calls live in the sibling `southbrook.gemini.client` — confirm a cap there (campaign added caps elsewhere). |
| 5 | LOW-MED | `ops.event.emit` is public + sudo → any employee can inject activity-feed rows (spoof "MO done"). | Feed-integrity; QWeb-escaped so low XSS risk. |
| 6a | LOW-MED | `cut.spec.override` writable by `base.group_user`; activator read granted to all users. | Tighten ACL (the activator-read enabled 3a's field read). |
| 4 / 1b | LOW | `_backlink_orphan_mos` matches MOs on free-text `origin` with no company scoping; wall error branch returns exception text to the anon caller. | Minor. |

## Pre-existing test failures (documented — NOT regressions; masked by the gate ERRORs at baseline)
Clearing the two sibling governance gates (this module's **MO availability gate** and
`southbrook_mrp_pm`'s **production-approval gate** — both legitimate product behavior the
tests predate) unmasked **8 pre-existing assertion failures**, in two buckets:
- **Test-isolation / seed-data collision (3):** the spine resolver + tool-asset resolver
  pick the lowest-id seeded record (`project(1)`, `asset(1)`) instead of the test's
  fixture — the tests assume a clean DB.
- **Cross-module behavioral drift (5):** SKU-grammar divergence, cutlist panel count
  (6 vs ≥7), workorder duration derivation (1596 vs 10 min), and the tool-lifecycle
  10%-threshold activity — all produced by *sibling* modules (estimating / kitchen_tools /
  cutlist), out of scope for a single-module review and needing sibling investigation.

These were **failing at baseline** (2 fail + 14 err); the ERRORs were setUp gate-blocks
that hid the assertions. My changes cleared all 14 ERRORs and introduced no regression
(fresh `-i`/`-u` clean; none of the 8 assertions touch the code I changed).

## Strong positives (verified)
- **No auto-release-to-production cron** (ECO cron creates `state='open'` proposals — human approval preserved). **No delete-all-recreate, no `cr.commit()`** in any cron.
- **No eval/exec**; the one raw SQL is fully static/parameterless. `action_confirm` override doesn't escalate or launder the mrp_pm gate.
- **v19-clean**: correct AbstractModel activation (new `mi.engine.state` model, not an `_inherit` of the abstract parent); correct cron schema; `@api.model_create_multi`; no removed-field/`res.groups.users`/`stock.move.name` usage; pervasive `_fields`-probing so it installs on bare CE.

## Validation
- `-i` (fresh DB, full 15-module dep chain) — **clean**, registry ~66 s.
- `-u` — clean (2.4 s).
- Tests — **8 fail / 0 err of 23** (from 2 fail + 14 err); all 14 gate-block ERRORs
  cleared + the phase3 idempotency bug fixed. 8 residuals pre-existing (documented).
  See `TEST_RESULTS.md`.
