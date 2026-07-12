# Code Review — `southbrook_floor_traveler`

**Module #44 of 46 · Odoo 19.0 CE · 617 LOC**
**Version:** 19.0.1.2.1 → **19.0.2.0.0**
**Reviewed:** 2026-07-11
**Method:** 2 parallel audit agents (security+IDOR; v19+QWeb) → independent source
verification incl. reading the scan endpoint + `record_scan` sudo path + the v19
`type="json"` alias source → HEAD baseline → real fixes + regression test → live
`-i`+`-u`+tests on isolated DB (`ci_floor44`, full dep stack staged).

## What the module does
Shop-floor **traveler**: a QWeb PDF per `sb.production.package` with a QR encoding the
package id, and a **scan endpoint** `/southbrook/api/floor-traveler/scan` that advances
the next `mrp.workorder` via the existing `button_finish` (+ tool-consumption debit) and
logs scan telemetry to `southbrook.qr.scan.log`.

## Verdict
**v19-clean** (v19 agent: installs/upgrades/runs clean, QWeb report works, `type="json"`
is a still-working deprecated alias — not a break). But the scan endpoint was a
**CRITICAL IDOR**: `auth="user"` + a `sudo()`-advanced workorder keyed on a caller-supplied
package id, with **no internal/group check** — so any authenticated user, **including an
external portal customer**, could finish production for any job by guessing a package id.
Fixed the IDOR + portal reachability + audit attribution + `type` future-proofing.
Baseline **1 err of 6 → 0 fail of 7** (+1 security regression test).

## Findings

### Fixed — security
| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **C1/H1** | **CRITICAL** | **IDOR — any authenticated user (incl. portal customer) advances/finishes any workorder.** `auth="user"` admits every session; `_resolve_package_id` accepts the **unsigned** `sb-package:<id>` format (a bare client int, printed in cleartext on every traveler QR); `sb.production.package.sudo().browse(id)` + `record_scan` → `wo.sudo().button_finish()` runs the advance + tool-consumption debit as superuser with **no id/ownership/group/company check**. A portal dealer POSTs `{"qr_payload":"sb-package:1"}` and drives another customer's production. | Gate the endpoint to **internal `mrp.group_mrp_user`** operators (`_is_internal()` + `has_group`) → `forbidden` otherwise, before any work. Shop-floor scanning is a **group-authorized** action (any operator, any job at their station), so a group gate — not per-object ownership — is the correct model; the `.sudo()` (needed for the legit cross-model consumption write) is now reachable only by authorized operators. |
| **M1** | MED | **Scan-log attribution destroyed by sudo** — `southbrook.qr.scan.log.sudo().create(...)` left `create_uid`/`user_id` as OdooBot, so a production-mutation audit log couldn't attribute a scan to a real operator. | Set `user_id: env.uid` explicitly on the log create. |
| **type** | LOW | `type="json"` (v19 keeps it as a working deprecated alias → jsonrpc, so not a break, but it warns and could be removed in v20). | `type="jsonrpc"`. |

### Documented (design / follow-up — not changed)
| # | Sev | Finding | Note |
|---|-----|---------|------|
| C2 | (design) | `record_scan` `sudo()`s `button_finish` — the security agent recommended dropping it. | **Kept intentionally**: shop-floor scanning is group-authorized (operators aren't assigned to specific packages), and the sudo covers a legitimate cross-model tool-consumption write that mrp operators may lack direct ACL for (the "BUG 1 fix"). Dropping it would break the workflow + regress that fix. The **group gate** is the correct boundary. |
| C3 | HIGH→doc | **Replay / no idempotency** — an authorized operator (now the only caller) can re-scan the same QR to double-advance / double-debit; the signed payload's `expired` flag is ignored (and `qr_kit` hardcodes it `False`). | Needs a per-package scan nonce/TTL + rate limit — a cross-module effort with `qr_kit` (which owns the TTL). Bounded now to authorized operators by the gate. |
| unsigned | MED→doc | The unsigned `sb-package:<id>` format is still accepted (forgeable). | Retiring it requires re-issuing every printed traveler PDF to the signed `sb://pkg/<id>?s=<hmac>` format — an operational rollout decision. The signed path already verifies HMAC+kind. |
| LOW1 | LOW | `southbrook.qr.scan.log` readable by every internal user (incl. `source_ip`/`user_agent`). | Gate to a shop-floor group if considered sensitive (sibling `qr_kit` ACL). |

## Strong positives (verified)
- **No injection** — `_resolve_package_id` is pure `int()` coercion + a signed-path delegate that uses `hmac.compare_digest` and rejects extra query keys. No eval/exec/SQL.
- The **signed `sb://pkg/<id>` path genuinely verifies** HMAC + kind (it's just not mandatory). `record_scan` routes through the existing `button_finish` (no re-implemented debit → "exactly once" holds) and snapshots the workcenter before the state transition. Log write is try/excepted (telemetry can't fail the scan).
- **v19-clean**: `type="json"` works (alias); `@api.depends` valid; QWeb report valid (`t-esc`, valid `ir.actions.report`, `_fields[...].selection` label pattern is QWeb-safe, qrcode soft-dep degrades gracefully); no removed-field usage; no security CSV needed (rides parent ACLs).

## Validation
- `-i` (fresh DB, full dep stack) — **clean**, registry ~70 s.
- `-u` — clean (2.2 s).
- Tests — **7/7 pass** (from a baseline of 1 err of 6). The baseline error was the
  premium_orchestration MO availability gate in setUp; the unmasked asset-collision
  (seeded asset(1) vs the test's asset — same class as module 43) was fixed by
  isolating the test to a fresh tool category. +1 HttpCase regression: a non-mrp user
  gets `forbidden`. See `TEST_RESULTS.md`.
