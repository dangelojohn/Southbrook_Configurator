---
course: 15 — Manufacturing Module Deep Dive
chapter: 15.4
title: BoM Extensions — Cut Constants, Panel Math, Lead-Time Bumps
duration: 35 minutes
audience: PLM engineer + Planner + Developer
prereqs: Lesson 15.1, Course 4 lesson 4.2 (cut specs), Course 11 lesson 11.x (BoM creation), basic Odoo mrp.bom knowledge
custom_modules: southbrook_estimating, southbrook_plm, southbrook_mrp_kitchen_workcenters, product_configurator_mrp
---

# BoM Extensions — Cut Constants, Panel Math, Lead-Time Bumps

## Who this lesson is for

You're a PLM engineer authoring cut specs, a planner trying to
understand why an MO landed with `effective_produce_delay = 28
days` when the cabinet says `produce_delay = 14`, or a developer
adding a new attribute that should affect lead time. The Southbrook
BoM extensions are five fields and seven methods — but the methods
are load-bearing for the entire cut-list pipeline, the cabinet 3D
preview, the FreeCAD bridge, and the shop copy report. This lesson
unpacks each piece and how they cooperate.

## Where this lives on the site

> **Manufacturing → Configuration → Bills of Materials → <BoM>**

The Southbrook fields show inline on the BoM form (no separate
notebook page — they're load-bearing computes that the planner needs
visible). The cut constants and panel math don't surface on the form
at all — they're called by the cutlist generator at MO time.

For the cut spec source-of-truth:

> **Southbrook PLM → Cut Specs** (`southbrook.cut.spec` records)

Exactly one cut spec is `active` at any time
(`_check_single_active` constraint). The `_get_cut_constants` seam
reads from the active spec.

## What your screen shows — fields on mrp.bom

### Owned by `southbrook_estimating`

| Label | Field (model.field, owner) | Type | Computed from |
|---|---|---|---|
| Southbrook Lead-Time Extra | `southbrook_lead_time_extra` (`mrp.bom`, estimating) | Float, stored compute | Sum of `lead_time_extra` over the variant's `product_template_attribute_value_ids → product_attribute_value_id.lead_time_extra` |
| Effective Produce Delay | `effective_produce_delay` (`mrp.bom`, estimating) | Float, stored compute | `produce_delay + southbrook_lead_time_extra` |

### Owned by `southbrook_plm`

| Label | Field (model.field, owner) | Type | What it tracks |
|---|---|---|---|
| BoM Version | `southbrook_version` (`mrp.bom`, plm) | Integer, default 1 | Incremented per ECO; prior version archived |
| ECOs Raised Against | `southbrook_eco_ids` (`mrp.bom`, plm) | One2many → `southbrook.eco` (inverse `bom_id`) | ECOs that target this BoM |
| ECO History | `southbrook_eco_history_ids` (`mrp.bom`, plm) | One2many → `southbrook.eco` (inverse `new_bom_id`) | ECOs that PRODUCED this BoM |
| ECO Count | `southbrook_eco_count` (`mrp.bom`, plm) | Integer, compute | Union count for smart button |

### Owned by `product_configurator_mrp` (OCA, not Southbrook-custom but shipped in the stack)

| Field | Type | What it does |
|---|---|---|
| `mrp.bom.config_ok` | Boolean (related, stored) | Mirrors `product_tmpl_id.config_ok`; flags configurable BoMs |
| `mrp.bom.line.config_set_id` | M2O → `mrp.bom.line.configuration.set` | Gates the BoM line to specific attribute-value combos |

## The eight cut constants

These are module-level floats in
`southbrook_estimating/models/mrp_bom.py` — the **baseline** before
any active cut spec overrides them. Real-world values, all mm:

