# Panel Digital Twin (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every cabinet panel a persistent, queryable manufacturing identity ("passport") with genealogy — the atomic object every later AI/optimization feature depends on.

**Architecture:** A new, **additive** Odoo 19 CE module `southbrook_panel_twin` that introduces three models — `sb.panel` (identity), `sb.panel.cycle` (per-operation history), `sb.machine.event` (raw event stream / future telemetry sink) — plus a deterministic **seeded simulator** that fabricates believable genealogy with no machine connected, and a barcode-lookup method that powers the "scan → see full history" demo. It touches **no existing module** (the buggy `sb.production.package.record_scan` is left alone; the twin owns its own lookup path), so it installs and rolls back cleanly.

**Tech Stack:** Odoo 19.0 Community Edition, Python 3, XML views, Odoo `TransactionCase` tests. No JS/OWL in Phase 1.

## Global Constraints

- **License:** every new file header `# SPDX-License-Identifier: LGPL-3.0-only`; manifest `"license": "LGPL-3"`, `"author": "Southbrook Cabinetry"`, `"version": "19.0.1.0.0"`.
- **Depends only on `["mrp"]`.** No dependency on `southbrook_integrations`, `southbrook_floor_traveler`, or any telemetry module — the twin is the foundation, not a consumer. `product.product`, `res.partner`, `res.users`, `mrp.production`, `mrp.workorder`, `mrp.workcenter` are all available transitively through `mrp`.
- **Module lives at:** `~/southbrook-v19cr/addons/southbrook_panel_twin/`. Inside the running container the same path is mounted at `/mnt/extra-addons/southbrook_panel_twin/` — test code that reads files on disk must use the `/mnt/extra-addons/...` path.
- **Odoo 19 API rules (verbatim, these bite):**
  - Views use `<list>`, never `<tree>`.
  - SQL uniqueness/check constraints use `models.Constraint(...)` class attributes, **not** the deprecated `_sql_constraints` list (silently ignored in v19).
  - Search-view group-by `<group>` must carry **no** `expand` or `string` attribute (RELAXNG rejects them).
  - Security groups reference is `group_ids` (not `groups_id`); `res.groups.category_id` is removed.
  - Product "is this stockable" is `is_storable` (not `product.type == 'product'`) — only relevant if you touch products (Phase 1 does not).
- **Test environment (cannot boot Odoo on the dev Mac).** Tests run on an **isolated database on a stack**, never on live `southbrook`. Recommended host: the `odooiq` stack (per the house recipe). A brand-new module is **not auto-discovered** — you must `update_list()` before the first `-i`. Logs go to a file, so always pass `--logfile=/dev/stderr` to see test output.
- **Determinism:** the simulator MUST use a locally-seeded `random.Random(seed)` instance, never the global `random` module and never wall-clock time — same seed must reproduce byte-identical genealogy (mirrors the existing `homag_session` "deterministic with seed" convention).
- **Human-in-the-loop / additive:** Phase 1 writes only its own tables. It never calls `button_finish`, never advances a work order, never mutates an existing record. This keeps it safe to install on live southbrook later.

---

## File Structure

```
addons/southbrook_panel_twin/
  __init__.py                      # imports models
  __manifest__.py                  # manifest (deps, data, version)
  models/
    __init__.py
    sb_panel.py                    # sb.panel + create-sequence + lookup + simulator
    sb_panel_cycle.py              # sb.panel.cycle
    sb_machine_event.py            # sb.machine.event
  data/
    ir_sequence.xml                # SB-PANEL-######## sequence
  security/
    ir.model.access.csv            # read: base.group_user, write: mrp.group_mrp_user
  views/
    sb_panel_views.xml             # list + form (genealogy notebook) + search + action
    sb_panel_menus.xml             # menu under Manufacturing
  tests/
    __init__.py
    test_panel_twin.py             # all TransactionCase tests
```

