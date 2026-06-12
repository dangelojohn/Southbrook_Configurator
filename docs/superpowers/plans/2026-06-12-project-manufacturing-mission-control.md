# Project Manufacturing Mission Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/odoo/project` a manufacturing mission-control view by adding project-level readiness counts and intelligence prompts sourced from existing project tasks, MOs, WOs, procurement, and maintenance readiness fields.

**Architecture:** Add a focused `project.project` model extension inside `southbrook_project_mrp` that aggregates already-computed task-level manufacturing facts. Enhance the native Odoo Project Kanban card with read-only chips and a prompt; retain native navigation and security. Do not rebuild MRP, scheduling, purchasing, costing, or access logic.

**Tech Stack:** Odoo 19 Community, Python ORM computed fields, XML inherited views, `TransactionCase` tests, QNAP deployment via `scripts/deploy_to_qnap.sh`.

---

## Files

- Create: `addons/southbrook_project_mrp/models/project_project.py`  
  Responsibility: project-level manufacturing summary fields, prompt severity, and native action helper.
- Modify: `addons/southbrook_project_mrp/models/__init__.py`  
  Responsibility: load the new `project_project` model extension.
- Modify: `addons/southbrook_project_mrp/views/project_task_views.xml`  
  Responsibility: add a `project.project` Kanban inheritance to render manufacturing chips and the prompt on `/odoo/project`.
- Modify: `addons/southbrook_project_mrp/tests/test_integration.py`  
  Responsibility: add regression coverage for project-level aggregation and view/model sync.
- No change: security files. Do not add groups, ACLs, record rules, users, passwords, followers, or visibility settings.

## Task 1: Project-Level Manufacturing Summary Fields

**Files:**
- Create: `addons/southbrook_project_mrp/models/project_project.py`
- Modify: `addons/southbrook_project_mrp/models/__init__.py`
- Test: `addons/southbrook_project_mrp/tests/test_integration.py`

- [ ] **Step 1: Write failing aggregation tests**

Append these tests to `TestProjectMrpIntegration` in `addons/southbrook_project_mrp/tests/test_integration.py`:

```python
    def test_project_manufacturing_summary_empty_project(self):
        project = self.env["project.project"].create({"name": "Empty Plant Board"})
        self.assertEqual(project.southbrook_job_count, 0)
        self.assertEqual(project.southbrook_active_mo_count, 0)
        self.assertEqual(project.southbrook_unscheduled_wo_count, 0)
        self.assertEqual(project.southbrook_intelligence_severity, "neutral")
        self.assertEqual(project.southbrook_intelligence_prompt, "No manufacturing jobs yet")

    def test_project_manufacturing_summary_from_job_tasks(self):
        task = self.env["project.task"].create({
            "name": "Mission Control Job",
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

        self.project.invalidate_recordset()
        self.assertEqual(self.project.southbrook_job_count, 1)
        self.assertEqual(self.project.southbrook_active_mo_count, 1)
        self.assertEqual(self.project.southbrook_unscheduled_wo_count, 1)
        self.assertEqual(self.project.southbrook_crew_gap_count, 1)
        self.assertEqual(self.project.southbrook_intelligence_severity, "warning")
        self.assertIn("planned start", self.project.southbrook_intelligence_prompt)
```

- [ ] **Step 2: Run tests and confirm they fail because fields do not exist**

Run:

```bash
/bin/bash -lc "docker exec sami-odoo odoo -d southbrook -u southbrook_project_mrp --test-enable --test-tags=/southbrook_project_mrp:TestProjectMrpIntegration.test_project_manufacturing_summary_empty_project,/southbrook_project_mrp:TestProjectMrpIntegration.test_project_manufacturing_summary_from_job_tasks --db_host=db --db_user=odoo --db_password='$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2)' --stop-after-init --no-http --http-port=8899 --gevent-port=8902 --workers=0 --max-cron-threads=0"
```

Expected: FAIL with a missing field such as `AttributeError: 'project.project' object has no attribute 'southbrook_job_count'`.

- [ ] **Step 3: Add the project model extension**

