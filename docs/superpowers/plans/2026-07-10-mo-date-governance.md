# MO-Date Governance (Step 0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Southbrook's MO deadlines *real* — replace the `create_date + Σ routing_time` fiction with a governed `today + material_lead_time + manufacturing_time`, locked at production release — so every downstream scheduler/delivery estimate has a truthful due date to reason about.

**Architecture:** A new, focused addon `southbrook_mo_date_governance` that (a) adds a reviewable `material_lead_time_days` to `mrp.production`, (b) computes `manufacturing_days` from the routing, (c) sets and **locks** `date_deadline = today + material_lead + manufacturing` at MO birth / release, and (d) provides the `S6`-style **artifact-vs-human** deadline categorizer that gives John his backfill worklist. It extends — never rewrites — `southbrook_mrp_pm` (which owns the SO→MO wiring).

**Tech Stack:** Odoo 19.0 CE, Python 3, XML views, `TransactionCase` tests. No JS.

## Global Constraints

- **License/manifest:** header `# SPDX-License-Identifier: LGPL-3.0-only`; `"license": "LGPL-3"`, `"author": "Southbrook Cabinetry"`, `"version": "19.0.1.0.0"`.
- **Depends:** `["southbrook_mrp_pm", "sale"]` (mrp/mrp_pm bring `mrp.production` + the `action_send_to_production` hook; `sale` for the SO-confirm path). Reuses `southbrook_mrp_pm`'s existing `action_send_to_production` and MO plumbing — do NOT duplicate SO→MO creation.
- **This is the §12.5 fix from the OdooIQ spec** and step 1 of the 2026-07-10 scheduler decision. The **audit signal that *detects* the fiction (`S6_DATE_AUTHENTICITY`) lives in the OdooIQ module**; this addon *resolves* it Southbrook-side.
- **Human-in-the-loop by design (spec §12.5):** `material_lead_time_days` is *suggested* from BOM component lead times but **John reviews/edits and the deadline locks at release** — never silently auto-recomputed. The lock is the whole point (auto-recompute was the fiction).
- **v19 API:** `mrp.production.date_deadline` is a **Datetime**; `<list>` not `<tree>`; `models.Constraint` not `_sql_constraints`; `@api.depends` field names must be exact (wrong name silently breaks the registry); new module needs `update_list()` before `-i`; `--logfile=/dev/stderr`.
- **Test env:** needs `southbrook_mrp_pm` + deps installed — run on an isolated db seeded like southbrook (odooiq staging or a southbrook clone), never live southbrook. Static-validate locally (`compileall` + XML parse); runtime `TransactionCase` on the stack.
- **Non-destructive to history:** governance applies to MOs at release and via an explicit backfill action John triggers — it does NOT mass-rewrite existing deadlines automatically.

---

## John's data/judgment tasks (NOT code — the handoff, per spec §12.5)

The code below is the scaffolding. These remain **John's** and gate the Month-2 sign-off:
1. Audit the current 30-day order book; categorize each deadline **artifact vs human** (Task 5 gives the worklist).
2. Set/verify `material_lead_time_days` per open MO (Task 2 suggests from BOM; John confirms real vendor lead times).
3. Decide the release-lock policy (lock at `action_send_to_production`, Task 6).
4. Re-run the OdooIQ audit; expect `S6_DATE_AUTHENTICITY` ~30% → ~85%+.

---

## File Structure

```
addons/southbrook_mo_date_governance/
  __init__.py
  __manifest__.py
  models/
    __init__.py
    mrp_production.py       # material_lead_time_days, manufacturing_days, governed deadline + lock, S6 categorizer
    sale_order.py           # lock governed deadline at action_send_to_production
  data/
    config_params.xml       # minutes_per_working_day default
  security/
    ir.model.access.csv     # (no new models; file present for convention — may stay header-only)
  views/
    mrp_production_views.xml # governance fields + the artifact worklist action
  tests/
    __init__.py
    test_mo_date_governance.py
  README.md
```

---

## Task 1: Scaffold addon

