# MRP Command Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Project/MRP Command Center MVP: project-level readiness score, gate summaries, release blocking, PM command panel, and exception queues.

**Architecture:** Extend `southbrook_project` as the project-level read model because `project.task` is the PM's job surface. Pull signals from existing source modules: sale order, MRP production/work orders, production packages, manufacturing intelligence checks, tool readiness, equipment condition, and purchase orders. Use Odoo-native computed fields, form/list/search/kanban views, and focused TransactionCase tests; no custom JavaScript in this MVP.

**Tech Stack:** Odoo 19 CE, Python ORM models, XML views/actions/menus, Odoo TransactionCase tests, QNAP rollback-only shell verification.

---

## File Structure

- Modify `addons/southbrook_project/__manifest__.py`
  - Add manufacturing dependencies.
  - Add new view XML files.
  - Bump version to `19.0.0.2.0`.
- Modify `addons/southbrook_project/models/__init__.py`
  - Import the new command-center model file.
- Create `addons/southbrook_project/models/manufacturing_command.py`
  - Own all readiness constants, gate computation, blocker summaries, related record collectors, and release action wrapper on `project.task`.
- Modify `addons/southbrook_project/views/project_task_views.xml`
  - Add header readiness fields and a Manufacturing Command notebook page.
- Create `addons/southbrook_project/views/mrp_command_center_views.xml`
  - Add PM dashboard actions, exception queue actions, list/search/kanban views.
- Create `addons/southbrook_project/tests/__init__.py`
  - Import new tests.
- Create `addons/southbrook_project/tests/test_mrp_command_center.py`
  - Business behavior tests for scoring, blockers, release gate, and action domains.
- Create `addons/southbrook_project/tests/test_mrp_command_views.py`
  - View/action loading tests.

---

## Task 1: Add Module Dependencies And Test Package

**Files:**
- Modify: `addons/southbrook_project/__manifest__.py`
- Modify: `addons/southbrook_project/models/__init__.py`
- Create: `addons/southbrook_project/tests/__init__.py`
- Test: Odoo module metadata load

- [ ] **Step 1: Update the manifest dependencies**

In `addons/southbrook_project/__manifest__.py`, change the version and dependency block to:

```python
    "version": "19.0.0.2.0",
    "depends": [
        "project",
        "sale_management",
        "purchase",
        "mrp",
        "maintenance",
        "southbrook_mrp_pm",
        "southbrook_mrp_kitchen_tools",
        "southbrook_kitchen_mrp",
        "southbrook_manufacturing_intelligence",
    ],
```

Change the data block to:

```python
    "data": [
        "data/project_tags.xml",
        "views/project_task_views.xml",
        "views/mrp_command_center_views.xml",
    ],
```

- [ ] **Step 2: Add model import**

In `addons/southbrook_project/models/__init__.py`, make the imports:

```python
# SPDX-License-Identifier: LGPL-3.0-only
from . import project_task
from . import manufacturing_command
```

- [ ] **Step 3: Add test package**

Create `addons/southbrook_project/tests/__init__.py`:

```python
# SPDX-License-Identifier: LGPL-3.0-only
from . import test_mrp_command_center
from . import test_mrp_command_views
```

- [ ] **Step 4: Verify manifest syntax**

Run:

```bash
python3 -m py_compile addons/southbrook_project/__manifest__.py
```

Expected: command exits `0`.

- [ ] **Step 5: Commit**

```bash
git add addons/southbrook_project/__manifest__.py \
        addons/southbrook_project/models/__init__.py \
        addons/southbrook_project/tests/__init__.py
git commit -m "feat(project): prepare MRP command center dependencies"
```

---

## Task 2: Add Readiness Fields And Gate Engine

**Files:**
- Create: `addons/southbrook_project/models/manufacturing_command.py`
- Create/Modify: `addons/southbrook_project/tests/test_mrp_command_center.py`

- [ ] **Step 1: Write the failing score test**

Create `addons/southbrook_project/tests/test_mrp_command_center.py` with:

```python
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "mrp_command")
class TestMrpCommandCenter(TransactionCase):

    def _new_task(self, **vals):
        project = self.env["project.project"].create({
            "name": vals.pop("project_name", "MRP Command Test Project"),
        })
        defaults = {
            "name": "SO24091 Kitchen A",
            "project_id": project.id,
        }
        defaults.update(vals)
        return self.env["project.task"].create(defaults)

    def test_ready_task_scores_100(self):
        task = self._new_task()
        gates = {
            "estimate": {
                "state": "ready",
                "message": "Estimate approved",
                "action": False,
                "blocking": False,
            },
            "engineering": {
                "state": "ready",
                "message": "Drawings approved",
                "action": False,
                "blocking": False,
            },
            "bom_cutlist": {
                "state": "ready",
                "message": "BOM and cutlist ready",
                "action": False,
                "blocking": False,
            },
            "purchasing": {
                "state": "ready",
                "message": "Purchasing ready",
                "action": False,
                "blocking": False,
            },
            "materials": {
                "state": "ready",
                "message": "Materials ready",
                "action": False,
                "blocking": False,
            },
            "tooling": {
                "state": "ready",
                "message": "Tooling ready",
                "action": False,
                "blocking": False,
            },
            "labor": {
                "state": "ready",
                "message": "Labor assigned",
                "action": False,
                "blocking": False,
            },
            "equipment": {
                "state": "ready",
                "message": "Equipment ready",
                "action": False,
                "blocking": False,
            },
            "schedule": {
                "state": "ready",
                "message": "Schedule ready",
                "action": False,
                "blocking": False,
            },
            "delivery": {
                "state": "ready",
                "message": "Delivery not due",
                "action": False,
                "blocking": False,
            },
            "install": {
                "state": "ready",
                "message": "Install not due",
                "action": False,
                "blocking": False,
            },
        }
        score, state, blocked_gate, summary, next_action = (
            task._southbrook_score_from_gates(gates)
        )
        self.assertEqual(score, 100)
        self.assertEqual(state, "ready")
        self.assertFalse(blocked_gate)
        self.assertEqual(summary, "All release gates are ready.")
        self.assertFalse(next_action)

    def test_blocked_gate_caps_score_and_summary(self):
        task = self._new_task()
        gates = {
            "bom_cutlist": {
                "state": "blocked",
                "message": "BOM or cutlist missing",
                "action": "Generate the cutlist before release.",
                "blocking": True,
            },
            "tooling": {
                "state": "warning",
                "message": "Tooling has warnings",
                "action": "Review optional tooling.",
                "blocking": False,
            },
        }
        score, state, blocked_gate, summary, next_action = (
            task._southbrook_score_from_gates(gates)
        )
        self.assertLessEqual(score, 69)
        self.assertEqual(state, "blocked")
        self.assertEqual(blocked_gate, "bom_cutlist")
        self.assertIn("BOM or cutlist missing", summary)
        self.assertEqual(next_action, "Generate the cutlist before release.")
```

- [ ] **Step 2: Run RED**

Run:

```bash
odoo -d southbrook -u southbrook_project \
  --test-enable --test-tags /southbrook_project:mrp_command \
  --stop-after-init --no-http
```

Expected before implementation: fail because `_southbrook_score_from_gates` is missing.

- [ ] **Step 3: Add readiness model file**

Create `addons/southbrook_project/models/manufacturing_command.py`:

```python
# SPDX-License-Identifier: LGPL-3.0-only
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError


READINESS_STATES = [
    ("ready", "Ready"),
    ("at_risk", "At Risk"),
    ("blocked", "Blocked"),
]

GATE_STATES = [
    ("not_started", "Not Started"),
    ("ready", "Ready"),
    ("warning", "Warning"),
    ("blocked", "Blocked"),
    ("waived", "Waived"),
]

GATE_SEQUENCE = [
    "estimate",
    "engineering",
    "bom_cutlist",
    "purchasing",
    "materials",
    "tooling",
    "labor",
    "equipment",
    "schedule",
    "delivery",
    "install",
]

GATE_LABELS = {
    "estimate": "Estimate",
    "engineering": "Engineering",
    "bom_cutlist": "BOM / Cutlist",
    "purchasing": "Purchasing",
    "materials": "Materials",
    "tooling": "Tooling",
    "labor": "Labor",
    "equipment": "Equipment",
    "schedule": "Production Schedule",
    "delivery": "Delivery",
    "install": "Install",
}

GATE_WEIGHTS = {
    "estimate": 4,
    "engineering": 10,
    "bom_cutlist": 12,
    "purchasing": 9,
    "materials": 9,
    "tooling": 12,
    "labor": 10,
    "equipment": 10,
    "schedule": 12,
    "delivery": 6,
    "install": 6,
}


class ProjectTask(models.Model):
    _inherit = "project.task"

    x_southbrook_readiness_score = fields.Integer(
        string="MRP Readiness Score",
        compute="_compute_southbrook_mrp_readiness",
        store=False,
    )
    x_southbrook_readiness_state = fields.Selection(
        READINESS_STATES,
        string="MRP Readiness",
        compute="_compute_southbrook_mrp_readiness",
        store=False,
    )
    x_southbrook_blocking_gate = fields.Selection(
        [(key, label) for key, label in GATE_LABELS.items()],
        string="Blocking Gate",
        compute="_compute_southbrook_mrp_readiness",
        store=False,
    )
    x_southbrook_blocker_summary = fields.Text(
        string="Blocker Summary",
        compute="_compute_southbrook_mrp_readiness",
        store=False,
    )
    x_southbrook_next_action = fields.Text(
        string="Next Action",
        compute="_compute_southbrook_mrp_readiness",
        store=False,
    )
    x_southbrook_gate_json = fields.Text(
        string="MRP Gate Detail",
        compute="_compute_southbrook_mrp_readiness",
        store=False,
    )

    @api.depends(
        "x_southbrook_sale_order_id",
        "x_southbrook_sale_order_id.state",
    )
    def _compute_southbrook_mrp_readiness(self):
        for task in self:
            gates = task._southbrook_collect_readiness_gates()
            score, state, blocked_gate, summary, next_action = (
                task._southbrook_score_from_gates(gates)
            )
            task.x_southbrook_readiness_score = score
            task.x_southbrook_readiness_state = state
            task.x_southbrook_blocking_gate = blocked_gate
            task.x_southbrook_blocker_summary = summary
            task.x_southbrook_next_action = next_action
            task.x_southbrook_gate_json = json.dumps(
                task._southbrook_gate_rows(gates),
                sort_keys=True,
            )

    def _southbrook_default_gate(self, gate, state="ready", message=False,
                                 action=False, blocking=False):
        return {
            "gate": gate,
            "label": GATE_LABELS[gate],
            "state": state,
            "message": message or _("%s ready.") % GATE_LABELS[gate],
            "action": action or False,
            "blocking": bool(blocking),
        }

    def _southbrook_gate_rows(self, gates):
        rows = []
        for gate in GATE_SEQUENCE:
            value = dict(gates.get(gate) or self._southbrook_default_gate(gate))
            value.setdefault("gate", gate)
            value.setdefault("label", GATE_LABELS[gate])
            rows.append(value)
        return rows

    def _southbrook_score_from_gates(self, gates):
        rows = self._southbrook_gate_rows(gates)
        total_weight = sum(GATE_WEIGHTS.values())
        earned = 0
        blockers = []
        warnings = []
        for row in rows:
            gate = row["gate"]
            state = row.get("state") or "not_started"
            weight = GATE_WEIGHTS[gate]
            if state in ("ready", "waived"):
                earned += weight
            elif state == "warning":
                earned += int(weight * 0.5)
                warnings.append(row)
            elif state == "blocked":
                blockers.append(row)
        score = int(round((earned / float(total_weight)) * 100.0))
        if blockers:
            score = min(score, 69)
            first = blockers[0]
            summary = "; ".join(
                (row.get("message") or GATE_LABELS[row["gate"]])
                for row in blockers[:3]
            )
            return (
                score,
                "blocked",
                first["gate"],
                summary,
                first.get("action") or first.get("message") or False,
            )
        if warnings:
            score = min(score, 89)
            first = warnings[0]
            summary = "; ".join(
                (row.get("message") or GATE_LABELS[row["gate"]])
                for row in warnings[:3]
            )
            return (
                score,
                "at_risk",
                False,
                summary,
                first.get("action") or first.get("message") or False,
            )
        return score, "ready", False, _("All release gates are ready."), False

    def _southbrook_collect_readiness_gates(self):
        self.ensure_one()
        return {
            gate: self._southbrook_default_gate(gate)
            for gate in GATE_SEQUENCE
        }
```

