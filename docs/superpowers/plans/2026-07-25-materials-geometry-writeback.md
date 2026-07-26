# Materials Phase-2 Geometry Writeback — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Persist a configured cabinet's `width_mm/height_mm/depth_mm` (+ the few panel-cut inputs) on the product variant so `sb_material_mrp._panel_volume_mm3()` produces **real** carcass panel volume instead of `0.0` — lighting up MO material weights (and the Phase-1 dormant weight KPIs), then (increment B) honoring per-placement drag-resize/filler overrides.

**Architecture:** Two increments. **A (per-variant):** new stored fields on `product.product` in `southbrook_estimating`, populated at OCA variant-creation time from the already-written `_extract_cabinet_inputs()`, read back by `_panel_volume_mm3` which now sums `_compute_panel_dimensions` panel volumes (each panel is `(l,w,thickness)`). **B (per-instance):** thread `southbrook.kitchen.design.line` W/H/D (incl. overrides) through to an `mrp.bom.line` override that `_panel_volume_mm3` prefers over the variant default.

**Tech Stack:** Odoo 19.0 CE; `southbrook_estimating`, `sb_material_mrp`, `southbrook_kitchen_3d_configurator` (all LIVE); OCA `product_configurator`.

## Global Constraints
- Odoo 19.0 CE only. TDD; tests on isolated DB `test_sbgeo` in the `v19c-odoo` container (writable mount `/Users/naadmin/Downloads/Official/V19C/product-configurator/`). Deploy GATED.
- **Touches LIVE modules** (`southbrook_estimating` + `sb_material_mrp` are in production) — every change backcompat; cross-module reads soft-guarded (`hasattr`/registry checks) since `sb_material_mrp` and `southbrook_kitchen_3d_configurator` are siblings that may be independently installed.
- **Honesty (no fabrication):** width is customer-accurate (from `attr_width.value_mm`); H/D come from the existing `_SKU_DEFAULTS` table — a *documented interim* (same numbers the 3D preview already shows), NOT invented per-line. `_panel_volume_mm3` must still return `0.0` (never a guess) when dims are genuinely absent.
- Panel volume convention: `_compute_panel_dimensions` returns each panel as `(length_mm, width_mm, thickness_mm)`; volume_mm³ = Σ `l*w*th`. Existing LOCKED weight conversion (`effective_density(g/cm³)*vol_mm3/1e6`, HALF-UP 2dp) is unchanged.
- `git add` ONLY task files (never `-A`/`commit -am`) — unrelated untracked docs exist in the tree.

## File structure
- `addons/southbrook_estimating/models/product_product.py` — **new**: variant fields `sb_width_mm/sb_height_mm/sb_depth_mm` (Integer), `sb_panel_family` (Char), `sb_door_count`/`sb_drawer_count` (Integer), `sb_finished_sides` (Char); a `_sb_geometry_inputs()` reader.
- `addons/southbrook_estimating/models/product_config_session.py` (or existing config model) — override `get_variant_vals`/`create_get_variant` to inject the geometry inputs.
- `addons/southbrook_estimating/__init__.py` / hooks — `post_init_hook` backfill for existing variants.
- `addons/sb_material_mrp/models/mrp_bom.py` — rewrite `_panel_volume_mm3` (A) + line-override preference (B).
- `addons/southbrook_kitchen_3d_configurator/models/kitchen_design.py` + `sale_order_line.py` — thread per-instance dims (B).

---

## INCREMENT A — per-variant geometry writeback

### Task A1: Variant geometry fields + reader on `product.product`
**Files:**
- Create: `addons/southbrook_estimating/models/product_product.py`
- Modify: `addons/southbrook_estimating/models/__init__.py` (add `from . import product_product`)
- Test: `addons/southbrook_estimating/tests/test_geometry_writeback.py`

**Interfaces:**
- Produces: `product.product` fields `sb_width_mm`, `sb_height_mm`, `sb_depth_mm` (Integer, mm), `sb_panel_family` (Char, default `"base"`), `sb_door_count` (Integer, default 1), `sb_drawer_count` (Integer, default 0), `sb_finished_sides` (Char, default `"none"`); method `_sb_geometry_inputs()` → `dict(width_mm,height_mm,depth_mm,family,door_count,drawer_count,finished_sides)` or `{}` when width/height/depth are all 0.

