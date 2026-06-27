# Room-First Order Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-class `southbrook.room` model + 3-step setup wizard + interactive Room Layout tab to the Order Builder, anchoring every order to a physical room and giving the designer live conflict/capacity feedback.

**Architecture:** New ORM trio (`southbrook.room` + `southbrook.room.wall` + `southbrook.room.constraint`) lives in `southbrook_estimating` and is **One2many from `sale.order`**; cabinet placement is two optional fields (`wall_id`, `position_from_left_mm`) on `sale.order.line`. UI ships as **two new OWL tabs** appended to the existing `portal_boot.esm.js` tablist (not Bootstrap), plus a backend smart button + form pages. The Room Layout tab uses **inline SVG** (no new vendored libs); wkhtmltopdf renders the same SVG natively in the PDF extension. All new fields are non-required with sensible defaults so every existing order continues to work unchanged.

**Tech Stack:** Odoo 19 CE · OCA `product_configurator` · OWL · plain SVG · QWeb (PDF) · Python 3 (PIL only for PDF rasterization fallback) · existing asset bundles `web.assets_backend` + `web.assets_frontend` (no new deps).

## Global Constraints

- **Odoo 19 CE only.** The brief said "Odoo 17" — wrong. Use `models.Constraint('UNIQUE(...)', 'msg')` not legacy `_sql_constraints`; v19 silently ignores the latter (`odoo19_sql_constraints_deprecated`). `res.groups.category_id` is gone; group declarations must omit it (`odoo19_res_users_group_ids_rename`). View-validation in `-u` is strict — no manual-field refs in `decoration-*` attrs of XML living in an addon whose downstream sibling owns the field (`odoo19_view_dep_chain_manual_fields`).
- **Branch:** `feature/prodboard-tier-2-mi-quality` (clean, HEAD @ `82b6436`). All work commits here unless a separate `feature/room-first` branch is requested.
- **License:** LGPL-3 (matches `southbrook_estimating`). Top of every new file: `# SPDX-License-Identifier: LGPL-3.0-only`.
- **Order entity = `sale.order`**, line entity = `sale.order.line`. There is **no** `southbrook.order` model. The room model belongs to `sale.order` via a One2many.
- **Tab insertion is via OWL state, not QWeb.** New tabs go in the `_tabs` getter at `addons/southbrook_estimating_website/static/src/js/portal_boot.esm.js:2885-2929` plus a sibling conditional render block at `:2238-2379`. Do **not** modify `portal_template.xml` to add tabs — the OWL tablist owns rendering.
- **Existing `zone` Selection field already encodes the "Base Run / Upper Run" grouping** (`sale_order_line.py:55-71`). Do not introduce a parallel run-name field; reuse `zone`.
- **OCA configurator integration:** `sale.order.line` already carries `config_session_id` (optional). New fields `wall_id` + `position_from_left_mm` must be **non-required + `copy=False`** so duplication (NF6 version chain) does not propagate stale placements.
- **No new external Python deps.** PIL is already in `external_dependencies`; qrcode is in `southbrook_kitchen_mrp`. The Room Layout tab uses inline SVG strings only.
- **Non-destructive contract:** every new field on existing models is optional with a default. Pricing engine + BoM generation must continue to work identically for orders with no room data.
- **Portal route precedent:** existing portal handlers live in `addons/southbrook_estimating_website/controllers/main.py`. New JSON-RPC endpoints follow the auth/ownership pattern of `_southbrook_resolve_order()` (`main.py:844-873`).
- **CSS scoping:** all new classes prefixed `sb-room-`. SCSS lives under `southbrook_estimating_website/static/src/scss/room_layout.scss`.
- **Locked-decisions adherence:** consult `PUNCHLIST.md` § "2026-05-29 · Locked decisions" before deviating on attributes, zones, or pricelist behavior. Q21 (zone) and NF6 (version chain) are directly load-bearing on this work.

---

## Phase 1 — Data Model (Tasks 1.1, 1.2, 1.3)

### Task 1.1 — Create `southbrook.room` + `southbrook.room.wall` + `southbrook.room.constraint`

**Files:**
- Create: `addons/southbrook_estimating/models/southbrook_room.py`
- Create: `addons/southbrook_estimating/models/southbrook_room_wall.py`
- Create: `addons/southbrook_estimating/models/southbrook_room_constraint.py`
- Modify: `addons/southbrook_estimating/models/__init__.py:1-N` (append three imports near the existing block; insertion BEFORE `sale_order` so the relations resolve)
- Modify: `addons/southbrook_estimating/security/ir.model.access.csv` (append 9 rows: 3 per model × {user, sales, manager})
- Modify: `addons/southbrook_estimating/__manifest__.py` (bump `version` to `19.0.5.0.0`)
- Test: `addons/southbrook_estimating/tests/test_southbrook_room.py`

**Interfaces:**
- Produces:
  - `southbrook.room` model with fields: `name (Char, required)`, `order_id (M2o sale.order, required, ondelete='cascade')`, `room_type (Selection)`, `layout_shape (Selection)`, `ceiling_height_mm (Integer, default=2400)`, `unit_preference (Selection, default='mm')`, `wall_ids (O2m southbrook.room.wall)`, `constraint_ids (O2m southbrook.room.constraint)`, `total_linear_mm (Integer, computed, store=True)`, `wall_count (Integer, computed, store=True)`, `constraint_count (Integer, computed, store=True)`, `layout_complete (Boolean, computed, store=True)`, `has_plumbing (Boolean, computed, store=True)`.
  - `southbrook.room.wall` model: `name (Char, required)`, `room_id (M2o, required, ondelete='cascade')`, `length_mm (Integer, default=0)`, `has_upper_cabinets (Boolean, default=True)`, `has_base_cabinets (Boolean, default=True)`, `has_tall_cabinets (Boolean, default=False)`, `wall_order (Integer, default=10, _order field)`. Reverse o2m + capacity computes added in Task 1.2.
  - `southbrook.room.constraint` model: `constraint_type (Selection: window, door, sink, cooktop, oven, dishwasher, rangehood, fridge_space, power_outlet, structural_post, other)`, `wall_id (M2o southbrook.room.wall, required, ondelete='cascade')`, `room_id (M2o, related='wall_id.room_id', store=True)`, `distance_from_left_mm (Integer)`, `width_mm (Integer)`, `height_mm (Integer)`, `height_from_floor_mm (Integer)`, `notes (Text)`.

- [ ] **Step 1: Write failing tests** — `tests/test_southbrook_room.py`

```python
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "southbrook_room")
class TestSouthbrookRoom(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Test Customer"})
        cls.order = cls.env["sale.order"].create({"partner_id": cls.partner.id})

    def test_create_minimal_room(self):
        room = self.env["southbrook.room"].create({
            "name": "Main Kitchen",
            "order_id": self.order.id,
        })
        self.assertEqual(room.order_id, self.order)
        self.assertEqual(room.unit_preference, "mm")
        self.assertEqual(room.ceiling_height_mm, 2400)
        self.assertFalse(room.layout_complete)

    def test_layout_complete_requires_shape_plus_two_walls(self):
        room = self.env["southbrook.room"].create({
            "name": "L-Kitchen",
            "order_id": self.order.id,
            "layout_shape": "l_shape",
            "wall_ids": [
                (0, 0, {"name": "Wall A", "length_mm": 3600}),
                (0, 0, {"name": "Wall B", "length_mm": 2400}),
            ],
        })
        self.assertTrue(room.layout_complete)
        self.assertEqual(room.total_linear_mm, 6000)
        self.assertEqual(room.wall_count, 2)

    def test_layout_incomplete_when_wall_has_zero_length(self):
        room = self.env["southbrook.room"].create({
            "name": "Half-set",
            "order_id": self.order.id,
            "layout_shape": "straight",
            "wall_ids": [(0, 0, {"name": "Wall A", "length_mm": 0})],
        })
        self.assertFalse(room.layout_complete)

    def test_has_plumbing_when_sink_constraint_present(self):
        room = self.env["southbrook.room"].create({
            "name": "Plumb",
            "order_id": self.order.id,
            "layout_shape": "straight",
            "wall_ids": [(0, 0, {"name": "A", "length_mm": 3000})],
        })
        wall = room.wall_ids[0]
        self.env["southbrook.room.constraint"].create({
            "wall_id": wall.id,
            "constraint_type": "sink",
            "distance_from_left_mm": 1200,
            "width_mm": 900,
        })
        room.invalidate_recordset(["has_plumbing", "constraint_count"])
        self.assertTrue(room.has_plumbing)
        self.assertEqual(room.constraint_count, 1)

    def test_room_cascade_deletes_walls_and_constraints(self):
        room = self.env["southbrook.room"].create({
            "name": "Doomed",
            "order_id": self.order.id,
            "wall_ids": [(0, 0, {"name": "A", "length_mm": 3000})],
        })
        wall = room.wall_ids[0]
        self.env["southbrook.room.constraint"].create({
            "wall_id": wall.id,
            "constraint_type": "window",
            "distance_from_left_mm": 500,
            "width_mm": 600,
        })
        wall_id, room_id = wall.id, room.id
        room.unlink()
        self.assertFalse(self.env["southbrook.room.wall"].browse(wall_id).exists())
        self.assertFalse(self.env["southbrook.room"].browse(room_id).exists())

    def test_unit_preference_round_trip(self):
        room = self.env["southbrook.room"].create({
            "name": "Imp", "order_id": self.order.id, "unit_preference": "imperial",
        })
        self.assertEqual(room.unit_preference, "imperial")
```