- [ ] **Step 4: Run GREEN**

Run the same Odoo test command.

Expected: both score tests pass.

- [ ] **Step 5: Commit**

```bash
git add addons/southbrook_project/models/manufacturing_command.py \
        addons/southbrook_project/tests/test_mrp_command_center.py
git commit -m "feat(project): add MRP readiness gate engine"
```

---

## Task 3: Aggregate Manufacturing Signals Into Gates

**Files:**
- Modify: `addons/southbrook_project/models/manufacturing_command.py`
- Modify: `addons/southbrook_project/tests/test_mrp_command_center.py`

- [ ] **Step 1: Add failing tests for missing production package and tool blocker**

Append to `TestMrpCommandCenter`:

```python
    def _new_mo_for_task(self, task):
        product = self.env["product.product"].create({
            "name": "MRP Command Cabinet",
            "type": "consu",
            "is_storable": True,
        })
        mo = self.env["mrp.production"].create({
            "product_id": product.id,
            "product_uom_id": product.uom_id.id,
            "product_qty": 1.0,
            "origin": task.x_southbrook_sale_order_id.name
            if task.x_southbrook_sale_order_id else task.name,
        })
        return mo

    def _new_sale_order_task(self):
        partner = self.env["res.partner"].create({"name": "MRP Command Customer"})
        sale = self.env["sale.order"].create({"partner_id": partner.id})
        return self._new_task(x_southbrook_sale_order_id=sale.id), sale

    def test_missing_package_blocks_bom_cutlist_gate(self):
        task, sale = self._new_sale_order_task()
        self._new_mo_for_task(task)
        gates = task._southbrook_collect_readiness_gates()
        self.assertEqual(gates["bom_cutlist"]["state"], "blocked")
        self.assertTrue(gates["bom_cutlist"]["blocking"])
        self.assertIn("production package", gates["bom_cutlist"]["message"].lower())

    def test_tool_readiness_blocker_blocks_tooling_gate(self):
        task, sale = self._new_sale_order_task()
        mo = self._new_mo_for_task(task)
        workcenter = self.env["mrp.workcenter"].create({
            "name": "MRP Command CNC",
            "code": "MCC-CNC",
        })
        workorder = self.env["mrp.workorder"].create({
            "name": "CNC",
            "production_id": mo.id,
            "workcenter_id": workcenter.id,
            "state": "ready",
            "southbrook_tool_readiness_state": "blocked",
            "southbrook_tool_readiness_msg": "Blocked: need compression bit",
        })
        gates = task._southbrook_collect_readiness_gates()
        self.assertEqual(gates["tooling"]["state"], "blocked")
        self.assertIn("compression bit", gates["tooling"]["message"])
```

- [ ] **Step 2: Run RED**

Run:

```bash
odoo -d southbrook -u southbrook_project \
  --test-enable --test-tags /southbrook_project:mrp_command \
  --stop-after-init --no-http
```

Expected: new tests fail because collectors only return default-ready gates.

- [ ] **Step 3: Add related record collectors and gate aggregation**

In `addons/southbrook_project/models/manufacturing_command.py`, replace `_southbrook_collect_readiness_gates` and add these helpers inside `ProjectTask`:

```python
    def _southbrook_related_sale_order(self):
        self.ensure_one()
        return self.x_southbrook_sale_order_id

    def _southbrook_related_productions(self):
        self.ensure_one()
        sale = self._southbrook_related_sale_order()
        domain = []
        if sale:
            domain = [("origin", "=", sale.name)]
        else:
            domain = [("origin", "=", self.name)]
        return self.env["mrp.production"].sudo().search(domain)

    def _southbrook_related_packages(self, productions=False):
        productions = productions or self._southbrook_related_productions()
        if not productions:
            return self.env["sb.production.package"]
        return self.env["sb.production.package"].sudo().search([
            ("mo_id", "in", productions.ids),
        ])

    def _southbrook_related_workorders(self, productions=False):
        productions = productions or self._southbrook_related_productions()
        if not productions:
            return self.env["mrp.workorder"]
        return productions.mapped("workorder_ids")

    def _southbrook_related_mi_checks(self, productions=False, packages=False):
        Check = self.env["southbrook.mi.check"].sudo()
        domains = []
        if productions:
            domains.append(("production_id", "in", productions.ids))
        if packages:
            domains.append(("production_package_id", "in", packages.ids))
        if not domains:
            return Check
        if len(domains) == 1:
            return Check.search([domains[0]])
        return Check.search(["|", domains[0], domains[1]])

    def _southbrook_gate_from_checks(self, gate, checks, fallback_ready):
        blockers = checks.filtered(lambda check: check.severity == "blocker")
        warnings = checks.filtered(lambda check: check.severity == "warning")
        if blockers:
            first = blockers.sorted(key=lambda c: (c.sequence or 100, c.id))[0]
            return self._southbrook_default_gate(
                gate,
                state="blocked",
                message=first.message or first.name,
                action=first.recommendation or first.message,
                blocking=True,
            )
        if warnings:
            first = warnings.sorted(key=lambda c: (c.sequence or 100, c.id))[0]
            return self._southbrook_default_gate(
                gate,
                state="warning",
                message=first.message or first.name,
                action=first.recommendation or first.message,
                blocking=False,
            )
        return fallback_ready

    def _southbrook_collect_readiness_gates(self):
        self.ensure_one()
        gates = {
            gate: self._southbrook_default_gate(gate)
            for gate in GATE_SEQUENCE
        }
        sale = self._southbrook_related_sale_order()
        productions = self._southbrook_related_productions()
        packages = self._southbrook_related_packages(productions)
        workorders = self._southbrook_related_workorders(productions)
        checks = self._southbrook_related_mi_checks(productions, packages)

        if not sale:
            gates["estimate"] = self._southbrook_default_gate(
                "estimate",
                state="warning",
                message=_("No originating quote or sales order is linked."),
                action=_("Link the project task to its originating sales order."),
            )
        elif sale.state not in ("sale", "done"):
            gates["estimate"] = self._southbrook_default_gate(
                "estimate",
                state="blocked",
                message=_("Sales order is not confirmed."),
                action=_("Confirm the sales order before release."),
                blocking=True,
            )

        if not productions:
            gates["schedule"] = self._southbrook_default_gate(
                "schedule",
                state="warning",
                message=_("No manufacturing orders exist for this job yet."),
                action=_("Release the job to create manufacturing orders."),
            )
        elif not packages:
            gates["bom_cutlist"] = self._southbrook_default_gate(
                "bom_cutlist",
                state="blocked",
                message=_("No production package is linked to the manufacturing order."),
                action=_("Create or recompute the production package and cutlist."),
                blocking=True,
            )
        else:
            package_blockers = packages.filtered(
                lambda package: package.x_mi_status == "blocked"
            )
            if package_blockers:
                first = package_blockers[0]
                gates["bom_cutlist"] = self._southbrook_default_gate(
                    "bom_cutlist",
                    state="blocked",
                    message=first.x_mi_next_stage_action
                    or first.x_mi_next_action
                    or _("Production package has blockers."),
                    action=first.x_mi_next_stage_action
                    or first.x_mi_next_action
                    or _("Open the production package intelligence checks."),
                    blocking=True,
                )

        tooling_blockers = workorders.filtered(
            lambda wo: getattr(wo, "southbrook_tool_readiness_state", False)
            == "blocked"
        )
        tooling_warnings = workorders.filtered(
            lambda wo: getattr(wo, "southbrook_tool_readiness_state", False)
            == "warning"
        )
        if tooling_blockers:
            first = tooling_blockers[0]
            gates["tooling"] = self._southbrook_default_gate(
                "tooling",
                state="blocked",
                message=first.southbrook_tool_readiness_msg
                or _("A work order is blocked by missing tooling."),
                action=_("Clear mandatory tool readiness before release."),
                blocking=True,
            )
        elif tooling_warnings:
            first = tooling_warnings[0]
            gates["tooling"] = self._southbrook_default_gate(
                "tooling",
                state="warning",
                message=first.southbrook_tool_readiness_msg
                or _("A work order has tooling warnings."),
                action=_("Review optional tooling before release."),
            )

        equipment_checks = checks.filtered(lambda check: check.stage in (
            "cnc", "edgeband", "assembly", "finish_qc"
        ) and check.category in ("production", "assembly"))
        gates["equipment"] = self._southbrook_gate_from_checks(
            "equipment", equipment_checks, gates["equipment"]
        )

        install_checks = checks.filtered(lambda check: check.stage == "install")
        gates["install"] = self._southbrook_gate_from_checks(
            "install", install_checks, gates["install"]
        )

        if workorders and any(not wo.date_start for wo in workorders):
            gates["schedule"] = self._southbrook_default_gate(
                "schedule",
                state="warning",
                message=_("One or more work orders are not scheduled."),
                action=_("Plan work orders before the daily production meeting."),
            )

        return gates
```

