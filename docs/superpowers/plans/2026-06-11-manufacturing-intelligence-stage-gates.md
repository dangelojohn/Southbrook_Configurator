# Manufacturing Intelligence Stage Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `southbrook_manufacturing_intelligence` into a stage-gate production-control addon with plant-manager dashboard views.

**Architecture:** Keep the existing addon and public recompute entry points. Extend `southbrook.mi.check` with stage metadata, make existing checks stage-aware, add rollups to `sb.production.package`, then expose manager views using standard Odoo list/search/kanban actions.

**Tech Stack:** Odoo 19 CE, Python ORM models, XML views/actions/menus, Odoo TransactionCase tests, QNAP live verification with rollback-only `odoo shell`.

---

## File Structure

- Modify `addons/southbrook_manufacturing_intelligence/__manifest__.py`
  - Bump version to `19.0.1.1.0`.
  - Add new manager view XML file to `data`.
- Modify `addons/southbrook_manufacturing_intelligence/models/mi_check.py`
  - Add `stage`, `workcenter_id`, `sequence`, `is_gate`.
- Modify `addons/southbrook_manufacturing_intelligence/models/sb_production_package.py`
  - Add blocked-stage and stage-count rollup fields.
- Modify `addons/southbrook_manufacturing_intelligence/models/mi_engine.py`
  - Add stage metadata helpers.
  - Convert existing check helpers to emit stage-aware values.
  - Add edgeband warning logic.
  - Add package stage rollup writes.
- Modify `addons/southbrook_manufacturing_intelligence/views/production_package_views.xml`
  - Show blocked stage, next stage action, and stage blocker counts.
  - Include stage columns in the check list.
- Create `addons/southbrook_manufacturing_intelligence/views/manager_dashboard_views.xml`
  - Plant-manager list/search/kanban actions for checks and packages.
- Modify `addons/southbrook_manufacturing_intelligence/tests/test_mi_engine.py`
  - Add stage metadata, rollup, and edgeband warning tests.
- Modify `addons/southbrook_manufacturing_intelligence/tests/test_mi_views.py`
  - Add manager view/action loading tests.
- Modify `addons/southbrook_manufacturing_intelligence/tests/test_mi_mrp.py`
  - Add package recompute stage rollup assertions.

---

## Task 1: Add Stage Metadata To MI Checks

**Files:**
- Modify: `addons/southbrook_manufacturing_intelligence/models/mi_check.py`
- Test: `addons/southbrook_manufacturing_intelligence/tests/test_mi_engine.py`

- [ ] **Step 1: Write the failing test**

Add this test to `TestManufacturingIntelligenceEngine`:

```python
def test_stage_values_include_stage_gate_sequence_and_workcenter(self):
    Engine = self.env["southbrook.mi.engine"]
    workcenter = self.env["mrp.workcenter"].create({"name": "Panel Saw"})
    values = Engine._stage_values(
        "saw",
        10,
        is_gate=True,
        workcenter=workcenter,
    )
    self.assertEqual(values["stage"], "saw")
    self.assertEqual(values["sequence"], 10)
    self.assertTrue(values["is_gate"])
    self.assertEqual(values["workcenter_id"], workcenter.id)
```

- [ ] **Step 2: Run test to verify RED**

Run live shell or test runner:

```bash
ssh admin@192.168.68.108 '/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker -H unix:///var/run/system-docker.sock exec -i southbrook-odoo sh -c "odoo shell --config=/etc/odoo/odoo.conf -d southbrook --no-http --workers 0"' <<'PY'
Engine = env["southbrook.mi.engine"]
assert not hasattr(Engine, "_stage_values"), "Expected _stage_values to be missing before implementation"
PY
```

Expected: command exits `0` and confirms the helper is missing before implementation.

- [ ] **Step 3: Add fields to `mi_check.py`**

Add constants above the model:

```python
MI_STAGES = [
    ("saw", "Saw"),
    ("cnc", "CNC"),
    ("edgeband", "Edgeband"),
    ("assembly", "Assembly"),
    ("finish_qc", "Finish / QC"),
    ("delivery", "Delivery"),
    ("install", "Install"),
]
```

Add fields to `SouthbrookMiCheck`:

```python
    stage = fields.Selection(MI_STAGES, string="Stage", index=True)
    workcenter_id = fields.Many2one(
        "mrp.workcenter", string="Work Center", ondelete="set null", index=True
    )
    sequence = fields.Integer(default=100, index=True)
    is_gate = fields.Boolean(default=True, index=True)
```

Change `_order` to:

```python
    _order = "sequence, stage, category, id"
```

- [ ] **Step 4: Add `_stage_values` to `mi_engine.py`**

Inside `SouthbrookMiEngine`:

```python
    @api.model
    def _stage_values(self, stage, sequence, is_gate=True, workcenter=False):
        values = {
            "stage": stage,
            "sequence": sequence,
            "is_gate": is_gate,
        }
        if workcenter:
            values["workcenter_id"] = workcenter.id
        return values
```

- [ ] **Step 5: Verify GREEN**

Run the same live shell, this time expecting the helper values:

