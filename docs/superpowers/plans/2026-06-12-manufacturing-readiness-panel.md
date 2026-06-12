# Manufacturing Readiness Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only Manufacturing Readiness command panel to `project.task` so a production manager can decide whether a job is ready, needs review, or is blocked.

**Architecture:** Extend `southbrook_project_mrp` only. Compute readiness from existing linked MOs, WOs, procurement, maintenance, crew, cost, and MI fields already surfaced on `project.task`; do not rebuild MRP, automate purchases, alter security, or touch Project overview Kanban.

**Tech Stack:** Odoo 19 Community, Python ORM computed fields, XML form inheritance, existing `southbrook_project_mrp` tests and live task `#182`.

---

### Task 1: Readiness Computation

**Files:**
- Modify: `addons/southbrook_project_mrp/models/project_task.py`
- Test: `addons/southbrook_project_mrp/tests/test_integration.py`

- [ ] **Step 1: Write the failing test**

Add this test to `TestProjectMrpIntegration`:

```python
    def test_manufacturing_readiness_decision_blocks_unscheduled_job(self):
        task = self.env["project.task"].create({
            "name": "Readiness Job",
            "project_id": self.project.id,
        })
        wc = self.env["mrp.workcenter"].create({"name": "Panel Saw"})
        mo = self._make_mo()
        mo.project_task_id = task.id
        self.env["mrp.workorder"].create({
            "name": "Cut panels",
            "production_id": mo.id,
            "workcenter_id": wc.id,
            "duration_expected": 12.0,
        })

        task.invalidate_recordset()

        self.assertEqual(task.manufacturing_readiness_state, "blocked")
        self.assertLess(task.manufacturing_readiness_score, 100)
        self.assertIn("Scheduling", task.manufacturing_blocker_summary)
        self.assertIn("not scheduled", task.manufacturing_blocker_summary)
        self.assertIn("Scheduling", task.manufacturing_waterfall_summary)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
make test-quick MODULES=southbrook_project_mrp ODOO_FLAGS="--db_host=db --db_user=odoo --db_password='$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2)' --stop-after-init --no-http --http-port=8899 --gevent-port=8902 --workers=0 --max-cron-threads=0 --test-tags=/southbrook_project_mrp:TestProjectMrpIntegration.test_manufacturing_readiness_decision_blocks_unscheduled_job"
```

Expected: FAIL because `manufacturing_readiness_state` does not exist.

- [ ] **Step 3: Implement minimal compute fields**

Add these fields to `ProjectTask`:

```python
    manufacturing_readiness_score = fields.Integer(
        string="Readiness Score", compute="_compute_manufacturing_readiness")
    manufacturing_readiness_state = fields.Selection(
        [("ready", "Ready"), ("review", "Review"), ("blocked", "Blocked")],
        string="Readiness Decision", compute="_compute_manufacturing_readiness")
    manufacturing_waterfall_summary = fields.Text(
        string="Waterfall Readiness", compute="_compute_manufacturing_readiness")
    manufacturing_blocker_summary = fields.Text(
        string="Start Blockers", compute="_compute_manufacturing_readiness")
    manufacturing_warning_summary = fields.Text(
        string="Manager Review", compute="_compute_manufacturing_readiness")
    manufacturing_info_summary = fields.Text(
        string="Efficiency Prompts", compute="_compute_manufacturing_readiness")
```

Add `_compute_manufacturing_readiness` using existing fields:

```python
    @api.depends(
        "production_count",
        "job_cad_status",
        "material_at_risk",
        "procurement_count",
        "unscheduled_workorder_count",
        "crew_gap",
        "equipment_blocked",
        "workcenter_over_capacity",
        "job_at_risk",
        "job_install_due",
        "manufacturing_calculation_count",
    )
    def _compute_manufacturing_readiness(self):
        for task in self:
            gates = []
            blockers = []
            warnings = []
            infos = []

            def gate(name, state, note):
                gates.append("%s: %s - %s" % (name, state, note))

            if not task.production_count:
                gate("MRP Link", "BLOCKED", "no linked manufacturing orders")
                blockers.append("MRP Link: no linked manufacturing orders")
            else:
                gate("MRP Link", "READY", "%d linked MO(s)" % task.production_count)

            if task.job_cad_status and "done" not in task.job_cad_status.lower():
                gate("Engineering / CAD", "REVIEW", task.job_cad_status)
                warnings.append("Engineering / CAD: review CAD status")
            else:
                gate("Engineering / CAD", "READY", task.job_cad_status or "no open CAD issue")

            if task.material_at_risk:
                gate("Materials / Purchasing", "BLOCKED", "material is at risk")
                blockers.append("Materials / Purchasing: material shortfall")
            elif task.procurement_count:
                gate("Materials / Purchasing", "REVIEW", "%d procurement order(s)" % task.procurement_count)
                warnings.append("Materials / Purchasing: review open procurement")
            else:
                gate("Materials / Purchasing", "READY", "components/procurement clear")

            if task.unscheduled_workorder_count:
                gate("Scheduling", "BLOCKED", "%d work order(s) not scheduled" % task.unscheduled_workorder_count)
                blockers.append("Scheduling: %d work order(s) not scheduled" % task.unscheduled_workorder_count)
            else:
                gate("Scheduling", "READY", "work orders scheduled")

            if task.crew_gap:
                gate("Crew", "REVIEW", "operator assignment gap")
                warnings.append("Crew: assign/reserve operators")
            else:
                gate("Crew", "READY", "crew assignment clear")

            if task.equipment_blocked:
                gate("Equipment / Tooling", "BLOCKED", "open maintenance condition")
                blockers.append("Equipment / Tooling: maintenance block")
            else:
                gate("Equipment / Tooling", "READY", "equipment clear")

            if task.workcenter_over_capacity:
                gate("Production Capacity", "REVIEW", "work-center load over daily capacity")
                warnings.append("Production Capacity: review overloaded work center")
            elif task.job_at_risk:
                gate("Production Capacity", "REVIEW", task.job_risk_reason or "job at risk")
                warnings.append("Production Capacity: review job risk")
            else:
                gate("Production Capacity", "READY", "no capacity/risk flag")

            if not task.job_install_due:
                gate("Delivery / Install", "INFO", "no install due date surfaced")
                infos.append("Delivery / Install: confirm install date and site readiness")
            else:
                gate("Delivery / Install", "READY", "install due %s" % task.job_install_due)

            if not task.manufacturing_calculation_count:
                infos.append("Calculations: run/review Manufacturing Intelligence checks")

            task.manufacturing_waterfall_summary = "\n".join(gates)
            task.manufacturing_blocker_summary = "\n".join(blockers) or "No start blockers."
            task.manufacturing_warning_summary = "\n".join(warnings) or "No manager-review warnings."
            task.manufacturing_info_summary = "\n".join(infos) or "No efficiency prompts."
            task.manufacturing_readiness_state = "blocked" if blockers else ("review" if warnings else "ready")
            penalty = len(blockers) * 25 + len(warnings) * 10
            task.manufacturing_readiness_score = max(0, min(100, 100 - penalty))
```

