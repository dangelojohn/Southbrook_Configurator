# Materials Phase-2b Procurement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> ## ⚠️ Architecture limitation — read before touching any task below
>
> **Fork-1 (locked in the Phase-2 spec, unchanged here) left the native BoM
> line `product_qty` untouched.** `product_configurator_mrp/models/
> product_config.py` still writes `bom_line_vals = {'product_id': ...,
> 'product_qty': 1}` for every attribute-linked component. That means:
>
> - The demand signal that **TRIGGERS** the native scheduler/reordering
>   pipeline — a manufacturing order's raw-material `stock.move` reserving
>   against on-hand stock, and `stock.warehouse.orderpoint.product_min_qty`
>   comparing forecast to that reservation — is still the **size-blind
>   native `product_qty`** (1 sheet "reserved" per cabinet, regardless of
>   whether the cabinet is 9″ or 96″ wide).
> - `material_demand_qty` (Phase-2a) — the honest, geometry-aware
>   consumption number — reaches only **two** places in this increment:
>   the orderpoint **MAX** (Task 2, "how much to replenish up to") and the
>   **PO-line assist note** (Task 4, "here's what the open MOs actually
>   need"). It never becomes the trigger.
> - Net effect: the native scheduler will fire (or not fire) based on the
>   size-blind qty=1 signal; when it fires, Task 2's MAX and Task 4's note
>   make the *resulting* RFQ size-aware and transparent, but a shop relying
>   solely on "did the scheduler generate an RFQ yet?" as its signal for
>   "do we have enough material coming" is still working off the size-blind
>   number. **This split-brain is a known, documented limitation carried
>   forward from Phase-2a, not something this increment closes.** A future,
>   deliberately-scoped pass to make the trigger itself size-aware (e.g. by
>   writing `material_demand_qty` back onto the raw-material move's
>   `product_uom_qty` post-confirm) is out of scope here and would need its
>   own fork decision (it changes what Manufacturing screens show — Fork-1
>   was an explicit choice not to do that).

**Goal:** Turn the demand/waste/yield math Phase-2a built
(`material_demand_qty`, `_effective_waste_pct()`, `suggested_purchase_qty`)
into an end-to-end, buyer-visible procurement loop on Odoo's **native**
scheduler and RFQ pipeline: convert canonical demand into an arbitrary
vendor UoM when a real unit conversion exists, maintain native
`stock.warehouse.orderpoint` MAX values from open-MO demand, prove the
native scheduler drafts an RFQ off that config, surface the material-aware
suggestion directly on the native PO line, and — gated, default-off, and
logged — optionally auto-confirm a draft RFQ under a value threshold. Zero
bespoke PO-creation code anywhere except the one explicitly-permitted
auto-confirm call site.

**Architecture:** Five additive increments, each reusing what already
exists rather than building a parallel engine:

1. A native `uom.uom` conversion helper (`sb_convert_demand_qty`) for the
   case Phase-2a's `uom_yield_qty` doesn't cover — a vendor selling in a
   *dimensionally compatible* unit (ft² instead of m², feet instead of
   metres) rather than a discrete pack (a "sheet").
2. A rollup helper (`product.template._sb_open_mo_material_demand_qty`)
   that sums `material_demand_qty` across currently open MOs, and an
   idempotent action that writes only `stock.warehouse.orderpoint.
   product_max_qty` from it — never `product_min_qty` (that stays a human/
   native decision; see the limitation above).
3. A test-only proof that native `stock.rule.run_scheduler()` + a Buy-route
   product + an orderpoint produces a draft `purchase.order` with **zero**
   Southbrook PO-creation code in the path.
4. A read-only, non-stored assist column + a "Materials" tab on the native
   `purchase.order.line`, reusing Task 1's converter and Task 2's rollup —
   never written back to `product_qty`, never confirms anything.
5. A double-gated, default-OFF `res.company` toggle + amount ceiling that
   lets `stock.rule._run_buy` (native, unmodified in this override) call
   `purchase.order.button_confirm()` **once**, only after the native code
   has already created/updated the PO — the sole permitted confirm site.

**Tech Stack:** Odoo 19.0 CE; Python; existing modules `sb_material_core`
(material master + UoM helper), `sb_material_mrp` (BoM-line demand,
orderpoint sync, PO-line assist, auto-confirm gate). No new modules, no new
Python dependencies.

## Global Constraints

- Odoo 19.0 Community Edition only. Both modules are **LIVE** — every
  change additive/backward-compatible; new fields default to 0/False/empty;
  no existing field semantics change.
- **Honesty contract (unchanged from Phase-2a):** any derived quantity or
  note is 0.0 / `""` / `is_exact=False`, never fabricated, when its inputs
  are genuinely absent (no material, no open-MO demand, no shared UoM
  reference, no vendor yield).
- **Native procurement only.** Zero PO-creation code — no
  `_make_po_select_seller`-style override, no direct
  `purchase.order.create()` anywhere in these modules. The **one** explicit
  exception is Task 5's `button_confirm()` call, which runs strictly after
  `super()._run_buy()` has already done all PO creation/selection/pricing
  natively — Task 5 never writes `product_id`/`product_qty`/`price_unit`/
  `partner_id`.
- **Assist-only / zero-PO-creation-code except Task 5's explicitly-gated
  auto-confirm** — every other new field/method in this plan is read-only
  transparency or native-config assistance a human still acts on.
- **v19 field facts, grep-verified against the installed core**
  (`/Users/naadmin/Downloads/Official/V19C/odoo`):
  - `uom.uom` has **no `category`/`category_id` model in v19.** Units relate
    via `relative_uom_id` (a `_parent_store` tree); `_has_common_reference`
    walks `parent_path` to check two units share a root; `_compute_quantity`
    itself does **not** gate on category — it blindly multiplies by
    `factor` ratios, so callers MUST check `_has_common_reference` first or
    risk a silently nonsensical conversion. (`addons/uom/models/uom_uom.py`)
  - `uom` ships real reference trees usable for this plan: `m²`
    (`uom.product_uom_square_meter`) with `ft²`
    (`uom.product_uom_square_foot`) as a related unit; `m`
    (`uom.product_uom_meter`) with `ft`/`yd`/`in` related; `kg`
    (`uom.product_uom_kgm`) with `lb`/`oz`/`ton`; `Units`
    (`uom.product_uom_unit`) with `dozen`/`pack_6`.
    (`addons/uom/data/uom_data.xml`)
  - `stock.warehouse.orderpoint`: `product_min_qty`/`product_max_qty` are
    plain `Float` in the product's own UoM (`product_uom` is a *related*
    field, `product_id.uom_id` — read-only); unique constraint on
    `(product_id, location_id, company_id)`; `trigger` defaults `'auto'`;
    the scheduler's trigger check is `qty_forecast < product_min_qty`
    (strict, `float_compare`) — `product_min_qty=0.0` with zero on-hand and
    zero reservation will **not** fire. (`addons/stock/models/
    stock_orderpoint.py`)
  - The native scheduler entry point in this v19 core is **`stock.rule.
    run_scheduler(use_new_cursor=False, company_id=False)`** —
    `stock.rule` (`_name = "stock.rule"`), **not** a separate
    `procurement.group` model. It calls `_run_scheduler_tasks`, which
    searches `trigger='auto'` orderpoints and calls
    `_procure_orderpoint_confirm()`. (`addons/stock/models/stock_rule.py`)
  - `purchase_stock.stock_rule._run_buy(procurements)` resolves a seller via
    `rule._get_matching_supplier(product_id, product_qty, product_uom,
    company_id, values)`, builds a PO-identity domain via
    `rule._make_po_get_domain(company_id, values, partner)`, and only then
    creates/updates the `purchase.order`/`purchase.order.line`. Both helper
    methods are reused (never re-implemented) by Task 5.
    (`addons/purchase_stock/models/stock_rule.py`)
  - `product.supplierinfo.product_uom_id` (v19 field name, confirmed in
    Phase-2a) is the vendor's purchase UoM; `product.template/product.uom_id`
    is the single native UoM field (`uom_po_id` was removed).
  - `route_warehouse0_buy` lives in `purchase_stock`, not `stock` — the
    correct external id is **`purchase_stock.route_warehouse0_buy`**
    (already used by the live `action_sb_set_route_buy`).
  - `mrp.production.state` "open" values are `confirmed`, `progress`,
    `to_close` (`draft`/`done`/`cancel` are not open). (`addons/mrp/models/
    mrp_production.py`)
