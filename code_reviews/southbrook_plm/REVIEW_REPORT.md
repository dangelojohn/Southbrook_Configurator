# Code Review — `southbrook_plm` (Module #15, Tier 3)

**Version:** 19.0.1.3.0 → **19.0.2.0.0**
**Reviewed:** 2026-07-11
**Scope:** ~1635 LOC — ECO workflow (`southbrook.eco`/`.eco.stage`/`.eco.type`), template-BoM version control, versioned `southbrook.cut.spec`, sale.order/line & mrp.bom extensions, security groups. No controllers.
**Method:** Two independent parallel audits (v19-compat + code; security + performance); every HIGH/MEDIUM claim re-verified against source before editing.

---

## Executive Summary

A lightweight PLM: an ECO change-control gate over production BoMs + cut specs. The v19-compat audit found it **CLEAN** (v19-aware `res.groups` sans `category_id`, `models.Constraint`/`@api.constrains`, `@api.model_create_multi`, correct `mrp.bom.copy()` versioning, all cross-module xpaths resolve). It's the **best-governed** custom module reviewed so far — proper **group-scoped ACL** (nothing to `base.group_user`), approver-gated `action_approve`/`action_apply`, and an existing (partial) workflow-bypass guard.

But the security audit found the guard **had a hole**: terminal ECO states were forgeable by direct write, and two lifecycle actions were ungated. Fixed **1 HIGH forge + 1 HIGH audit-wipe + 1 HIGH concurrency race + 3 MEDIUM** (all internal-user-gated integrity/SoD — no path drives a privileged production rewrite). Install + upgrade clean; **21/21 tests green** with 3 new regression tests.

---

## Original Issues Found

### Fixed

| # | Sev | Title | Root cause |
|---|-----|-------|-----------|
| H1 | HIGH (integrity) | Terminal ECO state forgeable by direct write | `write()` guarded the `stage_id`→terminal path only when `state` didn't match, so `write({"stage_id":applied,"state":"applied"})` slipped through; the approval gate only fired when the *current* stage had `approval_required` (only "Under Review" does). A non-approver (`group_southbrook_plm_user` has `perm_write`) could forge `state=applied` with **no handler run** (no BoM copy), blank `approver_id`. |
| H2 | HIGH (audit) | `action_reset_draft` ungated → wipes approval provenance | No `has_group` check (only the UI button carried `groups=`, which RPC ignores). A non-approver could reset an *applied* ECO and erase `approver_id`/`approval_date`/`applied_date` while the real BoM archive/version persisted. |
| H3 | HIGH (concurrency) | TOCTOU race in `_apply_bom` → two active BoMs | `old = bom.sudo(); new = old.copy(v+1); old.write(active=False)` with no lock. Two ECOs applying to the same BoM both read version N, both create active N+1, both archive → two active BoMs, breaking the one-active-per-template invariant the confirm-snapshot relies on. |
| M2 | MEDIUM (safety) | Apply could target an already-archived BoM | `bom_id` unscoped; `_apply_bom` archived whatever it pointed at with no active-check → double-archive/orphan possible. |
| M3 | MEDIUM (SoD) | `action_reject` ungated | Any PLM User could reject any ECO (no `has_group`, no creator≠rejecter). |
| M4 | MEDIUM (perf) | N+1 BoM search in confirm-time snapshot | `sale_order_line._capture` did `Bom.search(...)` per line at `action_confirm` (40-line order → 40 queries). |

### Documented (not applied)

| # | Sev | Title | Why not auto-fixed |
|---|-----|-------|--------------------|
| D1 | MEDIUM | `southbrook.cut.spec` has no upper/plausibility bounds on tolerances (`_check_positive` only rejects ≤0) | A fat-finger (`box_th=999`) flows to production cut math. Real, but the correct min/max bands are **Southbrook's authoritative tolerance ranges** — guessing them risks rejecting legit values. Only approvers write specs. Recommend a per-field band table (owner input). |
| D2 | MEDIUM | `eco_stage_data.xml` not `noupdate` → `-u` rewrites seeded stages | The header comment says it's intentional (flag-tuning on upgrade); it clobbers admin renames of seeded stages. A data-lifecycle decision — confirm intent, then `noupdate="1"` or tighten the README. |
| D3 | MEDIUM | `cut.spec` single-active enforced by `@api.constrains`, not a DB constraint (M5) | Concurrent `action_activate` can interleave. Same root cause as H3 but rarer (approver-only, infrequent). Recommend a row/advisory lock in `action_activate`. |
| D4 | LOW | No `ir.rule` company scoping (M6); non-stored count computes lack `@api.depends`; `(4,id)` vs `(6,0,ids)` in MO-flag; no `privilege_id` on groups | Single-company Southbrook; cosmetic/hygiene. |
| D5 | MEDIUM | `bom_id` not domain-restricted to "canonical template BoMs" | The archived-check (M2 fix) covers the concrete hazard; a full domain needs a precise definition of "template BoM" (owner input). |

---

## Repairs Completed
- **H1** — rewrote the ECO `write()` guard: terminal `state` (applied/rejected) OR `stage_id`→a final stage is refused unless the `plm_lifecycle` context flag is set. `action_apply`/`action_reject` set that flag on their (approver-gated, handler-run) writes. Covers both the state and stage_id paths; `action_advance` (non-final only) is unaffected.
- **H2 / M3** — added `has_group(group_southbrook_plm_approver)` gates to `action_reset_draft` and `action_reject`.
- **H3 / M2** — `_apply_bom` now `SELECT … FOR UPDATE`-locks the BoM row, re-reads, and refuses if it was archived by a concurrent apply, before copy/archive.
- **M4** — `_capture` batches the active-BoM lookup into one `search([("product_tmpl_id","in",…)])` + a `{tmpl: bom}` map.

## Files Changed
`models/southbrook_eco.py`, `models/sale_order_line.py`, `tests/test_eco_workflow.py` (+3 tests), `__manifest__.py`.

## Database Impact
- No schema/migration; no new fields/constraints/indexes. `FOR UPDATE` is a runtime lock only.

## Security Improvements
- ECO terminal states can no longer be forged (H1); provenance can't be wiped by non-approvers (H2); reject is approver-gated (M3).
- Residual (documented): D1 (spec bounds), D3 (activation race), D5 (bom_id domain), D4 (multi-company).

## Performance Improvements
- Confirm-time snapshot: N BoM searches → **1** (M4).

## Remaining Risks
- **H3 residual**: the FOR UPDATE lock serialises applies but there is still no DB unique constraint (deliberately — Odoo legitimately allows multiple BoMs per template, so a global unique would break core usage). The lock closes the realistic race.
- **D1**: unbounded tolerances remain until the owner supplies real bands.

## Recommendations (priority)
1. **D1** — supply per-field min/max tolerance bands for `southbrook.cut.spec`.
2. **D3** — lock `cut.spec.action_activate` (same pattern as H3).
3. **D2** — decide `eco_stage_data` `noupdate` intent.
4. **D5** — domain-restrict `bom_id` once "template BoM" is defined.
