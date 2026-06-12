# Southbrook Project ↔ Manufacturing

Job/coordination layer ABOVE MRP. Does **not** rebuild manufacturing logic.

- **T1.1** `project.task.production_ids` ↔ `mrp.production.project_task_id` (a job spans several MOs).
- **T1.2** read-only roll-up on the task (MO states, component availability, refs, cost) — pulled from mrp/stock/costing.
- **T1.3** confirming a sale that drives manufacturing auto-creates/links the job task and its MOs.

Reuses the MO's existing CAD / Intelligence / Production-Costs / Shop-Floor tabs — never duplicates them.

## Southbrook 9/10 Command Center

This module now surfaces kitchen-job decision support directly on Project:

- readiness decision, score, blocker, risk, and next best action;
- production release and install readiness checklists;
- cabinet specs, cabinet-family progress, and job templates;
- what-can-start-today, CAD, scheduling, crew, install, material, equipment,
  and capacity queues;
- quality/remake visibility for deficiency notes, rework WOs, warranty/remake
  tasks, scrap, and unbuild/remake records;
- a read-only Data QA dry run for rollout cleanup checks.

See `docs/ROLLOUT_PILOT.md` for the S00235 pilot validation checklist and
safe cleanup rules. See `docs/FINAL_VERIFICATION.md` for the 9/10 acceptance
map and final QA commands.