```bash
ssh admin@192.168.68.108 '/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker -H unix:///var/run/system-docker.sock exec -i southbrook-odoo sh -c "odoo shell --config=/etc/odoo/odoo.conf -d southbrook --no-http --workers 0"' <<'PY'
Engine = env["southbrook.mi.engine"]
wc = env["mrp.workcenter"].create({"name": "Panel Saw Test"})
values = Engine._stage_values("saw", 10, is_gate=True, workcenter=wc)
print("STAGE_VALUES", values)
assert values["stage"] == "saw"
assert values["sequence"] == 10
assert values["is_gate"] is True
assert values["workcenter_id"] == wc.id
env.cr.rollback()
PY
```

Expected: output includes `STAGE_VALUES` and command exits `0`.

- [ ] **Step 6: Commit**

```bash
git add addons/southbrook_manufacturing_intelligence/models/mi_check.py \
        addons/southbrook_manufacturing_intelligence/models/mi_engine.py \
        addons/southbrook_manufacturing_intelligence/tests/test_mi_engine.py
git commit -m "feat(mi): add stage metadata to checks"
```

---

## Task 2: Add Package Stage Rollup Fields

**Files:**
- Modify: `addons/southbrook_manufacturing_intelligence/models/sb_production_package.py`
- Modify: `addons/southbrook_manufacturing_intelligence/models/mi_engine.py`
- Test: `addons/southbrook_manufacturing_intelligence/tests/test_mi_engine.py`

- [ ] **Step 1: Write the failing test**

Add to `TestManufacturingIntelligenceEngine`:

```python
def test_stage_rollup_uses_first_blocked_stage_by_sequence(self):
    Engine = self.env["southbrook.mi.engine"]
    Check = self.env["southbrook.mi.check"]
    install = Check.create({
        "name": "Install blocker",
        "severity": "blocker",
        "category": "install",
        "stage": "install",
        "sequence": 70,
        "message": "Install blocked",
        "recommendation": "Fix install",
    })
    saw = Check.create({
        "name": "Saw blocker",
        "severity": "blocker",
        "category": "cut",
        "stage": "saw",
        "sequence": 10,
        "message": "Saw blocked",
        "recommendation": "Fix saw",
    })
    warning = Check.create({
        "name": "Assembly warning",
        "severity": "warning",
        "category": "assembly",
        "stage": "assembly",
        "sequence": 40,
        "message": "Assembly review",
        "recommendation": "Review assembly",
    })
    rollup = Engine._stage_rollup_from_checks(install | saw | warning)
    self.assertEqual(rollup["x_mi_blocked_stage"], "saw")
    self.assertEqual(rollup["x_mi_next_stage_action"], "Fix saw")
    self.assertEqual(rollup["x_mi_saw_blocker_count"], 1)
    self.assertEqual(rollup["x_mi_install_blocker_count"], 1)
    self.assertEqual(rollup["x_mi_assembly_blocker_count"], 0)
```

- [ ] **Step 2: Run RED**

```bash
ssh admin@192.168.68.108 '/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker -H unix:///var/run/system-docker.sock exec -i southbrook-odoo sh -c "odoo shell --config=/etc/odoo/odoo.conf -d southbrook --no-http --workers 0"' <<'PY'
Engine = env["southbrook.mi.engine"]
assert not hasattr(Engine, "_stage_rollup_from_checks"), "Expected _stage_rollup_from_checks to be missing before implementation"
PY
```

Expected: exits `0`.

- [ ] **Step 3: Add rollup fields to `sb_production_package.py`**

Add fields:

```python
    x_mi_blocked_stage = fields.Selection(
        [
            ("saw", "Saw"),
            ("cnc", "CNC"),
            ("edgeband", "Edgeband"),
            ("assembly", "Assembly"),
            ("finish_qc", "Finish / QC"),
            ("delivery", "Delivery"),
            ("install", "Install"),
        ],
        string="MI Blocked Stage",
        copy=False,
    )
    x_mi_next_stage_action = fields.Text(string="MI Next Stage Action", copy=False)
    x_mi_saw_blocker_count = fields.Integer(string="Saw Blockers", copy=False)
    x_mi_cnc_blocker_count = fields.Integer(string="CNC Blockers", copy=False)
    x_mi_edgeband_blocker_count = fields.Integer(string="Edgeband Blockers", copy=False)
    x_mi_assembly_blocker_count = fields.Integer(string="Assembly Blockers", copy=False)
    x_mi_finish_qc_blocker_count = fields.Integer(string="Finish/QC Blockers", copy=False)
    x_mi_delivery_blocker_count = fields.Integer(string="Delivery Blockers", copy=False)
    x_mi_install_blocker_count = fields.Integer(string="Install Blockers", copy=False)
```

- [ ] **Step 4: Add `_stage_rollup_from_checks` to `mi_engine.py`**

