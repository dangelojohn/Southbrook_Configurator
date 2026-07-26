# Cutlist Precision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give each `mrp.bom.line` an *exact* material demand/weight derived from the specific panels its material represents (via a material→panel-role assignment), replacing the whole-carcass qty-share estimate, while keeping the honesty fallback for unmapped lines.

**Architecture:** A seeded `sb.panel.role` tag model (vocabulary = `sb.cutlist.PANEL_NAMES`) is assigned to materials via `panel_role_ids`. On a BoM, a role is *owned* by a line's material only when exactly one line's material claims it; that line's exact volume = the summed `(L×W×th)` of the panels for its owned roles (material-scoped qty-share when several lines share a material). Unresolvable/ambiguous → today's `_sb_component_share_volume_mm3` estimate, flagged non-exact. Additive; no live number moves until roles are assigned.

**Tech Stack:** Odoo 19.0 CE; Python; `sb_material_core` (material master + roles), `sb_material_mrp` (BoM-line demand/weight), geometry from `southbrook_estimating._compute_panel_dimensions` (unchanged).

## Global Constraints

- Odoo 19.0 CE only. `sb_material_core` and `sb_material_mrp` are LIVE — every change **additive/backcompat**; new fields default empty/False; no stored number changes until a material gets `panel_role_ids`.
- **Honesty contract:** exact number only when role ownership is unambiguously resolvable; otherwise fall back to `_sb_component_share_volume_mm3` (today's estimate) — **never fabricated**. Expose `material_demand_is_exact` so estimate vs fact is visible.
- **LOCKED weight conversion unchanged:** `effective_density(g/cm³) × volume_mm³ / 1e6`, `float_round(...,2,"HALF-UP")`. Cutlist precision changes only the *volume*, never the conversion.
- Reuse `_sb_resolve_geo(line)` and `_compute_panel_dimensions(**geo)` (both live) for geometry — do NOT add a new geometry engine.
- Panel-role vocabulary MUST equal `sb.cutlist.PANEL_NAMES` values (`side_L, side_R, top, bottom, back, shelf, door`) so the post-MO cutlist can converge later — reuse the exact strings.
- LGPL-3 SPDX header on every new Python file. Tests: `TransactionCase`, tags `sbk_material` and `sb_geo`; run `-u <module> --test-enable --test-tags sbk_material,sb_geo -d test_sbgeo_b1 --stop-after-init --no-http --http-port=82XX` in the `v19c-odoo` container after `cp -R addons/{sb_material_core,sb_material_mrp,southbrook_estimating,southbrook_kitchen_3d_configurator} /Users/naadmin/Downloads/Official/V19C/product-configurator/`. A new test file MUST be imported in the module's `tests/__init__.py` — grep the run log to confirm the class actually ran. Use distinct unique `code` per material/family test record.
- Current live versions: `sb_material_core` 19.0.1.5.0, `sb_material_mrp` 19.0.1.6.0.

## File Structure

- `addons/sb_material_core/models/sb_panel_role.py` — **new**: `sb.panel.role` tag model + a `PANEL_ROLE_KEYS` constant.
- `addons/sb_material_core/data/sb_panel_role_data.xml` — **new**: seed the 7 role records (`noupdate`).
- `addons/sb_material_core/models/southbrook_kitchen_material.py` — **modify**: add `panel_role_ids` M2M.
- `addons/sb_material_core/data/material_seed_data.xml` — **modify**: assign `panel_role_ids` to seeded materials (`noupdate`).
- `addons/sb_material_core/migrations/19.0.1.6.0/post-migrate.py` — **new**: assign roles to legacy materials + trigger downstream recompute.
- `addons/sb_material_core/views/southbrook_kitchen_material_views.xml` — **modify**: show `panel_role_ids`.
- `addons/sb_material_mrp/models/mrp_bom.py` — **modify**: role-ownership + exact-volume helpers; wire into the two computes; `material_demand_is_exact`.
- `addons/sb_material_mrp/migrations/19.0.1.7.0/post-migrate.py` — **new**: recompute after wiring.
- `addons/sb_material_mrp/views/mrp_bom_views.xml` — **modify**: show `material_demand_is_exact` on the BoM line.

---

## Task 1: `sb.panel.role` tag model + `panel_role_ids` on material

**Files:**
- Create: `addons/sb_material_core/models/sb_panel_role.py`
- Create: `addons/sb_material_core/data/sb_panel_role_data.xml`
- Modify: `addons/sb_material_core/models/__init__.py` (add `from . import sb_panel_role`)
- Modify: `addons/sb_material_core/models/southbrook_kitchen_material.py` (add `panel_role_ids`)
- Modify: `addons/sb_material_core/views/southbrook_kitchen_material_views.xml` (show the field)
- Modify: `addons/sb_material_core/__manifest__.py` (register data+ version bump 19.0.1.5.0 → 19.0.1.6.0)
- Modify: `addons/sb_material_core/security/ir.model.access.csv` (ACL for `sb.panel.role`)
- Test: `addons/sb_material_core/tests/test_panel_role.py`

**Interfaces:**
- Produces: model `sb.panel.role` (fields: `name` Char, `code` Char unique — one of `side_L/side_R/top/bottom/back/shelf/door`); constant `PANEL_ROLE_KEYS = ("side_L","side_R","top","bottom","back","shelf","door")`; xml_ids `sb_material_core.panel_role_side_l|side_r|top|bottom|back|shelf|door`; `southbrook.kitchen.material.panel_role_ids` (M2M to `sb.panel.role`). Consumed by Tasks 2–4.

- [ ] **Step 1: Write the failing test**

```python
# addons/sb_material_core/tests/test_panel_role.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestPanelRole(TransactionCase):
    def test_seven_roles_seeded(self):
        Role = self.env["sb.panel.role"]
        codes = set(Role.search([]).mapped("code"))
        self.assertTrue(
            {"side_L", "side_R", "top", "bottom", "back", "shelf", "door"} <= codes)

    def test_material_panel_role_ids_assignable(self):
        back = self.env.ref("sb_material_core.panel_role_back")
        mat = self.env["southbrook.kitchen.material"].create({
            "name": "Test Back Mat", "code": "t_backmat",
            "panel_role_ids": [(6, 0, back.ids)]})
        self.assertEqual(mat.panel_role_ids.mapped("code"), ["back"])
```

- [ ] **Step 2: Run to verify it fails** — `docker exec v19c-odoo odoo -u sb_material_core --test-enable --test-tags sbk_material,sb_geo -d test_sbgeo_b1 --stop-after-init --no-http --http-port=8250`. Expected: FAIL (`sb.panel.role` missing).

- [ ] **Step 3: Model + constant**

```python
# addons/sb_material_core/models/sb_panel_role.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields, models

# Vocabulary MUST match sb.cutlist.PANEL_NAMES (southbrook_kitchen_mrp) so the
# post-MO cutlist can converge onto this material<->role link later.
PANEL_ROLE_KEYS = ("side_L", "side_R", "top", "bottom", "back", "shelf", "door")


class SbPanelRole(models.Model):
    _name = "sb.panel.role"
    _description = "Cabinet Panel Role"
    _order = "sequence, code"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)

    _sql = None  # (uniqueness enforced via models.Constraint below)
    _unique_code = models.Constraint("unique(code)", "Panel role code must be unique.")
```

> Note: use the v19 `models.Constraint` idiom already used elsewhere in `sb_material_core` (grep `models.Constraint` for the exact form; do NOT use `_sql_constraints`).

- [ ] **Step 4: Seed data**

```xml
<!-- addons/sb_material_core/data/sb_panel_role_data.xml -->
<?xml version="1.0" encoding="utf-8"?>
<odoo>
  <data noupdate="1">
    <record id="panel_role_side_l" model="sb.panel.role"><field name="name">Side (Left)</field><field name="code">side_L</field><field name="sequence">1</field></record>
    <record id="panel_role_side_r" model="sb.panel.role"><field name="name">Side (Right)</field><field name="code">side_R</field><field name="sequence">2</field></record>
    <record id="panel_role_top" model="sb.panel.role"><field name="name">Top</field><field name="code">top</field><field name="sequence">3</field></record>
    <record id="panel_role_bottom" model="sb.panel.role"><field name="name">Bottom</field><field name="code">bottom</field><field name="sequence">4</field></record>
    <record id="panel_role_back" model="sb.panel.role"><field name="name">Back</field><field name="code">back</field><field name="sequence">5</field></record>
    <record id="panel_role_shelf" model="sb.panel.role"><field name="name">Shelf</field><field name="code">shelf</field><field name="sequence">6</field></record>
    <record id="panel_role_door" model="sb.panel.role"><field name="name">Door</field><field name="code">door</field><field name="sequence">7</field></record>
  </data>
</odoo>
```

- [ ] **Step 5: `panel_role_ids` on material + view + `__init__` + manifest + ACL**

In `southbrook_kitchen_material.py` (`class KitchenMaterial`):
```python
    panel_role_ids = fields.Many2many(
        "sb.panel.role", string="Panel Roles",
        help="Which cabinet panel roles this material makes. Drives exact "
             "per-BoM-line material demand: a line's demand is the summed "
             "area of the panels whose role its material uniquely owns on "
             "that BoM. Leave empty to keep the estimation-grade share.",
    )
```
Add `from . import sb_panel_role` to `models/__init__.py`. Register `data/sb_panel_role_data.xml` (BEFORE `material_seed_data.xml`) in the manifest `data` list and bump `"version"` to `19.0.1.6.0`. Add an `sb.panel.role` ACL row to `security/ir.model.access.csv` (read for base.group_user, full for the material manager group — mirror the existing `material.family` rows). Inherit the material form to show `panel_role_ids` (widget `many2many_tags`) near `family_id`.

- [ ] **Step 6: Run to verify PASS** (same command as Step 2, port 8250). Confirm the test class ran (grep) and 0 failed.

- [ ] **Step 7: Commit**

```bash
git add addons/sb_material_core/models/sb_panel_role.py \
        addons/sb_material_core/data/sb_panel_role_data.xml \
        addons/sb_material_core/models/__init__.py \
        addons/sb_material_core/models/southbrook_kitchen_material.py \
        addons/sb_material_core/views/southbrook_kitchen_material_views.xml \
        addons/sb_material_core/security/ir.model.access.csv \
        addons/sb_material_core/__manifest__.py \
        addons/sb_material_core/tests/test_panel_role.py
git commit -m "feat(sb_material_core): sb.panel.role model + material.panel_role_ids (cutlist T1)"
```

---

## Task 2: Exact-resolution helpers on `mrp.bom.line`

**Files:**
- Modify: `addons/sb_material_mrp/models/mrp_bom.py` (add pure helpers on `class MrpBomLine`)
- Test: `addons/sb_material_mrp/tests/test_cutlist_exact.py`

**Interfaces:**
- Consumes: `_sb_resolve_geo(line)` (live); `Bom._compute_panel_dimensions(**geo)` returning per-role tuples under keys `side_L, side_R, top, bottom, back` (each `(L,W,th)|None`), `shelf` (`(L,W,th)|None`) + `shelf_count` (int), `door` (`(L,W,th)|None`) + `door_count` (int); `line.material_id.panel_role_ids` (Task 1); `line.material_id.thickness_mm`.
- Produces:
  - `_sb_role_to_lines(line)` → dict `{role_code: recordset of BoM lines whose material claims it}` for `line.bom_id`.
  - `_sb_line_owned_roles(line)` → set of role codes this line's material **uniquely** owns on the BoM (claimed by exactly one distinct material, and that material is this line's).
  - `_sb_line_exact_volume_mm3(line, _dims_cache=None)` → Float, the summed `(L×W×th)` of this line's owned-role panels (thickness = `material_id.thickness_mm` if >0 else the panel's own `th`; `shelf`×`shelf_count`, `door`×`door_count`), then material-scoped qty-share among same-`material_id` lines; or `None` when nothing is unambiguously owned (caller falls back).

