# Southbrook Project MRP Rollout Pilot

This runbook validates the Project module as the kitchen job command center
without changing production data by default.

## Pilot Job

- Job: Kitchen Cabinet Set - Shaker Style (Maple) [S00235]
- Source: S00235
- Expected MOs: WH/MO/00085 through WH/MO/00090
- Expected WO count: 47
- Known blockers: CAD pending, WOs unscheduled, crew unassigned, late MOs, no
  surfaced install due date.

The pilot is successful only if the job remains honest about those blockers.
Do not force a green readiness state unless the source data has actually been
fixed.

## Update And Test Locally

Run from the repository root:

```bash
make test-quick MODULES=southbrook_project_mrp
```

If Docker/OrbStack is not running, the command fails before Odoo starts. Start
the local Odoo stack, then rerun the same command.

Update the module in the local dev database:

```bash
docker exec sami-odoo odoo -d southbrook -u southbrook_project_mrp \
  --stop-after-init --no-http --db_host=db --db_user=odoo \
  --db_password='change-me-strong-password'
```

Do not reset, restore, or overwrite user data as part of this rollout.

## Dry-Run Data Quality Report

Open the Project record and click Data QA. The report is read-only and should
not modify production records.

Expected findings include:

- MOs with blank Kitchen Project links.
- Jobs with linked MOs but missing install due dates.
- Jobs with estimated cost of 0.00.
- Demo-looking scrap or unbuild records such as REF records.
- Readiness queue overlap.
- Equipment blocked/count mismatches.

Cleanup policy:

- Do not delete production data.
- Confirm demo records with the business before archiving or excluding them.
- Fix missing links and dates at the source record where possible.
- Rerun Data QA after each cleanup pass and compare findings.

Safe Cleanup button:

- For confirmed demo/reference scrap or unbuild records, the button marks the
  record `Exclude from Southbrook PM Reports` and records a cleanup note.
- For operational findings such as missing install due dates, blank kitchen
  project links, placeholder costs, queue overlap, or equipment mismatches, the
  button marks the finding as manual review only.
- The button does not unlink, delete, reset, or overwrite production records.

## Manual QA

1. Open Project / Kitchen Jobs kanban.
2. Confirm blocked, review, ready, late, and at-risk states are visually clear.
3. Open the Production Control Queue list.
4. Test filters for blocked, ready, CAD/cutlist, scheduling, crew, install,
   materials, equipment, capacity, stage mismatch, and production release.
5. Open the S00235 pilot job.
6. Confirm the header shows source, customer, install due, PM phase,
   manufacturing reality, readiness decision, score, risk, top blocker, and
   next best action.
7. Confirm the Readiness tab explains CAD, scheduling, crew, install, specs,
   and production-release blockers.
8. Confirm the Manufacturing tab shows linked MOs and WOs.
9. Confirm What Can Start Today excludes unscheduled or CAD-blocked work.
10. Confirm Cabinet Specs, Production Release, Install Readiness, and
    Quality / Rework tabs are visible.
11. Confirm warranty/remake tasks, rework WOs, scrap, and unbuild records drill
    through from the command center.
12. Confirm the job does not turn green while the known blockers remain.

## Role Checks

- MRP PM: use PM Queue for decision queues, readiness evidence, and next best
  action.
- Shop lead: use Shop Lead for executable WOs that can start today.
- Designer/engineer: use Design for CAD/cutlist and missing cabinet specs.
- Installer/coordinator: use Install for install date and install-readiness
  review.
- Owner/executive: use Exec for high-risk jobs and project-level throughput.

## Before Production Use

- Run focused tests successfully.
- Update the module in a staging/local database first.
- Capture before/after screenshots of S00235 kanban, list, and form.
- Train users from the pilot job while preserving the real blocker state.
