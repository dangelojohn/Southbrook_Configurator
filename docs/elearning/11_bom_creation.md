---
course: 11 — Creating a New Product End-to-End
chapter: 11.4
title: Creating the BoM for the New Product
duration: 40 minutes
audience: PLM engineer (with production-planner review) authoring the first `mrp.bom` for a brand-new SKU
prereqs: Lesson 11.3 (cut spec decision made — active spec serves, or new one activated), Lesson 11.2 (`pg.item` in prototype state), Lesson 1.1 (workcenter codes SB-EDGE / SB-CNC-BORE / SB-ASSY / SB-DOOR / SAND / PAINT / CURE / SB-QC / SB-PACK), Lesson 2.3 (bottleneck-aware scheduling — so you understand what your routing choices cost), Lesson 4.2 (cut spec — so you know what `_get_cut_constants` returns)
custom_modules: southbrook_estimating, southbrook_plm, southbrook_mrp_pm, southbrook_kitchen_mrp
---

# Creating the BoM for the New Product

## Who this lesson is for

You're the PLM engineer authoring the `mrp.bom` for a brand-new SKU,
working closely with the production planner who'll review your
routing choices. The BoM you create today is the bridge between the
abstract product (the `pg.item` from lesson 11.2 with its property
values and the active cut spec from lesson 11.3) and the concrete
shop floor (the workcenter codes, the operation cycle times, the
hardware lines).

A bad BoM is a slow shop. A non-existent BoM is a stuck quote — the
configurator (lesson 11.5) and the estimator (lesson 11.6) can't
produce a price without one. This lesson is the practical reality of
authoring the first BoM and getting it past validation.

## Where this lives on the site

> **Manufacturing → Products → Bills of Materials → New**

The BoM model is the standard `mrp.bom`
(`/Users/naadmin/southbrook-v19cr/addons/southbrook_plm/models/mrp_bom.py`
adds PLM tracking; the bulk of the model is Odoo native). You'll
also touch:

> **Sales → Configurable Products → Configurable Templates**

…to confirm the `product.template` you'll attach the BoM to exists.
For a brand-new SKU it usually doesn't yet — you create it now (the
configurator setup in lesson 11.5 builds it out further).

And the routing operations live on the BoM directly via
`operation_ids` (standard `mrp.routing.workcenter`). The Southbrook
seed example is at
`/Users/naadmin/southbrook-v19cr/addons/southbrook_mrp_pm/data/routing_base_1dr.xml`
— **read this file as a template** before authoring your own.

## What your screen shows

The `mrp.bom` form (standard Odoo, with Southbrook extensions
listed in parentheses):

- **Product** (`product_tmpl_id` → `product.template`) — the
  configurable template the BoM produces. For a new SKU you'll
  create the template first (see daily flow step 2).
- **Quantity** (`product_qty`) — almost always `1.0` for a
  cabinet. Cabinets are built one at a time on Southbrook routings.
- **Routing operations** (`operation_ids` → `mrp.routing.workcenter`)
  — the ordered list of work operations, each with a
  `workcenter_id` and a `time_cycle_manual` (minutes per piece).
  This is where most of the lesson's effort goes.
- **Components** (`bom_line_ids` → `mrp.bom.line`) — the raw and
  semi-finished inputs (panel substrate, edge tape, door blank,
  hardware kits). Each line has `product_id`, `product_qty`,
  `product_uom_id`.
- **Southbrook version** (`southbrook_version` Integer, added by
  `southbrook_plm/models/mrp_bom.py`) — bumped by ECO apply
  (`_apply_bom`). Starts at 1 for the new BoM. Lesson 11.8 covers
  the post-release ECO that bumps this when you iterate.
- **ECO history** (`southbrook_eco_ids` / `southbrook_eco_count`
  smart button) — empty on first creation; populates when ECOs
  start modifying this BoM.

## Your daily flow

**1. Pre-flight checklist (3 min):**