- [ ] **Step 1: Write the failing test**

```python
# addons/sb_material_mrp/tests/test_cutlist_exact.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestCutlistExact(TransactionCase):
    def _geo_variant(self):
        t = self.env["product.template"].create({"name": "Cab CL"})
        t.product_variant_id.write({
            "sb_width_mm": 600, "sb_height_mm": 720, "sb_depth_mm": 580,
            "sb_panel_family": "base", "sb_door_count": 1, "sb_drawer_count": 0,
            "sb_finished_sides": "none"})
        return t

    def _mat(self, code, role_codes, thickness=19.05):
        fam = self.env["material.family"].create({"name": code, "code": code})
        roles = self.env["sb.panel.role"].search([("code", "in", role_codes)])
        return self.env["southbrook.kitchen.material"].create({
            "name": code, "code": code, "family_id": fam.id, "density": 0.68,
            "weight_source": "density_volume", "thickness_mm": thickness,
            "panel_role_ids": [(6, 0, roles.ids)]})

    def test_back_line_gets_back_panel_area_exactly(self):
        t = self._geo_variant()
        carcass = self._mat("cl_carc", ["side_L", "side_R", "top", "bottom"])
        back = self._mat("cl_back", ["back"], thickness=6.35)
        cp = self.env["product.product"].create({"name": "carc"}); cp.product_tmpl_id.material_id = carcass.id
        bp = self.env["product.product"].create({"name": "bk"}); bp.product_tmpl_id.material_id = back.id
        bom = self.env["mrp.bom"].create({"product_tmpl_id": t.id, "product_id": t.product_variant_id.id})
        cl = self.env["mrp.bom.line"].create({"bom_id": bom.id, "product_id": cp.id, "product_qty": 1})
        bl = self.env["mrp.bom.line"].create({"bom_id": bom.id, "product_id": bp.id, "product_qty": 1})
        # back line uniquely owns "back" -> exact volume equals the back panel L*W*6.35
        v = bl._sb_line_exact_volume_mm3(bl)
        self.assertIsNotNone(v)
        self.assertGreater(v, 0.0)
        # carcass line owns 4 box panels; its exact volume > the single back panel's
        self.assertGreater(cl._sb_line_exact_volume_mm3(cl), v)

    def test_ambiguous_role_returns_none(self):
        t = self._geo_variant()
        a = self._mat("cl_a", ["shelf"]); b = self._mat("cl_b", ["shelf"])
        pa = self.env["product.product"].create({"name": "a"}); pa.product_tmpl_id.material_id = a.id
        pb = self.env["product.product"].create({"name": "b"}); pb.product_tmpl_id.material_id = b.id
        bom = self.env["mrp.bom"].create({"product_tmpl_id": t.id, "product_id": t.product_variant_id.id})
        la = self.env["mrp.bom.line"].create({"bom_id": bom.id, "product_id": pa.id, "product_qty": 1})
        self.env["mrp.bom.line"].create({"bom_id": bom.id, "product_id": pb.id, "product_qty": 1})
        self.assertIsNone(la._sb_line_exact_volume_mm3(la))  # shelf claimed by 2 materials
```