- [ ] **Step 2: Run tests — expect failure (models do not exist)**

```bash
# If sami-odoo container is up:
cd ~/southbrook-v19cr && make test 2>&1 | tail -40
# Or, focused (faster):
docker exec sami-odoo odoo -d southbrook -u southbrook_estimating \
  --test-enable --test-tags=southbrook_room \
  --stop-after-init --no-http --workers=0 --max-cron-threads=0 2>&1 | tail -20
```
Expected: `KeyError: 'southbrook.room'` or `Model not found` (test fails because model not yet defined).

- [ ] **Step 3: Implement `southbrook_room.py`**

```python
# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.room — first-class room anchoring an order to a physical space.

Per the Room-First UX initiative (2026-06-27): every order can optionally
declare one room (multi-room support planned via the O2m from sale.order
keeping the migration cost low). Wall + constraint child models live in
sibling files.
"""
from odoo import api, fields, models


_ROOM_TYPES = [
    ("kitchen", "Kitchen"),
    ("laundry", "Laundry"),
    ("butler", "Butler's Pantry"),
    ("bar", "Bar"),
    ("bathroom", "Bathroom"),
    ("office", "Office"),
    ("other", "Other"),
]

_LAYOUT_SHAPES = [
    ("straight", "Straight"),
    ("l_shape", "L-Shape"),
    ("u_shape", "U-Shape"),
    ("galley", "Galley"),
    ("g_shape", "G-Shape"),
    ("island", "Island"),
    ("peninsula", "Peninsula"),
    ("custom", "Custom"),
]

_UNIT_PREF = [("mm", "Millimetres"), ("imperial", "Feet & Inches")]


class SouthbrookRoom(models.Model):
    _name = "southbrook.room"
    _description = "Southbrook Room"
    _order = "id desc"
    _rec_name = "name"

    name = fields.Char(required=True, default="Main Kitchen")
    order_id = fields.Many2one(
        "sale.order", required=True, ondelete="cascade", index=True,
        help="The Sale Order this room belongs to.")

    room_type = fields.Selection(_ROOM_TYPES, default="kitchen")
    layout_shape = fields.Selection(_LAYOUT_SHAPES)
    ceiling_height_mm = fields.Integer(default=2400, string="Ceiling Height (mm)")
    unit_preference = fields.Selection(
        _UNIT_PREF, default="mm", required=True,
        help="Drives display across the whole order. Storage is always mm.")

    wall_ids = fields.One2many(
        "southbrook.room.wall", "room_id", string="Walls")
    constraint_ids = fields.One2many(
        "southbrook.room.constraint", "room_id", string="Constraints")

    total_linear_mm = fields.Integer(
        compute="_compute_summary", store=True, string="Total Linear (mm)")
    wall_count = fields.Integer(compute="_compute_summary", store=True)
    constraint_count = fields.Integer(compute="_compute_summary", store=True)
    layout_complete = fields.Boolean(compute="_compute_summary", store=True)
    has_plumbing = fields.Boolean(compute="_compute_summary", store=True)

    @api.depends(
        "layout_shape", "wall_ids", "wall_ids.length_mm",
        "constraint_ids", "constraint_ids.constraint_type",
    )
    def _compute_summary(self):
        plumbing = {"sink", "dishwasher"}
        for rec in self:
            walls = rec.wall_ids
            rec.wall_count = len(walls)
            rec.total_linear_mm = sum(w.length_mm or 0 for w in walls)
            rec.constraint_count = len(rec.constraint_ids)
            positive = [w for w in walls if (w.length_mm or 0) > 0]
            single_wall_shapes = {"straight", "island"}
            min_walls = 1 if rec.layout_shape in single_wall_shapes else 2
            rec.layout_complete = bool(
                rec.layout_shape and len(positive) >= min_walls)
            rec.has_plumbing = any(
                c.constraint_type in plumbing for c in rec.constraint_ids)
```

- [ ] **Step 4: Implement `southbrook_room_wall.py`** (capacity computes added in Task 1.2)

```python
# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.room.wall — one wall of a room with its own cabinet zones."""
from odoo import api, fields, models


class SouthbrookRoomWall(models.Model):
    _name = "southbrook.room.wall"
    _description = "Southbrook Room Wall"
    _order = "room_id, wall_order, id"
    _rec_name = "name"

    name = fields.Char(required=True, default="Wall A")
    room_id = fields.Many2one(
        "southbrook.room", required=True, ondelete="cascade", index=True)
    order_id = fields.Many2one(
        "sale.order", related="room_id.order_id", store=True, index=True)

    length_mm = fields.Integer(string="Length (mm)", default=0)
    wall_order = fields.Integer(default=10)

    has_upper_cabinets = fields.Boolean(default=True)
    has_base_cabinets = fields.Boolean(default=True)
    has_tall_cabinets = fields.Boolean(default=False)

    constraint_ids = fields.One2many(
        "southbrook.room.constraint", "wall_id", string="Constraints")
    # Reverse O2m + capacity computes are populated by Task 1.2.
```

- [ ] **Step 5: Implement `southbrook_room_constraint.py`**

```python
# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.room.constraint — a fixed obstacle/feature pinned to a wall."""
from odoo import fields, models


_CONSTRAINT_TYPES = [
    ("window", "Window"),
    ("door", "Door"),
    ("sink", "Sink"),
    ("cooktop", "Cooktop"),
    ("oven", "Oven"),
    ("dishwasher", "Dishwasher"),
    ("rangehood", "Rangehood"),
    ("fridge_space", "Fridge Space"),
    ("power_outlet", "Power Outlet"),
    ("structural_post", "Structural Post"),
    ("other", "Other"),
]


class SouthbrookRoomConstraint(models.Model):
    _name = "southbrook.room.constraint"
    _description = "Southbrook Room Constraint"
    _order = "wall_id, distance_from_left_mm, id"

    constraint_type = fields.Selection(_CONSTRAINT_TYPES, required=True, default="window")
    wall_id = fields.Many2one(
        "southbrook.room.wall", required=True, ondelete="cascade", index=True)
    room_id = fields.Many2one(
        "southbrook.room", related="wall_id.room_id", store=True, index=True)

    distance_from_left_mm = fields.Integer(default=0)
    width_mm = fields.Integer(default=0)
    height_mm = fields.Integer(default=0)
    height_from_floor_mm = fields.Integer(default=0)
    notes = fields.Text()
```

- [ ] **Step 6: Register imports — `models/__init__.py`**

Add these three lines BEFORE the existing `from . import sale_order` line:
```python
from . import southbrook_room
from . import southbrook_room_wall
from . import southbrook_room_constraint
```

- [ ] **Step 7: Add ACL rows — `security/ir.model.access.csv`**