**Files:**
- Create: `addons/southbrook_mo_date_governance/__init__.py`, `__manifest__.py`, `models/__init__.py`, `security/ir.model.access.csv`, `data/config_params.xml`

**Interfaces:** Produces installable `southbrook_mo_date_governance` depending on `southbrook_mrp_pm` + `sale`.

- [ ] **Step 1: `__init__.py`**
```python
# SPDX-License-Identifier: LGPL-3.0-only
from . import models
```

- [ ] **Step 2: `models/__init__.py`**
```python
# SPDX-License-Identifier: LGPL-3.0-only
from . import mrp_production
from . import sale_order
```

- [ ] **Step 3: `__manifest__.py`**
```python
# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook MO Date Governance",
    "summary": "Real, locked MO deadlines: today + material lead time + "
               "manufacturing time. Resolves the date-fiction blocker (S6).",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry",
    "website": "https://southbrookcabinetry.space",
    "category": "Manufacturing",
    "depends": ["southbrook_mrp_pm", "sale"],
    "data": [
        "security/ir.model.access.csv",
        "data/config_params.xml",
        "views/mrp_production_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
```

- [ ] **Step 4: config param default + ACL header**

`data/config_params.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
    <record id="param_minutes_per_working_day" model="ir.config_parameter">
        <field name="key">southbrook_mo_date_governance.minutes_per_working_day</field>
        <field name="value">480</field>
    </record>
</odoo>
```
`security/ir.model.access.csv` (header only — no new models):
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
```

- [ ] **Step 5: Temporarily trim manifest `data` (views come in Task 7), install on isolated db**
```python
    "data": [
        "security/ir.model.access.csv",
        "data/config_params.xml",
        # "views/mrp_production_views.xml",   # Task 7
    ],
```
Run (staging db that already has southbrook_mrp_pm):
```bash
docker exec odooiq-odoo odoo shell -d gov_test --no-http -c /etc/odoo/odoo.conf \
  --logfile=/dev/stderr <<'PY'
env['ir.module.module'].update_list(); env.cr.commit()
PY
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d gov_test \
  -i southbrook_mo_date_governance --stop-after-init --no-http --logfile=/dev/stderr
```
Expected: exits 0, no traceback.

- [ ] **Step 6: Commit**
```bash
cd ~/southbrook-v19cr
git add addons/southbrook_mo_date_governance
git commit -m "feat(mo-dates): scaffold MO date governance addon (Step 0 Task 1)"
```

---

## Task 2: `material_lead_time_days` + suggest-from-BOM

**Files:** Create `addons/southbrook_mo_date_governance/models/mrp_production.py`; create empty `sale_order.py`; Test: `tests/test_mo_date_governance.py`

**Interfaces:** Produces on `mrp.production`: `material_lead_time_days` (Float, editable), method `_suggest_material_lead_time()` → max of BOM components' supplier `delay`, and `action_suggest_material_lead_time()` (button).

- [ ] **Step 1: Write the failing test**

`tests/__init__.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from . import test_mo_date_governance
```
`tests/test_mo_date_governance.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "southbrook_mo_date_governance")
class TestMoDateGovernance(TransactionCase):

    def _product(self, name, lead=0):
        p = self.env["product.product"].create({"name": name, "is_storable": True})
        if lead:
            vendor = self.env["res.partner"].create({"name": name + " vendor"})
            self.env["product.supplierinfo"].create({
                "partner_id": vendor.id, "product_tmpl_id": p.product_tmpl_id.id,
                "delay": lead,
            })
        return p

    def test_suggest_material_lead_time_takes_max_component_delay(self):
        fin = self._product("Gov Cabinet")
        c1 = self._product("board", lead=5)
        c2 = self._product("hinge", lead=12)
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": fin.product_tmpl_id.id, "product_qty": 1.0,
            "bom_line_ids": [(0, 0, {"product_id": c1.id, "product_qty": 1.0}),
                             (0, 0, {"product_id": c2.id, "product_qty": 1.0})],
        })
        mo = self.env["mrp.production"].create(
            {"product_id": fin.id, "product_qty": 1.0, "bom_id": bom.id})
        self.assertEqual(mo._suggest_material_lead_time(), 12.0)
