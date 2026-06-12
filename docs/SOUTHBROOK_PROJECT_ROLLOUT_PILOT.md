# Southbrook Project Command Center Rollout Pilot

This pilot validates the Project module as the PM command surface while
Manufacturing remains the system of record.

## Pilot Job

Use job `S00235` for the manual pilot. Do not delete, merge, or rewrite
production records during the pilot.

## Preflight

1. Update `southbrook_project`.
2. Run the focused test target:

   ```bash
   make test-mrp-command
   ```

3. Open `Southbrook PM > Data Quality Dry Run`.
4. Run the server action `Generate Southbrook Data Quality Dry Run`.
5. Review blocker issues before training users:
   - blank Kitchen Project
   - blank Install Due
   - placeholder cost
   - demo scrap/unbuild records
   - queue overlap
   - equipment count mismatch

## S00235 Manual QA

1. Open `Southbrook PM > Daily Production Meeting`.
2. Search for `S00235`.
3. Confirm the queue shows:
   - readiness decision
   - score
   - blocking gate
   - checklist state
   - next action
   - job type
   - cabinet family
   - install due
4. Open the Project task form.
5. Confirm the header shows:
   - readiness state
   - Release to Production
   - Recompute Readiness
   - Family Progress
6. Open `Cabinetry Specs`.
7. Confirm structured specs are present:
   - job type
   - cabinet family
   - material/species
   - unit count
   - install due
   - hardware/spec summary
8. Open `Manufacturing Command`.
9. Confirm the PM can understand why the job is ready, at risk, or blocked
   without opening Manufacturing.
10. Open `Release Checklist`.
11. Leave one required item unchecked and recompute readiness.
12. Confirm the job becomes blocked by that checklist gate.
13. Complete or waive the item and recompute readiness.
14. Confirm the checklist no longer blocks readiness.
15. Click `Family Progress`.
16. Confirm the cabinet-family KPI page opens for the job family.

## Role-Based Smoke Checks

Use one user per role where available:

- PM: can open Daily Production Meeting, Data Quality Dry Run, and Job Templates.
- Shop lead: can open readiness queues and family progress.
- Designer: can read cabinet specs and checklist expectations.
- Installer: can read install due/checklist state.
- Executive: can read queue status and family throughput without editing records.

If dedicated role groups are not configured yet, record that as a rollout
gap instead of changing production ACLs during the pilot.

## Safe Cleanup Rules

- Dry-run reporting creates issue records only.
- `Exclude from PM Reporting` marks the issue excluded.
- `Archive Issue` archives the issue record.
- Neither action deletes the source production record.
- Source data fixes must be handled as explicit operational corrections.

## Before/After Rating Map

| Area | Previous | Target | Evidence |
| --- | ---: | ---: | --- |
| UX/UI | 6.5 | 9 | PM queues now show readiness, blocker, next action, checklist, job type, family, and install due from list/kanban/form. |
| Features | 6.5 | 9 | Job templates, release checklist, readiness gating, daily queues, family progress, and dry-run data quality tools exist. |
| Cabinet Manufacturing Fit | 6.5 | 9 | Cabinet family, material/species, unit count, hardware specs, and family throughput are visible from Project. |
| PM Decision Support | 6.5 | 9 | Readiness score caps, blocking gates, next action, queue filters, and data-quality issues provide deterministic guidance. |
| Practical Intelligence | 6.5 | 9 | Recommendations are rule-based and evidence-backed by checklist, MRP, tooling, MI checks, and install/package state. |
| Rollout Readiness | 6.5 | 9 | Upgrade backfill, dry-run cleanup issues, pilot checklist, and focused tests make the module trainable. |

## Runtime Evidence To Attach

Attach screenshots after live validation:

- Daily Production Meeting filtered to `S00235`
- `S00235` Manufacturing Command tab
- `S00235` Release Checklist tab
- Family Progress page opened from `S00235`
- Data Quality Dry Run grouped by issue type
