# What-If Schedule Simulator (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a planner ask "what if we run/insert/reprioritize this?" and see the throughput, tardiness, and completion impact **before committing** — without ever mutating the live schedule.

**Architecture:** A new module `southbrook_schedule_whatif` that drives the *existing* `mrp_sfc_scheduling_engine` (`mrp.scheduling.run`) inside a **DB savepoint**, captures its KPIs + per-WO schedule lines into plain Python, then **rolls back** so no live work-order date or capacity-load row is touched. It stores each run as an `sb.schedule.scenario` (baseline KPIs + scenario KPIs + computed deltas) with `sb.schedule.scenario.line` snapshots. Two v1 mutations: **objective comparison** (e.g. tardiness vs makespan) and **insert rush MO**.

**Tech Stack:** Odoo 19.0 CE, Python 3, XML views, `TransactionCase` tests. No JS in Phase 2.

## Global Constraints

- **License/manifest:** every file header `# SPDX-License-Identifier: LGPL-3.0-only`; manifest `"license": "LGPL-3"`, `"author": "Southbrook Cabinetry"`, `"version": "19.0.1.0.0"`.
- **CROSS-REPO DEPENDENCY (read this).** The scheduling engine is **not in this repo** — `mrp_sfc_scheduling_engine` + `mrp_shop_floor_control` live in `~/Downloads/openvalue/` and are deployed live to the `southbrook` DB. This module `depends` on them. Consequences:
  - It installs fine on `southbrook` (engine present there).
  - For an **isolated test DB**, the openvalue modules must be staged into the addons path first (copy `mrp_shop_floor_control` + `mrp_sfc_scheduling_engine` alongside, `update_list()`, install). Document this in the test steps; do NOT assume a bare `mrp`-only db.
  - If the team prefers, this module could instead live in the openvalue repo next to the engine — flagged as an open decision in the handoff. This plan assumes it lives in `southbrook-v19cr/addons/`.
- **THE NON-DESTRUCTIVE INVARIANT (the whole point).** A scenario run must never change a live `mrp.workorder.date_planned_start_wo`, never leave `mrp.workcenter.load` rows, never persist an `mrp.scheduling.run`. Enforced by the savepoint-rollback wrapper (Task 3) and proven by `test_scenario_does_not_mutate_live_workorders`. After rollback you MUST call `self.env.invalidate_all()` or the ORM cache will still hold the rolled-back (mutated) values.
- **Engine API (verified against `~/Downloads/openvalue/mrp_sfc_scheduling_engine/models/mrp_scheduling_run.py`):**
  - `mrp.scheduling.run` fields: `objective` (selection incl. `makespan`, `tardiness`, `sum_completion`, `wip`), `production_ids` (M2M `mrp.production`), `line_ids` (O2M `mrp.scheduling.run.line`). Stored KPI floats: `makespan_hours`, `total_tardiness_hours`, `sum_completion_hours`, `avg_wip`.
  - `action_run()` computes the schedule AND writes it to live WOs + rebuilds `mrp.workcenter.load` (destructive — hence the savepoint).
  - `mrp.scheduling.run.line` fields: `workorder_id`, `production_id`, `workcenter_id`, `sfc_sequence`, `date_planned_start_wo`, `date_planned_finished_wo`, `duration_hours`, `tardiness_hours`.
- **v19 API rules:** views use `<list>` not `<tree>`; `models.Constraint` not `_sql_constraints`; search `<group>` carries no `expand`/`string`; new module needs `update_list()` before `-i`; `--logfile=/dev/stderr` to see test output.
- **Test-fixture honesty:** these tests cannot be run on the dev Mac (no Odoo). The engine needs real schedulable WOs (product + BoM + routing operation + confirmed MO). The fixtures below are written against the engine's documented API; expect to tune them on the first real run on the stack. Static validation (`compileall` + XML parse) is the local gate; runtime green is a stack gate.

---

## File Structure

```
addons/southbrook_schedule_whatif/
  __init__.py
  __manifest__.py
  models/
    __init__.py
    sb_schedule_scenario.py         # sb.schedule.scenario + engine-capture wrapper + compute
    sb_schedule_scenario_line.py    # sb.schedule.scenario.line snapshot
  security/
    ir.model.access.csv
  views/
    sb_scenario_views.xml           # form (baseline|scenario|delta + lines) + list + search + action
    sb_scenario_menus.xml           # menu under Manufacturing
  tests/
    __init__.py
    test_schedule_whatif.py
  README.md
```

**Responsibilities:** `sb_schedule_scenario.py` owns the scenario record, the savepoint-rollback engine wrapper, and the two mutation modes. The line model is a thin snapshot. Views are presentation only.

---

## Task 1: Module scaffold that installs against the engine

**Files:**
- Create: `addons/southbrook_schedule_whatif/__init__.py`
- Create: `addons/southbrook_schedule_whatif/__manifest__.py`
- Create: `addons/southbrook_schedule_whatif/models/__init__.py`
- Create: `addons/southbrook_schedule_whatif/security/ir.model.access.csv`