- LGPL-3 SPDX header on every new Python file.
- Tests use `TransactionCase`, tagged `sbk_material` and `sb_geo`. Run via
  `-u <module> --test-enable --test-tags sbk_material,sb_geo -d
  test_sbgeo_b1 --stop-after-init --no-http --http-port=82XX` in the
  `v19c-odoo` docker container, after `cp -R addons/{sb_material_core,
  sb_material_mrp,southbrook_estimating,southbrook_kitchen_3d_configurator}
  /Users/naadmin/Downloads/Official/V19C/product-configurator/`. **A new
  test file MUST be imported in the module's `tests/__init__.py`** — grep
  the run log to confirm the class actually ran (established trap from the
  cutlist-precision plan; both `sb_material_core/tests/__init__.py` and
  `sb_material_mrp/tests/__init__.py` currently list every file
  explicitly, no auto-discovery).
- Current live versions at branch tip: `sb_material_core` 19.0.1.7.0,
  `sb_material_mrp` 19.0.1.7.0.
- **Live-data dependency flag** (every task is testable with synthetic data
  in the test suite regardless):
  - Task 1 (UoM helper) — useful immediately for materials whose vendor
    sells in a *dimensionally compatible* unit (ft², ft, lb); **not** useful
    for the common sheet-goods case (a "Sheet" pack unit shares no
    reference with m² — that's `uom_yield_qty`'s job, Task 4's primary
    path).
  - Task 2 (orderpoint sync) — useful immediately; MAX is derived purely
    from `material_demand_qty`, already live since Phase-2a.
  - Task 3 (scheduler proof) — needs *a* `product.supplierinfo` row to
    exist (any price/min_qty) for `_get_matching_supplier` to resolve, but
    **not** `uom_yield_qty` specifically.
  - Task 4 (PO-line note) — **most dependent on live data to be useful**:
    without a real `uom_yield_qty` on the vendor's `product.supplierinfo`,
    the note is honestly "no vendor yield recorded" — true, but not
    actionable for a buyer.
  - Task 5 (auto-confirm) — useful/safe only once vendor **pricing** is
    trustworthy (an ops-accuracy concern, not a materials-data one); the
    zero-default threshold keeps it inert either way.

## File Structure

- `addons/sb_material_core/models/uom_uom.py` — **new**: `uom.uom`
  extension, `sb_convert_demand_qty()` (Task 1).
- `addons/sb_material_core/models/southbrook_kitchen_material.py` —
  **modify**: add `_sb_canonical_demand_uom()` next to
  `_effective_waste_pct()` (Task 1).
- `addons/sb_material_core/models/__init__.py` — **modify**: import
  `uom_uom` (Task 1).
- `addons/sb_material_core/__manifest__.py` — **modify**: version bumps.
- `addons/sb_material_mrp/models/mrp_bom.py` — **modify**: add
  `_sb_demand_qty_in_uom()` on `mrp.bom.line` (Task 1).
- `addons/sb_material_mrp/models/product_template.py` — **modify**: add
  `_sb_open_mo_material_demand_qty()` + `action_sb_sync_orderpoint_max()`
  (Task 2).
- `addons/sb_material_mrp/views/product_template_views.xml` — **modify**:
  sync button (Task 2).
- `addons/sb_material_mrp/models/purchase_order_line.py` — **new**:
  `purchase.order.line` extension, the assist note (Task 4).
- `addons/sb_material_mrp/views/purchase_order_views.xml` — **new**:
  list column + Materials tab (Task 4).
- `addons/sb_material_mrp/models/stock_rule.py` — **new**: `stock.rule`
  extension, the gated auto-confirm (Task 5).
- `addons/sb_material_mrp/models/res_company.py` — **new**: the two
  threshold fields (Task 5).
- `addons/sb_material_mrp/models/res_config_settings.py` — **new**: related
  Settings-page fields (Task 5).
- `addons/sb_material_mrp/views/res_config_settings_views.xml` — **new**:
  Settings UI (Task 5).
- `addons/sb_material_mrp/models/__init__.py` — **modify**: imports for
  Tasks 4/5.
- `addons/sb_material_mrp/__manifest__.py` — **modify**: version bumps +
  new view registrations.
- Test files under each module's `tests/`, each added to that module's
  `tests/__init__.py`.

---

## Task 1: UoM conversion helper — canonical demand into an arbitrary UoM

**Files:**
- Create: `addons/sb_material_core/models/uom_uom.py`
- Modify: `addons/sb_material_core/models/southbrook_kitchen_material.py`
- Modify: `addons/sb_material_core/models/__init__.py`
- Modify: `addons/sb_material_core/__manifest__.py` (bump `19.0.1.7.0` →
  `19.0.1.8.0`)
- Create: `addons/sb_material_core/tests/test_uom_conversion.py`
- Modify: `addons/sb_material_core/tests/__init__.py`
- Modify: `addons/sb_material_mrp/models/mrp_bom.py`
- Modify: `addons/sb_material_mrp/__manifest__.py` (bump `19.0.1.7.0` →
  `19.0.1.8.0`)
- Create: `addons/sb_material_mrp/tests/test_demand_qty_uom_conversion.py`
- Modify: `addons/sb_material_mrp/tests/__init__.py`

**Interfaces:**
- Produces: `uom.uom.sb_convert_demand_qty(self, qty, to_uom) -> (float,
  bool)` — `self` is the source UoM. Returns `(converted_qty, True)` when a
  real native conversion applied (same unit, or `_has_common_reference` is
  true); `(qty, False)` — **unchanged input, never fabricated** — when
  `to_uom` is falsy or the two units share no reference.
- Produces: `southbrook.kitchen.material._sb_canonical_demand_uom(self) ->
  uom.uom recordset (0 or 1)` — resolves the material's canonical demand
  unit from `weight_source`: `density_volume`/`density_area` → m²
  (`uom.product_uom_square_meter`), `linear_density` → m
  (`uom.product_uom_meter`), `per_unit`/`none` → Units
  (`uom.product_uom_unit`). Empty recordset if the xml_id is somehow
  missing (defensive `raise_if_not_found=False`, never a hard crash).
- Produces: `mrp.bom.line._sb_demand_qty_in_uom(self, to_uom) -> (float,
  bool)` — thin wrapper: resolves `self.material_id._sb_canonical_demand_uom()`
  then delegates to `sb_convert_demand_qty(self.material_demand_qty,
  to_uom)`. `(self.material_demand_qty, False)` when no material or no
  canonical uom resolves.
