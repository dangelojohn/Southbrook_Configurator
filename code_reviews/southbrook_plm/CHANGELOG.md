# CHANGELOG — `southbrook_plm`

## 19.0.2.0.0 — 2026-07-11 — Code-review pass (Module #15)

### Security / integrity
- **[HIGH] ECO terminal states can no longer be forged by direct write.** The
  `write()` guard now refuses any write that sets `state` to applied/rejected —
  or `stage_id` to a final stage — unless made through the gated Apply/Reject
  actions (which set an internal `plm_lifecycle` flag after running the change
  handlers + enforcing approver rights). Previously
  `write({"stage_id":applied,"state":"applied"})` slipped through, letting a
  non-approver forge an "applied" ECO with no BoM copy and blank approver.
  `models/southbrook_eco.py`.
- **[HIGH] `action_reset_draft` is approver-gated.** It clears
  approver/approval/applied stamps, so a plain PLM User could previously wipe
  the change-control provenance of an applied ECO. `models/southbrook_eco.py`.
- **[HIGH] `_apply_bom` serialises concurrent applies.** `SELECT … FOR UPDATE`
  locks the BoM row and re-checks `active` before copy/archive, so two ECOs
  applying to the same BoM can't both create an active v+1 (was a TOCTOU race
  producing two active BoMs). Also refuses applying to an already-archived BoM.
  `models/southbrook_eco.py`.
- **[MEDIUM] `action_reject` is approver-gated** (was ungated — any PLM User
  could reject any ECO). `models/southbrook_eco.py`.

### Performance
- **[MEDIUM] Confirm-time BoM snapshot** batches the active-BoM lookup into one
  grouped search keyed by template (was a `search()` per order line).
  `models/sale_order_line.py`.

### Tests
- Added `test_direct_write_cannot_forge_terminal_state`,
  `test_plain_user_cannot_reject`, `test_plain_user_cannot_reset_applied_eco`.
- Result: **21/21 green** (install + upgrade), all existing ECO/BoM/cut-spec
  tests still pass with the new lock + guards.

### Notes (documented, not changed)
- `southbrook.cut.spec` still has no upper/plausibility bounds on tolerances —
  needs Southbrook's authoritative min/max ranges (D1).
- `eco_stage_data.xml` is not `noupdate` (rewrites seeded stages on `-u`) — a
  documented data-lifecycle decision (D2).
- cut-spec single-active is `@api.constrains`-only (activation race, D3);
  `bom_id` not domain-restricted (D5); no multi-company record rules (D4).