- [ ] **Step 2: Run to verify it fails** (port 8251). Expected: FAIL (`_sb_line_exact_volume_mm3` missing).

- [ ] **Step 3: Implement the helpers** (on `class MrpBomLine`, near `_sb_component_share_volume_mm3`):

```python
    def _sb_line_owned_roles(self):
        """Role codes this line's material UNIQUELY owns on its BoM: a role
        claimed (via material.panel_role_ids) by exactly one distinct material
        across the BoM's lines, and that material is this line's. Ambiguous
        roles (claimed by >1 material) are excluded -> caller falls back."""
        self.ensure_one()
        mat = self.material_id
        if not mat or not mat.panel_role_ids:
            return set()
        # role_code -> set of distinct material ids claiming it on this BoM
        claim = {}
        for line in self.bom_id.bom_line_ids:
            m = line.material_id
            if not m:
                continue
            for role in m.panel_role_ids:
                claim.setdefault(role.code, set()).add(m.id)
        return {r.code for r in mat.panel_role_ids
                if len(claim.get(r.code, ())) == 1}

    def _sb_line_exact_volume_mm3(self, line, _dims_cache=None):
        """Exact panel volume (mm3) for `line` from the panels whose role its
        material uniquely owns; material-scoped qty-share when several lines
        share the material. Returns None when nothing is unambiguously owned
        (caller uses the estimate)."""
        owned = line._sb_line_owned_roles()
        if not owned:
            return None
        geo = line._sb_resolve_geo()
        if not geo:
            return None
        Bom = self.env["mrp.bom"]
        if _dims_cache is None:
            dims = Bom._compute_panel_dimensions(**geo)
        else:
            key = tuple(sorted(geo.items()))
            dims = _dims_cache.get(key)
            if dims is None:
                dims = Bom._compute_panel_dimensions(**geo)
                _dims_cache[key] = dims
        mat_th = line.material_id.thickness_mm or 0.0

        def _vol(p, count=1):
            if not p:
                return 0.0
            th = mat_th if mat_th > 0 else p[2]
            return p[0] * p[1] * th * count

        total = 0.0
        for role in owned:
            if role in ("side_L", "side_R", "top", "bottom", "back"):
                total += _vol(dims.get(role))
            elif role == "shelf":
                total += _vol(dims.get("shelf"), dims.get("shelf_count") or 0)
            elif role == "door":
                total += _vol(dims.get("door"), dims.get("door_count") or 0)
        # material-scoped share: split this material's owned-panel total across
        # sibling lines of the SAME material by product_qty (per-unit result,
        # since _weight_for_qty multiplies by product_qty downstream).
        same = self.bom_id.bom_line_ids.filtered(
            lambda l: l.material_id == line.material_id)
        tot_qty = sum(same.mapped("product_qty")) or line.product_qty or 1.0
        return total / tot_qty
```