- Confirm `PG-ASM-NNNN` is in `prototype` state (lesson 11.2).
- Confirm cut spec status from lesson 11.3 (either "active spec
  serves" or "new active spec applied").
- Have the conception sketch and `spec_draft.md` open.

**2. Create or confirm the `product.template` (5 min):**

- **Sales → Configurable Products → Configurable Templates → New**.
- **Name**: matches the `pg.item.name` from lesson 11.2.
- **Type**: *Storable Product*.
- **Can be sold**, **Can be purchased = No**.
- **Configurable**: tick this on (`config_ok = True` on
  `product.template` — see `product_configurator/models/product.py`
  line 78). Lesson 11.5 fills in the attributes; today you just
  create the shell so the BoM has something to attach to.
- **XML ID**: convention `southbrook.<family>_<descriptor>` (e.g.
  `southbrook.wall_3dr_corner`). This locks the ID per Q8 of the
  estimating brief.
- **Save.** Note the database ID and the XML ID.

**3. Open the routing seed file as a reference (3 min):**

- Open
  `/Users/naadmin/southbrook-v19cr/addons/southbrook_mrp_pm/data/routing_base_1dr.xml`
  in a text editor (or via VCS) — **do not edit it**. This is the
  canonical 8-operation routing for a base 1-door cabinet.
- The seed example shows: `SB-SAW` cut → `SB-EDGE` band →
  `SB-CNC-BORE` drill → `SB-ASSY` assemble → `SB-DOOR` mount →
  `SB-HW` hardware install → `SB-QC` inspect → `SB-PACK` pack.
- Your new BoM probably follows the same 8-step skeleton with
  different `time_cycle_manual` values. Deviations from this
  skeleton (e.g. an extra finish step at `SAND`/`PAINT`/`CURE`,
  or a routing that skips `SB-DOOR` for a doorless cabinet) are
  where the design decisions live.

**4. Create the BoM record (5 min):**

- **Manufacturing → Products → Bills of Materials → New**.
- **Product**: pick the `product.template` you just created.
- **Quantity**: 1.0.
- **BoM Type**: *Manufacture this product* (the default).
- **Save.** `southbrook_version` is now 1, no ECO history yet.

**5. Add the routing operations (15 min):**

For each operation in your planned routing:

- *Operations* tab → *Add a line*.
- **Operation name**: short, station-anchored. *"Saw — panel cut"*,
  *"Edge band — front rail"*, etc.
- **Workcenter** (`workcenter_id`) — pick the right code:
  - Cutting → `SB-SAW`
  - Edge banding → `SB-EDGE`
  - CNC boring (primary) → `SB-CNC-BORE`
  - CNC boring (backup / overflow) → `CNC02`
  - Assembly → `SB-ASSY`
  - Door mounting → `SB-DOOR`
  - Sanding → `SAND`
  - Painting → `PAINT`
  - Curing → `CURE`
  - Hardware install → `SB-HW`
  - Quality → `SB-QC`
  - Packing → `SB-PACK`
- **Cycle time** (`time_cycle_manual`, minutes per piece) — your
  best estimate, validated against the conception sketch. Cabinet
  cycle times typically: SAW 6-12 min, EDGE 8-15 min (bottleneck —
  see lesson 1.2), CNC-BORE 5-10 min, ASSY 15-30 min, DOOR 5-10 min,
  HW 5-10 min, QC 3-5 min, PACK 3-5 min. **You'll refine these
  after the first MO (lesson 11.7); today's numbers are the seed.**
- **Sequence**: the order operations run. SAW first, PACK last.

**6. Add the components (10 min):**

For each material input:

- *Components* tab → *Add a line*.
- **Product** (`product_id`) — the input product (panel substrate,
  edge tape SKU, door blank, hardware kit).
- **Quantity** (`product_qty`) — how many per cabinet. **Do not
  hardcode panel dimensions here** — panel sizes derive from the
  active cut spec via `_get_cut_constants()`; the BoM line is
  the *count* of panels and the *substrate*, not the dimensions.
- **UoM** (`product_uom_id`) — pieces for panels, metres for edge
  tape, units for hardware.

For hardware specifically, the `southbrook_hardware_catalog`
auto-resolver handles per-door/per-shelf/per-cabinet hardware lines
at MO confirm time (lesson 5.3). You add only the **bespoke**
hardware lines that the auto-resolver doesn't cover.

**7. Validate the BoM against the routing seed (3 min):**

- Compare operation count, sequence, and cycle-time order-of-
  magnitude against `routing_base_1dr.xml`. Outliers (e.g. your
  cycle time at `SB-EDGE` is 45 min when the seed says 12) are
  almost always a measurement error or a misunderstanding of the
  cabinet — escalate to the production planner.

**8. The `_get_cut_constants()` seam — what to verify (3 min):**

- The BoM does **not** store panel dimensions. At MO rollup time,
  Odoo calls `mrp.bom._get_cut_constants()`
  (`/Users/naadmin/southbrook-v19cr/addons/southbrook_plm/models/mrp_bom.py:106`)
  which reads the active `southbrook.cut.spec`. The 8 NF14
  constants come back as a dict.
- Confirm: open an MO against your BoM (do not confirm it — keep
  it in draft). Check the cut list preview. The panel dimensions
  should be derived from the constants, not hardcoded. If you see
  hardcoded dimensions, you've mis-authored the BoM — the cabinet
  isn't reading from the cut spec seam and your changes to the cut
  spec won't propagate.

**9. Move `pg.item` state forward (1 min):**

- Back in ProductGraph, open `PG-ASM-NNNN`. *Action → Move to
  Engineering* (`action_to_engineering` on `pg.item`). State
  flips `prototype → engineering`. The audit log fires.
- This signals to lesson 11.5 (configurator setup) that the BoM
  exists and they can hook the configurator attribute mapping to a
  real BoM.

**10. Hand-off to lesson 11.5 (1 min):**

- Slack the configurator admin:
  *"BoM authored for `PG-ASM-NNNN` /
  `southbrook.<xml_id>`; ready for configurator wiring."*

## Common mistakes + how to recover

**"I hardcoded the panel dimensions in the BoM lines."**

The BoM should carry *what* (substrate, count) not *how big* (the
cut spec carries that). If you hardcoded e.g. `Panel 720x580x18mm`
as the product on a BoM line, your cut spec changes will not
propagate to this cabinet — the cabinet will keep cutting 720x580
forever regardless of `box_th` updates. **Recovery**: replace the
hardcoded-dimension product with the generic-substrate product
(*Panel — White Melamine 18mm Stock*), and rely on
`_get_cut_constants()` at MO time to size the cut. Confirm by
opening a fresh MO and checking the cut list reflects the active
spec.

**"My cycle times on `SB-EDGE` are higher than the seed example
suggests. The planner says my schedule's going to be wrong."**

Two real causes: (1) your estimate is genuinely wrong and the new
cabinet is faster than you think — measure on the first MO (lesson
11.7), revise via ECO; (2) the new cabinet is genuinely slower (e.g.
solid-wood edge tape vs melamine, or odd-shaped panels). Talk to the
planner: a slower-than-seed cycle on the bottleneck workcenter (see
lesson 1.2) reduces shop throughput and may justify a different
routing (skip `SB-EDGE` if the cabinet has no banded edges; offload
to alternative workcenter via `alternative_workcenter_ids` —
documented in lesson 2.3).

**"I assigned an operation to a workcenter that doesn't support the
panel material."**

The workcenter has `x_sbk_supported_material_ids`. If you assigned
e.g. solid-wood panels to `SB-EDGE` (which is melamine/MDF/
particleboard only), the MO will block at the operator's station
(lesson 1.2). **Recovery**: change the workcenter on that operation
to one that supports the substrate, or split the operation into a
sub-operation that pre-processes the wood and then bands.

**"I forgot to add the routing operations and saved the BoM as
component-list-only."**

The BoM is technically valid (component-only BoMs are allowed in
Odoo) but the MO won't have work orders — the shop floor sees
nothing to do. **Recovery**: edit the BoM, add the operations,
save. Existing draft MOs will not pick up the new operations; you'll
need to cancel and re-create them.

**"The XML ID I chose collides with an existing template."**

You'll get a constraint error on save. Rename and retry. Note that
the locked XML IDs per Q8 of the estimating brief
(`southbrook.base_1dr`, `southbrook.wall_2dr`, etc.) are *reserved*
— do not poach them. New SKUs need new IDs.

**"I added a hardware line that the auto-resolver already covers
(e.g. soft-close hinges per door)."**

The hardware auto-resolver
(`southbrook.hardware.catalog.resolve(...)` — lesson 5.3) is
idempotent but if you also added the same line manually, the
estimator's quote double-counts the hardware. **Recovery**: remove
the manual line; let the auto-resolver handle per-door / per-shelf
/ per-cabinet hardware. Add only bespoke hardware (one-off vendor
parts the auto-resolver doesn't know about).

## What the system is doing behind the scenes

When you save the BoM:

- A row in `mrp.bom` is created with `product_tmpl_id`,
  `product_qty`, and `southbrook_version = 1`.
- Rows in `mrp.bom.line` are created (one per component).
- Rows in `mrp.routing.workcenter` are created (one per operation)
  with `bom_id` back-reference.
- The `southbrook_plm` extension adds `southbrook_eco_ids`
  (`One2many` inverse `bom_id` on `southbrook.eco`) — empty list.

When an MO confirms against this BoM:

- `mrp.production._action_confirm()` (Odoo native) runs the rollup.
- `mrp.production` creates `mrp.workorder` rows (one per
  operation) and `stock.move` rows (one per component).
- Workcenter capacity is checked against
  `mrp.workcenter.workcenter_load`; the bottleneck flag
  (`x_sbk_is_bottleneck` on `SB-EDGE`) is honoured by the planner
  (lesson 2.3).
- The Southbrook MI engine
  (`southbrook_manufacturing_intelligence`) reads the cycle times
  and produces its first cycle-time-baseline-pending recommendation
  for this BoM (Course 3 lesson 3.1).
- The PLM override of `_get_cut_constants()` returns the active
  cut spec's constants; the FreeCAD bridge (lesson 4.3) renders
  the cabinet using those constants if `freecad_bridge.enabled` is
  true.

When the first ECO modifies this BoM (lesson 11.8):

- `southbrook.eco.action_apply()` dispatches to `_apply_bom()`
  (`/Users/naadmin/southbrook-v19cr/addons/southbrook_plm/models/southbrook_eco.py`).
- `_apply_bom` copies the BoM with `southbrook_version + 1`,
  archives the old one (`active=False`), writes the new one's id
  back to `southbrook.eco.new_bom_id`.
- The bridge addon `southbrook_plm_productgraph` fires
  `_should_trigger_pg_release()`; if true, creates a `pg.release`
  on the linked `pg.ebom` and calls `action_execute_release()` —
  ProductGraph learns about the new BoM revision via the release
  flow (lesson 11.8 walks through this).

## Quiz (5 questions, applied)

**1.** You're authoring the BoM for a new wall cabinet. The cabinet
has 2 doors. The active cut spec says `door_th = 18mm`. Do you
hardcode `18mm` somewhere in the BoM, and if not, what do you do
instead?

> Do not hardcode `18mm`. Add a BoM line for the *door blank
> substrate* product (e.g. *MDF Door Blank 18mm Stock*). The
> dimensions and door reveals come from
> `mrp.bom._get_cut_constants()` at MO rollup time. If `door_th`
> changes in the cut spec, your cabinet automatically uses the new
> thickness on the next MO with no BoM edits.

**2.** You authored the routing as 8 operations: SAW → EDGE → BORE →
ASSY → DOOR → HW → QC → PACK. The cabinet has no door (open
shelving). What do you do with the DOOR operation?

> Remove it. A routing operation that does no work consumes planner
> capacity (the work order shows up at SB-DOOR, the operator
> tries to start it, sees no door to mount, and either skips it
> or wastes 5 minutes confused). Better: shorter routing on the
> BoM. If you want the operation to be conditional ("present only
> when door_count > 0"), file a ticket — Odoo's `mrp.bom`
> doesn't support conditional operations natively in v19; you'd
> need a Southbrook extension.

**3.** Your cycle time on `SB-EDGE` is 25 min for the new cabinet
while the seed example for `base_1dr` is 12 min. The planner is
concerned. What do you do?

> Three options: (a) confirm the estimate by measuring against a
> hand-built prototype if available; (b) split the operation across
> `SB-EDGE` and `SB-DOOR` if some of the banding is door-edge
> banding that DOOR can handle; (c) accept the higher cycle time
> and let the planner re-balance the shop using
> `alternative_workcenter_ids` (lesson 2.3). Do **not** lie about
> the cycle time to look better — the MI engine will detect
> actual >> planned variance after the first MO and flag a
> `slow_workorder` recommendation, and you'll be debugging the
> wrong thing.

**4.** You created the `product.template` with `config_ok = True`
but didn't yet attach any attributes (lesson 11.5 does that). Can
the BoM be authored without attributes?

> Yes. `mrp.bom` doesn't require attributes — it's anchored on the
> template, not on a configured variant. The BoM you author is the
> *base* BoM; once the configurator (lesson 11.5) layers attributes
> on, the configurator's `product_configurator_mrp` integration
> generates variant-specific BoM modifications on the fly. Your job
> today is the substrate-and-routing skeleton.

**5.** You finish the BoM. The planner reviews and says the
operations look fine but you're missing the `SAND` → `PAINT` →
`CURE` block because the new cabinet is finished, not raw. What do
you do?

> Insert three operations between `SB-ASSY` and `SB-DOOR` (because
> finishing happens after assembly but before door mounting):
> `SAND` (10-15 min), `PAINT` (15-25 min), `CURE` (overnight —
> typically modelled as a long cycle time that the planner handles
> with parallel CURE slots, not as a blocking operation). The
> three-station finish flow is documented in lesson 1.5.

---

## What this lesson does NOT cover

- Workcenter codes and what each station does — lesson 1.1, plus
  per-station lessons 1.2 through 1.5.
- The cut spec model and `_get_cut_constants` seam — lesson 4.2
  and lesson 11.3.
- Hardware auto-resolution (per-door / per-shelf / per-cabinet) —
  lesson 5.3.
- Configurator attribute setup on the `product.template` — lesson
  11.5.
- Variant-specific BoM modifications via
  `product_configurator_mrp` — lesson 5.1.
- The MI cycle-time baseline that fires after the first MO —
  Course 3.
- ECO-driven BoM revision (post-release) — lesson 11.8 and
  lesson 4.1.
- FreeCAD render of the new BoM — lesson 4.3.