**Interfaces:**
- Produces: installable module `southbrook_schedule_whatif` depending on `mrp_sfc_scheduling_engine`.

- [ ] **Step 1: Package `__init__.py`**

`addons/southbrook_schedule_whatif/__init__.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from . import models
```

- [ ] **Step 2: `models/__init__.py` (empty for now)**

`addons/southbrook_schedule_whatif/models/__init__.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
```

- [ ] **Step 3: Manifest**

`addons/southbrook_schedule_whatif/__manifest__.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook What-If Schedule Simulator",
    "summary": "Non-destructive scenario runner over the SFC scheduling "
               "engine: compare objectives, insert rush orders, diff KPIs.",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry",
    "website": "https://southbrookcabinetry.space",
    "category": "Manufacturing",
    "depends": ["mrp_sfc_scheduling_engine"],
    "data": [
        "security/ir.model.access.csv",
        # "views/sb_scenario_views.xml",   # Task 6
        # "views/sb_scenario_menus.xml",   # Task 6
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
```

- [ ] **Step 4: Placeholder ACL (header only)**

`addons/southbrook_schedule_whatif/security/ir.model.access.csv`:
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
```

- [ ] **Step 5: Stage the engine + install on an isolated test db**

The test db needs the openvalue modules. On the odooiq stack host:
```bash
# stage engine + base from the openvalue checkout into the odooiq addons path
# (adjust source path if the openvalue repo lives elsewhere on the stack host)
for m in mrp_shop_floor_control mrp_sfc_scheduling_engine; do
  docker cp ~/Downloads/openvalue/$m odooiq-odoo:/mnt/extra-addons/ 2>/dev/null || \
  echo "stage $m manually into the odooiq addons dir"
done
docker exec odooiq-odoo odoo shell -d whatif_test --no-http -c /etc/odoo/odoo.conf \
  --logfile=/dev/stderr <<'PY'
env['ir.module.module'].update_list(); env.cr.commit()
PY
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d whatif_test \
  -i southbrook_schedule_whatif --stop-after-init --no-http --logfile=/dev/stderr
```
Expected: exits 0; installs `mrp_shop_floor_control` + `mrp_sfc_scheduling_engine` as deps, then `southbrook_schedule_whatif`; no traceback.

- [ ] **Step 6: Commit**

```bash
cd ~/southbrook-v19cr
git add addons/southbrook_schedule_whatif
git commit -m "feat(whatif): scaffold what-if simulator module (Phase 2 Task 1)"
```

---

## Task 2: Scenario + scenario-line models with KPI deltas

**Files:**
- Create: `addons/southbrook_schedule_whatif/models/sb_schedule_scenario.py`
- Create: `addons/southbrook_schedule_whatif/models/sb_schedule_scenario_line.py`
- Modify: `addons/southbrook_schedule_whatif/models/__init__.py`
- Modify: `addons/southbrook_schedule_whatif/security/ir.model.access.csv`
- Test: `addons/southbrook_schedule_whatif/tests/test_schedule_whatif.py`

**Interfaces:**
- Produces: `sb.schedule.scenario` with `name`, `objective` (Selection matching the engine), `alt_objective` (Selection), `mutation` (Selection: `objective`/`insert_rush`), `production_ids` (M2M `mrp.production`), `state` (`draft`/`computed`), baseline KPI floats `base_makespan/base_tardiness/base_sum_completion/base_avg_wip`, scenario KPI floats `makespan/tardiness/sum_completion/avg_wip`, computed deltas `d_makespan/d_tardiness/d_sum_completion/d_avg_wip`, `line_ids` (O2M). And `sb.schedule.scenario.line` snapshot fields.

- [ ] **Step 1: Write the failing test (create tests package + delta test)**

`addons/southbrook_schedule_whatif/tests/__init__.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from . import test_schedule_whatif
```

`addons/southbrook_schedule_whatif/tests/test_schedule_whatif.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "southbrook_schedule_whatif")
class TestScheduleWhatIf(TransactionCase):

    def test_kpi_deltas_compute_from_base_and_scenario(self):
        scenario = self.env["sb.schedule.scenario"].create({
            "name": "delta probe",
            "base_makespan": 10.0, "makespan": 13.0,
            "base_tardiness": 2.0, "tardiness": 5.0,
            "base_sum_completion": 40.0, "sum_completion": 44.0,
            "base_avg_wip": 3.0, "avg_wip": 3.5,
        })
        self.assertAlmostEqual(scenario.d_makespan, 3.0)
        self.assertAlmostEqual(scenario.d_tardiness, 3.0)
        self.assertAlmostEqual(scenario.d_sum_completion, 4.0)
        self.assertAlmostEqual(scenario.d_avg_wip, 0.5)
```

- [ ] **Step 2: Run to verify it fails**

```bash
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d whatif_test \
  -u southbrook_schedule_whatif --test-enable --test-tags southbrook_schedule_whatif \
  --stop-after-init --no-http --logfile=/dev/stderr 2>&1 | grep -Ei "whatif|delta|FAIL|ERROR"
