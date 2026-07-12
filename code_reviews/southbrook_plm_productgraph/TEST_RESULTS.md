# Test Results — `southbrook_plm_productgraph` (Module #23)

**Harness:** v19c-odoo, isolated DB, staged with southbrook_plm + southbrook_estimating
+ southbrook_qr_kit AND the full ProductGraph suite (14 `product_graph_*` addons
from ~/product_graph_v19/addons/) over the OCA modules.

## Install
- Fresh install (`-i`): ✅ SUCCESS — 94 modules loaded. v19-CLEAN (no obj() trap;
  `api_key_duration` is a real v19 res.groups field; the base.group_user noupdate
  record and both inherited-view xpaths resolve).

## Unit tests
`--test-enable --test-tags southbrook_plm_productgraph` → ✅ **0 failed / 0 error / 4 tests**
(install + upgrade).

### Fixture bug fixed (pre-existing, cross-module)
- Baseline: `setUpClass` ERRORed — `cls.cab_rev.action_release()` raised
  `UserError: You submitted revision ... yourself — a different user must release
  it (Segregation of Duties)`. The fixture submitted AND released as one user,
  which `product_graph_revision`'s SoD (a legitimate governance rule) rejects.
  Because setUpClass errored, ZERO bridge tests ran.
- After adding a distinct pg-admin releaser user for the 3 release steps, all 4
  tests run and pass: `test_bridge_fires_release` (ECO apply → pg.release executes,
  state='completed', mrp.bom created — exercises the savepoint success path),
  `test_bridge_skips_without_ebom`, `test_bridge_skips_when_auto_release_off`,
  `test_bridge_idempotent`.

## Audit cross-checks
- Combined audit: **CLEAN, ship-ready** — no CRITICAL/HIGH. No sudo/eval/HTTP/SSRF/
  secret-logging; no privilege escalation (the ECO trigger's pg.release create +
  execute both re-check group_pg_approver as the current user). Graceful
  degradation confirmed. Only MEDIUM = the broad api_key_duration (documented).

## Conclusion
A clean, correctly-degrading bridge. The savepoint fix hardens the "PG failure
doesn't roll back the ECO" contract against the DB-error edge case; the SoD fixture
fix lets the suite actually validate the bridge (4/4 green). The broad API-key
policy is a deliberate D6 decision documented for owner re-scoping.
