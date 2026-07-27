# Prebuilt Sample Kitchen Templates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement task-by-task. Steps use checkbox (`- [x]`) syntax.

**Spec (the authority):** `docs/superpowers/specs/2026-07-27-kitchen-templates-design.md`
**Gap investigation (file:line ground truth):** `/private/tmp/claude-502/-Users-naadmin/30f764c9-d9ab-4b10-9bc7-d9348ab43200/scratchpad/sdd-briefs/ktmpl-investigation.md`
**Catalog data input (T4 only):** `/private/tmp/claude-502/-Users-naadmin/30f764c9-d9ab-4b10-9bc7-d9348ab43200/scratchpad/sdd-briefs/ktmpl-catalog-design.md`
**Worktree:** `/Users/naadmin/sb_ktmpl` (branch `feat/kitchen-templates`, at main `4e25f39`)

**Goal:** A rep/customer starts from a prebuilt sample kitchen: pick a template (shape thumbnail), a cabinet count, a module width, and appliance sizes — the design instantiates as canonical `southbrook.kitchen.design.line` records and the EXISTING `action_auto_arrange` pipeline derives every pose, corner, and filler. Then reorient/swap via a server-side manipulation API.

**Architecture:** Templates are pure DATA (`southbrook.kitchen.template` + `.line` slots: wall + run_seq + type + width — no coordinates). Instantiation = slot→product resolution + canonical line creation + `action_auto_arrange(sync=True)` (`kitchen_design.py:433`), which already owns reset-to-canonical, corner insertion (M2 per-leg claims), rule-driven filler strips (M3), pose derivation via `resolve_and_layout`/`anchor_pose_mm` (`kitchen_layout_engine.py:817/:185`), capacity honesty (`LayoutCapacityExceeded`, `:133`), and the manufacturing mirror. **Zero new geometry code anywhere in this plan.**

**Tech Stack:** Odoo 19 CE; `southbrook_kitchen_3d_configurator` (LIVE, 19.0.5.25.0) only — `southbrook_estimating` is consumed (engine, archetypes, placement rules, `_LAYOUT_SHAPES`), never modified.

## Global Constraints

- **Reuse-first / NO new geometry code.** All poses come from `action_auto_arrange` → `kitchen_layout_engine`. Nothing in this plan computes an x/y/z/rotation. `design.action_reflow` is a thin alias of `action_auto_arrange` — never a second reflow.
- **Corners + fillers are engine-derived, never templated.** Template lines may carry a corner *slot preference* at most (`cabinet_type='corner'` with archetype/pin) — never corner dims/hand; filler slots do not exist in the template model at all (M3 rule-driven derivation + design-level `filler_strategy` own them).
- **Appliances are design lines** (`cabinet_type='appliance'`, `zone='accessory'`, placeholder products + `southbrook.placement.rule` clearance records). `sb.kitchen.appliance` (southbrook_kitchen_workspace) is NOT imported/depended on — wrong coordinate model, hard `project_id`+crm coupling.
- **Honesty.** Unresolved slots become VISIBLE placeholder lines (never skipped, never silently substituted); undersized parametrics BLOCK with a clear message; the room is NEVER silently grown — server side `LayoutCapacityExceeded` already enforces this, T7 removes the client auto-grow violation.
- **LIVE module — additive/backcompat only.** New models, new fields, new selection values, new routes; no renames of existing fields/methods; existing tests stay green. `_sql_constraints` is dead in v19 — use `models.Constraint` (mirror `cabinet_archetype.py:244`).
- **Concurrent session in this module!** Before EVERY commit: `git fetch origin && git merge origin/main` in `/Users/naadmin/sb_ktmpl`, re-read `__manifest__.py`'s version after the merge, and take the next free bump if main moved past the planned number. Resolve conflicts by rebasing our additive changes on top — never discard main's.
- **Versions (planned; renumber upward if main moves):** 19.0.5.25.0 → T1 **5.26.0** → T2 **5.27.0** → T3 **5.28.0** → T4 **5.29.0** → T5 **5.30.0** → T6 **5.31.0** (+ migration folder same version) → T7 **5.32.0** → T8 docs-only, no bump.
- **Tests:** `TransactionCase`, tagged `("post_install", "-at_install", "southbrook", "southbrook_kitchen_3d_configurator", "kitchen_templates")` (house style, see `test_collision_matrix.py:62`). New test files MUST be imported in `tests/__init__.py` with a dated comment (house style). Distinct unique `code`s/names per test record. Grep the log to confirm each new class actually ran.
- **Run recipe (cp-to-mount):** `cp -R /Users/naadmin/sb_ktmpl/addons/{southbrook_estimating,southbrook_kitchen_3d_configurator} /Users/naadmin/Downloads/Official/V19C/product-configurator/` then run in `v19c-odoo`: `-u southbrook_kitchen_3d_configurator --test-enable --test-tags kitchen_templates -d test_sbgeo_b1 --stop-after-init --no-http --http-port=83XX` (unique port per step, assigned below; final full pass uses `--test-tags southbrook_kitchen_3d_configurator`).
- **Naming:** the layout flip is `action_flip_layout` — deliberately NOT "mirror"; `southbrook.design.reconcile` owns "mirror" (manufacturing) across this codebase.
- **JS:** every touched OWL template must pass the pre-commit `scripts/lint-owl-expr.py` hook — keep `t-att`/`t-esc` expressions trivial (tokenizer limits).
- **Room-shape lexicon:** reuse `southbrook.room._LAYOUT_SHAPES` (`southbrook_estimating/models/southbrook_room.py:33`) — no parallel enum, no `single_wall`.

---

### Task 1: Template data models + ACL + views + menu (5.26.0)

**Files:**
- Create: `addons/southbrook_kitchen_3d_configurator/models/kitchen_template.py`
- Modify: `addons/southbrook_kitchen_3d_configurator/models/__init__.py` (import it)
- Create: `addons/southbrook_kitchen_3d_configurator/views/kitchen_template_views.xml`
- Modify: `addons/southbrook_kitchen_3d_configurator/security/ir.model.access.csv`
- Modify: `addons/southbrook_kitchen_3d_configurator/__manifest__.py` (data entry + version 19.0.5.26.0)
- Create: `addons/southbrook_kitchen_3d_configurator/tests/test_kitchen_template_model.py` (+ import in `tests/__init__.py`)

**Interfaces:**
- Produces: `southbrook.kitchen.template` (fields below) and `southbrook.kitchen.template.line`. **No geometry fields on slots** — `wall` + `run_seq` is the whole spatial contract; the engine owns poses.
- Consumed by: T2 (resolver/instantiate), T3 (picker), T4 (data records).

- [x] **Step 1: Write failing tests** (`tests/test_kitchen_template_model.py`):

```python
from psycopg2.errors import UniqueViolation

from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install", "southbrook",
        "southbrook_kitchen_3d_configurator", "kitchen_templates")
class TestKitchenTemplateModel(TransactionCase):

    def _mk_template(self, code, shape="straight"):
        return self.env["southbrook.kitchen.template"].create({
            "name": "T1 fixture %s" % code,
            "code": code,
            "layout_shape": shape,
            "default_room_width_in": 120.0,
            "default_room_depth_in": 96.0,
            "default_room_height_in": 96.0,
            "default_module_width_in": 24.0,
            "min_cabinet_count": 3,
            "max_cabinet_count": 8,
        })

    def test_template_and_slot_create(self):
        tpl = self._mk_template("T1-SW-A")
        slot = self.env["southbrook.kitchen.template.line"].create({
            "template_id": tpl.id,
            "slot_code": "SINK",
            "cabinet_type": "base",
            "wall": "back",
            "run_seq": 10,
            "nominal_width_in": 0.0,   # 0 = takes module width
        })
        self.assertEqual(slot.zone, "base_run")   # zone defaults from type
        self.assertFalse(slot.is_appliance_slot)
        appl = self.env["southbrook.kitchen.template.line"].create({
            "template_id": tpl.id,
            "slot_code": "RANGE",
            "cabinet_type": "appliance",
            "appliance_type": "range",
            "wall": "back",
            "run_seq": 20,
            "nominal_width_in": 30.0,
        })
        self.assertTrue(appl.is_appliance_slot)
        self.assertEqual(appl.zone, "accessory")

    def test_shape_lexicon_is_the_room_lexicon(self):
        tpl = self._mk_template("T1-SW-B")
        room_keys = {k for k, _ in
                     self.env["southbrook.room"]._fields["layout_shape"].selection}
        tpl_keys = {k for k, _ in tpl._fields["layout_shape"].selection}
        self.assertEqual(tpl_keys, room_keys,
                         "template layout_shape must reuse _LAYOUT_SHAPES verbatim")

    @mute_logger("odoo.sql_db")
    def test_code_unique(self):
        self._mk_template("T1-DUP")
        with self.assertRaises(UniqueViolation), self.env.cr.savepoint():
            self._mk_template("T1-DUP")
```

