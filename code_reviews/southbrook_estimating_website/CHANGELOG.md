# CHANGELOG — `southbrook_estimating_website`

## 19.0.31.4.0 — 2026-07-11 — Code-review pass (Module #18)

### Security
- **[HIGH] `send_to_manufacturing` is staff-only + approval-gated.** The action now
  rejects `share=True` (portal customer / dealer) callers and, when
  southbrook_mrp_pm is installed, requires `production_approval_state == 'approved'`
  (guarded on field presence). Previously any order-owner in the partner chain could
  release an order to the shop floor under sudo with only a state check. `controllers/main.py`.
- **[MEDIUM] `set-customer` is internal-only.** Rejects `share=True` callers — it
  backfills a matched-by-email partner's blank PII from the payload with
  trusted=True. `controllers/main.py`.

### Changed (v19)
- **`type="json"` → `type="jsonrpc"`** on 34 routes (main.py ×26, room_api.py ×8).
- Added `auth_passkey` to `depends` (auth_template.xml inherits it; was auto_install-implicit).

### Tests
- Added `test_portal_user_cannot_send_to_manufacturing` (HIGH-1 regression) — passes.

### Notes (documented, not changed)
- Self-serve variant creation bypasses OCA config-rules (wrong price until confirm,
  which re-validates; + variant-table bloat) — HIGH-2, needs a 4-site refactor + GC.
- Public docs PDF CPU-DoS (MEDIUM-2); N+1 per-line BoM search in the order payload
  (MEDIUM-3); order-creation on GET / unrate-limited session-create (LOW-1/2).
- Pricing is server-side and IDOR is closed — verified, unchanged.
- 2 pre-existing cross-module test failures (panel-count / design_3d_tab fixture),
  confirmed on unmodified HEAD; not regressions.