Create `addons/southbrook_project_mrp/models/project_project.py`:

```python
# SPDX-License-Identifier: LGPL-3.0-only
from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    southbrook_job_count = fields.Integer(
        string="Manufacturing Jobs", compute="_compute_southbrook_mission_control")
    southbrook_active_mo_count = fields.Integer(
        string="Active MOs", compute="_compute_southbrook_mission_control")
    southbrook_ready_job_count = fields.Integer(
        string="Ready Jobs", compute="_compute_southbrook_mission_control")
    southbrook_at_risk_job_count = fields.Integer(
        string="At-Risk Jobs", compute="_compute_southbrook_mission_control")
    southbrook_material_risk_count = fields.Integer(
        string="Material Risk", compute="_compute_southbrook_mission_control")
    southbrook_unscheduled_wo_count = fields.Integer(
        string="Unscheduled WOs", compute="_compute_southbrook_mission_control")
    southbrook_crew_gap_count = fields.Integer(
        string="Crew Gaps", compute="_compute_southbrook_mission_control")
    southbrook_equipment_blocked_count = fields.Integer(
        string="Equipment Blocks", compute="_compute_southbrook_mission_control")
    southbrook_over_capacity_count = fields.Integer(
        string="Over Capacity", compute="_compute_southbrook_mission_control")
    southbrook_job_cost_total = fields.Monetary(
        string="MO Job Cost", compute="_compute_southbrook_mission_control",
        currency_field="currency_id")
    southbrook_intelligence_prompt = fields.Char(
        string="Manufacturing Prompt", compute="_compute_southbrook_mission_control")
    southbrook_intelligence_severity = fields.Selection(
        [
            ("neutral", "Neutral"),
            ("info", "Info"),
            ("success", "Ready"),
            ("warning", "Review"),
            ("danger", "Stop"),
        ],
        string="Manufacturing Severity",
        compute="_compute_southbrook_mission_control",
    )

    @api.depends(
        "tasks.production_count",
        "tasks.job_at_risk",
        "tasks.components_available",
        "tasks.workorder_count",
        "tasks.unscheduled_workorder_count",
        "tasks.crew_gap",
        "tasks.job_industrial_cost",
        "tasks.material_at_risk",
        "tasks.equipment_blocked",
        "tasks.workcenter_over_capacity",
    )
    def _compute_southbrook_mission_control(self):
        for project in self:
            tasks = project.tasks.filtered(lambda task: task.production_count > 0)
            project.southbrook_job_count = len(tasks)
            project.southbrook_active_mo_count = sum(tasks.mapped("production_count"))
            project.southbrook_ready_job_count = len(tasks.filtered(
                lambda task: task.components_available == "ready"
                and not task.job_at_risk
                and not task.material_at_risk
                and not task.equipment_blocked
            ))
            project.southbrook_at_risk_job_count = len(tasks.filtered("job_at_risk"))
            project.southbrook_material_risk_count = len(tasks.filtered("material_at_risk"))
            project.southbrook_unscheduled_wo_count = sum(
                tasks.mapped("unscheduled_workorder_count"))
            project.southbrook_crew_gap_count = len(tasks.filtered("crew_gap"))
            project.southbrook_equipment_blocked_count = len(tasks.filtered("equipment_blocked"))
            project.southbrook_over_capacity_count = len(tasks.filtered("workcenter_over_capacity"))
            project.southbrook_job_cost_total = sum(tasks.mapped("job_industrial_cost"))
            severity, prompt = project._southbrook_pick_mission_prompt()
            project.southbrook_intelligence_severity = severity
            project.southbrook_intelligence_prompt = prompt

    def _southbrook_pick_mission_prompt(self):
        self.ensure_one()
        if not self.southbrook_job_count:
            return "neutral", "No manufacturing jobs yet"
        if self.southbrook_equipment_blocked_count:
            return "danger", "Stop: equipment blocked on %d job(s)" % (
                self.southbrook_equipment_blocked_count,)
        if self.southbrook_material_risk_count:
            return "danger", "Stop: material shortfall on %d job(s)" % (
                self.southbrook_material_risk_count,)
        if self.southbrook_at_risk_job_count:
            return "warning", "Review: %d job(s) at risk" % (
                self.southbrook_at_risk_job_count,)
        if self.southbrook_unscheduled_wo_count:
            return "warning", "Review: %d WO(s) need planned start" % (
                self.southbrook_unscheduled_wo_count,)
        if self.southbrook_crew_gap_count:
            return "warning", "Review: crew gap on %d job(s)" % (
                self.southbrook_crew_gap_count,)
        if self.southbrook_over_capacity_count:
            return "warning", "Review: work-center load over capacity on %d job(s)" % (
                self.southbrook_over_capacity_count,)
        return "success", "Clear: material, crew, and equipment ready"

    def action_southbrook_open_manufacturing_jobs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Manufacturing Jobs - %s" % self.display_name,
            "res_model": "project.task",
            "domain": [
                ("project_id", "=", self.id),
                ("production_count", ">", 0),
            ],
            "view_mode": "kanban,list,form",
            "context": {"create": False},
        }
```