- [x] **Step 2: Run to verify FAIL** (models missing). Port **8301**.
- [x] **Step 3: Implement** `models/kitchen_template.py`:

```python
from odoo import api, fields, models
# Reuse — never fork — the room lexicon and the design-line zone lexicon.
from odoo.addons.southbrook_estimating.models.southbrook_room import _LAYOUT_SHAPES
from .kitchen_design import ZONE_SELECTION, _ZONE_FROM_CABINET_TYPE


class SouthbrookKitchenTemplate(models.Model):
    _name = "southbrook.kitchen.template"
    _description = "Prebuilt Sample Kitchen Template"
    _order = "sequence, id"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True,
                       help="Stable short code (e.g. L-10X8). Referenced by the "
                            "picker's legacy-preset compat map.")
    description = fields.Text()
    layout_shape = fields.Selection(selection=_LAYOUT_SHAPES, required=True,
                                    default="straight")
    default_room_width_in = fields.Float(required=True, default=120.0, digits=(6, 2))
    default_room_depth_in = fields.Float(required=True, default=96.0, digits=(6, 2))
    default_room_height_in = fields.Float(required=True, default=96.0, digits=(6, 2))
    default_module_width_in = fields.Float(required=True, default=24.0, digits=(6, 2))
    min_cabinet_count = fields.Integer(default=1)
    max_cabinet_count = fields.Integer(default=0,
                                       help="0 = engine-bounded only (n_max).")
    default_filler_strategy = fields.Selection(
        [("split", "Split (both ends)"), ("right", "Right side"),
         ("left", "Left side"), ("scribe", "Scribe (no filler)")],
        default="split", required=True)
    default_wall_cab_top_alignment = fields.Selection(
        [("fixed_gap", "Fixed 18\" gap above counter"),
         ("to_ceiling", "Up to ceiling"), ("to_soffit", "Up to soffit")],
        default="fixed_gap", required=True)
    thumbnail = fields.Image(max_width=512, max_height=512,
                             help="Optional manual override; the generated "
                                  "top-view SVG (T3) is the default preview.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    notes = fields.Text()
    line_ids = fields.One2many("southbrook.kitchen.template.line",
                               "template_id", string="Slots", copy=True)

    _code_uniq = models.Constraint(
        "unique (code)",
        "Template code must be unique.",
    )


class SouthbrookKitchenTemplateLine(models.Model):
    _name = "southbrook.kitchen.template.line"
    _description = "Kitchen Template Slot"
    _order = "wall, run_seq, sequence, id"

    template_id = fields.Many2one("southbrook.kitchen.template", required=True,
                                  ondelete="cascade", index=True)
    slot_code = fields.Char(required=True,
                            help="Stable per-template slot id (SINK, RANGE, B1…).")
    cabinet_type = fields.Selection(
        [("base", "Base Cabinet"), ("wall", "Wall Cabinet"),
         ("tall", "Tall Cabinet"), ("corner", "Corner Preference"),
         ("appliance", "Appliance Space")],
        required=True, default="base",
        help="Corner slots carry a PRODUCT PREFERENCE only — the corner "
             "engine (M2 rules-as-data) owns all corner geometry. Fillers "
             "are never templated (M3 derives them).")
    zone = fields.Selection(selection=ZONE_SELECTION, compute="_compute_zone",
                            store=True, readonly=False, precompute=True)
    wall = fields.Selection(
        [("back", "Back"), ("left", "Left"),
         ("right", "Right"), ("front", "Front")],
        required=True, default="back")
    run_seq = fields.Integer(default=0)
    sequence = fields.Integer(default=10)
    nominal_width_in = fields.Float(
        default=0.0, digits=(6, 2),
        help="0 = this slot takes the parametric module width.")
    archetype_id = fields.Many2one("southbrook.cabinet.archetype",
                                   string="Archetype (preferred)")
    product_id = fields.Many2one("product.product", string="Pinned Product",
                                 help="Optional hard pin for fixed quotable BOMs; "
                                      "wins over the archetype resolver.")
    is_appliance_slot = fields.Boolean(compute="_compute_is_appliance", store=True)
    appliance_type = fields.Selection(
        [("range", "Range"), ("fridge", "Fridge"),
         ("dishwasher", "Dishwasher"), ("hood", "Hood"), ("other", "Other")])
    repeat_ok = fields.Boolean(
        default=False,
        help="When the requested cabinet count exceeds this template's module "
             "slots, slots flagged repeat_ok are cloned (in run order) to fill.")
    priority = fields.Integer(
        default=10,
        help="Drop order when the room/count shrinks — HIGHER drops first.")
    notes = fields.Char()

    @api.depends("cabinet_type")
    def _compute_zone(self):
        for line in self:
            if not line.zone:
                line.zone = ("accessory" if line.cabinet_type == "appliance"
                             else _ZONE_FROM_CABINET_TYPE.get(line.cabinet_type,
                                                              "other"))

    @api.depends("cabinet_type")
    def _compute_is_appliance(self):
        for line in self:
            line.is_appliance_slot = line.cabinet_type == "appliance"
```

Then: `models/__init__.py` adds `from . import kitchen_template` (after kitchen_design — it imports from it). ACL rows (append to `security/ir.model.access.csv`, mirroring the existing group xmlids — templates are curated: readonly for readonly+designer, full CRUD for manager only):

```
access_sbk_kitchen_template_readonly,southbrook.kitchen.template (readonly),model_southbrook_kitchen_template,southbrook_kitchen_3d_configurator.group_kitchen_readonly,1,0,0,0
access_sbk_kitchen_template_designer,southbrook.kitchen.template (designer),model_southbrook_kitchen_template,southbrook_kitchen_3d_configurator.group_kitchen_designer,1,0,0,0
access_sbk_kitchen_template_manager,southbrook.kitchen.template (manager),model_southbrook_kitchen_template,southbrook_kitchen_3d_configurator.group_kitchen_manager,1,1,1,1
access_sbk_kitchen_template_line_readonly,southbrook.kitchen.template.line (readonly),model_southbrook_kitchen_template_line,southbrook_kitchen_3d_configurator.group_kitchen_readonly,1,0,0,0
access_sbk_kitchen_template_line_designer,southbrook.kitchen.template.line (designer),model_southbrook_kitchen_template_line,southbrook_kitchen_3d_configurator.group_kitchen_designer,1,0,0,0
access_sbk_kitchen_template_line_manager,southbrook.kitchen.template.line (manager),model_southbrook_kitchen_template_line,southbrook_kitchen_3d_configurator.group_kitchen_manager,1,1,1,1
```

`views/kitchen_template_views.xml`: list (name, code, layout_shape, default_module_width_in, sequence, active) + form (header fields, notebook page "Slots" with editable inline list of line_ids: slot_code, cabinet_type, appliance_type, wall, run_seq, nominal_width_in, archetype_id, product_id, repeat_ok, priority) + `<menuitem id="menu_sbk_kitchen_templates" parent="menu_sbk_root" action="..." sequence="35"/>` (parent `menu_sbk_root` is in `views/kitchen_configurator_views.xml:20`). Manifest: add the view file to `data` (after `kitchen_design_views.xml`), bump version. v19 view-validation traps: only reference fields present in the view; no manual fields in domains.

- [x] **Step 4: Run to verify PASS** — new class green + full module install clean. Port **8302**.
- [x] **Step 5: Merge + Commit** — `git fetch origin && git merge origin/main` (re-check version), then `git commit -m "feat(kitchen_3d): southbrook.kitchen.template data models + ACL + views (templates T1)"`.

---

### Task 2: Resolver + `action_instantiate` + appliance/placeholder products (5.27.0)

**Files:**
- Modify: `addons/southbrook_kitchen_3d_configurator/models/kitchen_template.py` (resolver, `parametric_fit`, `action_instantiate`)
- Modify: `addons/southbrook_kitchen_3d_configurator/models/kitchen_design.py` (line: add `appliance` selection value, `template_slot_code`, `appliance_type`, `is_unresolved`; extend `_compute_position_label`; `_ZONE_FROM_CABINET_TYPE["appliance"]`; add `UNRESOLVED_SLOT` to `_check_production_ready`)
- Modify: `addons/southbrook_kitchen_3d_configurator/models/product_template.py` (add `("appliance", "Appliance Space")` to `southbrook_cabinet_type`)
- Create: `addons/southbrook_kitchen_3d_configurator/data/template_support_products.xml` (appliance-space + unresolved-placeholder products, `noupdate="0"`, plus appliance clearance placement rules)
- Modify: `__manifest__.py` (data entry, version 19.0.5.27.0)
- Create: `tests/test_template_instantiate.py` (+ import in `tests/__init__.py`)

