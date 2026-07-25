# Materials App — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a v19 CE-native material calculator that turns a cabinet's BoM into a total material **weight** (density → weight) and a **cost** resolved through a tiered sourcing cascade, browsable in the generalized Miller-column Explorer.

**Architecture:** Two new Southbrook modules — `sb_material_core` (extends the existing `southbrook.kitchen.material` into a material master with a family taxonomy, effective density, and a `weight_source` dispatcher) and `sb_material_mrp` (computes per-line weight/cost and rolls them up through native `mrp.bom`/`mrp.production` via `bom.explode()`, with a cost-sourcing cascade resolver). Separately, `mrp_process_explorer` (in `realpublish-ai/odoo-addons`) is generalized on a branch to serve a new `material.explorer` provider alongside the existing `mrp.process.explorer`, with backcompat tests.

**Tech Stack:** Odoo 19.0 CE (Python 3.12), OWL 2 (existing Explorer component), PostgreSQL. Tests = `odoo.tests.common.TransactionCase`.

## Global Constraints

- **Odoo 19.0 CE only** — no Enterprise deps (`mrp_plm`, `quality`, `sale_product_matrix`, etc.). Copied from spec §2.6.
- **SPDX header** `# SPDX-License-Identifier: LGPL-3.0-only` on every `.py` file (matches `southbrook_mrp_kitchen_workcenters`).
- **Extend, do not duplicate** — the material master is `southbrook.kitchen.material` via `_inherit`; there is **no** new `sb.material` model (spec §14.3).
- **Weight formula constant (locked):** `weight_kg = density_g_cm3 * volume_mm3 / 1_000_000`, then `float_round(..., precision_digits=2, rounding_method="HALF-UP")` (resolves spec §14.10 unit-conversion item).
- **Volume source (made):** `southbrook_estimating.mrp.bom._compute_panel_dimensions()` → list of `(length_mm, width_mm, thickness_mm)`; never `product.template.volume` (spec §14.6, §12.1).
- **Cost is never a single stored field** — always resolved via the cascade (vendor→manual→online) and carries a provenance tag (spec §14.5). Vendor tier = snapshot-with-refresh.
- **Multi-level rollup** uses native `bom.explode()`; never sum only top-level lines (spec §14.8, blindspot #5).
- **Currency:** the cost cascade result carries `currency_id`, default `company_id.currency_id` (resolves spec §14.10 currency item; Southbrook is single-currency CAD, field added for future multi-currency).
- **Test tags:** every test class `@tagged("post_install", "-at_install", "southbrook", "sbk_material")`.
- **Test command:** `odoo -d test_sbmat -i sb_material_core,sb_material_mrp --test-enable --test-tags sbk_material --stop-after-init` on a local/staging v19 CE with the Southbrook addons path (see spec §9 and memory `southbrook_v19cr_local_test_recipe`). **Never run `--test-enable` against the live production DB.**
- **Deploy:** scoped `-u <module> --stop-after-init` on the system-docker `southbrook-odoo`, then `kill -HUP 1`; container restart when asset bundles change (spec §9). Staging soak before production for the Explorer change (spec §14.9).

---

## File Structure

```
addons/sb_material_core/
├── __manifest__.py                     depends: southbrook_mrp_kitchen_workcenters, product, uom, mail
├── models/__init__.py
├── models/material_family.py           NEW model material.family (taxonomy, parent_id nesting)
├── models/southbrook_kitchen_material.py   _inherit: family_id, weight_source, density,
│                                       density_source, base_uom_id, facing, waste_* fields
├── models/product_attribute_value.py   _inherit: material_id link + constraint
├── data/material_family_data.xml       seed taxonomy (families + types for the 14 families)
├── security/ir.model.access.csv
├── views/material_family_views.xml
├── views/southbrook_kitchen_material_views.xml   inherit form: add the new fields
└── tests/{__init__.py, test_family.py, test_material_fields.py, test_attribute_link.py}

addons/sb_material_mrp/
├── __manifest__.py                     depends: sb_material_core, mrp, purchase, southbrook_estimating
├── models/__init__.py
├── models/material_cost_source.py      NEW Transient-free helper model material.cost.source
│                                       (cascade resolver: vendor→manual→online, snapshot, provenance)
├── models/mrp_bom.py                   _inherit mrp.bom.line: material_id, component_volume_mm3,
│                                       component_weight_kg, component_material_cost (+ currency)
├── models/mrp_production.py            _inherit: material_weight_total, material_cost_total,
│                                       scrap_factor, weight_to_purchase
└── tests/{__init__.py, test_weight_line.py, test_weight_rollup_multilevel.py,
             test_cost_cascade.py, test_production_totals.py}

realpublish-ai/odoo-addons/mrp_process_explorer/  (on branch feat/material-provider)
├── models/__init__.py                  + material_explorer
├── models/material_explorer.py         NEW provider material.explorer with get_data(source_id=None)
├── views/mrp_explorer_action.xml       + a client action record with context explorer_provider=material.explorer
└── tests/{__init__.py, test_provider_backcompat.py, test_material_provider.py}
```

---

## Task 1: Scaffold `sb_material_core` (installs empty)

**Files:**
- Create: `addons/sb_material_core/__manifest__.py`
- Create: `addons/sb_material_core/__init__.py`
- Create: `addons/sb_material_core/models/__init__.py`
- Create: `addons/sb_material_core/security/ir.model.access.csv`

**Interfaces:**
- Produces: an installable module `sb_material_core` depending on `southbrook_mrp_kitchen_workcenters`.

- [ ] **Step 1: Write the manifest**

```python
# addons/sb_material_core/__manifest__.py
# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Materials — Core",
    "version": "19.0.1.0.0",
    "category": "Manufacturing",
    "summary": "Material master (extends kitchen material): family taxonomy, "
               "effective density, weight_source, per-family waste.",
    "author": "Southbrook / METISA",
    "license": "LGPL-3",
    "depends": ["southbrook_mrp_kitchen_workcenters", "product", "uom", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/material_family_data.xml",
        "views/material_family_views.xml",
        "views/southbrook_kitchen_material_views.xml",
    ],
    "installable": True,
}
```

- [ ] **Step 2: Write the package inits**

```python
# addons/sb_material_core/__init__.py
# SPDX-License-Identifier: LGPL-3.0-only
from . import models
```
```python
# addons/sb_material_core/models/__init__.py
# SPDX-License-Identifier: LGPL-3.0-only
from . import material_family
from . import southbrook_kitchen_material
from . import product_attribute_value
```

- [ ] **Step 3: Minimal ACL (filled per model in later tasks)**

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_material_family_user,material.family user,model_material_family,base.group_user,1,0,0,0
access_material_family_mgr,material.family mgr,model_material_family,base.group_system,1,1,1,1
```

- [ ] **Step 4: Create empty data/view files referenced by the manifest** so install doesn't fail (they get real content in Tasks 2–3).

```xml
<!-- addons/sb_material_core/data/material_family_data.xml -->
<odoo><data noupdate="1"></data></odoo>
```
Repeat empty `<odoo/>` stubs for `views/material_family_views.xml` and `views/southbrook_kitchen_material_views.xml`.

- [ ] **Step 5: Commit**

```bash
git add addons/sb_material_core
git commit -m "feat(sb_material_core): scaffold module"
```

---

## Task 2: `material.family` taxonomy model + seed

**Files:**
- Create: `addons/sb_material_core/models/material_family.py`
- Modify: `addons/sb_material_core/data/material_family_data.xml`
- Modify: `addons/sb_material_core/views/material_family_views.xml`
- Test: `addons/sb_material_core/tests/test_family.py`

**Interfaces:**
- Produces: model `material.family` with fields `name` (Char), `code` (Char), `parent_id` (Many2one self), `complete_name` (computed, stored), `default_weight_source` (Selection), `default_waste_pct` (Float). XML ids `sb_material_core.fam_<code>`.

- [ ] **Step 1: Write the failing test**

```python
# addons/sb_material_core/tests/test_family.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_material")
class TestFamily(TransactionCase):
    def test_taxonomy_seeded_and_nested(self):
        Fam = self.env["material.family"]
        ewood = self.env.ref("sb_material_core.fam_ewood")
        ply = self.env.ref("sb_material_core.fam_ewood_ply")
        self.assertEqual(ply.parent_id, ewood)
        self.assertEqual(ply.complete_name, "Engineered Wood / Plywood")
        # all 14 top-level families present
        self.assertGreaterEqual(Fam.search_count([("parent_id", "=", False)]), 14)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `odoo -d test_sbmat -i sb_material_core --test-enable --test-tags sbk_material --stop-after-init`
Expected: FAIL — `ValueError: External ID not found: sb_material_core.fam_ewood`.

- [ ] **Step 3: Write the model**

```python
# addons/sb_material_core/models/material_family.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo import api, fields, models

WEIGHT_SOURCES = [
    ("density_volume", "Density × volume (sheet/solid wood)"),
    ("density_area", "Density × area × thickness (tile/drywall/stone)"),
    ("linear_density", "Linear density kg/m (edgebanding)"),
    ("per_unit", "Weight per unit (hardware)"),
    ("none", "Not tracked (bought/subcontracted)"),
]


class MaterialFamily(models.Model):
    _name = "material.family"
    _description = "Material Family"
    _parent_store = True
    _order = "complete_name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    parent_id = fields.Many2one("material.family", ondelete="cascade", index=True)
    parent_path = fields.Char(index=True, unaccent=False)
    complete_name = fields.Char(compute="_compute_complete_name", store=True, recursive=True)
    default_weight_source = fields.Selection(WEIGHT_SOURCES, default="density_volume")
    default_waste_pct = fields.Float(string="Default Waste %", default=0.0)

    _code_uniq = models.Constraint("unique(code)", "Family code must be unique.")

    @api.depends("name", "parent_id.complete_name")
    def _compute_complete_name(self):
        for fam in self:
            fam.complete_name = (
                "%s / %s" % (fam.parent_id.complete_name, fam.name)
                if fam.parent_id else fam.name
            )
```

- [ ] **Step 4: Seed the taxonomy** (14 families + representative types)

```xml
<!-- addons/sb_material_core/data/material_family_data.xml -->
<odoo><data noupdate="1">
  <record id="fam_ewood" model="material.family">
    <field name="name">Engineered Wood</field><field name="code">ewood</field>
    <field name="default_weight_source">density_volume</field><field name="default_waste_pct">12</field>
  </record>
  <record id="fam_ewood_ply" model="material.family">
    <field name="name">Plywood</field><field name="code">ewood_ply</field>
    <field name="parent_id" ref="fam_ewood"/>
  </record>
  <record id="fam_swood" model="material.family"><field name="name">Solid Wood</field><field name="code">swood</field><field name="default_weight_source">density_volume</field></record>
  <record id="fam_lam" model="material.family"><field name="name">Laminates &amp; Edgeband</field><field name="code">lam</field><field name="default_weight_source">linear_density</field></record>
  <record id="fam_glass" model="material.family"><field name="name">Glass</field><field name="code">glass</field><field name="default_weight_source">density_area</field></record>
  <record id="fam_stone" model="material.family"><field name="name">Stone / Quartz</field><field name="code">stone</field><field name="default_weight_source">none</field></record>
  <record id="fam_ctop_stone" model="material.family"><field name="name">Countertop Stone</field><field name="code">ctop_stone</field><field name="parent_id" ref="fam_stone"/><field name="default_weight_source">none</field></record>
  <record id="fam_ctop_lam" model="material.family"><field name="name">Countertop Laminate</field><field name="code">ctop_lam</field><field name="default_weight_source">none</field></record>
  <record id="fam_tile" model="material.family"><field name="name">Ceramic Tile</field><field name="code">tile</field><field name="default_weight_source">none</field></record>
  <record id="fam_drywall" model="material.family"><field name="name">Drywall / Gypsum</field><field name="code">drywall</field><field name="default_weight_source">none</field></record>
  <record id="fam_metal" model="material.family"><field name="name">Metals</field><field name="code">metal</field><field name="default_weight_source">density_volume</field></record>
  <record id="fam_plastic" model="material.family"><field name="name">Plastics</field><field name="code">plastic</field><field name="default_weight_source">density_volume</field></record>
  <record id="fam_concrete" model="material.family"><field name="name">Concrete / Cement</field><field name="code">concrete</field><field name="default_weight_source">density_area</field></record>
  <record id="fam_hw" model="material.family"><field name="name">Hardware / Fasteners</field><field name="code">hw</field><field name="default_weight_source">per_unit</field></record>
  <record id="fam_finish" model="material.family"><field name="name">Adhesives &amp; Finishes</field><field name="code">finish</field><field name="default_weight_source">none</field></record>
</data></odoo>
```

- [ ] **Step 5: Minimal tree/form view** so the model is navigable

```xml
<!-- addons/sb_material_core/views/material_family_views.xml -->
<odoo>
  <record id="view_material_family_list" model="ir.ui.view">
    <field name="name">material.family.list</field>
    <field name="model">material.family</field>
    <field name="arch" type="xml">
      <list><field name="complete_name"/><field name="code"/><field name="default_weight_source"/></list>
    </field>
  </record>
  <record id="action_material_family" model="ir.actions.act_window">
    <field name="name">Material Families</field><field name="res_model">material.family</field>
    <field name="view_mode">list,form</field>
  </record>
</odoo>
```

- [ ] **Step 6: Run test to verify it passes**

Run: `odoo -d test_sbmat -i sb_material_core --test-enable --test-tags sbk_material --stop-after-init`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add addons/sb_material_core
git commit -m "feat(sb_material_core): material.family taxonomy + seed"
```

---

## Task 3: Extend `southbrook.kitchen.material` into the master

**Files:**
- Create: `addons/sb_material_core/models/southbrook_kitchen_material.py`
- Modify: `addons/sb_material_core/views/southbrook_kitchen_material_views.xml`
- Test: `addons/sb_material_core/tests/test_material_fields.py`

**Interfaces:**
- Produces on `southbrook.kitchen.material`: `family_id` (M2o material.family), `weight_source` (Selection, WEIGHT_SOURCES), `density` (Float g/cm³), `density_source` (Selection: material|family_default), `effective_density` (computed Float), `base_uom_id` (M2o uom.uom), `facing` (Selection: none|paper|fiberglass), `waste_pct` (Float), `linear_density` (Float kg/m), `weight_per_unit` (Float kg).

- [ ] **Step 1: Write the failing test**

```python
# addons/sb_material_core/tests/test_material_fields.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_material")
class TestMaterialFields(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Mat = self.env["southbrook.kitchen.material"]
        self.fam_ply = self.env.ref("sb_material_core.fam_ewood_ply")

    def test_effective_density_uses_own_value(self):
        m = self.Mat.create({"name": "Walnut Ply 18", "code": "WPL18",
                             "family_id": self.fam_ply.id, "density": 0.65,
                             "density_source": "material"})
        self.assertEqual(m.effective_density, 0.65)

    def test_effective_density_falls_back_to_family_default(self):
        # family default density lives on family via a fallback map; when the
        # material has none and density_source=family_default, effective!=0
        m = self.Mat.create({"name": "Generic Ply", "code": "GPL",
                             "family_id": self.fam_ply.id, "density": 0.0,
                             "density_source": "family_default"})
        self.assertGreater(m.effective_density, 0.0)
```

- [ ] **Step 2: Run to verify it fails**

Run: `odoo -d test_sbmat -u sb_material_core --test-enable --test-tags sbk_material --stop-after-init`
Expected: FAIL — field `effective_density` does not exist.

- [ ] **Step 3: Write the extension** (family default density map keeps the master to ~a dozen values per spec §14.3)

```python
# addons/sb_material_core/models/southbrook_kitchen_material.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo import api, fields, models
from .material_family import WEIGHT_SOURCES

# Estimation-grade family fallback densities (g/cm³), spec §14.4 (±15%).
FAMILY_DEFAULT_DENSITY = {
    "ewood": 0.68, "ewood_ply": 0.65, "swood": 0.70, "metal": 7.85,
    "plastic": 1.20, "glass": 2.50, "stone": 2.60, "concrete": 2.30,
}


class KitchenMaterial(models.Model):
    _inherit = "southbrook.kitchen.material"

    family_id = fields.Many2one("material.family", index=True)
    weight_source = fields.Selection(WEIGHT_SOURCES, default="density_volume")
    density = fields.Float(string="Density (g/cm³)", digits=(8, 3),
                           help="Effective density — estimation grade (±15%).")
    density_source = fields.Selection(
        [("material", "This material"), ("family_default", "Family default")],
        default="material")
    effective_density = fields.Float(compute="_compute_effective_density", digits=(8, 3))
    base_uom_id = fields.Many2one("uom.uom")
    facing = fields.Selection(
        [("none", "None"), ("paper", "Paper-faced"), ("fiberglass", "Fiberglass (DensGlass)")],
        default="none", help="Drywall/board facing.")
    waste_pct = fields.Float(string="Waste %")
    linear_density = fields.Float(string="Linear density (kg/m)", help="Edgebanding etc.")
    weight_per_unit = fields.Float(string="Weight per unit (kg)", help="Hardware etc.")
    # Cost cascade Tier-2 (manual) inputs — consumed by material.cost.source (Task 8).
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id)
    manual_unit_price = fields.Monetary(
        string="Manual Unit Price", currency_field="currency_id",
        help="Manual cost-basis override for the sourcing cascade (Tier 2).")

    @api.depends("density", "density_source", "family_id")
    def _compute_effective_density(self):
        for m in self:
            if m.density_source == "material" and m.density:
                m.effective_density = m.density
            else:
                code = m.family_id.code or ""
                # walk up to a known family default
                fam = m.family_id
                val = 0.0
                while fam and not val:
                    val = FAMILY_DEFAULT_DENSITY.get(fam.code, 0.0)
                    fam = fam.parent_id
                m.effective_density = val
```

- [ ] **Step 4: Extend the form view** (append the new fields; view id from workcenters module)

```xml
<!-- addons/sb_material_core/views/southbrook_kitchen_material_views.xml -->
<odoo>
  <record id="view_kitchen_material_form_material" model="ir.ui.view">
    <field name="name">southbrook.kitchen.material.form.material</field>
    <field name="model">southbrook.kitchen.material</field>
    <field name="inherit_id" ref="southbrook_mrp_kitchen_workcenters.view_sbk_material_form"/>
    <field name="arch" type="xml">
      <field name="note" position="before">
        <group string="Material Master">
          <field name="family_id"/>
          <field name="weight_source"/>
          <field name="density"/>
          <field name="density_source"/>
          <field name="effective_density" readonly="1"/>
          <field name="base_uom_id"/>
          <field name="facing"/>
          <field name="waste_pct"/>
          <field name="linear_density" invisible="weight_source != 'linear_density'"/>
          <field name="weight_per_unit" invisible="weight_source != 'per_unit'"/>
          <field name="manual_unit_price"/>
          <field name="currency_id" invisible="1"/>
        </group>
      </field>
    </field>
  </record>
</odoo>
```
> **Verified** (agent, 2026-07-25): the real external id is `view_sbk_material_form`
> (`southbrook_mrp_kitchen_workcenters/views/southbrook_kitchen_material_views.xml:19`).
> No field collisions — all added fields are new on `southbrook.kitchen.material`.

- [ ] **Step 5: Run to verify it passes**

Run: `odoo -d test_sbmat -u sb_material_core --test-enable --test-tags sbk_material --stop-after-init`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add addons/sb_material_core
git commit -m "feat(sb_material_core): extend kitchen material with master fields + effective density"
```

---

## Task 4: `product.attribute.value` → material link

**Files:**
- Create: `addons/sb_material_core/models/product_attribute_value.py`
- Modify: `addons/sb_material_core/security/ir.model.access.csv` (no new model; skip)
- Test: `addons/sb_material_core/tests/test_attribute_link.py`

**Interfaces:**
- Produces on `product.attribute.value`: `material_id` (M2o southbrook.kitchen.material). Helper `product.product._resolve_material()` → returns the linked material or `False`.

- [ ] **Step 1: Failing test**

```python
# addons/sb_material_core/tests/test_attribute_link.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_material")
class TestAttributeLink(TransactionCase):
    def test_value_carries_material(self):
        mat = self.env["southbrook.kitchen.material"].create(
            {"name": "Maple Ply 18", "code": "MPL18", "density": 0.62})
        attr = self.env["product.attribute"].create({"name": "Material"})
        val = self.env["product.attribute.value"].create(
            {"name": "Maple Ply 18", "attribute_id": attr.id, "material_id": mat.id})
        self.assertEqual(val.material_id, mat)
```

- [ ] **Step 2: Run — expect FAIL** (field `material_id` unknown).
Run: `odoo -d test_sbmat -u sb_material_core --test-enable --test-tags sbk_material --stop-after-init`

- [ ] **Step 3: Implement**

```python
# addons/sb_material_core/models/product_attribute_value.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields, models


class ProductAttributeValue(models.Model):
    _inherit = "product.attribute.value"
    material_id = fields.Many2one(
        "southbrook.kitchen.material", string="Material",
        help="Physical material this attribute value resolves to.")


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _resolve_material(self):
        """Return the southbrook.kitchen.material for this variant via its
        'Material' attribute value, else empty recordset."""
        self.ensure_one()
        vals = self.product_template_attribute_value_ids.mapped(
            "product_attribute_value_id").filtered("material_id")
        return vals[:1].material_id
```

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** `git commit -am "feat(sb_material_core): link attribute value -> material + _resolve_material()"`

---

## Task 5: Scaffold `sb_material_mrp` (installs empty)

**Files:**
- Create: `addons/sb_material_mrp/__manifest__.py`, `__init__.py`, `models/__init__.py`

**Interfaces:**
- Produces: installable `sb_material_mrp` depending on `sb_material_core, mrp, purchase, southbrook_estimating`.

- [ ] **Step 1: Manifest**

```python
# addons/sb_material_mrp/__manifest__.py
# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Materials — MRP",
    "version": "19.0.1.0.0",
    "category": "Manufacturing",
    "summary": "Density->weight + tiered cost sourcing on native MRP BoM/MO.",
    "license": "LGPL-3",
    "depends": ["sb_material_core", "mrp", "purchase", "southbrook_estimating"],
    "data": ["security/ir.model.access.csv"],
    "installable": True,
}
```

- [ ] **Step 2:** `__init__.py` → `from . import models`; `models/__init__.py` → import `material_cost_source`, `mrp_bom`, `mrp_production` (create the files empty-but-valid now, filled next).
- [ ] **Step 3:** `security/ir.model.access.csv` header row + a line for `material.cost.source` (added in Task 8).
- [ ] **Step 4: Commit** `git add addons/sb_material_mrp && git commit -m "feat(sb_material_mrp): scaffold"`

---

## Task 6: Per-line weight (weight_source dispatch + locked conversion)

**Files:**
- Create: `addons/sb_material_mrp/models/mrp_bom.py`
- Test: `addons/sb_material_mrp/tests/test_weight_line.py`

**Interfaces:**
- Consumes: `product.product._resolve_material()` (Task 4); `southbrook.kitchen.material.effective_density`, `weight_source`, `linear_density`, `weight_per_unit` (Task 3); `southbrook_estimating.mrp.bom._compute_panel_dimensions()` (existing).
- Produces on `mrp.bom.line`: `material_id` (computed M2o), `component_volume_mm3` (computed Float), `component_weight_kg` (computed Float, stored).

- [ ] **Step 1: Failing test — the exact conversion**

```python
# addons/sb_material_mrp/tests/test_weight_line.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_material")
class TestWeightLine(TransactionCase):
    def test_density_volume_conversion(self):
        # 600 x 400 x 18 mm panel = 4_320_000 mm3; walnut ply 0.65 g/cm3
        # weight_kg = 0.65 * 4_320_000 / 1_000_000 = 2.808 -> 2.81 kg
        Mat = self.env["southbrook.kitchen.material"]
        m = Mat.create({"name": "WPL18", "code": "WPL18", "density": 0.65,
                        "weight_source": "density_volume"})
        line = self.env["mrp.bom.line"].new({})
        line.material_id = m  # test the pure helper directly
        w = line._weight_from_volume(m, 4_320_000.0)
        self.assertAlmostEqual(w, 2.81, places=2)

    def test_per_unit_source(self):
        Mat = self.env["southbrook.kitchen.material"]
        m = Mat.create({"name": "Hinge", "code": "HNG",
                        "weight_source": "per_unit", "weight_per_unit": 0.4})
        line = self.env["mrp.bom.line"].new({})
        self.assertAlmostEqual(line._weight_for_qty(m, 0.0, 2.0), 0.8, places=2)
```

- [ ] **Step 2: Run — expect FAIL** (`_weight_from_volume` missing).

- [ ] **Step 3: Implement the dispatcher + conversion**

```python
# addons/sb_material_mrp/models/mrp_bom.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo import api, fields, models
from odoo.tools import float_round


class MrpBomLine(models.Model):
    _inherit = "mrp.bom.line"

    material_id = fields.Many2one(
        "southbrook.kitchen.material", compute="_compute_material_id", store=True)
    component_volume_mm3 = fields.Float(compute="_compute_component_weight", store=True)
    component_weight_kg = fields.Float(
        string="Weight (kg)", compute="_compute_component_weight", store=True, digits=(10, 2))

    @api.depends("product_id")
    def _compute_material_id(self):
        for line in self:
            line.material_id = line.product_id._resolve_material() if line.product_id else False

    def _weight_from_volume(self, material, volume_mm3):
        """LOCKED constant: kg = density(g/cm3) * volume(mm3) / 1e6."""
        raw = material.effective_density * volume_mm3 / 1_000_000.0
        return float_round(raw, precision_digits=2, rounding_method="HALF-UP")

    def _panel_volume_mm3(self, line):
        """Total cut-panel volume (mm³) for the CABINET this line belongs to.
        `_compute_panel_dimensions` is an @api.model method on `mrp.bom` taking
        (width_mm, height_mm, depth_mm, ...) and returning a dict of panel tuples
        `(length_mm, width_mm, thickness_mm)` + hardware counts (VERIFIED, agent
        2026-07-25). Carcass weight is a cabinet-level figure, so we read the parent
        BoM product's dimensions. Returns 0.0 (weight unavailable — never faked) if
        dims/cutlist are absent, and LOGS rather than silently swallowing a real error."""
        import logging
        _logger = logging.getLogger(__name__)
        Bom = self.env["mrp.bom"]
        if not hasattr(Bom, "_compute_panel_dimensions"):
            return 0.0
        cab = line.bom_id.product_tmpl_id
        # EXECUTION-TIME STEP: confirm the cabinet W/H/D field names in
        # southbrook_estimating with:
        #   grep -rnE "width|height|depth" addons/southbrook_estimating/models/product_*.py
        # and replace the getattr keys below with the real fields.
        W = getattr(cab, "sb_width_mm", 0.0) or 0.0
        H = getattr(cab, "sb_height_mm", 0.0) or 0.0
        D = getattr(cab, "sb_depth_mm", 0.0) or 0.0
        if not (W and H and D):
            return 0.0
        try:
            res = Bom._compute_panel_dimensions(W, H, D)
            panels = res.get("panels", []) if isinstance(res, dict) else res
            return sum(L * Wi * T for (L, Wi, T) in panels)
        except Exception as e:  # noqa: BLE001 — log, don't mask upstream breakage
            _logger.warning("panel-dim volume failed for BoM %s: %s", line.bom_id.id, e)
            return 0.0

    def _weight_for_qty(self, material, volume_mm3, qty):
        src = material.weight_source
        if src == "density_volume":
            return self._weight_from_volume(material, volume_mm3) * qty
        if src == "linear_density":
            # qty interpreted as linear metres for linear materials
            return float_round(material.linear_density * qty, precision_digits=2,
                               rounding_method="HALF-UP")
        if src == "per_unit":
            return float_round(material.weight_per_unit * qty, precision_digits=2,
                               rounding_method="HALF-UP")
        # density_area / none: no volumetric weight in Phase 1 (bought path)
        return 0.0

    @api.depends("material_id", "product_qty", "material_id.weight_source",
                 "material_id.effective_density")
    def _compute_component_weight(self):
        for line in self:
            m = line.material_id
            if not m:
                line.component_volume_mm3 = 0.0
                line.component_weight_kg = 0.0
                continue
            vol = self._panel_volume_mm3(line) if m.weight_source == "density_volume" else 0.0
            line.component_volume_mm3 = vol
            line.component_weight_kg = self._weight_for_qty(m, vol, line.product_qty)
```

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** `git commit -am "feat(sb_material_mrp): per-line weight via weight_source dispatch"`

---

## Task 7: Multi-level weight rollup via `bom.explode()`

**Files:**
- Modify: `addons/sb_material_mrp/models/mrp_bom.py` (add rollup on `mrp.bom`)
- Test: `addons/sb_material_mrp/tests/test_weight_rollup_multilevel.py`

**Interfaces:**
- Produces on `mrp.bom`: `material_weight_total` (computed Float). Uses native `bom.explode(product, qty)`.

- [ ] **Step 1: Failing test — a 2-level BoM sums leaf weights**

```python
# addons/sb_material_mrp/tests/test_weight_rollup_multilevel.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_material")
class TestRollup(TransactionCase):
    def _material_product(self, name, weight_per_unit):
        """Create a product whose variant resolves to a per_unit material via the
        REAL attribute->material link (Task 4). per_unit avoids any cutlist dependency
        so this test isolates the multi-level rollup."""
        mat = self.env["southbrook.kitchen.material"].create(
            {"name": name, "code": name, "weight_source": "per_unit",
             "weight_per_unit": weight_per_unit})
        attr = self.env["product.attribute"].create(
            {"name": "Material-%s" % name, "create_variant": "no_variant"})
        val = self.env["product.attribute.value"].create(
            {"name": name, "attribute_id": attr.id, "material_id": mat.id})
        tmpl = self.env["product.template"].create({
            "name": name, "type": "consu",
            "attribute_line_ids": [(0, 0, {
                "attribute_id": attr.id, "value_ids": [(6, 0, [val.id])]})],
        })
        variant = tmpl.product_variant_ids[:1]
        self.assertEqual(variant._resolve_material(), mat)  # link works
        return variant

    def test_multilevel_sums_leaves(self):
        Bom = self.env["mrp.bom"]
        leaf = self._material_product("LEAF", 0.5)          # 0.5 kg per unit
        sub = self.env["product.product"].create({"name": "Sub", "type": "consu"})
        top = self.env["product.product"].create({"name": "Top", "type": "consu"})
        # sub-assembly BoM: 1 x leaf
        Bom.create({"product_tmpl_id": sub.product_tmpl_id.id, "product_qty": 1.0,
                    "bom_line_ids": [(0, 0, {"product_id": leaf.id, "product_qty": 1.0})]})
        # top BoM: 1 x sub  (sub has its own BoM -> explode() must reach the leaf)
        top_bom = Bom.create({"product_tmpl_id": top.product_tmpl_id.id, "product_qty": 1.0,
                    "bom_line_ids": [(0, 0, {"product_id": sub.id, "product_qty": 1.0})]})
        self.assertAlmostEqual(top_bom.material_weight_total, 0.5, places=2)

- [ ] **Step 2: Run — expect FAIL** (`material_weight_total` missing).

- [ ] **Step 3: Implement the rollup**

```python
# append to addons/sb_material_mrp/models/mrp_bom.py

class MrpBom(models.Model):
    _inherit = "mrp.bom"

    material_weight_total = fields.Float(
        string="Total Material Weight (kg)", compute="_compute_material_weight_total",
        digits=(10, 2))

    def _compute_material_weight_total(self):
        for bom in self:
            total = 0.0
            # explode to leaves so nested/phantom BoMs are flattened (blindspot #5)
            _boms, lines = bom.explode(bom.product_id or bom.product_tmpl_id.product_variant_id,
                                       bom.product_qty)
            for line, data in lines:
                m = line.material_id
                if not m:
                    continue
                qty = data.get("qty", line.product_qty)
                vol = line._panel_volume_mm3(line) if m.weight_source == "density_volume" else 0.0
                total += line._weight_for_qty(m, vol, qty)
            bom.material_weight_total = round(total, 2)
```

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** `git commit -am "feat(sb_material_mrp): multi-level weight rollup via bom.explode"`

---

## Task 8: Cost-sourcing cascade resolver

**Files:**
- Create: `addons/sb_material_mrp/models/material_cost_source.py`
- Modify: `addons/sb_material_mrp/security/ir.model.access.csv`
- Test: `addons/sb_material_mrp/tests/test_cost_cascade.py`

**Interfaces:**
- Produces model `material.cost.source` with `_resolve(product, qty)` → dict `{unit_price, currency_id, tier, provenance, dated}`. Tier order: `vendor` (product.seller_ids latest price / last PO) → `manual` (material master manual price, if set) → `online` (stub, returns tier="online", price 0.0, flagged). Snapshot fields live on the consuming line (Task 9).

- [ ] **Step 1: Failing test**

```python
# addons/sb_material_mrp/tests/test_cost_cascade.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_material")
class TestCostCascade(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Src = self.env["material.cost.source"]
        self.vendor = self.env["res.partner"].create({"name": "Acme Ply Co"})
        self.prod = self.env["product.product"].create({"name": "Walnut Ply", "type": "consu"})

    def test_vendor_tier_wins_when_supplierinfo_exists(self):
        self.env["product.supplierinfo"].create(
            {"partner_id": self.vendor.id, "product_tmpl_id": self.prod.product_tmpl_id.id,
             "price": 92.0})
        res = self.Src._resolve(self.prod, 1.0)
        self.assertEqual(res["tier"], "vendor")
        self.assertAlmostEqual(res["unit_price"], 92.0)
        self.assertIn("Acme", res["provenance"])

    def test_falls_to_online_when_nothing(self):
        res = self.Src._resolve(self.prod, 1.0)
        self.assertEqual(res["tier"], "online")
        self.assertEqual(res["unit_price"], 0.0)
```

- [ ] **Step 2: Run — expect FAIL** (model missing).

- [ ] **Step 3: Implement**

```python
# addons/sb_material_mrp/models/material_cost_source.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo import api, fields, models


class MaterialCostSource(models.AbstractModel):
    _name = "material.cost.source"
    _description = "Material cost-sourcing cascade resolver"

    @api.model
    def _resolve(self, product, qty):
        """Return the best available unit price for `product`, with provenance.
        Order: vendor (Purchasing) -> manual (material master) -> online stub."""
        company = self.env.company
        # Tier 1 — vendor: cheapest current supplierinfo price
        seller = product._select_seller(quantity=qty) if hasattr(product, "_select_seller") else False
        if seller and seller.price:
            return {"unit_price": seller.price,
                    "currency_id": (seller.currency_id or company.currency_id).id,
                    "tier": "vendor",
                    "provenance": "vendor · %s" % seller.partner_id.display_name,
                    "dated": fields.Date.context_today(self)}
        # Tier 2 — manual: a manual price on the resolved material master
        material = product._resolve_material() if hasattr(product, "_resolve_material") else False
        if material and getattr(material, "manual_unit_price", 0.0):
            return {"unit_price": material.manual_unit_price,
                    "currency_id": company.currency_id.id, "tier": "manual",
                    "provenance": "manual", "dated": fields.Date.context_today(self)}
        # Tier 3 — online stub (Phase 5 wires real research); flagged, never trusted
        return {"unit_price": 0.0, "currency_id": company.currency_id.id,
                "tier": "online", "provenance": "online est. (unset)", "dated": False}
```
Add `manual_unit_price = fields.Monetary(currency_field="currency_id")` + `currency_id` (default company) to `southbrook.kitchen.material` in `sb_material_core` (Task 3 file) — small follow-up edit; commit with this task.
Add ACL line for `material.cost.source`? No — AbstractModel needs none.

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** `git commit -am "feat(sb_material_mrp): cost-sourcing cascade resolver (vendor->manual->online)"`

---

## Task 9: MO totals — cost snapshot, scrap, weight-to-purchase

**Files:**
- Create: `addons/sb_material_mrp/models/mrp_production.py`
- Test: `addons/sb_material_mrp/tests/test_production_totals.py`

**Interfaces:**
- Consumes: `mrp.bom.material_weight_total` (Task 7); `material.cost.source._resolve` (Task 8).
- Produces on `mrp.production`: `material_weight_total` (related/computed), `scrap_factor` (Float %), `weight_to_purchase` (computed), `material_cost_total` (computed via cascade over components), `cost_provenance` (Char summary), `cost_snapshot_date` (Date), action `action_refresh_material_prices()`.

- [ ] **Step 1: Failing test**

```python
# addons/sb_material_mrp/tests/test_production_totals.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_material")
class TestProductionTotals(TransactionCase):
    def test_weight_to_purchase_applies_scrap(self):
        mo = self.env["mrp.production"].new({})
        self.assertAlmostEqual(mo._weight_to_purchase(100.0, 12.0), 112.0, places=2)

    def test_missing_price_is_flagged_not_zeroed_silently(self):
        mo = self.env["mrp.production"].new({})
        prov = mo._merge_provenance([{"tier": "vendor"}, {"tier": "online"}])
        self.assertIn("online", prov)  # honesty: surfaced, not hidden
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

```python
# addons/sb_material_mrp/models/mrp_production.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo import api, fields, models


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    material_weight_total = fields.Float(compute="_compute_material_totals", digits=(10, 2))
    scrap_factor = fields.Float(string="Scrap %", default=0.0)
    weight_to_purchase = fields.Float(compute="_compute_material_totals", digits=(10, 2))
    material_cost_total = fields.Monetary(compute="_compute_material_totals",
                                          currency_field="company_currency_id")
    company_currency_id = fields.Many2one(related="company_id.currency_id")
    cost_provenance = fields.Char(compute="_compute_material_totals")
    cost_snapshot_date = fields.Date()

    def _weight_to_purchase(self, weight_total, scrap_pct):
        return round(weight_total * (1.0 + (scrap_pct or 0.0) / 100.0), 2)

    def _merge_provenance(self, rows):
        tiers = sorted({r.get("tier", "online") for r in rows})
        return " · ".join(tiers)

    @api.depends("bom_id", "move_raw_ids.product_id", "move_raw_ids.product_uom_qty",
                 "scrap_factor")
    def _compute_material_totals(self):
        Src = self.env["material.cost.source"]
        for mo in self:
            weight = mo.bom_id.material_weight_total if mo.bom_id else 0.0
            rows, cost = [], 0.0
            for move in mo.move_raw_ids:
                r = Src._resolve(move.product_id, move.product_uom_qty)
                rows.append(r)
                # Phase-1 is single-currency (company). Converting r["currency_id"] ->
                # company currency is a later-phase item (spec §14.10 currency).
                cost += r["unit_price"] * move.product_uom_qty
            mo.material_weight_total = weight
            mo.weight_to_purchase = mo._weight_to_purchase(weight, mo.scrap_factor)
            mo.material_cost_total = cost
            mo.cost_provenance = mo._merge_provenance(rows) if rows else ""

    def action_refresh_material_prices(self):
        """Snapshot-with-refresh: stamp today's date; recompute pulls fresh vendor prices."""
        self.cost_snapshot_date = fields.Date.context_today(self)
        self._compute_material_totals()
        return True
```

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** `git commit -am "feat(sb_material_mrp): MO material totals, scrap, cost snapshot + provenance"`

---

## Task 10: Generalize `mrp_process_explorer` — `material.explorer` provider (on a branch)

**Files (in `realpublish-ai/odoo-addons`, branch `feat/material-provider`):**
- Create: `mrp_process_explorer/models/material_explorer.py`
- Modify: `mrp_process_explorer/models/__init__.py`
- Modify: `mrp_process_explorer/views/mrp_explorer_action.xml` (add a client action with `context={'explorer_provider': 'material.explorer'}`)
- Test: `mrp_process_explorer/tests/test_provider_backcompat.py`, `test_material_provider.py`

**Interfaces:**
- Consumes: the existing provider contract — a model exposing `get_data(source_id=None)` returning the Explorer payload (the existing `mrp.process.explorer` is the reference).
- Produces: `material.explorer.get_data(source_id=None)` returning `{ok, rows, ...}` where rows are families→materials with a density-first detail payload.

- [ ] **Step 1: Backcompat failing test — existing provider unchanged**

```python
# mrp_process_explorer/tests/test_provider_backcompat.py
from odoo.tests.common import TransactionCase, tagged

@tagged("post_install", "-at_install", "mpx")
class TestBackcompat(TransactionCase):
    def test_process_provider_still_returns_contract(self):
        data = self.env["mrp.process.explorer"].get_data()
        self.assertIn("ok", data)  # existing keys preserved
```

- [ ] **Step 2: Material provider failing test**

```python
# mrp_process_explorer/tests/test_material_provider.py
from odoo.tests.common import TransactionCase, tagged

@tagged("post_install", "-at_install", "mpx")
class TestMaterialProvider(TransactionCase):
    def test_material_provider_contract(self):
        data = self.env["material.explorer"].get_data()
        self.assertIn("ok", data)
        self.assertIn("rows", data)
```

- [ ] **Step 3: Run both — backcompat PASSES (no change yet), material FAILS (model missing).**
Run: `odoo -d test_mpx -u mrp_process_explorer --test-enable --test-tags mpx --stop-after-init`

- [ ] **Step 4: Implement the provider** (returns the same top-level contract keys as `mrp.process.explorer`, so the OWL shell renders it unchanged)

```python
# mrp_process_explorer/models/material_explorer.py
# -*- coding: utf-8 -*-
from odoo import api, fields, models


class MaterialExplorer(models.AbstractModel):
    _name = "material.explorer"
    _description = "Material catalog provider for the Miller-column Explorer"

    @api.model
    def get_data(self, source_id=None):
        Mat = self.env.get("southbrook.kitchen.material")
        rows = []
        if Mat is not None:
            for m in Mat.search([]):
                rows.append({
                    "task_id": m.id,          # CONTRACT: frontend keys rows on task_id, NOT id
                    "name": m.name,
                    "stage_name": "Active", "stage_seq": 0, "stage_known": True,
                    "effective_dd": None, "has_own_dd": False, "days_to_dd": None,
                    "dd_offset_days": None, "exceeds_end": False,
                    "milestones": [],         # non-MRP rows have no work-order milestones
                    "detail": [
                        {"label": "Density", "value": "%.3f g/cm³" % m.effective_density},
                        {"label": "Weight source", "value": m.weight_source or "—"},
                        {"label": "Family", "value": m.family_id.complete_name if m.family_id else "—"},
                    ],
                    "flags": [], "bom": None, "versions": [],
                })
        return {
            "ok": True,
            "rows": rows,
            "today": fields.Date.context_today(self).isoformat(),
            "timeline": {"id": 0, "name": "Material Catalog", "drop_dead": None,
                         "is_live": True, "source_note": "read-only · material master",
                         "sync_label": "materials updated", "sync_hint": ""},
            "synced": fields.Datetime.now().isoformat() if rows else None,
            "synced_age_h": 0.0,
            "workload": {"orders": len(rows), "blocked": 0, "ready": 0,
                         "progress": 0, "done": 0, "at_risk": 0, "late": 0},
            "workcenters": [],
            "ontime": None,
            "capabilities": {},
            "can_purchase": False,           # required by the BUY-badge branch
            "data_map": [{"domain": "Material master", "state": "live"}],
            "schedule": {"ok": False, "reason": "Materials are not scheduled."},
            "anchor_rule": "none — materials have no deadline.",
            "provenance": "Read-only material master. Density is estimation-grade (±15%).",
        }
```
> **Contract verified against `mrp_explorer.js` (agent, 2026-07-25):** the frontend keys every
> row on **`task_id`** (a row with only `id` is unselectable — silent broken UI); `timeline` and
> `schedule` must be **objects**, `provenance` a **string**, and **`can_purchase`** must be present
> for the BUY-badge branch. Context key `explorer_provider` and action tag `mrp_process_explorer`
> confirmed correct. Add a Task-10 test asserting `data["rows"][0]["task_id"]` exists.

- [ ] **Step 5: Add the client action** so the catalog opens with this provider

```xml
<!-- append to mrp_process_explorer/views/mrp_explorer_action.xml -->
<record id="action_material_explorer" model="ir.actions.client">
  <field name="name">Material Catalog</field>
  <field name="tag">mrp_process_explorer</field>
  <field name="context">{'explorer_provider': 'material.explorer'}</field>
</record>
<menuitem id="menu_material_explorer" name="Material Catalog"
          parent="mrp.menu_mrp_root" sequence="36" action="action_material_explorer"/>
```

- [ ] **Step 6: Run — both PASS.** Bump `mrp_process_explorer` manifest to `19.0.1.1.0` (minor: new provider, backward compatible).

- [ ] **Step 7: Commit on the branch**

```bash
git checkout -b feat/material-provider
git add mrp_process_explorer
git commit -m "feat(mrp_process_explorer): material.explorer provider (backcompat-preserved)"
```

---

## Task 11: Deploy to staging, soak, then production

**Files:** none (ops task; recipe from spec §9, §14.9).

- [ ] **Step 1:** Push `sb_material_core`, `sb_material_mrp` (Southbrook repo) and the `feat/material-provider` branch (odoo-addons). Open PRs.
- [ ] **Step 2: Staging install** on an isolated DB (per memory `southbrook_v19cr_local_test_recipe`):
```
odoo -d stage_sbmat -i mrp_process_explorer,sb_material_core,sb_material_mrp \
  --test-enable --test-tags sbk_material,mpx --stop-after-init
```
Expected: all tests PASS; both Explorer providers work.
- [ ] **Step 3: Backcompat soak** — open the existing **Process Explorer** on staging, confirm it still renders MOs (blindspot #9). Then open **Material Catalog**, confirm materials list + density detail.
- [ ] **Step 4: Production deploy** (single consolidated `-u` to avoid the ormcache wedge, spec §9 / memory `qnap_multi_deploy_worker_wedge`):
```
ssh qnap-tunnel
SD=/share/CACHEDEV3_DATA/.qpkg/container-station/bin/system-docker
# rsync modules to /mnt/extra-addons first, then:
$SD exec -i southbrook-odoo sh -c 'PW=...; odoo -c /etc/odoo/odoo.conf -d southbrook \
  -u mrp_process_explorer,sb_material_core,sb_material_mrp --stop-after-init --no-http'
$SD restart southbrook-odoo   # assets changed (new provider/menus) -> bump bundle hash
```
- [ ] **Step 5: Production smoke test** — confirm `ir_module_module.state='installed'` for all three; open a real Walnut Base 600 MO; verify **Material Summary** weight matches hand calc and cost shows a provenance badge. Hard-refresh the browser.
- [ ] **Step 6: Commit** any manifest version bumps; note results in `PUNCHLIST.md`.

---

## Open items resolved in this plan

- **§14.10 unit-conversion** → locked constant `kg = density_g_cm3 * volume_mm3 / 1e6`, HALF-UP 2dp (Task 6, Global Constraints).
- **§14.10 currency** → `currency_id` on the material manual price + `company_currency_id` on the MO totals, default company currency (Tasks 8–9).
- **§14.10 companion/assembly materials** → **deferred**: countertop/tile/drywall are buy-path; their companion lines (grout/thinset/mud/edge) attach as ordinary BoM components and price through the same cascade (Task 8) — no special model needed in Phase 1. Auto-derive of bought-surface area from the design is a **Phase-2 estimating-integration task** (logged, not built here). Phase 1 supports manual entry of those lines.
- **§12.1 volume basis** → `_compute_panel_dimensions()` (Task 6).
- **§12.2 cost rollup home** → implemented in `sb_material_mrp` (distinct field `material_cost_total`); does **not** hard-depend on `mrp_product_costing` (may be absent); no field collision.
- **§12.3 providers home** → in `mrp_process_explorer` (Task 10).

## Explicitly NOT in Phase 1 (later phases)
- `sb_material_stock` (weight-on-hand, valuation) — Phase 2.
- `sb_material_purchase` (reorder, lead time) — Phase 3.
- Sheet-goods **nesting** yield (Accucutt bridge) — Phase 4; Phase 1 uses the flat waste %.
- **AI Material Onboarding** (the AI button) — Phase 5.
- Auto-derive of bought-surface area from the design — Phase 2 estimating integration.