```

- [ ] **Step 2: Run to verify it fails** (`... --test-tags southbrook_mo_date_governance ...` → FAIL, method undefined).

- [ ] **Step 3: Implement**

`models/mrp_production.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from odoo import api, fields, models


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    material_lead_time_days = fields.Float(
        string="Material Lead Time (days)",
        help="Days from release until materials are available. Suggested "
             "from BOM component vendor lead times; reviewed by the planner.",
    )

    def _suggest_material_lead_time(self):
        """Max vendor delay across BOM components (0 if none)."""
        self.ensure_one()
        bom = self.bom_id
        if not bom:
            return 0.0
        delays = [0.0]
        for line in bom.bom_line_ids:
            seller = line.product_id.seller_ids[:1]
            if seller:
                delays.append(seller.delay or 0.0)
        return max(delays)

    def action_suggest_material_lead_time(self):
        for mo in self:
            mo.material_lead_time_days = mo._suggest_material_lead_time()
        return True
```
`models/sale_order.py` (placeholder, filled in Task 6):
```python
# SPDX-License-Identifier: LGPL-3.0-only
from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"
```

- [ ] **Step 4: Run to verify it passes.**
- [ ] **Step 5: Commit** — `feat(mo-dates): material_lead_time_days + suggest-from-BOM (Task 2)`

---

## Task 3: `manufacturing_days` from the routing

**Files:** Modify `models/mrp_production.py`; modify test file.

**Interfaces:** Produces `mrp.production.manufacturing_days` (Float, computed) = `ceil(Σ workorder.duration_expected / minutes_per_working_day)`, min 1 when any work exists.

- [ ] **Step 1: Write the failing test**
```python
    def test_manufacturing_days_from_routing(self):
        wc = self.env["mrp.workcenter"].search([("code", "=", "SB-CNC-BORE")], limit=1) \
            or self.env["mrp.workcenter"].create({"name": "Bore", "code": "SB-CNC-BORE"})
        fin = self._product("Gov Cab 2")
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": fin.product_tmpl_id.id, "product_qty": 1.0,
            "operation_ids": [(0, 0, {"name": "Bore", "workcenter_id": wc.id,
                                      "time_cycle_manual": 960.0})],  # 960 min = 2 days @480
        })
        mo = self.env["mrp.production"].create(
            {"product_id": fin.id, "product_qty": 1.0, "bom_id": bom.id})
        mo.action_confirm()  # spawns WOs with duration_expected
        self.assertGreaterEqual(mo.manufacturing_days, 2.0)
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement** — add to `MrpProduction`:
```python
    import math  # place at top of file with the other imports, not inside the class

    manufacturing_days = fields.Float(
        string="Manufacturing Time (days)", compute="_compute_manufacturing_days",
        help="Routing work time converted to working days.",
    )

    @api.depends("workorder_ids.duration_expected")
    def _compute_manufacturing_days(self):
        mins_per_day = float(self.env["ir.config_parameter"].sudo().get_param(
            "southbrook_mo_date_governance.minutes_per_working_day", 480.0))
        for mo in self:
            total = sum(mo.workorder_ids.mapped("duration_expected")) or 0.0
            mo.manufacturing_days = math.ceil(total / mins_per_day) if total else 0.0
```
> NOTE: put `import math` at module top. The `mins_per_day` guard: `get_param` returns a str; `float(...)` it. If 0, default 480 (guard: `mins_per_day or 480.0`).

- [ ] **Step 4: Run to verify it passes.**
- [ ] **Step 5: Commit** — `feat(mo-dates): manufacturing_days from routing (Task 3)`

---

## Task 4: Governed deadline + lock

**Files:** Modify `models/mrp_production.py`; modify test file.

