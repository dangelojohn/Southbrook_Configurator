---
course: 1 — Workcenter Operators
chapter: 1.7
title: Reading a Cut Spec from PLM
duration: 25 minutes
audience: CNC, edge banding, and assembly operators who see the cut spec on the floor
prereqs: Lesson 1.1 (workcenter orientation), your role lesson (1.2–1.4)
custom_modules: southbrook_plm, southbrook_mrp_kitchen_workcenters
---

# Reading a Cut Spec from PLM

## Who this lesson is for

You're at SB-CNC-BORE, SB-EDGE, or SB-ASSY and the traveler on your bench
references a **cut spec** — a row in `southbrook.cut.spec` that the
engineer authored and an ECO promoted to live. The cut spec is the
parametric source of truth for every panel dimension, every rabbet, every
reveal in the shop. This lesson is how to read it, what each field means
in your station's vocabulary, and when to escalate back to the engineer
instead of cutting / banding / assembling around a wrong number.

## Where this lives on the site

Sign in at **southbrookcabinetry.space/odoo** with your operator account.

> **Manufacturing → Engineering → Cut Specifications**

The list shows every cut spec, ordered by create date desc. Exactly one row
is in state `active` — that's the spec the BoM math currently reads. Other
rows are `draft` (proposed but not promoted) or `superseded` (formerly
active, retained for audit).

Your traveler references the spec by name (e.g. "NF14 Cut Spec — Rev C").
The spec name and the chatter on its record together tell you which ECO
promoted it and when.

## What your screen shows

Open the active cut spec and you'll see:

- **Name** (`name` on `southbrook.cut.spec`) — human label like "NF14 Cut
  Spec — Rev C." This is what appears on the traveler.
- **State** (`state`) — `draft` / `active` / `superseded`. Only the
  `active` row drives live production. The `_check_single_active`
  constraint enforces exactly one active spec at a time.
- **Provenance note** (`note`) — free text describing where the values
  came from. Reads like "values from workbook revision 8, measured
  2026-05-12 by Peter T." Useful when the numbers feel wrong and you
  need to know whether to escalate.
- **Engineering Change Orders** (`southbrook_eco_ids` — inverse of
  `southbrook.eco.cut_spec_id`) — the ECOs that proposed or activated
  this spec. The smart-button on the form shows the count.

The eight numeric fields (all millimetres) drive every panel-cut
calculation downstream:

- **Box / Carcass Thickness** (`box_th`, default 15.875mm = 5/8" melamine) —
  the carcass material thickness. Sides, top, bottom, fixed shelves
  all this thick. CNC tooling for grooves and rabbets references this.
- **Back-Panel Thickness** (`back_th`, default 6.35mm = 1/4" hardboard) —
  the back panel thickness. The rabbet at the rear edge of the sides
  is depth `rabbet` and width `back_th` so the back drops in flush.
- **Rabbet Depth** (`rabbet`, default 6.35mm) — the routed channel at
  the rear of sides/top/bottom that captures the back panel. CNC
  cuts this; if the value's wrong the back won't seat flush.
- **Door Thickness** (`door_th`, default 18.0mm = 3/4") — slab or
  5-piece door thickness. Drives door-hinge cup depth at SB-DOOR.
- **Door Reveal** (`door_reveal`, default 3.0mm) — the uniform gap on
  all four edges of the door against the cabinet face. Drives door
  panel size relative to opening size; SB-DOOR uses this to set the
  hinge baseline.
- **Shelf Tolerance** (`shelf_tol`, default 1.5mm) — hand-placement
  clearance subtracted from the inside width when computing
  adjustable-shelf dimensions. Also the squareness tolerance
  assembly works to.
- **Shelf Ventilation Gap** (`shelf_vent_gap`, default 12.7mm = 1/2") —
  subtracted from depth at the back so shelves don't trap moisture
  against the back panel.
- **Toe-Kick Height** (`toekick_h`, default 101.6mm = 4") — integrated
  into the side panels for base / sink / tall / vanity cabinets.

## Your daily flow — how to read the spec at each station

**At SB-CNC-BORE / CNC02 (CNC operator):**

- The traveler tells you which cut spec is active and which cabinet
  template the MO is built from. Both are deterministic — the BoM
  math at MO creation read the active spec via the
  `_get_cut_constants()` seam in `southbrook_estimating/models/mrp_bom.py`.
- Confirm the **box_th** value matches the sheet stock loaded on the
  bed. 15.875mm is 5/8" melamine; if the sheet is 18mm and the spec
  says 15.875, the engineer either revised the spec without telling
  the shop, or the wrong sheet is loaded. Don't cut — escalate.
- Confirm the **rabbet** depth matches your loaded bit's depth-of-cut
  setting. The toolpath was generated from the spec; if your bit
  is set to 8mm and the spec says 6.35mm, the back-panel groove
  won't capture properly.
- The **toekick_h** is integrated into the side panels for base
  units. If you see a base cabinet's side panel cut with no toekick
  notch, the spec was changed mid-batch — escalate.

**At SB-EDGE (edge banding operator):**

- The cut spec drives which edges get tape. The panel labels on each
  cart panel (printed at CNC) reference the cabinet model's edge
  pattern. The traveler typically attaches the edge spec sheet as
  a printout.
- The **box_th** value drives the tape height. 15.875mm tape on a
  15.875mm panel; if the engineer revised box_th to 19mm but you're
  still loaded with 15.875mm tape, you'll have a strip of bare
  particleboard at the top.
- Match the panel **count** on the traveler against the cart count.
  Mismatch → escalate (CNC scrapped one or the cart was mis-loaded).

**At SB-ASSY (assembler):**

- The **shelf_tol** value is your squareness tolerance. The diagonal
  measure across the carcass should be within `shelf_tol` mm of
  perfect square; if it's outside, re-square (see lesson 1.4).
- The **rabbet** + **back_th** values define how the back panel
  seats. If the back is loose in the groove, back_th is too thin
  for the spec; if it binds, back_th is too thick. Either is a spec
  mismatch — escalate.
- The **door_reveal** is set by SB-DOOR, not you, but if you're
  rotating through SB-DOOR you'll set the hinge baseline using it.

## Common mistakes + how to recover

**"The cut spec on the traveler says NF14 Rev B but the active spec
in Odoo is NF14 Rev C. Which one do I follow?"**

Follow the active one (Rev C). The traveler was printed when the MO
was created — if the spec was upgraded after MO creation but before
your shift, the printed traveler shows the older revision. Open the
active cut spec in Odoo and check the eight numeric values against
what your work calls for. If anything changed materially (a rabbet
depth shifted from 6.35 to 7mm), the cut-spec form's chatter has the
diff. If you're unsure, escalate before cutting; do not assume the
older traveler is wrong without confirmation.

**"The spec says box_th = 15.875mm but my CNC operator loaded an 18mm
sheet. Who's wrong?"**

Probably the operator (wrong sheet from stock), but it could be the
spec (engineer hasn't propagated a thickness change). Stop and
confirm:
- Open the active spec → read box_th.
- Read the sheet label on the bed.
- If they don't match, do NOT cut. The cabinet panels will be the
  wrong thickness; downstream banding tape, rabbet, and door reveal
  will all be off.
- Escalate to PLM via the *Block* button on the WO — the system
  raises a `cut_spec_audit` recommendation for the engineer.

**"The cut spec hasn't been updated in 6 months but the cabinet
template was updated last week. Why does the math still work?"**

The cabinet template and the cut spec live separately. The template
defines the cabinet's bounding dimensions (W × H × D) and which
panels exist; the cut spec defines the *thicknesses, reveals, and
tolerances* applied to those panels. A template change rarely
needs a spec change — you can introduce a new cabinet shape without
revising material thicknesses. They only co-revise when materials
or joinery technique change shop-wide.

**"I think the active spec is wrong — the rabbet depth is 6.35mm
but every back panel I've banded this week is loose."**

You may be right. Don't fix it yourself. Open the active spec → tap
the smart-button to see the ECOs that bound it — was there a recent
ECO that activated this spec? Talk to the engineer who applied it.
If they agree it's wrong, the path is a new ECO of `target_kind =
'cut_spec'` that proposes a revised spec, the ECO is approved, and
`action_apply` calls `action_activate` on the new spec. The old
spec moves to `superseded` automatically. The chatter on both
records traces the change.

**"I see two specs both showing state `active`."**

You shouldn't — the `_check_single_active` constraint on
`southbrook.cut.spec` enforces exactly one active at a time, and
it's a backstop for manual edits. If you genuinely see two,
something has gone wrong in the database; raise it to the
engineer or IT admin immediately. The cut-math seam returns
`limit=1` so it'll pick one of the two arbitrarily — the wrong
one half the time. This is a P0 data integrity issue.

## What the system is doing behind the scenes

(Optional reading — the database trail.)

The cut spec is the parametric source of truth for the panel
dimensions in every BoM. When an MO is created from an estimating
session, `southbrook_estimating/models/mrp_bom.py`'s
`_get_cut_constants()` seam calls `southbrook.cut.spec._get_active()`,
which returns the single `active` row. The eight constants are then
applied to the cabinet template's W × H × D to produce panel
dimensions, edge counts, rabbet positions, and toolpath references.

When an engineer revises the spec:

1. They create a new `southbrook.cut.spec` row in `draft` state,
   with the proposed values.
2. They raise a `southbrook.eco` of `target_kind = 'cut_spec'`
   pointing at the draft.
3. The ECO goes through its approval stages (covered in Course 4,
   lesson 4.1).
4. On approval, `southbrook.eco.action_apply` calls the new spec's
   `action_activate()` method:
   - The current active spec is found via `_get_active()`.
   - The current active is updated to `state = 'superseded'` and
     its chatter records "Superseded by cut spec <new>."
   - The new spec is updated to `state = 'active'` and its
     chatter records "Activated as the live cut specification."
5. The next MO created after activation uses the new constants.
   In-flight MOs (created before activation) still reference the
   old constants on their existing BoM lines.

This is why an in-flight MO carries the cut spec values it was
born with — the BoM rows are stored, not recomputed. If you need
to re-issue an in-flight MO against a revised spec, the engineer
re-creates the MO; existing work orders are not retroactively
patched.

The chatter on the cut spec is your audit trail. When the manager
asks "when did this rabbet depth change?", the chatter on the now-
`active` spec answers it — including which ECO and which user
applied it.

## Quiz (5 questions, applied)

**1.** The CNC traveler at your station references "NF14 Cut Spec —
Rev C." You open the cut-spec list in Odoo. There's a Rev C in state
`active` and a Rev B in state `superseded`. Both exist, no error.
What does this tell you?

> The spec was upgraded recently — Rev B was the previous active,
> Rev C is the current. Your traveler matches the current state.
> The MO was created after Rev C went active so the BoM lines use
> Rev C's constants. Proceed.

**2.** Your traveler references Rev B but the active spec is Rev C.
You're at SB-EDGE about to band a panel. What do you do?

> Stop. Open both specs and compare the `box_th` and any other
> value that affects your station. If they're identical for your
> fields, you can proceed with the Rev B traveler (the BoM rows
> for this MO were calculated under Rev B and the panels were cut
> to Rev B — banding them under Rev C tape height would be
> incorrect). If they differ at fields you care about, escalate
> via *Block* on the WO and let the engineer decide whether to
> re-issue the MO or accept the in-flight Rev B build.

**3.** You see a row in state `draft` named "NF14 Cut Spec — Rev D"
with `rabbet` set to 8mm (Rev C had 6.35mm). It's not active. Does
it affect your work today?

> No. Only the `active` row drives the BoM math. The draft is a
> proposal — an ECO is probably in review somewhere targeting this
> spec. When the ECO is approved and applied, `action_activate`
> will promote the draft to active and supersede Rev C. Until
> then, ignore it.

**4.** At SB-ASSY, your carcass measures 4mm out of square. The
active cut spec's `shelf_tol` is 1.5mm. Is the carcass acceptable?

> No. The tolerance is 1.5mm, the diagonal is 4mm out — that's
> 2.6× the tolerance. Re-square (loosen and reseat the back panel
> usually fixes it; the rabbet capture is normally what's
> binding). If you can't get it within 1.5mm, the cut spec or the
> panels themselves may be wrong — escalate via *Block* and the
> PLM engineer will audit.

**5.** Your supervisor says "the engineer changed the door reveal
this morning, push it through fast." You check `southbrook.cut.spec`
— the active spec still shows `door_reveal = 3.0mm`, unchanged
since last quarter. Where's the disconnect?

> The engineer's change is probably still in `draft` state, or
> the ECO hasn't been applied yet. Don't act on the supervisor's
> verbal — the active spec is the source of truth. Either find
> the draft spec + the pending ECO and ask why it hasn't been
> applied (maybe it's stuck waiting for approval), or confirm the
> supervisor was wrong about what changed. The chatter on the
> active spec will show no change event if nothing's been applied.

---

## What this lesson does NOT cover

- Native Odoo work-order vocabulary and MRP basics — Odoo's own
  training portal.
- Raising or approving an ECO (engineering-side) — Course 4,
  lesson 4.1.
- Authoring a new cut spec — Course 4, lesson 4.2.
- The BoM math that applies the spec to cabinet templates — Course 5,
  lesson 5.1.
- Your station's daily flow — lessons 1.2–1.5.
- Downtime logging — lesson 1.6.