- [ ] **Step 4: Run GREEN**

Run the same Odoo test command.

Expected: all `mrp_command` tests pass.

- [ ] **Step 5: Commit**

```bash
git add addons/southbrook_project/models/manufacturing_command.py \
        addons/southbrook_project/tests/test_mrp_command_center.py
git commit -m "feat(project): aggregate MRP readiness gates"
```

---

## Task 4: Add Release-To-Production Gate

**Files:**
- Modify: `addons/southbrook_project/models/manufacturing_command.py`
- Modify: `addons/southbrook_project/tests/test_mrp_command_center.py`

- [ ] **Step 1: Add failing release blocker test**

Append to `TestMrpCommandCenter`:

```python
    def test_release_to_production_raises_with_blocker_summary(self):
        task, sale = self._new_sale_order_task()
        sale.action_confirm()
        self._new_mo_for_task(task)
        with self.assertRaises(UserError) as err:
            task.action_southbrook_release_to_production()
        self.assertIn("Cannot release", str(err.exception))
        self.assertIn("production package", str(err.exception).lower())
```

- [ ] **Step 2: Run RED**

Run:

```bash
odoo -d southbrook -u southbrook_project \
  --test-enable --test-tags /southbrook_project:mrp_command \
  --stop-after-init --no-http
```

Expected: fail because `action_southbrook_release_to_production` is missing.

- [ ] **Step 3: Implement release action**

Add to `ProjectTask` in `manufacturing_command.py`:

```python
    def action_southbrook_recompute_mrp_readiness(self):
        for task in self:
            productions = task._southbrook_related_productions()
            for production in productions:
                if hasattr(production, "action_recompute_manufacturing_intelligence"):
                    production.action_recompute_manufacturing_intelligence()
            packages = task._southbrook_related_packages(productions)
            for package in packages:
                if hasattr(package, "action_recompute_manufacturing_intelligence"):
                    package.action_recompute_manufacturing_intelligence()
            workorders = task._southbrook_related_workorders(productions)
            for workorder in workorders:
                if hasattr(workorder, "action_check_tool_readiness"):
                    workorder.action_check_tool_readiness()
        return True

    def action_southbrook_release_to_production(self):
        self.ensure_one()
        self.action_southbrook_recompute_mrp_readiness()
        gates = self._southbrook_collect_readiness_gates()
        score, state, blocked_gate, summary, next_action = (
            self._southbrook_score_from_gates(gates)
        )
        if state == "blocked":
            raise UserError(_(
                "Cannot release %(job)s. %(summary)s"
            ) % {
                "job": self.display_name,
                "summary": summary,
            })
        sale = self._southbrook_related_sale_order()
        if sale and hasattr(sale, "action_send_to_production"):
            return sale.action_send_to_production()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Ready for Production"),
                "message": _("All release gates are ready."),
                "type": "success",
                "sticky": False,
            },
        }
```

- [ ] **Step 4: Run GREEN**

Run the same Odoo test command.

Expected: release blocker test passes.

- [ ] **Step 5: Commit**

```bash
git add addons/southbrook_project/models/manufacturing_command.py \
        addons/southbrook_project/tests/test_mrp_command_center.py
git commit -m "feat(project): gate production release by readiness"
```

---

## Task 5: Add Project Command Panel UX

**Files:**
- Modify: `addons/southbrook_project/views/project_task_views.xml`
- Create/Modify: `addons/southbrook_project/tests/test_mrp_command_views.py`

- [ ] **Step 1: Add failing view test**

Create `addons/southbrook_project/tests/test_mrp_command_views.py`:

```python
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "mrp_command")
class TestMrpCommandViews(TransactionCase):

    def test_project_task_form_has_mrp_command_panel(self):
        view = self.env.ref("southbrook_project.view_project_task_form_inherit_southbrook")
        arch = view.arch_db
        for marker in [
            "southbrook_mrp_command",
            "x_southbrook_readiness_score",
            "x_southbrook_readiness_state",
            "x_southbrook_blocking_gate",
            "x_southbrook_blocker_summary",
            "action_southbrook_release_to_production",
            "action_southbrook_recompute_mrp_readiness",
        ]:
            self.assertIn(marker, arch)
```

- [ ] **Step 2: Run RED**

Run:

```bash
odoo -d southbrook -u southbrook_project \
  --test-enable --test-tags /southbrook_project:mrp_command \
  --stop-after-init --no-http
```

Expected: fail because view markers are missing.

- [ ] **Step 3: Add header buttons and command page**

In `addons/southbrook_project/views/project_task_views.xml`, inside the existing form inheritance record, add this under the existing header xpath:

```xml
                <button name="action_southbrook_recompute_mrp_readiness"
                        string="Recompute Readiness"
                        type="object"
                        class="btn-secondary"/>
                <button name="action_southbrook_release_to_production"
                        string="Release to Production"
                        type="object"
                        class="btn-primary"
                        invisible="x_southbrook_readiness_state == 'blocked'"/>
                <field name="x_southbrook_readiness_state"
                       widget="badge"
                       decoration-success="x_southbrook_readiness_state == 'ready'"
                       decoration-warning="x_southbrook_readiness_state == 'at_risk'"
                       decoration-danger="x_southbrook_readiness_state == 'blocked'"/>
```