```python
    @api.model
    def _stage_rollup_from_checks(self, checks):
        stages = [
            "saw",
            "cnc",
            "edgeband",
            "assembly",
            "finish_qc",
            "delivery",
            "install",
        ]
        rollup = {
            "x_mi_blocked_stage": False,
            "x_mi_next_stage_action": False,
        }
        for stage in stages:
            rollup["x_mi_%s_blocker_count" % stage] = len(
                checks.filtered(
                    lambda c, stage=stage: c.stage == stage and c.severity == "blocker"
                )
            )
        blocker = checks.filtered(lambda c: c.severity == "blocker").sorted(
            key=lambda c: (c.sequence or 100, c.id)
        )[:1]
        if blocker:
            rollup["x_mi_blocked_stage"] = blocker.stage
            rollup["x_mi_next_stage_action"] = (
                blocker.recommendation or blocker.message
            )
            return rollup
        warning = checks.filtered(lambda c: c.severity == "warning").sorted(
            key=lambda c: (c.sequence or 100, c.id)
        )[:1]
        if warning:
            rollup["x_mi_next_stage_action"] = (
                warning.recommendation or warning.message
            )
        return rollup
```

- [ ] **Step 5: Verify GREEN**

Run the focused shell equivalent:

```bash
ssh admin@192.168.68.108 '/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker -H unix:///var/run/system-docker.sock exec -i southbrook-odoo sh -c "odoo shell --config=/etc/odoo/odoo.conf -d southbrook --no-http --workers 0"' <<'PY'
Engine = env["southbrook.mi.engine"]
Check = env["southbrook.mi.check"].sudo()
saw = Check.create({"name":"Saw blocker","severity":"blocker","category":"cut","stage":"saw","sequence":10,"message":"Saw blocked","recommendation":"Fix saw"})
install = Check.create({"name":"Install blocker","severity":"blocker","category":"install","stage":"install","sequence":70,"message":"Install blocked","recommendation":"Fix install"})
rollup = Engine._stage_rollup_from_checks(saw | install)
print("ROLLUP", rollup)
assert rollup["x_mi_blocked_stage"] == "saw"
assert rollup["x_mi_next_stage_action"] == "Fix saw"
assert rollup["x_mi_saw_blocker_count"] == 1
assert rollup["x_mi_install_blocker_count"] == 1
env.cr.rollback()
PY
```

Expected: output includes `ROLLUP` and command exits `0`.

- [ ] **Step 6: Commit**

```bash
git add addons/southbrook_manufacturing_intelligence/models/sb_production_package.py \
        addons/southbrook_manufacturing_intelligence/models/mi_engine.py \
        addons/southbrook_manufacturing_intelligence/tests/test_mi_engine.py
git commit -m "feat(mi): roll up blockers by production stage"
```

---

## Task 3: Convert Existing Checks To Stage-Aware Checks

**Files:**
- Modify: `addons/southbrook_manufacturing_intelligence/models/mi_engine.py`
- Test: `addons/southbrook_manufacturing_intelligence/tests/test_mi_engine.py`

- [ ] **Step 1: Write failing test**

Add to `TestManufacturingIntelligenceEngine`:

```python
def test_existing_checks_are_stage_aware(self):
    Engine = self.env["southbrook.mi.engine"]
    cut = Engine._cut_checks_from_panels(
        [
            {
                "panel_name": "Tall pantry side",
                "qty": 1,
                "length_mm": 3000,
                "width_mm": 1300,
                "thickness_mm": 19,
                "substrate": "plywood",
                "grain_dir": "length",
            }
        ],
        {"waste_area_m2": 0.2},
    )
    hardware = Engine._hardware_checks_from_summary(None)
    install = Engine._install_checks_from_dimensions(900, 2400, 650)
    self.assertEqual(cut[0]["stage"], "saw")
    self.assertEqual(cut[0]["sequence"], 10)
    self.assertTrue(cut[0]["is_gate"])
    self.assertEqual(hardware[0]["stage"], "assembly")
    self.assertEqual(hardware[0]["sequence"], 40)
    self.assertEqual(
        [check["stage"] for check in install],
        ["install", "install", "install"],
    )
```

- [ ] **Step 2: Run RED**

Run the test method or live shell and expect `KeyError: 'stage'` for current checks.

```bash
ssh admin@192.168.68.108 '/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker -H unix:///var/run/system-docker.sock exec -i southbrook-odoo sh -c "odoo shell --config=/etc/odoo/odoo.conf -d southbrook --no-http --workers 0"' <<'PY'
Engine = env["southbrook.mi.engine"]
checks = Engine._hardware_checks_from_summary(None)
assert "stage" not in checks[0], "Expected old hardware checks to lack stage before implementation"
PY
```

- [ ] **Step 3: Add stage metadata to existing helper return values**

In `mi_engine.py`, update every check dict returned by these helpers:

- `_cut_checks_from_panels`: add `**self._stage_values("saw", 10)`.
- `_cut_batching_checks_from_summary`: add `**self._stage_values("saw", 10, is_gate=False)`.
- `_assembly_checks_from_panels`: add `**self._stage_values("assembly", 40)`.
- `_material_handling_checks_from_panels`: add `**self._stage_values("assembly", 40)`.
- `_hardware_checks_from_summary`: add `**self._stage_values("assembly", 40)`.
- `_install_checks_from_dimensions`: add `**self._stage_values("install", 70)` to warnings and `**self._stage_values("install", 70, is_gate=False)` to filler/scribe info.
- Missing cutlist checks in `_recompute_production` and `_recompute_package`: add `**self._stage_values("saw", 10)`.
- CAD warning in `_recompute_production`: add `**self._stage_values("cnc", 20)`.
- Low yield warning in `_recompute_package`: add `**self._stage_values("saw", 10)`.

