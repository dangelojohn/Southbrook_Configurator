# Code Review & Repair Report — `southbrook_qr_kit`

**Module:** Southbrook QR Kit · **Version:** 19.0.0.14.0 → **19.0.0.15.0**
**Reviewed:** 2026-07-10 · **Odoo target:** v19 Community Edition
**Queue position:** #2 of 46 (Tier 0 — leaf; deps all standard Odoo: base, web, mail, stock, hr, mrp)
**Review method:** 3 parallel read-only audit agents (v19-compat/code, security, performance) + independent source verification + **live test execution** on Odoo 19 CE.

---

## Executive Summary

QR Kit is the platform's QR foundation: HMAC-signed `sb://<kind>/<id>?t=&s=` payloads, a `/sb/qr/scan` dispatcher, a public POD/floor-action framework, an append-only scan-log, an operator-PIN identity layer, a service-worker offline queue, and a kind-registry pattern other addons extend.

**Unlike Module #1, this module was NOT clean — it shipped with real, serious defects, and its own test suite was red (15 of 57 tests failing).** The review found and fixed:

- **A CRITICAL production correctness bug (C1):** the kind-registry dispatch mis-used the AbstractModel-falsy trap (`if not handler:` on a resolved-but-empty recordset), so **every QR scan, POD, floor action, and trolley bind returned `unknown_kind`** — the entire QR feature set was non-functional in prod. Proven by running the suite (`unknown_kind` assertions failing).
- **Three CRITICAL security vulnerabilities:** a reflected XSS in `scan_get`, an unauthenticated query-param-smuggling XSS across the public POD/floor pages (root cause: signature covered only `kind/id/t`), and an unthrottled operator-PIN brute-force endpoint.
- **A HIGH privilege bug:** `bin_scan` moved stock under `sudo()`, letting any logged-in user bypass Inventory ACL.
- Plus a broken tablet-redirect URL, a broken floor-shell render, deprecated v19 APIs, missing indexes, and no scan-log retention.

**Result: the suite went from 15 failing to 0 failing (60/60 green, incl. 3 new security regression tests), and all three security criticals are closed.**

---

## Original Issues Found

### Correctness (verified by live test run — suite was shipping RED)
| # | Sev | Finding |
|---|-----|---------|
| C1 | **CRITICAL** | `resolve_kind()` returns a *falsy* empty AbstractModel recordset on a hit and literal `False` on a miss; every caller (`qr_scan.py`, `floor_action.py` ×2) tested `if not handler:`, so **hits were treated as misses → `unknown_kind` for every scan/POD/floor/trolley op**. AbstractModel-falsy trap. (7 failing tests.) |
| W071 | **HIGH** | Trolley-bind calls `self.message_post()` on `mrp.workorder`, which has **no `mail.thread` in base v19 CE** → `AttributeError` (crash) on bind. (2 failing tests.) |
| W073 | **HIGH** | `_render_floor_shell` read `get_data()` on a **lazy** QWeb Response (empty at that point), then `set_data()` clobbered the template — the floor companion pages served only `<!DOCTYPE html>`. (2 failing tests, real over HTTP.) |
| H2 | HIGH | `scan_get` tablet redirect built `/odoo/action-<model>/<id>` — the `action-` prefix is v19-reserved for numeric action ids, so the redirect was dead. |
| H3 | MED | `qr_kind.handle_action` returned a `redirect` to `base.action_open_view` (a non-existent xmlid). |
| W072 | — (test) | 4 tests used a hand-rolled `_FakeResponse` that v19's stricter route return-validator rejects. |

### Security
| # | Sev | Finding |
|---|-----|---------|
| S1 | **CRITICAL** | Reflected XSS in `scan_get`: `result['error']` (which echoes the raw pre-signature-check payload) and `json.dumps(result)` interpolated into HTML unescaped. `GET /sb/qr/scan?p=<script>…</script>` runs JS in the authenticated session. |
| S2 | **CRITICAL** | Query-param smuggling XSS: `parse()` signed only `kind/ident?t=<ts>`, silently ignoring other query keys — so a validly-signed QR could carry `&x=</script><script>…` that rode along unsigned into the public POD/floor pages' inline `<script>` (via `repr(payload)`). Unauthenticated. |
| S3 | **CRITICAL** | `/sb/qr/identify` (public, csrf=False) checked a 3–12-digit operator PIN with **no rate limit** → trivial brute-force + employee enumeration. |
| S4 | **HIGH** | `bin_scan` ran `stock.move._scan_quick_move` under `.sudo()` on an `auth="user"` route — any logged-in user (no Inventory rights) could move arbitrary stock, violating the module's own "ACL still enforced" claim. |
| S5 | HIGH | Stored XSS in `/sb/qr/labels`: record `display_name` interpolated unescaped. |
| M1 | MED | `qr_kind.get_record` used deprecated v19 `check_access_rights()`/`check_access_rule()`. |
| — | MED | `@route(type="json")` deprecated in v19 (→ `jsonrpc`). |

