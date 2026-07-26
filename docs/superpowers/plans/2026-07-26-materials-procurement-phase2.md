# Materials Phase-2 Procurement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Materials app compute, for every cabinet BoM line, how much of a continuous material (sheet/edgeband/area good) a manufacturing order actually consumes, and turn that into a transparent *suggested purchase quantity* (in the vendor's purchase unit, with waste and yield applied) that a buyer confirms — using Odoo's native procurement, no bespoke PO engine.

**Architecture:** Two new stored fields (`mrp.bom.line.material_demand_qty`, `product.supplierinfo.uom_yield_qty`) plus a computed `suggested_purchase_qty`/`suggested_purchase_uom_id` on the BoM line, all reusing the already-live geometry→volume pipeline (`_sb_component_share_volume_mm3`, `_compute_panel_dimensions`) and the existing material master (`weight_source`, `thickness_mm`, `waste_pct`, `material.family.default_waste_pct`, `base_uom_id`). Waste is a structural multiplier applied before a ceiling round-up; the whole thing is an assist layer surfaced in the UI — the actual RFQ/PO stays 100% native (`route=Buy` + native scheduler). This increment builds the *decision numbers*; auto-orderpoints and auto-confirm are deferred per the spec.

**Tech Stack:** Odoo 19.0 CE; Python; existing modules `sb_material_core` (material master), `sb_material_mrp` (BoM-line weight/procurement), `southbrook_estimating` (geometry). No new modules, no new dependencies.

## Global Constraints

- Odoo 19.0 Community Edition only. All three modules are LIVE in production — every change must be **additive / backward-compatible** (new fields default to 0/False; no existing field semantics change).
- **Honesty contract (verbatim from the live codebase):** any derived quantity returns **0.0, never a fabricated number**, when its inputs are genuinely absent (no geometry, no material, no yield). Mirror `_panel_volume_mm3`'s 0.0-when-`{}` behavior exactly.
- **Fork decisions (locked in the approved spec, do not revisit):** (1) **new field** `material_demand_qty` — leave the native BoM line `product_qty` untouched; (2) **ceiling round-up uniformly** across all families (never buy a fraction of a purchase unit); (3) **assist-only** — compute and display the suggested qty; never create or confirm a PO in code (reject any `_make_po_select_seller`-style override); (4) **net-new data entry** — `uom_yield_qty` and vendor `supplierinfo` are shop-entered, not derived.
- **Continuous families only.** `material_demand_qty` is computed for `weight_source in {"density_volume", "density_area", "linear_density"}`. For `"per_unit"` and `"none"`, `material_demand_qty == product_qty` (the native count model is already correct) and no suggestion waste/yield math is applied beyond a straight pass-through.
- **Reuse, do not duplicate.** Use `_sb_component_share_volume_mm3(line, _dims_cache)` for the carcass share (it already enforces the sibling-qty split + honesty). Use `material.family` / `southbrook.kitchen.material` fields as-is. No new geometry math.
- **Canonical demand units (intentional v1 decision, documented in field help):** `material_demand_qty` is expressed in **m²** for area families (`density_volume`, `density_area`), **linear m** for `linear_density`, and **units** for `per_unit`/`none`. `uom_yield_qty` must be entered in the *same* canonical unit per purchase unit (e.g. 2.97 m² per 4×8 ft sheet). Native `uom.uom` conversion into an arbitrary `base_uom_id`/`uom_po` is a documented Phase-2b follow-up — do not build it now (YAGNI).
- LGPL-3 SPDX header on every new Python file: `# SPDX-License-Identifier: LGPL-3.0-only`.
- Tests use Odoo's `TransactionCase`, tagged `sbk_material` and `sb_geo` (the existing tags for this suite). Run via `-u <module> --test-enable --test-tags sbk_material,sb_geo -d test_sbgeo_b1 --stop-after-init --no-http` in the `v19c-odoo` docker container (fresh `-i` is blocked by a pre-existing unrelated `groups.xml obj()` bug — always use `-u` on the already-installed `test_sbgeo_b1` DB). Copy addons to the mount first: `cp -R /Users/naadmin/southbrook-v19cr/addons/{sb_material_core,sb_material_mrp,southbrook_estimating,southbrook_kitchen_3d_configurator} /Users/naadmin/Downloads/Official/V19C/product-configurator/`.

---

## File Structure

- `addons/sb_material_core/models/product_supplierinfo.py` — **new**: `product.supplierinfo` extension holding `uom_yield_qty` (Task 1).
- `addons/sb_material_core/models/southbrook_kitchen_material.py` — **modify**: add `_effective_waste_pct()` helper on the material master (Task 2).
- `addons/sb_material_core/views/southbrook_kitchen_material_views.xml` — **modify**: (no change needed; waste fields already shown — verify only).
- `addons/sb_material_core/models/__init__.py` — **modify**: import the new `product_supplierinfo` file (Task 1).
- `addons/sb_material_mrp/models/mrp_bom.py` — **modify**: add `material_demand_qty` (Task 3) and `suggested_purchase_qty` / `suggested_purchase_uom_id` (Task 4) to `mrp.bom.line`, with helpers.
- `addons/sb_material_mrp/models/product_template.py` — **new**: `product.template` helper `action_sb_set_route_buy()` to tag material component products with the native Buy route (Task 5).
- `addons/sb_material_mrp/views/mrp_bom_views.xml` — **modify or new**: surface `material_demand_qty` + `suggested_purchase_qty` on the BoM line (Task 5).
- `addons/sb_material_core/views/product_supplierinfo_views.xml` — **new**: show `uom_yield_qty` on the vendor pricelist line (Task 1).
- Manifests + `README` of both modules — **modify**: version bumps + Phase-2 note (folded into the tasks that need them).
- Migrations `19.0.1.x.0/post-migrate.py` in each module whose stored fields need a one-time recompute (Tasks 3, 4).