- [ ] **Step 1: failing test** — assert the fields exist and `_sb_geometry_inputs()` returns `{}` for a variant with no dims:
```python
from odoo.tests import TransactionCase, tagged
@tagged("post_install", "-at_install", "sb_geo")
class TestGeometryWriteback(TransactionCase):
    def test_variant_geometry_fields_and_reader(self):
        p = self.env["product.product"].create({"name": "Cab A"})
        for f in ("sb_width_mm","sb_height_mm","sb_depth_mm","sb_panel_family",
                  "sb_door_count","sb_drawer_count","sb_finished_sides"):
            self.assertIn(f, p._fields)
        self.assertEqual(p._sb_geometry_inputs(), {})  # all dims zero -> empty
        p.write({"sb_width_mm": 600, "sb_height_mm": 762, "sb_depth_mm": 600})
        self.assertEqual(p._sb_geometry_inputs()["width_mm"], 600)
```
- [ ] **Step 2: run — expect FAIL** (fields/method absent). Recipe: copy `southbrook_estimating` (+deps) into the mount, `-i southbrook_estimating --test-enable --test-tags sb_geo -d test_sbgeo1 --stop-after-init --no-http --http-port=8190`.
- [ ] **Step 3: implement** `product_product.py`:
```python
from odoo import models, fields

class ProductProduct(models.Model):
    _inherit = "product.product"

    sb_width_mm = fields.Integer("Cabinet Width (mm)", help="Configured outer width; set at variant creation for the Materials weight calc.")
    sb_height_mm = fields.Integer("Cabinet Height (mm)")
    sb_depth_mm = fields.Integer("Cabinet Depth (mm)")
    sb_panel_family = fields.Char("Panel Family", default="base")
    sb_door_count = fields.Integer("Door Count", default=1)
    sb_drawer_count = fields.Integer("Drawer Count", default=0)
    sb_finished_sides = fields.Char("Finished Sides", default="none")

    def _sb_geometry_inputs(self):
        self.ensure_one()
        if not (self.sb_width_mm and self.sb_height_mm and self.sb_depth_mm):
            return {}
        return {
            "width_mm": self.sb_width_mm, "height_mm": self.sb_height_mm,
            "depth_mm": self.sb_depth_mm, "family": self.sb_panel_family or "base",
            "door_count": self.sb_door_count, "drawer_count": self.sb_drawer_count,
            "finished_sides": self.sb_finished_sides or "none",
        }
```
- [ ] **Step 4: run — expect PASS.**
- [ ] **Step 5: commit** `feat(southbrook_estimating): variant geometry fields + _sb_geometry_inputs reader`

### Task A2: Populate geometry at variant creation
**Files:**
- Modify: `addons/southbrook_estimating/models/product_config_session.py` (the model inheriting `product.config.session`; if named differently, the file that already overrides config-session behavior — grep `_extract_cabinet_inputs` to confirm it's `product_config_line.py`'s class; add the override in the session model). Add: `from . import product_config_session` to `models/__init__.py` if new.
- Test: same test file.

**Interfaces:**
- Consumes: `self._extract_cabinet_inputs()` (returns family, door_count, drawer_count, width_mm, height_mm, depth_mm, finished_sides — confirm exact return shape at `product_config_line.py:178`), and A1's variant fields.
- Produces: a `product.product` created via `create_get_variant` carries `sb_width_mm/...` from the session's `_extract_cabinet_inputs()`.

- [ ] **Step 1: failing test** — build a variant through a config session for a known SKU and assert dims land:
```python
    def test_variant_created_via_config_gets_geometry(self):
        # find a configurable cabinet template with a default_code in _SKU_DEFAULTS
        tmpl = self.env.ref("southbrook_estimating.base_1dr", raise_if_not_found=False)
        if not tmpl:
            self.skipTest("base_1dr template not present")
        session = self.env["product.config.session"].create({
            "product_tmpl_id": tmpl.product_tmpl_id.id if hasattr(tmpl,"product_tmpl_id") else tmpl.id})
        variant = session.create_get_variant(session.value_ids.ids)
        self.assertTrue(variant.sb_width_mm and variant.sb_height_mm and variant.sb_depth_mm)
```
  (Adjust the ref/xmlid to a real configurable cabinet; confirm `create_get_variant` signature at `product_config.py:915`.)