Example pattern:

```python
checks.append(
    {
        **self._stage_values("saw", 10),
        "name": "Oversized panel",
        "severity": "blocker",
        "category": "cut",
        "message": "...",
        "recommendation": "...",
    }
)
```

- [ ] **Step 4: Verify GREEN**

```bash
ssh admin@192.168.68.108 '/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker -H unix:///var/run/system-docker.sock exec -i southbrook-odoo sh -c "odoo shell --config=/etc/odoo/odoo.conf -d southbrook --no-http --workers 0"' <<'PY'
Engine = env["southbrook.mi.engine"]
cut = Engine._cut_checks_from_panels([{"panel_name":"Tall pantry side","qty":1,"length_mm":3000,"width_mm":1300,"thickness_mm":19,"substrate":"plywood","grain_dir":"length"}], {"waste_area_m2":0.2})
hardware = Engine._hardware_checks_from_summary(None)
install = Engine._install_checks_from_dimensions(900, 2400, 650)
print("STAGED", cut[0], hardware[0], install)
assert cut[0]["stage"] == "saw"
assert hardware[0]["stage"] == "assembly"
assert all(check["stage"] == "install" for check in install)
env.cr.rollback()
PY
```

- [ ] **Step 5: Commit**

```bash
git add addons/southbrook_manufacturing_intelligence/models/mi_engine.py \
        addons/southbrook_manufacturing_intelligence/tests/test_mi_engine.py
git commit -m "feat(mi): make checks stage aware"
```

---

## Task 4: Add Edgeband Stage Checks

**Files:**
- Modify: `addons/southbrook_manufacturing_intelligence/models/mi_engine.py`
- Test: `addons/southbrook_manufacturing_intelligence/tests/test_mi_engine.py`

- [ ] **Step 1: Write failing tests**

Add to `TestManufacturingIntelligenceEngine`:

```python
def test_edgeband_checks_warn_on_malformed_edge_config(self):
    Engine = self.env["southbrook.mi.engine"]
    checks = Engine._edgeband_checks_from_panels(
        [
            {
                "panel_name": "Door",
                "qty": 1,
                "length_mm": 700,
                "width_mm": 400,
                "thickness_mm": 19,
                "edge_banding_config": "{bad json",
            }
        ],
        {"edge_band_m": 2.2},
    )
    malformed = [
        check for check in checks if check["name"] == "Edge banding config review"
    ]
    self.assertEqual(len(malformed), 1)
    self.assertEqual(malformed[0]["stage"], "edgeband")
    self.assertEqual(malformed[0]["severity"], "warning")

def test_edgeband_checks_info_for_high_edge_band_length(self):
    Engine = self.env["southbrook.mi.engine"]
    checks = Engine._edgeband_checks_from_panels([], {"edge_band_m": 45.0})
    staging = [
        check for check in checks if check["name"] == "Edge band material staging"
    ]
    self.assertEqual(len(staging), 1)
    self.assertEqual(staging[0]["stage"], "edgeband")
    self.assertEqual(staging[0]["severity"], "info")
```

- [ ] **Step 2: Run RED**

```bash
ssh admin@192.168.68.108 '/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker -H unix:///var/run/system-docker.sock exec -i southbrook-odoo sh -c "odoo shell --config=/etc/odoo/odoo.conf -d southbrook --no-http --workers 0"' <<'PY'
Engine = env["southbrook.mi.engine"]
assert not hasattr(Engine, "_edgeband_checks_from_panels"), "Expected _edgeband_checks_from_panels to be missing before implementation"
PY
```

- [ ] **Step 3: Add `_edge_config_needs_review` helper**

```python
    @api.model
    def _edge_config_needs_review(self, config):
        if not config:
            return False
        if isinstance(config, str):
            try:
                json.loads(config)
            except json.JSONDecodeError:
                return True
        return False
```

- [ ] **Step 4: Add `_edgeband_checks_from_panels`**

```python
    @api.model
    def _edgeband_checks_from_panels(self, panels, summary):
        checks = []
        for panel in panels:
            if self._edge_config_needs_review(panel.get("edge_banding_config")):
                checks.append(
                    {
                        **self._stage_values("edgeband", 30),
                        "name": "Edge banding config review",
                        "severity": "warning",
                        "category": "cut",
                        "message": "%s has malformed edge-banding data."
                        % (panel.get("panel_name") or "Panel"),
                        "recommendation": "Confirm required edges before running the edgebander.",
                    }
                )
        edge_band_m = (summary or {}).get("edge_band_m") or 0.0
        if edge_band_m >= 40.0:
            checks.append(
                {
                    **self._stage_values("edgeband", 30, is_gate=False),
                    "name": "Edge band material staging",
                    "severity": "info",
                    "category": "cut",
                    "message": "Package requires %.1f m of edge banding." % edge_band_m,
                    "recommendation": "Stage matching banding coil, adhesive, and cleanup before edgebanding.",
                }
            )
        return checks
```

- [ ] **Step 5: Wire edgeband checks into `_recompute_package`**

After `_cut_batching_checks_from_summary(summary)`:

```python
            for check in self._edgeband_checks_from_panels(panels, summary):
                check["production_package_id"] = package.id
                self._create_check(check)
```