---

## Task 1: `uom_yield_qty` on vendor pricelist (`product.supplierinfo`)

**Files:**
- Create: `addons/sb_material_core/models/product_supplierinfo.py`
- Create: `addons/sb_material_core/views/product_supplierinfo_views.xml`
- Modify: `addons/sb_material_core/models/__init__.py` (add `from . import product_supplierinfo`)
- Modify: `addons/sb_material_core/__manifest__.py` (add the new view to `data`; bump version `19.0.1.3.0` → `19.0.1.4.0`)
- Test: `addons/sb_material_core/tests/test_supplierinfo_yield.py`

**Interfaces:**
- Produces: `product.supplierinfo.uom_yield_qty` (Float, default 0.0) — "base-UoM quantity obtained from one purchase-UoM unit" (e.g. 2.97 m² per 4×8 ft sheet). Consumed by Task 4.

- [ ] **Step 1: Write the failing test**

```python
# addons/sb_material_core/tests/test_supplierinfo_yield.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestSupplierinfoYield(TransactionCase):
    def test_uom_yield_qty_field_defaults_zero_and_stores(self):
        vendor = self.env["res.partner"].create({"name": "Sheet Vendor"})
        product = self.env["product.product"].create({"name": "Melamine Sheet"})
        seller = self.env["product.supplierinfo"].create({
            "partner_id": vendor.id,
            "product_tmpl_id": product.product_tmpl_id.id,
        })
        self.assertEqual(seller.uom_yield_qty, 0.0)
        seller.uom_yield_qty = 2.97
        self.assertAlmostEqual(seller.uom_yield_qty, 2.97, places=2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec v19c-odoo odoo -u sb_material_core --test-enable --test-tags sbk_material,sb_geo -d test_sbgeo_b1 --stop-after-init --no-http --http-port=8220`
Expected: FAIL — `uom_yield_qty` is not a field on `product.supplierinfo`.

- [ ] **Step 3: Write minimal implementation**

```python
# addons/sb_material_core/models/product_supplierinfo.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields, models


class ProductSupplierinfo(models.Model):
    _inherit = "product.supplierinfo"

    uom_yield_qty = fields.Float(
        string="Yield per Purchase Unit",
        digits=(12, 4),
        default=0.0,
        help="How much material (in the material's canonical demand unit — "
             "m² for sheet/area goods, linear m for edgebanding) one purchase "
             "unit yields. Example: a 4'×8' sheet yields ~2.97 m². Used to "
             "convert consumption demand into a suggested purchase quantity. "
             "0 = not recorded (no suggestion produced).",
    )
```

Add to `addons/sb_material_core/models/__init__.py`:
```python
from . import product_supplierinfo
```

- [ ] **Step 4: Create the view**

```xml
<!-- addons/sb_material_core/views/product_supplierinfo_views.xml -->
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="product_supplierinfo_form_sb_yield" model="ir.ui.view">
        <field name="name">product.supplierinfo.form.sb.yield</field>
        <field name="model">product.supplierinfo</field>
        <field name="inherit_id" ref="product.product_supplierinfo_form_view"/>
        <field name="arch" type="xml">
            <field name="price" position="after">
                <field name="uom_yield_qty"/>
            </field>
        </field>
    </record>
</odoo>
```

Register it in `addons/sb_material_core/__manifest__.py` `data` list (after the existing views) and bump `"version"` to `19.0.1.4.0`.

- [ ] **Step 5: Run test to verify it passes**

Run: `docker exec v19c-odoo odoo -u sb_material_core --test-enable --test-tags sbk_material,sb_geo -d test_sbgeo_b1 --stop-after-init --no-http --http-port=8220`
Expected: PASS (0 failed, 0 error).

- [ ] **Step 6: Commit**

```bash
git add addons/sb_material_core/models/product_supplierinfo.py \
        addons/sb_material_core/views/product_supplierinfo_views.xml \
        addons/sb_material_core/models/__init__.py \
        addons/sb_material_core/__manifest__.py \
        addons/sb_material_core/tests/test_supplierinfo_yield.py
git commit -m "feat(sb_material_core): supplierinfo.uom_yield_qty for procurement (Phase-2 T1)"
```

---

## Task 2: Effective waste helper on the material master

**Files:**
- Modify: `addons/sb_material_core/models/southbrook_kitchen_material.py` (add method near the existing `_compute_effective_density`)
- Test: `addons/sb_material_core/tests/test_effective_waste.py`