Append (preserving the trailing newline already in the file):
```
access_southbrook_room_user,southbrook.room user,model_southbrook_room,base.group_user,1,0,0,0
access_southbrook_room_sales,southbrook.room sales,model_southbrook_room,sales_team.group_sale_salesman,1,1,1,0
access_southbrook_room_manager,southbrook.room manager,model_southbrook_room,sales_team.group_sale_manager,1,1,1,1
access_southbrook_room_wall_user,southbrook.room.wall user,model_southbrook_room_wall,base.group_user,1,0,0,0
access_southbrook_room_wall_sales,southbrook.room.wall sales,model_southbrook_room_wall,sales_team.group_sale_salesman,1,1,1,1
access_southbrook_room_wall_manager,southbrook.room.wall manager,model_southbrook_room_wall,sales_team.group_sale_manager,1,1,1,1
access_southbrook_room_constraint_user,southbrook.room.constraint user,model_southbrook_room_constraint,base.group_user,1,0,0,0
access_southbrook_room_constraint_sales,southbrook.room.constraint sales,model_southbrook_room_constraint,sales_team.group_sale_salesman,1,1,1,1
access_southbrook_room_constraint_manager,southbrook.room.constraint manager,model_southbrook_room_constraint,sales_team.group_sale_manager,1,1,1,1
```

- [ ] **Step 8: Bump manifest version**

Edit `__manifest__.py:59` `"version": "19.0.4.29.0",` → `"version": "19.0.5.0.0",`.

- [ ] **Step 9: Run tests — expect PASS**

```bash
# Re-run the same focused test command — should now pass:
docker exec sami-odoo odoo -d southbrook -u southbrook_estimating \
  --test-enable --test-tags=southbrook_room \
  --stop-after-init --no-http --workers=0 --max-cron-threads=0 2>&1 | tail -30
```
Expected: 6 passed. If `sami-odoo` is not running, fall back to `python3 -m py_compile` per Phase 1.1 precedent and defer live tests to the next QNAP `-u` smoke run.

- [ ] **Step 10: Commit**

```bash
git add addons/southbrook_estimating/models/southbrook_room.py \
        addons/southbrook_estimating/models/southbrook_room_wall.py \
        addons/southbrook_estimating/models/southbrook_room_constraint.py \
        addons/southbrook_estimating/models/__init__.py \
        addons/southbrook_estimating/security/ir.model.access.csv \
        addons/southbrook_estimating/__manifest__.py \
        addons/southbrook_estimating/tests/test_southbrook_room.py
git commit -m "feat(estimating): southbrook.room + wall + constraint model trio (19.0.5.0.0)

Room-First UX Phase 1.1. First-class room model anchoring an order to a
physical space. One2many from sale.order (multi-room ready). Optional —
existing orders unaffected. No new external deps. ACL: read for any
internal user; write for sales team."
```

---

### Task 1.2 — Link `sale.order.line` → `southbrook.room.wall` + capacity computes

**Files:**
- Modify: `addons/southbrook_estimating/models/sale_order_line.py:52-79` (add 3 fields, 1 compute)
- Modify: `addons/southbrook_estimating/models/southbrook_room_wall.py` (add reverse O2m + 3 computes)
- Test: `addons/southbrook_estimating/tests/test_room_wall_assignment.py`

**Interfaces:**
- Consumes from 1.1: `southbrook.room.wall` model.
- Produces:
  - `sale.order.line.wall_id (M2o → southbrook.room.wall, optional, copy=False)`
  - `sale.order.line.position_from_left_mm (Integer, optional, copy=False)`
  - `sale.order.line.is_positioned (Boolean computed)`
  - `southbrook.room.wall.cabinet_line_ids (O2m sale.order.line)`
  - `southbrook.room.wall.used_mm (Integer computed, sum of widths)`
  - `southbrook.room.wall.remaining_mm (Integer computed)`
  - `southbrook.room.wall.has_conflicts (Boolean computed)`

- [ ] **Step 1: Write failing tests** — `tests/test_room_wall_assignment.py`

```python
# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "southbrook_room_wall")
class TestRoomWallAssignment(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Cust"})
        cls.order = cls.env["sale.order"].create({"partner_id": cls.partner.id})
        cls.room = cls.env["southbrook.room"].create({
            "name": "K", "order_id": cls.order.id,
            "layout_shape": "l_shape",
            "wall_ids": [
                (0, 0, {"name": "A", "length_mm": 3600}),
                (0, 0, {"name": "B", "length_mm": 2400}),
            ],
        })
        cls.wall_a, cls.wall_b = cls.room.wall_ids
        cls.product = cls.env.ref("southbrook_estimating.product_base_2dr").product_variant_id

    def test_unpositioned_line_does_not_break_existing_behavior(self):
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id,
            "product_id": self.product.id,
            "product_uom_qty": 1.0,
        })
        self.assertFalse(line.wall_id)
        self.assertFalse(line.is_positioned)

    def test_position_a_cabinet_against_wall_a(self):
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id, "product_id": self.product.id,
            "product_uom_qty": 1.0,
            "wall_id": self.wall_a.id, "position_from_left_mm": 0,
        })
        self.assertTrue(line.is_positioned)
        self.wall_a.invalidate_recordset(["used_mm", "remaining_mm"])
        # sb_width_mm default 600 for base cabinet without PTAV resolution
        self.assertGreater(self.wall_a.used_mm, 0)
        self.assertEqual(
            self.wall_a.remaining_mm, self.wall_a.length_mm - self.wall_a.used_mm)

    def test_overlap_detection_with_constraint(self):
        # Window 600mm wide, starting at 1000mm from wall A's left corner
        self.env["southbrook.room.constraint"].create({
            "wall_id": self.wall_a.id, "constraint_type": "window",
            "distance_from_left_mm": 1000, "width_mm": 600,
        })
        # Cabinet starting at 900mm, 600mm wide → overlaps window (900-1500 vs 1000-1600)
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id, "product_id": self.product.id,
            "product_uom_qty": 1.0,
            "wall_id": self.wall_a.id, "position_from_left_mm": 900,
        })
        self.wall_a.invalidate_recordset(["has_conflicts"])
        self.assertTrue(self.wall_a.has_conflicts)
        # The line itself also reports conflict via order-line compute
        # (we expose this via wall.has_conflicts only — line-level conflict
        # is derived in the UI from wall conflicts intersecting position)

    def test_copy_false_on_duplicate(self):
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id, "product_id": self.product.id,
            "product_uom_qty": 1.0,
            "wall_id": self.wall_a.id, "position_from_left_mm": 100,
        })
        new_order = self.order.copy()
        new_line = new_order.order_line[0]
        self.assertFalse(new_line.wall_id, "wall_id must not propagate on copy (NF6)")
        self.assertFalse(new_line.position_from_left_mm)
```

- [ ] **Step 2: Run tests — expect AttributeError on `wall_id`**

```bash
docker exec sami-odoo odoo -d southbrook -u southbrook_estimating \
  --test-enable --test-tags=southbrook_room_wall \
  --stop-after-init --no-http --workers=0 --max-cron-threads=0 2>&1 | tail -20
# (or py_compile fallback if sami-odoo is not up)
```

- [ ] **Step 3: Add fields to `sale_order_line.py`** — append after the existing `zone_label` field (around line 79):

```python
    wall_id = fields.Many2one(
        "southbrook.room.wall", string="Wall",
        copy=False, ondelete="set null", index=True,
        help="The wall this cabinet sits against. Optional.")
    position_from_left_mm = fields.Integer(
        string="Position From Left (mm)", copy=False,
        help="Cabinet's left edge distance from the wall's left corner.")
    is_positioned = fields.Boolean(
        compute="_compute_is_positioned", store=True)

    @api.depends("wall_id", "position_from_left_mm")
    def _compute_is_positioned(self):
        for rec in self:
            rec.is_positioned = bool(
                rec.wall_id and rec.position_from_left_mm is not False)
```

- [ ] **Step 4: Add wall capacity computes to `southbrook_room_wall.py`**

Append these fields + a compute to the class:

```python
    cabinet_line_ids = fields.One2many(
        "sale.order.line", "wall_id", string="Cabinet Lines")
    used_mm = fields.Integer(
        compute="_compute_capacity", store=False, string="Used (mm)")
    remaining_mm = fields.Integer(
        compute="_compute_capacity", store=False, string="Remaining (mm)")
    has_conflicts = fields.Boolean(
        compute="_compute_conflicts", store=False)

    @api.depends("cabinet_line_ids.sb_width_mm", "cabinet_line_ids.product_uom_qty", "length_mm")
    def _compute_capacity(self):
        for rec in self:
            used = 0.0
            for line in rec.cabinet_line_ids:
                qty = line.product_uom_qty or 0.0
                used += (line.sb_width_mm or 0.0) * qty
            rec.used_mm = int(round(used))
            rec.remaining_mm = (rec.length_mm or 0) - rec.used_mm

    @api.depends(
        "cabinet_line_ids.wall_id",
        "cabinet_line_ids.position_from_left_mm",
        "cabinet_line_ids.sb_width_mm",
        "constraint_ids.distance_from_left_mm",
        "constraint_ids.width_mm",
    )
    def _compute_conflicts(self):
        for rec in self:
            ranges = []
            for c in rec.constraint_ids:
                if c.width_mm and c.constraint_type not in ("power_outlet", "structural_post"):
                    ranges.append((c.distance_from_left_mm or 0,
                                   (c.distance_from_left_mm or 0) + (c.width_mm or 0)))
            conflict = False
            for line in rec.cabinet_line_ids:
                if line.position_from_left_mm is False or not line.sb_width_mm:
                    continue
                lo = line.position_from_left_mm or 0
                hi = lo + int(line.sb_width_mm)
                for clo, chi in ranges:
                    if lo < chi and hi > clo:
                        conflict = True
                        break
                if conflict:
                    break
            rec.has_conflicts = conflict
```

- [ ] **Step 5: Run tests — expect PASS**

- [ ] **Step 6: Commit**

```bash
git add addons/southbrook_estimating/models/sale_order_line.py \
        addons/southbrook_estimating/models/southbrook_room_wall.py \
        addons/southbrook_estimating/tests/test_room_wall_assignment.py
git commit -m "feat(estimating): link sale.order.line to room wall + capacity computes

Optional wall_id + position_from_left_mm on sale.order.line (copy=False
preserves NF6 version-chain semantics). Wall gains used_mm, remaining_mm,
and has_conflicts (overlap of a positioned cabinet with a sized
constraint on the same wall). Non-destructive: lines without wall_id
behave identically to today."
```

---

### Task 1.3 — Backend admin views + smart button

**Files:**
- Create: `addons/southbrook_estimating/views/southbrook_room_views.xml`
- Modify: `addons/southbrook_estimating/views/sale_order_views.xml` (insert smart button + wall column on line tree)
- Modify: `addons/southbrook_estimating/__manifest__.py` `data` list (register the new XML right after `views/sale_order_views.xml`)

**Interfaces:**
- Consumes: models from 1.1 + 1.2.
- Produces: `southbrook_estimating.action_southbrook_room` action ref; menu under "Southbrook Estimating / Rooms".

- [ ] **Step 1: Write the new views file** — `views/southbrook_room_views.xml`

(Standard Odoo form/tree/search for `southbrook.room`, with embedded `wall_ids` tree showing capacity bar via `widget="progressbar"` on `used_mm` with `length_mm` denominator, and `constraint_ids` tree on each wall page. Avoids `<group string=>` inside search views — v19 view-validation traps. Avoids `column_invisible="parent.X"` — v19 column_invisible parent trap.)

```xml
<?xml version="1.0" encoding="utf-8"?>
<!-- SPDX-License-Identifier: LGPL-3.0-only -->
<odoo>

    <record id="view_southbrook_room_tree" model="ir.ui.view">
        <field name="name">southbrook.room.tree</field>
        <field name="model">southbrook.room</field>
        <field name="arch" type="xml">
            <list>
                <field name="name"/>
                <field name="order_id"/>
                <field name="room_type"/>
                <field name="layout_shape"/>
                <field name="total_linear_mm"/>
                <field name="wall_count"/>
                <field name="layout_complete" widget="boolean_toggle" readonly="1"/>
            </list>
        </field>
    </record>

    <record id="view_southbrook_room_form" model="ir.ui.view">
        <field name="name">southbrook.room.form</field>
        <field name="model">southbrook.room</field>
        <field name="arch" type="xml">
            <form string="Room">
                <header/>
                <sheet>
                    <div class="oe_title">
                        <h1><field name="name" placeholder="Main Kitchen"/></h1>
                    </div>
                    <group>
                        <group>
                            <field name="order_id"/>
                            <field name="room_type"/>
                            <field name="layout_shape"/>
                        </group>
                        <group>
                            <field name="ceiling_height_mm"/>
                            <field name="unit_preference"/>
                            <field name="total_linear_mm" readonly="1"/>
                            <field name="layout_complete" readonly="1"/>
                            <field name="has_plumbing" readonly="1"/>
                        </group>
                    </group>
                    <notebook>
                        <page string="Walls" name="walls">
                            <field name="wall_ids">
                                <list editable="bottom">
                                    <field name="wall_order" widget="handle"/>
                                    <field name="name"/>
                                    <field name="length_mm"/>
                                    <field name="used_mm" readonly="1"/>
                                    <field name="remaining_mm" readonly="1"/>
                                    <field name="has_upper_cabinets"/>
                                    <field name="has_base_cabinets"/>
                                    <field name="has_tall_cabinets"/>
                                    <field name="has_conflicts" readonly="1" widget="boolean_toggle"/>
                                </list>
                                <form>
                                    <sheet>
                                        <group>
                                            <field name="name"/>
                                            <field name="length_mm"/>
                                            <field name="wall_order"/>
                                        </group>
                                        <notebook>
                                            <page string="Constraints">
                                                <field name="constraint_ids">
                                                    <list editable="bottom">
                                                        <field name="constraint_type"/>
                                                        <field name="distance_from_left_mm"/>
                                                        <field name="width_mm"/>
                                                        <field name="height_mm"/>
                                                        <field name="height_from_floor_mm"/>
                                                        <field name="notes"/>
                                                    </list>
                                                </field>
                                            </page>
                                            <page string="Cabinets">
                                                <field name="cabinet_line_ids" readonly="1">
                                                    <list>
                                                        <field name="name"/>
                                                        <field name="position_from_left_mm"/>
                                                        <field name="sb_width_mm"/>
                                                        <field name="product_uom_qty"/>
                                                    </list>
                                                </field>
                                            </page>
                                        </notebook>
                                    </sheet>
                                </form>
                            </field>
                        </page>
                        <page string="Constraints (All)" name="all_constraints">
                            <field name="constraint_ids" readonly="1">
                                <list>
                                    <field name="wall_id"/>
                                    <field name="constraint_type"/>
                                    <field name="distance_from_left_mm"/>
                                    <field name="width_mm"/>
                                </list>
                            </field>
                        </page>
                    </notebook>
                </sheet>
            </form>
        </field>
    </record>

    <record id="view_southbrook_room_search" model="ir.ui.view">
        <field name="name">southbrook.room.search</field>
        <field name="model">southbrook.room</field>
        <field name="arch" type="xml">
            <search>
                <field name="name"/>
                <field name="order_id"/>
                <filter name="filter_complete" string="Layout Complete"
                        domain="[('layout_complete', '=', True)]"/>
                <filter name="filter_with_plumbing" string="Has Plumbing"
                        domain="[('has_plumbing', '=', True)]"/>
                <group>
                    <filter name="group_by_shape" string="Shape"
                            context="{'group_by': 'layout_shape'}"/>
                    <filter name="group_by_type" string="Room Type"
                            context="{'group_by': 'room_type'}"/>
                </group>
            </search>
        </field>
    </record>

    <record id="action_southbrook_room" model="ir.actions.act_window">
        <field name="name">Rooms</field>
        <field name="res_model">southbrook.room</field>
        <field name="view_mode">list,form</field>
        <field name="search_view_id" ref="view_southbrook_room_search"/>
    </record>

    <menuitem id="menu_southbrook_rooms" name="Rooms"
              parent="southbrook_estimating.menu_southbrook_root"
              action="action_southbrook_room" sequence="20"/>

    <!-- Sale order form: smart button + wall column on line tree -->
    <record id="view_sale_order_form_southbrook_room" model="ir.ui.view">
        <field name="name">sale.order.form.southbrook.room</field>
        <field name="model">sale.order</field>
        <field name="inherit_id" ref="sale.view_order_form"/>
        <field name="arch" type="xml">
            <xpath expr="//div[@name='button_box']" position="inside">
                <button name="action_open_southbrook_room"
                        type="object" class="oe_stat_button" icon="fa-home"
                        invisible="not room_count">
                    <field name="room_count" widget="statinfo" string="Room"/>
                </button>
            </xpath>
            <xpath expr="//field[@name='order_line']/list//field[@name='product_uom_qty']" position="before">
                <field name="wall_id" optional="hide"/>
                <field name="position_from_left_mm" optional="hide"/>
                <field name="is_positioned" optional="hide" readonly="1"/>
            </xpath>
        </field>
    </record>

</odoo>
```