- [ ] **Step 6: Verify GREEN**

```bash
ssh admin@192.168.68.108 '/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker -H unix:///var/run/system-docker.sock exec -i southbrook-odoo sh -c "odoo shell --config=/etc/odoo/odoo.conf -d southbrook --no-http --workers 0"' <<'PY'
Engine = env["southbrook.mi.engine"]
checks = Engine._edgeband_checks_from_panels([{"panel_name":"Door","edge_banding_config":"{bad json"}], {"edge_band_m":45.0})
print("EDGEBAND", checks)
assert any(c["name"] == "Edge banding config review" and c["stage"] == "edgeband" for c in checks)
assert any(c["name"] == "Edge band material staging" and c["stage"] == "edgeband" for c in checks)
env.cr.rollback()
PY
```

- [ ] **Step 7: Commit**

```bash
git add addons/southbrook_manufacturing_intelligence/models/mi_engine.py \
        addons/southbrook_manufacturing_intelligence/tests/test_mi_engine.py
git commit -m "feat(mi): add edgeband stage checks"
```

---

## Task 5: Write Stage Rollups During Package Recompute

**Files:**
- Modify: `addons/southbrook_manufacturing_intelligence/models/mi_engine.py`
- Test: `addons/southbrook_manufacturing_intelligence/tests/test_mi_mrp.py`

- [ ] **Step 1: Write failing test**

Add to the package/MRP test class in `test_mi_mrp.py`:

```python
def test_package_recompute_writes_stage_rollups(self):
    product = self.env["product.product"].create({
        "name": "MI Rollup Product",
        "type": "consu",
    })
    mo = self.env["mrp.production"].create({
        "product_id": product.id,
        "product_uom_id": product.uom_id.id,
        "product_qty": 1,
    })
    cutlist = self.env["sb.cutlist"].create({"mo_id": mo.id})
    self.env["sb.cutlist.line"].create({
        "cutlist_id": cutlist.id,
        "panel_name": "side_L",
        "qty": 1,
        "length_mm": 3000,
        "width_mm": 1300,
        "thickness_mm": 19,
        "substrate": "melamine_white_5_8",
        "grain_dir": "with_grain",
    })
    package = self.env["sb.production.package"].create({
        "mo_id": mo.id,
        "cutlist_id": cutlist.id,
    })
    package.action_recompute_manufacturing_intelligence()
    self.assertEqual(package.x_mi_blocked_stage, "saw")
    self.assertIn("Split the part", package.x_mi_next_stage_action)
    self.assertEqual(package.x_mi_saw_blocker_count, 1)
```

- [ ] **Step 2: Run RED**

Expected before wiring: `x_mi_blocked_stage` remains false or field is missing if Task 2 has not run.

- [ ] **Step 3: Apply rollup values in `_recompute_package`**

Before `package.write(...)`, compute:

```python
        stage_rollup = self._stage_rollup_from_checks(checks)
```

Add to the `package.write` dict:

```python
                **stage_rollup,
```

The final write should still include existing values:

```python
                "x_mi_status": self._status_from_severities(severities),
                "x_mi_yield_pct": summary["yield_pct"],
                "x_mi_waste_area_m2": summary["waste_area_m2"],
                "x_mi_edge_band_m": summary["edge_band_m"],
                "x_mi_blocker_count": len(checks.filtered(lambda c: c.severity == "blocker")),
                "x_mi_warning_count": len(checks.filtered(lambda c: c.severity == "warning")),
                "x_mi_install_warning_count": len(
                    checks.filtered(
                        lambda c: c.category == "install" and c.severity == "warning"
                    )
                ),
                "x_mi_next_action": self._next_action_from_checks(checks),
                **stage_rollup,
```

- [ ] **Step 4: Verify GREEN with live shell**

```bash
ssh admin@192.168.68.108 '/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker -H unix:///var/run/system-docker.sock exec -i southbrook-odoo sh -c "odoo shell --config=/etc/odoo/odoo.conf -d southbrook --no-http --workers 0"' <<'PY'
Product = env["product.product"]
product = Product.create({"name":"MI Rollup Product","type":"consu"})
mo = env["mrp.production"].create({"product_id":product.id,"product_uom_id":product.uom_id.id,"product_qty":1})
cutlist = env["sb.cutlist"].create({"mo_id":mo.id})
env["sb.cutlist.line"].create({"cutlist_id":cutlist.id,"panel_name":"side_L","qty":1,"length_mm":3000,"width_mm":1300,"thickness_mm":19,"substrate":"melamine_white_5_8","grain_dir":"with_grain"})
package = env["sb.production.package"].create({"mo_id":mo.id,"cutlist_id":cutlist.id})
package.action_recompute_manufacturing_intelligence()
print("PACKAGE_ROLLUP", package.x_mi_blocked_stage, package.x_mi_next_stage_action, package.x_mi_saw_blocker_count)
assert package.x_mi_blocked_stage == "saw"
assert package.x_mi_saw_blocker_count == 1
env.cr.rollback()
PY
```

- [ ] **Step 5: Commit**

```bash
git add addons/southbrook_manufacturing_intelligence/models/mi_engine.py \
        addons/southbrook_manufacturing_intelligence/tests/test_mi_mrp.py
git commit -m "feat(mi): write stage rollups on packages"
```