- [ ] **Step 4: Run to verify PASS** (port 8251). Confirm class ran + 0 failed.

- [ ] **Step 5: Commit**

```bash
git add addons/sb_material_mrp/models/mrp_bom.py addons/sb_material_mrp/tests/test_cutlist_exact.py
git commit -m "feat(sb_material_mrp): exact per-line panel-role volume helpers (cutlist T2)"
```

---

## Task 3: Wire exact volume into demand/weight + `material_demand_is_exact` + recompute

**Files:**
- Modify: `addons/sb_material_mrp/models/mrp_bom.py` (`_compute_component_weight`, `_compute_material_demand_qty`, add `material_demand_is_exact`; extend `@api.depends`)
- Create: `addons/sb_material_mrp/migrations/19.0.1.7.0/post-migrate.py`
- Modify: `addons/sb_material_mrp/__manifest__.py` (version 19.0.1.6.0 → 19.0.1.7.0)
- Test: `addons/sb_material_mrp/tests/test_cutlist_exact.py` (extend)

**Interfaces:**
- Consumes: `_sb_line_exact_volume_mm3` (Task 2), `_sb_component_share_volume_mm3` (live fallback).
- Produces: `mrp.bom.line.material_demand_is_exact` (Boolean, stored, computed) — True when the line used an exact per-role volume, False when it fell back to the estimate.