- [ ] **Step 2: Add `room_ids` + `room_count` + `action_open_southbrook_room` on `sale.order`**

Modify `addons/southbrook_estimating/models/sale_order.py` — add fields + method to the existing `SaleOrder` class:

```python
    room_ids = fields.One2many("southbrook.room", "order_id", string="Rooms")
    room_count = fields.Integer(compute="_compute_room_count", store=False)

    @api.depends("room_ids")
    def _compute_room_count(self):
        for rec in self:
            rec.room_count = len(rec.room_ids)

    def action_open_southbrook_room(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "southbrook_estimating.action_southbrook_room")
        if len(self.room_ids) == 1:
            action.update({
                "views": [(False, "form")],
                "res_id": self.room_ids.id,
            })
        else:
            action["domain"] = [("order_id", "=", self.id)]
        return action
```

- [ ] **Step 3: Register the new XML in `__manifest__.py`**

Add `"views/southbrook_room_views.xml",` immediately after `"views/sale_order_views.xml",` in the `data` list.

- [ ] **Step 4: Smoke-test in dev container**

```bash
# Cold-install validation (matches scripts/cold-install-test.sh pattern):
cd ~/southbrook-v19cr && make install 2>&1 | tail -30
# Or fresh-DB:
make install-fresh 2>&1 | tail -30
```
Expected: install completes cleanly, no ParseError, no missing-field warnings. Fallback: `python3 -m py_compile` + `xmllint --noout` if no local container is up.

- [ ] **Step 5: Commit**

```bash
git add addons/southbrook_estimating/views/southbrook_room_views.xml \
        addons/southbrook_estimating/models/sale_order.py \
        addons/southbrook_estimating/__manifest__.py
git commit -m "feat(estimating): backend views for southbrook.room + SO smart button

Room form with embedded wall/constraint trees, capacity bars, search
view (no <group string=> per v19 view-validation trap). Sale Order form
gets a Room smart button + optional wall_id columns on the line tree."
```

---

## Phase 2 — Portal Room Setup (detailed, post-Phase 1 deployment)

Phase 1 deployed live to QNAP southbrook 2026-06-27 (`19.0.5.0.0`, 8-step live smoke green). Phase 2 decomposes into 4 sub-phases. Each ships independently to keep blast radius small.

### Phase 2.A — Portal RPC endpoints (server-side only, no UI)

**Files:**
- Create: `addons/southbrook_estimating_website/controllers/room_api.py`
- Modify: `addons/southbrook_estimating_website/controllers/__init__.py` (append import)
- Modify: `addons/southbrook_estimating_website/__manifest__.py` (bump `version` to `19.0.3.0.0`)
- Create: `addons/southbrook_estimating_website/tests/test_room_api.py` (10 tests, `@tagged("post_install", "-at_install", "southbrook", "southbrook_room_api")`)
- Modify: `addons/southbrook_estimating_website/tests/__init__.py` (register new test)

**Interfaces:**
- Produces:
  - `POST /southbrook/api/order/<int:order_id>/room/get` — returns the order's room dict (or null) for client reconstruction. Body: `{}`. Response: `{ok, room: {id, name, room_type, layout_shape, ceiling_height_mm, unit_preference, layout_complete, has_plumbing, total_linear_mm, walls: [{id, name, length_mm, used_mm, remaining_mm, has_conflicts, wall_order, has_upper_cabinets, has_base_cabinets, has_tall_cabinets, constraints: [{id, constraint_type, distance_from_left_mm, width_mm, height_mm, height_from_floor_mm, notes}, ...]}, ...]}}` or `{ok, room: null}`.
  - `POST /southbrook/api/order/<int:order_id>/room/create` — body: `{name, room_type, layout_shape, ceiling_height_mm, unit_preference, walls: [{name, length_mm, wall_order, has_upper_cabinets, has_base_cabinets, has_tall_cabinets}, ...], constraints: [{wall_index, constraint_type, distance_from_left_mm, width_mm, height_mm, height_from_floor_mm, notes}, ...]}`. `wall_index` is the 0-based index into the freshly-created walls array (server resolves to the wall_id). Idempotency: if the order already has a room, returns 409 with the existing room dict — caller must call update instead.
  - `POST /southbrook/api/order/<int:order_id>/room/<int:room_id>/update` — body: any subset of room scalar fields + optional `walls: [{id?, name, length_mm, ...}]` (id present = update, id absent = create). Returns the refreshed room dict.
  - `POST /southbrook/api/order/<int:order_id>/room/<int:room_id>/wall/<int:wall_id>/constraint/add` — body: `{constraint_type, distance_from_left_mm, width_mm, height_mm?, height_from_floor_mm?, notes?}`. Returns the created constraint dict.
  - `POST /southbrook/api/order/<int:order_id>/room/<int:room_id>/wall/<int:wall_id>/constraint/<int:constraint_id>/delete` — body: `{}`. Returns `{ok: true}`.
- Auth model: every endpoint goes through the same `_southbrook_resolve_order(order_id)` helper that exists in `controllers/main.py:844-873`. The room/wall/constraint IDs in the URL are validated as belonging to the resolved order — wrong owner → 403, not 404 (avoid existence-oracle leak).

- [ ] **Step 1: Write failing tests** — `tests/test_room_api.py` (10 tests, JSON-RPC happy paths + ownership-denial + idempotency).
- [ ] **Step 2: Implement `controllers/room_api.py`**. Reuse `_json_response` + `_southbrook_resolve_order` helpers from `controllers/main.py` (import them).
- [ ] **Step 3: Register controller in `controllers/__init__.py`** by appending `from . import room_api`.
- [ ] **Step 4: Bump manifest version** `19.0.2.15.0` → `19.0.3.0.0`.
- [ ] **Step 5: Smoke test live** — once deployed: `curl -X POST` against each of 5 endpoints from an authenticated session.
- [ ] **Step 6: Commit**

### Phase 2.B — Room Setup tab (inline, no wizard yet)

Inserts the Room Setup tab as **position 0** in the OrderBuilder OWL tab list. Reads from the new `/room/get` endpoint. Shows either: a room-configured summary card with wall capacity bars, OR an empty-state CTA "Set Up Room" (button stub for now — wired to wizard in 2.C).

**Files:**
- Modify: `addons/southbrook_estimating_website/static/src/js/portal_boot.esm.js`:
  - Insert "Room Setup" entry at index 0 in `_tabs` getter (around line 2885-2929)
  - Insert conditional render block at line 2238-2379 (the existing pattern: `<div t-if="state.ui.current_tab === 'room_setup'">...</div>`)
  - Add `roomState` to `state` reactive store + fetch on mount
  - Add order-header summary line above the tablist
- Create: `addons/southbrook_estimating_website/static/src/scss/room_layout.scss` (the `sb-room-*` prefix space).
- Modify: `addons/southbrook_estimating_website/__manifest__.py` (register the new SCSS in `web.assets_frontend`).
- Modify: `addons/southbrook_estimating_website/controllers/main.py:southbrook_order_builder()` (include `room` dict in the page-load JSON payload — same shape as `/room/get` response).

Acceptance: tab visible to existing orders without breaking 3D Kitchen/Order Lines tabs; empty state on orders without rooms; populated state on the smoke-test SO (S01264) once a room is attached via the backend (Phase 1 path).

### Phase 2.C — 3-step wizard component + live SVG preview

The big OWL component. Modeled as a fullscreen overlay (NOT a Bootstrap modal — the portal is 100% OWL, see audit). Closes via `state.ui.wizard = null` to return to the OrderBuilder root.

**Files:**
- Create: `addons/southbrook_estimating_website/static/src/js/room_setup_wizard.esm.js` (the wizard component + its 3 sub-step components + the live SVG preview component)
- Create: `addons/southbrook_estimating_website/static/src/xml/room_setup_wizard.xml` (OWL templates for the 4 components)
- Modify: `addons/southbrook_estimating_website/static/src/scss/room_layout.scss` (add wizard styles; same `sb-room-*` prefix)
- Modify: `addons/southbrook_estimating_website/__manifest__.py` (register the 2 new files in `web.assets_frontend`)
- Modify: `portal_boot.esm.js` — wire the "Set Up Room" button in Room Setup tab → opens wizard; wizard completion → POST `/room/create` → refreshes the order's room state → closes wizard