| Constant | Default (mm) | Real-world | Consumed by |
|---|---|---|---|
| `BOX_TH` | 15.875 | 5/8" melamine carcass | Side/top/bottom/shelf thickness; `inside_width = W − 2·BOX_TH` |
| `BACK_TH` | 6.35 | 1/4" hardboard | Back panel thickness; shelf depth subtractor |
| `RABBET` | 6.35 | back-capture groove | Back length/width inflation; shelf depth subtractor |
| `DOOR_TH` | 18.0 | 3/4" door slab | Door thickness |
| `DOOR_REVEAL` | 3.0 | uniform door gap | Door L/W; 2-door split formula |
| `SHELF_TOL` | 1.5 | hand clearance | `shelf_l = inside_width − SHELF_TOL` |
| `SHELF_VENT_GAP` | 12.7 | 1/2" rear vent | `shelf_w = D − BACK_TH − RABBET − SHELF_VENT_GAP` |
| `TOEKICK_H` | 101.6 | 4" base toe-kick height | Declared but NOT consumed by current `_compute_panel_dimensions` (Phase 1 gap — toe-kick is integrated into side panels) |

Plus one set: `TOEKICK_FAMILIES = frozenset(['base', 'sink', 'tall',
'vanity'])` — declared, not yet consumed.

## The PLM seam — `_get_cut_constants()`

Defined in two places, with PLM overriding estimating:

| Where | Behaviour |
|---|---|
| `southbrook_estimating/models/mrp_bom.py:_get_cut_constants(self)` | `@api.model`. Returns the dict of module-level constants: `{box_th, back_th, rabbet, door_th, door_reveal, shelf_tol, shelf_vent_gap, toekick_h}`. |
| `southbrook_plm/models/mrp_bom.py:_get_cut_constants(self)` | Overrides. Looks up the active `southbrook.cut.spec` via `self.env['southbrook.cut.spec'].sudo()._get_active()`. If found, returns `active.constants_dict()` (same 8 keys, loaded from the spec record). If no active spec → falls back to `super()`. |

This is the load-bearing seam. PLM authors a cut spec, hits
`Activate` on it, the new constants take effect on every BoM call to
`_get_cut_constants()` from that moment on. No DB migration; no
recompile. The constraint `_check_single_active` enforces exactly
one active spec — see lesson 4.2 and lesson 1.7 for the PLM side.

**Test coverage**: `southbrook_plm/tests/test_eco_workflow.py`
asserts that an ECO-applied reveal change flows through to panel
dimensions via the seam.

## The math — `_compute_panel_dimensions(...)`

Signature:
```
@api.model
def _compute_panel_dimensions(
    self,
    width_mm, height_mm, depth_mm,
    family='base', door_count=1, drawer_count=0,
    finished_sides='none'
):
```

Returns a dict shaped like:
```
{
    'side_L':  (L, W, T) or None,
    'side_R':  (L, W, T) or None,
    'top':     (L, W, T) or None,
    'bottom':  (L, W, T) or None,
    'back':    (L, W, T) or None,
    'shelf':   (L, W, T) or None,
    'door':    (L, W, T) or None,
    'shelf_count':            int,
    'door_count':             int,
    'drawer_count':           int,
    'hinge_pair_count':       int,
    'handle_count':           int,
    'drawer_slide_pair_count':int,
    'edge_banding_length_mm': int,
}
```

The key formulas (from the active cut constants via
`_get_cut_constants()`):

- `inside_width = width_mm − 2·BOX_TH`
- `back = (inside_width + 2·RABBET, height_mm − 2·BOX_TH + 2·RABBET, BACK_TH)`
- Shelf-count heuristic: `H ≤ 600` → 1; `H ≤ 900` → 2; else 3.
- 1-door: `door = (height_mm − 2·DOOR_REVEAL, width_mm − 2·DOOR_REVEAL, DOOR_TH)`
- 2-door: width is split in half minus reveals.
- Drawer family: `door_count` is repurposed as drawer-front count;
  the dict's `drawer_count` mirrors `door_count` for the drawer
  family.

**Callers** (where the BoM math is consumed):

