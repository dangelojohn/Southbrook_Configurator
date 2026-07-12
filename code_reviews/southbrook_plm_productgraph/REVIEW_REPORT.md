# Code Review — `southbrook_plm_productgraph` (Module #23, Tier 4)

**Version:** 19.0.1.0.0 → **19.0.1.1.0**
**Reviewed:** 2026-07-11
**Scope:** ~353 LOC, no controllers — the bridge that makes applying a Southbrook ECO also trigger a ProductGraph release (`southbrook.eco.action_apply` → `pg.release`). Models: southbrook_eco.py (extends the ECO apply); data/api_key_policy.xml. Depends: southbrook_plm, product_graph_release (external ProductGraph suite).
**Method:** One combined audit (v19 + security) + live install/test validation against the full staged ProductGraph suite (14 addons).

## Executive Summary
A small, **clean, well-built bridge**. The audit found no CRITICAL/HIGH: no `sudo()`, no `eval`/`exec`, no HTTP/SSRF, no secret logging, v19-correct syntax, and — verified — **no privilege escalation** (the ECO trigger runs `pg.release` create + `action_execute_release` as the *current* user; both re-check `group_pg_approver`, so a PLM approver without a PG approver role degrades to a chatter note, not a privileged release). Graceful-degradation semantics are correct (super() the authoritative apply first, then optional release; failures log + chatter, ECO stays applied).

Fixed: **1 robustness gap** (savepoint) + a **pre-existing cross-module test-fixture bug** (ProductGraph SoD). Install clean; **4/4 bridge tests green**. The one MEDIUM (broad API-key policy) is a deliberate D6 decision, documented.

## Fixed
| # | Sev | Title | Fix |
|---|-----|-------|-----|
| R1 | LOW→robustness | `_trigger_pg_release`'s `try/except` had no savepoint: a DB-level failure (IntegrityError before ProductGraph's own inner savepoint — the advisory-lock query / `state='executing'` write) would poison the cursor, so the `message_post` then failed and the whole transaction — INCLUDING the authoritative ECO apply — rolled back, defeating the "failures do NOT roll back the ECO" contract | wrapped the `pg.release` create + execute in `with self.env.cr.savepoint()` (belt-and-braces cursor isolation; also makes the "orphan failed pg.release" LOW moot — a failed release now rolls back cleanly) |
| T1 | (test) | `test_bridge` setUpClass submitted AND released each `pg.revision`/`pg.ebom` as the same user → `product_graph_revision`'s Segregation-of-Duties rejected it (submitter ≠ releaser), erroring setUpClass so NO bridge test ran | added a distinct pg-admin `releaser` user; the 3 release steps now run `.with_user(cls.releaser)` |

## Documented (not applied)
- **MEDIUM (security)** — `data/api_key_policy.xml` sets `api_key_duration=1825` (5 years) on **`base.group_user`**, so EVERY internal user can mint 5-year API keys (a larger exposure window if any key leaks). This is a **deliberate D6 decision** (to let the `mcp-bot` service account mint long-lived keys without group elevation). The least-privilege fix — a dedicated single-member `group_pg_mcp_service` with the 5-year cap, restoring the 90-day default on `base.group_user` (`max()` semantics keep the service account's cap) — requires assigning the specific `mcp-bot` account, so it's left to the owner to avoid breaking the MCP integration. Not remotely exploitable (internal-user mint only), `noupdate` so an admin can revert.

## Database / Security / Performance
- No schema changes. No new model (fields added to `southbrook.eco` via `_inherit` → no ACL needed). No sudo/eval/HTTP/secret-logging. The ECO trigger is ACL-gated at the ProductGraph layer. Savepoint isolation added.

## Testing Results
- **Install (with 14 ProductGraph addons + southbrook deps staged):** ✅ SUCCESS. v19-CLEAN (`api_key_duration` is a real v19 `res.groups` field; the `base.group_user` noupdate record + both inherited-view xpaths load cleanly).
- **Unit tests:** ✅ **0 failed / 0 error / 4 tests** (install + upgrade).
  - Baseline: setUpClass ERRORed (the SoD fixture bug) → 0 tests ran. After the fixture fix, all 4 run and pass, incl. `test_bridge_fires_release` (ECO apply → `pg.release` executes, `state='completed'`, `mrp.bom` created) — which exercises the savepoint fix's success path.

## Recommendations (priority)
1. **MEDIUM** — re-scope `api_key_duration=1825` from `base.group_user` to a dedicated single-member service group; assign only `mcp-bot`.
2. Consider stamping `pg_release_id` even on a failed release for discoverability (mostly moot now the failed release rolls back via the savepoint).