- Consumed by: Task 4 (PO-line note's fallback path, via the material-level
  method directly — Task 4 doesn't need a `mrp.bom.line`).

### Step 1: Write the failing test (`uom.uom` helper)

```python
# addons/sb_material_core/tests/test_uom_conversion.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestUomConversion(TransactionCase):
    def test_converts_within_shared_reference(self):
        sqm = self.env.ref("uom.product_uom_square_meter")
        sqft = self.env.ref("uom.product_uom_square_foot")
        qty, is_exact = sqm.sb_convert_demand_qty(1.0, sqft)
        self.assertTrue(is_exact)
        self.assertAlmostEqual(qty, 10.7639, places=3)  # 1 m2 in ft2

    def test_same_uom_is_passthrough(self):
        sqm = self.env.ref("uom.product_uom_square_meter")
        qty, is_exact = sqm.sb_convert_demand_qty(3.2, sqm)
        self.assertTrue(is_exact)
        self.assertEqual(qty, 3.2)

    def test_no_common_reference_is_honest_fallback(self):
        sqm = self.env.ref("uom.product_uom_square_meter")
        kg = self.env.ref("uom.product_uom_kgm")
        qty, is_exact = sqm.sb_convert_demand_qty(5.0, kg)
        self.assertFalse(is_exact)
        self.assertEqual(qty, 5.0)  # unchanged, never fabricated

    def test_missing_to_uom_is_honest_fallback(self):
        sqm = self.env.ref("uom.product_uom_square_meter")
        qty, is_exact = sqm.sb_convert_demand_qty(5.0, self.env["uom.uom"])
        self.assertFalse(is_exact)
        self.assertEqual(qty, 5.0)
```

Add `from . import test_uom_conversion` to `addons/sb_material_core/tests/__init__.py`.

### Step 2: Run to verify it fails

`docker exec v19c-odoo odoo -u sb_material_core --test-enable --test-tags sbk_material,sb_geo -d test_sbgeo_b1 --stop-after-init --no-http --http-port=8260`
Expected: FAIL — `sb_convert_demand_qty` is not a method on `uom.uom`.

### Step 3: Write minimal implementation

```python
# addons/sb_material_core/models/uom_uom.py
# SPDX-License-Identifier: LGPL-3.0-only
"""Task 1 (Materials Phase-2b Procurement). v19 `uom.uom` has NO
`category`/`category_id` model (grep-verified against the installed core,
addons/uom/models/uom_uom.py) — units relate via `relative_uom_id`, a
_parent_store tree, and `_has_common_reference` walks `parent_path` to
check two units share a root. `_compute_quantity` itself does NOT gate on
that — it blindly multiplies by `factor` ratios regardless of category, so
this helper checks `_has_common_reference` FIRST and never calls
`_compute_quantity` when it's false.
"""
from odoo import models


class UomUom(models.Model):
    _inherit = "uom.uom"

    def sb_convert_demand_qty(self, qty, to_uom):
        """Convert `qty` (expressed in `self`) into `to_uom`.

        Returns (qty, is_exact):
        - is_exact True: a real native conversion applied; `qty` is now in
          `to_uom`.
        - is_exact False: `self`/`to_uom` share no reference (e.g. canonical
          m2 vs. a vendor's non-dimensional "Sheet" pack unit -- that case
          is `uom_yield_qty`'s job, Phase-2a, not this helper's). `qty` is
          returned UNCHANGED -- never fabricated.
        """
        self.ensure_one()
        if not self or not to_uom:
            return qty, False
        to_uom.ensure_one()
        if self == to_uom:
            return qty, True
        if not self._has_common_reference(to_uom):
            return qty, False
        return self._compute_quantity(qty, to_uom, round=False), True
```

Add `from . import uom_uom` to `addons/sb_material_core/models/__init__.py`.
Bump `addons/sb_material_core/__manifest__.py` `"version"` to `19.0.1.8.0`.

### Step 4: Run to verify it passes

Same command as Step 2, port 8260. Expected: PASS.

### Step 5: Commit

```bash
git add addons/sb_material_core/models/uom_uom.py \
        addons/sb_material_core/models/__init__.py \
        addons/sb_material_core/__manifest__.py \
        addons/sb_material_core/tests/test_uom_conversion.py \
        addons/sb_material_core/tests/__init__.py
git commit -m "feat(sb_material_core): native uom.uom conversion helper (Phase-2b T1a)"
```

### Step 6: Write the failing test (`southbrook.kitchen.material` canonical uom resolver)

```python
# append to addons/sb_material_core/tests/test_uom_conversion.py
class TestMaterialCanonicalUom(TransactionCase):
    def _mat(self, code, weight_source):
        fam = self.env["material.family"].create({"name": code, "code": code})
        return self.env["southbrook.kitchen.material"].create({
            "name": code, "code": code, "family_id": fam.id,
            "weight_source": weight_source,
        })

    def test_density_volume_maps_to_square_meter(self):
        mat = self._mat("cu_dv", "density_volume")
        self.assertEqual(
            mat._sb_canonical_demand_uom(), self.env.ref("uom.product_uom_square_meter"))

    def test_linear_density_maps_to_meter(self):
        mat = self._mat("cu_ld", "linear_density")
        self.assertEqual(
            mat._sb_canonical_demand_uom(), self.env.ref("uom.product_uom_meter"))

    def test_per_unit_maps_to_units(self):
        mat = self._mat("cu_pu", "per_unit")
        self.assertEqual(
            mat._sb_canonical_demand_uom(), self.env.ref("uom.product_uom_unit"))
```

(Add `@tagged(...)` decorator matching the file's convention on this second class too.)

### Step 7: Run to verify it fails

Same command, port 8260. Expected: FAIL — `_sb_canonical_demand_uom` missing.

### Step 8: Write minimal implementation

Add to `southbrook_kitchen_material.py`, near `_effective_waste_pct`:

```python
    _SB_CANONICAL_DEMAND_UOM_XMLID = {
        "density_volume": "uom.product_uom_square_meter",
        "density_area": "uom.product_uom_square_meter",
        "linear_density": "uom.product_uom_meter",
        "per_unit": "uom.product_uom_unit",
        "none": "uom.product_uom_unit",
    }

    def _sb_canonical_demand_uom(self):
        """The uom.uom record representing this material's canonical
        material_demand_qty unit (Phase-2b Task 1): m² for area families,
        m for linear, Units for per_unit/none. Empty recordset (never a
        crash) if the xml_id is somehow missing."""
        self.ensure_one()
        xmlid = self._SB_CANONICAL_DEMAND_UOM_XMLID.get(
            self.weight_source, "uom.product_uom_unit")
        return self.env.ref(xmlid, raise_if_not_found=False) or self.env["uom.uom"]
```

### Step 9: Run to verify it passes

Same command, port 8260. Expected: PASS.

### Step 10: Commit

```bash
git add addons/sb_material_core/models/southbrook_kitchen_material.py \
        addons/sb_material_core/tests/test_uom_conversion.py
git commit -m "feat(sb_material_core): material canonical demand UoM resolver (Phase-2b T1b)"
```

### Step 11: Write the failing test (`mrp.bom.line` wrapper)

```python
# addons/sb_material_mrp/tests/test_demand_qty_uom_conversion.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestDemandQtyUomConversion(TransactionCase):
    def _line_with_demand(self, weight_source, demand_qty):
        fam = self.env["material.family"].create({"name": "UC", "code": "uc_test"})
        mat = self.env["southbrook.kitchen.material"].create({
            "name": "UC Mat", "code": "uc_mat", "family_id": fam.id,
            "density": 0.68, "weight_source": weight_source, "thickness_mm": 19.05,
        })
        tmpl = self.env["product.template"].create({"name": "Cab UC"})
        comp = self.env["product.product"].create({"name": "Comp UC"})
        comp.product_tmpl_id.material_id = mat.id
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": tmpl.id, "product_id": tmpl.product_variant_id.id})
        line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": comp.id, "product_qty": 1.0})
        line.material_demand_qty = demand_qty  # force a known value
        return line

    def test_area_family_converts_to_square_feet(self):
        line = self._line_with_demand("density_volume", 2.0)
        sqft = self.env.ref("uom.product_uom_square_foot")
        qty, is_exact = line._sb_demand_qty_in_uom(sqft)
        self.assertTrue(is_exact)
        self.assertAlmostEqual(qty, 21.5278, places=3)  # 2 m2 in ft2

    def test_linear_family_converts_to_feet(self):
        line = self._line_with_demand("linear_density", 3.0)
        ft = self.env.ref("uom.product_uom_foot")
        qty, is_exact = line._sb_demand_qty_in_uom(ft)
        self.assertTrue(is_exact)
        self.assertAlmostEqual(qty, 9.8425, places=3)  # 3 m in ft

    def test_incompatible_target_uom_is_honest_fallback(self):
        line = self._line_with_demand("density_volume", 2.0)
        kg = self.env.ref("uom.product_uom_kgm")
        qty, is_exact = line._sb_demand_qty_in_uom(kg)
        self.assertFalse(is_exact)
        self.assertEqual(qty, 2.0)
```

Add `from . import test_demand_qty_uom_conversion` to
`addons/sb_material_mrp/tests/__init__.py`.

### Step 12: Run to verify it fails

`docker exec v19c-odoo odoo -u sb_material_mrp --test-enable --test-tags sbk_material,sb_geo -d test_sbgeo_b1 --stop-after-init --no-http --http-port=8261`
Expected: FAIL — `_sb_demand_qty_in_uom` missing.

### Step 13: Write minimal implementation

Add to `class MrpBomLine` in `mrp_bom.py`:

```python
    def _sb_demand_qty_in_uom(self, to_uom):
        """material_demand_qty converted into `to_uom` via native uom.uom
        conversion (Phase-2b Task 1) when the material's canonical demand
        unit and `to_uom` share a reference. Returns (qty, is_exact);
        honest fallback (unchanged qty, is_exact=False) when no common
        reference -- e.g. a vendor 'Sheet'/'Roll' pack unit, which is
        uom_yield_qty's job (Phase-2a), not this helper's."""
        self.ensure_one()
        if not self.material_id or not to_uom:
            return self.material_demand_qty, False
        from_uom = self.material_id._sb_canonical_demand_uom()
        if not from_uom:
            return self.material_demand_qty, False
        return from_uom.sb_convert_demand_qty(self.material_demand_qty, to_uom)
```

Bump `addons/sb_material_mrp/__manifest__.py` `"version"` to `19.0.1.8.0`.

### Step 14: Run to verify it passes

Same command, port 8261. Expected: PASS.

### Step 15: Commit

```bash
git add addons/sb_material_mrp/models/mrp_bom.py \
        addons/sb_material_mrp/__manifest__.py \
        addons/sb_material_mrp/tests/test_demand_qty_uom_conversion.py \
        addons/sb_material_mrp/tests/__init__.py
git commit -m "feat(sb_material_mrp): mrp.bom.line demand-qty UoM conversion wrapper (Phase-2b T1c)"
```

---

## Task 2: Orderpoint sync — MAX from open-MO demand rollup

**Files:**
- Modify: `addons/sb_material_mrp/models/product_template.py`
- Modify: `addons/sb_material_mrp/views/product_template_views.xml`
- Modify: `addons/sb_material_mrp/__manifest__.py` (bump `19.0.1.8.0` →
  `19.0.1.9.0`)
- Create: `addons/sb_material_mrp/tests/test_orderpoint_sync.py`
- Modify: `addons/sb_material_mrp/tests/__init__.py`

**Interfaces:**
- Consumes: `mrp.bom.line.material_demand_qty` (Phase-2a, live);
  `mrp.production.state`/`bom_id`/`product_qty` (native).
- Produces: `product.template._sb_open_mo_material_demand_qty(self) ->
  float` — sums, over every `mrp.production` in state `('confirmed',
  'progress', 'to_close')` whose `bom_id` has a line for one of this
  template's variants, `sum(bom_line.material_demand_qty for matching
  lines) * (production.product_qty / (bom.product_qty or 1.0))`. `0.0`
  (honest) when no open MO references this template as a component.
- Produces: `product.template.action_sb_sync_orderpoint_max(self,
  warehouse_ids=None) -> dict (client notification action)` — for each
  target warehouse (param recordset, or all warehouses of
  `self.env.companies` when omitted), find-or-create a
  `stock.warehouse.orderpoint` keyed on `(product_id=self.product_variant_id,
  location_id=warehouse.lot_stock_id, company_id=warehouse.company_id)` and
  set **only** `product_max_qty = max(ceil(rollup), existing
  product_min_qty)` (native `_check_min_max_qty` requires max ≥ min).
  `product_min_qty`, `trigger`, `route_id` are **never** touched by this
  action once the orderpoint exists — native config, human-owned (see the
  architecture note at the top of this plan). **Skips** (creates nothing)
  when the rollup is `0.0` — no phantom orderpoints for products with no
  current open-MO signal. Consumed by: nothing downstream in code (terminal
  config action); Task 3's proof test creates an orderpoint directly rather
  than calling this action, to keep that proof independent of Task 2.

### Step 1: Write the failing test

```python
# addons/sb_material_mrp/tests/test_orderpoint_sync.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestOrderpointSync(TransactionCase):
    def _cabinet_with_open_mo(self, comp, qty_per_cab=2.5, mo_qty=3.0):
        cab_tmpl = self.env["product.template"].create(
            {"name": "Cab OP", "is_storable": True})
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": cab_tmpl.id,
            "product_id": cab_tmpl.product_variant_id.id,
            "product_qty": 1.0,
        })
        line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": comp.id, "product_qty": 1.0,
        })
        line.material_demand_qty = qty_per_cab
        mo = self.env["mrp.production"].create({
            "product_id": cab_tmpl.product_variant_id.id,
            "bom_id": bom.id, "product_qty": mo_qty,
        })
        mo.action_confirm()
        return mo

    def test_no_open_mo_rollup_is_zero(self):
        comp = self.env["product.product"].create({"name": "Comp OP0", "is_storable": True})
        self.assertEqual(comp.product_tmpl_id._sb_open_mo_material_demand_qty(), 0.0)

    def test_rollup_scales_by_mo_qty(self):
        comp = self.env["product.product"].create({"name": "Comp OP1", "is_storable": True})
        self._cabinet_with_open_mo(comp, qty_per_cab=2.5, mo_qty=3.0)
        # 2.5 m2/cabinet * 3 cabinets = 7.5 m2 of open demand
        self.assertAlmostEqual(
            comp.product_tmpl_id._sb_open_mo_material_demand_qty(), 7.5, places=2)

    def test_sync_creates_orderpoint_with_max_from_rollup(self):
        comp = self.env["product.product"].create(
            {"name": "Comp OP2", "is_storable": True, "purchase_ok": True})
        self._cabinet_with_open_mo(comp, qty_per_cab=4.0, mo_qty=2.0)  # 8.0 m2
        wh = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1)
        comp.product_tmpl_id.action_sb_sync_orderpoint_max(warehouse_ids=wh)
        op = self.env["stock.warehouse.orderpoint"].search([
            ("product_id", "=", comp.id), ("warehouse_id", "=", wh.id)])
        self.assertEqual(len(op), 1)
        self.assertEqual(op.product_max_qty, 8.0)
        self.assertEqual(op.product_min_qty, 0.0)  # untouched -- not this task's job

    def test_sync_is_idempotent_and_refreshes_existing_max(self):
        comp = self.env["product.product"].create(
            {"name": "Comp OP3", "is_storable": True, "purchase_ok": True})
        self._cabinet_with_open_mo(comp, qty_per_cab=1.0, mo_qty=1.0)  # 1.0 m2
        wh = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1)
        comp.product_tmpl_id.action_sb_sync_orderpoint_max(warehouse_ids=wh)
        op1 = self.env["stock.warehouse.orderpoint"].search([
            ("product_id", "=", comp.id), ("warehouse_id", "=", wh.id)])
        self._cabinet_with_open_mo(comp, qty_per_cab=5.0, mo_qty=2.0)  # +10.0 m2
        comp.product_tmpl_id.action_sb_sync_orderpoint_max(warehouse_ids=wh)
        op2 = self.env["stock.warehouse.orderpoint"].search([
            ("product_id", "=", comp.id), ("warehouse_id", "=", wh.id)])
        self.assertEqual(op1.id, op2.id)  # same record, not duplicated
        self.assertAlmostEqual(op2.product_max_qty, 11.0, places=2)

    def test_zero_demand_skips_creating_orderpoint(self):
        comp = self.env["product.product"].create({"name": "Comp OP4", "is_storable": True})
        wh = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1)
        comp.product_tmpl_id.action_sb_sync_orderpoint_max(warehouse_ids=wh)
        op = self.env["stock.warehouse.orderpoint"].search([
            ("product_id", "=", comp.id), ("warehouse_id", "=", wh.id)])
        self.assertFalse(op)  # honest: no phantom orderpoint for zero demand