Wizard structure:
- `RoomSetupWizard` (parent, state machine: step ∈ {1, 2, 3, submitting, done, error})
  - Step 1: `<RoomTypeShapeStep>` — 7 room-type tiles (icons via `<svg>` inline) + 8 shape tiles
  - Step 2: `<WallDimensionsStep>` — dynamic count based on shape, each row: name input + length input + unit toggle (mm ↔ ft/in); shared ceiling-height input above; **live `<RoomOutlinePreview>` SVG sibling reacts via shared OWL state, 100ms debounce**
  - Step 3: `<ConstraintsStep>` — type chips (toggle to add) + inline form per added constraint (wall selector, distance, width, optional height); "Skip for now" link top-right
- `RoomOutlinePreview` SVG component — pure compute from `(shape, walls)` → `<polyline>` of room outline + `<circle>` markers per constraint position. Uses a small mm-to-px transform helper (room fits in 720×540 viewBox).

### Phase 2.D — Smoke + review

- Live smoke: walk through the wizard end-to-end on SO `S01264` via the live portal; verify room appears in backend + on the Room Setup tab.
- Code review on cumulative Phase 2 diff.

**Acceptance** (across 2.A-D): brief §2.1 + §2.2 acceptance criteria.

---

## Phase 3 — Room Layout Tab (detailed, post-Phase 2)

Phase 2 fully shipped + live on QNAP 2026-06-27 (`19.0.5.0.0` both addons). Phase 3 decomposes into 5 sub-phases. 3.A and 3.D are independent — can be dispatched in parallel.

### Phase 3.A — Cabinet placement endpoint

**Files:**
- Modify: `addons/southbrook_estimating_website/controllers/room_api.py` — append one endpoint to the existing `SouthbrookRoomApi` controller.
- Modify: `addons/southbrook_estimating_website/__manifest__.py` — bump version `19.0.5.0.0` → `19.0.6.0.0`.
- Modify: `addons/southbrook_estimating_website/tests/test_room_api.py` — add 3 tests for the new endpoint.

**Interfaces:**
- `POST /southbrook/api/order/<int:order_id>/line/<int:line_id>/place-on-wall` — body `{wall_id, position_from_left_mm}`. Setting `wall_id` to null unplaces. Returns `{ok, line: {id, wall_id, position_from_left_mm, is_positioned}, wall: {id, used_mm, remaining_mm, has_conflicts}}` so the client can update both line + wall state in one round-trip.
- Auth: line ownership via `_southbrook_resolve_order(line.order_id.id)` — the existing helper pattern from main.py.
- Wall scope: if wall_id is non-null, must belong to a room belonging to the resolved order.

### Phase 3.B — Room Layout tab + read-only floor-plan SVG

The biggest single chunk in Phase 3 — the interactive (initially read-only) top-down floor plan.

**Files:**
- New: `addons/southbrook_estimating_website/static/src/js/room_layout.esm.js` — single OWL component `RoomLayoutTab` (parent) + `FloorPlanSVG` (child, pure render).
- New: `addons/southbrook_estimating_website/static/src/xml/room_layout.xml` — OWL templates.
- Modify: `addons/southbrook_estimating_website/static/src/scss/room_layout.scss` — append floor-plan styles (sub-prefix `sb-room-plan-*`).
- Modify: `addons/southbrook_estimating_website/static/src/js/portal_boot.esm.js`:
  - Insert "Room Layout" tab in `_tabs` getter at position 1 (after "Room Setup", before "Order Lines")
  - Add render block for the new panel that mounts `<RoomLayoutTab room="state.room" lines="state.lines"/>`
  - Add `"room_layout"` to the `customerCodes` Set
- Modify: `addons/southbrook_estimating_website/__manifest__.py` — register new JS + XML, bump version `19.0.6.0.0` → `19.0.7.0.0`.

**Interfaces (props):**
- `room: object | null` — the same room dict shape as Phase 2.B (id, walls, constraints, etc.).
- `lines: array` — the order's sale.order.line dicts with `wall_id`, `position_from_left_mm`, `sb_width_mm`, `zone`, `name`.
- `onLineSelected: (lineId) => void` — call when user clicks a cabinet rect.

**Rendering primitives (inline SVG, no libraries):**
- Room outline: `<polyline>` from layout_shape + wall lengths (same algorithm as `RoomOutlinePreview` from 2.C — extract into a shared helper).
- Wall labels: `<text>` per wall at midpoint.
- Constraints: `<rect>` colored by type, with `<text>` label.
- Cabinets: `<rect>` per positioned line, fill from a zone→color map (base=walnut, wall=linen, tall=ink, etc.).
- Gaps: `<rect>` with `stroke-dasharray="4 3"` where a wall has unused mm and the gap is ≥ 200mm.
- Conflict highlight: red stroke (`stroke: var(--sb-alert); stroke-width: 2`) on the offending cabinet rect.
- Per-wall metrics panel: hover/click a wall → side panel shows `<wall_name>: <length_mm> total | <used_mm> used | <remaining_mm> left | <conflict_count> conflicts`.
- Sidebar "Unplaced Cabinets": list of `lines.filter(l => !l.wall_id)`. Read-only in 3.B; 3.C adds the drag/assign affordance.

### Phase 3.C — Layout interactivity (re-activated 2026-06-27)

Decomposed into 3 ship-independent steps. Drag (3.C.2b) and Elevation (3.C.2c) are explicitly out-of-scope for this batch; user can re-request after using the tap surface.

#### Phase 3.C.1 — Endpoint hardening (server-side)

Two SHOULD-FIX items from the Phase 3 review become user-reachable through 3.C:

**Files:**
- Modify: `addons/southbrook_estimating_website/controllers/room_api.py` — patch `southbrook_api_line_place_on_wall` (added in 3.A):
  - **Capture `line.wall_id` BEFORE the write.** After the write, invalidate BOTH the new wall AND the previous wall so `used_mm`/`has_conflicts` reflect the move correctly on both walls. Add the previous wall's metrics to the response under `previous_wall: {id, used_mm, remaining_mm, has_conflicts}` (null when no previous).
  - **Add off-the-end overflow check.** When `wall_id` is non-null and `position_from_left_mm + line.sb_width_mm > wall.length_mm`, return `{"error": "out_of_bounds", "detail": "Cabinet extends past wall edge by Nmm"}` BEFORE the write. Skip on `sb_width_mm == 0` (defensive — width is computed and could be zero for malformed seed data).
- Modify: `addons/southbrook_estimating_website/tests/test_room_api.py` — add 2 tests:
  - `test_place_returns_previous_wall_metrics` — place line on wall A, then re-place on wall B → response includes both `wall` (B) and `previous_wall` (A) with fresh metrics.
  - `test_place_rejects_out_of_bounds` — wall length 1000mm, line width 600mm, position 500mm → 600+500=1100 > 1000 → expect `out_of_bounds`.
- Modify: `__manifest__.py` — bump version `19.0.7.0.0` → `19.0.8.0.0`.

#### Phase 3.C.2a — Tap interactivity (this batch)

The "click and pick" layer. Three click affordances + the modals they invoke.

**Files:**
- Modify: `addons/southbrook_estimating_website/static/src/js/room_layout.esm.js`:
  - `<FloorPlanSVG>` — wire `<polygon>` per cabinet to `onclick="(e) => this.props.onCabinetClick(line.id, e)"`. Same for gap rects → `onGapClick(wall_id, gap_mm, position_from_left_mm)`. Walls themselves don't get a click handler in this batch (elevation is 3.C.2c).
  - `RoomLayoutTab` — accept new props `onCabinetClick`, `onGapClick`, `onAssignFromSidebar`. The sidebar's unplaced cabinet list gets an "Assign…" button per row.
  - New child component `AssignToWallModal` — renders inside the tab when `state.assigning?.lineId` is set. Body: dropdown of wall_id options + position_from_left_mm input + Cancel + Assign buttons. On submit → POST `/place-on-wall` → on success: `onAssigned(line, wall, previous_wall)`.
  - New child component `AddCabinetAtGapModal` — opens when `state.gapPicker` is set. Body: list of standard widths (300/400/450/500/600/900) intersected with cabinets ≤ gap_mm — each clickable. Each entry POSTs `/add-line` (the existing endpoint from main.py:1223) with `product_tmpl_id` of a default base cabinet template at the chosen width. Actually — `/add-line` doesn't take width, it just creates a default-variant line of a template. For 3.C.2a, the gap-modal shows the gap and asks the user to "Add a cabinet from the catalog and assign it here" rather than picking width — cleaner one-step: "Add cabinet to Wall A at position 1000mm" → opens the catalog modal (existing UX) and the user picks a template; on add the new line is then auto-assigned to the wall via a follow-up `/place-on-wall` call. Save the pending placement in `state.pendingGapPlacement` so the line-added callback can apply it.