```
Expected: FAIL — model `sb.schedule.scenario` does not exist.

- [ ] **Step 3: Create the scenario model**

`addons/southbrook_schedule_whatif/models/sb_schedule_scenario.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from odoo import api, fields, models

# Objective selection mirrors mrp.scheduling.run in mrp_sfc_scheduling_engine.
OBJECTIVES = [
    ("makespan", "Makespan"),
    ("tardiness", "Tardiness"),
    ("sum_completion", "Sum Completion"),
    ("wip", "WIP"),
]


class SbScheduleScenario(models.Model):
    _name = "sb.schedule.scenario"
    _description = "What-If Schedule Scenario"
    _order = "create_date desc"

    name = fields.Char(required=True, default="New Scenario")
    objective = fields.Selection(OBJECTIVES, string="Baseline Objective",
                                 required=True, default="tardiness")
    alt_objective = fields.Selection(OBJECTIVES, string="Scenario Objective",
                                     default="makespan")
    mutation = fields.Selection(
        [("objective", "Compare Objectives"), ("insert_rush", "Insert Rush MO")],
        string="Scenario Type", required=True, default="objective",
    )
    production_ids = fields.Many2many("mrp.production", string="Manufacturing Orders")
    rush_product_id = fields.Many2one("product.product", string="Rush Product")
    rush_qty = fields.Float("Rush Quantity", default=1.0)
    state = fields.Selection([("draft", "Draft"), ("computed", "Computed")],
                             default="draft", required=True)

    base_makespan = fields.Float(readonly=True)
    base_tardiness = fields.Float(readonly=True)
    base_sum_completion = fields.Float(readonly=True)
    base_avg_wip = fields.Float(readonly=True)
    makespan = fields.Float(readonly=True)
    tardiness = fields.Float(readonly=True)
    sum_completion = fields.Float(readonly=True)
    avg_wip = fields.Float(readonly=True)

    d_makespan = fields.Float("Δ Makespan", compute="_compute_deltas", store=True)
    d_tardiness = fields.Float("Δ Tardiness", compute="_compute_deltas", store=True)
    d_sum_completion = fields.Float("Δ Sum Completion", compute="_compute_deltas",
                                    store=True)
    d_avg_wip = fields.Float("Δ Avg WIP", compute="_compute_deltas", store=True)

    line_ids = fields.One2many("sb.schedule.scenario.line", "scenario_id",
                               string="Scenario Schedule")

    @api.depends("base_makespan", "makespan", "base_tardiness", "tardiness",
                 "base_sum_completion", "sum_completion", "base_avg_wip", "avg_wip")
    def _compute_deltas(self):
        for s in self:
            s.d_makespan = s.makespan - s.base_makespan
            s.d_tardiness = s.tardiness - s.base_tardiness
            s.d_sum_completion = s.sum_completion - s.base_sum_completion
            s.d_avg_wip = s.avg_wip - s.base_avg_wip
```

- [ ] **Step 4: Create the line model**

`addons/southbrook_schedule_whatif/models/sb_schedule_scenario_line.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields, models


class SbScheduleScenarioLine(models.Model):
    _name = "sb.schedule.scenario.line"
    _description = "What-If Schedule Scenario Line"
    _order = "date_planned_start_wo, id"

    scenario_id = fields.Many2one("sb.schedule.scenario", required=True,
                                  ondelete="cascade", index=True)
    # workorder_id is optional: an inserted rush WO does not survive the
    # rollback, so it is captured by label only.
    workorder_id = fields.Many2one("mrp.workorder", string="Work Order")
    label = fields.Char(string="Operation")
    workcenter_id = fields.Many2one("mrp.workcenter", string="Work Center")
    sfc_sequence = fields.Integer(string="Sequence")
    date_planned_start_wo = fields.Datetime(string="Scheduled Start")
    date_planned_finished_wo = fields.Datetime(string="Scheduled End")
    duration_hours = fields.Float(string="Duration (h)")
    tardiness_hours = fields.Float(string="Tardiness (h)")
```

- [ ] **Step 5: Register models**

`addons/southbrook_schedule_whatif/models/__init__.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from . import sb_schedule_scenario
from . import sb_schedule_scenario_line
```

- [ ] **Step 6: ACL rows**

Replace `security/ir.model.access.csv` with:
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_sb_scenario_user,sb.schedule.scenario user,model_sb_schedule_scenario,base.group_user,1,0,0,0
access_sb_scenario_mrp,sb.schedule.scenario mrp,model_sb_schedule_scenario,mrp.group_mrp_user,1,1,1,1
access_sb_scenario_line_user,sb.schedule.scenario.line user,model_sb_schedule_scenario_line,base.group_user,1,0,0,0
access_sb_scenario_line_mrp,sb.schedule.scenario.line mrp,model_sb_schedule_scenario_line,mrp.group_mrp_user,1,1,1,1
```

- [ ] **Step 7: Run the test to verify it passes**

```bash
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d whatif_test \
  -u southbrook_schedule_whatif --test-enable --test-tags southbrook_schedule_whatif \
  --stop-after-init --no-http --logfile=/dev/stderr 2>&1 | grep -Ei "whatif|delta|FAIL|ERROR|passed"
```
Expected: delta test PASS.