- [ ] **Step 4: Import the new model**

Modify `addons/southbrook_project_mrp/models/__init__.py`:

```python
from . import mrp_production
from . import mrp_workorder
from . import project_project
from . import project_task
from . import sale_order
```

- [ ] **Step 5: Run the two focused tests**

Run the command from Step 2 again.

Expected: PASS, or Odoo reports no Python exception and no test failure for these two methods.

- [ ] **Step 6: Commit Task 1**

```bash
git add addons/southbrook_project_mrp/models/__init__.py addons/southbrook_project_mrp/models/project_project.py addons/southbrook_project_mrp/tests/test_integration.py
git commit -m "feat(project-mrp): add project mission control rollups"
```

## Task 2: Project Kanban Manufacturing Card UX

**Files:**
- Modify: `addons/southbrook_project_mrp/views/project_task_views.xml`
- Test: `addons/southbrook_project_mrp/tests/test_integration.py`

- [ ] **Step 1: Write failing view test**

Append this test to `TestProjectMrpIntegration`:

```python
    def test_project_kanban_has_mission_control_fields(self):
        view = self.env.ref(
            "southbrook_project_mrp.project_project_kanban_mission_control")
        arch = view.arch_db
        self.assertIn("southbrook_intelligence_prompt", arch)
        self.assertIn("southbrook_unscheduled_wo_count", arch)
        self.assertIn("southbrook_equipment_blocked_count", arch)
        self.assertIn("action_southbrook_open_manufacturing_jobs", arch)
```

- [ ] **Step 2: Run the view test and confirm it fails**

Run:

```bash
/bin/bash -lc "docker exec sami-odoo odoo -d southbrook -u southbrook_project_mrp --test-enable --test-tags=/southbrook_project_mrp:TestProjectMrpIntegration.test_project_kanban_has_mission_control_fields --db_host=db --db_user=odoo --db_password='$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2)' --stop-after-init --no-http --http-port=8899 --gevent-port=8902 --workers=0 --max-cron-threads=0"
```

Expected: FAIL because `southbrook_project_mrp.project_project_kanban_mission_control` does not exist yet.

- [ ] **Step 3: Add the inherited Project Kanban view**

Append this record inside `<odoo>` in `addons/southbrook_project_mrp/views/project_task_views.xml`, after the existing `project_task_kanban_mrp` record:

```xml
    <record id="project_project_kanban_mission_control" model="ir.ui.view">
        <field name="name">project.project.kanban.southbrook.mission.control</field>
        <field name="model">project.project</field>
        <field name="inherit_id" ref="project.view_project_kanban"/>
        <field name="arch" type="xml">
            <xpath expr="//templates" position="before">
                <field name="southbrook_job_count"/>
                <field name="southbrook_active_mo_count"/>
                <field name="southbrook_ready_job_count"/>
                <field name="southbrook_at_risk_job_count"/>
                <field name="southbrook_material_risk_count"/>
                <field name="southbrook_unscheduled_wo_count"/>
                <field name="southbrook_crew_gap_count"/>
                <field name="southbrook_equipment_blocked_count"/>
                <field name="southbrook_over_capacity_count"/>
                <field name="southbrook_job_cost_total"/>
                <field name="southbrook_intelligence_prompt"/>
                <field name="southbrook_intelligence_severity"/>
            </xpath>
            <xpath expr="//footer" position="before">
                <div class="o_southbrook_project_mission mt-2"
                     t-if="record.southbrook_job_count.raw_value">
                    <div class="small fw-semibold mb-1"
                         t-att-class="{
                            'text-danger': record.southbrook_intelligence_severity.raw_value == 'danger',
                            'text-warning': record.southbrook_intelligence_severity.raw_value == 'warning',
                            'text-success': record.southbrook_intelligence_severity.raw_value == 'success',
                            'text-info': record.southbrook_intelligence_severity.raw_value == 'info',
                         }">
                        <field name="southbrook_intelligence_prompt"/>
                    </div>
                    <div class="d-flex flex-wrap gap-1">
                        <span class="badge text-bg-success"
                              t-if="record.southbrook_ready_job_count.raw_value">
                            <field name="southbrook_ready_job_count"/> ready
                        </span>
                        <span class="badge text-bg-danger"
                              t-if="record.southbrook_at_risk_job_count.raw_value">
                            <field name="southbrook_at_risk_job_count"/> at risk
                        </span>
                        <span class="badge text-bg-danger"
                              t-if="record.southbrook_material_risk_count.raw_value">
                            <field name="southbrook_material_risk_count"/> material
                        </span>
                        <span class="badge text-bg-warning"
                              t-if="record.southbrook_unscheduled_wo_count.raw_value">
                            <field name="southbrook_unscheduled_wo_count"/> unscheduled WO
                        </span>
                        <span class="badge text-bg-warning"
                              t-if="record.southbrook_crew_gap_count.raw_value">
                            <field name="southbrook_crew_gap_count"/> crew gap
                        </span>
                        <span class="badge text-bg-danger"
                              t-if="record.southbrook_equipment_blocked_count.raw_value">
                            <field name="southbrook_equipment_blocked_count"/> equipment
                        </span>
                        <span class="badge text-bg-warning"
                              t-if="record.southbrook_over_capacity_count.raw_value">
                            <field name="southbrook_over_capacity_count"/> capacity
                        </span>
                    </div>
                    <button type="object"
                            name="action_southbrook_open_manufacturing_jobs"
                            class="btn btn-sm btn-outline-primary mt-2"
                            t-if="record.southbrook_job_count.raw_value">
                        Open Production Board
                    </button>
                </div>
            </xpath>
        </field>
    </record>
```

- [ ] **Step 4: Run the view test**

Run the command from Step 2 again.

Expected: PASS.

- [ ] **Step 5: Run a local registry/view upgrade**

Run:

```bash
/bin/bash -lc "docker exec sami-odoo odoo -d southbrook -u southbrook_project_mrp --stop-after-init --no-http --db_host=db --db_user=odoo --db_password='$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2)' --http-port=8899 --gevent-port=8902 --workers=0 --max-cron-threads=0"
```

Expected: Exit code 0 and log contains `Modules loaded`.

- [ ] **Step 6: Commit Task 2**

```bash
git add addons/southbrook_project_mrp/views/project_task_views.xml addons/southbrook_project_mrp/tests/test_integration.py
git commit -m "feat(project-mrp): add manufacturing mission control project cards"
```

## Task 3: Local Full Verification And Live Deployment

**Files:**
- No source edits expected.
- Use deploy script: `scripts/deploy_to_qnap.sh`

- [ ] **Step 1: Run static Python compile**

Run:

```bash
python3 -m py_compile \
  addons/southbrook_project_mrp/models/project_project.py \
  addons/southbrook_project_mrp/models/project_task.py \
  addons/southbrook_project_mrp/models/mrp_workorder.py
```

Expected: no output and exit code 0.

- [ ] **Step 2: Run the focused module test suite**

Run:

```bash
/bin/bash -lc "docker exec sami-odoo odoo -d southbrook -u southbrook_project_mrp --test-enable --test-tags=/southbrook_project_mrp --db_host=db --db_user=odoo --db_password='$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2)' --stop-after-init --no-http --http-port=8899 --gevent-port=8902 --workers=0 --max-cron-threads=0"
```

Expected: Odoo exits 0. If Odoo reports `0 post-tests`, treat registry load as useful but not sufficient; continue with live ORM verification after deployment.

- [ ] **Step 3: Deploy to QNAP with restart**

Run:

```bash
RESTART=1 ./scripts/deploy_to_qnap.sh southbrook_project_mrp
```

Expected:

- `Modules loaded`
- `Registry loaded`
- `live /web/login -> 200`

- [ ] **Step 4: Verify live `/odoo/project` data through ORM**

Run:

```bash
ssh admin@192.168.68.108 '/share/CACHEDEV3_DATA/.qpkg/container-station/bin/system-docker exec -i southbrook-odoo odoo shell --config=/etc/odoo/odoo.conf -d southbrook --no-http --workers 0' <<'PY'
project = env['project.project'].search([('name','=','Test')], limit=1)
print('PROJECT', project.id, project.display_name)
print(project.read([
    'southbrook_job_count',
    'southbrook_active_mo_count',
    'southbrook_ready_job_count',
    'southbrook_at_risk_job_count',
    'southbrook_material_risk_count',
    'southbrook_unscheduled_wo_count',
    'southbrook_crew_gap_count',
    'southbrook_equipment_blocked_count',
    'southbrook_over_capacity_count',
    'southbrook_job_cost_total',
    'southbrook_intelligence_prompt',
    'southbrook_intelligence_severity',
])[0])
action = project.action_southbrook_open_manufacturing_jobs()
print('ACTION', action['res_model'], action['domain'], action['view_mode'])
env.cr.rollback()
PY
```

Expected for current live data:

- `PROJECT 1 Test`
- `southbrook_job_count` at least `1`
- `southbrook_active_mo_count` at least `6`
- `southbrook_unscheduled_wo_count` at least `47`
- Prompt contains either `Review` or `Stop`
- Action model is `project.task`

- [ ] **Step 5: Verify live `/odoo/project` grouped web read**

Run:

```bash
ssh admin@192.168.68.108 '/share/CACHEDEV3_DATA/.qpkg/container-station/bin/system-docker exec -i southbrook-odoo odoo shell --config=/etc/odoo/odoo.conf -d southbrook --no-http --workers 0' <<'PY'
Project = env['project.project']
spec = {
    'display_name': {},
    'southbrook_job_count': {},
    'southbrook_active_mo_count': {},
    'southbrook_ready_job_count': {},
    'southbrook_at_risk_job_count': {},
    'southbrook_material_risk_count': {},
    'southbrook_unscheduled_wo_count': {},
    'southbrook_crew_gap_count': {},
    'southbrook_equipment_blocked_count': {},
    'southbrook_over_capacity_count': {},
    'southbrook_intelligence_prompt': {},
    'southbrook_intelligence_severity': {},
}
records = Project.search([], limit=20)
print('PROJECT_READ_OK', records.read(list(spec.keys()))[:3])
env.cr.rollback()
PY
```

Expected: `PROJECT_READ_OK` prints project rows and no RPC/compute traceback.

- [ ] **Step 6: Browser/user verification**

Open `https://southbrookcabinetry.space/odoo/project` in the existing authenticated browser session. Do not enter credentials. Confirm:

- The Project page loads with no RPC error.
- The `Test` project card shows manufacturing prompt and chips.
- `Open Production Board` opens manufacturing-linked project tasks.
- Task #182 still opens.

- [ ] **Step 7: Commit/push if deployment verification required any final source fix**

If no source changes were made after Task 2, skip this commit step. If a live-only issue required a source fix:

```bash
git add addons/southbrook_project_mrp
git commit -m "fix(project-mrp): stabilize project mission control cards"
git push
```

If no final fix was needed, push existing commits:

```bash
git push
```