```

Add `from . import test_orderpoint_sync` to `addons/sb_material_mrp/tests/__init__.py`.

### Step 2: Run to verify it fails

`docker exec v19c-odoo odoo -u sb_material_mrp --test-enable --test-tags sbk_material,sb_geo -d test_sbgeo_b1 --stop-after-init --no-http --http-port=8262`
Expected: FAIL — `_sb_open_mo_material_demand_qty`/`action_sb_sync_orderpoint_max` missing.

### Step 3: Write minimal implementation

Add `import math` at the top of `product_template.py` if not already present.
Add to `class ProductTemplate`:

```python
    _SB_OPEN_MO_STATES = ("confirmed", "progress", "to_close")

    def _sb_open_mo_material_demand_qty(self):
        """Rollup of material_demand_qty this template's component demands
        across currently OPEN manufacturing orders (Phase-2b Task 2) --
        scaled by each MO's own product_qty relative to its BoM's base
        qty. 0.0 (never fabricated) when no open MO's BoM references this
        template as a component.

        NOTE (architecture limitation -- see the top of the Phase-2b plan):
        this rollup feeds the orderpoint MAX only. It does NOT make the
        native scheduler's TRIGGER size-aware -- the trigger is still the
        native, size-blind product_qty on each MO's raw-material move
        (Fork-1: product_configurator_mrp writes qty=1 per component; left
        untouched)."""
        self.ensure_one()
        productions = self.env["mrp.production"].search([
            ("state", "in", self._SB_OPEN_MO_STATES),
            ("bom_id.bom_line_ids.product_id.product_tmpl_id", "=", self.id),
        ])
        total = 0.0
        for prod in productions:
            bom = prod.bom_id
            base_qty = bom.product_qty or 1.0
            scale = prod.product_qty / base_qty
            lines = bom.bom_line_ids.filtered(
                lambda l: l.product_id.product_tmpl_id == self)
            total += sum(lines.mapped("material_demand_qty")) * scale
        return total

    def action_sb_sync_orderpoint_max(self, warehouse_ids=None):
        """Find-or-create a native stock.warehouse.orderpoint per warehouse
        for this material component product, and set its MAX from the
        open-MO demand rollup. NATIVE CONFIG ASSISTED, not a bespoke
        reorder engine: this only ever writes product_max_qty (and creates
        the orderpoint row with native defaults -- trigger='auto',
        product_min_qty=0.0 -- when none exists). product_min_qty,
        trigger, and route_id are left exactly as a human configured them
        on every subsequent call.

        Skips (creates nothing) when the rollup is 0.0 -- no phantom
        orderpoints for products with no current open-MO demand signal."""
        warehouses = warehouse_ids or self.env["stock.warehouse"].search(
            [("company_id", "in", self.env.companies.ids)])
        Orderpoint = self.env["stock.warehouse.orderpoint"]
        touched = Orderpoint.browse()
        for tmpl in self:
            rollup = tmpl._sb_open_mo_material_demand_qty()
            if rollup <= 0.0:
                continue
            target_max = math.ceil(rollup)
            variant = tmpl.product_variant_id
            for wh in warehouses:
                op = Orderpoint.search([
                    ("product_id", "=", variant.id),
                    ("location_id", "=", wh.lot_stock_id.id),
                    ("company_id", "=", wh.company_id.id),
                ], limit=1)
                if op:
                    op.product_max_qty = max(target_max, op.product_min_qty)
                else:
                    op = Orderpoint.create({
                        "product_id": variant.id,
                        "location_id": wh.lot_stock_id.id,
                        "warehouse_id": wh.id,
                        "company_id": wh.company_id.id,
                        "product_max_qty": target_max,
                    })
                touched |= op
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "message": _("%s orderpoint(s) synced from open-MO demand.", len(touched)),
                "sticky": False,
            },
        }