**Responsibilities:** `sb_panel.py` owns identity, derivation, lookup, and the simulator (it's the aggregate root). Cycles and events are thin leaf models in their own files. Views/menus are presentation only. One test file is fine at this size.

---

## Task 1: Module scaffold that installs clean

**Files:**
- Create: `addons/southbrook_panel_twin/__init__.py`
- Create: `addons/southbrook_panel_twin/__manifest__.py`
- Create: `addons/southbrook_panel_twin/models/__init__.py`
- Create: `addons/southbrook_panel_twin/security/ir.model.access.csv`

**Interfaces:**
- Produces: an installable module named `southbrook_panel_twin` depending on `mrp`.

- [ ] **Step 1: Create the package `__init__.py`**

`addons/southbrook_panel_twin/__init__.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from . import models
```

- [ ] **Step 2: Create `models/__init__.py` (empty for now, models added in later tasks)**

`addons/southbrook_panel_twin/models/__init__.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
```

- [ ] **Step 3: Create the manifest**

`addons/southbrook_panel_twin/__manifest__.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Panel Digital Twin",
    "summary": "Per-panel manufacturing passport: identity, genealogy, "
               "event stream. Foundation for optimization + AI advisor.",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry",
    "website": "https://southbrookcabinetry.space",
    "category": "Manufacturing",
    "depends": ["mrp"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "views/sb_panel_views.xml",
        "views/sb_panel_menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
```

- [ ] **Step 4: Create a placeholder ACL file (columns only; rows added as models land)**

`addons/southbrook_panel_twin/security/ir.model.access.csv`:
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
```

- [ ] **Step 5: Temporarily trim the manifest `data` list so install works before views/sequence exist**

Edit `__manifest__.py` — comment the not-yet-created files so Task 1 installs standalone:
```python
    "data": [
        "security/ir.model.access.csv",
        # "data/ir_sequence.xml",        # Task 2
        # "views/sb_panel_views.xml",    # Task 8
        # "views/sb_panel_menus.xml",    # Task 8
    ],
```

- [ ] **Step 6: Install on an isolated test DB and verify clean install**

Run (on the odooiq stack host, adjust container/db names to your recipe):
```bash
# make the new module discoverable, then install into a throwaway db
docker exec odooiq-odoo odoo shell -d twin_test --no-http --logfile=/dev/stderr \
  -c /etc/odoo/odoo.conf <<'PY'
env['ir.module.module'].update_list()
env.cr.commit()
PY
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d twin_test \
  -i southbrook_panel_twin --stop-after-init --no-http --logfile=/dev/stderr
```
Expected: process exits 0; log shows `Module southbrook_panel_twin: loading` and no traceback.

- [ ] **Step 7: Commit**

```bash
cd ~/southbrook-v19cr
git add addons/southbrook_panel_twin
git commit -m "feat(panel-twin): scaffold installable module (Phase 1 Task 1)"
```

---

## Task 2: `sb.panel` identity model + sequence + barcode uniqueness

**Files:**
- Create: `addons/southbrook_panel_twin/models/sb_panel.py`
- Create: `addons/southbrook_panel_twin/data/ir_sequence.xml`
- Modify: `addons/southbrook_panel_twin/models/__init__.py`
- Modify: `addons/southbrook_panel_twin/security/ir.model.access.csv`
- Modify: `addons/southbrook_panel_twin/__manifest__.py` (re-enable `data/ir_sequence.xml`)
- Test: `addons/southbrook_panel_twin/tests/test_panel_twin.py`

**Interfaces:**
- Produces: model `sb.panel` with fields `name` (Char, auto from sequence), `barcode` (Char, unique), `production_id` (M2O `mrp.production`), `product_id` (M2O `product.product`), `material` (Char), `cabinet_ref` (Char), `kitchen_ref` (Char), `customer_id` (M2O `res.partner`), `state` (Selection), `install_date` (Date). Later tasks add O2M `cycle_ids`, `event_ids`, and methods `_lookup_by_barcode`, `_simulate_from_production`.

- [ ] **Step 1: Write the failing test (create the tests package + first tests)**

`addons/southbrook_panel_twin/tests/__init__.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from . import test_panel_twin
```

`addons/southbrook_panel_twin/tests/test_panel_twin.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError
from psycopg2 import IntegrityError
from odoo.tools import mute_logger


@tagged("post_install", "-at_install", "southbrook", "southbrook_panel_twin")
class TestPanelTwin(TransactionCase):

    def test_panel_gets_sequenced_name(self):
        panel = self.env["sb.panel"].create({"barcode": "BC-0001"})
        self.assertTrue(panel.name.startswith("SB-PANEL-"),
                        f"expected SB-PANEL- prefix, got {panel.name!r}")

    def test_barcode_must_be_unique(self):
        self.env["sb.panel"].create({"barcode": "BC-DUP"})
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self.env["sb.panel"].create({"barcode": "BC-DUP"})
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d twin_test \
  -u southbrook_panel_twin --test-enable --test-tags southbrook_panel_twin \
  --stop-after-init --no-http --logfile=/dev/stderr 2>&1 | grep -Ei "panel|FAIL|ERROR"
```
Expected: FAIL — model `sb.panel` does not exist.

- [ ] **Step 3: Create the model**

`addons/southbrook_panel_twin/models/sb_panel.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from odoo import api, fields, models


class SbPanel(models.Model):
    _name = "sb.panel"
    _description = "Panel Manufacturing Passport"
    _order = "name desc"

    name = fields.Char(
        string="Panel ID", required=True, copy=False, readonly=True,
        index=True, default=lambda self: "New",
    )
    barcode = fields.Char(string="Barcode", required=True, index=True, copy=False)
    production_id = fields.Many2one("mrp.production", string="Manufacturing Order",
                                    ondelete="set null", index=True)
    product_id = fields.Many2one("product.product", string="Panel Product")
    material = fields.Char(string="Material")
    cabinet_ref = fields.Char(string="Cabinet")
    kitchen_ref = fields.Char(string="Kitchen")
    customer_id = fields.Many2one("res.partner", string="Customer")
    state = fields.Selection(
        [("draft", "Draft"), ("in_progress", "In Progress"),
         ("complete", "Complete"), ("installed", "Installed")],
        string="Status", default="draft", required=True,
    )
    install_date = fields.Date(string="Installation Date")

    _barcode_unique = models.Constraint(
        "unique(barcode)",
        "A panel with this barcode already exists.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("sb.panel") or "New"
                )
        return super().create(vals_list)
```

- [ ] **Step 4: Register the model in `models/__init__.py`**

`addons/southbrook_panel_twin/models/__init__.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from . import sb_panel
```

- [ ] **Step 5: Create the sequence data**

`addons/southbrook_panel_twin/data/ir_sequence.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
    <record id="seq_sb_panel" model="ir.sequence">
        <field name="name">Panel Passport</field>
        <field name="code">sb.panel</field>
        <field name="prefix">SB-PANEL-</field>
        <field name="padding">8</field>
        <field name="number_increment">1</field>
    </record>
</odoo>
```

- [ ] **Step 6: Grant ACL rows for `sb.panel`**

Replace `addons/southbrook_panel_twin/security/ir.model.access.csv` with:
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_sb_panel_user,sb.panel user,model_sb_panel,base.group_user,1,0,0,0
access_sb_panel_mrp,sb.panel mrp,model_sb_panel,mrp.group_mrp_user,1,1,1,1
```

- [ ] **Step 7: Re-enable the sequence file in the manifest**

In `__manifest__.py`, uncomment the sequence line:
```python
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        # "views/sb_panel_views.xml",    # Task 8
        # "views/sb_panel_menus.xml",    # Task 8
    ],
```

- [ ] **Step 8: Run the tests to verify they pass**

```bash
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d twin_test \
  -u southbrook_panel_twin --test-enable --test-tags southbrook_panel_twin \
  --stop-after-init --no-http --logfile=/dev/stderr 2>&1 | grep -Ei "panel|FAIL|ERROR|0 failed"
```
Expected: both tests PASS; no failures.

- [ ] **Step 9: Commit**

```bash
cd ~/southbrook-v19cr
git add addons/southbrook_panel_twin
git commit -m "feat(panel-twin): sb.panel identity model + sequence + unique barcode (Task 2)"
```

---

## Task 3: `sb.panel.cycle` per-operation history + genealogy back-link

**Files:**
- Create: `addons/southbrook_panel_twin/models/sb_panel_cycle.py`
- Modify: `addons/southbrook_panel_twin/models/sb_panel.py` (add `cycle_ids` O2M + `qc_result` compute)
- Modify: `addons/southbrook_panel_twin/models/__init__.py`
- Modify: `addons/southbrook_panel_twin/security/ir.model.access.csv`
- Modify: `addons/southbrook_panel_twin/tests/test_panel_twin.py`

**Interfaces:**
- Consumes: `sb.panel` from Task 2.
- Produces: model `sb.panel.cycle` with `panel_id` (M2O `sb.panel`, required, ondelete cascade), `workorder_id` (M2O `mrp.workorder`), `workcenter_id` (M2O `mrp.workcenter`), `operation` (Char), `program` (Char), `tool_ref` (Char), `operator_id` (M2O `res.users`), `duration_s` (Float), `qc_result` (Selection pass/fail/na), `timestamp` (Datetime). Adds `sb.panel.cycle_ids` (O2M) and computed `sb.panel.qc_result` (Selection: pass if all cycles pass, fail if any fail, else na).

- [ ] **Step 1: Write the failing test**

Append to `addons/southbrook_panel_twin/tests/test_panel_twin.py` (inside the class):
```python
    def test_cycle_links_to_panel_and_rolls_up_qc(self):
        panel = self.env["sb.panel"].create({"barcode": "BC-QC-1"})
        self.env["sb.panel.cycle"].create({
            "panel_id": panel.id, "operation": "CUT", "qc_result": "pass",
        })
        self.env["sb.panel.cycle"].create({
            "panel_id": panel.id, "operation": "DRILL", "qc_result": "pass",
        })
        self.assertEqual(len(panel.cycle_ids), 2)
        self.assertEqual(panel.qc_result, "pass")

    def test_panel_qc_fails_if_any_cycle_fails(self):
        panel = self.env["sb.panel"].create({"barcode": "BC-QC-2"})
        self.env["sb.panel.cycle"].create({
            "panel_id": panel.id, "operation": "DRILL", "qc_result": "fail",
        })
        self.assertEqual(panel.qc_result, "fail")
```

- [ ] **Step 2: Run to verify it fails**

```bash
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d twin_test \
  -u southbrook_panel_twin --test-enable --test-tags southbrook_panel_twin \
  --stop-after-init --no-http --logfile=/dev/stderr 2>&1 | grep -Ei "cycle|FAIL|ERROR"
```
Expected: FAIL — model `sb.panel.cycle` does not exist.

- [ ] **Step 3: Create the cycle model**

`addons/southbrook_panel_twin/models/sb_panel_cycle.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields, models


class SbPanelCycle(models.Model):
    _name = "sb.panel.cycle"
    _description = "Panel Operation Cycle"
    _order = "timestamp, id"

    panel_id = fields.Many2one("sb.panel", string="Panel", required=True,
                               ondelete="cascade", index=True)
    workorder_id = fields.Many2one("mrp.workorder", string="Work Order")
    workcenter_id = fields.Many2one("mrp.workcenter", string="Work Center")
    operation = fields.Char(string="Operation")
    program = fields.Char(string="Program")
    tool_ref = fields.Char(string="Tool")
    operator_id = fields.Many2one("res.users", string="Operator")
    duration_s = fields.Float(string="Cycle Time (s)")
    qc_result = fields.Selection(
        [("pass", "Pass"), ("fail", "Fail"), ("na", "N/A")],
        string="QC", default="na", required=True,
    )
    timestamp = fields.Datetime(string="Timestamp")
```

- [ ] **Step 4: Add the O2M + rolled-up QC compute to `sb.panel`**

In `addons/southbrook_panel_twin/models/sb_panel.py`, add these fields after `install_date` and the compute method after `create`:
```python
    cycle_ids = fields.One2many("sb.panel.cycle", "panel_id", string="Operations")
    qc_result = fields.Selection(
        [("pass", "Pass"), ("fail", "Fail"), ("na", "N/A")],
        string="Overall QC", compute="_compute_qc_result", store=True,
    )

    @api.depends("cycle_ids.qc_result")
    def _compute_qc_result(self):
        for panel in self:
            results = panel.cycle_ids.mapped("qc_result")
            if "fail" in results:
                panel.qc_result = "fail"
            elif results and all(r == "pass" for r in results):
                panel.qc_result = "pass"
            else:
                panel.qc_result = "na"
```

- [ ] **Step 5: Register the model**

`addons/southbrook_panel_twin/models/__init__.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from . import sb_panel
from . import sb_panel_cycle
```

- [ ] **Step 6: Add ACL rows for the cycle model**

Append to `addons/southbrook_panel_twin/security/ir.model.access.csv`:
```csv
access_sb_panel_cycle_user,sb.panel.cycle user,model_sb_panel_cycle,base.group_user,1,0,0,0
access_sb_panel_cycle_mrp,sb.panel.cycle mrp,model_sb_panel_cycle,mrp.group_mrp_user,1,1,1,1
```

- [ ] **Step 7: Run the tests to verify they pass**

```bash
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d twin_test \
  -u southbrook_panel_twin --test-enable --test-tags southbrook_panel_twin \
  --stop-after-init --no-http --logfile=/dev/stderr 2>&1 | grep -Ei "cycle|FAIL|ERROR|passed"
```
Expected: all four tests PASS.

- [ ] **Step 8: Commit**

```bash
cd ~/southbrook-v19cr
git add addons/southbrook_panel_twin
git commit -m "feat(panel-twin): sb.panel.cycle history + rolled-up QC (Task 3)"
```

---

## Task 4: `sb.machine.event` raw event stream (future telemetry sink)

**Files:**
- Create: `addons/southbrook_panel_twin/models/sb_machine_event.py`
- Modify: `addons/southbrook_panel_twin/models/sb_panel.py` (add `event_ids` O2M)
- Modify: `addons/southbrook_panel_twin/models/__init__.py`
- Modify: `addons/southbrook_panel_twin/security/ir.model.access.csv`
- Modify: `addons/southbrook_panel_twin/tests/test_panel_twin.py`

**Interfaces:**
- Consumes: `sb.panel` from Task 2.
- Produces: model `sb.machine.event` with `panel_id` (M2O `sb.panel`, optional, ondelete set null), `workorder_id` (M2O `mrp.workorder`), `workcenter_id` (M2O `mrp.workcenter`), `machine_code` (Char), `event_type` (Selection: scan/cycle_start/cycle_end/tool_change/alarm), `timestamp` (Datetime), `payload` (Text — raw JSON string). Adds `sb.panel.event_ids` (O2M). **Rationale:** events may arrive before a panel is matched, so `panel_id` is optional — this is the seam the real DRILLTEQ transport writes into in Phase 5 with no schema change.

- [ ] **Step 1: Write the failing test**

Append to the test class in `test_panel_twin.py`:
```python
    def test_event_stream_accepts_unmatched_events(self):
        # An event with no panel yet must be storable (telemetry arrives first).
        evt = self.env["sb.machine.event"].create({
            "event_type": "alarm", "machine_code": "DRILLTEQ",
            "payload": '{"code": "LOW_AIR"}',
        })
        self.assertFalse(evt.panel_id)
        panel = self.env["sb.panel"].create({"barcode": "BC-EVT-1"})
        evt.panel_id = panel.id
        self.assertIn(evt, panel.event_ids)
```

- [ ] **Step 2: Run to verify it fails**

```bash
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d twin_test \
  -u southbrook_panel_twin --test-enable --test-tags southbrook_panel_twin \
  --stop-after-init --no-http --logfile=/dev/stderr 2>&1 | grep -Ei "event|FAIL|ERROR"
```
Expected: FAIL — model `sb.machine.event` does not exist.

- [ ] **Step 3: Create the event model**

`addons/southbrook_panel_twin/models/sb_machine_event.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields, models


class SbMachineEvent(models.Model):
    _name = "sb.machine.event"
    _description = "Machine Event Stream"
    _order = "timestamp desc, id desc"

    panel_id = fields.Many2one("sb.panel", string="Panel", ondelete="set null",
                               index=True)
    workorder_id = fields.Many2one("mrp.workorder", string="Work Order")
    workcenter_id = fields.Many2one("mrp.workcenter", string="Work Center")
    machine_code = fields.Char(string="Machine")
    event_type = fields.Selection(
        [("scan", "Scan"), ("cycle_start", "Cycle Start"),
         ("cycle_end", "Cycle End"), ("tool_change", "Tool Change"),
         ("alarm", "Alarm")],
        string="Event Type", required=True,
    )
    timestamp = fields.Datetime(string="Timestamp")
    payload = fields.Text(string="Raw Payload")
```

- [ ] **Step 4: Add the O2M to `sb.panel`**

In `sb_panel.py`, after `cycle_ids`:
```python
    event_ids = fields.One2many("sb.machine.event", "panel_id", string="Events")
```

- [ ] **Step 5: Register the model**

`addons/southbrook_panel_twin/models/__init__.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from . import sb_panel
from . import sb_panel_cycle
from . import sb_machine_event
```

- [ ] **Step 6: Add ACL rows**

Append to `ir.model.access.csv`:
```csv
access_sb_machine_event_user,sb.machine.event user,model_sb_machine_event,base.group_user,1,0,0,0
access_sb_machine_event_mrp,sb.machine.event mrp,model_sb_machine_event,mrp.group_mrp_user,1,1,1,1
```

- [ ] **Step 7: Run the tests to verify they pass**

```bash
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d twin_test \
  -u southbrook_panel_twin --test-enable --test-tags southbrook_panel_twin \
  --stop-after-init --no-http --logfile=/dev/stderr 2>&1 | grep -Ei "event|FAIL|ERROR|passed"
```
Expected: all five tests PASS.

- [ ] **Step 8: Commit**

```bash
cd ~/southbrook-v19cr
git add addons/southbrook_panel_twin
git commit -m "feat(panel-twin): sb.machine.event stream w/ optional panel link (Task 4)"
```

---

## Task 5: Best-effort customer derivation from the MO (crash-safe)

**Files:**
- Modify: `addons/southbrook_panel_twin/models/sb_panel.py`
- Modify: `addons/southbrook_panel_twin/tests/test_panel_twin.py`

**Interfaces:**
- Consumes: `sb.panel.production_id`, `sb.panel.customer_id`.
- Produces: method `sb.panel._derive_customer()` that sets `customer_id` from the MO's sale/partner link **if discoverable**, else leaves it False. **Rationale:** CE `mrp.production` has no guaranteed `partner_id`; southbrook may wire it via `sale_id`/procurement. The method probes known paths with `getattr` guards so it never raises regardless of which modules are installed.

- [ ] **Step 1: Write the failing test**

Append to the test class:
```python
    def test_derive_customer_is_crash_safe_without_link(self):
        # A bare MO with no sale/partner link must not raise; customer stays empty.
        product = self.env["product.product"].create(
            {"name": "Twin Test Panel"})
        mo = self.env["mrp.production"].create({"product_id": product.id})
        panel = self.env["sb.panel"].create(
            {"barcode": "BC-CUST-1", "production_id": mo.id})
        panel._derive_customer()  # must not raise
        # No assertion on value (env-dependent); the point is no exception.
        self.assertTrue(True)
```

- [ ] **Step 2: Run to verify it fails**

```bash
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d twin_test \
  -u southbrook_panel_twin --test-enable --test-tags southbrook_panel_twin \
  --stop-after-init --no-http --logfile=/dev/stderr 2>&1 | grep -Ei "derive|FAIL|ERROR|AttributeError"
```
Expected: FAIL — `_derive_customer` is not defined.

- [ ] **Step 3: Implement the crash-safe derivation**

In `sb_panel.py`, add the method (after `_compute_qc_result`):
```python
    def _derive_customer(self):
        """Best-effort: set customer_id from the MO's sale/partner link.

        CE mrp.production has no guaranteed partner. Probe known link
        paths with getattr guards so this never raises regardless of
        which optional modules are installed. Silent no-op when nothing
        resolves.
        """
        for panel in self:
            mo = panel.production_id
            if not mo:
                continue
            partner = False
            # Path A: a direct partner_id (present if some module added it).
            partner = getattr(mo, "partner_id", False)
            # Path B: sale_id.partner_id (sale_mrp-style link).
            if not partner:
                sale = getattr(mo, "sale_id", False)
                partner = getattr(sale, "partner_id", False) if sale else False
            if partner:
                panel.customer_id = partner.id
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d twin_test \
  -u southbrook_panel_twin --test-enable --test-tags southbrook_panel_twin \
  --stop-after-init --no-http --logfile=/dev/stderr 2>&1 | grep -Ei "derive|FAIL|ERROR|passed"
```
Expected: PASS, no exception.

- [ ] **Step 5: Commit**

```bash
cd ~/southbrook-v19cr
git add addons/southbrook_panel_twin
git commit -m "feat(panel-twin): crash-safe customer derivation from MO (Task 5)"
```

---

## Task 6: Barcode lookup — "scan → full genealogy"

**Files:**
- Modify: `addons/southbrook_panel_twin/models/sb_panel.py`
- Modify: `addons/southbrook_panel_twin/tests/test_panel_twin.py`

**Interfaces:**
- Consumes: `sb.panel`, `sb.panel.cycle`.
- Produces: model method `sb.panel._lookup_by_barcode(barcode)` → returns the matching `sb.panel` recordset (empty recordset if none). This is the twin's **own** scan path — it does NOT touch `sb.production.package.record_scan`.

- [ ] **Step 1: Write the failing test**

Append to the test class:
```python
    def test_lookup_by_barcode_returns_panel_with_ordered_history(self):
        panel = self.env["sb.panel"].create({"barcode": "BC-LOOK-1"})
        self.env["sb.panel.cycle"].create({
            "panel_id": panel.id, "operation": "CUT",
            "timestamp": "2026-07-10 08:32:00",
        })
        self.env["sb.panel.cycle"].create({
            "panel_id": panel.id, "operation": "DRILL",
            "timestamp": "2026-07-10 10:08:00",
        })
        found = self.env["sb.panel"]._lookup_by_barcode("BC-LOOK-1")
        self.assertEqual(found, panel)
        # cycle_ids are _order'd by timestamp → CUT before DRILL
        self.assertEqual(found.cycle_ids.mapped("operation"), ["CUT", "DRILL"])

    def test_lookup_by_barcode_empty_when_missing(self):
        found = self.env["sb.panel"]._lookup_by_barcode("BC-DOES-NOT-EXIST")
        self.assertFalse(found)
```

- [ ] **Step 2: Run to verify it fails**

```bash
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d twin_test \
  -u southbrook_panel_twin --test-enable --test-tags southbrook_panel_twin \
  --stop-after-init --no-http --logfile=/dev/stderr 2>&1 | grep -Ei "lookup|FAIL|ERROR"
```
Expected: FAIL — `_lookup_by_barcode` not defined.

- [ ] **Step 3: Implement the lookup**

In `sb_panel.py`, add:
```python
    @api.model
    def _lookup_by_barcode(self, barcode):
        """Return the panel matching this barcode (empty recordset if none)."""
        if not barcode:
            return self.browse()
        return self.search([("barcode", "=", barcode)], limit=1)
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d twin_test \
  -u southbrook_panel_twin --test-enable --test-tags southbrook_panel_twin \
  --stop-after-init --no-http --logfile=/dev/stderr 2>&1 | grep -Ei "lookup|FAIL|ERROR|passed"
```
Expected: both new tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/southbrook-v19cr
git add addons/southbrook_panel_twin
git commit -m "feat(panel-twin): _lookup_by_barcode scan path (Task 6)"
```

---

## Task 7: Deterministic seeded simulator (genealogy with no machine)

**Files:**
- Modify: `addons/southbrook_panel_twin/models/sb_panel.py`
- Modify: `addons/southbrook_panel_twin/tests/test_panel_twin.py`

**Interfaces:**
- Consumes: `sb.panel`, `sb.panel.cycle`, `sb.machine.event`, `mrp.production`.
- Produces: method `sb.panel._simulate_from_production(production, panel_count, seed)` → creates `panel_count` panels for the given MO, each with a CUT + DRILL cycle and a matching scan event, using a **locally-seeded** `random.Random(seed)` for cycle times/QC. Returns the created `sb.panel` recordset. Same `seed` reproduces identical durations and QC outcomes.

- [ ] **Step 1: Write the failing test**

Append to the test class:
```python
    def _make_mo(self):
        product = self.env["product.product"].create({"name": "Sim Panel"})
        return self.env["mrp.production"].create({"product_id": product.id})

    def test_simulator_creates_panels_with_genealogy(self):
        mo = self._make_mo()
        panels = self.env["sb.panel"]._simulate_from_production(
            mo, panel_count=3, seed=42)
        self.assertEqual(len(panels), 3)
        for p in panels:
            self.assertEqual(p.production_id, mo)
            self.assertEqual(p.cycle_ids.mapped("operation"), ["CUT", "DRILL"])
            self.assertTrue(p.event_ids)

    def test_simulator_is_deterministic_with_seed(self):
        mo1 = self._make_mo()
        mo2 = self._make_mo()
        a = self.env["sb.panel"]._simulate_from_production(mo1, 3, seed=7)
        b = self.env["sb.panel"]._simulate_from_production(mo2, 3, seed=7)
        self.assertEqual(
            a.cycle_ids.mapped("duration_s"),
            b.cycle_ids.mapped("duration_s"),
            "same seed must produce identical cycle times",
        )
```

- [ ] **Step 2: Run to verify it fails**

```bash
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d twin_test \
  -u southbrook_panel_twin --test-enable --test-tags southbrook_panel_twin \
  --stop-after-init --no-http --logfile=/dev/stderr 2>&1 | grep -Ei "simulat|FAIL|ERROR"
```
Expected: FAIL — `_simulate_from_production` not defined.

- [ ] **Step 3: Implement the simulator**

At the top of `sb_panel.py`, add `import random` and `import json` to the imports, then add the method:
```python
    def _simulate_from_production(self, production, panel_count=1, seed=0):
        """Fabricate deterministic genealogy for an MO (no machine needed).

        Uses a locally-seeded Random so the same seed reproduces
        byte-identical cycle times + QC. Mirrors the homag_session
        'deterministic with seed' convention. Each panel gets a CUT
        and a DRILL cycle plus a scan event.
        """
        rng = random.Random(seed)
        bore_wc = self.env["mrp.workcenter"].search(
            [("code", "=", "SB-CNC-BORE")], limit=1)
        programs = ["HINGE_32MM_RIGHT", "HINGE_32MM_LEFT", "SHELF_PIN_5MM"]
        panels = self.browse()
        for _i in range(panel_count):
            panel = self.create({
                "barcode": "SIM-%s-%s" % (production.id, rng.randint(10**6, 10**7)),
                "production_id": production.id,
                "product_id": production.product_id.id,
                "material": "18mm MDF White",
                "state": "in_progress",
            })
            for op, wc in [("CUT", False), ("DRILL", bore_wc)]:
                dur = round(rng.uniform(38.0, 52.0), 1)
                qc = "pass" if rng.random() > 0.05 else "fail"
                self.env["sb.panel.cycle"].create({
                    "panel_id": panel.id,
                    "workcenter_id": wc.id if wc else False,
                    "operation": op,
                    "program": rng.choice(programs) if op == "DRILL" else False,
                    "tool_ref": "5mm Drill" if op == "DRILL" else "8mm Comp Bit",
                    "duration_s": dur,
                    "qc_result": qc,
                })
            self.env["sb.machine.event"].create({
                "panel_id": panel.id,
                "workcenter_id": bore_wc.id if bore_wc else False,
                "machine_code": "SIMULATOR",
                "event_type": "scan",
                "payload": json.dumps({"barcode": panel.barcode}),
            })
            panels |= panel
        return panels
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d twin_test \
  -u southbrook_panel_twin --test-enable --test-tags southbrook_panel_twin \
  --stop-after-init --no-http --logfile=/dev/stderr 2>&1 | grep -Ei "simulat|FAIL|ERROR|passed"
```
Expected: both simulator tests PASS (determinism holds).

- [ ] **Step 5: Commit**

```bash
cd ~/southbrook-v19cr
git add addons/southbrook_panel_twin
git commit -m "feat(panel-twin): deterministic seeded genealogy simulator (Task 7)"
```

---

## Task 8: Backend views + menu ("scan a panel → see its history")

**Files:**
- Create: `addons/southbrook_panel_twin/views/sb_panel_views.xml`
- Create: `addons/southbrook_panel_twin/views/sb_panel_menus.xml`
- Modify: `addons/southbrook_panel_twin/__manifest__.py` (re-enable view files)

**Interfaces:**
- Consumes: `sb.panel` and its O2M fields.
- Produces: an `ir.actions.act_window` `action_sb_panel`, a list + form + search view, and a menu `Manufacturing → Panel Twin → Panels`. The form's notebook renders the full genealogy (operations + events) — this is the demo surface.

- [ ] **Step 1: Create the views (note `<list>`, and search `<group>` with no attrs)**

`addons/southbrook_panel_twin/views/sb_panel_views.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_sb_panel_list" model="ir.ui.view">
        <field name="name">sb.panel.list</field>
        <field name="model">sb.panel</field>
        <field name="arch" type="xml">
            <list string="Panels">
                <field name="name"/>
                <field name="barcode"/>
                <field name="production_id"/>
                <field name="cabinet_ref"/>
                <field name="kitchen_ref"/>
                <field name="customer_id"/>
                <field name="state"/>
                <field name="qc_result"/>
            </list>
        </field>
    </record>

    <record id="view_sb_panel_form" model="ir.ui.view">
        <field name="name">sb.panel.form</field>
        <field name="model">sb.panel</field>
        <field name="arch" type="xml">
            <form string="Panel Passport">
                <sheet>
                    <div class="oe_title">
                        <h1><field name="name" readonly="1"/></h1>
                    </div>
                    <group>
                        <group>
                            <field name="barcode"/>
                            <field name="product_id"/>
                            <field name="material"/>
                            <field name="production_id"/>
                        </group>
                        <group>
                            <field name="customer_id"/>
                            <field name="kitchen_ref"/>
                            <field name="cabinet_ref"/>
                            <field name="state"/>
                            <field name="qc_result"/>
                            <field name="install_date"/>
                        </group>
                    </group>
                    <notebook>
                        <page string="Operations">
                            <field name="cycle_ids">
                                <list>
                                    <field name="timestamp"/>
                                    <field name="operation"/>
                                    <field name="workcenter_id"/>
                                    <field name="program"/>
                                    <field name="tool_ref"/>
                                    <field name="operator_id"/>
                                    <field name="duration_s"/>
                                    <field name="qc_result"/>
                                </list>
                            </field>
                        </page>
                        <page string="Machine Events">
                            <field name="event_ids">
                                <list>
                                    <field name="timestamp"/>
                                    <field name="event_type"/>
                                    <field name="machine_code"/>
                                    <field name="workcenter_id"/>
                                    <field name="payload"/>
                                </list>
                            </field>
                        </page>
                    </notebook>
                </sheet>
            </form>
        </field>
    </record>

    <record id="view_sb_panel_search" model="ir.ui.view">
        <field name="name">sb.panel.search</field>
        <field name="model">sb.panel</field>
        <field name="arch" type="xml">
            <search string="Panels">
                <field name="name"/>
                <field name="barcode"/>
                <field name="production_id"/>
                <field name="customer_id"/>
                <filter name="failed_qc" string="Failed QC"
                        domain="[('qc_result','=','fail')]"/>
                <group>
                    <filter name="group_state" string="Status"
                            context="{'group_by': 'state'}"/>
                    <filter name="group_mo" string="Manufacturing Order"
                            context="{'group_by': 'production_id'}"/>
                </group>
            </search>
        </field>
    </record>

    <record id="action_sb_panel" model="ir.actions.act_window">
        <field name="name">Panels</field>
        <field name="res_model">sb.panel</field>
        <field name="view_mode">list,form</field>
        <field name="search_view_id" ref="view_sb_panel_search"/>
    </record>
</odoo>
```

- [ ] **Step 2: Create the menu**

`addons/southbrook_panel_twin/views/sb_panel_menus.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <menuitem id="menu_sb_panel_twin_root" name="Panel Twin"
              parent="mrp.menu_mrp_root" sequence="90"/>
    <menuitem id="menu_sb_panel" name="Panels"
              parent="menu_sb_panel_twin_root"
              action="action_sb_panel" sequence="10"/>
</odoo>
```

- [ ] **Step 3: Re-enable the view files in the manifest**

`__manifest__.py` `data` list — all four active now:
```python
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "views/sb_panel_views.xml",
        "views/sb_panel_menus.xml",
    ],