- [ ] **Step 8: Commit**

```bash
cd ~/southbrook-v19cr
git add addons/southbrook_schedule_whatif
git commit -m "feat(whatif): scenario + line models with KPI deltas (Task 2)"
```

---

## Task 3: The savepoint-rollback engine wrapper (the core + the invariant test)

**Files:**
- Modify: `addons/southbrook_schedule_whatif/models/sb_schedule_scenario.py`
- Modify: `addons/southbrook_schedule_whatif/tests/test_schedule_whatif.py`

**Interfaces:**
- Consumes: `mrp.scheduling.run` (engine).
- Produces: method `sb.schedule.scenario._run_engine_capture(production_ids, objective, rush_vals=None)` → returns a dict `{makespan, tardiness, sum_completion, avg_wip, lines: [ {workorder_id|False, label, workcenter_id, sfc_sequence, date_planned_start_wo, date_planned_finished_wo, duration_hours, tardiness_hours} ]}`, having run the engine inside a savepoint and rolled it back (no live mutation). Also a helper `_make_fixture_mo(...)` is NOT part of this module — fixtures live in the test.

- [ ] **Step 1: Write the failing test — the non-destructive invariant + capture shape**

Append to the test class in `test_schedule_whatif.py` (add imports at top: `from datetime import datetime`):
```python
    def _fixture_workcenter(self):
        wc = self.env["mrp.workcenter"].search([("code", "=", "SB-CNC-BORE")], limit=1)
        if not wc:
            wc = self.env["mrp.workcenter"].create(
                {"name": "Test Bore", "code": "SB-CNC-BORE"})
        return wc

    def _fixture_confirmed_mo(self, wc, name="WHATIF-P"):
        # product + single-operation BoM → confirmed MO that spawns a WO.
        product = self.env["product.product"].create(
            {"name": name, "is_storable": True})
        comp = self.env["product.product"].create(
            {"name": name + " comp", "is_storable": True})
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_qty": 1.0,
            "bom_line_ids": [(0, 0, {"product_id": comp.id, "product_qty": 1.0})],
            "operation_ids": [(0, 0, {
                "name": "Bore", "workcenter_id": wc.id, "time_cycle_manual": 30.0,
            })],
        })
        mo = self.env["mrp.production"].create({
            "product_id": product.id, "product_qty": 1.0, "bom_id": bom.id,
        })
        mo.action_confirm()
        return mo

    def test_scenario_run_does_not_mutate_live_workorders(self):
        wc = self._fixture_workcenter()
        mo = self._fixture_confirmed_mo(wc)
        wo = mo.workorder_ids[:1]
        before = wo.date_planned_start_wo
        scenario = self.env["sb.schedule.scenario"].create({
            "name": "invariant", "production_ids": [(6, 0, mo.ids)],
        })
        result = scenario._run_engine_capture(mo.ids, "tardiness")
        # 1) the engine produced KPIs
        self.assertIn("makespan", result)
        self.assertIsInstance(result["lines"], list)
        # 2) THE INVARIANT: the live WO's planned date is unchanged.
        wo.invalidate_recordset(["date_planned_start_wo"])
        self.assertEqual(wo.date_planned_start_wo, before,
                         "scenario run must NOT mutate live work-order dates")
        # 3) no capacity-load rows persisted for this WO
        self.assertFalse(self.env["mrp.workcenter.load"].search(
            [("workorder_id", "=", wo.id)]),
            "scenario run must NOT leave workcenter.load rows")
```

- [ ] **Step 2: Run to verify it fails**

```bash
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d whatif_test \
  -u southbrook_schedule_whatif --test-enable --test-tags southbrook_schedule_whatif \
  --stop-after-init --no-http --logfile=/dev/stderr 2>&1 | grep -Ei "invariant|mutate|FAIL|ERROR"
```
Expected: FAIL — `_run_engine_capture` not defined.

- [ ] **Step 3: Implement the savepoint-rollback wrapper**