---

## Task 6: Update Package Form View For Stage Gates

**Files:**
- Modify: `addons/southbrook_manufacturing_intelligence/views/production_package_views.xml`
- Test: `addons/southbrook_manufacturing_intelligence/tests/test_mi_views.py`

- [ ] **Step 1: Write failing test**

Add to `TestManufacturingIntelligenceViews`:

```python
def test_package_view_has_stage_gate_fields(self):
    view = self.env.ref(
        "southbrook_manufacturing_intelligence.view_sb_production_package_form_mi"
    )
    arch = view.arch_db
    self.assertIn("x_mi_blocked_stage", arch)
    self.assertIn("x_mi_next_stage_action", arch)
    self.assertIn("x_mi_saw_blocker_count", arch)
    self.assertIn("stage", arch)
    self.assertIn("is_gate", arch)
```

- [ ] **Step 2: Run RED**

Expected: assertions fail because these strings are not in the current view.

- [ ] **Step 3: Modify package form view**

In the Intelligence tab, add these fields near `x_mi_status`:

```xml
<field name="x_mi_blocked_stage"/>
<field name="x_mi_next_stage_action"/>
```

Add stage count fields in the metrics group:

```xml
<field name="x_mi_saw_blocker_count"/>
<field name="x_mi_cnc_blocker_count"/>
<field name="x_mi_edgeband_blocker_count"/>
<field name="x_mi_assembly_blocker_count"/>
<field name="x_mi_finish_qc_blocker_count"/>
<field name="x_mi_delivery_blocker_count"/>
<field name="x_mi_install_blocker_count"/>
```

In the `x_mi_check_ids` list, add before `severity`:

```xml
<field name="sequence"/>
<field name="stage"/>
<field name="is_gate"/>
```

- [ ] **Step 4: Verify GREEN**

Run live shell:

```bash
ssh admin@192.168.68.108 '/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker -H unix:///var/run/system-docker.sock exec -i southbrook-odoo sh -c "odoo shell --config=/etc/odoo/odoo.conf -d southbrook --no-http --workers 0"' <<'PY'
view = env.ref("southbrook_manufacturing_intelligence.view_sb_production_package_form_mi")
arch = view.arch_db
print("PACKAGE_VIEW_STAGE_FIELDS", all(s in arch for s in ["x_mi_blocked_stage", "x_mi_next_stage_action", "x_mi_saw_blocker_count", "stage", "is_gate"]))
assert "x_mi_blocked_stage" in arch
assert "x_mi_next_stage_action" in arch
assert "x_mi_saw_blocker_count" in arch
assert "stage" in arch
assert "is_gate" in arch
env.cr.rollback()
PY
```

- [ ] **Step 5: Commit**

```bash
git add addons/southbrook_manufacturing_intelligence/views/production_package_views.xml \
        addons/southbrook_manufacturing_intelligence/tests/test_mi_views.py
git commit -m "feat(mi): show stage gates on package form"
```

---

## Task 7: Add Manager Dashboard Views

**Files:**
- Create: `addons/southbrook_manufacturing_intelligence/views/manager_dashboard_views.xml`
- Modify: `addons/southbrook_manufacturing_intelligence/__manifest__.py`
- Test: `addons/southbrook_manufacturing_intelligence/tests/test_mi_views.py`

- [ ] **Step 1: Write failing tests**

Add to `TestManufacturingIntelligenceViews`:

```python
def test_manager_dashboard_views_load(self):
    for xmlid in [
        "southbrook_manufacturing_intelligence.view_southbrook_mi_check_list",
        "southbrook_manufacturing_intelligence.view_southbrook_mi_check_search",
        "southbrook_manufacturing_intelligence.view_southbrook_mi_package_list",
        "southbrook_manufacturing_intelligence.action_southbrook_mi_checks",
        "southbrook_manufacturing_intelligence.action_southbrook_mi_packages",
    ]:
        self.assertTrue(self.env.ref(xmlid, raise_if_not_found=False), xmlid)
```

- [ ] **Step 2: Run RED**

Expected: XML IDs are not found.

- [ ] **Step 3: Create `manager_dashboard_views.xml`**