**Interfaces:** Produces `deadline_locked` (Boolean), `deadline_source` (Selection: `auto`/`governed`/`manual`), method `_governed_deadline()` → Datetime = now + (material_lead_time_days + manufacturing_days) days, and `action_apply_governed_deadline()` that writes `date_deadline`, sets `deadline_locked=True`, `deadline_source='governed'`.

- [ ] **Step 1: Write the failing test**
```python
    def test_apply_governed_deadline_sets_and_locks(self):
        wc = self.env["mrp.workcenter"].search([("code", "=", "SB-CNC-BORE")], limit=1) \
            or self.env["mrp.workcenter"].create({"name": "Bore", "code": "SB-CNC-BORE"})
        fin = self._product("Gov Cab 3")
        board = self._product("board3", lead=4)
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": fin.product_tmpl_id.id, "product_qty": 1.0,
            "bom_line_ids": [(0, 0, {"product_id": board.id, "product_qty": 1.0})],
            "operation_ids": [(0, 0, {"name": "Bore", "workcenter_id": wc.id,
                                      "time_cycle_manual": 480.0})],  # 1 day
        })
        mo = self.env["mrp.production"].create(
            {"product_id": fin.id, "product_qty": 1.0, "bom_id": bom.id})
        mo.action_confirm()
        mo.material_lead_time_days = 4.0
        before = mo.date_deadline
        mo.action_apply_governed_deadline()
        self.assertTrue(mo.deadline_locked)
        self.assertEqual(mo.deadline_source, "governed")
        self.assertNotEqual(mo.date_deadline, before)
        # governed = now + 4 (lead) + 1 (mfg) = ~5 days out
        delta_days = (mo.date_deadline - fields.Datetime.now()).days
        self.assertGreaterEqual(delta_days, 4)
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement** — add to `MrpProduction` (and `from datetime import timedelta` at top):
```python
    deadline_locked = fields.Boolean(
        string="Deadline Locked", copy=False,
        help="When set, date_deadline is a governed commitment and must not "
             "be auto-recomputed.")
    deadline_source = fields.Selection(
        [("auto", "Auto (routing artifact)"), ("governed", "Governed"),
         ("manual", "Manual commitment")],
        string="Deadline Source", default="auto", copy=False)

    def _governed_deadline(self):
        self.ensure_one()
        days = (self.material_lead_time_days or 0.0) + (self.manufacturing_days or 0.0)
        return fields.Datetime.now() + timedelta(days=days)

    def action_apply_governed_deadline(self):
        for mo in self:
            mo.with_context(governing_deadline=True).write({
                "date_deadline": mo._governed_deadline(),
                "deadline_locked": True,
                "deadline_source": "governed",
            })
        return True