Inside the existing notebook xpath, after the Cabinetry Specs page, add:

```xml
                <page string="Manufacturing Command"
                      name="southbrook_mrp_command">
                    <group>
                        <group string="Readiness">
                            <field name="x_southbrook_readiness_score"/>
                            <field name="x_southbrook_readiness_state"
                                   widget="badge"
                                   decoration-success="x_southbrook_readiness_state == 'ready'"
                                   decoration-warning="x_southbrook_readiness_state == 'at_risk'"
                                   decoration-danger="x_southbrook_readiness_state == 'blocked'"/>
                            <field name="x_southbrook_blocking_gate"/>
                            <field name="x_southbrook_next_action"/>
                        </group>
                        <group string="Source Links">
                            <field name="x_southbrook_sale_order_id"
                                   options="{'no_create': True, 'no_open': False}"/>
                        </group>
                    </group>
                    <group string="Blocker Summary">
                        <field name="x_southbrook_blocker_summary"
                               nolabel="1"
                               readonly="1"/>
                    </group>
                    <group string="Gate Detail">
                        <field name="x_southbrook_gate_json"
                               nolabel="1"
                               readonly="1"/>
                    </group>
                </page>
```

- [ ] **Step 4: Run GREEN**

Run the same Odoo test command.

Expected: view test passes.

- [ ] **Step 5: Commit**

```bash
git add addons/southbrook_project/views/project_task_views.xml \
        addons/southbrook_project/tests/test_mrp_command_views.py
git commit -m "feat(project): add MRP command panel"
```

---

## Task 6: Add PM Queues And Daily Production Meeting Views

**Files:**
- Create: `addons/southbrook_project/views/mrp_command_center_views.xml`
- Modify: `addons/southbrook_project/tests/test_mrp_command_views.py`

- [ ] **Step 1: Add failing action/view test**

Append to `TestMrpCommandViews`:

```python
    def test_mrp_command_center_actions_load(self):
        xmlids = [
            "southbrook_project.view_project_task_list_mrp_command",
            "southbrook_project.view_project_task_search_mrp_command",
            "southbrook_project.view_project_task_kanban_mrp_command",
            "southbrook_project.action_mrp_command_daily_meeting",
            "southbrook_project.action_mrp_command_blocked_jobs",
            "southbrook_project.action_mrp_command_ready_jobs",
            "southbrook_project.action_mrp_command_at_risk_jobs",
        ]
        for xmlid in xmlids:
            self.assertTrue(self.env.ref(xmlid, raise_if_not_found=False), xmlid)
        search = self.env.ref("southbrook_project.view_project_task_search_mrp_command")
        for marker in [
            "readiness_blocked",
            "readiness_ready",
            "readiness_at_risk",
            "group_blocking_gate",
            "group_readiness_state",
        ]:
            self.assertIn(marker, search.arch_db)
```

- [ ] **Step 2: Run RED**

Run:

```bash
odoo -d southbrook -u southbrook_project \
  --test-enable --test-tags /southbrook_project:mrp_command \
  --stop-after-init --no-http
```

Expected: fail because XML ids are missing.

- [ ] **Step 3: Create command center XML**