Use this content:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_southbrook_mi_check_list" model="ir.ui.view">
        <field name="name">southbrook.mi.check.list</field>
        <field name="model">southbrook.mi.check</field>
        <field name="arch" type="xml">
            <list string="Manufacturing Intelligence Checks"
                  decoration-danger="severity == 'blocker'"
                  decoration-warning="severity == 'warning'"
                  decoration-info="severity == 'info'">
                <field name="sequence"/>
                <field name="stage"/>
                <field name="severity"/>
                <field name="is_gate"/>
                <field name="category"/>
                <field name="name"/>
                <field name="production_package_id"/>
                <field name="production_id"/>
                <field name="workcenter_id"/>
                <field name="message"/>
                <field name="recommendation"/>
            </list>
        </field>
    </record>

    <record id="view_southbrook_mi_check_search" model="ir.ui.view">
        <field name="name">southbrook.mi.check.search</field>
        <field name="model">southbrook.mi.check</field>
        <field name="arch" type="xml">
            <search string="Manufacturing Intelligence">
                <field name="name"/>
                <field name="stage"/>
                <field name="severity"/>
                <filter name="blockers" string="Blockers" domain="[('severity','=','blocker')]"/>
                <filter name="warnings" string="Warnings" domain="[('severity','=','warning')]"/>
                <filter name="gate_checks" string="Gate Checks" domain="[('is_gate','=',True)]"/>
                <separator/>
                <filter name="stage_saw" string="Saw" domain="[('stage','=','saw')]"/>
                <filter name="stage_cnc" string="CNC" domain="[('stage','=','cnc')]"/>
                <filter name="stage_edgeband" string="Edgeband" domain="[('stage','=','edgeband')]"/>
                <filter name="stage_assembly" string="Assembly" domain="[('stage','=','assembly')]"/>
                <filter name="stage_finish_qc" string="Finish / QC" domain="[('stage','=','finish_qc')]"/>
                <filter name="stage_delivery" string="Delivery" domain="[('stage','=','delivery')]"/>
                <filter name="stage_install" string="Install" domain="[('stage','=','install')]"/>
                <group expand="0" string="Group By">
                    <filter name="group_stage" string="Stage" context="{'group_by':'stage'}"/>
                    <filter name="group_severity" string="Severity" context="{'group_by':'severity'}"/>
                    <filter name="group_package" string="Package" context="{'group_by':'production_package_id'}"/>
                    <filter name="group_workcenter" string="Work Center" context="{'group_by':'workcenter_id'}"/>
                </group>
            </search>
        </field>
    </record>

    <record id="view_southbrook_mi_package_list" model="ir.ui.view">
        <field name="name">sb.production.package.list.manufacturing.intelligence</field>
        <field name="model">sb.production.package</field>
        <field name="arch" type="xml">
            <list string="Production Packages - Manufacturing Intelligence"
                  decoration-danger="x_mi_status == 'blocked'"
                  decoration-warning="x_mi_status == 'review'"
                  decoration-success="x_mi_status == 'ok'">
                <field name="name"/>
                <field name="mo_id"/>
                <field name="state"/>
                <field name="x_mi_status"/>
                <field name="x_mi_blocked_stage"/>
                <field name="x_mi_blocker_count"/>
                <field name="x_mi_warning_count"/>
                <field name="x_mi_next_stage_action"/>
            </list>
        </field>
    </record>

    <record id="action_southbrook_mi_checks" model="ir.actions.act_window">
        <field name="name">Manufacturing Intelligence Checks</field>
        <field name="res_model">southbrook.mi.check</field>
        <field name="view_mode">list,search</field>
        <field name="search_view_id" ref="view_southbrook_mi_check_search"/>
        <field name="context">{'search_default_blockers': 1, 'search_default_group_stage': 1}</field>
    </record>

    <record id="action_southbrook_mi_packages" model="ir.actions.act_window">
        <field name="name">Production Intelligence Board</field>
        <field name="res_model">sb.production.package</field>
        <field name="view_mode">list,form</field>
        <field name="view_id" ref="view_southbrook_mi_package_list"/>
    </record>
</odoo>
```

- [ ] **Step 4: Add XML file to manifest**

Add to `data` after `views/production_package_views.xml`:

```python
        "views/manager_dashboard_views.xml",
```

Update version:

```python
    "version": "19.0.1.1.0",
```

- [ ] **Step 5: Verify GREEN**

Run:

```bash
ssh admin@192.168.68.108 '/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker -H unix:///var/run/system-docker.sock exec -i southbrook-odoo sh -c "odoo shell --config=/etc/odoo/odoo.conf -d southbrook --no-http --workers 0"' <<'PY'
for xmlid in [
    "southbrook_manufacturing_intelligence.view_southbrook_mi_check_list",
    "southbrook_manufacturing_intelligence.view_southbrook_mi_check_search",
    "southbrook_manufacturing_intelligence.view_southbrook_mi_package_list",
    "southbrook_manufacturing_intelligence.action_southbrook_mi_checks",
    "southbrook_manufacturing_intelligence.action_southbrook_mi_packages",
]:
    rec = env.ref(xmlid, raise_if_not_found=False)
    print("XMLID", xmlid, bool(rec))
    assert rec
env.cr.rollback()
PY
```

- [ ] **Step 6: Commit**

```bash
git add addons/southbrook_manufacturing_intelligence/__manifest__.py \
        addons/southbrook_manufacturing_intelligence/views/manager_dashboard_views.xml \
        addons/southbrook_manufacturing_intelligence/tests/test_mi_views.py
git commit -m "feat(mi): add plant manager dashboard views"
```

---

## Task 8: Deploy And Verify Live

**Files:**
- Deploy all changed files under `addons/southbrook_manufacturing_intelligence/`

- [ ] **Step 1: Sync addon to QNAP**

```bash
scp -r /Users/naadmin/southbrook-v19cr/addons/southbrook_manufacturing_intelligence/. \
  admin@192.168.68.108:/share/CACHEDEV3_DATA/Container/southbrook/addons/southbrook_manufacturing_intelligence/