| Caller | File | What it does |
|---|---|---|
| Sale order pricing | `southbrook_estimating/models/sale_order.py:293` | Computes panel area for material cost |
| Configurator preview | `southbrook_estimating/models/product_config_line.py:99` | Feeds the 3D viewport |
| Website kitchen planner | `southbrook_estimating_website/controllers/main.py:1935` | Live 3D update as the customer drags handles |
| Cutlist generator | `sb.production.package.generate_from_mo` (lesson 15.7) calls `panel_cut_list(...)` which calls this | The MO-time cutlist is written from this output |
| FreeCAD bridge tests | `southbrook_freecad_bridge/tests/test_bom_contents.py` | Smoke tests panel geometry against expected |

## The perimeter — `_compute_edge_banding_length(...)`

Signature: `@api.model def _compute_edge_banding_length(self, width_mm, height_mm, depth_mm, finished_sides)`. Returns an int (mm).

Approach: sum of side-panel perimeters `2·(H + D)` for finished
sides ('both' → ×2, 'left' or 'right' → ×1) PLUS top + bottom
front-edge bands (`2 · inside_width`).

**KNOWN GAP**: This function reads module-level `BOX_TH` directly,
NOT via `_get_cut_constants()`. So an ECO-applied `box_th` change
will NOT flow through here. If you're authoring a cut spec change
to box thickness, log a ticket for this to be patched to route
through the seam.

## Lead-time extras

The chain:

1. **Master field** — `product.attribute.value.lead_time_extra`
   (Float, default 0.0) defined in
   `southbrook_estimating/models/product_attribute_value.py:59`. Per
   attribute value, "this value adds N days to the BoM produce_delay
   if selected on a variant."
2. **Seed example** — `data/attributes.xml:200`: maple box material
   has `lead_time_extra = 14.0` (two weeks).
3. **BoM rollup** — `mrp.bom.southbrook_lead_time_extra` (stored
   compute, depends
   `product_id.product_template_attribute_value_ids.product_attribute_value_id.lead_time_extra`).
   Sums across every attribute value chosen on the variant.
4. **Effective delay** — `mrp.bom.effective_produce_delay = produce_delay + southbrook_lead_time_extra` (stored compute).

**Consumed by**:

| Where | What it does |
|---|---|
| `southbrook_estimating/reports/shop_copy.xml:53,56-58` | Renders effective delay on the shop copy traveler |
| `southbrook_estimating_website/controllers/main.py:1888-1889` | Order ETA across multi-line orders takes MAX `effective_produce_delay` across all lines |

So a customer who picks a maple box on a base 1-door cabinet (14
days + base `produce_delay`) drives the entire order ETA, even if
other lines are stock 7-day items. This is intentional — the
customer's promise date has to honour the slowest line.

## The configurator-gated BoM lines (OCA, but you need to know)

`product_configurator_mrp` adds `mrp.bom.line.config_set_id`
(M2O → `mrp.bom.line.configuration.set`). A configuration set holds
many `value_ids` (M2M → `product.attribute.value`). At MO creation,
the configurator wizard filters BoM lines whose `config_set_id`
matches the chosen attribute-value combo on the variant. **No Python
inflates BoM lines from attributes** — it's all declarative gating.

This is why "BoM rollup of configured products" (a phrase the brief
sometimes uses) doesn't mean dynamic line creation. It means
`config_set_id` filtering. If a line has `config_set_id` empty, it
always applies; if set, it applies only when the variant's
attribute values match the set.

## Your daily flow

**1. PLM engineer authoring a new cut spec:**

- Open **Southbrook PLM → Cut Specs**, create new.
- Set the 8 constants (box_th, back_th, rabbet, door_th,
  door_reveal, shelf_tol, shelf_vent_gap, toekick_h).
- Save as `draft`. Run the suite of tests
  (`test_eco_workflow.py`) against a copy of the BoM math to
  verify the new spec doesn't crash anything.
- When ready, raise an ECO referencing the old spec → new spec.
  ECO approval transitions the new spec to `active` and the old
  to `superseded`. From that moment, every `_get_cut_constants()`
  call reads the new values.

**2. Planner debugging an unexpected ETA:**

- Customer's order shows ETA of 28 days. Native produce_delay on
  the cabinet is 14. Why 28?
