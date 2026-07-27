# Southbrook UX Carryover Backlog

This backlog keeps broader UX and workflow findings separate from targeted
module patches. Items here should be triaged into their own tickets before code
changes.

## Current Focus Split

Configuration Sets are handled in `southbrook_estimating` as seed data only:
starter Product Configurator/MRP condition sets are available for production
review, but they are not linked to BoM lines yet.

The remaining items below are separate from that seed decision.

## Open Carryover Items

| Area | Finding | Notes |
|---|---|---|
| Navigation | Southbrook Estimating launcher opens the configurator instead of the intended module surface. | Verify action/menu binding and first route after module load. |
| 3D Preview | Order-level 3D Kitchen Preview can render blank. | Needs browser/runtime asset investigation. |
| MI Dashboard | Blocked/Warnings counts appear global, not per-workcenter. | Confirm intended dashboard scope before changing aggregation. |
| PM Ready Queue | Historical MOs may still be unlinked to kitchen jobs/install dates. | Approval-created MOs should be linked going forward; historical backfill may be separate. |
| PLM/ECO | ECO Target BoM is required but can be empty. | Validate defaulting or relax required state by stage. |
| Risk Views | Top Blocker duplicates Risk Reason. | De-duplicate labels or fields in the project/readiness view. |
| Install Risk | At Risk jobs missing from Install Risk view. | Check domain against readiness score/risk fields. |
| Catalog Hygiene | Duplicate Double-Door and Single-Door templates were observed. | Confirm whether duplicates are seed data, test artifacts, or variants. |
| Variant Economics | Configured variants can show Cost $0, Margin 100%, and no Sales tax. | Needs costing/tax default audit. |
| Performance | 3-5s lag observed with no inline spinners. | Add deterministic loading states after measuring slow RPCs. |
| Configurator Inputs | Fields lack visible input affordance. | UX polish; keep separate from rule enforcement. |
| Wizard Copy | Final wizard step says Next instead of Confirm. | Low-risk label/state change once final-step logic is located. |
| Kanban | Kanban card clicks can be unreliable. | Needs reproduction with browser trace. |
| Approval Buttons | Approve/Reject buttons exist but may fail to appear on first paint. | Likely load/permission timing; make render deterministic. |
| Readiness Evidence | Checklist may not auto-populate on first load. | Existing Refresh Readiness Evidence works; investigate initial compute/load timing. |
| Job Templates | Apply Template gives no confirmation/re-apply guard; sub-tasks lack owners/dates. | Add confirmation, idempotency guard, and scheduling defaults after owner/date policy is decided. |
| Hermes BOM | Hermes API key is not configured in production. | Setup/config item, not a code defect unless fallback behavior is desired. |

## Closed Or Downgraded From Earlier Runs

| Earlier Finding | Updated Status |
|---|---|
| No Approve/Reject buttons | Corrected: buttons exist, but first-paint reliability still needs polish. |
| Request Production creates no MOs | Corrected: approval creates the MO; Request Production is an approval request. |
| Readiness checklist empty | Corrected: evidence populates after refresh; first-load timing remains open. |
| Configuration Sets empty | Addressed by seed data in `southbrook_estimating` 19.0.4.2.0; BoM attachment remains a production decision. |