```

(`_` is already imported in `product_template.py` from Phase-2a's
`action_sb_set_route_buy`.)

Add a matching button to `product_template_views.xml`, inside the same
`button_box` xpath as the existing Buy-route button:

```xml
<button name="action_sb_sync_orderpoint_max" type="object"
        class="oe_stat_button" icon="fa-refresh"
        invisible="not material_id">
    <div class="o_stat_info">
        <span class="o_stat_text">Sync Orderpoint Max</span>
    </div>
</button>
```

Bump `addons/sb_material_mrp/__manifest__.py` `"version"` to `19.0.1.9.0`.

### Step 4: Run to verify it passes

Same command, port 8262. Expected: PASS.

### Step 5: Commit

```bash
git add addons/sb_material_mrp/models/product_template.py \
        addons/sb_material_mrp/views/product_template_views.xml \
        addons/sb_material_mrp/__manifest__.py \
        addons/sb_material_mrp/tests/test_orderpoint_sync.py \
        addons/sb_material_mrp/tests/__init__.py
git commit -m "feat(sb_material_mrp): orderpoint MAX sync from open-MO demand rollup (Phase-2b T2)"
```

---

## Task 3: Scheduler → draft RFQ proof (test-only, zero PO-creation code)

**Files:**
- Create: `addons/sb_material_mrp/tests/test_scheduler_draft_rfq.py`
- Modify: `addons/sb_material_mrp/tests/__init__.py`

No manifest version bump — this task adds a test only, no runtime code.

**Interfaces:**
- Consumes: `product.template.action_sb_set_route_buy()` (Phase-2a, live);
  native `stock.warehouse.orderpoint`; native `stock.rule.run_scheduler()`.
- Produces: nothing new — this task is the proof that the existing
  Phase-2a Buy-route helper plus a plain native orderpoint is *sufficient*
  for the native scheduler to draft an RFQ, with no Southbrook code in the
  PO-creation path at all.

### Step 1: Write the failing test

```python
# addons/sb_material_mrp/tests/test_scheduler_draft_rfq.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestSchedulerDraftRfq(TransactionCase):
    def test_orderpoint_plus_buy_route_yields_draft_po_via_native_scheduler(self):
        vendor = self.env["res.partner"].create({"name": "Sheet Vendor RFQ"})
        comp_tmpl = self.env["product.template"].create({
            "name": "Sheet RFQ Proof", "is_storable": True, "purchase_ok": True,
        })
        comp = comp_tmpl.product_variant_id
        self.env["product.supplierinfo"].create({
            "partner_id": vendor.id,
            "product_tmpl_id": comp_tmpl.id,
            "price": 40.0,
            "min_qty": 1.0,
        })
        # Phase-2a Task 5: native Buy route -- zero PO-creation code, just a
        # route flag the native scheduler reads.
        comp_tmpl.action_sb_set_route_buy()

        wh = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1)
        # product_min_qty=1.0 (not 0.0): the native trigger check is the
        # STRICT `qty_forecast < product_min_qty` (float_compare) -- with
        # zero on-hand and zero reservation, a min of 0.0 would never fire.
        # This value simulates what Task 2's sync action would set once a
        # human also configures a real safety-stock MIN; Task 2 itself
        # never writes MIN (see the plan's architecture note).
        self.env["stock.warehouse.orderpoint"].create({
            "product_id": comp.id,
            "location_id": wh.lot_stock_id.id,
            "warehouse_id": wh.id,
            "company_id": wh.company_id.id,
            "product_min_qty": 1.0,
            "product_max_qty": 5.0,  # simulates Task 2's rollup-derived MAX
        })

        po_before = self.env["purchase.order"].search([
            ("partner_id", "=", vendor.id), ("state", "=", "draft")])
        self.assertFalse(po_before)

        # THE native scheduler -- zero PO-creation code in this test or in
        # any Southbrook module. `stock.rule` is the model that carries
        # `run_scheduler` in this v19 core (grep-verified: addons/stock/
        # models/stock_rule.py, class StockRule, _name = "stock.rule" --
        # NOT a separate "procurement.group" model as in older Odoo).
        self.env["stock.rule"].run_scheduler(use_new_cursor=False)

        po = self.env["purchase.order"].search([
            ("partner_id", "=", vendor.id), ("state", "=", "draft")])
        self.assertTrue(po, "native scheduler should have drafted an RFQ")
        self.assertIn(comp.id, po.order_line.mapped("product_id").ids)
        # never auto-confirmed by this proof -- assist-only until Task 5
        self.assertEqual(po.state, "draft")
```

Add `from . import test_scheduler_draft_rfq` to `addons/sb_material_mrp/tests/__init__.py`.

### Step 2: Run to verify it fails

`docker exec v19c-odoo odoo -u sb_material_mrp --test-enable --test-tags sbk_material,sb_geo -d test_sbgeo_b1 --stop-after-init --no-http --http-port=8263`
Expected: FAIL at this point only if the environment lacks something (e.g.
no default company warehouse) — if it fails for an environmental reason,
fix the test's setup, not add implementation code (there is none to add;
this task proves existing native+Phase-2a behavior). If it fails because
no draft PO is created, that is a real signal something about the Buy
route/orderpoint/supplier wiring is broken and must be diagnosed — do
**not** paper over it with new PO-creation code.

### Step 3: (No implementation step — this task is a proof, not a feature)

If Step 2 genuinely fails after correct setup, the fix belongs in
Phase-2a's existing code (`action_sb_set_route_buy`, the orderpoint fields,
or the supplierinfo minimum fields) — this plan's Task 3 does not add new
production code.

### Step 4: Run to verify it passes

Same command, port 8263. Expected: PASS.

### Step 5: Commit

```bash
git add addons/sb_material_mrp/tests/test_scheduler_draft_rfq.py \
        addons/sb_material_mrp/tests/__init__.py