Create `addons/southbrook_project/views/mrp_command_center_views.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
  <data>
    <record id="view_project_task_list_mrp_command" model="ir.ui.view">
      <field name="name">project.task.list.mrp.command</field>
      <field name="model">project.task</field>
      <field name="arch" type="xml">
        <list string="MRP Command Center"
              decoration-danger="x_southbrook_readiness_state == 'blocked'"
              decoration-warning="x_southbrook_readiness_state == 'at_risk'"
              decoration-success="x_southbrook_readiness_state == 'ready'">
          <field name="name"/>
          <field name="project_id"/>
          <field name="x_southbrook_sale_order_id"/>
          <field name="x_southbrook_readiness_score"/>
          <field name="x_southbrook_readiness_state" widget="badge"/>
          <field name="x_southbrook_blocking_gate"/>
          <field name="x_southbrook_next_action"/>
          <field name="date_deadline"/>
          <field name="user_ids" widget="many2many_tags"/>
        </list>
      </field>
    </record>

    <record id="view_project_task_search_mrp_command" model="ir.ui.view">
      <field name="name">project.task.search.mrp.command</field>
      <field name="model">project.task</field>
      <field name="arch" type="xml">
        <search string="MRP Command Center">
          <field name="name"/>
          <field name="project_id"/>
          <field name="x_southbrook_sale_order_id"/>
          <field name="x_southbrook_readiness_state"/>
          <field name="x_southbrook_blocking_gate"/>
          <filter name="readiness_blocked"
                  string="Blocked"
                  domain="[('x_southbrook_readiness_state','=','blocked')]"/>
          <filter name="readiness_at_risk"
                  string="At Risk"
                  domain="[('x_southbrook_readiness_state','=','at_risk')]"/>
          <filter name="readiness_ready"
                  string="Ready"
                  domain="[('x_southbrook_readiness_state','=','ready')]"/>
          <separator/>
          <filter name="gate_bom"
                  string="BOM / Cutlist"
                  domain="[('x_southbrook_blocking_gate','=','bom_cutlist')]"/>
          <filter name="gate_purchasing"
                  string="Purchasing"
                  domain="[('x_southbrook_blocking_gate','=','purchasing')]"/>
          <filter name="gate_tooling"
                  string="Tooling"
                  domain="[('x_southbrook_blocking_gate','=','tooling')]"/>
          <filter name="gate_equipment"
                  string="Equipment"
                  domain="[('x_southbrook_blocking_gate','=','equipment')]"/>
          <group>
            <filter name="group_readiness_state"
                    string="Readiness"
                    context="{'group_by':'x_southbrook_readiness_state'}"/>
            <filter name="group_blocking_gate"
                    string="Blocking Gate"
                    context="{'group_by':'x_southbrook_blocking_gate'}"/>
            <filter name="group_project"
                    string="Project"
                    context="{'group_by':'project_id'}"/>
          </group>
        </search>
      </field>
    </record>

    <record id="view_project_task_kanban_mrp_command" model="ir.ui.view">
      <field name="name">project.task.kanban.mrp.command</field>
      <field name="model">project.task</field>
      <field name="arch" type="xml">
        <kanban class="o_kanban_small_column">
          <field name="name"/>
          <field name="x_southbrook_readiness_score"/>
          <field name="x_southbrook_readiness_state"/>
          <field name="x_southbrook_blocking_gate"/>
          <field name="x_southbrook_next_action"/>
          <templates>
            <t t-name="card">
              <div class="oe_kanban_card oe_kanban_global_click">
                <strong><field name="name"/></strong>
                <div>
                  <span>Score </span>
                  <field name="x_southbrook_readiness_score"/>
                </div>
                <div>
                  <field name="x_southbrook_readiness_state" widget="badge"/>
                </div>
                <div>
                  <field name="x_southbrook_blocking_gate"/>
                </div>
                <small>
                  <field name="x_southbrook_next_action"/>
                </small>
              </div>
            </t>
          </templates>
        </kanban>
      </field>
    </record>

    <record id="action_mrp_command_daily_meeting" model="ir.actions.act_window">
      <field name="name">Daily Production Meeting</field>
      <field name="res_model">project.task</field>
      <field name="view_mode">kanban,list,form</field>
      <field name="view_id" ref="view_project_task_kanban_mrp_command"/>
      <field name="search_view_id" ref="view_project_task_search_mrp_command"/>
      <field name="context">{'search_default_group_readiness_state': 1}</field>
    </record>

    <record id="action_mrp_command_blocked_jobs" model="ir.actions.act_window">
      <field name="name">Blocked Jobs</field>
      <field name="res_model">project.task</field>
      <field name="view_mode">list,form</field>
      <field name="view_id" ref="view_project_task_list_mrp_command"/>
      <field name="search_view_id" ref="view_project_task_search_mrp_command"/>
      <field name="domain">[('x_southbrook_readiness_state','=','blocked')]</field>
    </record>

    <record id="action_mrp_command_at_risk_jobs" model="ir.actions.act_window">
      <field name="name">At-Risk Jobs</field>
      <field name="res_model">project.task</field>
      <field name="view_mode">list,form</field>
      <field name="view_id" ref="view_project_task_list_mrp_command"/>
      <field name="search_view_id" ref="view_project_task_search_mrp_command"/>
      <field name="domain">[('x_southbrook_readiness_state','=','at_risk')]</field>
    </record>

    <record id="action_mrp_command_ready_jobs" model="ir.actions.act_window">
      <field name="name">Ready to Release</field>
      <field name="res_model">project.task</field>
      <field name="view_mode">list,form</field>
      <field name="view_id" ref="view_project_task_list_mrp_command"/>
      <field name="search_view_id" ref="view_project_task_search_mrp_command"/>
      <field name="domain">[('x_southbrook_readiness_state','=','ready')]</field>
    </record>

    <menuitem id="menu_mrp_command_daily_meeting"
              parent="southbrook_mrp_pm.menu_southbrook_pm_root"
              name="Daily Meeting"
              action="action_mrp_command_daily_meeting"
              sequence="3"/>
    <menuitem id="menu_mrp_command_blocked_jobs"
              parent="southbrook_mrp_pm.menu_southbrook_pm_root"
              name="Blocked Jobs"
              action="action_mrp_command_blocked_jobs"
              sequence="4"/>
    <menuitem id="menu_mrp_command_ready_jobs"
              parent="southbrook_mrp_pm.menu_southbrook_pm_root"
              name="Ready to Release"
              action="action_mrp_command_ready_jobs"
              sequence="8"/>
    <menuitem id="menu_mrp_command_at_risk_jobs"
              parent="southbrook_mrp_pm.menu_southbrook_pm_root"
              name="At-Risk Jobs"
              action="action_mrp_command_at_risk_jobs"
              sequence="9"/>
  </data>
</odoo>
```

- [ ] **Step 4: Run GREEN**

Run the same Odoo test command.

Expected: command-center action tests pass.

- [ ] **Step 5: Commit**

```bash
git add addons/southbrook_project/views/mrp_command_center_views.xml \
        addons/southbrook_project/tests/test_mrp_command_views.py
git commit -m "feat(project): add MRP command center queues"
```

---

## Task 7: Make Readiness Searchable For Queue Domains

**Files:**
- Modify: `addons/southbrook_project/models/manufacturing_command.py`
- Modify: `addons/southbrook_project/tests/test_mrp_command_center.py`

- [ ] **Step 1: Add failing searchability test**

