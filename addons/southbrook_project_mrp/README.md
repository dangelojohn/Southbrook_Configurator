# Southbrook Project ↔ Manufacturing

Job/coordination layer ABOVE MRP. Does **not** rebuild manufacturing logic.

- **T1.1** `project.task.production_ids` ↔ `mrp.production.project_task_id` (a job spans several MOs).
- **T1.2** read-only roll-up on the task (MO states, component availability, refs, cost) — pulled from mrp/stock/costing.
- **T1.3** confirming a sale that drives manufacturing auto-creates/links the job task and its MOs.

Reuses the MO's existing CAD / Intelligence / Production-Costs / Shop-Floor tabs — never duplicates them.