At the top of `sb_schedule_scenario.py`, below the imports add the sentinel; then add the method to the class:
```python
class _ScenarioRollback(Exception):
    """Internal: forces the scenario savepoint to roll back after capture."""
```
Add to `SbScheduleScenario`:
```python
    def _run_engine_capture(self, production_ids, objective, rush_vals=None):
        """Run the SFC engine on the given MOs (optionally + a rush MO) inside a
        savepoint, capture KPIs + schedule lines as plain Python, then roll back
        so NO live workorder date / workcenter.load row is mutated. Returns dict.
        """
        self.ensure_one()
        base_ids = list(production_ids)
        captured = {"makespan": 0.0, "tardiness": 0.0, "sum_completion": 0.0,
                    "avg_wip": 0.0, "lines": []}
        try:
            with self.env.cr.savepoint():
                run_ids = list(base_ids)
                rush_label = None
                if rush_vals:
                    rush_mo = self.env["mrp.production"].create(rush_vals)
                    rush_mo.action_confirm()
                    run_ids.append(rush_mo.id)
                    rush_label = rush_vals.get("origin") or "RUSH"
                run = self.env["mrp.scheduling.run"].create({
                    "objective": objective,
                    "production_ids": [(6, 0, run_ids)],
                })
                run.action_run()
                lines = []
                for ln in run.line_ids:
                    is_base = ln.production_id.id in base_ids
                    lines.append({
                        "workorder_id": ln.workorder_id.id if is_base else False,
                        "label": ln.workorder_id.display_name if is_base
                                 else rush_label,
                        "workcenter_id": ln.workcenter_id.id,
                        "sfc_sequence": ln.sfc_sequence,
                        "date_planned_start_wo": ln.date_planned_start_wo,
                        "date_planned_finished_wo": ln.date_planned_finished_wo,
                        "duration_hours": ln.duration_hours,
                        "tardiness_hours": ln.tardiness_hours,
                    })
                captured = {
                    "makespan": run.makespan_hours,
                    "tardiness": run.total_tardiness_hours,
                    "sum_completion": run.sum_completion_hours,
                    "avg_wip": run.avg_wip,
                    "lines": lines,
                }
                raise _ScenarioRollback()
        except _ScenarioRollback:
            pass
        # Discard the ORM cache so live records read their pre-savepoint values.
        self.env.invalidate_all()
        return captured
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d whatif_test \
  -u southbrook_schedule_whatif --test-enable --test-tags southbrook_schedule_whatif \
  --stop-after-init --no-http --logfile=/dev/stderr 2>&1 | grep -Ei "invariant|mutate|FAIL|ERROR|passed"
```
Expected: PASS — KPIs captured, live WO date unchanged, no load rows. (If the engine fixture needs extra fields — e.g. a resource calendar — tune `_fixture_confirmed_mo` per the traceback; the savepoint logic itself is the deliverable.)

- [ ] **Step 5: Commit**

```bash
cd ~/southbrook-v19cr
git add addons/southbrook_schedule_whatif
git commit -m "feat(whatif): savepoint-rollback engine capture + non-destructive invariant test (Task 3)"
```

---

## Task 4: `action_compute` — objective-comparison scenario

**Files:**
- Modify: `addons/southbrook_schedule_whatif/models/sb_schedule_scenario.py`
- Modify: `addons/southbrook_schedule_whatif/tests/test_schedule_whatif.py`

**Interfaces:**
- Consumes: `_run_engine_capture`.
- Produces: method `sb.schedule.scenario.action_compute()` that, for `mutation == "objective"`, runs the engine twice (baseline `objective`, scenario `alt_objective`) on the same `production_ids`, writes the 8 KPI floats + rebuilds `line_ids` from the scenario run, and sets `state = "computed"`.

- [ ] **Step 1: Write the failing test**

Append to the test class:
```python
    def test_objective_comparison_populates_kpis_and_lines(self):
        wc = self._fixture_workcenter()
        mo = self._fixture_confirmed_mo(wc, name="WHATIF-OBJ")
        scenario = self.env["sb.schedule.scenario"].create({
            "name": "obj cmp", "mutation": "objective",
            "objective": "tardiness", "alt_objective": "makespan",
            "production_ids": [(6, 0, mo.ids)],
        })
        scenario.action_compute()
        self.assertEqual(scenario.state, "computed")
        # KPIs are populated (base + scenario) and lines snapshotted.
        self.assertTrue(scenario.line_ids, "scenario should snapshot schedule lines")
        # deltas are self-consistent
        self.assertAlmostEqual(scenario.d_makespan,
                               scenario.makespan - scenario.base_makespan)
```

- [ ] **Step 2: Run to verify it fails**

```bash
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d whatif_test \
  -u southbrook_schedule_whatif --test-enable --test-tags southbrook_schedule_whatif \
  --stop-after-init --no-http --logfile=/dev/stderr 2>&1 | grep -Ei "objective|FAIL|ERROR"
```
Expected: FAIL — `action_compute` not defined.

- [ ] **Step 3: Implement `action_compute` (objective branch) + a line-writer helper**

Add to `SbScheduleScenario`:
```python
    def _write_lines(self, captured_lines):
        self.line_ids.unlink()
        self.env["sb.schedule.scenario.line"].create([{
            "scenario_id": self.id,
            "workorder_id": d["workorder_id"] or False,
            "label": d["label"],
            "workcenter_id": d["workcenter_id"] or False,
            "sfc_sequence": d["sfc_sequence"],
            "date_planned_start_wo": d["date_planned_start_wo"],
            "date_planned_finished_wo": d["date_planned_finished_wo"],
            "duration_hours": d["duration_hours"],
            "tardiness_hours": d["tardiness_hours"],
        } for d in captured_lines])

    def action_compute(self):
        for scenario in self:
            base_ids = scenario.production_ids.ids
            base = scenario._run_engine_capture(base_ids, scenario.objective)
            if scenario.mutation == "objective":
                scen = scenario._run_engine_capture(
                    base_ids, scenario.alt_objective or scenario.objective)
            else:  # insert_rush — implemented in Task 5
                scen = scenario._compute_insert_rush(base_ids)
            scenario.write({
                "base_makespan": base["makespan"],
                "base_tardiness": base["tardiness"],
                "base_sum_completion": base["sum_completion"],
                "base_avg_wip": base["avg_wip"],
                "makespan": scen["makespan"],
                "tardiness": scen["tardiness"],
                "sum_completion": scen["sum_completion"],
                "avg_wip": scen["avg_wip"],
                "state": "computed",
            })
            scenario._write_lines(scen["lines"])
        return True
```