git commit -m "test(sb_material_mrp): prove native scheduler drafts RFQ off Buy route + orderpoint (Phase-2b T3)"
```

---

## Task 4: Suggested-qty transparency on the native PO/RFQ line

**Files:**
- Create: `addons/sb_material_mrp/models/purchase_order_line.py`
- Modify: `addons/sb_material_mrp/models/__init__.py`
- Create: `addons/sb_material_mrp/views/purchase_order_views.xml`
- Modify: `addons/sb_material_mrp/__manifest__.py` (bump `19.0.1.9.0` →
  `19.0.1.10.0`; register the new view)
- Create: `addons/sb_material_mrp/tests/test_purchase_line_material_note.py`
- Modify: `addons/sb_material_mrp/tests/__init__.py`

**Interfaces:**
- Consumes: `product.template._sb_open_mo_material_demand_qty()` (Task 2);
  `southbrook.kitchen.material._effective_waste_pct()` /
  `_sb_canonical_demand_uom()` (Phase-2a / Task 1); `product.supplierinfo.
  uom_yield_qty` via `product.product._select_seller(partner_id, uom_id)`
  (native, `addons/product/models/product_product.py`); `uom.uom.
  sb_convert_demand_qty()` (Task 1) as the fallback path.
- Produces (both **non-stored** computed fields — deliberate: this is a
  live, same-moment decision-support snapshot of *currently open* MO
  demand, not a persisted business fact; storing it would let it go stale
  the moment an MO is confirmed/done elsewhere without touching this PO
  line):
  - `purchase.order.line.sb_material_demand_qty` (Float) — the open-MO
    rollup for `line.product_id`, in canonical units. `0.0` when the
    product has no resolved material or no open-MO demand.
  - `purchase.order.line.sb_material_suggested_note` (Char) — human-
    readable transparency string. Three honest branches: (a) a
    yield-based suggestion when the matched seller has `uom_yield_qty >
    0` (mirrors Phase-2a's `suggested_purchase_qty` formula, ceil +
    waste, but scoped to THIS PO line's vendor/UoM rather than the
    product's globally-selected seller); (b) a native-UoM-conversion
    display when no yield is recorded but Task 1's converter finds a
    common reference; (c) an honest "no vendor yield / no compatible
    UoM" message otherwise. `""` when there's no material or no open-MO
    demand at all.
- Consumed by: view only (Task 4 UI). Never written back to `product_qty`,
  never used to confirm anything.

### Step 1: Write the failing test

```python
# addons/sb_material_mrp/tests/test_purchase_line_material_note.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestPurchaseLineMaterialNote(TransactionCase):
    def _setup_material_and_component(self, waste_pct, yield_qty=0.0):
        fam = self.env["material.family"].create(
            {"name": "PL", "code": "pl_test", "default_waste_pct": waste_pct})
        mat = self.env["southbrook.kitchen.material"].create({
            "name": "PL Mat", "code": "pl_mat", "family_id": fam.id,
            "density": 0.68, "weight_source": "density_volume", "thickness_mm": 19.05,
        })
        vendor = self.env["res.partner"].create({"name": "PL Vendor"})
        comp_tmpl = self.env["product.template"].create(
            {"name": "PL Comp", "is_storable": True, "purchase_ok": True})
        comp_tmpl.material_id = mat.id
        if yield_qty:
            self.env["product.supplierinfo"].create({
                "partner_id": vendor.id, "product_tmpl_id": comp_tmpl.id,
                "price": 40.0, "uom_yield_qty": yield_qty})
        return mat, vendor, comp_tmpl

    def _open_mo_demand(self, comp_tmpl, demand_qty=5.0):
        cab_tmpl = self.env["product.template"].create({"name": "PL Cab", "is_storable": True})
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": cab_tmpl.id, "product_id": cab_tmpl.product_variant_id.id})
        line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": comp_tmpl.product_variant_id.id, "product_qty": 1.0})
        line.material_demand_qty = demand_qty
        mo = self.env["mrp.production"].create({
            "product_id": cab_tmpl.product_variant_id.id, "bom_id": bom.id, "product_qty": 1.0})
        mo.action_confirm()

    def _po_line(self, vendor, comp_tmpl):
        po = self.env["purchase.order"].create({"partner_id": vendor.id})
        return self.env["purchase.order.line"].create({
            "order_id": po.id, "product_id": comp_tmpl.product_variant_id.id,
            "product_qty": 1.0, "product_uom_id": comp_tmpl.uom_id.id,
            "price_unit": 40.0, "name": comp_tmpl.name,
        })

    def test_note_shows_yield_based_suggestion(self):
        mat, vendor, comp_tmpl = self._setup_material_and_component(waste_pct=12.0, yield_qty=2.97)
        self._open_mo_demand(comp_tmpl, demand_qty=5.0)
        line = self._po_line(vendor, comp_tmpl)
        self.assertGreater(line.sb_material_demand_qty, 0.0)
        self.assertIn("suggests", line.sb_material_suggested_note)

    def test_note_is_honest_when_no_yield_and_no_uom_match(self):
        mat, vendor, comp_tmpl = self._setup_material_and_component(waste_pct=12.0, yield_qty=0.0)
        self._open_mo_demand(comp_tmpl, demand_qty=5.0)
        line = self._po_line(vendor, comp_tmpl)
        # comp_tmpl.uom_id defaults to Units, which shares no reference
        # with the canonical m2 unit -> honest fallback, no suggestion
        self.assertIn("No vendor yield", line.sb_material_suggested_note)

    def test_no_material_no_demand_gives_empty_note(self):
        vendor = self.env["res.partner"].create({"name": "PL Vendor2"})
        comp_tmpl = self.env["product.template"].create(
            {"name": "PL Comp2", "is_storable": True, "purchase_ok": True})
        line = self._po_line(vendor, comp_tmpl)
        self.assertEqual(line.sb_material_suggested_note, "")
        self.assertEqual(line.sb_material_demand_qty, 0.0)
```

Add `from . import test_purchase_line_material_note` to
`addons/sb_material_mrp/tests/__init__.py`.

### Step 2: Run to verify it fails

`docker exec v19c-odoo odoo -u sb_material_mrp --test-enable --test-tags sbk_material,sb_geo -d test_sbgeo_b1 --stop-after-init --no-http --http-port=8264`
Expected: FAIL — `sb_material_demand_qty`/`sb_material_suggested_note` not
fields on `purchase.order.line`.

### Step 3: Write minimal implementation

```python
# addons/sb_material_mrp/models/purchase_order_line.py
# SPDX-License-Identifier: LGPL-3.0-only
"""Phase-2b Task 4 -- assist-only transparency on the native PO/RFQ line.

Both fields below are deliberately NON-STORED: they are a live snapshot of
CURRENTLY OPEN MO demand (product.template._sb_open_mo_material_demand_qty,
Task 2), which changes as MOs are confirmed/closed independently of this
PO line -- storing them would let them go stale silently. Neither field is
ever written back to product_qty, and nothing here confirms a PO (see
models/stock_rule.py, Task 5, for the one gated exception elsewhere).
"""
import math

from odoo import _, api, fields, models
from odoo.tools import float_round


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    sb_material_demand_qty = fields.Float(
        string="Open-MO Material Demand",
        compute="_compute_sb_material_suggested_note",
        digits=(12, 4),
        help="Read-only assist (Phase-2b Task 4): this line's product's "
             "rollup of material_demand_qty across currently OPEN "
             "manufacturing orders, in the material's canonical demand "
             "unit. 0.0 when the product has no resolved material or no "
             "open-MO demand. NOT the number that generated this RFQ line "
             "-- the native scheduler's trigger is still the size-blind "
             "orderpoint MIN / native BoM qty (Fork-1; see the Phase-2b "
             "plan's architecture note). This is a live, same-moment "
             "transparency snapshot, not this line's origin.",
    )
    sb_material_suggested_note = fields.Char(
        string="Material Suggestion",
        compute="_compute_sb_material_suggested_note",
        help="Assist-only, human-readable transparency note. Never writes "
             "product_qty, never confirms this PO. Empty string when the "
             "product has no resolved material or no open-MO demand -- "
             "never a fabricated suggestion.",
    )

    @api.depends("product_id", "product_uom_id", "partner_id")
    def _compute_sb_material_suggested_note(self):
        for line in self:
            line.sb_material_demand_qty = 0.0
            line.sb_material_suggested_note = ""
            tmpl = line.product_id.product_tmpl_id if line.product_id else False
            mat = tmpl.material_id if tmpl else False
            if not mat:
                continue
            demand = tmpl._sb_open_mo_material_demand_qty()
            if demand <= 0.0:
                continue
            line.sb_material_demand_qty = demand
            waste = mat._effective_waste_pct()
            gross = demand * (1.0 + waste / 100.0)
            canonical_uom = mat._sb_canonical_demand_uom()
            unit_label = canonical_uom.name if canonical_uom else _("unit(s)")
            seller = False
            if line.partner_id and line.product_id:
                seller = line.product_id._select_seller(
                    partner_id=line.partner_id.id,
                    uom_id=line.product_uom_id.id or False,
                )
            yield_qty = seller.uom_yield_qty if seller else 0.0
            po_uom_name = line.product_uom_id.name or _("unit")
            if yield_qty > 0.0:
                ratio = float_round(gross / yield_qty, precision_digits=4)
                packs = math.ceil(ratio)
                line.sb_material_suggested_note = _(
                    "Open-MO demand: %(demand).2f %(unit)s (incl. "
                    "%(waste)g%% waste) -> suggests %(packs)g %(po_uom)s "
                    "@ %(yield_qty)g %(unit)s/%(po_uom)s.",
                    demand=demand, unit=unit_label, waste=waste,
                    packs=packs, po_uom=po_uom_name, yield_qty=yield_qty,
                )
                continue
            converted, is_exact = (
                canonical_uom.sb_convert_demand_qty(gross, line.product_uom_id)
                if canonical_uom and line.product_uom_id else (gross, False)
            )
            if is_exact:
                line.sb_material_suggested_note = _(
                    "Open-MO demand: %(demand).2f %(unit)s (incl. "
                    "%(waste)g%% waste) ~= %(converted).2f %(po_uom)s "
                    "(native UoM conversion; no vendor yield recorded).",
                    demand=demand, unit=unit_label, waste=waste,
                    converted=converted, po_uom=po_uom_name,
                )
            else:
                line.sb_material_suggested_note = _(
                    "Open-MO demand: %(demand).2f %(unit)s (incl. "
                    "%(waste)g%% waste). No vendor yield recorded and no "
                    "compatible UoM conversion -- record "
                    "product.supplierinfo.uom_yield_qty for a "
                    "purchase-qty suggestion.",
                    demand=demand, unit=unit_label, waste=waste,
                )
```

Add `from . import purchase_order_line` to `addons/sb_material_mrp/models/__init__.py`.

Add the view (list column + Materials tab on the PO line's inline form —
xpath grep-verified against the installed core,
`addons/purchase/views/purchase_views.xml`, `id="purchase_order_form"`,
external id `purchase.purchase_order_form`: the nested list holds `<field
name="product_uom_id" .../>` directly inside `<field name="order_line">
<list ...>`, and the inline per-line `<form string="Purchase Order
Line">` — embedded in the same view, not a separate reusable view id —
carries `<notebook colspan="4"><page string="Notes" name="notes">`):