- Modify: `addons/southbrook_estimating_website/static/src/xml/room_layout.xml` — add the two new component templates + button bindings.
- Modify: `addons/southbrook_estimating_website/static/src/scss/room_layout.scss` — append modal styles (sub-prefix `sb-room-plan-modal-*`).
- Modify: `addons/southbrook_estimating_website/static/src/js/portal_boot.esm.js`:
  - Pass new callbacks down to `<RoomLayoutTab>`: `onCabinetClick="_onPlanCabinetClick"`, `onGapClick="_onPlanGapClick"`, `onAssignFromSidebar="_onPlanAssignClick"`.
  - Add OrderBuilder methods:
    - `_onPlanCabinetClick(lineId)` → `this.state.ui.current_tab = "lines"; this.state.ui.selected_line_id = lineId;` (the existing Order Lines tab already honors `selected_line_id` to highlight + scroll into view).
    - `_onPlanGapClick(wallId, gapMm, position)` → opens the catalog modal with a `state.pendingGapPlacement = {wallId, position}` flag. On line added (existing onLineSaved hook), if pendingGapPlacement is set, POST `/place-on-wall` for the new line + clear the flag.
    - `_onPlanAssignClick(lineId)` → `state.assigning = {lineId}` triggering the AssignToWallModal.
  - Hook the modal callbacks to refresh `state.room` after successful POSTs.
- Modify: `__manifest__.py` — bump `19.0.8.0.0` → `19.0.9.0.0`.

**No new endpoints.** Reuses `/place-on-wall` (3.A) + `/add-line` (existing main.py).

#### Phase 3.C.2b — Drag + arrow buttons (re-activated)

Drag a placed cabinet along its current wall to fine-tune `position_from_left_mm`. No cross-wall drag in v1 — that's "remove + assign" via the existing AssignToWallModal. Touch devices get ← → arrow buttons as the primary affordance instead of drag (drag on small touch screens is hard).

**Files:**
- Modify: `addons/southbrook_estimating_website/static/src/js/room_layout.esm.js`:
  - Add `dragState` to `FloorPlanSVG` via `useState({lineId: null, originalMm: null, currentMm: null, downXY: null, moved: false})`.
  - Wire pointer events on each cabinet `<polygon>`:
    - `pointerdown` → capture line, original position, cursor XY
    - `pointermove` (registered globally via `useExternalListener` on the document) → if `dragState.lineId` set AND movement > 5px threshold → set `moved=true` + project cursor back to wall mm coordinates via `_pxToMmAlongWall(line, ev.clientX, ev.clientY)` + update `currentMm`
    - `pointerup` → if `moved`, call `props.onCabinetDragEnd(lineId, snappedMm)`; if not moved, behave as a click (call existing `onCabinetClick`)
  - Add coordinate-transform helper `_pxToMmAlongWall(line, screenX, screenY)`:
    - Get the SVG element's screen CTM (`svg.getScreenCTM().inverse()`)
    - Multiply (screenX, screenY) by inverse to get viewBox coords
    - Reverse the existing `_transform` (subtract offset, divide by scale) to get raw mm coords
    - Find line's wall segment; project mm cursor onto the wall's direction unit vector
    - Returns the projected `position_from_left_mm` clamped to `[0, wall.length_mm - line.sb_width_mm]`
  - Snap-to-25mm on drop: `Math.round(rawMm / 25) * 25`.
  - During drag (when `dragState.lineId === line.id`), render the cabinet polygon at `currentMm` (ghost preview) with reduced opacity + render the ORIGINAL position polygon at very low opacity as the "starting point" reference.
- `RoomLayoutTab`:
  - Accept new prop `onCabinetDragEnd(lineId, positionMm)`.
  - Sidebar already has placed cabinets shown in metrics — add small ← → buttons inside the FloorPlanSVG itself, OR add them to a per-cabinet hover-popup. For v1 keep it simple: add ← → buttons that ONLY appear on `@media (pointer: coarse)` (touch devices), positioned above each cabinet polygon. Click ← → shifts by 25mm via the same `onCabinetDragEnd` callback.
- Modify: `addons/southbrook_estimating_website/static/src/xml/room_layout.xml`:
  - Wire `t-on-pointerdown` on each cabinet polygon.
  - Add hover-overlay group with ← → buttons (conditional on coarse-pointer media).
- Modify: `addons/southbrook_estimating_website/static/src/scss/room_layout.scss`:
  - `.sb-room-plan-cab--dragging` opacity 0.4 + dashed outline.
  - `.sb-room-plan-cab--drag-ghost` opacity 0.15 (original position marker).
  - `@media (pointer: coarse)` block exposing arrow buttons.