**Interfaces:**
- Consumes: existing `southbrook.kitchen.material.waste_pct` (Float) and `material.family.default_waste_pct` (Float), and `family_id` (Many2one, may be a multi-level tree — walk to the first non-zero like `_compute_effective_density` does).
- Produces: `southbrook.kitchen.material._effective_waste_pct()` → Float percent (e.g. `12.0` for 12%). Material override wins; else nearest ancestor family `default_waste_pct`; else `0.0`. Consumed by Task 4.

- [ ] **Step 1: Write the failing test**

```python
# addons/sb_material_core/tests/test_effective_waste.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestEffectiveWaste(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Fam = self.env["material.family"]
        self.Mat = self.env["southbrook.kitchen.material"]

    def test_material_override_wins(self):
        fam = self.Fam.create({"name": "F", "code": "f_test", "default_waste_pct": 15.0})
        mat = self.Mat.create({"name": "M", "code": "m_ov", "family_id": fam.id, "waste_pct": 8.0})
        self.assertEqual(mat._effective_waste_pct(), 8.0)

    def test_falls_back_to_family_default(self):
        fam = self.Fam.create({"name": "F2", "code": "f_test2", "default_waste_pct": 12.0})
        mat = self.Mat.create({"name": "M2", "code": "m_fam", "family_id": fam.id})
        self.assertEqual(mat._effective_waste_pct(), 12.0)

    def test_walks_parent_family(self):
        parent = self.Fam.create({"name": "P", "code": "p_test", "default_waste_pct": 10.0})
        child = self.Fam.create({"name": "C", "code": "c_test", "parent_id": parent.id})
        mat = self.Mat.create({"name": "M3", "code": "m_walk", "family_id": child.id})
        self.assertEqual(mat._effective_waste_pct(), 10.0)

    def test_no_waste_anywhere_is_zero(self):
        fam = self.Fam.create({"name": "F3", "code": "f_none"})
        mat = self.Mat.create({"name": "M4", "code": "m_none", "family_id": fam.id})
        self.assertEqual(mat._effective_waste_pct(), 0.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec v19c-odoo odoo -u sb_material_core --test-enable --test-tags sbk_material,sb_geo -d test_sbgeo_b1 --stop-after-init --no-http --http-port=8221`
Expected: FAIL — `_effective_waste_pct` does not exist.

- [ ] **Step 3: Write minimal implementation**

Add to `addons/sb_material_core/models/southbrook_kitchen_material.py` inside `class KitchenMaterial`:

```python
    def _effective_waste_pct(self):
        """Structural waste percentage for this material (e.g. 12.0 == 12%).

        Material override (`waste_pct`) wins; else the nearest ancestor
        family's `default_waste_pct` (walk up `family_id.parent_id`); else
        0.0. Mirrors the fallback shape of `_compute_effective_density`.
        This is the STRUCTURAL waste (cutting/offcut loss) applied before
        the ceiling round-up in the purchase-qty suggestion — kept separate
        from the operational `mrp.production.scrap_factor`.
        """
        self.ensure_one()
        if self.waste_pct:
            return self.waste_pct
        fam = self.family_id
        while fam:
            if fam.default_waste_pct:
                return fam.default_waste_pct
            fam = fam.parent_id
        return 0.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec v19c-odoo odoo -u sb_material_core --test-enable --test-tags sbk_material,sb_geo -d test_sbgeo_b1 --stop-after-init --no-http --http-port=8221`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add addons/sb_material_core/models/southbrook_kitchen_material.py \
        addons/sb_material_core/tests/test_effective_waste.py
