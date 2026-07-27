# Unwired tests — read before adding these to `__init__.py`

`test_bulkbar_gating.py`, `test_loaderror_safety.py`,
`test_t3_commit_warnings.py` and `test_template_compile.py` are present
but **deliberately not imported** by `__init__.py`, so they do not run.

They were recovered from `feature/prodboard-tier-2-mi-quality`, which
authored them against that branch's `southbrook_configurator_ux` 19.0.7.x
lineage. Main's addon is 19.0.6.2.0, re-imported by an audit pass and then
extended from the configurator-loop lineage — a different ancestry.

Wiring them was attempted and measured on 2026-07-26:

| test | ran | failed |
|---|---|---|
| `test_bulkbar_gating` | 0 | 0 (collected nothing) |
| `test_loaderror_safety` | 4 | 4 |
| `test_t3_commit_warnings` | 5 | 5 |
| `test_template_compile` | 3 | 1 |

10 failures — a lineage mismatch, not a quick repair. They are kept
because the intent they encode is worth having; porting them to main's
lineage is real work, not a wiring change.
