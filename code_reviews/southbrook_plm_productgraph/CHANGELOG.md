# CHANGELOG — `southbrook_plm_productgraph`

## 19.0.1.1.0 — 2026-07-11 — Code-review pass (Module #23)

### Fixed
- **Savepoint isolation on the ProductGraph release trigger.** `_trigger_pg_release`
  now wraps the `pg.release` create + `action_execute_release()` in
  `with self.env.cr.savepoint()`, so a DB-level failure rolls back only the
  release (not the authoritative ECO apply from super()) and leaves the cursor
  usable for the chatter note — honouring the documented "failures do NOT roll
  back the ECO" contract even for the pre-savepoint DB-error edge case.
  `models/southbrook_eco.py`.
- **Test fixture: honour ProductGraph Segregation of Duties.** `test_bridge`
  setUpClass submitted and released each pg.revision/pg.ebom as the same user,
  which `product_graph_revision`'s SoD rejects (submitter ≠ releaser), erroring
  setUpClass so no bridge test ran. Added a distinct pg-admin releaser user for
  the release steps. All 4 bridge tests now run and pass. `tests/test_bridge.py`.

### Notes (documented, not changed)
- `api_key_policy.xml` sets `api_key_duration=1825` (5-year keys) on
  `base.group_user` — a deliberate D6 decision, but broad (every internal user).
  Recommend a dedicated single-member service group instead (owner decision;
  needs the mcp-bot account assigned). Audit confirmed: no sudo/eval/HTTP/SSRF,
  no privilege escalation (release is ACL-gated at the PG layer).