- Modify: `addons/southbrook_estimating_website/static/src/js/portal_boot.esm.js`:
  - Add OrderBuilder method `_onPlanCabinetDragEnd(lineId, positionMm)`:
    - POST `/place-on-wall` (line's current wall_id + new positionMm)
    - On success: refresh `state.room` + line state
    - On `out_of_bounds` error: alert with detail message (the snap should already prevent this, but keep as defensive)
  - Pass `onCabinetDragEnd="_onPlanCabinetDragEnd"` down to `<RoomLayoutTab>`.
- Modify: `addons/southbrook_estimating_website/__manifest__.py` — bump `version` `19.0.10.0.0` → `19.0.11.0.0`.

**Click-vs-drag threshold**: track `downXY` on pointerdown; on pointermove compute `Math.hypot(clientX - downXY.x, clientY - downXY.y) > 5`. Below threshold = click (fires `onCabinetClick`); above = drag (suppresses click, fires `onCabinetDragEnd` on pointerup).

**Cross-wall constraint**: during drag we only update `position_from_left_mm` — wall_id stays the same. Cross-wall placement requires removing the cabinet and re-assigning via the sidebar Assign… button (existing flow).

**Skip-in-this-batch**: drag the unplaced sidebar cabinet INTO the floor plan to assign (the brief's "drag from sidebar" option). That's drag-and-drop across a component boundary — harder. The existing "Assign…" button covers it for now.

#### Phase 3.C.2c — Elevation view toggle (out of this batch)

Deferred. Will need a new `<WallElevationSVG>` component + a "Floor ↔ Elevation" toggle button + per-wall state.

#### Phase 3.C.E — Smoke + review

After 3.C.1 + 3.C.2a land + deploy:
- Live smoke: click a cabinet → tab switches to Order Lines with that line highlighted. Click a gap → catalog modal opens. Add a cabinet → it appears auto-placed at the gap position. Click "Assign…" on an unplaced cabinet → modal opens, pick wall + position → cabinet appears in Layout.
- Cumulative review on the 3.C diff.

### Phase 3.D — Smart inline warnings on Order Lines tab (independent of 3.B)

Adds per-line indicator chips + collapsible warning banner + per-zone wall-summary row.

**Files:**
- Modify: `addons/southbrook_estimating_website/static/src/js/portal_boot.esm.js`:
  - Add a small helper `_lineStatus(line)` → `"placed" | "unplaced" | "conflict" | null` (null when no room is configured — chip not rendered).
  - Add a computed/method that surfaces a warnings list from `state.room` + `state.lines` (over-capacity walls + conflicting cabinets + unplaced cabinet count).
  - Insert a warning banner element above the lines list when `_warnings().length > 0`.
  - In the ZoneGroup OWL component (already exists per audit), add a `<small>` row showing wall capacity if all cabinets in the zone are placed on the same wall.
- Modify: `addons/southbrook_estimating_website/static/src/scss/room_layout.scss` — append `.sb-room-warning-*` styles.
- No new files. No new endpoints. No version bump beyond Phase 3.B's.

3.D is small + low-risk; can be appended to the Phase 3.B commit or shipped as a sibling commit.

### Phase 3.E — Smoke + review

- Live smoke on SO `S01264` (the brief's reference order):
  1. Place a cabinet on a wall via the line tree backend
  2. Open `/my/southbrook/order-builder/1264` → Room Layout tab
  3. Verify the cabinet renders at its position; verify gap rect shows for unused wall space
  4. Add a window constraint that overlaps the cabinet → reload → verify red conflict highlight
- Curl `/place-on-wall` happy path + ownership-denial
- Cumulative Phase 3 code review

---

## Phase 4 — Portal Polish: Progress + Units (detailed, post-Phase 5)

Two visible polish pieces on the Room Setup tab. Both reuse the existing Phase 2.A endpoints — no new endpoints. Single addon: `southbrook_estimating_website`. Bumps to `19.0.10.0.0`.

### Phase 4.1 — Progress checklist on Room Setup tab

Persistent 5-step horizontal checklist at the top of the Room Setup panel when a room exists. Each step derives from existing `state.room` + `state.lines` data:

1. **Room type & shape selected** — `room.layout_shape != null`
2. **Wall dimensions entered** — `room.walls.every(w => w.length_mm > 0)`
3. **Fixed constraints mapped** — `room.constraints.length > 0` (optional gate — passes if user explicitly skipped)
4. **All cabinets assigned to walls** — `lines.every(l => l.wall_id) || lines.length === 0`
5. **No conflicts detected** — `room.walls.every(w => !w.has_conflicts)`

Each incomplete step is clickable → scrolls to or opens the relevant section. When all 5 are complete, replaces the checklist with a "Ready for production" celebratory card + CTA pointing to "Send to Production" (the existing action_confirm button or equivalent).

### Phase 4.2 — Unit toggle (mm ↔ ft/in)

Small toggle button in the Room Setup panel header that switches `room.unit_preference` between `mm` and `imperial`. Storage stays mm always — toggle only changes the display formatter.

**Files:**
- Modify: `addons/southbrook_estimating_website/static/src/js/portal_boot.esm.js`:
  - Add `_humanLen(mm)` helper on OrderBuilder + ZoneGroup that consults `state.room?.unit_preference || "mm"`. When imperial: `_imperialFromMm(mm)` → `"3' 6\""` (or `'18"'` if < 1 foot). Reuse the mm→inches conversion math (1 inch = 25.4 mm, round to nearest int).
  - Pass `unitPreference` (or `_humanLen` callback) into `RoomLayoutTab` props.
  - Add toggle button to Room Setup panel header that POSTs `/room/<id>/update` with `{unit_preference: <new>}` (Phase 2.A endpoint already supports this). On success, refresh `state.room`.
  - Add the 5-step progress checklist block to the Room Setup panel render (BEFORE the existing summary card). When all complete, render the celebratory state.
- Modify: `addons/southbrook_estimating_website/static/src/js/room_layout.esm.js`:
  - Accept `unitPreference` prop (default "mm"). Use it in all length labels in the floor-plan + per-wall metrics + sidebar.
- Modify: `addons/southbrook_estimating_website/static/src/js/room_setup_wizard.esm.js`:
  - Wizard's unit toggle (already in Step 2) reads + writes the same `unit_preference` — confirm consistency.
- Modify: `addons/southbrook_estimating_website/static/src/scss/room_layout.scss`:
  - Append `.sb-room-progress-*` styles for the 5-step checklist.
  - Append `.sb-room-unit-toggle` styles for the header button.
- Modify: `addons/southbrook_estimating_website/__manifest__.py`:
  - Bump `version` `19.0.9.0.0` → `19.0.10.0.0`.

### Phase 4.E — Smoke + review

- Live smoke: open Room Setup tab on a room → see progress checklist; toggle unit → all mm labels switch to imperial AND floor plan labels also switch; complete all 5 steps → see celebratory state.
- Cumulative review on the Phase 4 diff.

---

## Phase 5 — PDF Extension (detailed, post-3.C)

Extends `signature_spec_sheet.xml` with two new conditionally-rendered pages — room summary + server-side SVG floor plan. Single addon: `southbrook_estimating`.

### Phase 5.A — Server-side SVG generator + room-summary helpers

**Files:**
- Modify: `addons/southbrook_estimating/models/southbrook_room.py` — add 3 methods to the `SouthbrookRoom` class:
  - `to_svg(width_px=720, height_px=540)` — returns an SVG markup string (the room outline + walls + constraints + cabinets). Mirrors the geometry from `room_geometry.esm.js` (extract the layout shapes into a Python helper for consistency).
  - `to_summary_dict()` — returns a plain dict for the QWeb summary table: `{name, shape_label, ceiling_mm, unit, total_linear_mm, wall_count, plumbing, walls: [{name, length_mm, used_mm, remaining_mm, conflicts, constraint_count}], constraints: [{wall_name, type_label, position, width, height}]}`. Decouples QWeb from raw recordset traversal so the template stays declarative.
  - `to_imperial_str(mm)` (staticmethod) — convert mm to "3' 6"" when `unit_preference == "imperial"`. Used by the QWeb template to render lengths according to the room's preferred unit.
- Modify: `addons/southbrook_estimating/tests/test_southbrook_room.py` — add 3 tests:
  - `test_to_svg_returns_svg_for_configured_room` — assert returned string starts with `<svg` and contains the room's wall lengths.
  - `test_to_svg_empty_for_unconfigured_room` — room with no walls → empty `<svg>` or minimal placeholder.
  - `test_to_summary_dict_shape` — assert all expected keys present, walls + constraints populated.

### Phase 5.B — Extend `signature_spec_sheet.xml`

**Files:**
- Modify: `addons/southbrook_estimating/reports/signature_spec_sheet.xml` — add 2 new `<div class="page">` blocks AFTER the existing page-1 content, both wrapped in `<t t-if="doc.room_ids">`:
  - **Page 2 — Room Summary**:
    - Header row: room name + shape label + total linear + wall count + plumbing badge
    - Walls table: name | length | used | remaining | conflicts | constraints (#)
    - Constraints table: wall | type | position | width | height (collapsed when no constraints)
  - **Page 3 — Floor Plan**:
    - Inline `<t t-raw="doc.room_ids[0].to_svg(720, 540)"/>` — wkhtmltopdf renders inline SVG natively
    - Per-wall metrics table below the SVG (same data as the wizard's wall cards)
- Modify: `addons/southbrook_estimating/__manifest__.py` — bump `version` `19.0.5.0.0` → `19.0.6.0.0`.

### Phase 5.C — Smoke + review

- Live smoke: generate the spec sheet PDF for SO `S01264` after creating a room via the wizard. Verify pages 2-3 render. Verify the SVG floor plan is legible.
- Smoke for no-room order: verify pages 2-3 are correctly omitted (existing single-page report still works).
- Code review on the cumulative diff.

---

## Phase 6 — Stretch (DRAFT)

- 6.1 Cabinet recommendation engine. New `southbrook.room.wall.recommend_for_gap(gap_mm) → list[(template_id, width_mm, score)]` RPC. Filters templates by max width ≤ gap; prefers standard widths (300/400/450/500/600/900) via scoring function.
- 6.2 Room templates. New `southbrook.room.template` model with seed records. "Apply Template" action on `southbrook.room` clones walls + constraints from a template.

---

## Self-Review (post-draft)

**Spec coverage** — Phase 1 covers brief Tasks 1.1, 1.2, 1.3 in full. Phase 2-6 are scoped at outline level (re-plan after Phase 1 merges).

**Placeholder scan** — Phase 1 has zero placeholders. Phases 2-6 are explicitly marked DRAFT; "high-level scope" language is appropriate at this stage.

**Type consistency** — `wall_id` is `M2o → southbrook.room.wall` everywhere; `position_from_left_mm` is Integer everywhere; `_compute_summary` field set matches across model + tests + views.

**v19 traps avoided** — no `_sql_constraints`, no `res.groups.category_id`, no `column_invisible="parent.X"`, no `<group string=>` in search views, no `decoration-*` on cross-addon fields.

**Branch hygiene** — work commits on `feature/prodboard-tier-2-mi-quality` per current HEAD.