```

- [ ] **Step 2: Update module**

```bash
ssh admin@192.168.68.108 '/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker -H unix:///var/run/system-docker.sock exec southbrook-odoo sh -c "odoo --config=/etc/odoo/odoo.conf -d southbrook --no-http --workers 0 --stop-after-init -u southbrook_manufacturing_intelligence"'
```

Expected: exit `0`.

- [ ] **Step 3: Verify module/version/schema**

```bash
ssh admin@192.168.68.108 '/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker -H unix:///var/run/system-docker.sock exec -i southbrook-odoo sh -c "odoo shell --config=/etc/odoo/odoo.conf -d southbrook --no-http --workers 0"' <<'PY'
module = env["ir.module.module"].search([("name", "=", "southbrook_manufacturing_intelligence")], limit=1)
print("MODULE", module.name, module.state, module.installed_version)
assert module.state == "installed"
assert module.installed_version == "19.0.1.1.0"
for field in ["stage", "workcenter_id", "sequence", "is_gate"]:
    assert field in env["southbrook.mi.check"]._fields, field
for field in ["x_mi_blocked_stage", "x_mi_next_stage_action", "x_mi_saw_blocker_count"]:
    assert field in env["sb.production.package"]._fields, field
env.cr.rollback()
PY
```

- [ ] **Step 4: Verify representative calculations**

```bash
ssh admin@192.168.68.108 '/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker -H unix:///var/run/system-docker.sock exec -i southbrook-odoo sh -c "odoo shell --config=/etc/odoo/odoo.conf -d southbrook --no-http --workers 0"' <<'PY'
Engine = env["southbrook.mi.engine"]
checks = []
checks += Engine._cut_checks_from_panels([{"panel_name":"Tall pantry side","qty":1,"length_mm":3000,"width_mm":1300,"thickness_mm":19,"substrate":"plywood","grain_dir":"length"}], {"waste_area_m2":0.2})
checks += Engine._edgeband_checks_from_panels([{"panel_name":"Door","edge_banding_config":"{bad json"}], {"edge_band_m":45.0})
checks += Engine._hardware_checks_from_summary(None)
checks += Engine._install_checks_from_dimensions(900, 2400, 650)
print("REP_CHECKS", [(c["name"], c["severity"], c["stage"], c["sequence"]) for c in checks])
assert any(c["name"] == "Oversized panel" and c["stage"] == "saw" for c in checks)
assert any(c["name"] == "Edge banding config review" and c["stage"] == "edgeband" for c in checks)
assert any(c["name"] == "Missing hardware package" and c["stage"] == "assembly" for c in checks)
assert any(c["name"] == "Tip-up clearance review" and c["stage"] == "install" for c in checks)
env.cr.rollback()
PY
```

- [ ] **Step 5: Verify views/actions**

```bash
ssh admin@192.168.68.108 '/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker -H unix:///var/run/system-docker.sock exec -i southbrook-odoo sh -c "odoo shell --config=/etc/odoo/odoo.conf -d southbrook --no-http --workers 0"' <<'PY'
for xmlid in [
    "southbrook_manufacturing_intelligence.view_sb_production_package_form_mi",
    "southbrook_manufacturing_intelligence.view_southbrook_mi_check_list",
    "southbrook_manufacturing_intelligence.view_southbrook_mi_check_search",
    "southbrook_manufacturing_intelligence.view_southbrook_mi_package_list",
    "southbrook_manufacturing_intelligence.action_southbrook_mi_checks",
    "southbrook_manufacturing_intelligence.action_southbrook_mi_packages",
]:
    rec = env.ref(xmlid, raise_if_not_found=False)
    print("VIEW_OR_ACTION", xmlid, bool(rec))
    assert rec
env.cr.rollback()
PY
```

- [ ] **Step 6: Verify health**

```bash
curl -I https://southbrookcabinetry.space/web/health
ssh admin@192.168.68.108 '/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker -H unix:///var/run/system-docker.sock ps --format "table {{.Names}}\t{{.Status}}" | grep "southbrook"'
```

Expected:

- HTTP status `200`.
- `southbrook-odoo`, `southbrook-postgres`, and `southbrook-freecad-bridge` show healthy.

- [ ] **Step 7: Commit deployment verification notes if any tracked docs changed**

Only commit if a tracked verification note file was intentionally updated. Do not commit unrelated files.

---

## Task 9: Push Branch

**Files:**
- No source edits.

- [ ] **Step 1: Check status**

```bash
git -C /Users/naadmin/southbrook-v19cr status --short --branch
```

Expected: only unrelated untracked `marathon-import/*.json` files may remain.

- [ ] **Step 2: Push branch**

```bash
git -C /Users/naadmin/southbrook-v19cr push origin feature/southbrook-manufacturing-intelligence
```

Expected: push exits `0`.

- [ ] **Step 3: Report pushed commits**

```bash
git -C /Users/naadmin/southbrook-v19cr log --oneline origin/main..feature/southbrook-manufacturing-intelligence
```

Report the commit hashes and summary to the user.

---

## Self-Review

- Spec coverage: data model, stage gates, rollups, manager views, testing, deployment, and out-of-scope constraints are covered by Tasks 1-9.
- Placeholder scan: no `TBD`, `TODO`, or undefined task placeholders remain.
- Type consistency: field names match the approved spec and use existing Odoo naming style.
- Scope: this remains one addon upgrade and does not introduce custom JavaScript, machine telemetry, barcode workflows, or nesting optimization.
