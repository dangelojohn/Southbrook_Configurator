# CHANGELOG — southbrook_premium_orchestration

## 19.0.4.8.0 — 2026-07-11 (code-review campaign, module #43)

### Fixed — security
- **Gemini key leak (3a, HIGH).** `models/gemini_activator.py` — send the key in the
  `x-goog-api-key` header (not the `?key=` query param) so it never enters the request
  URL / exception string; redact defensively on the non-200 and exception paths.
- **Admin-gate AI mutators (3b, HIGH).** Added an `env.is_system()` guard
  (`_check_admin`) to every public sudo-mutator on the Gemini activator
  (`action_set_api_key`, `action_enable_real_calls`, `action_health_check`) and the
  FreeCAD activator (`_inverse_url`, `_inverse_enabled`, `action_health_check`,
  `action_enable`, `action_render_first_mo`) — closes the any-employee escalation +
  the CAD-bridge SSRF (3c).
- **Wall-feed token gate (1, HIGH).** `controllers/wall.py` — optional shared-token
  gate (`southbrook_premium_orchestration.wall_token`, constant-time compare); no-op
  when unset (preserves the documented public POC), lets the owner lock down the
  customer-PII feed without a network change.

### Fixed — cron governance
- **ECO cron user_id (2a).** `data/eco_proposal_cron.xml` — pinned to `base.user_root`.
- **Readiness cron isolation (2b).** `models/project_task.py` — per-task `try/except`
  so one bad task doesn't abort the root-run sweep (+ module `_logger`).

### Fixed — correctness
- **create() template asymmetry (create-sym).** `models/project_task_template_spawn.py`
  — `create` now applies an explicitly-set `x_kitchen_job_template_id` (idempotent),
  matching `write`; a task created *with* a template previously spawned no subtasks.

### Tests
- Cleared all 14 baseline ERRORs (sibling governance gates the tests predate): bypass
  this module's MO availability gate (`bypass_availability_gate` context / the
  `southbrook.mo_availability_gate.enabled=0` param) and satisfy southbrook_mrp_pm's
  approval gate (`force_production_release`) across test_phase1_spine,
  test_phase2_practical_loop, test_p1_auto_emit_cutlist, test_golden_path_all_flags_on.
- test_phase3_generative.test_template_idempotent now passes (create-sym fix).

### Not changed (documented in REVIEW_REPORT.md)
- 8 pre-existing assertion failures (test-isolation seed-collision + cross-module
  behavioral drift — SKU grammar / cutlist count / duration / lifecycle threshold);
  2c ECO HTML sanitization (verify field type in plm); 3d AI cost cap (sibling client);
  5 ops.event spoofing; 6a cut.spec.override ACL; 4 backlink company scoping; 1b wall
  error text.

### Manifest
- Version `19.0.4.7.0` → `19.0.4.8.0`.