```

- [ ] **Step 4: Upgrade and verify views load (validation is strict in v19)**

```bash
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d twin_test \
  -u southbrook_panel_twin --stop-after-init --no-http --logfile=/dev/stderr 2>&1 \
  | grep -Ei "panel_twin|ParseError|ValidationError|Invalid|loaded"
```
Expected: no ParseError/ValidationError; module reloads cleanly.

- [ ] **Step 5: Manual smoke — simulate genealogy, then open a panel**

```bash
docker exec odooiq-odoo odoo shell -d twin_test --no-http \
  -c /etc/odoo/odoo.conf --logfile=/dev/stderr <<'PY'
prod = env["product.product"].create({"name": "Smoke Panel"})
mo = env["mrp.production"].create({"product_id": prod.id})
panels = env["sb.panel"]._simulate_from_production(mo, panel_count=5, seed=99)
print("panels:", panels.mapped("name"))
p = env["sb.panel"]._lookup_by_barcode(panels[0].barcode)
print("genealogy:", p.name, p.cycle_ids.mapped("operation"),
      "events:", len(p.event_ids), "qc:", p.qc_result)
env.cr.rollback()   # smoke only — don't persist
PY
```
Expected: prints 5 panel IDs and a genealogy line (`['CUT','DRILL'] events: 1 qc: ...`).

- [ ] **Step 6: Commit**

```bash
cd ~/southbrook-v19cr
git add addons/southbrook_panel_twin
git commit -m "feat(panel-twin): backend views + menu, genealogy form (Task 8)"
```

---

## Task 9: Full-module verification pass + install docs

**Files:**
- Create: `addons/southbrook_panel_twin/README.md`

**Interfaces:**
- Consumes: the whole module.
- Produces: a green full-suite run and an install/deploy note.

- [ ] **Step 1: Run the entire test suite from a clean install**

```bash
# drop + recreate the test db to prove a cold install, then run all tests
docker exec odooiq-postgres dropdb -U odoo --if-exists twin_test
docker exec odooiq-postgres createdb -U odoo twin_test
docker exec odooiq-odoo odoo shell -d twin_test --no-http -c /etc/odoo/odoo.conf \
  --logfile=/dev/stderr <<'PY'