**Interfaces:**
- Consumes: `action_auto_arrange(sync=True)` (`kitchen_design.py:433`), `kitchen_layout_engine.LayoutCapacityExceeded` (`:133`) and `_CORNER_FOOTPRINT_MM`, archetype link `product.template.x_prodboard_archetype_id` (`southbrook_estimating/models/product_template.py:150`), `southbrook.placement.rule` (payload `clearance_front_mm` — already consumed by the M4 motion-envelope validator + tested in `tests/test_collision_matrix.py`).
- Produces (consumed by T3/T4):
  - `template._resolve_slot(slot, width_in) -> product.product` (empty recordset = unresolved; pin > archetype(+width) > cabinet_type+exact-width > empty; appliance slots resolve to the SBK-APPL-* products by `appliance_type`).
  - `template.parametric_fit(cabinet_count=None, module_width_in=None, appliance_widths=None) -> {"ok", "message", "count", "n_max", "module_width_in", "slots": [(slot, width_in), ...]}` — pure math per spec: per run `usable = wall_len − corner_claims − Σ appliance_widths; n_max = floor(usable / module_width)`; corner claims approximated with `kitchen_layout_engine._CORNER_FOOTPRINT_MM / 25.4` per junction touched (UI bound only — the AUTHORITATIVE fit check remains `LayoutCapacityExceeded` at arrange time). Count trimming drops highest-`priority` module slots first; growth clones `repeat_ok` slots; growth with no `repeat_ok` slot → `ok=False`.
  - `template.action_instantiate(partner_id=False, cabinet_count=None, module_width_in=None, appliance_widths=None) -> southbrook.kitchen.design` (savepoint-atomic; `appliance_widths` = `{"range": 36.0, "fridge": 36.0, "dishwasher": 24.0, ...}` keyed by `appliance_type`, overriding slot nominal widths).

- [x] **Step 1: Write failing tests** (`tests/test_template_instantiate.py`):

```python
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook",
        "southbrook_kitchen_3d_configurator", "kitchen_templates")
class TestTemplateInstantiate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Tpl = cls.env["southbrook.kitchen.template"]
        Slot = cls.env["southbrook.kitchen.template.line"]
        base = cls.env.ref("southbrook_estimating.base_2dr")
        sink = cls.env.ref("southbrook_estimating.sink_base")
        wall = cls.env.ref("southbrook_estimating.wall_2dr")
        cls.tpl = Tpl.create({
            "name": "T2 Straight 10ft", "code": "T2-SW-10",
            "layout_shape": "straight",
            "default_room_width_in": 120.0, "default_room_depth_in": 96.0,
            "default_room_height_in": 96.0, "default_module_width_in": 24.0,
            "min_cabinet_count": 2,
        })
        Slot.create([
            {"template_id": cls.tpl.id, "slot_code": "SINK", "cabinet_type": "base",
             "wall": "back", "run_seq": 10, "product_id": sink.product_variant_id.id},
            {"template_id": cls.tpl.id, "slot_code": "B1", "cabinet_type": "base",
             "wall": "back", "run_seq": 20, "repeat_ok": True,
             "product_id": base.product_variant_id.id},
            {"template_id": cls.tpl.id, "slot_code": "RANGE",
             "cabinet_type": "appliance", "appliance_type": "range",
             "wall": "back", "run_seq": 30, "nominal_width_in": 30.0},
            {"template_id": cls.tpl.id, "slot_code": "W1", "cabinet_type": "wall",
             "wall": "back", "run_seq": 10,
             "product_id": wall.product_variant_id.id},
        ])

    def test_instantiate_creates_canonical_lines_with_engine_poses(self):
        design = self.tpl.action_instantiate()
        self.assertEqual(design.state, "configured")
        self.assertEqual(design.room_width_in, 120.0)   # template defaults, untouched
        canon = design.cabinet_line_ids.filtered(
            lambda l: l.layout_role == "canonical")
        self.assertGreaterEqual(len(canon), 4)
        # poses came from auto-arrange, not the template (no template coords exist)
        xs = sorted(canon.filtered(lambda l: l.cabinet_type == "base")
                    .mapped("x_position_in"))
        self.assertEqual(len(xs), len(set(xs)), "base run x positions must be distinct")

    def test_appliance_slot_becomes_design_line(self):
        design = self.tpl.action_instantiate(
            appliance_widths={"range": 36.0})
        appl = design.cabinet_line_ids.filtered(
            lambda l: l.cabinet_type == "appliance")
        self.assertEqual(len(appl), 1)
        self.assertEqual(appl.zone, "accessory")
        self.assertEqual(appl.width_in, 36.0)            # dropdown width wins
        self.assertEqual(appl.appliance_type, "range")
        self.assertIn("APPLIANCE", appl.position_label)

    def test_unresolved_slot_is_visible_placeholder(self):
        arch = self.env["southbrook.cabinet.archetype"].create({
            "code": "T2-NOPRODUCT", "collection": "classic",
            "body_class": "floor", "cabinet_type": "XX"})
        self.env["southbrook.kitchen.template.line"].create({
            "template_id": self.tpl.id, "slot_code": "GHOST",
            "cabinet_type": "base", "wall": "back", "run_seq": 40,
            "archetype_id": arch.id})
        design = self.tpl.action_instantiate()
        ghost = design.cabinet_line_ids.filtered(lambda l: l.is_unresolved)
        self.assertEqual(len(ghost), 1, "unresolved slot must land as a line")
        self.assertTrue(ghost.position_label.startswith("UNRESOLVED"))
        issues = design._check_production_ready()
        self.assertIn("UNRESOLVED_SLOT", [i["code"] for i in issues])

    def test_no_silent_room_growth(self):
        before = self.env["southbrook.kitchen.design"].search_count([])
        with self.assertRaises(UserError):
            self.tpl.action_instantiate(cabinet_count=40)   # cannot fit 10 ft
        self.assertEqual(
            self.env["southbrook.kitchen.design"].search_count([]), before,
            "failed instantiation must not leave a half-built design")

    def test_module_width_parametric(self):
        design = self.tpl.action_instantiate(module_width_in=21.0)
        b1 = design.cabinet_line_ids.filtered(
            lambda l: l.template_slot_code == "B1")
        self.assertEqual(b1.width_in, 21.0)
```