- [ ] **Step 1: Write the failing test** (append to `test_cutlist_exact.py`):

```python
    def test_demand_is_exact_flag_and_value(self):
        t = self._geo_variant()
        back = self._mat("cl_back2", ["back"], thickness=6.35)
        bp = self.env["product.product"].create({"name": "bk2"}); bp.product_tmpl_id.material_id = back.id
        bom = self.env["mrp.bom"].create({"product_tmpl_id": t.id, "product_id": t.product_variant_id.id})
        bl = self.env["mrp.bom.line"].create({"bom_id": bom.id, "product_id": bp.id, "product_qty": 1})
        self.assertTrue(bl.material_demand_is_exact)
        self.assertGreater(bl.material_demand_qty, 0.0)

    def test_unmapped_line_falls_back_and_flag_false(self):
        t = self._geo_variant()
        fam = self.env["material.family"].create({"name": "cl_nr", "code": "cl_nr"})
        m = self.env["southbrook.kitchen.material"].create({
            "name": "cl_norole", "code": "cl_norole", "family_id": fam.id,
            "density": 0.68, "weight_source": "density_volume", "thickness_mm": 19.05})
        p = self.env["product.product"].create({"name": "nr"}); p.product_tmpl_id.material_id = m.id
        bom = self.env["mrp.bom"].create({"product_tmpl_id": t.id, "product_id": t.product_variant_id.id})
        bl = self.env["mrp.bom.line"].create({"bom_id": bom.id, "product_id": p.id, "product_qty": 1})
        self.assertFalse(bl.material_demand_is_exact)   # no roles -> estimate
        self.assertGreater(bl.material_demand_qty, 0.0)  # still non-zero (share)
```

- [ ] **Step 2: Run to verify it fails** (port 8252). Expected: FAIL (`material_demand_is_exact` missing).

- [ ] **Step 3: Add the flag field + wire both computes**

Field on `class MrpBomLine`:
```python
    material_demand_is_exact = fields.Boolean(
        string="Exact (cutlist)", compute="_compute_material_demand_qty",
        store=True,
        help="True when this line's demand/weight came from the exact panels "
             "its material uniquely owns; False when it fell back to the "
             "estimation-grade carcass share.")
```