```xml
<!-- addons/sb_material_mrp/views/purchase_order_views.xml -->
<?xml version="1.0" encoding="utf-8"?>
<!-- SPDX-License-Identifier: LGPL-3.0-only -->
<odoo>
    <record id="purchase_order_form_sb_material" model="ir.ui.view">
        <field name="name">purchase.order.form.sb.material</field>
        <field name="model">purchase.order</field>
        <field name="inherit_id" ref="purchase.purchase_order_form"/>
        <field name="arch" type="xml">
            <xpath expr="//field[@name='order_line']/list/field[@name='product_uom_id']" position="after">
                <field name="sb_material_suggested_note" optional="show" readonly="1"/>
            </xpath>
            <xpath expr="//field[@name='order_line']/form//page[@name='notes']" position="after">
                <page string="Materials" name="sb_materials">
                    <field name="sb_material_demand_qty" readonly="1"/>
                    <field name="sb_material_suggested_note" readonly="1"/>
                </page>
            </xpath>
        </field>
    </record>
</odoo>
```

> Note (same discipline as Phase-2a's documented xpath caveats): if the
> installed `purchase.purchase_order_form` arch differs from the grep
> above on this build (unlikely — verified 2026-07-26 against
> `/Users/naadmin/Downloads/Official/V19C/odoo`), the reviewer/implementer
> should adjust the two xpath targets to the actual list/form structure —
> the two field additions are the deliverable, not the exact xpath string.

Register the new view file in `addons/sb_material_mrp/__manifest__.py`
`data` list. Bump `"version"` to `19.0.1.10.0`.

### Step 4: Run to verify it passes

Same command, port 8264. Expected: PASS, and the module loads with the new
view (no ParseError).

### Step 5: Commit

```bash
git add addons/sb_material_mrp/models/purchase_order_line.py \
        addons/sb_material_mrp/models/__init__.py \
        addons/sb_material_mrp/views/purchase_order_views.xml \
        addons/sb_material_mrp/__manifest__.py \
        addons/sb_material_mrp/tests/test_purchase_line_material_note.py \
        addons/sb_material_mrp/tests/__init__.py
git commit -m "feat(sb_material_mrp): material-aware suggestion note on native PO line (Phase-2b T4)"
```

---

## Task 5: Auto-confirm-below-threshold (Fork-3, gated, default OFF)

**Files:**
- Create: `addons/sb_material_mrp/models/stock_rule.py`
- Create: `addons/sb_material_mrp/models/res_company.py`
- Create: `addons/sb_material_mrp/models/res_config_settings.py`
- Modify: `addons/sb_material_mrp/models/__init__.py`
- Create: `addons/sb_material_mrp/views/res_config_settings_views.xml`
- Modify: `addons/sb_material_mrp/__manifest__.py` (bump `19.0.1.10.0` →
  `19.0.1.11.0`; register the new view)
- Create: `addons/sb_material_mrp/tests/test_auto_confirm_threshold.py`
- Modify: `addons/sb_material_mrp/tests/__init__.py`

**Interfaces:**
- Produces: `res.company.sb_material_po_auto_confirm` (Boolean, default
  `False`).
- Produces: `res.company.sb_material_po_auto_confirm_max_amount`
  (Monetary, default `0.0` — double-gated: leaving this at `0.0` keeps
  auto-confirm inert even if the toggle is on, since the check requires
  `> 0.0`).
- Produces: `res.config.settings` related fields exposing both above on the
  Purchase settings page.
- Produces: `stock.rule._run_buy(self, procurements)` **override** — calls
  `super()._run_buy(procurements)` **first and unchanged** (zero
  PO-creation code added; native `purchase_stock` logic runs exactly as it
  does today), then calls the new
  `self._sb_maybe_auto_confirm_buy_pos(procurements)`.
- Produces: `stock.rule._sb_maybe_auto_confirm_buy_pos(self, procurements)`
  — the **only** call site of `purchase.order.button_confirm()` anywhere
  in the Southbrook Materials modules. For each `(procurement, rule)` with
  a resolved `procurement.values.get("supplier")`: re-derives the PO's
  identity via the **native** `rule._make_po_get_domain(company, values,
  partner)` (reused verbatim, not reinvented), searches for that PO, and —
  only if `company.sb_material_po_auto_confirm` is True AND
  `company.sb_material_po_auto_confirm_max_amount > 0.0` AND
  `po.state == 'draft'` AND `po.amount_total <=` that threshold — logs
  (`_logger.info` + `po.message_post`) and calls `po.button_confirm()`.

### Step 1: Write the failing test

```python
# addons/sb_material_mrp/tests/test_auto_confirm_threshold.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestAutoConfirmThreshold(TransactionCase):
    def _draft_rfq_via_scheduler(self, vendor_name, price=40.0, min_qty=1.0):
        vendor = self.env["res.partner"].create({"name": vendor_name})
        comp_tmpl = self.env["product.template"].create({
            "name": f"{vendor_name} Comp", "is_storable": True, "purchase_ok": True})
        comp = comp_tmpl.product_variant_id
        self.env["product.supplierinfo"].create({
            "partner_id": vendor.id, "product_tmpl_id": comp_tmpl.id,
            "price": price, "min_qty": min_qty})
        comp_tmpl.action_sb_set_route_buy()
        wh = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1)
        self.env["stock.warehouse.orderpoint"].create({
            "product_id": comp.id, "location_id": wh.lot_stock_id.id,
            "warehouse_id": wh.id, "company_id": wh.company_id.id,
            "product_min_qty": 1.0, "product_max_qty": 2.0,
        })
        self.env["stock.rule"].run_scheduler(use_new_cursor=False)
        return self.env["purchase.order"].search([("partner_id", "=", vendor.id)], limit=1)

    def test_default_off_leaves_po_draft(self):
        self.env.company.sb_material_po_auto_confirm = False
        po = self._draft_rfq_via_scheduler("AutoConfirm Off Vendor")
        self.assertTrue(po)
        self.assertEqual(po.state, "draft")

    def test_enabled_under_threshold_auto_confirms(self):
        self.env.company.sb_material_po_auto_confirm = True
        self.env.company.sb_material_po_auto_confirm_max_amount = 1000.0
        po = self._draft_rfq_via_scheduler("AutoConfirm On Vendor", price=40.0, min_qty=1.0)
        self.assertTrue(po)
        self.assertEqual(po.state, "purchase")  # native button_confirm ran

    def test_enabled_over_threshold_stays_draft(self):
        self.env.company.sb_material_po_auto_confirm = True
        self.env.company.sb_material_po_auto_confirm_max_amount = 10.0
        po = self._draft_rfq_via_scheduler("AutoConfirm Over Vendor", price=999.0, min_qty=1.0)
        self.assertTrue(po)
        self.assertEqual(po.state, "draft")

    def test_zero_threshold_never_fires_even_if_enabled(self):
        self.env.company.sb_material_po_auto_confirm = True
        self.env.company.sb_material_po_auto_confirm_max_amount = 0.0
        po = self._draft_rfq_via_scheduler("AutoConfirm ZeroCeiling Vendor")
        self.assertEqual(po.state, "draft")
```

Add `from . import test_auto_confirm_threshold` to
`addons/sb_material_mrp/tests/__init__.py`.

### Step 2: Run to verify it fails

`docker exec v19c-odoo odoo -u sb_material_mrp --test-enable --test-tags sbk_material,sb_geo -d test_sbgeo_b1 --stop-after-init --no-http --http-port=8265`
Expected: FAIL — `sb_material_po_auto_confirm` not a field on `res.company`
(and, absent the override, every test observes `po.state == 'draft'`, so
the "enabled" tests fail their assertion).

### Step 3: Write minimal implementation

```python
# addons/sb_material_mrp/models/res_company.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    sb_material_po_auto_confirm = fields.Boolean(
        string="Auto-Confirm Material RFQs Below Threshold",
        default=False,
        help="Fork-3 (Materials Phase-2 spec, delivered Phase-2b Task 5): "
             "when a draft RFQ the native scheduler generates for a "
             "material component's Buy route + orderpoint is at or under "
             "the amount threshold below, confirm it automatically. "
             "DEFAULT OFF. This is the ONLY place in the Southbrook "
             "Materials modules that calls purchase.order.button_confirm() "
             "-- everywhere else the suggestion is assist-only.",
    )
    sb_material_po_auto_confirm_max_amount = fields.Monetary(
        string="Auto-Confirm Max Amount",
        currency_field="currency_id",
        default=0.0,
        help="Double-gated with the toggle above: a PO auto-confirms only "
             "when the toggle is on AND its amount_total is <= this AND "
             "this is > 0. Leaving this at 0.0 keeps auto-confirm inert "
             "even if the toggle is accidentally left on.",
    )
```

```python
# addons/sb_material_mrp/models/res_config_settings.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    sb_material_po_auto_confirm = fields.Boolean(
        related="company_id.sb_material_po_auto_confirm", readonly=False)
    sb_material_po_auto_confirm_max_amount = fields.Monetary(
        related="company_id.sb_material_po_auto_confirm_max_amount",
        readonly=False, currency_field="currency_id")
```

```python
# addons/sb_material_mrp/models/stock_rule.py
# SPDX-License-Identifier: LGPL-3.0-only
"""Phase-2b Task 5 -- the ONLY permitted purchase.order.button_confirm()
call site in the Southbrook Materials modules (Fork-3: auto-confirm-
below-threshold, default OFF, explicitly gated).

`_run_buy` below calls `super()._run_buy(procurements)` FIRST and
UNCHANGED -- the native `purchase_stock` PO-creation/selection/pricing
logic runs exactly as it does today (verified against
addons/purchase_stock/models/stock_rule.py). Only AFTER that does this
override ever touch the resulting PO, and only to confirm one the native
code already created/updated -- never to write product_id/product_qty/
price_unit/partner_id, and never to create a purchase.order or
purchase.order.line itself.
"""
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StockRule(models.Model):
    _inherit = "stock.rule"

    def _run_buy(self, procurements):
        result = super()._run_buy(procurements)
        self._sb_maybe_auto_confirm_buy_pos(procurements)
        return result

    def _sb_maybe_auto_confirm_buy_pos(self, procurements):
        for procurement, rule in procurements:
            supplier = procurement.values.get("supplier")
            if not supplier:
                continue
            company = rule.company_id or procurement.company_id
            if not company.sb_material_po_auto_confirm:
                continue
            if company.sb_material_po_auto_confirm_max_amount <= 0.0:
                continue
            partner = supplier.partner_id
            domain = rule._make_po_get_domain(company, procurement.values, partner)
            po = self.env["purchase.order"].sudo().search(domain, limit=1)
            if not po or po.state != "draft":
                continue
            if po.amount_total > company.sb_material_po_auto_confirm_max_amount:
                continue
            _logger.info(
                "sb_material_mrp: auto-confirming RFQ %s (%.2f <= threshold "
                "%.2f) for %s -- Phase-2b Task 5, gated, default-off.",
                po.name, po.amount_total,
                company.sb_material_po_auto_confirm_max_amount, partner.display_name,
            )
            po.message_post(
                body=(
                    "Auto-confirmed by Southbrook Materials (Phase-2b Task "
                    "5): amount %.2f <= configured threshold %.2f."
                ) % (po.amount_total, company.sb_material_po_auto_confirm_max_amount)
            )
            po.sudo().button_confirm()
```

Add `from . import res_company`, `from . import res_config_settings`,
`from . import stock_rule` to `addons/sb_material_mrp/models/__init__.py`.

Add the Settings UI (external id grep-verified,
`addons/purchase/views/res_config_settings_views.xml`,
`purchase.res_config_settings_view_form_purchase`):

```xml
<!-- addons/sb_material_mrp/views/res_config_settings_views.xml -->
<?xml version="1.0" encoding="utf-8"?>
<!-- SPDX-License-Identifier: LGPL-3.0-only -->
<odoo>
    <record id="res_config_settings_view_form_sb_material" model="ir.ui.view">
        <field name="name">res.config.settings.view.form.sb.material</field>
        <field name="model">res.config.settings</field>
        <field name="inherit_id" ref="purchase.res_config_settings_view_form_purchase"/>
        <field name="arch" type="xml">
            <xpath expr="//block[last()]" position="after">
                <block title="Southbrook Materials" name="sb_material_settings">
                    <setting id="sb_material_po_auto_confirm_setting"
                             help="Default OFF. Auto-confirm a draft material RFQ under the amount threshold below.">
                        <field name="sb_material_po_auto_confirm"/>
                        <div class="content-group" invisible="not sb_material_po_auto_confirm">
                            <field name="sb_material_po_auto_confirm_max_amount"/>
                        </div>
                    </setting>
                </block>
            </xpath>
        </field>
    </record>
</odoo>
```

> Note: the `//block[last()]` xpath targets the end of the Purchase
> settings page generically. If the installed
> `purchase.res_config_settings_view_form_purchase` arch structure differs
> on this build, the reviewer/implementer should retarget the xpath — the
> two field additions are the deliverable, not the exact xpath string.

Register the new view in `addons/sb_material_mrp/__manifest__.py` `data`
list. Bump `"version"` to `19.0.1.11.0`.

### Step 4: Run to verify it passes

Same command, port 8265. Expected: PASS.

### Step 5: Commit

```bash
git add addons/sb_material_mrp/models/stock_rule.py \
        addons/sb_material_mrp/models/res_company.py \
        addons/sb_material_mrp/models/res_config_settings.py \
        addons/sb_material_mrp/models/__init__.py \
        addons/sb_material_mrp/views/res_config_settings_views.xml \
        addons/sb_material_mrp/__manifest__.py \
        addons/sb_material_mrp/tests/test_auto_confirm_threshold.py \
        addons/sb_material_mrp/tests/__init__.py
git commit -m "feat(sb_material_mrp): gated default-OFF auto-confirm-below-threshold (Phase-2b T5, Fork-3)"
```

---

## Task 6: Docs

**Files:**
- Modify: `addons/sb_material_mrp/README.md`
- Modify: `docs/superpowers/specs/2026-07-25-materials-procurement-phase2-design.md`

- [ ] **Step 1** — Add a "Procurement loop (Phase-2b)" section to the
  README: the UoM conversion helper and when it applies vs. `uom_yield_qty`;
  the orderpoint MAX sync action and the explicit "MIN is never touched"
  boundary; the scheduler proof; the PO-line note fields and their
  non-stored/live-snapshot nature; the auto-confirm toggle, its double
  gate, and that it is the only `button_confirm()` call site. Restate the
  Fork-1 architecture limitation (trigger is still size-blind) prominently.
- [ ] **Step 2** — Append to the spec's "Still deferred (Phase-2b)" line a
  "Delivered (Phase-2b, 2026-07-26): T1 UoM conversion helper, T2
  orderpoint MAX sync, T3 scheduler proof, T4 PO-line assist note, T5
  gated auto-confirm-below-threshold. Still deferred: actual-vs-estimate
  variance reconciliation / waste self-tuning; making the scheduler
  TRIGGER itself size-aware (the Fork-1 split-brain remains)."
- [ ] **Step 3: Commit** —
  `git commit -m "docs(materials): Phase-2b procurement — README + spec delivery note"`

---

## Self-Review

**1. Spec coverage:**
- UoM conversion into an arbitrary vendor UoM via native `_compute_quantity`
  when units share a reference, honest fallback otherwise → **Task 1** ✓
- Orderpoint min/max per material component product per warehouse, derived
  from `material_demand_qty` rollup across open MOs, native config only →
  **Task 2** ✓ (MAX only, by design — MIN stays native/human, documented
  as the Fork-1-adjacent limitation)
- Scheduler → draft RFQ, zero PO-creation code → **Task 3** ✓ (test-only,
  no production code added)
- Suggested-qty transparency on the native PO/RFQ line + a Materials tab,
  read-only assist → **Task 4** ✓
- Auto-confirm-below-threshold, default OFF, gated, logged, sole
  `button_confirm()` site → **Task 5** ✓
- Fork-1 limitation (trigger is still size-blind; `material_demand_qty`
  reaches MAX and the PO-line note, not the trigger) stated prominently at
  the top and re-referenced in Tasks 2 and 4 → ✓
- Every task's core behavior testable with synthetic data; live-data
  dependency explicitly flagged per task in Global Constraints → ✓

**2. Placeholder scan:** No TBD/TODO; every code step shows complete code.
The two "reviewer should retarget the xpath if this build's arch differs"
notes (Tasks 4 and 5) are explicit fallback instructions with a concrete,
already-grep-verified default — not placeholders — mirroring the identical
pattern already used and accepted in the Phase-2a and cutlist-precision
plans.

**3. Type consistency:** `sb_convert_demand_qty(qty, to_uom) -> (float,
bool)` (Task 1) is consumed identically by `mrp.bom.line.
_sb_demand_qty_in_uom` (Task 1) and `purchase.order.line.
_compute_sb_material_suggested_note` (Task 4) — same tuple shape, same
honesty semantics (`is_exact=False` ⇒ input unchanged). `_sb_canonical_demand_uom()`
returns a `uom.uom` recordset (0 or 1) consumed by both. `_sb_open_mo_material_demand_qty()`
(Task 2) returns a plain `float`, consumed identically by Task 2's own sync
action and Task 4's PO-line compute. `res.company` fields (Task 5) are
`Boolean`/`Monetary`, related verbatim onto `res.config.settings` and read
directly in `stock.rule._sb_maybe_auto_confirm_buy_pos`. Consistent across
tasks.