- [ ] **Step 4: Run focused test to verify it passes**

Run the same `make test-quick ...test_manufacturing_readiness_decision_blocks_unscheduled_job` command.

Expected: PASS.

---

### Task 2: Project Task Form Panel

**Files:**
- Modify: `addons/southbrook_project_mrp/views/project_task_views.xml`
- Test: `addons/southbrook_project_mrp/tests/test_integration.py`

- [ ] **Step 1: Write the failing view test**

Add this assertion to `test_project_task_exposes_manufacturing_calculations` or create a new test:

```python
    def test_project_task_form_has_manufacturing_readiness_panel(self):
        view = self.env.ref("southbrook_project_mrp.project_task_form_mrp")
        arch = view.arch_db
        self.assertIn("Manufacturing Readiness", arch)
        self.assertIn("manufacturing_readiness_score", arch)
        self.assertIn("manufacturing_waterfall_summary", arch)
        self.assertIn("manufacturing_blocker_summary", arch)
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL because the XML panel is absent.

- [ ] **Step 3: Add the panel**

Insert this panel near the top of the Manufacturing/Work Orders page, before detailed work-order rollups:

```xml
                    <group string="Manufacturing Readiness">
                        <group>
                            <field name="manufacturing_readiness_state"
                                   widget="badge"
                                   decoration-success="manufacturing_readiness_state == 'ready'"
                                   decoration-warning="manufacturing_readiness_state == 'review'"
                                   decoration-danger="manufacturing_readiness_state == 'blocked'"
                                   readonly="1"/>
                            <field name="manufacturing_readiness_score" readonly="1"/>
                        </group>
                        <group>
                            <field name="manufacturing_blocker_summary"
                                   nolabel="1" readonly="1" widget="text"/>
                        </group>
                        <field name="manufacturing_waterfall_summary"
                               nolabel="1" readonly="1" widget="text"/>
                        <field name="manufacturing_warning_summary"
                               nolabel="1" readonly="1" widget="text"/>
                        <field name="manufacturing_info_summary"
                               nolabel="1" readonly="1" widget="text"/>
                    </group>
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
make test-quick MODULES=southbrook_project_mrp ODOO_FLAGS="--db_host=db --db_user=odoo --db_password='$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2)' --stop-after-init --no-http --http-port=8899 --gevent-port=8902 --workers=0 --max-cron-threads=0 --test-tags=/southbrook_project_mrp:TestProjectMrpIntegration.test_project_task_form_has_manufacturing_readiness_panel"
```

Expected: PASS.

---

### Task 3: Deploy And Verify Live

**Files:**
- Deploy module directory: `addons/southbrook_project_mrp/`

- [ ] **Step 1: Deploy**

```bash
rsync -avz addons/southbrook_project_mrp/ admin@192.168.68.108:/share/CACHEDEV3_DATA/Container/southbrook/addons/southbrook_project_mrp/
ssh admin@192.168.68.108 'sudo /share/CACHEDEV3_DATA/.qpkg/container-station/bin/system-docker exec -d southbrook-odoo bash -lc "odoo -d southbrook -u southbrook_project_mrp --stop-after-init --no-http --workers=0 --max-cron-threads=0"'
```

- [ ] **Step 2: Verify task #182**

Run an Odoo shell script that prints:

```python
task = env["project.task"].browse(182)
print(task.manufacturing_readiness_state)
print(task.manufacturing_readiness_score)
print(task.manufacturing_blocker_summary)
print(task.manufacturing_waterfall_summary)
```

Expected: task opens and prints a decision/score; current data should likely be `blocked` because 47 WOs are not scheduled.

- [ ] **Step 3: Commit and push**

```bash
git add addons/southbrook_project_mrp/models/project_task.py addons/southbrook_project_mrp/views/project_task_views.xml addons/southbrook_project_mrp/tests/test_integration.py
git commit -m "feat(project-mrp): add manufacturing readiness gates"
git push origin HEAD:main
```