- Open the BoM for the configured variant. Read
  `southbrook_lead_time_extra`. If it's 14, you've found the
  source — an attribute on that variant carries a 14-day bump.
- Click into the variant's
  `product_template_attribute_value_ids`. Find which attribute
  value has `lead_time_extra > 0`. Maple box is the common
  culprit at 14 days.
- Decide: educate the customer (real lead time on maple) or
  re-quote with a different material.

**3. Developer adding a new attribute that affects timing:**

- Open the attribute in
  **Sales → Configuration → Attributes**.
- For the relevant attribute value (e.g. "Soft-Close Drawers"),
  set `lead_time_extra` to the number of extra days needed.
- The BoM compute is reactive — every BoM whose variant uses this
  value automatically picks up the bump on the next page-load.
- Add a regression test in
  `southbrook_estimating/tests/test_bom_math.py` asserting the
  bump appears on `effective_produce_delay`.

## Common mistakes + how to recover

**"I activated a new cut spec but `_compute_edge_banding_length`
is still using the old box_th."**

KNOWN GAP. `_compute_edge_banding_length` reads module-level
`BOX_TH` directly, not via `_get_cut_constants()`. The fix is a
code change to route through the seam. Until then, any change to
`box_th` in a cut spec is ignored by the edge banding calculation.
File a ticket; work around by avoiding `box_th` changes via cut
spec.

**"I added `lead_time_extra = 7` on a new attribute value but the
BoM's `southbrook_lead_time_extra` didn't update."**

The compute depends on `product_template_attribute_value_ids` of
the BoM's variant. If your new attribute hasn't been applied to
any existing variant, no existing BoM's compute fires. Create or
configure a sale order line that picks the new value — the variant
gets created and the BoM reads the bump.

**"Two BoM lines have the same product and same quantity, but only
one fires at MO creation."**

`config_set_id` filtering. One line has a config set that matches
your attribute combo; the other has a set that doesn't. Open both
lines, inspect `config_set_id` and its `value_ids`.

**"`_compute_panel_dimensions` returned `door = None` for a
configured 1-door base. Where's the bug?"**

Check the family argument. If `family='base'` and `door_count=1`,
the door dict should be populated. If `door_count=0` (a drawer
bank), the door is None and `drawer_count` is repurposed. Likely
the caller passed `door_count=0` by mistake — check
`sale.order.line` or `product.config.line` for how it derived
`door_count` from the variant's attribute.

**"ECO activated but BoM's `southbrook_version` didn't bump."**

The version bump happens inside the ECO workflow, not the BoM
form. Open the ECO, walk through its state transitions — the
`southbrook.eco` state machine writes both the new BoM's version
and archives the old. If the ECO is stuck in `draft`, no bump
happens.

## What the system is doing behind the scenes

The BoM-side of the platform is **three addons cooperating**:

1. `southbrook_estimating` defines the base methods (`_get_cut_constants`, `_compute_panel_dimensions`, `_compute_edge_banding_length`) and the lead-time fields.
2. `southbrook_plm` overrides `_get_cut_constants` to read from active cut spec, and adds the ECO history fields.
3. `product_configurator_mrp` (OCA) adds the `config_ok` flag and the line-level `config_set_id` gating.

The cut constants are read **at call time** via the seam — there's
no startup cache, no module reload required to pick up an ECO. The
ORM cache invalidates the active cut spec when an ECO writes it,
and the next `_get_cut_constants` call sees the new values.

The cutlist generator (lesson 15.7) is the biggest consumer. When
`sb.production.package.generate_from_mo()` runs, it calls
`panel_cut_list(...)` which calls `_compute_panel_dimensions(...)`
which calls `_get_cut_constants()`. So the chain ECO → cut spec
record → BoM math → cutlist lines is one connected pipeline.

Lead-time computes use Odoo's standard `@api.depends` mechanism —
any write to `product.attribute.value.lead_time_extra` invalidates
the dependent BoM computes for variants using that value, on the
next read.

**Phase 1 limitations** (documented in source comments):
- `TOEKICK_H` declared but not consumed (toe-kick is integrated
  into side panels by the cutlist contract — see lesson 15.7).