```

- [ ] **Step 4: Run to verify it passes.**
- [ ] **Step 5: Commit** — `feat(mo-dates): governed deadline + lock (Task 4)`

---

## Task 5: `S6` deadline-authenticity categorizer + worklist

**Files:** Modify `models/mrp_production.py`; modify test file.

**Interfaces:** Produces `deadline_authenticity` (Selection: `artifact`/`human`/`governed`/`unknown`, computed, stored) — `governed` if locked; else compares `(date_deadline − create_date)` to `Σ routing minutes`: ratio ≤ `ARTIFACT_RATIO` (default 1.3) → `artifact` (the fiction), higher → `human`. Powers John's backfill worklist (Task 7 action).

- [ ] **Step 1: Write the failing test**
```python
    def test_deadline_authenticity_flags_artifact(self):
        wc = self.env["mrp.workcenter"].search([("code", "=", "SB-CNC-BORE")], limit=1) \
            or self.env["mrp.workcenter"].create({"name": "Bore", "code": "SB-CNC-BORE"})
        fin = self._product("Gov Cab 4")
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": fin.product_tmpl_id.id, "product_qty": 1.0,
            "operation_ids": [(0, 0, {"name": "Bore", "workcenter_id": wc.id,
                                      "time_cycle_manual": 480.0})],
        })
        mo = self.env["mrp.production"].create(
            {"product_id": fin.id, "product_qty": 1.0, "bom_id": bom.id})
        mo.action_confirm()
        # deadline ≈ create_date + routing time → artifact
        mo.date_deadline = fields.Datetime.now()  # ~ create_date + tiny
        mo._compute_deadline_authenticity()
        self.assertIn(mo.deadline_authenticity, ("artifact", "unknown"))
        # governed always wins
        mo.material_lead_time_days = 10.0
        mo.action_apply_governed_deadline()
        self.assertEqual(mo.deadline_authenticity, "governed")
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement** — add to `MrpProduction`:
```python
    ARTIFACT_RATIO = 1.3  # (deadline-create)/routing <= this ⇒ likely a computed artifact

    deadline_authenticity = fields.Selection(
        [("artifact", "Artifact (fiction)"), ("human", "Human commitment"),
         ("governed", "Governed"), ("unknown", "Unknown")],
        string="Deadline Authenticity", compute="_compute_deadline_authenticity",
        store=True)

    @api.depends("date_deadline", "create_date", "deadline_locked",
                 "workorder_ids.duration_expected")
    def _compute_deadline_authenticity(self):
        for mo in self:
            if mo.deadline_locked:
                mo.deadline_authenticity = "governed"
                continue
            routing_min = sum(mo.workorder_ids.mapped("duration_expected")) or 0.0
            if not mo.date_deadline or not mo.create_date or routing_min <= 0:
                mo.deadline_authenticity = "unknown"
                continue
            span_min = (mo.date_deadline - mo.create_date).total_seconds() / 60.0
            ratio = span_min / routing_min
            mo.deadline_authenticity = "artifact" if ratio <= mo.ARTIFACT_RATIO else "human"
```

- [ ] **Step 4: Run to verify it passes.**
- [ ] **Step 5: Commit** — `feat(mo-dates): S6 deadline-authenticity categorizer (Task 5)`

---

## Task 6: Lock governance at production release (the SO→MO hook)

**Files:** Modify `models/sale_order.py`; modify `models/mrp_production.py` (respect-lock guard on write); modify test file.

**Interfaces:** Consumes `action_apply_governed_deadline`. Overrides `southbrook_mrp_pm`'s `sale.order.action_send_to_production()` so each MO it creates gets its material lead time suggested + a governed, locked deadline. Adds a write-guard so a locked MO's `date_deadline` is not silently auto-recomputed.

- [ ] **Step 1: Write the failing test**
```python
    def test_release_applies_and_locks_governed_deadline(self):
        # Minimal: a confirmed MO passed through the release helper gets locked.
        wc = self.env["mrp.workcenter"].search([("code", "=", "SB-CNC-BORE")], limit=1) \
            or self.env["mrp.workcenter"].create({"name": "Bore", "code": "SB-CNC-BORE"})
        fin = self._product("Gov Cab 5")
        board = self._product("board5", lead=3)
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": fin.product_tmpl_id.id, "product_qty": 1.0,
            "bom_line_ids": [(0, 0, {"product_id": board.id, "product_qty": 1.0})],
            "operation_ids": [(0, 0, {"name": "Bore", "workcenter_id": wc.id,
                                      "time_cycle_manual": 480.0})],
        })
        mo = self.env["mrp.production"].create(
            {"product_id": fin.id, "product_qty": 1.0, "bom_id": bom.id})
        mo.action_confirm()
        mo._govern_on_release()          # the helper the SO hook calls per MO
        self.assertTrue(mo.deadline_locked)
        self.assertEqual(mo.deadline_source, "governed")
        # a subsequent auto-recompute attempt is ignored while locked
        locked_deadline = mo.date_deadline
        mo.write({"date_deadline": fields.Datetime.now()})  # simulated auto-recompute
        # guard only blocks non-governing writes:
        self.assertEqual(mo.date_deadline, locked_deadline)
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement.** Add to `MrpProduction`:
```python
    def _govern_on_release(self):
        """Suggest lead time (if unset) and apply+lock the governed deadline."""
        for mo in self:
            if not mo.material_lead_time_days:
                mo.material_lead_time_days = mo._suggest_material_lead_time()
            mo.action_apply_governed_deadline()
        return True

    def write(self, vals):
        # Respect the lock: drop silent date_deadline auto-recomputes on locked MOs,
        # unless this write is the governing write itself.
        if "date_deadline" in vals and not self.env.context.get("governing_deadline"):
            locked = self.filtered("deadline_locked")
            if locked:
                unlocked = self - locked
                res = super(MrpProduction, unlocked).write(vals) if unlocked else True
                vals_no_deadline = {k: v for k, v in vals.items() if k != "date_deadline"}
                if vals_no_deadline:
                    super(MrpProduction, locked).write(vals_no_deadline)
                return res
        return super().write(vals)