### Performance
| # | Sev | Finding |
|---|-----|---------|
| P1 | **CRITICAL** | Scan-log (`target_model`, `target_id`) unindexed — the pair the audit log exists to be queried by. |
| P2 | HIGH | No retention/pruning cron — append-only log grows unbounded forever. |
| P3 | HIGH | `create_date` unindexed despite being `_order` + the default "Last 24h" filter. |
| P4 | MED | `/sb/qr/labels` accepted an unbounded `ids` list → synchronous per-record QR render = worker-block DoS. |

---

## Repairs Completed

**Correctness**
1. **C1:** `resolve_kind` callers now test `if handler is False:` (the sentinel), not truthiness — 3 call sites + the test that encoded the same misconception. Restores the entire scan/POD/floor/trolley pipeline.
2. **W071:** guarded the workorder `message_post` with `hasattr` (the picking-side chatter, always present, is unchanged); trolley-bind no longer crashes on a lean install. (Reverted an initial `_inherit mail.thread` attempt that broke the registry with an M2M-relation collision.)
3. **W073:** `_render_floor_shell` now calls `resp.flatten()` to materialise the QWeb body before touching it.
4. **H2/H3:** redirect URLs corrected to `/odoo/<model>/<id>`.

**Security**
5. **S2 (root cause):** `parse()` now rejects any query key other than `t`/`s`, so a "valid_signature" payload is also structurally canonical — no unsigned smuggling.
6. **S1:** every interpolated value in `scan_get` HTML is `markupsafe.escape`d.
7. **S5:** `display_name` in `/sb/qr/labels` is `html.escape`d.
8. **defense-in-depth:** the 3 inline-`<script>` `repr(payload)` sites → `json.dumps(payload).replace("</","<\\/")`.
9. **S3:** dedicated per-IP failed-PIN throttle (5 / 5 min) on `/sb/qr/identify`.
10. **S4:** dropped the `.sudo()` in `bin_scan` — stock ACL now applies to the acting user.
11. **M1:** `check_access("read")` replaces the deprecated pair.
12. **v19:** all 9 `type="json"` routes → `type="jsonrpc"` (deprecation warnings gone).

**Performance**
13. **P1/P3:** `index=True` on `target_model`, `target_id`, and `create_date`.
14. **P2:** `autovacuum()` retention method + daily `ir_cron_qr_scan_log_prune` cron (config `southbrook.qr_kit.scan_log_retention_days`, default 180; `<=0` = keep forever).
15. **P4:** `/sb/qr/labels` caps `ids` at 200.

**Tests**
16. New `test_security_hardening.py` — query-key rejection + PIN-throttle regression tests. Fixed 2 test harnesses (w072 `_FakeResponse`→werkzeug `Response`; w071 conditional workorder chatter).

### Deliberately NOT changed (documented as recommendations)
- Exception-text leakage to anonymous callers on public routes (return generic messages) — MED; deferred to avoid broad handler churn.
- Tightening scan-log `base.group_system` unlink/write for true forensic append-only — admins legitimately need a purge path.
- TTL / one-time-use on `install_check`/`temp_labor_signin` floor QRs — MED, design change.
- Multi-company scan-log record rule — the model has no `company_id` field; would require a schema addition.
- QR-image caching / stable-timestamp signatures — the per-call `ts` is intentional; a redesign, not a repair.

---

## Files Changed
11 modified, 2 new (`data/ir_cron.xml`, `tests/test_security_hardening.py`). +218/−68 lines. No public method signatures or business logic removed; the QR wire format is unchanged (only stricter validation added).

## Database Impact
- 3 new indexes on `southbrook_qr_scan_log` (table ~empty in a fresh install; brief `CREATE INDEX` otherwise).
- 1 new daily cron (`noupdate`), 1 new config param (lazy).
- No column drops / type changes / data migration. Forward-compatible.

## Security Improvements
Three CRITICAL vulns closed (2 XSS + PIN brute-force), one HIGH ACL bypass closed, one stored XSS closed, canonical-signature enforcement added. HMAC crypto was already sound (constant-time compare, CSPRNG secret) — left intact.

## Performance Improvements
Audit-log reads no longer full-scan (3 indexes); unbounded table growth capped by retention; label-print DoS bounded.

## Testing Results
_See `TEST_RESULTS.md`._ Cold install + full suite on Odoo 19 CE (isolated DB): **60/60 pass, 0 failed, 0 errors** (was 42 pass / 15 fail before this review). DB objects verified present. jsonrpc deprecation warnings eliminated.

## Remaining Risks
The 5 "not changed" items above, all MEDIUM or design-level. Most notably: consider exception-message sanitization on the public routes and a TTL for replayable floor QRs before broadening public exposure. None block the module; all are documented for the owner.

## Recommendations
- Deploy the C1 fix promptly — the QR feature set is currently non-functional in prod.
- Set `southbrook.qr_kit.scan_log_retention_days` per retention policy.
- Schedule the deferred MEDIUM items (exception sanitization, floor-QR TTL) as a follow-up hardening pass.