- [ ] **Step 4: Add a stub for the rush branch so objective mode imports cleanly**

Add to `SbScheduleScenario` (fully implemented in Task 5):
```python
    def _compute_insert_rush(self, base_ids):
        # Placeholder until Task 5; objective-mode never calls this.
        return self._run_engine_capture(base_ids, self.objective)
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d whatif_test \
  -u southbrook_schedule_whatif --test-enable --test-tags southbrook_schedule_whatif \
  --stop-after-init --no-http --logfile=/dev/stderr 2>&1 | grep -Ei "objective|FAIL|ERROR|passed"
```
Expected: objective-comparison test PASS.

- [ ] **Step 6: Commit**

```bash
cd ~/southbrook-v19cr
git add addons/southbrook_schedule_whatif
git commit -m "feat(whatif): action_compute objective-comparison mode (Task 4)"
```

---

## Task 5: Insert-rush-MO mutation

**Files:**
- Modify: `addons/southbrook_schedule_whatif/models/sb_schedule_scenario.py`
- Modify: `addons/southbrook_schedule_whatif/tests/test_schedule_whatif.py`

**Interfaces:**
- Consumes: `_run_engine_capture` (its `rush_vals` param).
- Produces: real `_compute_insert_rush(base_ids)` — builds `rush_vals` from `rush_product_id`/`rush_qty`, runs the engine on `base_ids + rush`, returns the captured dict. Baseline (Task 4) is the same MOs without the rush; the delta = the rush order's impact.

- [ ] **Step 1: Write the failing test**

Append to the test class:
```python
    def test_insert_rush_increases_or_holds_makespan(self):
        wc = self._fixture_workcenter()
        mo = self._fixture_confirmed_mo(wc, name="WHATIF-BASE")
        rush_product = self.env["product.product"].create(
            {"name": "Rush Kitchen 417", "is_storable": True})
        # a BoM+routing so the rush MO spawns a schedulable WO
        comp = self.env["product.product"].create(
            {"name": "rush comp", "is_storable": True})
        self.env["mrp.bom"].create({
            "product_tmpl_id": rush_product.product_tmpl_id.id, "product_qty": 1.0,
            "bom_line_ids": [(0, 0, {"product_id": comp.id, "product_qty": 1.0})],
            "operation_ids": [(0, 0, {
                "name": "Bore", "workcenter_id": wc.id, "time_cycle_manual": 30.0})],
        })
        scenario = self.env["sb.schedule.scenario"].create({
            "name": "rush", "mutation": "insert_rush",
            "objective": "tardiness",
            "production_ids": [(6, 0, mo.ids)],
            "rush_product_id": rush_product.id, "rush_qty": 1.0,
        })
        scenario.action_compute()
        self.assertEqual(scenario.state, "computed")
        # Adding work never reduces makespan on a single work center.
        self.assertGreaterEqual(scenario.makespan, scenario.base_makespan)
        # The rush WO appears in the scenario snapshot (by label, no live WO id).
        self.assertTrue(
            any(l.label and "Rush" in (l.label or "") for l in scenario.line_ids)
            or len(scenario.line_ids) > len(mo.workorder_ids),
            "rush operation should appear in the scenario schedule",
        )
```

- [ ] **Step 2: Run to verify it fails**

```bash
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d whatif_test \
  -u southbrook_schedule_whatif --test-enable --test-tags southbrook_schedule_whatif \
  --stop-after-init --no-http --logfile=/dev/stderr 2>&1 | grep -Ei "rush|FAIL|ERROR"
```
Expected: FAIL — makespan not populated as expected (rush is a stub).

- [ ] **Step 3: Implement the real rush branch**

Replace the `_compute_insert_rush` stub with:
```python
    def _compute_insert_rush(self, base_ids):
        self.ensure_one()
        if not self.rush_product_id:
            return self._run_engine_capture(base_ids, self.objective)
        rush_vals = {
            "product_id": self.rush_product_id.id,
            "product_qty": self.rush_qty or 1.0,
            "origin": "Rush: %s" % self.rush_product_id.display_name,
        }
        return self._run_engine_capture(base_ids, self.objective, rush_vals=rush_vals)
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d whatif_test \
  -u southbrook_schedule_whatif --test-enable --test-tags southbrook_schedule_whatif \
  --stop-after-init --no-http --logfile=/dev/stderr 2>&1 | grep -Ei "rush|FAIL|ERROR|passed"
```
Expected: rush test PASS; the rush MO is discarded on rollback (verify no orphan MO persists — covered by the Task 3 invariant pattern).

- [ ] **Step 5: Commit**

