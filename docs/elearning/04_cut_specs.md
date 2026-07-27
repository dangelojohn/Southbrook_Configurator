---
course: 4 — PLM + Design
chapter: 4.2
title: Authoring a Cut Spec Sheet — What Fields Drive the Operator's Job
duration: 30 minutes
audience: ECO Engineer authoring a parametric cut specification for the cabinet panel-cut math
prereqs: Lesson 4.1 (ECOs), basic understanding that every cabinet's panel dimensions derive from a small set of geometric constants
custom_modules: southbrook_plm, southbrook_estimating
---

# Authoring a Cut Spec Sheet — What Fields Drive the Operator's Job

## Who this lesson is for

You're the engineer who owns the NF14 cut constants — the panel
thicknesses, the reveal, the rabbet depth, the toe-kick height — and
you have to revise one of them without breaking the cabinets already
in production. A cut spec record isn't a per-cabinet drawing; it's
a single set of geometric constants that *every* template BoM reads
through the `_get_cut_constants()` seam. Get one number wrong here
and every base cabinet in the shop cuts wrong tomorrow. This lesson
is the practical reality of authoring one and the gotchas you'll hit.

## Where this lives on the site

> **Southbrook PLM → Cut Specifications**

You'll see one record marked **Active** (green decoration), zero or
more **Draft** records, and zero or more **Superseded** records
(muted decoration). The active spec is the one the cut math is
currently using; drafts are candidates waiting for an ECO to
activate them; supersededs are the audit trail.