- `_compute_edge_banding_length` doesn't route through the seam.
- Cut-list lines are computed in-memory, not persisted as
  `mrp.bom.line` rows. The Accucutt bridge (Phase 4) is where
  persistence happens.

## Quiz (5 questions, applied)

**1.** A customer adds a base 1-door cabinet (produce_delay = 14
days) and picks "Maple Box Material" (lead_time_extra = 14). The
order also has a stock 30-day shelving line. What ETA does the
website show?

> ETA is taken as MAX across lines. The cabinet's
> `effective_produce_delay = 14 + 14 = 28`. The shelving line has
> `effective_produce_delay = 30`. Order ETA = 30 days. The
> customer sees the shelving lead time, but the cabinet's 28 days
> is the bottleneck if shelving is from stock.

**2.** A PLM engineer authors a new cut spec with `box_th = 18`
(up from 15.875). They activate it. Walk through what changes
for an MO created tomorrow.

> Tomorrow's MO calls `sb.production.package.generate_from_mo()`,
> which calls `_compute_panel_dimensions()`, which calls
> `_get_cut_constants()`. The PLM override resolves the active
> cut spec, returns `box_th=18`. The cutlist's `side_L`, `top`,
> `bottom`, `shelf` all use 18mm thickness instead of 15.875.
> `inside_width = W − 36` instead of `W − 31.75`. **GOTCHA:**
> `_compute_edge_banding_length` still uses module-level
> `BOX_TH=15.875` — known bug; edge banding will be slightly off
> for this MO. File a ticket.

**3.** Developer asks "why isn't my new attribute's lead-time bump
showing on the BoM?" You check
`product.attribute.value.lead_time_extra` and it's set to 7. The
BoM's `southbrook_lead_time_extra` is still 0.

> The BoM's variant likely doesn't include the new attribute
> value. The compute depends on
> `product_id.product_template_attribute_value_ids.product_attribute_value_id.lead_time_extra`.
> If the variant was created BEFORE the new attribute was added,
> Odoo doesn't retroactively add it. Either configure a new
> variant via the configurator that picks the value, or rebuild
> the variant set.

**4.** Two BoM lines have the same product and config_set_id.
One has `value_ids = [maple_box]`, the other `value_ids =
[white_melamine_box]`. The customer configures a variant with
melamine. Which line fires?

> Only the white-melamine-box line fires. The configurator wizard
> evaluates each line's `config_set_id.value_ids` against the
> variant's attribute values. The maple-box set doesn't match →
> that line is skipped. No Python inflates lines; it's pure
> declarative gating.

**5.** A test asserts toe-kick is NEVER emitted as a separate
cutlist line. Why is this a contract, and how is it enforced in
code?

> Toe-kick is INTEGRATED INTO THE SIDE PANELS by Southbrook's
> shop convention — the bottom of each side panel includes the
> toe-kick height. This is enforced at three layers:
> (a) `_compute_panel_dimensions()` returns no separate toe-kick
> key; (b) `sb.cutlist.generate_lines_from_panel_dict()` has a
> hardcoded `keys_to_emit` tuple that omits 'toe_kick' even if
> someone adds it to the dict; (c) the test
> `test_toe_kick_never_emitted_as_line` asserts the absence. The
> `TOEKICK_H` constant exists so future refactors that want to
> separate toe-kick from side panels have a defined value, but
> no current code path emits it.

---

## What this lesson does NOT cover

- MO-side fields (Kitchen tab, Intelligence tab) → lesson 15.2.
- Workorder-side fields (variance, tool readiness, downtime) → lesson 15.3.
- Workcenter form + alternative chain → lesson 15.5.
- MO Kanban + search filters → lesson 15.6.
- Cutlist + hardware + production package model → lesson 15.7.
- The cut spec authoring workflow (PLM side) → Course 4 lesson 4.2.
- ECO state machine → Course 4 lesson 4.1.
- Operator reading a cut spec → Course 1 lesson 1.7.
- Native Odoo BoM creation → Odoo native training.