```bash
cd ~/southbrook-v19cr
git add addons/southbrook_schedule_whatif
git commit -m "feat(whatif): insert-rush-MO scenario mutation (Task 5)"
```

---

## Task 6: Backend views — baseline | scenario | delta

**Files:**
- Create: `addons/southbrook_schedule_whatif/views/sb_scenario_views.xml`
- Create: `addons/southbrook_schedule_whatif/views/sb_scenario_menus.xml`
- Modify: `addons/southbrook_schedule_whatif/__manifest__.py` (enable view files)

**Interfaces:**
- Produces: an `ir.actions.act_window` `action_sb_scenario`, list/form/search views, a "Compute" button bound to `action_compute`, and a menu `Manufacturing → What-If → Scenarios`.

- [ ] **Step 1: Create the views (form shows a base|scenario|delta KPI block + the lines)**

`addons/southbrook_schedule_whatif/views/sb_scenario_views.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_sb_scenario_list" model="ir.ui.view">
        <field name="name">sb.schedule.scenario.list</field>
        <field name="model">sb.schedule.scenario</field>
        <field name="arch" type="xml">
            <list string="Scenarios">
                <field name="name"/>
                <field name="mutation"/>
                <field name="state"/>
                <field name="d_makespan"/>
                <field name="d_tardiness"/>
            </list>
        </field>
    </record>

    <record id="view_sb_scenario_form" model="ir.ui.view">
        <field name="name">sb.schedule.scenario.form</field>
        <field name="model">sb.schedule.scenario</field>
        <field name="arch" type="xml">
            <form string="What-If Scenario">
                <header>
                    <button name="action_compute" type="object" string="Compute"
                            class="btn-primary"/>
                    <field name="state" widget="statusbar"/>
                </header>
                <sheet>
                    <div class="oe_title"><h1><field name="name"/></h1></div>
                    <group>
                        <group>
                            <field name="mutation"/>
                            <field name="objective"/>
                            <field name="alt_objective"
                                   invisible="mutation != 'objective'"/>
                        </group>
                        <group>
                            <field name="rush_product_id"
                                   invisible="mutation != 'insert_rush'"/>
                            <field name="rush_qty"
                                   invisible="mutation != 'insert_rush'"/>
                        </group>
                    </group>
                    <field name="production_ids" widget="many2many_tags"/>
                    <group string="KPI Comparison (baseline → scenario → Δ)">
                        <group>
                            <field name="base_makespan"/>
                            <field name="makespan"/>
                            <field name="d_makespan"/>
                            <field name="base_tardiness"/>
                            <field name="tardiness"/>
                            <field name="d_tardiness"/>
                        </group>
                        <group>
                            <field name="base_sum_completion"/>
                            <field name="sum_completion"/>
                            <field name="d_sum_completion"/>
                            <field name="base_avg_wip"/>
                            <field name="avg_wip"/>
                            <field name="d_avg_wip"/>
                        </group>
                    </group>
                    <notebook>
                        <page string="Scenario Schedule">
                            <field name="line_ids">
                                <list>
                                    <field name="sfc_sequence"/>
                                    <field name="label"/>
                                    <field name="workcenter_id"/>
                                    <field name="date_planned_start_wo"/>
                                    <field name="date_planned_finished_wo"/>
                                    <field name="duration_hours"/>
                                    <field name="tardiness_hours"/>
                                </list>
                            </field>
                        </page>
                    </notebook>
                </sheet>
            </form>
        </field>
    </record>

    <record id="view_sb_scenario_search" model="ir.ui.view">
        <field name="name">sb.schedule.scenario.search</field>
        <field name="model">sb.schedule.scenario</field>
        <field name="arch" type="xml">
            <search string="Scenarios">
                <field name="name"/>
                <filter name="computed" string="Computed"
                        domain="[('state','=','computed')]"/>
                <group>
                    <filter name="group_mutation" string="Type"
                            context="{'group_by': 'mutation'}"/>
                </group>
            </search>
        </field>
    </record>

    <record id="action_sb_scenario" model="ir.actions.act_window">
        <field name="name">Scenarios</field>
        <field name="res_model">sb.schedule.scenario</field>
        <field name="view_mode">list,form</field>
        <field name="search_view_id" ref="view_sb_scenario_search"/>
    </record>
</odoo>
```

- [ ] **Step 2: Create the menu**

`addons/southbrook_schedule_whatif/views/sb_scenario_menus.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <menuitem id="menu_sb_whatif_root" name="What-If"
              parent="mrp.menu_mrp_root" sequence="91"/>
    <menuitem id="menu_sb_scenario" name="Scenarios"
              parent="menu_sb_whatif_root"
              action="action_sb_scenario" sequence="10"/>
</odoo>
```

- [ ] **Step 3: Enable the view files in the manifest**

```python
    "data": [
        "security/ir.model.access.csv",
        "views/sb_scenario_views.xml",
        "views/sb_scenario_menus.xml",
    ],
```

- [ ] **Step 4: Upgrade + verify views load**