ECOs that reference any cut spec live in the standard ECO list at
**Southbrook PLM → Change Orders**, but a small flag-icon smart
button on each cut spec's form (visible when `southbrook_eco_count
> 0`) takes you directly to the ECOs that have proposed or activated
this spec.

## What your screen shows

The form on `southbrook.cut.spec` has four field groups, all in
millimetres:

- **Name** (`name`) — free text. Convention: cite the workbook
  revision that produced these values, e.g. *2026 Workbook Rev B*.
- **State** (`state`) — `draft` / `active` / `superseded`. Statusbar
  widget at the top. **You never write this field directly.** The
  Activate button (which only an Approver sees, and only when not
  already active) flips draft → active and supersedes the previous
  active. ECO Apply on a Cut-Geometry Revision does the same thing
  via the `action_activate` handler.

**Carcass group:**

- **Box / Carcass Thickness** (`box_th`, default 15.875) — carcass
  material thickness in millimetres. 5/8" melamine is the
  Signature-Series standard. Drives the inside-width and
  inside-depth subtractions on every panel.
- **Back-Panel Thickness** (`back_th`, default 6.35) — 1/4"
  hardboard. Read by the rabbet computation.
- **Rabbet Depth** (`rabbet`, default 6.35) — the back-panel capture
  groove routed into the sides, top, and bottom. By convention
  matches `back_th`; if you change `back_th` you almost always
  change `rabbet` to match.

**Door group:**

- **Door Thickness** (`door_th`, default 18.0) — 3/4" slab or
  five-piece. Used by the door-cut math and by hinge selection
  rules downstream.
- **Door Reveal** (`door_reveal`, default 3.0) — uniform gap on all
  four door edges. Drives every door's outside-dimension subtraction
  off the cabinet opening. The single highest-leverage value in the
  spec — bumping reveal by 1 mm changes every door on every cabinet
  in the shop.

**Shelf group:**

- **Shelf Tolerance** (`shelf_tol`, default 1.5) — hand-placement
  clearance subtracted from inside width. Bigger value = looser
  shelf, more rattle; smaller value = tighter, harder to place.
- **Shelf Ventilation Gap** (`shelf_vent_gap`, default 12.7) — 1/2"
  subtracted from shelf depth at the back so air circulates around
  contents. Distinct from `back_th` — even with a 6 mm back, you
  still want a 12.7 mm vent gap.

**Toe-Kick group:**

- **Toe-Kick Height** (`toekick_h`, default 101.6) — 4" standard,
  integrated into the side panels for base/sink/tall/vanity
  cabinets. Driven by ergonomics, not material — almost never
  changes.

**Provenance:**

- **Note** (`note`, Text) — where these values came from. The seed
  spec note reads "*NF14 reminder: the seed spec values are
  ASSUMED until the canonical #8 workbook lands.*" If you author
  a new spec, cite the workbook revision, the measurement event,
  and the person who took the measurement. Auditors read this.

**Smart button:**

- **ECOs** — count of `southbrook.eco` records referencing this
  spec via `cut_spec_id`. Click-through opens the ECO list
  filtered to this spec with `default_cut_spec_id` and
  `default_eco_type_id` pre-set, so creating a new ECO from this
  view is one click.

## How a cut spec ties to a BoM line, an MO, and the operator's screen

The cut spec doesn't live on the BoM directly. Instead:

1. **At BoM compute time**, `mrp.bom._get_cut_constants()` reads
   the active spec via
   `self.env["southbrook.cut.spec"].sudo()._get_active()` and
   returns its `constants_dict()` — a mapping like
   `{"box_th": 15.875, "back_th": 6.35, …}`. The estimating
   module's panel-cut formulas consume this dict. When no spec is
   active (fresh install, or all superseded), the seam falls back
   to the module-level Python defaults via `super()`.

2. **At sale-order confirm time**, the line captures a snapshot:
   `sale.order.line.southbrook_cut_spec_version_id` (m2o to
   `southbrook.cut.spec`) and `southbrook_bom_version` (Integer)
   are written by `_capture_southbrook_version_snapshots`, called
   from `sale.order.action_confirm`. The snapshot is the
   point-in-time the manufacturing chain reads — an ECO that
   activates a new spec mid-day does **not** retroactively change
   the panel cuts of orders confirmed before it. Two different
   MOs confirmed before and after the same Apply can legitimately
   use two different cut specs.

3. **At MO release**, the work order's cut list — what lands on
   the CNC operator's screen as the panel-dimension labels — is
   derived from the line's BoM × line's cut-spec snapshot. The
   operator never sees the spec name; they see *outputs* (panel
   width 596.25 mm, depth 555.5 mm, rabbet 6.35 mm). The
   planner reading the MO sees the spec snapshot in a backend
   view so they know which constants the cut was computed
   against.

4. **The edge banding operator** doesn't read the cut spec at
   all — they read the panel ID and the edge-tape side spec
   off the cut-spec label printed at CNC (lesson 1.7). Two
   panels from two different cut specs on the same shift are
   indistinguishable at the bander; the difference is in the
   sub-millimetre dimensions, which the bander pulls from the
   panel itself, not from a spec record.

5. **The assembler** reads the same cut-spec label for the
   reveal — they need to know what gap to expect between the
   door and the cabinet face so they can spot a hinge-shim
   issue before the cabinet ships. The reveal value visible on
   the assembler's shop drawing IS `door_reveal` from the spec
   active at the time the MO was confirmed.

## Your daily flow

**1. Why you're authoring a new cut spec.**

A cut spec revision is the single highest-leverage change in the
entire PLM workflow. You author a new spec when:

- The material vendor substitutes 5/8" (15.875 mm) melamine with
  18 mm and you have to ship the change to production tomorrow.
- A QA review of returns finds that 3 mm door reveal is showing
  too much shadow line and customer service wants 2 mm.
- An ergonomics review for a senior-living account requires a
  taller toe-kick.
- A workbook revision (Peter Tuschak signs off on a new spec
  table) lands and the seeded "assumed" defaults need to be
  replaced with measured values.

You DO NOT author a new cut spec when:

- Only one cabinet template needs a different panel thickness —
  that's a BoM-kind ECO on that one template's BoM.
- A construction rule changes (e.g. Contractor series no longer
  offers maple boxes) — that's a Construction-Rule ECO on the
  config_rules.xml file.
- A vendor cut sheet changed but the geometry didn't — that's an
  Engineering Document ECO with the new PDF attached.

**2. Authoring the draft.**

- From **Cut Specifications**, click **New**.
- The form opens with all eight constants pre-filled from the
  hard-coded defaults (NOT from the currently-active spec —
  the form's `default` annotations come from the field
  definitions). **This is the most common pitfall.** If you
  only meant to change `door_reveal`, you need to copy across
  the other seven values from the active spec by hand before
  saving, otherwise you'll silently revert any of them that
  the active spec had bumped away from the seed defaults.
- Set the **Name** to cite the workbook revision and the date —
  "Workbook Rev C — 2026-07-15" beats "new spec."
- Fill the **Note** field with provenance: which workbook, who
  signed off, what changed from the prior spec, and why.
- Save. The state is **Draft**.

**3. Wiring the draft to an ECO.**

- Go to **Southbrook PLM → Change Orders**, click **New**.
- Type: **Cut-Geometry Revision** (this is the
  `target_kind=cut_spec` ECO type).
- Target tab: pick your draft cut spec in `cut_spec_id`.
- Title and Description: cite the specific constants that
  changed AND the prior values. "Bump door_reveal 3.0 → 2.0 mm
  per Workbook Rev C; all other constants unchanged." A
  diff-style description is what an auditor wants.
- Advance Draft → Under Review → Approved → Apply. (See
  lesson 4.1 for the gate semantics.)
- Apply runs the `_apply_cut_spec` handler, which calls
  `action_activate()` on your draft. The draft flips to
  `state=active`; the previously-active spec flips to
  `state=superseded`. The chatter on both records captures the
  swap. The active-spec invariant
  (`_check_single_active`: at most one record with
  `state=active`) holds.

**4. Validating the activation took effect.**

- Refresh **Cut Specifications**. Your draft now shows green
  (Active). The previous active shows muted (Superseded).
- Open any cabinet template's mrp.bom form and compute a
  panel — the dimensions should reflect the new constants.
  (In practice you'll do this via the estimating addon's
  preview tab, not by hand-calling `_get_cut_constants`.)
- Find a sale order that was confirmed before today and look
  at its order lines: the `southbrook_cut_spec_version_id`
  snapshot still points at the *old* spec. This is correct.
  The change ONLY affects orders confirmed from this point
  forward.

## Common mistakes + how to recover

**"I created a new cut spec to change the door reveal, but when
the ECO applied, the shop's panel cuts went weird — three other
constants also moved back to their original defaults."**

You authored your draft starting from the default values
(15.875, 6.35, 6.35, 18.0, 3.0, 1.5, 12.7, 101.6) instead of
copying the currently-active spec's values forward. The active
spec had bumped `box_th` to 18.0 (for the new material vendor)
and `door_th` to 19.0 (for a heavier door style), but your
draft kept them at 15.875 and 18.0. When the ECO activated, the
shop floor started cutting with the seed defaults plus your
new reveal. Recovery: author a NEW draft cut spec that copies
the *previous* active spec's values forward AND keeps your
intended reveal change. Raise a new Cut-Geometry Revision ECO,
title it explicitly as a corrective ("Correct yesterday's
reveal-only revision to preserve box_th and door_th from
Workbook Rev B"), and apply. The chatter trail will read clean.

**"I tried to activate a draft cut spec directly from the form
button, and it worked — no ECO needed."**

The Activate button is gated to the PLM Approver group and IS
the same code path the ECO apply handler uses; it works because
the activation is technically just a record-write. **But** the
ECO trail is how an auditor traces *why* the spec changed. If
you activate without raising an ECO, the cut-spec record's
chatter will show "Activated as the live cut specification" but
nothing about the workbook revision, the approval, the
rationale. The convention is: always go through an ECO. The
direct-activate button exists as an admin escape hatch, not a
daily-flow tool. Set yourself a personal rule: only click it
if you're recovering from a corrupted ECO and a comment block
explains why.

**"My tolerance bands are tight — I set shelf_tol to 0.5 mm and
now every shelf is binding in the cabinet."**

Shelf tolerance is *hand-placement clearance*, not the
shelf-pin precision. 0.5 mm is below the dimensional accuracy
of the CNC's panel-saw kerf, never mind the carpenter's hand.
The seed default of 1.5 mm exists because below it, even a
perfectly-cut shelf binds against unavoidable carcass
variation. Recovery: raise a new Cut-Geometry Revision ECO,
bump `shelf_tol` back to at least 1.5 mm. The over-tight
shelves in production are a one-shift issue — sand them down
by 1 mm at the assembly station. Document the recovery in
the new ECO's description as a lesson.

**"I forgot to write the edge-tape side spec on the cut spec
record."**

The cut spec doesn't carry edge-tape side spec at all — that's
a per-cabinet, per-panel concern that lives on the BoM
(`mrp.bom.line` rows for each panel carry the edge-tape attribute
sub-records). The cut spec carries only the eight geometric
constants. If you find yourself looking for a side-spec field
on `southbrook.cut.spec`, you've reached for the wrong tool;
the right tool is a BoM-kind ECO on the specific cabinet
template.

**"I bumped `door_reveal` from 3.0 to 2.0 and the configurator's
3D preview still shows a 3 mm gap on existing quotes."**

Existing quotes — sale orders in draft state — read the cut
spec at render time, so they SHOULD reflect the new value.
Refresh the browser; if it's still wrong, the assets bundle
may be cached. For sale orders already CONFIRMED, the snapshot
(`southbrook_cut_spec_version_id`) pins them to the OLD spec,
which is correct behaviour — those orders are in production,
their panels are mid-cut, you don't want the rendered preview
to drift from the actual material on the floor.

## What the system is doing behind the scenes

The cut spec is a versioned record store; the cut math is a
seam (`mrp.bom._get_cut_constants()`) that the PLM module
overrides to read the live spec. The override falls back to
`super()` (the code defaults defined in
`southbrook_estimating/models/mrp_bom.py` as module constants)
when no spec is active, so installing the PLM module on a
fresh install never silently changes cut output until the
first spec is activated.

`action_activate` is the single state-mutation entry point.
It checks if `self` is already active (no-op), finds the prior
active via `_get_active()`, supersedes it with a chatter post
on both records, and writes `state=active` on `self`. The
"exactly one active" invariant is enforced by the
`@api.constrains("state")` constraint
`_check_single_active`, which queries
`search_count([("state", "=", "active")])` after every write
and raises ValidationError if it exceeds 1. (Implemented as
a Python constraint rather than a PostgreSQL partial-unique
index because the latter needs the `btree_gist` extension,
which isn't part of the standard PG image we ship.)

The cut-spec snapshot pattern on `sale.order.line` is the
load-bearing piece of the manufacturing immune system: a
line's
`_capture_southbrook_version_snapshots` runs at
`action_confirm`, writes the active spec's `id` to
`southbrook_cut_spec_version_id`, and the snapshot is
*idempotent* — re-confirming a line (which Odoo guards
against anyway) preserves the existing snapshot. Manufacturing
reads from the snapshot, never from the currently-active
spec, so mid-day ECO applies are safe.

The seam read is wrapped in `sudo()` because portal users
(customers fetching their order payload via
`/southbrook/api/order/<id>`) need the panel dimensions
computed, but `ir.model.access.csv` restricts cut-spec read
to the PLM User group. The portal user never sees the spec
record directly — only the derived panel dimensions — so the
sudo is safe.

## Quiz (5 questions, applied)

**1.** You raise a Cut-Geometry Revision ECO that bumps
`door_reveal` from 3.0 mm to 2.5 mm. You hit Apply at 11:00.
A sale order was confirmed at 09:00 this morning; a different
sale order is confirmed at 13:00. Which cut spec do their
respective MOs cut against?

> The 09:00 order's lines captured the OLD cut spec (door
> reveal 3.0 mm) as their `southbrook_cut_spec_version_id`
> snapshot at confirm time. Its MOs read from the snapshot,
> not the live spec, and cut with reveal 3.0 mm — by design.
> The 13:00 order's lines were confirmed after the activate
> at 11:00, so their snapshot points at the NEW spec; their
> MOs cut with reveal 2.5 mm. This is the whole point of the
> snapshot pattern: two days of orders on two different specs
> live side-by-side in the shop without interfering.

**2.** A vendor swap means melamine carcass material is now
18 mm instead of 15.875 mm. You author a draft cut spec
called "Vendor Swap — 18 mm Melamine," fill in only
`box_th = 18.0`, save, and raise an ECO. What goes wrong on
Apply, and what's the fix?

> Your draft set `box_th = 18.0` but inherited the seed
> defaults for everything else: `back_th=6.35`, `rabbet=6.35`,
> `door_th=18.0`, `door_reveal=3.0`, `shelf_tol=1.5`,
> `shelf_vent_gap=12.7`, `toekick_h=101.6`. If the
> currently-active spec had bumped *any* of those (say
> `door_th=19.0` for a heavier door style), Apply will
> activate your draft and lose that bump — every cabinet's
> door cut goes back to 18 mm. Fix: open the currently-active
> spec, screenshot every value, edit your draft to copy them
> forward except `box_th`, save, and re-apply (or raise a
> follow-up ECO that restores the lost values). The cut spec
> is not a delta — it's a complete record. Always copy
> forward.

**3.** Your operator escalates: "the shelves on yesterday's
base cabinets are too loose, they rattle when you close the
door." You check the active cut spec — `shelf_tol` is 3.0
mm. What's the right corrective ECO, and what risks are you
weighing?

> Raise a Cut-Geometry Revision ECO that drops `shelf_tol`
> from 3.0 mm to the historical 1.5 mm default (the value
> the seam used before any spec activation). Copy the other
> seven constants forward unchanged. The risk of going below
> 1.5 mm: shelves may bind against carcass variation, which
> at the panel-saw kerf precision is a coin-flip. Don't go
> below 1.5 mm without a measurement event that demonstrates
> the saw is holding tighter than that. The yesterday-shipped
> cabinets that already left at 3.0 mm are a customer-service
> issue, not a cut-spec issue — those carcasses are in homes,
> and the spec snapshot on their MOs correctly records the
> 3.0 mm decision.

**4.** A junior designer hit the **Activate** button on a
draft cut spec without raising an ECO. The new spec is live;
the previous one is superseded; the audit trail shows
"Activated as the live cut specification." Should you
roll it back? Walk through the steps if so.

> The activation itself was a legitimate state move — the
> Approver group is what gates the button, and they had it.
> The problem is the missing ECO trail: an auditor reading
> the cut-spec chatter has no "why" — no workbook revision
> cited, no approval rationale. Don't roll back the values
> if they're correct; instead, raise a *retroactive*
> Cut-Geometry Revision ECO pointing at the now-active
> spec, with a description like "Audit-completion ECO for
> manual activation of <spec name> by <designer> at
> <timestamp>; rationale: <workbook cite>." Apply it. The
> handler is a no-op on an already-active spec (the
> `if self.state == "active": return True` early-return),
> so nothing changes geometrically — but the audit chatter
> now references the ECO, closing the loop. Counsel the
> junior to go through ECO next time.

**5.** You're explaining to a new edge-banding operator
why the panels they're banding today look identical to
yesterday's but the planner says "different cut spec." What
do you say?

> The panel they're physically handling has its dimensions
> printed on the cut-spec label at CNC — those dimensions
> ARE the difference. Yesterday's spec might have had
> `back_th=6.35`; today's might have `back_th=9.0`. The
> visible panel looks the same because it's the SIDE panel,
> not the back, and side dimensions are dominated by box
> thickness and reveal — both unchanged. The edge tape and
> the banding routine are identical; the operator's job
> doesn't change. The reason the planner cares is that the
> sub-millimetre door reveal change shifts how the assembler
> sees the door-to-cabinet gap, and the assembler will flag
> a defect if it doesn't match the day's spec.

---

## What this lesson does NOT cover

- Raising the ECO that activates a cut spec — lesson 4.1.
- The FreeCAD render artifacts that update after a spec
  change — lesson 4.3.
- Per-panel edge-tape side spec — that's on the BoM line,
  not the cut spec; see Course 1 (CNC + edge banding).
- How the edge banding operator reads a cut-spec *label*
  on a physical panel — lesson 1.7.
- Native Odoo `mrp.bom` mechanics — Odoo's own training.