In `_compute_material_demand_qty`, for the `density_volume`/`density_area` branch, prefer the exact volume:
```python
            if src in ("density_volume", "density_area"):
                exact = line._sb_line_exact_volume_mm3(line)
                if exact is not None:
                    vol = exact
                    line.material_demand_is_exact = True
                else:
                    vol = line._sb_component_share_volume_mm3(line)
                    line.material_demand_is_exact = False
                if not vol:
                    line.material_demand_qty = 0.0
                    continue
                th = line.material_id.thickness_mm or line._SB_DEFAULT_SHEET_THICKNESS_MM
                line.material_demand_qty = vol * line.product_qty / th / 1_000_000.0
            else:
                line.material_demand_is_exact = False
                # (linear / per_unit / passthrough branches unchanged)
```
Apply the SAME exact-first / fallback selection in `_compute_component_weight` (use `_sb_line_exact_volume_mm3` when not None, else `_sb_component_share_volume_mm3`), so weight and demand agree on which volume they used. Thread a shared `_dims_cache` dict through both loops (as the weight compute already does).

Extend BOTH computes' `@api.depends` with: `"material_id.panel_role_ids"`, `"bom_id.bom_line_ids.material_id"` (ownership depends on sibling materials — already present for demand from the prior fix; ensure weight has it too).

- [ ] **Step 4: Recompute migration**

```python
# addons/sb_material_mrp/migrations/19.0.1.7.0/post-migrate.py
# SPDX-License-Identifier: LGPL-3.0-only
"""19.0.1.7.0 — recompute demand/weight now that exact panel-role volume is
wired (idempotent; recomputing stored computes is always safe)."""
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
    for fname in ("material_demand_qty", "material_demand_is_exact",
                  "component_weight_kg", "component_volume_mm3"):
        env.add_to_compute(lines._fields[fname], lines)
    lines.flush_recordset(["material_demand_qty", "material_demand_is_exact",
                           "component_weight_kg", "component_volume_mm3"])
    _logger.info("cutlist 19.0.1.7.0: recomputed %s lines (from %s).", len(lines), version)
```
Bump `sb_material_mrp` manifest to `19.0.1.7.0`.

- [ ] **Step 5: Run to verify PASS** (port 8252). Confirm both new tests ran + migration fired + 0 failed + existing tests unchanged (regression gate).

- [ ] **Step 6: Commit**

```bash
git add addons/sb_material_mrp/models/mrp_bom.py \
        addons/sb_material_mrp/migrations/19.0.1.7.0/post-migrate.py \
        addons/sb_material_mrp/__manifest__.py \
        addons/sb_material_mrp/tests/test_cutlist_exact.py
git commit -m "feat(sb_material_mrp): use exact panel-role volume for demand/weight + exact flag (cutlist T3)"
```

---

## Task 4: Seed panel roles on standard/legacy materials + surface the flag + recompute

**Files:**
- Modify: `addons/sb_material_core/data/material_seed_data.xml` (add `panel_role_ids` to seeded materials)
- Create: `addons/sb_material_core/migrations/19.0.1.6.0/post-migrate.py` (assign roles to legacy materials + trigger recompute)
- Modify: `addons/sb_material_mrp/views/mrp_bom_views.xml` (show `material_demand_is_exact`)
- Test: `addons/sb_material_core/tests/test_panel_role.py` (extend — seeded materials carry roles)

**Interfaces:**
- Consumes: `panel_role_ids` (Task 1), the role xml_ids, seeded material xml_ids (`mat_mdf_34`, `mat_ply_34`, `mat_ply_14_back`, `mat_melamine_34`, `mat_mel_58`, `mat_hardboard_14`, …).

**Role assignment (standard defaults, correctable):**
- Carcass box sheet goods (`mat_mdf_34`, `mat_particle_34`, `mat_melamine_34`, `mat_mel_58`, `mat_ply_34`) → `side_L, side_R, top, bottom` (+ `shelf` for the ones used as shelves — assign `shelf` to `mat_ply_34`/`mat_melamine_34` per shop convention; document).
- Back sheet goods (`mat_ply_14_back`, `mat_hardboard_14`) → `back`.
- (No seeded door-stock material today → door role assigned when a door material is added; leave unassigned now, documented.)

- [ ] **Step 1: Write the failing test** (append to `test_panel_role.py`):

```python
    def test_seeded_back_material_has_back_role(self):
        back = self.env.ref("sb_material_core.mat_ply_14_back")
        self.assertIn("back", back.panel_role_ids.mapped("code"))

    def test_seeded_carcass_material_has_box_roles(self):
        mel = self.env.ref("sb_material_core.mat_melamine_34")
        self.assertTrue({"side_L", "side_R", "top", "bottom"}
                        <= set(mel.panel_role_ids.mapped("code")))
```