- [ ] **Step 2: run — expect FAIL** (dims 0 — nothing populates them).
- [ ] **Step 3: implement** — override `get_variant_vals` on the `product.config.session` inheriting model in `southbrook_estimating`:
```python
from odoo import models

class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

    def get_variant_vals(self, value_ids, custom_vals=None, **kw):
        vals = super().get_variant_vals(value_ids, custom_vals=custom_vals, **kw)
        try:
            geo = self._extract_cabinet_inputs()  # existing resolver (product_config_line.py)
        except Exception:
            geo = None
        if geo:
            vals.update({
                "sb_width_mm": int(geo.get("width_mm") or 0),
                "sb_height_mm": int(geo.get("height_mm") or 0),
                "sb_depth_mm": int(geo.get("depth_mm") or 0),
                "sb_panel_family": geo.get("family") or "base",
                "sb_door_count": int(geo.get("door_count") or 1),
                "sb_drawer_count": int(geo.get("drawer_count") or 0),
                "sb_finished_sides": geo.get("finished_sides") or "none",
            })
        return vals
```
  **Verify** `_extract_cabinet_inputs()` is callable on `product.config.session` (it's defined on the session's line/session model per the investigation — confirm `self` has it; if it lives on a different model, call it via the session's relation). Its return keys must match — adjust `.get()` names to the real return dict.
- [ ] **Step 4: run — expect PASS.**
- [ ] **Step 5: commit** `feat(southbrook_estimating): write cabinet geometry onto variant at config time`

### Task A3: Backfill existing variants
**Files:**
- Modify: `addons/southbrook_estimating/__manifest__.py` (add `"post_init_hook": "post_init_backfill_geometry"`), `addons/southbrook_estimating/__init__.py` (define the hook)
- Test: same test file.

**Interfaces:**
- Produces: existing `product.product` rows with a `default_code` in `_SKU_DEFAULTS` (or a resolvable `attr_width`) get `sb_width_mm/...` populated on upgrade.

- [ ] **Step 1: failing test** — a pre-existing variant (no dims) with a known default_code gets backfilled by calling the hook logic directly:
```python
    def test_backfill_sets_geometry_on_existing_variant(self):
        p = self.env["product.product"].create({"name":"Legacy","default_code":"SB-BASE-1DR"})
        self.assertFalse(p.sb_width_mm)
        self.env["product.product"]._sb_backfill_geometry()   # idempotent classmethod-ish
        p.invalidate_recordset()
        self.assertTrue(p.sb_width_mm and p.sb_height_mm and p.sb_depth_mm)
```
- [ ] **Step 2: run — expect FAIL.**
- [ ] **Step 3: implement** a `_sb_backfill_geometry()` model method on `product.product` (in `product_product.py`) that, for variants missing dims, resolves W/H/D from `_SKU_DEFAULTS` (import the constant from the config session model — expose it as a module-level dict or a helper) keyed by `default_code`, and where an `attr_width` value exists on the variant use its `value_mm` for width. Then a `post_init_backfill_geometry(env)` hook in `__init__.py` calling `env["product.product"]._sb_backfill_geometry()`. Only sets rows where dims are currently 0 (idempotent).
- [ ] **Step 4: run — expect PASS.**
- [ ] **Step 5: commit** `feat(southbrook_estimating): post_init backfill of variant geometry from SKU defaults`

### Task A4: `_panel_volume_mm3` returns real volume
**Files:**
- Modify: `addons/sb_material_mrp/models/mrp_bom.py:166-204` (`_panel_volume_mm3`)
- Test: `addons/sb_material_mrp/tests/test_panel_volume.py`

**Interfaces:**
- Consumes: the cabinet variant's `_sb_geometry_inputs()` (A1), `mrp.bom._compute_panel_dimensions(**inputs)` (southbrook_estimating).
- Produces: `_panel_volume_mm3(line)` returns Σ carcass-panel `l*w*th` (side_L, side_R, top, bottom, back, shelf×shelf_count) when the cabinet variant has geometry; `0.0` otherwise (unchanged honesty contract).

- [ ] **Step 1: failing test** — a cabinet variant WITH geometry + a density_volume carcass material yields non-zero volume:
```python
from odoo.tests import TransactionCase, tagged
@tagged("post_install","-at_install","sbk_material")
class TestPanelVolume(TransactionCase):
    def test_panel_volume_nonzero_with_geometry(self):
        variant = self.env["product.product"].create(
            {"name":"Cab","sb_width_mm":600,"sb_height_mm":762,"sb_depth_mm":600,
             "sb_panel_family":"base","sb_door_count":1})
        bom = self.env["mrp.bom"].create({"product_tmpl_id":variant.product_tmpl_id.id,
                                          "product_id":variant.id})
        # a density_volume material component line
        mat = self.env["southbrook.kitchen.material"].search([("weight_source","=","density_volume")],limit=1)
        line = self.env["mrp.bom.line"].create({"bom_id":bom.id,"product_id":mat.product_variant_id.id if hasattr(mat,'product_variant_id') else variant.id,"product_qty":1})
        vol = line._panel_volume_mm3(line)
        self.assertGreater(vol, 0.0)
```
  (Wire the material→product link the way the bridge's `_resolve_material` expects; the reviewer/impl adjusts to the real material→product wiring.)
- [ ] **Step 2: run — expect FAIL** (returns 0.0 today).
- [ ] **Step 3: implement** — replace the body of `_panel_volume_mm3` (keep the `_compute_panel_dimensions`-missing guard):
```python
    def _panel_volume_mm3(self, line):
        Bom = self.env["mrp.bom"]
        if not hasattr(Bom, "_compute_panel_dimensions"):
            return 0.0
        cab = line.bom_id.product_id or line.bom_id.product_tmpl_id.product_variant_id
        geo = cab._sb_geometry_inputs() if hasattr(cab, "_sb_geometry_inputs") else {}
        if not geo:
            _logger.debug("_panel_volume_mm3: no geometry on variant %s (line %s) -> 0.0",
                          cab.id, line.id)
            return 0.0
        dims = Bom._compute_panel_dimensions(**geo)
        total = 0.0
        for key in ("side_L", "side_R", "top", "bottom", "back"):
            p = dims.get(key)
            if p:
                total += p[0] * p[1] * p[2]
        shelf = dims.get("shelf")
        if shelf:
            total += shelf[0] * shelf[1] * shelf[2] * (dims.get("shelf_count") or 0)
        return total
```
  Note (document in a comment): doors are excluded — a door is typically a different material; Increment-B / a precision pass maps panel-type→material. For A, a density_volume line = the carcass sheet good (sides/top/bottom/back/shelves).
- [ ] **Step 4: run — expect PASS**; also re-run the existing `sbk_material` suite → still green (weights that were 0.0 now non-zero; adjust any test that hardcoded 0.0-weight expectations, noting the change).
- [ ] **Step 5: commit** `feat(sb_material_mrp): _panel_volume_mm3 reads variant geometry -> real carcass volume`

### Task A5: Increment-A install + full suite
- [ ] **Step 1:** on fresh `test_sbgeo_a`, `-i sb_material_mrp,southbrook_estimating --test-enable --test-tags sb_geo,sbk_material --stop-after-init --no-http --http-port=8191`.
- [ ] **Step 2:** confirm all `sb_geo` + `sbk_material` green; a configured cabinet's MO shows non-zero `material_weight_total`. Classify any pre-existing baseline failures. Record "Increment A green" in the ledger.

---

## INCREMENT B — per-instance (drag-resize / filler) overrides  *(after A)*

### Task B1: `mrp.bom.line` geometry override fields
**Files:** Modify `addons/sb_material_mrp/models/mrp_bom.py` (add fields on the `mrp.bom.line` inherit); Test: `test_panel_volume.py`.
**Interfaces:** Produces `mrp.bom.line.sb_line_width_mm/sb_line_height_mm/sb_line_depth_mm` (Integer, default 0 = "use variant").
- [ ] Steps: TDD — add the three Integer fields (default 0); test they exist and default 0. Commit `feat(sb_material_mrp): per-line geometry override fields`.

### Task B2: `_panel_volume_mm3` prefers line-level dims
**Files:** Modify `_panel_volume_mm3` (sb_material_mrp/models/mrp_bom.py); Test: `test_panel_volume.py`.
**Interfaces:** Consumes B1 fields.
- [ ] **Step 1: failing test** — a bom.line with `sb_line_width_mm=900` (variant is 600) yields a volume matching a 900-wide cabinet, not 600.
- [ ] **Step 2: run — FAIL.**
- [ ] **Step 3: implement** — in `_panel_volume_mm3`, before reading the variant, build `geo` from the line's own dims when all three `sb_line_*` are set (>0), merging the variant's family/door_count/etc.:
```python
        line_geo = {}
        if line.sb_line_width_mm and line.sb_line_height_mm and line.sb_line_depth_mm:
            base = cab._sb_geometry_inputs() if hasattr(cab, "_sb_geometry_inputs") else {}
            line_geo = {**base, "width_mm": line.sb_line_width_mm,
                        "height_mm": line.sb_line_height_mm, "depth_mm": line.sb_line_depth_mm}
        geo = line_geo or (cab._sb_geometry_inputs() if hasattr(cab, "_sb_geometry_inputs") else {})
```
- [ ] **Step 4: run — PASS.** Commit `feat(sb_material_mrp): _panel_volume_mm3 prefers per-line geometry override`

### Task B3: Thread 3D-configurator per-instance dims to the BoM line
**Files:** Modify `addons/southbrook_kitchen_3d_configurator/models/kitchen_design.py` (`action_create_quotation:1428` — carry `width_in/height_in/depth_in` onto the created `sale.order.line`) + `sale_order_line.py` (persist them, ×25.4→mm) + the BoM-build path that creates `mrp.bom.line` (set `sb_line_*` from the SO line). Test: `southbrook_kitchen_3d_configurator/tests/`.
**Interfaces:** Consumes B1 fields; bridges design.line → SO line → bom.line.
- [ ] **Step 1: failing test** — a design line with a drag-resized `width_in` produces a `mrp.bom.line.sb_line_width_mm` equal to `round(width_in*25.4)` (not the template default).
- [ ] **Step 2: run — FAIL** (dims dropped today at `action_create_quotation:1490-1496`).
- [ ] **Step 3: implement** — add `sb_line_width_mm/height/depth` (or reuse names) on `sale.order.line`; in `action_create_quotation`, set them from the design line's `width_in/height_in/depth_in * 25.4`; in the `mrp.bom` build path, copy them onto the generated `mrp.bom.line`. Soft-guard (only when the 3D configurator supplied real per-instance dims).
- [ ] **Step 4: run — PASS.** Commit `feat: thread 3D-configurator per-instance cabinet dims to the material BoM line`

### Task B4: Increment-B install + suite
- [ ] Fresh DB `-i sb_material_mrp,southbrook_estimating,southbrook_kitchen_3d_configurator --test-enable --test-tags sb_geo,sbk_material` + the 3D-configurator tests → all green; a drag-resized cabinet yields a weight reflecting its placed size. Record "Increment B green".

---

## Deploy (GATED — separate go-ahead)
Consolidated `-u southbrook_estimating,sb_material_mrp` (+`southbrook_kitchen_3d_configurator` for B) on live `southbrook` → restart → smoke (configure a cabinet, confirm MO `material_weight_total` non-zero). Pre-deploy backup; run the install **detached** (`setsid`) to survive a tunnel drop (per the Production Media deploy lesson).

## Self-Review
- **Spec coverage:** A1 fields, A2 config-time writeback, A3 backfill, A4 real volume, A5 verify; B1 line fields, B2 line preference, B3 3D-configurator threading, B4 verify — matches the decided A-then-B fork + investigation.
- **Placeholders:** none — each code step has real code; the two spots needing runtime confirmation (`_extract_cabinet_inputs` exact return keys; `create_get_variant` signature) are called out explicitly with the file:line to verify, not left vague.
- **Type consistency:** field names `sb_width_mm/sb_height_mm/sb_depth_mm/sb_panel_family/sb_door_count/sb_drawer_count/sb_finished_sides` (variant) and `sb_line_width_mm/height/depth` (bom.line) used consistently A1↔A2↔A4↔B1↔B2↔B3; `_sb_geometry_inputs()` return dict keys match `_compute_panel_dimensions(**geo)` params.