git commit -m "feat(sb_material_core): _effective_waste_pct material/family fallback (Phase-2 T2)"
```

---

## Task 3: `material_demand_qty` on the BoM line (consumption in canonical demand unit)

**Files:**
- Modify: `addons/sb_material_mrp/models/mrp_bom.py` (add field + compute on `class MrpBomLine`)
- Modify: `addons/sb_material_mrp/__manifest__.py` (bump `19.0.1.2.0` → `19.0.1.3.0`)
- Create: `addons/sb_material_mrp/migrations/19.0.1.3.0/post-migrate.py`
- Test: `addons/sb_material_mrp/tests/test_material_demand_qty.py`

**Interfaces:**
- Consumes: `_sb_component_share_volume_mm3(line, _dims_cache=None)` → Float mm³ (already live); `line.material_id` → `southbrook.kitchen.material` (may be empty); `material.weight_source`, `material.thickness_mm`; `_compute_panel_dimensions(**geo)["edge_banding_length_mm"]` for linear; `line.product_qty`.
- Produces: `mrp.bom.line.material_demand_qty` (Float, stored, digits (12,4)) — consumption in the canonical demand unit (m² area / linear m / units). Consumed by Task 4.

**Computation rule (exact):**
- `density_volume`, `density_area`: `area_m2 = share_volume_mm3 / effective_thickness_mm / 1_000_000.0`, where `effective_thickness_mm = material.thickness_mm if > 0 else 19.05` (¾" default, documented — the same cut-constant family the volume already used). Returns 0.0 when share volume is 0.0 (honesty).
- `linear_density`: resolve the cabinet geometry exactly as `_panel_volume_mm3` does (variant/line override → `geo`), then `length_m = _compute_panel_dimensions(**geo)["edge_banding_length_mm"] / 1000.0 * line.product_qty`; 0.0 when `geo` is `{}`.
- `per_unit`, `none`, or no `material_id`: `material_demand_qty = line.product_qty` (straight pass-through, count model already correct).

- [ ] **Step 1: Write the failing test**

```python
# addons/sb_material_mrp/tests/test_material_demand_qty.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestMaterialDemandQty(TransactionCase):
    def _make_cabinet_bom(self, weight_source, thickness_mm):
        fam = self.env["material.family"].create({"name": "EW", "code": "ew_dq"})
        mat = self.env["southbrook.kitchen.material"].create({
            "name": "Sheet", "code": "sheet_dq", "family_id": fam.id,
            "density": 0.68, "weight_source": weight_source,
            "thickness_mm": thickness_mm,
        })
        # a cabinet variant carrying real geometry
        tmpl = self.env["product.template"].create({"name": "Cab DQ"})
        variant = tmpl.product_variant_id
        variant.write({
            "sb_width_mm": 600, "sb_height_mm": 720, "sb_depth_mm": 580,
            "sb_panel_family": "base", "sb_door_count": 1, "sb_drawer_count": 0,
            "sb_finished_sides": "none",
        })
        comp = self.env["product.product"].create({"name": "Comp DQ"})
        comp.product_tmpl_id.material_id = mat.id
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": tmpl.id, "product_id": variant.id, "product_qty": 1.0,
        })
        line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": comp.id, "product_qty": 1.0,
        })
        return mat, line

    def test_density_volume_demand_is_area_m2(self):
        mat, line = self._make_cabinet_bom("density_volume", 19.05)
        # area = carcass volume / thickness / 1e6, and must be > 0
        self.assertGreater(line.material_demand_qty, 0.0)
        # thinner sheet, same geometry -> larger area for the same volume share
        mat2, line2 = self._make_cabinet_bom("density_volume", 12.70)
        self.assertGreater(line2.material_demand_qty, line.material_demand_qty)

    def test_per_unit_demand_equals_product_qty(self):
        fam = self.env["material.family"].create({"name": "HW", "code": "hw_dq"})
        mat = self.env["southbrook.kitchen.material"].create({
            "name": "Hinge", "code": "hinge_dq", "family_id": fam.id,
            "weight_source": "per_unit", "weight_per_unit": 0.05,
        })
        tmpl = self.env["product.template"].create({"name": "Cab HW"})
        comp = self.env["product.product"].create({"name": "Comp HW"})
        comp.product_tmpl_id.material_id = mat.id
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": tmpl.id, "product_id": tmpl.product_variant_id.id,
        })
        line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": comp.id, "product_qty": 4.0,
        })
        self.assertEqual(line.material_demand_qty, 4.0)

    def test_no_geometry_is_zero(self):
        mat, line = self._make_cabinet_bom("density_volume", 19.05)
        line.bom_id.product_id.write({"sb_width_mm": 0, "sb_height_mm": 0, "sb_depth_mm": 0})
        line.invalidate_recordset(["material_demand_qty"])
        # recompute
        line._compute_material_demand_qty()
        self.assertEqual(line.material_demand_qty, 0.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec v19c-odoo odoo -u sb_material_mrp --test-enable --test-tags sbk_material,sb_geo -d test_sbgeo_b1 --stop-after-init --no-http --http-port=8222`
Expected: FAIL — `material_demand_qty` not a field.

- [ ] **Step 3: Write minimal implementation**

Add to `class MrpBomLine` in `addons/sb_material_mrp/models/mrp_bom.py`. Field declaration (near `component_weight_kg`):

```python
    material_demand_qty = fields.Float(
        string="Material Demand",
        compute="_compute_material_demand_qty",
        store=True,
        digits=(12, 4),
        help="Consumption of this component per this BoM, in the material's "
             "canonical demand unit: m² for sheet/area goods (density_volume/"
             "density_area), linear m for edgebanding (linear_density), or "
             "units for hardware (per_unit/none). Continuous families reuse "
             "the geometry→volume pipeline; hardware passes product_qty "
             "through unchanged. 0.0 when geometry is genuinely absent "
             "(never fabricated). Drives the suggested purchase quantity — "
             "the native BoM product_qty is left untouched (Fork 1).",
    )

    _SB_DEFAULT_SHEET_THICKNESS_MM = 19.05  # 3/4" — documented fallback
```

Compute method (place after `_compute_component_weight`):

```python
    @api.depends(
        "product_id", "product_qty", "material_id",
        "material_id.weight_source", "material_id.thickness_mm",
        "sb_line_width_mm", "sb_line_height_mm", "sb_line_depth_mm",
        "bom_id.product_id.sb_width_mm",
        "bom_id.product_id.sb_height_mm",
        "bom_id.product_id.sb_depth_mm",
    )
    def _compute_material_demand_qty(self):
        Bom = self.env["mrp.bom"]
        has_geo = hasattr(Bom, "_compute_panel_dimensions")
        for line in self:
            mat = line.material_id
            src = mat.weight_source if mat else "none"
            if src in ("density_volume", "density_area"):
                vol = line._sb_component_share_volume_mm3(line)
                if not vol:
                    line.material_demand_qty = 0.0
                    continue
                th = mat.thickness_mm if mat.thickness_mm > 0 else \
                    line._SB_DEFAULT_SHEET_THICKNESS_MM
                line.material_demand_qty = vol / th / 1_000_000.0
            elif src == "linear_density":
                geo = line._sb_resolve_geo() if has_geo else {}
                if not geo:
                    line.material_demand_qty = 0.0
                    continue
                dims = Bom._compute_panel_dimensions(**geo)
                length_mm = dims.get("edge_banding_length_mm") or 0
                line.material_demand_qty = length_mm / 1000.0 * line.product_qty
            else:
                # per_unit / none / no material: native count model is correct
                line.material_demand_qty = line.product_qty
```

Add a small geometry-resolution helper `_sb_resolve_geo` (extracted from the exact logic already inside `_panel_volume_mm3` so the two never drift). Place it just above `_panel_volume_mm3` and have `_panel_volume_mm3` call it:

```python
    def _sb_resolve_geo(self):
        """Resolve the cabinet geometry dict for this line: per-line override
        (all three sb_line_* set) merged over the cabinet variant geometry,
        else the variant geometry, else {} (honesty). Single source of truth
        shared by _panel_volume_mm3 and _compute_material_demand_qty."""
        self.ensure_one()
        cab = self.bom_id.product_id or self.bom_id.product_tmpl_id.product_variant_id
        base_geo = cab._sb_geometry_inputs() if hasattr(cab, "_sb_geometry_inputs") else {}
        if self.sb_line_width_mm and self.sb_line_height_mm and self.sb_line_depth_mm:
            return {
                **base_geo,
                "width_mm": self.sb_line_width_mm,
                "height_mm": self.sb_line_height_mm,
                "depth_mm": self.sb_line_depth_mm,
            }
        return base_geo
```

Then in `_panel_volume_mm3`, REPLACE the inline `cab = ... ; base_geo = ... ; line_geo = ... ; geo = line_geo or base_geo` block with `geo = line._sb_resolve_geo()` (keeping the `if not geo: return 0.0` and everything after identical). This is a pure refactor — the existing `_panel_volume_mm3` tests are the regression gate and must pass unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec v19c-odoo odoo -u sb_material_mrp --test-enable --test-tags sbk_material,sb_geo -d test_sbgeo_b1 --stop-after-init --no-http --http-port=8222`
Expected: PASS, including ALL pre-existing `_panel_volume_mm3` tests (regression gate for the refactor).

- [ ] **Step 5: Add the recompute migration**

```python
# addons/sb_material_mrp/migrations/19.0.1.3.0/post-migrate.py
# SPDX-License-Identifier: LGPL-3.0-only
"""19.0.1.3.0 — populate the new stored material_demand_qty on existing
BoM lines (idempotent: recomputing a stored compute is always safe)."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    lines = env["mrp.bom.line"].search([])
    if not lines:
        return
    env.add_to_compute(lines._fields["material_demand_qty"], lines)
    lines.flush_recordset(["material_demand_qty"])
    _logger.info(
        "sb_material_mrp 19.0.1.3.0: recomputed material_demand_qty on %s "
        "bom line(s) (from %s).", len(lines), version,
    )
```

Bump `addons/sb_material_mrp/__manifest__.py` `"version"` to `19.0.1.3.0`.

- [ ] **Step 6: Commit**

```bash
git add addons/sb_material_mrp/models/mrp_bom.py \
        addons/sb_material_mrp/migrations/19.0.1.3.0/post-migrate.py \
        addons/sb_material_mrp/__manifest__.py \
        addons/sb_material_mrp/tests/test_material_demand_qty.py
git commit -m "feat(sb_material_mrp): material_demand_qty consumption per BoM line (Phase-2 T3)"
```

---

## Task 4: `suggested_purchase_qty` — the assist number

**Files:**
- Modify: `addons/sb_material_mrp/models/mrp_bom.py` (add two fields + compute on `class MrpBomLine`)
- Modify: `addons/sb_material_mrp/__manifest__.py` (bump `19.0.1.3.0` → `19.0.1.4.0`)
- Create: `addons/sb_material_mrp/migrations/19.0.1.4.0/post-migrate.py`
- Test: `addons/sb_material_mrp/tests/test_suggested_purchase_qty.py`

**Interfaces:**
- Consumes: `material_demand_qty` (Task 3); `material._effective_waste_pct()` (Task 2); `product.supplierinfo.uom_yield_qty` (Task 1) via `line.product_id._select_seller()`; `product_id.uom_po_id` (native purchase UoM).
- Produces: `mrp.bom.line.suggested_purchase_qty` (Float, stored) and `suggested_purchase_uom_id` (Many2one `uom.uom`, stored, related-free — set to the seller's `product_uom` / `product_id.uom_po_id`). Consumed by Task 5 (UI).

**Formula (exact, Fork 2 = ceiling round-up uniformly):**
`suggested_purchase_qty = ceil( material_demand_qty * (1 + effective_waste_pct/100) / uom_yield_qty )`, using `math.ceil`. Returns 0.0 when `material_demand_qty == 0` OR `uom_yield_qty == 0` OR no seller (honesty — no yield data → no suggestion). For `per_unit`/`none` with no `uom_yield_qty`, also 0.0 (hardware suggestion is out of scope this increment; the native count still flows through `product_qty`).

- [ ] **Step 1: Write the failing test**

```python
# addons/sb_material_mrp/tests/test_suggested_purchase_qty.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestSuggestedPurchaseQty(TransactionCase):
    def _setup(self, demand, waste_pct, yield_qty):
        fam = self.env["material.family"].create({
            "name": "EW", "code": "ew_sp", "default_waste_pct": waste_pct})
        mat = self.env["southbrook.kitchen.material"].create({
            "name": "Sheet", "code": "sheet_sp", "family_id": fam.id,
            "density": 0.68, "weight_source": "density_volume", "thickness_mm": 19.05})
        vendor = self.env["res.partner"].create({"name": "V"})
        comp = self.env["product.product"].create({"name": "Comp SP", "purchase_method": "purchase"})
        comp.product_tmpl_id.material_id = mat.id
        self.env["product.supplierinfo"].create({
            "partner_id": vendor.id, "product_tmpl_id": comp.product_tmpl_id.id,
            "price": 40.0, "uom_yield_qty": yield_qty})
        tmpl = self.env["product.template"].create({"name": "Cab SP"})
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": tmpl.id, "product_id": tmpl.product_variant_id.id})
        line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": comp.id, "product_qty": 1.0})
        # force a known demand independent of geometry for a deterministic assertion
        line.material_demand_qty = demand
        line._compute_suggested_purchase_qty()
        return line

    def test_ceiling_with_waste(self):
        # demand 5.0 m², 12% waste => 5.6; yield 2.97 m²/sheet => 1.885 => ceil 2
        line = self._setup(demand=5.0, waste_pct=12.0, yield_qty=2.97)
        self.assertEqual(line.suggested_purchase_qty, 2.0)

    def test_no_yield_no_suggestion(self):
        line = self._setup(demand=5.0, waste_pct=12.0, yield_qty=0.0)
        self.assertEqual(line.suggested_purchase_qty, 0.0)

    def test_zero_demand_no_suggestion(self):
        line = self._setup(demand=0.0, waste_pct=12.0, yield_qty=2.97)
        self.assertEqual(line.suggested_purchase_qty, 0.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec v19c-odoo odoo -u sb_material_mrp --test-enable --test-tags sbk_material,sb_geo -d test_sbgeo_b1 --stop-after-init --no-http --http-port=8223`
Expected: FAIL — `suggested_purchase_qty` not a field.

- [ ] **Step 3: Write minimal implementation**

Add `import math` at the top of `mrp_bom.py` if not present. Add fields to `class MrpBomLine`:

```python
    suggested_purchase_qty = fields.Float(
        string="Suggested Order Qty",
        compute="_compute_suggested_purchase_qty",
        store=True,
        digits=(12, 2),
        help="Assist-only: CEIL(demand × (1 + waste%) ÷ yield-per-unit) in "
             "the vendor's purchase unit. Transparent suggestion a buyer "
             "confirms — this NEVER creates or confirms a PO. 0 when demand, "
             "yield, or a vendor is missing (no fabricated suggestion).",
    )
    suggested_purchase_uom_id = fields.Many2one(
        "uom.uom", string="Suggested Order UoM",
        compute="_compute_suggested_purchase_qty", store=True,
    )

    @api.depends(
        "material_demand_qty", "material_id",
        "material_id.waste_pct", "material_id.family_id",
        "product_id",
    )
    def _compute_suggested_purchase_qty(self):
        for line in self:
            line.suggested_purchase_qty = 0.0
            line.suggested_purchase_uom_id = False
            mat = line.material_id
            demand = line.material_demand_qty
            if not mat or demand <= 0.0:
                continue
            seller = line.product_id._select_seller() if line.product_id else False
            yield_qty = seller.uom_yield_qty if seller else 0.0
            if not seller or yield_qty <= 0.0:
                continue
            waste = mat._effective_waste_pct()
            gross = demand * (1.0 + waste / 100.0)
            line.suggested_purchase_qty = float(math.ceil(gross / yield_qty))
            line.suggested_purchase_uom_id = (
                seller.product_uom or line.product_id.uom_po_id
            ).id
```

> Note: `product.supplierinfo` in v19 exposes the purchase UoM as `product_uom` — if that attribute is absent on this build, fall back to `line.product_id.uom_po_id` only. The reviewer should confirm the field name against the installed core; keep the `or line.product_id.uom_po_id` fallback regardless.

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec v19c-odoo odoo -u sb_material_mrp --test-enable --test-tags sbk_material,sb_geo -d test_sbgeo_b1 --stop-after-init --no-http --http-port=8223`
Expected: PASS.

- [ ] **Step 5: Add the recompute migration + version bump**

```python
# addons/sb_material_mrp/migrations/19.0.1.4.0/post-migrate.py
# SPDX-License-Identifier: LGPL-3.0-only
"""19.0.1.4.0 — populate suggested_purchase_qty/_uom on existing lines."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    lines = env["mrp.bom.line"].search([])
    if not lines:
        return
    env.add_to_compute(lines._fields["suggested_purchase_qty"], lines)
    env.add_to_compute(lines._fields["suggested_purchase_uom_id"], lines)
    lines.flush_recordset(["suggested_purchase_qty", "suggested_purchase_uom_id"])
    _logger.info(
        "sb_material_mrp 19.0.1.4.0: recomputed suggested_purchase_qty on %s "
        "line(s) (from %s).", len(lines), version,
    )
```

Bump `addons/sb_material_mrp/__manifest__.py` `"version"` to `19.0.1.4.0`.

- [ ] **Step 6: Commit**

```bash
git add addons/sb_material_mrp/models/mrp_bom.py \
        addons/sb_material_mrp/migrations/19.0.1.4.0/post-migrate.py \
        addons/sb_material_mrp/__manifest__.py \
        addons/sb_material_mrp/tests/test_suggested_purchase_qty.py
git commit -m "feat(sb_material_mrp): suggested_purchase_qty assist (ceil, waste, yield) (Phase-2 T4)"
```

---

## Task 5: Surface the assist + a Buy-route helper

**Files:**
- Create: `addons/sb_material_mrp/models/product_template.py` (route helper)
- Modify: `addons/sb_material_mrp/models/__init__.py` (import it)
- Modify (or create): `addons/sb_material_mrp/views/mrp_bom_views.xml` (show the two new fields on the BoM line tree)
- Create: `addons/sb_material_mrp/views/product_template_views.xml` (button for the route helper)
- Modify: `addons/sb_material_mrp/__manifest__.py` (register views; bump `19.0.1.4.0` → `19.0.1.5.0`)
- Test: `addons/sb_material_mrp/tests/test_route_buy_helper.py`

**Interfaces:**
- Consumes: `material_demand_qty`, `suggested_purchase_qty`, `suggested_purchase_uom_id` (Tasks 3–4); the native `stock.route` with `xml_id` `stock.route_warehouse0_buy` (the standard Buy route).
- Produces: `product.template.action_sb_set_route_buy()` — adds the Buy route to `self` (idempotent; only material-linked products). Returns a notification action.

- [ ] **Step 1: Write the failing test**

```python
# addons/sb_material_mrp/tests/test_route_buy_helper.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestRouteBuyHelper(TransactionCase):
    def test_adds_buy_route_idempotently(self):
        buy = self.env.ref("stock.route_warehouse0_buy")
        tmpl = self.env["product.template"].create({"name": "Sheet Buy", "type": "consu"})
        tmpl.action_sb_set_route_buy()
        self.assertIn(buy.id, tmpl.route_ids.ids)
        # idempotent
        tmpl.action_sb_set_route_buy()
        self.assertEqual(tmpl.route_ids.ids.count(buy.id), 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec v19c-odoo odoo -u sb_material_mrp --test-enable --test-tags sbk_material,sb_geo -d test_sbgeo_b1 --stop-after-init --no-http --http-port=8224`
Expected: FAIL — `action_sb_set_route_buy` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
# addons/sb_material_mrp/models/product_template.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo import _, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def action_sb_set_route_buy(self):
        """Add the native Buy route to these products so the native
        scheduler can procure them (assist-only: this configures native
        procurement, it does NOT create POs). Idempotent."""
        buy = self.env.ref("stock.route_warehouse0_buy", raise_if_not_found=False)
        if not buy:
            return False
        for tmpl in self:
            if buy.id not in tmpl.route_ids.ids:
                tmpl.route_ids = [(4, buy.id)]
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "message": _("Buy route set on %s product(s).", len(self)),
                "sticky": False,
            },
        }
```

Add `from . import product_template` to `addons/sb_material_mrp/models/__init__.py`.

- [ ] **Step 4: Add the views**

BoM-line fields — inherit the native BoM form's `bom_line_ids` tree (`mrp.mrp_bom_form_view`):

```xml
<!-- addons/sb_material_mrp/views/mrp_bom_views.xml -->
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="mrp_bom_form_sb_procurement" model="ir.ui.view">
        <field name="name">mrp.bom.form.sb.procurement</field>
        <field name="model">mrp.bom</field>
        <field name="inherit_id" ref="mrp.mrp_bom_form_view"/>
        <field name="arch" type="xml">
            <xpath expr="//field[@name='bom_line_ids']/list/field[@name='product_qty']" position="after">
                <field name="material_demand_qty" optional="show"/>
                <field name="suggested_purchase_qty" optional="show"/>
                <field name="suggested_purchase_uom_id" optional="hide"/>
            </xpath>
        </field>
    </record>
</odoo>
```

Route-helper button on the product form:

```xml
<!-- addons/sb_material_mrp/views/product_template_views.xml -->
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="product_template_form_sb_route_buy" model="ir.ui.view">
        <field name="name">product.template.form.sb.route.buy</field>
        <field name="model">product.template</field>
        <field name="inherit_id" ref="product.product_template_form_view"/>
        <field name="arch" type="xml">
            <xpath expr="//div[@name='button_box']" position="inside">
                <button name="action_sb_set_route_buy" type="object"
                        class="oe_stat_button" icon="fa-shopping-cart"
                        invisible="not material_id">
                    <div class="o_stat_info">
                        <span class="o_stat_text">Set Buy Route</span>
                    </div>
                </button>
            </xpath>
        </field>
    </record>
</odoo>
```

> Note: the button uses `material_id` (the Wave-3 `product.template.material_id`) for `invisible` so it only shows on material-linked products. If the BoM-line tree xpath fails against the installed `mrp` view (element name/path differs on this build), the reviewer/implementer should adjust the xpath to the actual `bom_line_ids` list — the two `<field>` additions are the deliverable, not the exact xpath string.

Register both views in `addons/sb_material_mrp/__manifest__.py` `data` and add `"stock"`/`"purchase"` to `depends` only if not already present (`purchase` already is; `stock` comes transitively via `mrp` — confirm). Bump `"version"` to `19.0.1.5.0`.

- [ ] **Step 5: Run test to verify it passes**

Run: `docker exec v19c-odoo odoo -u sb_material_mrp --test-enable --test-tags sbk_material,sb_geo -d test_sbgeo_b1 --stop-after-init --no-http --http-port=8224`
Expected: PASS, and the module loads with the new views (no ParseError).

- [ ] **Step 6: Commit**

```bash
git add addons/sb_material_mrp/models/product_template.py \
        addons/sb_material_mrp/models/__init__.py \
        addons/sb_material_mrp/views/mrp_bom_views.xml \
        addons/sb_material_mrp/views/product_template_views.xml \
        addons/sb_material_mrp/__manifest__.py \
        addons/sb_material_mrp/tests/test_route_buy_helper.py
git commit -m "feat(sb_material_mrp): surface demand+suggested-qty, Buy-route helper (Phase-2 T5)"
```

---

## Task 6: READMEs + Phase-2 doc note

**Files:**
- Modify: `addons/sb_material_mrp/README.md` (or create a short one if absent) — document the procurement-assist fields + the "assist-only, native procurement" boundary.
- Modify: `docs/superpowers/specs/2026-07-25-materials-procurement-phase2-design.md` — append a "Delivered (Phase-2a)" note listing what shipped vs. what stays deferred (orderpoint automation, auto-confirm, uom.uom conversion, variance reconciliation).

- [ ] **Step 1: Write the README section**

Add a "Procurement assist (Phase-2)" section to `addons/sb_material_mrp/README.md` describing: `material_demand_qty` (canonical units), `uom_yield_qty` (net-new vendor data), `suggested_purchase_qty` (ceil + waste + yield, assist-only), the `Set Buy Route` button, and the explicit boundary "this module computes decision numbers and configures native procurement; it never creates or confirms a PO."

- [ ] **Step 2: Append the spec delivery note**

Append to the spec file a short section: **Delivered (Phase-2a, 2026-07-26):** T1 uom_yield_qty, T2 effective waste, T3 material_demand_qty, T4 suggested_purchase_qty, T5 UI + Buy-route helper. **Still deferred:** orderpoint min/max automation, native scheduler end-to-end RFQ, auto-confirm-below-threshold, `uom.uom` conversion into arbitrary purchase UoMs, actual-vs-estimate variance reconciliation.

- [ ] **Step 3: Commit**

```bash
git add addons/sb_material_mrp/README.md \
        docs/superpowers/specs/2026-07-25-materials-procurement-phase2-design.md
git commit -m "docs(materials): Phase-2a procurement assist — README + spec delivery note"
```

---

## Self-Review

**1. Spec coverage:**
- `material_demand_qty` new field, continuous families, reuses geometry pipeline, leaves product_qty untouched (Fork 1) → **Task 3** ✓
- `uom_yield_qty` on supplierinfo, net-new data (Fork 4) → **Task 1** ✓
- Purchase qty = CEIL(demand × (1+waste) / yield), ceiling uniformly (Fork 2) → **Task 4** ✓
- Waste wiring: `waste_pct` / `default_waste_pct`, structural, separate from scrap_factor → **Task 2** + used in Task 4 ✓
- Assist-only, transparent on the line, no PO code (Fork 3) → **Tasks 4–5** ✓ (computed + displayed; zero PO creation)
- `route=Buy` native config → **Task 5** helper ✓
- No new models (2 fields + 1 supplierinfo field + helpers) → ✓
- Deferred (orderpoint automation, auto-confirm, variance, uom conversion) → documented in Task 6, not built ✓

**2. Placeholder scan:** No TBD/TODO; every code step shows complete code. The two xpath "adjust if the installed view differs" notes are explicit reviewer instructions with a concrete fallback (the field additions), not placeholders.

**3. Type consistency:** `material_demand_qty` (Float) produced in T3, consumed in T4; `uom_yield_qty` (Float) produced T1, consumed T4 via `_select_seller().uom_yield_qty`; `_effective_waste_pct()` returns percent Float, T4 divides by 100; `_sb_resolve_geo()` introduced in T3 and reused by `_panel_volume_mm3` (refactor, regression-gated). `suggested_purchase_qty`/`suggested_purchase_uom_id` produced T4, displayed T5. Consistent.