Append to `TestMrpCommandCenter`:

```python
    def test_blocked_jobs_domain_finds_blocked_task(self):
        task, sale = self._new_sale_order_task()
        sale.action_confirm()
        self._new_mo_for_task(task)
        task.action_southbrook_refresh_mrp_readiness_snapshot()
        blocked = self.env["project.task"].search([
            ("x_southbrook_readiness_state", "=", "blocked"),
        ])
        self.assertIn(task, blocked)
```

- [ ] **Step 2: Run RED**

Run:

```bash
odoo -d southbrook -u southbrook_project \
  --test-enable --test-tags /southbrook_project:mrp_command \
  --stop-after-init --no-http
```

Expected: fail because non-stored computed fields cannot power reliable action domains.

- [ ] **Step 3: Store snapshot fields and add refresh action**

In `manufacturing_command.py`, change the readiness fields to stored snapshot fields instead of computed fields:

```python
    x_southbrook_readiness_score = fields.Integer(
        string="MRP Readiness Score",
        default=0,
        copy=False,
    )
    x_southbrook_readiness_state = fields.Selection(
        READINESS_STATES,
        string="MRP Readiness",
        default="at_risk",
        copy=False,
        index=True,
    )
    x_southbrook_blocking_gate = fields.Selection(
        [(key, label) for key, label in GATE_LABELS.items()],
        string="Blocking Gate",
        copy=False,
        index=True,
    )
    x_southbrook_blocker_summary = fields.Text(
        string="Blocker Summary",
        copy=False,
    )
    x_southbrook_next_action = fields.Text(
        string="Next Action",
        copy=False,
    )
    x_southbrook_gate_json = fields.Text(
        string="MRP Gate Detail",
        copy=False,
    )
```

Remove `_compute_southbrook_mrp_readiness` and add:

```python
    def action_southbrook_refresh_mrp_readiness_snapshot(self):
        for task in self:
            gates = task._southbrook_collect_readiness_gates()
            score, state, blocked_gate, summary, next_action = (
                task._southbrook_score_from_gates(gates)
            )
            task.write({
                "x_southbrook_readiness_score": score,
                "x_southbrook_readiness_state": state,
                "x_southbrook_blocking_gate": blocked_gate,
                "x_southbrook_blocker_summary": summary,
                "x_southbrook_next_action": next_action,
                "x_southbrook_gate_json": json.dumps(
                    task._southbrook_gate_rows(gates),
                    sort_keys=True,
                ),
            })
        return True
```

At the end of `action_southbrook_recompute_mrp_readiness`, add:

```python
        self.action_southbrook_refresh_mrp_readiness_snapshot()
```

In `action_southbrook_release_to_production`, replace direct scoring with:

```python
        self.action_southbrook_recompute_mrp_readiness()
        if self.x_southbrook_readiness_state == "blocked":
            raise UserError(_(
                "Cannot release %(job)s. %(summary)s"
            ) % {
                "job": self.display_name,
                "summary": self.x_southbrook_blocker_summary,
            })
```

- [ ] **Step 4: Run GREEN**

Run the same Odoo test command.

Expected: queue domain test passes.

- [ ] **Step 5: Commit**

```bash
git add addons/southbrook_project/models/manufacturing_command.py \
        addons/southbrook_project/tests/test_mrp_command_center.py
git commit -m "feat(project): store MRP readiness snapshots"
```

---

## Task 8: Final Verification And Deployment Notes

**Files:**
- Modify: `docs/superpowers/plans/2026-06-12-mrp-command-center.md` only if real-world verification changes the plan.

- [ ] **Step 1: Run focused tests**

Run:

```bash
odoo -d southbrook -u southbrook_project \
  --test-enable --test-tags /southbrook_project:mrp_command \
  --stop-after-init --no-http
```

Expected: all `mrp_command` tests pass.

- [ ] **Step 2: Run module update without tests**

Run:

```bash
odoo -d southbrook -u southbrook_project --stop-after-init --no-http
```

Expected: module update exits `0`, no XML parse errors, no missing external ids.

- [ ] **Step 3: Run rollback-only shell smoke check**

Run:

```bash
odoo shell -d southbrook --no-http <<'PY'
Task = env["project.task"]
task = Task.search([], limit=1)
if task:
    task.action_southbrook_refresh_mrp_readiness_snapshot()
    print("MRP_COMMAND", task.display_name, task.x_southbrook_readiness_state, task.x_southbrook_readiness_score)
    assert task.x_southbrook_readiness_state in ("ready", "at_risk", "blocked")
for xmlid in [
    "southbrook_project.action_mrp_command_daily_meeting",
    "southbrook_project.action_mrp_command_blocked_jobs",
    "southbrook_project.action_mrp_command_ready_jobs",
]:
    assert env.ref(xmlid, raise_if_not_found=False), xmlid
env.cr.rollback()
PY
```

Expected: output starts with `MRP_COMMAND` when a task exists, assertions pass, transaction rolls back.

- [ ] **Step 4: Inspect git status**

Run:

```bash
git status --short
```

Expected: clean working tree after commits, or only known deployment/runtime artifacts ignored by `.gitignore`.

- [ ] **Step 5: Final commit if verification required doc updates**

Only if verification changed docs:

```bash
git add docs/superpowers/plans/2026-06-12-mrp-command-center.md
git commit -m "docs: update MRP command center verification notes"
```