```bash
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d whatif_test \
  -u southbrook_schedule_whatif --stop-after-init --no-http --logfile=/dev/stderr 2>&1 \
  | grep -Ei "whatif|ParseError|ValidationError|Invalid|loaded"
```
Expected: no ParseError/ValidationError.

- [ ] **Step 5: Commit**

```bash
cd ~/southbrook-v19cr
git add addons/southbrook_schedule_whatif
git commit -m "feat(whatif): backend scenario views + menu (Task 6)"
```

---

## Task 7: Full-suite verification + README

**Files:**
- Create: `addons/southbrook_schedule_whatif/README.md`

- [ ] **Step 1: Cold-install + full test run**

```bash
docker exec odooiq-postgres dropdb -U odoo --if-exists whatif_test
docker exec odooiq-postgres createdb -U odoo whatif_test
docker exec odooiq-odoo odoo shell -d whatif_test --no-http -c /etc/odoo/odoo.conf \
  --logfile=/dev/stderr <<'PY'
env['ir.module.module'].update_list(); env.cr.commit()
PY
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d whatif_test \
  -i southbrook_schedule_whatif --test-enable --test-tags southbrook_schedule_whatif \
  --stop-after-init --no-http --logfile=/dev/stderr 2>&1 \
  | grep -Ei "FAIL|ERROR|0 failed|tests"
```
Expected: all tests pass; `0 failed`. **Critically, the invariant test (Task 3) is green** — the live schedule was never touched.

- [ ] **Step 2: Write the README**

`addons/southbrook_schedule_whatif/README.md`:
```markdown
# Southbrook What-If Schedule Simulator (Phase 2)

Non-destructive scenario runner over `mrp_sfc_scheduling_engine`. Answers
"what if we insert this rush order?" / "what if we optimize for makespan
instead of tardiness?" by running the engine inside a **DB savepoint**,
capturing KPIs (makespan / tardiness / sum-completion / avg-WIP) + a schedule
snapshot, then **rolling back** so the live schedule is never mutated.

## Dependency (cross-repo)
Depends on `mrp_sfc_scheduling_engine` + `mrp_shop_floor_control` from the
**openvalue** repo (deployed live on `southbrook`). For an isolated test db,
stage those two modules into the addons path first, `update_list()`, then
install.

## The invariant
`test_scenario_does_not_mutate_live_workorders` proves the core guarantee: after
a scenario runs, live `mrp.workorder.date_planned_start_wo` is unchanged and no
`mrp.workcenter.load` rows are left behind. If you extend this module, that test
must stay green.

## Demo
Manufacturing → What-If → Scenarios → New → pick MOs, choose "Insert Rush MO" +
a rush product → Compute → read the baseline | scenario | Δ KPI block.
```

- [ ] **Step 3: Commit**

```bash
cd ~/southbrook-v19cr
git add addons/southbrook_schedule_whatif
git commit -m "docs(whatif): README + full-suite verification (Task 7)"
```

---

## Out of scope for Phase 2 (explicit follow-ups)

- **Setup-cost / batching objectives** (tool-change, material, pattern clustering) — that's **Phase 3**; this module only *measures* schedules the engine already produces. Once Phase 3 adds those objectives to the engine, they appear here for free as new `objective` options.
- **Reorder-by-hand mutation** (drag a specific MO earlier) — deferred; the two v1 mutations (objective compare, insert rush) cover the headline demos. Add later as a third `mutation` value.
- **OWL/graphical Gantt of the scenario** — Phase 2 is backend list/form only.
- **Deploying to live southbrook** — only after green on the isolated db + review. The module reads live MOs but writes nothing to them; still, deploy via the standard rsync + `-u` recipe, never a casual `docker restart southbrook-odoo`.
- **Panel-twin coupling** — intentionally decoupled; scheduling is about MOs/WOs, not panels.

---

## Self-Review (against the Phase 2 spec)

- **Spec coverage:** "schedule cloning" → savepoint-run-rollback (T3) ✓ · "scenario comparison" → objective mode (T4) + insert-rush (T5) ✓ · "KPI diff" → base/scenario/delta fields + view (T2/T6) ✓ · "what if insert rush order?" → T5 ✓ · "what if batch walnut?" → deferred to Phase 3 objectives (documented; this module surfaces them when they exist) ✓ · non-destructive → invariant test (T3) ✓.
- **Placeholder scan:** no TBD/TODO; every step has real code or a real command. The `_compute_insert_rush` stub in T4 is explicitly replaced in T5 (a sequenced build step, not a shipped placeholder).
- **Type consistency:** `_run_engine_capture(production_ids, objective, rush_vals=None)` returns the same dict keys (`makespan/tardiness/sum_completion/avg_wip/lines`) consumed by `action_compute` and `_write_lines`; line-dict keys match `sb.schedule.scenario.line` fields; `OBJECTIVES` selection mirrors the engine.
- **Honest risk:** the engine fixtures (`_fixture_confirmed_mo`) are best-effort against the engine's API and may need field tuning on the first real run (no local Odoo to shake them out). The savepoint-rollback logic — the actual deliverable — is independent of fixture specifics.
- **Scope:** one module, one subsystem — correctly sized.
```