(Adjust the archetype `create` kwargs to `southbrook.cabinet.archetype`'s real required fields — read `cabinet_archetype.py:121-200` first; `body_class`/`collection` are Selections, use valid keys.)

- [x] **Step 2: Run to verify FAIL.** Port **8303**.
- [x] **Step 3: Implement.**

(a) `data/template_support_products.xml` (`noupdate="0"`): five products — `product_tmpl_appl_range` (SBK-APPL-RANGE, "Appliance Space — Range"), `..._fridge`, `..._dishwasher`, `..._hood`, and `product_tmpl_unresolved_slot` (SBK-UNRESOLVED, "Unresolved Template Slot"). All: `type=consu`, `list_price=0.0`, `sale_ok=True`, `purchase_ok=False`, `southbrook_is_cabinet=False` (never in the drag catalog), `southbrook_cabinet_type="appliance"` (appliances) / unset (placeholder), sensible default dims (`southbrook_width_in` 30/36/24/30, height 36/70/34.5/12, depth 25/30/24/18). Plus three `southbrook.placement.rule` records (`anchor_class="run"`, `tier="base"`, `product_tmpl_id` → the appliance template, `payload='{"clearance_front_mm": 610}'` for range/dishwasher, 914 for fridge) so the existing M4 motion-envelope validator enforces appliance clearances with ZERO new validator code.

(b) `kitchen_design.py` additive line changes: append `("appliance", "Appliance Space")` to the line `cabinet_type` selection (`:2120`) and to `product_template.py`'s `southbrook_cabinet_type`; add `"appliance": "accessory"` to `_ZONE_FROM_CABINET_TYPE` (`:2070`); new line fields `template_slot_code = fields.Char(index=True)`, `appliance_type = fields.Selection([...same 5 keys...])`, `is_unresolved = fields.Boolean(default=False)`; extend `_compute_position_label` (`:2331`, add `"is_unresolved", "appliance_type", "width_in", "template_slot_code"` to depends):

```python
        for line in self:
            if line.is_unresolved:
                line.position_label = "UNRESOLVED: %s" % (
                    line.template_slot_code or line.product_id.display_name)
                continue
            if line.cabinet_type == "appliance":
                line.position_label = 'APPLIANCE: %s %g"' % (
                    line.appliance_type or "space", line.width_in or 0)
                continue
            label = type_map.get(line.cabinet_type, line.cabinet_type)
            line.position_label = "%s @ X=%.0f\"" % (label, line.x_position_in)
```

Add to `_check_production_ready` (near the other design-level checks, `:957`ff): every `is_unresolved` line yields `{"code": "UNRESOLVED_SLOT", "severity": "blocking", "message": ...}` (match the file's existing issue-dict shape exactly — read a neighbouring check first).
IMPORTANT: verify the `action_auto_arrange` cab-list loop (`:483-501`) picks appliance lines up — it skips only `("filler", "panel", "corner")`, so `appliance` flows through with `family="base"` (floor-standing run member, correct) and `zone="accessory"` (ground cursor per `sale_order.py:411 _ZONE_LAYOUT` — same floor run as base). Do NOT add appliance to the skip tuple.

(c) `kitchen_template.py`: `_resolve_slot`, `parametric_fit`, `action_instantiate` per the Interfaces contract. Core of `action_instantiate` (real shape — savepoint + honesty):

```python
    def action_instantiate(self, partner_id=False, cabinet_count=None,
                           module_width_in=None, appliance_widths=None):
        self.ensure_one()
        fit = self.parametric_fit(cabinet_count, module_width_in,
                                  appliance_widths)
        if not fit["ok"]:
            raise UserError(fit["message"])          # constrain — never grow
        Design = self.env["southbrook.kitchen.design"]
        Line = self.env["southbrook.kitchen.design.line"]
        unresolved_slot = self.env.ref(
            "southbrook_kitchen_3d_configurator.product_tmpl_unresolved_slot")
        with self.env.cr.savepoint():
            design = Design.create({
                "name": self.name,
                "partner_id": partner_id or False,
                "room_width_in": self.default_room_width_in,
                "room_depth_in": self.default_room_depth_in,
                "room_height_in": self.default_room_height_in,
                "filler_strategy": self.default_filler_strategy,
                "wall_cab_top_alignment": self.default_wall_cab_top_alignment,
            })
            for idx, (slot, width_in) in enumerate(fit["slots"]):
                product = self._resolve_slot(slot, width_in)
                is_unresolved = not product
                if is_unresolved:
                    product = unresolved_slot.product_variant_id
                tmpl = product.product_tmpl_id
                Line.create({
                    "design_id": design.id,
                    "sequence": (idx + 1) * 10,
                    "product_id": product.id,
                    "quantity": 1,
                    "price_unit": 0.0 if is_unresolved else (
                        product.lst_price or tmpl.list_price),
                    "cabinet_type": slot.cabinet_type,
                    "zone": slot.zone,
                    "width_in": width_in,
                    "height_in": tmpl.southbrook_height_in or 34.5,
                    "depth_in": tmpl.southbrook_depth_in or 24.0,
                    "wall": slot.wall,
                    "run_seq": slot.run_seq,
                    "origin": "configurator",
                    "layout_role": "canonical",
                    "layout_key": "tpl-%s-%s-%d" % (self.code, slot.slot_code, idx),
                    "template_slot_code": slot.slot_code,
                    "appliance_type": slot.appliance_type or False,
                    "is_unresolved": is_unresolved,
                })
            try:
                design.action_auto_arrange(sync=True)
            except kitchen_layout_engine.LayoutCapacityExceeded as e:
                raise UserError(
                    "This template does not fit a %g\" x %g\" room with the "
                    "chosen count/widths (%s). Reduce the cabinet count or "
                    "module width — the room is never grown automatically."
                    % (design.room_width_in, design.room_depth_in, e)) from e
            design.state = "configured"
            design.message_post(body=(
                "Instantiated from template %s (%s): %d slot(s), "
                "%d unresolved." % (
                    self.name, self.code, len(fit["slots"]),
                    len(design.cabinet_line_ids.filtered("is_unresolved")))))
        return design
```

(`from odoo.addons.southbrook_estimating.models import kitchen_layout_engine` at top — same import kitchen_design.py:11 uses.) Corner slots (`cabinet_type="corner"`): create NO design line — the engine inserts corners itself; instead a corner slot only expresses preference, which is already rule-`sequence`-ranked — log a chatter note if a template carries one. Bump manifest, add the data file BEFORE the views entry.

- [x] **Step 4: Run to verify PASS** — new suite + `test_auto_arrange_service` + `test_collision_matrix` still green (we touched the cab-list neighbourhood). Port **8304**.
- [x] **Step 5: Merge origin/main + Commit** — `feat(kitchen_3d): template resolver + action_instantiate + appliance design lines (templates T2)`.

---

### Task 3: Picker rewire — four-dropdown flow + toolbar button + SVG thumbnails (5.28.0)

**Files:**
- Modify: `models/kitchen_design.py` (picker class `:2347-2404`; DELETE `_KITCHEN_TEMPLATE_PRESETS` `:1477`, `_get_preset_layout` `:1573`, `_apply_kitchen_template` `:1583` after re-pointing callers)
- Modify: `models/kitchen_template.py` (`_generate_thumbnail_svg`)
- Modify: `views/kitchen_design_views.xml` (picker form `:439-482`)
- Modify: `static/src/js/kitchen_configurator.js` + its XML template (toolbar "Start from Template" button)
- Modify: `__manifest__.py` (version 19.0.5.28.0)
- Create: `tests/test_template_picker.py` (+ import in `tests/__init__.py`)

**Interfaces:**
- Consumes: T2 `action_instantiate` / `parametric_fit`; `action_open_configurator` (existing).
- Produces: picker fields `template_id` (m2o, required unless legacy `preset="empty"`), `cabinet_count` (Integer, 0=template default, live-clamped to `[min, n_max]`), `module_width_in` Selection `[("18","18\""),("21","21\""),("24","24\""),("30","30\"")]` default `"24"`, `range_width_in` `[("0","No range"),("30","30\""),("36","36\""),("48","48\"")]`, `fridge_width_in` `[("0","No fridge"),("30","30\""),("33","33\""),("36","36\"")]`, `dishwasher_width_in` `[("0","No dishwasher"),("24","24\"")]`; computed `count_max` + `fit_summary` (Text) + `template_preview` (Html, sanitize=False, server-generated SVG only); legacy `preset` Selection KEPT for compat, mapped via `_COMPAT_PRESET_CODES = {"empty": None, "l_shape": "L-10X8", "u_shape": "U-10X8X10", "galley": "GAL-10"}` (codes reconciled against the actual T4 catalog — see T4 Step 4).

- [x] **Step 1: Write failing tests** (`tests/test_template_picker.py`) — reuse T2's fixture builder (extract it into a small mixin/helper in the T2 file and import it):

```python
    def test_confirm_instantiates_and_opens_configurator(self):
        picker = self.env["kitchen.design.template.picker"].create({
            "template_id": self.tpl.id,
            "module_width_in": "24",
            "range_width_in": "36",
        })
        action = picker.action_create()
        self.assertEqual(action.get("tag") or action.get("res_model"),
                         action.get("tag") or action.get("res_model"))
        design = self.env["southbrook.kitchen.design"].search(
            [], order="id desc", limit=1)
        self.assertTrue(design.cabinet_line_ids)
        appl = design.cabinet_line_ids.filtered(
            lambda l: l.cabinet_type == "appliance")
        self.assertEqual(appl.width_in, 36.0)

    def test_count_is_live_bounded(self):
        picker = self.env["kitchen.design.template.picker"].create({
            "template_id": self.tpl.id, "module_width_in": "24"})
        self.assertGreater(picker.count_max, 0)
        picker.cabinet_count = picker.count_max + 5
        picker._onchange_parametrics()
        self.assertLessEqual(picker.cabinet_count, picker.count_max)

    def test_legacy_preset_compat_maps_to_template_code(self):
        # dict deleted; compat map must resolve by CODE (data-driven)
        Design = self.env["southbrook.kitchen.design"]
        self.assertFalse(hasattr(Design, "_KITCHEN_TEMPLATE_PRESETS"))
        picker = self.env["kitchen.design.template.picker"].create(
            {"preset": "empty"})
        picker.action_create()   # empty = plain draft design, no template

    def test_thumbnail_svg_generated(self):
        svg = self.tpl._generate_thumbnail_svg()
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("<rect", svg)
```

(Fix the first assertion to what `action_open_configurator()` really returns — read it first and assert on its actual `tag`/`res_model`.)

- [x] **Step 2: Run to verify FAIL.** Port **8305**.
- [x] **Step 3: Implement.**
  - Picker: new fields per Interfaces; `_onchange_parametrics` (`@api.onchange("template_id", "cabinet_count", "module_width_in", "range_width_in", "fridge_width_in", "dishwasher_width_in")`) recomputes `count_max`/`fit_summary` via `template_id.parametric_fit(...)` and clamps `cabinet_count` (greying via clamp + summary message — Selection fields can't be dynamically constrained in a transient; the clamp + `fit_summary` warning IS the spec's "constrain or flag"); `_appliance_widths()` helper builds the dict skipping `"0"` values; `action_create` resolves `template_id or _COMPAT_PRESET_CODES[preset]` by `search([("code", "=", code)])` (missing record → `UserError` naming the code — honesty, no silent fallback), calls `action_instantiate(partner_id=..., cabinet_count=self.cabinet_count or None, module_width_in=float(self.module_width_in), appliance_widths=...)`, returns `design.action_open_configurator()`; `preset="empty"`/no template keeps today's plain-draft path (create + open).
  - Delete `_KITCHEN_TEMPLATE_PRESETS`, `_get_preset_layout`, `_apply_kitchen_template`; `grep -rn "_apply_kitchen_template\|_get_preset_layout\|_KITCHEN_TEMPLATE_PRESETS" addons/ tests/` and re-point every hit (the picker was the only production caller; fix any test that pinned the dict).
  - `_generate_thumbnail_svg` on the template (server-generated top view, floor slots only — walls layer skipped):

```python
    def _generate_thumbnail_svg(self):
        self.ensure_one()
        W = self.default_room_width_in or 120.0
        D = self.default_room_depth_in or 96.0
        s = 200.0 / max(W, D)
        out = ['<svg xmlns="http://www.w3.org/2000/svg" '
               'viewBox="0 0 %.0f %.0f">' % (W * s, D * s),
               '<rect width="%.0f" height="%.0f" fill="#F4EFE7" '
               'stroke="#5E5346"/>' % (W * s, D * s)]
        cursors = {"back": 0.0, "front": 0.0, "left": 0.0, "right": 0.0}
        dpx = 24.0 * s
        for slot in self.line_ids.sorted(lambda l: (l.wall, l.run_seq)):
            if slot.cabinet_type == "wall":
                continue
            w = (slot.nominal_width_in
                 or self.default_module_width_in or 24.0) * s
            c = cursors[slot.wall]
            cursors[slot.wall] = c + w
            if slot.wall == "back":
                x, y, rw, rh = c, 0.0, w, dpx
            elif slot.wall == "front":
                x, y, rw, rh = c, D * s - dpx, w, dpx
            elif slot.wall == "left":
                x, y, rw, rh = 0.0, c, dpx, w
            else:
                x, y, rw, rh = W * s - dpx, c, dpx, w
            fill = ("#C28840" if slot.cabinet_type == "appliance"
                    else "#5E8FBE")
            out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" '
                       'fill="%s" opacity="0.85"/>' % (x, y, rw, rh, fill))
        out.append("</svg>")
        return "".join(out)
```

  `template_preview` on the picker: `fields.Html(compute=..., sanitize=False)` returning `Markup` of the SVG (server-generated only — never user input; document that in a comment). Picker form view: template_id + preview + the four parametric fields + fit_summary + partner_id + footer buttons (keep the legacy `preset` field `invisible="1"` for context-driven compat).
  - Toolbar button: in the configurator topbar template add `<button class="btn btn-secondary" t-on-click="_openTemplatePicker">Start from Template</button>`; in `kitchen_configurator.js` (`this.action = useService("action")` — check whether the component already has it; add if not):

```js
    async _openTemplatePicker() {
        // v19 doAction REQUIRES views (memory: odoo19_doaction_views_required)
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Start from Template",
            res_model: "kitchen.design.template.picker",
            views: [[false, "form"]],
            target: "new",
        });
    }
```

  Keep the OWL expression trivial (lint hook).
- [x] **Step 4: Run to verify PASS** + `node_js` suite still green (`cd addons/southbrook_kitchen_3d_configurator/tests/node_js && npm test`). Port **8306**.
- [x] **Step 5: Merge origin/main + Commit** — `feat(kitchen_3d): four-dropdown template picker + toolbar entry + SVG thumbnails (templates T3)`.

---

### Task 4: Starter template data records (5.29.0)

**Files:**
- Create: `addons/southbrook_kitchen_3d_configurator/data/kitchen_templates.xml` (`noupdate="0"` — spec locked decision #2: dimensions correctable without deploys)
- Modify: `__manifest__.py` (data entry AFTER `template_support_products.xml`; version 19.0.5.29.0)
- Modify: `models/kitchen_design.py` (reconcile `_COMPAT_PRESET_CODES` to the shipped codes)
- Create: `tests/test_template_catalog.py` (+ import in `tests/__init__.py`)

**Interfaces:**
- **DATA INPUT:** the implementer MUST first read `/private/tmp/claude-502/-Users-naadmin/30f764c9-d9ab-4b10-9bc7-d9348ab43200/scratchpad/sdd-briefs/ktmpl-catalog-design.md` (output of the blindspot/ReAct validation run wf_b7ad9cf6) and author ONLY the templates it keeps (validated ≥7/10), with its runs/slot lists/widths/appliances. **If the file does not exist yet, STOP and report — do not invent a catalog.**
- Authoring rules (apply regardless of catalog content): 10-ft reference runs on the starter set; slots reference Q8 xmlid pins (`southbrook_estimating.sink_base`, `.base_2dr`, `.base_1dr`, `.drawer_bank`, `.wall_2dr`, `.wall_1dr`, `.tall_pantry`, `.tall_oven` — variants via `product_variant_id` resolved in the resolver, pin field is `product.product`: pin via `<field name="product_id" ref="..."/>` only if the catalog doc names concrete products; otherwise leave archetype/fallback resolution); appliance slots as `cabinet_type="appliance"` lines; **NO corner slots and NO filler slots** — l_shape/u_shape templates simply place runs on 2/3 walls and the engine derives corners+fillers; module slots use `nominal_width_in=0` + `repeat_ok` on the plain base/wall fill slots; `priority` higher on decorative/optional slots so they drop first.
- Stable xmlids: template `ktpl_<code_lowercased_underscored>` (e.g. `ktpl_l_10x8`), lines `ktpl_<code>_<slot_code_lower>`.
- Any island/peninsula template the catalog keeps ships `active="False"` with a note (free-anchor ORM support not wired — investigation §C/§task-6), unless the catalog doc explicitly re-scopes it to wall runs only.

- [x] **Step 1: Write failing test** (`tests/test_template_catalog.py`) — generic over whatever T4 ships:

```python
@tagged("post_install", "-at_install", "southbrook",
        "southbrook_kitchen_3d_configurator", "kitchen_templates")
class TestShippedTemplateCatalog(TransactionCase):

    def test_every_active_shipped_template_instantiates(self):
        templates = self.env["southbrook.kitchen.template"].search(
            [("code", "not like", "T2-%"), ("code", "not like", "T1-%")])
        self.assertTrue(templates, "T4 must ship at least one template")
        for tpl in templates:
            with self.subTest(template=tpl.code):
                design = tpl.action_instantiate()
                self.assertTrue(design.cabinet_line_ids)
                self.assertFalse(
                    design.cabinet_line_ids.filtered("is_unresolved"),
                    "%s: shipped templates must fully resolve" % tpl.code)
                self.assertGreater(design.estimated_price, 0.0)
                self.assertEqual(design.room_width_in,
                                 tpl.default_room_width_in)  # no growth
                if tpl.layout_shape in ("l_shape", "u_shape", "g_shape"):
                    self.assertTrue(design.cabinet_line_ids.filtered(
                        lambda l: l.layout_role == "derived"
                        and l.cabinet_type == "corner"),
                        "%s: corner must be ENGINE-derived" % tpl.code)

    def test_no_corner_or_filler_slots_templated(self):
        slots = self.env["southbrook.kitchen.template.line"].search([])
        self.assertFalse(slots.filtered(
            lambda s: s.cabinet_type == "corner"),
            "corners are engine-derived — never templated (starter set)")
```

(If the catalog doc documents expected-unresolved slots for a specific template, encode that exact allowlist in the test instead of blanket-zero, with a comment citing the doc.)
- [x] **Step 2: Run to verify FAIL** (no shipped templates). Port **8307**.
- [x] **Step 3: Author the data XML from the catalog doc.** One `<record model="southbrook.kitchen.template">` + child `<record model="southbrook.kitchen.template.line">` per kept row; `layout_shape` values MUST be `_LAYOUT_SHAPES` keys (`straight`/`l_shape`/`u_shape`/`galley`/…; the catalog's `single_wall` ≈ `straight`; an `l_with_island` row composes `l_shape` + island slots, or ships inactive per Interfaces). Add file to manifest.
- [x] **Step 4: Reconcile the T3 compat map** — set `_COMPAT_PRESET_CODES`'s three codes to the ACTUAL shipped codes for the l/u/galley shapes and update the T3 test if codes differ.
- [x] **Step 5: Run to verify PASS** — catalog suite + T2/T3 suites. Port **8308**.
- [x] **Step 6: Merge origin/main + Commit** — `feat(kitchen_3d): starter kitchen template catalog data (templates T4)`.

---

### Task 5: Server-side manipulation API (5.30.0)

**Files:**
- Modify: `models/kitchen_design.py` (design: `action_flip_layout`, `action_rotate_layout`, `action_reflow`; line: `action_swap_product`, `action_set_width`, `action_move`)
- Modify: `__manifest__.py` (version 19.0.5.30.0)
- Create: `tests/test_layout_manipulation.py` (+ import in `tests/__init__.py`)

**Interfaces:**
- Every action mutates ONLY canonical semantics (wall/run_seq/product/width) then re-runs `action_auto_arrange(sync=True)` — poses are always re-derived, never transformed numerically; `_compute_totals` recomputes price/counts automatically via its depends. `LayoutCapacityExceeded` inside auto-arrange rolls the whole action back (its savepoint) → wrap in a `UserError` with a plain message (same honesty contract as T2).
- Name is `action_flip_layout` — NOT "mirror" (reconcile owns that word).

- [x] **Step 1: Write failing tests** (`tests/test_layout_manipulation.py`; reuse the T2 fixture helper; build one straight + one l_shape design via `action_instantiate`):

```python
    def test_flip_x_round_trip_is_identity(self):
        design = self.tpl_l.action_instantiate()
        canon = design.cabinet_line_ids.filtered(
            lambda l: l.layout_role == "canonical")
        before = {l.id: (l.wall, l.run_seq) for l in canon}
        design.action_flip_layout(axis="x")
        after_once = {l.id: (l.wall, l.run_seq) for l in canon}
        self.assertNotEqual(before, after_once, "flip must change assignment")
        design.action_flip_layout(axis="x")
        self.assertEqual(
            {l.id: (l.wall, l.run_seq) for l in canon}, before,
            "flip twice = identity on (wall, run_seq)")

    def test_rotate_four_quarters_is_identity(self):
        design = self.tpl_l.action_instantiate()
        canon = design.cabinet_line_ids.filtered(
            lambda l: l.layout_role == "canonical")
        before = {l.id: (l.wall, l.run_seq) for l in canon}
        for _ in range(4):
            design.action_rotate_layout(quarters=1)
        self.assertEqual({l.id: (l.wall, l.run_seq) for l in canon}, before)

    def test_swap_product_reprices_and_rearranges(self):
        design = self.tpl.action_instantiate()
        line = design.cabinet_line_ids.filtered(
            lambda l: l.template_slot_code == "B1")
        drawer = self.env.ref(
            "southbrook_estimating.drawer_bank").product_variant_id
        price_before = design.estimated_price
        line.action_swap_product(drawer.id)
        self.assertEqual(line.product_id, drawer)
        self.assertNotEqual(design.estimated_price, price_before)

    def test_set_width_capacity_honesty(self):
        design = self.tpl.action_instantiate()
        line = design.cabinet_line_ids.filtered(
            lambda l: l.template_slot_code == "B1")
        w = line.width_in
        with self.assertRaises(UserError):
            line.action_set_width(400.0)     # cannot fit a 10ft room
        self.assertEqual(line.width_in, w, "failed action must roll back fully")

    def test_reflow_is_auto_arrange_alias(self):
        design = self.tpl.action_instantiate()
        res = design.action_reflow()
        self.assertIn("corners", res)        # auto-arrange's return shape

    def test_derived_lines_are_engine_owned(self):
        design = self.tpl_l.action_instantiate()
        corner = design.cabinet_line_ids.filtered(
            lambda l: l.layout_role == "derived" and l.cabinet_type == "corner")
        with self.assertRaises(UserError):
            corner[:1].action_set_width(30.0)
```

- [x] **Step 2: Run to verify FAIL.** Port **8309**.
- [x] **Step 3: Implement** on the design:

```python
    def action_reflow(self):
        """Thin alias — auto-arrange IS the reflow (never a second one)."""
        self.ensure_one()
        return self.action_auto_arrange(sync=True)

    def _transform_layout(self, wall_map, reverse_walls):
        """Rewrite canonical (wall, run_seq) semantics, then re-derive ALL
        poses via auto-arrange. Restores archived canonicals first (the
        arrange reset does it too, but the transform must see them)."""
        self.ensure_one()
        ctx = self.with_context(active_test=False)
        canon = ctx.cabinet_line_ids.filtered(
            lambda l: l.layout_role == "canonical")
        canon.filtered(lambda l: not l.active).write({"active": True})
        by_wall = {}
        for line in canon:
            by_wall.setdefault(line.wall or "back", []).append(line)
        for wall, lines in by_wall.items():
            seqs = sorted({l.run_seq for l in lines})
            remap = (dict(zip(seqs, reversed(seqs)))
                     if wall in reverse_walls else {})
            for line in lines:
                line.write({"wall": wall_map[wall],
                            "run_seq": remap.get(line.run_seq, line.run_seq)})
        try:
            return self.action_auto_arrange(sync=True)
        except kitchen_layout_engine.LayoutCapacityExceeded as e:
            raise UserError(
                "The transformed layout does not fit this room (%s). "
                "Nothing was changed." % e) from e

    def action_flip_layout(self, axis="x"):
        """Flip left<->right (axis='x') or back<->front (axis='z').
        Deliberately NOT named 'mirror' — southbrook.design.reconcile
        owns that word (the manufacturing mirror)."""
        if axis == "x":
            return self._transform_layout(
                {"back": "back", "front": "front",
                 "left": "right", "right": "left"},
                reverse_walls=("back", "front"))
        if axis == "z":
            return self._transform_layout(
                {"back": "front", "front": "back",
                 "left": "left", "right": "right"},
                reverse_walls=("left", "right"))
        raise UserError("axis must be 'x' or 'z'")

    def action_rotate_layout(self, quarters=1):
        cw = {"back": "right", "right": "front",
              "front": "left", "left": "back"}
        res = None
        for _ in range(int(quarters) % 4):
            res = self._transform_layout(cw, reverse_walls=())
        return res if res is not None else self.action_reflow()
```

The room is NEVER resized by rotate — a non-fitting rotation raises (honesty; documented). Line actions (`action_swap_product(product_id)`, `action_set_width(width_in)`, `action_move(wall, run_seq)`): guard `self.layout_role == "canonical"` (else `UserError("Derived lines are engine-owned…")`); write the semantic fields (swap also rewrites `price_unit`/dims from the new product's template — same field set `_create_line` `:2039` uses; clear `is_unresolved` on swap); then `return self.design_id.action_auto_arrange(sync=True)` wrapped in the same `LayoutCapacityExceeded → UserError` translation. These formalize the client-only `_swapSelectedProduct`/`_updateSelectedWidth` (kitchen_configurator.js:1103/1082) server-side — do NOT remove the client paths in this task.
- [x] **Step 4: Run to verify PASS** + `test_auto_arrange_service` green (idempotence untouched). Port **8310**.
- [x] **Step 5: Merge origin/main + Commit** — `feat(kitchen_3d): server-side layout manipulation API — flip/rotate/swap/width/move/reflow (templates T5)`.

---

### Task 6: `total_cabinets` filler exclusion + `filler_count` — ISOLATED cross-consumer change (5.31.0)

**Files:**
- Modify: `models/kitchen_design.py` (`_compute_totals` `:384`; new stored `filler_count`)
- Modify: `views/kitchen_design_views.xml` (surface `filler_count` next to `total_cabinets` — hits at `:29/:115/:143/:261/:327`)
- Create: `migrations/19.0.5.31.0/post-migrate.py` (recompute stored totals — stored computes do NOT self-recompute on `-u`)
- Modify: `static/src/js/kitchen_configurator.js` (client summary parity in `_recomputeLayoutFromItems` ~`:1158` — exclude `is_filler` items from the cabinet COUNT; price handling already excludes fillers, leave it)
- Modify: `__manifest__.py` (version 19.0.5.31.0)
- Create: `tests/test_totals_filler_exclusion.py` (+ import in `tests/__init__.py`)

**Interfaces:**
- New contract: `total_cabinets` = Σ quantity of lines with `cabinet_type != "filler"`; `filler_count` = Σ quantity of `cabinet_type == "filler"` lines. The sale-order fallback branch (`:396-412`) applies the same exclusion via `southbrook_cabinet_type != "filler"`. `base_count`/`wall_count`/`estimated_price` semantics UNCHANGED (price still includes filler lines — they are real BOM-reaching lines).
- Consumer audit (do in Step 3, in-repo greps, fix or explicitly clear each): `views/kitchen_design_views.xml` (display only — add filler_count), `models/reconcile.py` (greps show NO total_cabinets use — confirm), `tests/test_m1_m2_reconcile_fixes.py:100/148/164` (order-line fallback assertions — verify fixtures contain no filler products; if one does, update the expected number WITH a comment citing this plan), kanban `t-esc` at `:143`, and `southbrook_estimating_website` JS greps for `total_cabinets`.

- [x] **Step 1: Write failing test:**

```python
@tagged("post_install", "-at_install", "southbrook",
        "southbrook_kitchen_3d_configurator", "kitchen_templates")
class TestTotalsFillerExclusion(TransactionCase):

    def test_fillers_excluded_from_total_but_counted(self):
        design = self.env["southbrook.kitchen.design"].create(
            {"name": "T6 totals", "room_width_in": 120.0})
        base = self.env.ref(
            "southbrook_estimating.base_2dr").product_variant_id
        filler = self.env.ref(
            "southbrook_kitchen_3d_configurator.product_tmpl_fp3"
        ).product_variant_id
        Line = self.env["southbrook.kitchen.design.line"]
        for seq, (p, ct) in enumerate(
                [(base, "base"), (base, "base"), (filler, "filler")]):
            Line.create({
                "design_id": design.id, "sequence": seq * 10,
                "product_id": p.id, "quantity": 1, "price_unit": p.lst_price,
                "cabinet_type": ct, "width_in": 24.0, "height_in": 34.5,
                "depth_in": 24.0, "origin": "configurator"})
        self.assertEqual(design.total_cabinets, 2,
                         "fillers must not count as cabinets")
        self.assertEqual(design.filler_count, 1)
```

(Verify the FP3 xmlid — `data/demo_cabinets.xml:114` defines `product_tmpl_fp3`; adjust module prefix to the record's real one.)
- [x] **Step 2: Run to verify FAIL** (`total_cabinets == 3`, no `filler_count`). Port **8311**.
- [x] **Step 3: Implement** — in `_compute_totals`:

```python
                cab_lines = lines.filtered(lambda l: l.cabinet_type != "filler")
                fillers = lines - cab_lines
                design.total_cabinets = sum(cab_lines.mapped("quantity"))
                design.filler_count = sum(fillers.mapped("quantity"))
```

mirror in the order-line fallback (filter `southbrook_cabinet_type != "filler"`; `filler_count` from the filler order lines). New field `filler_count = fields.Integer(compute="_compute_totals", store=True)`. Migration `post-migrate.py` (idiom: `def migrate(cr, version):` guard `if not version: return`, build env): `env["southbrook.kitchen.design"].with_context(active_test=False).search([])._compute_totals()`. Views: add `filler_count` beside each `total_cabinets` display. JS summary count parity. Run the consumer audit list above; note each verdict in the commit body.
- [x] **Step 4: Run to verify PASS** — new test + `test_m1_m2_reconcile_fixes` + full `kitchen_templates` suite; grep upgrade log for `19.0.5.31.0` migration firing. Port **8312**.
- [x] **Step 5: Merge origin/main + Commit** — `fix(kitchen_3d): total_cabinets excludes fillers; add filler_count (templates T6, isolated)`.

---

### Task 7: Canvas JS sweep v2 (5.32.0)

**Files:**
- Modify: `static/src/js/kitchen_configurator.js` (`__sbk` hook; auto-save gate; room-resize rerouting `_changeRoom`/`_stretchWidth` `:649-656` + the depth handles `:2541/:2558`; auto-grow removal `:983-988`)
- Modify: `static/src/js/canvas/kitchen_canvas.esm.js` (ghost preview on wall hover during drag — extend the existing hover soft-glow `:312-322`)
- Modify: `controllers/main.py` (new `/southbrook_kitchen/configurator/rearrange` route)
- Modify: `__manifest__.py` (version 19.0.5.32.0)
- Create: `tests/node_js/contracts/13_sbk_getlayout.test.mjs`, `tests/node_js/contracts/14_autosave_first_action_gate.test.mjs` (follow the harness in `tests/node_js/README.md`)
- Create: `tests/test_rearrange_route.py` (+ import in `tests/__init__.py`)

**Interfaces:**
- `window.__sbk.getLayout()` → `[{id, sku, wall, x_position_in, width_in, cabinet_type, is_filler}]` snapshot of `state.items` (map from the ACTUAL item keys — read `_recomputeLayoutFromItems` first; contract keys are fixed, values deep-copied). Installed in `onMounted`, removed in `onWillUnmount`. Read-only — never a mutation surface.
- Auto-save gate: `this._userActed = false` at setup; `_queueAutoSave` (`:1752`) early-returns until the first GENUINE user mutation (add/drop, drag end, remove, width/swap, room change, wall select) sets `_userActed = true`. The existing `_hydrationFailed` guard stays; this closes the "programmatic refresh auto-saves over a template-instantiated design before the user touched anything" hole. Undo/redo explicitly deferred (investigation E-f: gate is the safe half).
- Room-resize regen honesty: when `state.designId` is set, `_changeRoom`/`_stretchWidth`/depth-resize call the NEW `rearrange` route (writes room dims, runs `action_auto_arrange(sync=False)` — the corner engine, NOT the naive `/layout` single-wall generator at `controllers/main.py:61`), then re-hydrate items from its response (reuse the `load_design_lines` emission shape). Fresh unsaved sessions keep the `/layout` path unchanged. On `ROOM_TOO_SMALL`: revert the room field in state + warning toast — never persist a non-fitting resize.
- Auto-grow removal (`:983-988`): the silent `state.room.width_in = Math.ceil(required/6)*6` on add is REPLACED by a warning toast ("Run needs %s in — room is %s in. Remove a cabinet or widen the room.") with NO room mutation — this is the spec's "54→60→84 growth" defect fix.

- [x] **Step 1: Write failing node contract tests** (mirror an existing `contracts/*.test.mjs` for harness imports):
  - `13_sbk_getlayout.test.mjs`: mount the component shim with 2 items (one filler), assert `window.__sbk.getLayout()` returns exactly the 7 contract keys, `is_filler` true for the filler, and that mutating the returned array does NOT mutate `state.items`.
  - `14_autosave_first_action_gate.test.mjs`: after mount + programmatic `_refreshLayout`, `_queueAutoSave()` schedules nothing; after simulating a user add (`_addCabinetFromProduct(...)` via the shim), `_queueAutoSave()` schedules. Also assert `_addCabinetFromProduct` no longer mutates `state.room.width_in` when the run exceeds it.
- [x] **Step 2: Run to verify FAIL** — `cd addons/southbrook_kitchen_3d_configurator/tests/node_js && npm test`.
- [x] **Step 3: Write failing python test** (`tests/test_rearrange_route.py`, TransactionCase on the model seam): build a 2-wall design via T2's fixture, write new room dims + `action_auto_arrange(sync=False)`, assert poses changed and derived corner regenerated; assert shrinking below capacity raises `LayoutCapacityExceeded` and leaves lines' poses unchanged (savepoint). Run — expect the route-shape parts to fail. Port **8313**.
- [x] **Step 4: Implement** — controller route (mirror `save_design`'s auth/ACL pattern at `controllers/main.py:302-575`, including the `LayoutCapacityExceeded` → `error_code` mapping the file already does at `:11-26`):

```python
    @http.route("/southbrook_kitchen/configurator/rearrange",
                type="json", auth="user")
    def rearrange(self, design_id, room=None):
        design = request.env["southbrook.kitchen.design"].browse(
            int(design_id)).exists()
        if not design:
            return {"error": "Design not found", "error_code": "NOT_FOUND"}
        design.check_access("write")
        if room:
            design.write({
                "room_width_in": float(room.get("width_in") or design.room_width_in),
                "room_depth_in": float(room.get("depth_in") or design.room_depth_in),
                "room_height_in": float(room.get("height_in") or design.room_height_in),
            })
        try:
            design.action_auto_arrange(sync=False)
        except kitchen_layout_engine.LayoutCapacityExceeded as e:
            return {"error": str(e), "error_code": "ROOM_TOO_SMALL"}
        return {"items": self._design_lines_payload(design)}
```

(`_design_lines_payload` = extract/reuse the existing `load_design_lines` line-emission helper — do NOT re-implement the item dict shape; refactor-extract if it's inline.) JS changes per Interfaces; ghost preview: on dragover with a hovered wall, add ONE translucent box mesh (product w/h/d, existing material palette) at the hovered wall's run end, disposed on dragleave/drop/deselect — visual affordance only, no placement math (the drop still goes through the existing server-side placement). Every touched template expression must pass `python3 scripts/lint-owl-expr.py` (pre-commit runs it anyway).
- [x] **Step 5: Run to verify PASS** — npm suite + python suites + full-module tag pass. Port **8314**.
- [x] **Step 6: Merge origin/main + Commit** — `feat(kitchen_3d): __sbk.getLayout, autosave first-action gate, engine-routed room resize, ghost preview, no silent room growth (templates T7)`.

---

### Task 8: Docs + README + spec delivery note (docs-only, no version bump)

**Files:**
- Create: `addons/southbrook_kitchen_3d_configurator/README.md` (module has none — new: dependency note on southbrook_estimating; templates feature: data model, resolver contract, parametric fill math, manipulation API surface, honesty guarantees, `__sbk.getLayout()` contract for automation)
- Modify: `docs/superpowers/specs/2026-07-27-kitchen-templates-design.md` (append `## Delivery note` — what shipped per task, versions, deviations if any, the reconciled compat-preset→code map, any templates shipped `active=False` and why)
- Modify: `docs/superpowers/plans/2026-07-27-kitchen-templates.md` (tick checkboxes; note any renumbered versions)

- [x] **Step 1: Write the three docs.** Delivery note must be honest: list anything cut/deferred (undo/redo, island free-anchor, drag mis-grab non-repro) with the reason.
- [x] **Step 2: Final verification** — full-module pass: `-u southbrook_kitchen_3d_configurator --test-enable --test-tags southbrook_kitchen_3d_configurator -d test_sbgeo_b1 --stop-after-init --no-http --http-port=8315` (grep log: 0 failed, 0 error, and confirm the `kitchen_templates` classes all ran) + `npm test` in `tests/node_js` + `pre-commit run -a` (OWL lint included) + cold-install sanity: `-i southbrook_kitchen_3d_configurator -d test_ktpl_cold --stop-after-init --no-http --http-port=8316` (v19 cold-install ParseError traps are real — see memory `odoo19_view_validation_v19_traps`).
- [x] **Step 3: Merge origin/main + Commit** — `docs(kitchen_3d): kitchen templates README + spec delivery note (templates T8)`. Then run the superpowers:requesting-code-review flow on the whole branch before any merge decision (merge/deploy remains gated on John per house rules).

---

## Self-Review

**Spec coverage:** slots-not-SKU-pins + optional pin (T1 fields, T2 resolver order) ✓; templates as `noupdate="0"` data (T4) ✓; finish-agnostic — resolver resolves on pin/archetype+width with material/door-style deliberately NOT required (matches investigation §G: series/finish don't exist as product fields; treated as future optional preference) ✓; four-dropdown UX with live-bounded count + constrain/flag (T3 `parametric_fit` + clamp + fit_summary; blocking validation at instantiate T2) ✓; zero new geometry — instantiate/manipulate/rearrange all terminate in `action_auto_arrange` (T2/T5/T7) ✓; corners/fillers engine-derived, never templated (T4 authoring rule + pinned by `test_no_corner_or_filler_slots_templated`) ✓; appliances as design lines with placement-rule clearances, no workspace dependency (T2) ✓; room-shape lexicon reused (T1 test pins parity) ✓; placeholder honesty (T2 line + `UNRESOLVED_SLOT` blocking check) ✓; no silent growth server (T2/T5 UserError translation) and client (T7 auto-grow removal + resize revert) ✓; picker rewire + compat presets as data + toolbar button + generated SVG thumbnails (T3/T4) ✓; manipulation API with auto recompute + not-"mirror" naming (T5) ✓; counts fix isolated with consumer audit + migration recompute (T6) ✓; `__sbk.getLayout()`/autosave-gate/ghost/resize-through-engine (T7) ✓; per-template instantiation + manipulation round-trip tests (T4/T5) ✓; docs+delivery note (T8) ✓.
**Ambiguities resolved:** count-growth semantics = clone `repeat_ok` slots (new field, T1) — the spec's count dropdown needed a defined expansion rule; corner claims in the UI-side fit math are the engine constant approximation with `LayoutCapacityExceeded` authoritative; thumbnails stored as generated SVG markup (Html preview, `fields.Image` would reject SVG via PIL) with `fields.Image thumbnail` kept as manual override; rotate never swaps room dims (honesty over convenience); legacy presets map to T4 codes reconciled at T4 Step 4; T7 ships the autosave GATE, undo deferred (investigation E-f).
**Placeholders:** none load-bearing — where a snippet says "read X first" the anchor file:line is given and the contract keys/assertions are fully specified.
**Type consistency:** `appliance_widths` dict keyed by `appliance_type` flows picker→`parametric_fit`→`action_instantiate`; `fit["slots"]` list of `(slot, width_in)` produced and consumed inside T2; `_COMPAT_PRESET_CODES` produced T3, reconciled T4; `rearrange` returns the `load_design_lines` item shape (extracted helper, single source). One version bump per code task, T6's migration folder matches its manifest version, T8 bumps nothing.

---

### Task 4a: Corner-SKU data repair + L-10x8 flagship template (ADDED per user directive — corners are the point)

**Why:** validation kept zero L/U templates solely due to SB-CORNER's data (LH-only; dims inconsistent: variants 33″ vs southbrook_width_in 36 vs dimensions 36×36×34.5 vs depth 24; "rotating carousel" description vs highline archetype CC-CHL). The corner ENGINE is sound — this is data repair, in scope now.

**Files:** southbrook_estimating data (the Q8 `southbrook.corner` product template + attribute values) and/or a data migration; then ONE new template data record `L-10x8` in the T4 file.

- [x] **Step 1 — ground-truth**: read the live SB-CORNER product/template/variant fields + its archetype link (code CC-CHL, width_default_mm/depth_default_mm in `southbrook.cabinet.archetype`); enumerate every inconsistent field with current values. Do NOT guess the correct dims — take them from the archetype record; if the archetype itself is ambiguous, STOP and report (controller escalates to user).
- [x] **Step 2 — repair as data/migration**: align `southbrook_width_in` / depth / dimensions / variant width values to the archetype; fix the description; keep xmlids stable; idempotent (only rewrite when matching the known-bad values — never clobber a later hand edit).
- [x] **Step 3 — RH variant**: add the RH hand as an attribute value (mirroring the existing LH mechanism — read how hand is modeled first; if hand is NOT modeled at all, add the attribute minimally per the configurator's existing attribute idioms).
- [x] **Step 4 — L-10x8 template record**: back(120″)+left(96″) runs meeting at the corner slot (cabinet_type='corner', engine claims both legs); slots per the catalog formula (SB30+range on the long leg, fridge slot on the short leg, modules+fillers computed); knobs: module_width, per-wall run lengths.
- [x] **Step 5 — tests**: instantiate L-10x8 → corner line present with both-leg claim (assert via the engine's outputs), no placeholder for the corner, price computes; RH flip via action_flip_layout keeps corner valid (hand swapped).
- [x] **Step 6 — commit.**

Sequencing: runs after T4 (catalog templates) and T5 (flip exists for Step 5); L-10x8 is the whole-feature acceptance benchmark.


---
**Delivery (2026-07-27):** all tasks complete inline (T1–T8 + T4a).
Version renumbering vs this plan: T4a shipped as 5.31.0 (+
southbrook_estimating 19.0.9.1.0), T6 as 5.32.0, T7 as 5.33.0. Full
deviation list: spec's Delivery note
(docs/superpowers/specs/2026-07-27-kitchen-templates-design.md).