- [ ] **Step 2: Run to verify it fails** (port 8253). Expected: FAIL (seeded materials have no roles yet).

- [ ] **Step 3: Add `panel_role_ids` to `material_seed_data.xml`** — for each seeded material record, add e.g.:
```xml
    <field name="panel_role_ids" eval="[(6,0,[ref('panel_role_side_l'),ref('panel_role_side_r'),ref('panel_role_top'),ref('panel_role_bottom')])]"/>
```
(box roles for carcass materials; `[(6,0,[ref('panel_role_back')])]` for the two back materials; add `panel_role_shelf` where the shop uses that sheet for shelves). Keep `noupdate="1"` so a shop's later edits survive.

- [ ] **Step 4: Legacy-material migration** — `addons/sb_material_core/migrations/19.0.1.6.0/post-migrate.py` (mirror the 19.0.1.5.0 relink migration idiom): for legacy materials still lacking roles, assign by `code` (e.g. `mdf`/`melamine`/`plywood`/`particle_board`/`solid_wood` → box roles; and if any back-ish legacy exists → back) **only when `panel_role_ids` is empty** (idempotent; never overwrite a shop choice). Then force-recompute dependent `mrp.bom.line` fields (`material_demand_qty`, `material_demand_is_exact`, `component_weight_kg`, `component_volume_mm3`) — the same unconditional recompute the 19.0.1.6.0 mrp migration uses, guarded for when `sb_material_mrp` isn't installed.

- [ ] **Step 5: View** — inherit the BoM form's `bom_line_ids` list (`mrp.mrp_bom_form_view`) to show `material_demand_is_exact` (widget `boolean_toggle`, `optional="show"`) beside `material_demand_qty`.

- [ ] **Step 6: Run to verify PASS** (port 8253). Confirm the new tests ran + migration fired + 0 failed.

- [ ] **Step 7: Commit**

```bash
git add addons/sb_material_core/data/material_seed_data.xml \
        addons/sb_material_core/migrations/19.0.1.6.0/post-migrate.py \
        addons/sb_material_mrp/views/mrp_bom_views.xml \
        addons/sb_material_core/tests/test_panel_role.py
git commit -m "feat(materials): seed panel roles on materials + surface exact flag (cutlist T4)"
```

---

## Task 5: Docs

**Files:**
- Modify: `addons/sb_material_mrp/README.md` (add a "Cutlist precision" section)
- Modify: `docs/superpowers/specs/2026-07-26-cutlist-precision-design.md` (append a "Delivered" note)

- [ ] **Step 1** — Document: the `panel_role` model + `material.panel_role_ids`; exact-when-uniquely-owned resolution; `material_demand_is_exact`; the honesty fallback; what's deferred (sb.cutlist convergence, density_area, nesting).
- [ ] **Step 2** — Append "Delivered (cutlist precision, 2026-07-26): T1–T5" + the live version numbers to the spec.
- [ ] **Step 3: Commit** — `git commit -m "docs(materials): cutlist precision — README + spec delivery note (cutlist T5)"`

---

## Self-Review

**Spec coverage:** role vocabulary=`sb.cutlist.PANEL_NAMES` (T1) ✓; material→role assignment (T1, seeded T4) ✓; exact per-line = uniquely-owned panels (T2) ✓; material-scoped share for N-same-material (T2) ✓; honesty fallback + `is_exact` flag (T3) ✓; back & door first-class (T2 handles `back`/`door` roles; door area via `door_count`) ✓; additive/no-move-until-assigned (all fields default empty; recompute explicit) ✓; deferred items untouched ✓.

**Placeholder scan:** none — every code step has complete code; the two "assign per shop convention, document" notes are explicit curation decisions with a stated default, not placeholders.

**Type consistency:** `_sb_line_exact_volume_mm3(line, _dims_cache=None)` returns `float|None`; callers (T3) branch on `is not None`. `_sb_line_owned_roles()` returns `set[str]` of role codes; matched against `_compute_panel_dimensions` keys (`side_L/side_R/top/bottom/back/shelf/door`). `panel_role_ids` M2M ↔ `sb.panel.role.code`. `material_demand_is_exact` Boolean stored, computed by `_compute_material_demand_qty`. Consistent across tasks.
