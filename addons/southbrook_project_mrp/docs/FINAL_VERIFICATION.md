# Southbrook Project 9/10 Verification Map

This document maps the Southbrook Project command-center changes to the
original 9/10 acceptance criteria.

## Required Automated Verification

Run from the repository root after Docker/OrbStack is available:

```bash
make test-quick MODULES=southbrook_project_mrp
```

Expected result: Odoo starts, updates `southbrook_project_mrp`, and the focused
Southbrook Project/MRP tests pass.

Local static checks used during implementation:

```bash
python3 -m py_compile \
  addons/southbrook_project_mrp/models/data_quality_report.py \
  addons/southbrook_project_mrp/models/project_job_template.py \
  addons/southbrook_project_mrp/models/project_project.py \
  addons/southbrook_project_mrp/models/project_readiness_line.py \
  addons/southbrook_project_mrp/models/project_task.py \
  addons/southbrook_project_mrp/tests/test_integration.py

python3 - <<'PY'
from pathlib import Path
from lxml import etree
for path in [
    'addons/southbrook_project_mrp/views/project_task_views.xml',
    'addons/southbrook_project_mrp/views/data_quality_report_views.xml',
    'addons/southbrook_project_mrp/data/project_job_templates.xml',
]:
    etree.parse(str(Path(path)))
    print(f'xml ok: {path}')
PY

git diff --check -- addons/southbrook_project_mrp
```

## Manual Pilot Verification

Use `docs/ROLLOUT_PILOT.md` for the S00235 pilot checklist.

The pilot job should remain blocked/review while these facts remain true:

- CAD/cutlist is not approved.
- WOs are unscheduled.
- Crew is not assigned/reserved.
- Install due date is not surfaced.
- MOs are late or at risk.

## Rating Evidence

| Area | Target | Evidence |
| --- | --- | --- |
| UX/UI | 9/10 | Kanban/list/form expose readiness, score, risk, blocker, next action, source, customer, install, MO/WO counts, release/install state, and family progress. |
| Features | 9/10 | Production release checklist, install readiness checklist, what-can-start-today, CAD/scheduling/crew/install/material/equipment/capacity queues, and Data QA dry run are available. |
| Cabinet Manufacturing Fit | 9/10 | Cabinet specs, family progress, cabinet job templates, production release gates, quality/remake visibility, and rework/scrap/unbuild drill-through are surfaced from the job. |
| PM Decision Support | 9/10 | Readiness decision, score caps, risk level/reason, top blocker, next best action, stage mismatch, and project-level queue actions support daily triage. |
| Practical Intelligence | 9/10 | Readiness evidence lines explain each decision with status, reason, evidence, recommended action, and severity. Recommendations are deterministic and evidence-based. |
| Rollout Readiness | 9/10 | Dry-run data-quality reporting, safe cleanup exclusion flags, S00235 pilot runbook, role checks, and focused tests make rollout trainable and auditable. |

## Production Safety

- Manufacturing remains the system of record for MOs, WOs, BoMs, components,
  work centers, capacity, scrap, and unbuild records.
- Project provides the PM command surface and does not rename core Odoo models.
- Data QA does not delete records.
- Safe cleanup only excludes confirmed demo/reference scrap or unbuild records
  from Southbrook PM reports and records a cleanup note.
- Operational findings stay manual until a user fixes the source record.