```
Add to `models/sale_order.py`:
```python
# SPDX-License-Identifier: LGPL-3.0-only
from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_send_to_production(self):
        """Extend southbrook_mrp_pm: govern+lock the deadline on each MO created
        by the release action."""
        mos_before = self.env["mrp.production"].search([]).ids
        res = super().action_send_to_production()
        new_mos = self.env["mrp.production"].search([("id", "not in", mos_before)])
        new_mos._govern_on_release()
        return res
```
> NOTE: if `southbrook_mrp_pm.action_send_to_production` returns the created MOs, prefer capturing them from the return value; the before/after diff is the safe generic fallback. Verify the parent's signature at build time.

- [ ] **Step 4: Run to verify it passes.**
- [ ] **Step 5: Commit** — `feat(mo-dates): govern+lock deadline at production release (Task 6)`

---

## Task 7: Views (governance fields + artifact worklist) + backfill action + verify + README

**Files:** Create `views/mrp_production_views.xml`; modify `models/mrp_production.py` (backfill action); enable views in manifest; create `README.md`.

- [ ] **Step 1: Backfill action for John's worklist** — add to `MrpProduction`:
```python
    @api.model
    def action_open_artifact_worklist(self):
        """John's Step-0 worklist: open MOs whose deadline is a computed artifact."""
        return {
            "type": "ir.actions.act_window",
            "name": "Deadline Artifacts (fix these)",
            "res_model": "mrp.production",
            "view_mode": "list,form",
            "domain": [("state", "in", ["confirmed", "progress"]),
                       ("deadline_authenticity", "=", "artifact")],
        }
```

- [ ] **Step 2: Views** — `views/mrp_production_views.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_mo_form_date_governance" model="ir.ui.view">
        <field name="name">mrp.production.form.date.governance</field>
        <field name="model">mrp.production</field>
        <field name="inherit_id" ref="mrp.mrp_production_form_view"/>
        <field name="arch" type="xml">
            <field name="date_deadline" position="after">
                <field name="material_lead_time_days"/>
                <field name="manufacturing_days"/>
                <field name="deadline_authenticity"/>
                <field name="deadline_locked"/>
                <field name="deadline_source"/>
            </field>
        </field>
    </record>

    <record id="view_mo_form_governance_buttons" model="ir.ui.view">
        <field name="name">mrp.production.form.governance.buttons</field>
        <field name="model">mrp.production</field>
        <field name="inherit_id" ref="mrp.mrp_production_form_view"/>
        <field name="arch" type="xml">
            <xpath expr="//header" position="inside">
                <button name="action_suggest_material_lead_time" type="object"
                        string="Suggest Lead Time"/>
                <button name="action_apply_governed_deadline" type="object"
                        string="Govern Deadline" class="btn-primary"/>
            </xpath>
        </field>
    </record>

    <record id="action_deadline_artifacts" model="ir.actions.act_window">
        <field name="name">Deadline Artifacts (fix these)</field>
        <field name="res_model">mrp.production</field>
        <field name="view_mode">list,form</field>
        <field name="domain">[('state','in',['confirmed','progress']),('deadline_authenticity','=','artifact')]</field>
    </record>
    <menuitem id="menu_deadline_artifacts" name="Deadline Artifacts"
              parent="mrp.menu_mrp_manufacturing" action="action_deadline_artifacts"
              sequence="95"/>
