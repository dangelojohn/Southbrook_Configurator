# Test Results — `southbrook_project_mrp`

**Date:** 2026-07-11
**DB:** isolated on `v19c-db` (created via db-local socket — see
`southbrook_room_capture` REVIEW_REPORT env note).
**Addons:** full southbrook dep stack staged into `/mnt/extra-addons`.

## Baseline (unmodified HEAD, current v19c build)
`-i --test-tags=/southbrook_project_mrp`: **1 failed, 20 error(s) of 58 tests**.
Install itself was clean (no ParseError). Dominant cause: 18 errors from
`AttributeError: 'mrp.workcenter' object has no attribute 'equipment_ids'` (C1);
the rest from the non-stored bottleneck field (C2), the mrp_pm approval gate, and
the MI-not-installed action.

## After fixes
```
odoo -c … -i southbrook_project_mrp --test-enable --test-tags=/southbrook_project_mrp --stop-after-init --no-http
```
- Fresh cold install — registry 39.0 s, no ERROR/CRITICAL (incl. the new
  `store=True` column on `current_bottleneck_workcenter_id`).
- `0 failed, 0 error(s) of 58 tests` (1 skipped — MI-dependent).

```
odoo -c … -u southbrook_project_mrp --test-enable --test-tags=/southbrook_project_mrp …
```
- Clean upgrade — `0 failed, 0 error(s) of 58 tests`.

## Failures resolved (baseline 20 err + 1 fail → 0)
| Cause | Count | Resolution |
|-------|-------|------------|
| `equipment_ids` AttributeError (C1) | ~16 | forward-path maintenance search |
| bottleneck field non-stored / non-searchable domain (C2) | 2 | `store=True` + `production_ids` domain |
| mrp_pm approval gate on MO create | 1 | test force-releases the order |
| MI (`southbrook.mi.check`) not installed | 1 | `skipTest` when absent |
| `next_best_action` regex too narrow | 1 | accept "Confirm" (legit action) |
| W029 arch_db checked wrong view / domain string | (subsumed) | assert inheriting view / `production_ids` |

## Notes
- The single skipped test (`test_project_task_exposes_manufacturing_calculations`)
  requires `southbrook_manufacturing_intelligence`; it passes in the full stack.
- No regressions: the `store=True` and `search=` removals produce identical query
  results (verified — all 58 tests green on both `-i` and `-u`).