env['ir.module.module'].update_list(); env.cr.commit()
PY
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d twin_test \
  -i southbrook_panel_twin --test-enable --test-tags southbrook_panel_twin \
  --stop-after-init --no-http --logfile=/dev/stderr 2>&1 \
  | grep -Ei "FAIL|ERROR|tests? .* (passed|failed)|0 failed"
```
Expected: all tests from Tasks 2–7 pass; `0 failed`.

- [ ] **Step 2: Write the README (install order + demo)**

`addons/southbrook_panel_twin/README.md`:
```markdown
# Southbrook Panel Digital Twin (Phase 1)

Per-panel manufacturing passport: identity (`sb.panel`), genealogy
(`sb.panel.cycle`), event stream (`sb.machine.event`). Foundation for the
optimization + AI-advisor phases. Depends only on `mrp`; touches no existing
module.

## Install (isolated test db)
1. `update_list()` (new module isn't auto-discovered), then
   `odoo -d <db> -i southbrook_panel_twin --stop-after-init`.
2. Tests: add `--test-enable --test-tags southbrook_panel_twin`.

## Demo (no machine required)
```python
mo = env["mrp.production"].create({"product_id": <panel_product>.id})
env["sb.panel"]._simulate_from_production(mo, panel_count=5, seed=99)
# open Manufacturing → Panel Twin → Panels; each panel shows its
# CUT/DRILL genealogy + scan event.
```

## Phase 5 seam
`sb.machine.event.panel_id` is optional so real DRILLTEQ telemetry can be
ingested before a panel is matched. The real transport replaces the
simulator with no schema change.
```

- [ ] **Step 3: Commit**

```bash
cd ~/southbrook-v19cr
git add addons/southbrook_panel_twin
git commit -m "docs(panel-twin): README + full-suite verification (Task 9)"
```

---

## Out of scope for Phase 1 (explicit follow-ups, do NOT do here)

- **Fixing `sb.production.package.record_scan`** (routes to next *sequential* WO instead of by work center). Real bug, but it lives in `southbrook_floor_traveler` and changing it risks live flow. Track separately; the twin deliberately uses its own `_lookup_by_barcode` path.
- **Barcode label printing/application** on the floor — a physical process, not this module.
- **Real telemetry ingest** (API-key endpoint writing `sb.machine.event`) — Phase 5.
- **Tool-wear / cycle-time learning** off the event stream — Phase 6 (needs data volume).
- **Deploying to live `southbrook`** — only after green on the isolated db and a code review; use the standard rsync + `-u` + verify recipe, never a casual `docker restart southbrook-odoo`.

---

## Self-Review (completed against the Phase 1 spec)

- **Spec coverage:** `sb.panel` model ✓ (T2) · barcode ✓ (T2) · genealogy events ✓ (T3 cycles + T4 events) · operation history ✓ (T3) · "scan → complete history" demo ✓ (T6 lookup + T8 form + T8 smoke) · simulator seam ✓ (T7) · depends-on-nothing-but-Odoo ✓ (manifest `["mrp"]`). Customer/kitchen/cabinet from the passport example: customer ✓ (T5, crash-safe) · kitchen_ref/cabinet_ref ✓ (T2 Char fields, caller/simulator-populated — deliberately not over-coupled to an uncertain kitchen model).
- **Placeholder scan:** no TBD/TODO; every step has real code or a real command.
- **Type consistency:** `_lookup_by_barcode`, `_simulate_from_production(production, panel_count, seed)`, `_derive_customer`, `qc_result` selection values (`pass`/`fail`/`na`), and `event_type` values are used identically across tasks and tests.
- **Scope:** single installable module, one subsystem — correctly sized for one plan.