</odoo>
```

- [ ] **Step 3: Enable views in manifest, upgrade, verify parse**
```bash
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d gov_test \
  -u southbrook_mo_date_governance --stop-after-init --no-http --logfile=/dev/stderr 2>&1 \
  | grep -Ei "governance|ParseError|ValidationError|Invalid|loaded"
```
Expected: no ParseError/ValidationError. (If `mrp.mrp_production_form_view` xmlid differs in v19, resolve the real form-view external id and re-anchor.)

- [ ] **Step 4: Full-suite run**
```bash
docker exec odooiq-odoo odoo -c /etc/odoo/odoo.conf -d gov_test \
  -u southbrook_mo_date_governance --test-enable --test-tags southbrook_mo_date_governance \
  --stop-after-init --no-http --logfile=/dev/stderr 2>&1 | grep -Ei "FAIL|ERROR|0 failed|tests"
```
Expected: all tests pass; `0 failed`.

- [ ] **Step 5: README**

`README.md`:
```markdown
# Southbrook MO Date Governance (Step 0)

Resolves the MO-date-fiction blocker (OdooIQ spec §12.5, scheduler decision step 1):
`date_deadline` becomes `today + material_lead_time_days + manufacturing_days`,
**locked** at production release, instead of the `create_date + Σ routing_time`
artifact. `deadline_authenticity` (artifact/human/governed) is the S6 signal;
Manufacturing → Deadline Artifacts is John's backfill worklist.

## Planner workflow
1. Open **Deadline Artifacts** — the MOs whose deadline is a computed fiction.
2. Per MO: **Suggest Lead Time** (from BOM vendors), review/edit, **Govern Deadline** (locks it).
3. New releases via Send-to-Production are governed+locked automatically.
Re-run the OdooIQ audit; S6_DATE_AUTHENTICITY should climb ~30% → ~85%+.

## Depends: southbrook_mrp_pm, sale.
```

- [ ] **Step 6: Commit** — `feat(mo-dates): views + artifact worklist + README (Task 7)`

---

## Out of scope (Step 0)

- **The OdooIQ `S6_DATE_AUTHENTICITY` audit signal itself** — lives in `odooiq_factory_intelligence`; this addon provides the Southbrook-side fix + an equivalent `deadline_authenticity` field the audit can read.
- **Per-component multi-level lead-time explosion** — v1 uses max first-level component vendor delay; deeper BOM explosion is a later refinement.
- **resource.calendar-accurate manufacturing_days** — v1 uses a flat minutes/working-day param; can later use `southbrook.capacity.day` / the work calendar for precision.
- **Auto-mass-rewriting historical deadlines** — deliberately excluded; John governs via the worklist.

---

## Self-Review (against spec §12.5 + the decision)

- **Coverage:** `material_lead_time_days` ✓ (T2) · `today + material_lead + manufacturing` deadline ✓ (T3+T4) · **lock (no auto-recompute)** ✓ (T4 + T6 write-guard) · lock at SO-confirm/release ✓ (T6) · artifact-vs-human detection = S6 ✓ (T5) · John's worklist ✓ (T7). John's non-code tasks explicitly carved out.
- **Placeholders:** none; the `sale_order.py` Task-2 stub is explicitly filled in Task 6 (sequenced, not shipped empty).
- **Type/name consistency:** `_govern_on_release`, `action_apply_governed_deadline`, `_governed_deadline`, `deadline_locked`, `deadline_source`, `deadline_authenticity`, `material_lead_time_days`, `manufacturing_days` used identically across tasks. `governing_deadline` context key gates the write-guard consistently.
- **Risk flagged honestly:** the parent `action_send_to_production` signature + the `mrp.mrp_production_form_view` xmlid must be verified at build (both noted inline); fixtures may need tuning on first real run (no local Odoo).
- **Scope:** one focused addon, one concern — correctly sized.
```
