---
course: 11 — Creating a New Product End-to-End
chapter: 11.3
title: Authoring the Cut Spec for the New Product
duration: 35 minutes
audience: PLM engineer authoring or revising the geometric constants that drive the new product's panel-cut math
prereqs: Lesson 11.2 (the `pg.item` exists and is in `prototype` state), Lesson 4.2 (cut spec authoring fundamentals), Lesson 4.1 (ECOs — required because activation happens via ECO apply, not the form), Lesson 1.7 (how operators read a cut spec)
custom_modules: southbrook_plm, southbrook_estimating, southbrook_plm_productgraph
---

# Authoring the Cut Spec for the New Product

## Who this lesson is for

You're the PLM engineer who owns the geometric constants — the panel
thickness, the rabbet depth, the door reveal, the toe-kick height —
that every cabinet template's BoM reads through the
`_get_cut_constants()` seam. Yesterday lesson 11.2 created
`PG-ASM-NNNN`. Today you decide whether the new product needs a *new
cut spec* (almost never — only if the constants genuinely change) or
whether the existing active cut spec serves (almost always — same
constants, new BoM expression of them).

This lesson is **workflow-specific**: it does not re-cover the cut
spec model in detail (that's lesson 4.2). It covers the *decision*
("new spec? same spec?") and the *activation path* in the context of
introducing a brand-new product.

The honest reality: 9 times out of 10, your answer is *"same active
cut spec serves; no new spec needed; proceed to lesson 11.4."* This
lesson teaches you to recognise the 1 in 10 where a new spec **is**
required, and how to land it without breaking the cabinets already in
production.

## Where this lives on the site

Cut spec lives in the main Southbrook Odoo database (not in
ProductGraph). Sign in at
**southbrookcabinetry.space/odoo** with your PLM-Approver account
(`group_southbrook_plm_approver`), then:

> **Southbrook PLM → Cut Specifications**

You'll see exactly **one** record marked **Active** (green
decoration), some number of **Draft** records, and an archive of
**Superseded** records. The single-active invariant is enforced by
`_check_single_active`
(`/Users/naadmin/southbrook-v19cr/addons/southbrook_plm/models/southbrook_cut_spec.py`,
line 124) and is the whole reason this lesson is delicate.

ECOs that propose or activate cut specs live at:

> **Southbrook PLM → Change Orders**

…filtered by `target_kind = cut_spec`.

## What your screen shows

The `southbrook.cut.spec` form (lesson 4.2 covers every field; this
section recaps what matters for the new-product workflow):

- **Name** (`name`) — convention: cite the source of these
  constants. *"2026 Workbook Rev B"*. **Not** the product name. Cut
  specs are global, not per-product.
- **State** (`state` — Selection `draft` / `active` / `superseded`)
  — statusbar widget. **You never write this field directly.** The
  `_check_single_active` constraint enforces one active at a time.
- **The 8 NF14 constants**, all `Float`, all millimetres:
  - `box_th` — box panel thickness
  - `back_th` — back panel thickness
  - `rabbet` — rabbet depth at back
  - `door_th` — door thickness
  - `door_reveal` — gap around door edge
  - `shelf_tol` — shelf clearance tolerance
  - `shelf_vent_gap` — vent gap at top of shelf
  - `toekick_h` — toe-kick height
- **ECO smart button** (`southbrook_eco_ids`, count
  `southbrook_eco_count`) — every ECO that has proposed or activated
  this spec.

The form also surfaces a button **Activate** (visible only to
PLM-Approvers, only when state is `draft`). Clicking it calls
`action_activate()` (line 177) which: looks up the current active
via `_get_active()`, writes `state='superseded'` on it, posts
chatter, then writes `state='active'` on self. **But you almost
never click this button directly.** The activation should be the
side effect of an ECO `_apply_cut_spec`, not a manual flip. See
*Common mistakes* below.

## Your daily flow

**1. Read the property values from lesson 11.2 (5 min):**

- Open `PG-ASM-NNNN` in ProductGraph. Open revision A. Read every
  `pg.property.value`.
- Question: do any of the property values **disagree** with the
  current active cut spec's 8 NF14 constants? Specifically:
  - Box panel thickness — does the new product use a thicker box
    (e.g. solid-wood vs melamine 18mm)?
  - Door thickness — does the new product use a thicker door
    (e.g. 22mm shaker vs 18mm slab)?
  - Door reveal — does the new product have a tighter or looser
    reveal than the shop standard?
- If every property value is consistent with the current active
  spec, **stop here and skip to lesson 11.4**. The active spec
  serves; you don't need to author a new one. **This is the
  expected outcome.**

**2. If a constant genuinely differs, decide the path (10 min):**

There are three real paths and one tempting wrong path:

- **(a) Update the global spec.** If the new product's value is the
  *new shop standard* (e.g. the shop is switching from 18mm to
  19mm box stock industry-wide), a new global active spec is
  correct — every cabinet now uses the new value.
- **(b) Per-product override in the BoM.** If the new product is
  the **only** cabinet using the differing constant (e.g. a
  one-family thick-door SKU), the right fix is **not** a new cut
  spec — it's the per-product BoM in lesson 11.4 carrying the
  override directly on its operation parameters or hardware lines.
  Cut spec is global; per-product variation lives in the BoM.
- **(c) Add a new attribute value.** If the differing constant is
  really a *choice* the customer makes (e.g. door thickness
  selectable), the right fix is a new attribute value in the
  configurator (lesson 11.5), with the BoM math reading the choice.
  Not a cut spec change.
- **(WRONG path) Author a new cut spec to "cover" this product's
  case.** Cut specs are **not** scoped — there is only ever one
  active. Authoring a new spec to handle this product breaks
  every other cabinet in production because every other cabinet's
  BoM now reads the new constants too.

If you've decided on (a) — a new global spec — proceed. Otherwise
escalate to lesson 11.4 (path b) or lesson 11.5 (path c).

**3. Draft the new cut spec (10 min):**

- **Southbrook PLM → Cut Specifications → New**.
- **Name**: cite the source. *"2026 Workbook Rev C — 19mm box
  stock"*.
- Fill **all 8 constants** with the new values. Even constants that
  didn't change must be present — copying the active spec's other
  seven and updating only the one that changed is correct (lesson
  4.2 covers the *copy from active* gotcha).
- **State** stays `draft`. **Do not** click Activate. We're going
  to activate it via an ECO, not by hand.
- **Save.** The draft is now visible in the list view under
  *Draft*.

**4. Raise the ECO (5 min):**

- **Southbrook PLM → Change Orders → New**.
- **eco_type_id** → pick an ECO type with **target_kind = cut_spec**
  (`southbrook.eco.eco_type` — typed in `southbrook_eco_type.py`).
- **title**: *"Activate cut spec for `PG-ASM-NNNN` — 19mm box
  stock"*.
- **description** (Html): include a short rationale citing the
  ProductGraph item, the property value that drives the constant
  change, and the affected cabinets (almost always *"all cabinets
  in production"* — cut spec is global, this is the point).
- **cut_spec_id** → pick the draft you just authored.
- **document_ids** → attach the source workbook revision PDF and
  the conception folder's `spec_draft.md`.
- **Save.** State is `open`.

**5. Walk the ECO through approval (varies; minutes to days):**

- The ECO follows the configured stage Kanban
  (`southbrook.eco.stage`). For cut-spec ECOs the typical flow is:
  *Draft → Review → Approved*.
- The Review stage requires an approver outside your team to sign
  off — cut spec changes affect every cabinet, so a second pair of
  eyes is non-negotiable.
- When the Approver clicks *Apply*, `action_apply()` dispatches to
  `_apply_cut_spec()` which calls
  `cut_spec_id.action_activate()` — the activation happens **as a
  side effect of the ECO apply**, not by you clicking the form
  button. This is why we drafted the spec without activating it.

**6. Verify the activation (2 min):**

- Reload **Southbrook PLM → Cut Specifications**. The previous
  active is now superseded; your draft is now active.
- Open an MO that's mid-flight (any one — pick something benign).
  The MO's BoM now reads your new constants. **No data migration
  was needed** because the constants are read at BoM-rollup time,
  not stored on the BoM.

**7. Hand-off to lesson 11.4 (1 min):**

- Slack the BoM author (often the same person but often not):
  *"Cut spec active; ready for BoM authoring on `PG-ASM-NNNN`."*

## Common mistakes + how to recover

**"I clicked the Activate button on the form directly and it worked.
Why is that bad?"**

It worked *mechanically* — `action_activate()` is callable from the
form. But you bypassed the audit trail: no `southbrook.eco` row, no
ECO history smart button on the new active spec, no approver
sign-off recorded, no chatter explaining why the constants changed.
Two months from now when the shop floor's cycle times degrade and
the production manager asks *"what changed?"*, the answer
"someone clicked Activate" is unacceptable. **Recovery**: open the
new active spec. Raise the ECO retroactively (target_kind=cut_spec,
cut_spec_id=this active record), describe what should have happened,
walk it through the stages, and apply it. The activation is a
no-op (already active) but the audit trail catches up. Then write
yourself a sticky note.

**"I authored a draft spec with one constant changed, activated it,
and now every base cabinet's cycle time exploded."**

This is path (a) gone wrong: the constant you changed was
appropriate for the new product but wrong for every existing
cabinet. **Recovery**: immediately raise an ECO to re-activate the
previous (now superseded) spec. The superseded record is still in
the table; the ECO `_apply_cut_spec` flow re-activates it cleanly.
Then go back to step 2 of the daily flow and reconsider whether you
actually needed path (b) or (c).

**"I want to author a 'product-scoped' cut spec just for the new
product so I don't affect the others."**

You cannot. The model has no scoping field; the
`_check_single_active` constraint is global; the
`_get_cut_constants` seam reads `_get_active()` which returns the
single active record. If the new product genuinely needs different
constants, the design path is (b) — per-product override in the BoM
— or (c) — attribute choice. *Filing a ticket* to add cut spec
scoping is fine ("add `product_tmpl_id` to `southbrook.cut.spec`
for per-product variants"), but that's a future feature; today you
take path (b) or (c).

**"The ECO approval is held up and I need to ship the new product."**

The new product cannot ship until the cut spec it depends on is
active. If you're blocked on approval, two real options: (1)
escalate the ECO approval — the approver is the bottleneck, not the
spec; (2) reconsider whether path (a) was right. Often the
re-think reveals the constant change wasn't really needed, the
product can ship on the existing spec, and you cancel the draft.

**"I forgot to attach the workbook PDF as `document_ids` on the
ECO."**

Edit the ECO, attach it, save. The ECO carries the audit trail of
the constants change; without the source workbook attachment,
six months from now when an auditor asks *"where did 19mm come
from?"* the answer is *"trust me"*. Always attach the source.

## What the system is doing behind the scenes

When you click **Apply** on the ECO:

- `southbrook.eco.action_apply()` runs
  (`/Users/naadmin/southbrook-v19cr/addons/southbrook_plm/models/southbrook_eco.py`).
- It dispatches on `target_kind` — for `cut_spec` it calls
  `_apply_cut_spec()`.
- `_apply_cut_spec()` calls `self.cut_spec_id.action_activate()`.
- `action_activate()` (in `southbrook_cut_spec.py` line 177):
  - Calls `_get_active()` to find the current active record.
  - Writes `state='superseded'` on the previous active. Posts a
    chatter message: *"Superseded by ECO `<name>`"*.
  - Writes `state='active'` on `self`. Posts a chatter message:
    *"Activated by ECO `<name>`"*.
- The `_check_single_active` constraint runs as part of this write
  and verifies that, after the write, exactly one record has
  `state='active'`. (Two would raise `ValidationError`; zero is
  allowed transiently inside the same database transaction.)
- The ECO's own state advances to `applied`, `applied_date` set to
  `fields.Datetime.now()`, and an audit chatter row is written.

When any cabinet's MO confirms after this point and the BoM rollup
runs:

- `mrp.bom._get_cut_constants()` is the seam
  (`/Users/naadmin/southbrook-v19cr/addons/southbrook_estimating/models/mrp_bom.py:73`
  is the base; the PLM override is at
  `/Users/naadmin/southbrook-v19cr/addons/southbrook_plm/models/mrp_bom.py:106`).
- The PLM override calls
  `self.env['southbrook.cut.spec'].sudo()._get_active()`. `sudo()`
  is required so portal users hitting `/southbrook/api/order/<id>`
  don't `AccessError` (cut specs are not portal-accessible).
- If found, returns `spec.constants_dict()` (the 8 NF14 constants).
- If not found (no active spec — only possible during a brief
  transition window or in a broken environment), returns
  `super()` — the hard-coded estimating defaults.

The ProductGraph bridge (`southbrook_plm_productgraph`) does **not
fire on cut spec activation** in v1 — the bridge fires only when
ECO `target_kind` is `bom` (creates a `pg.release`). Cut spec
activation is intentionally not propagated to ProductGraph, because
cut spec is a shop-floor constant, not a per-part attribute. If
your new product's cut constants needed to land as ProductGraph
property values, they did — back in lesson 11.2.

## Quiz (5 questions, applied)

**1.** You're authoring a new wall cabinet SKU. The property values
in revision A say *box thickness 18mm, door thickness 18mm, reveal
3mm* — exactly the same as the active cut spec. Do you author a new
spec?

> No. The active spec serves. Skip to lesson 11.4 (BoM creation).
> Authoring a "no-op" cut spec would burn a record, require an ECO,
> and add noise to the supersession chain for no benefit.

**2.** The new product is a thick-door luxury SKU with `door_th =
22mm` while the active spec is `door_th = 18mm`. Every other
cabinet stays at 18mm. Which path do you take?

> Path (b) — per-product override in the BoM. The BoM's
> operation parameters or door-cut math carries the 22mm
> dimension directly. Cut spec stays at 18mm because every other
> cabinet still uses 18mm. **Do not** activate a new global
> 22mm cut spec — you'd break every other cabinet.

**3.** You drafted a new cut spec, raised the ECO, the approver
clicked Apply, and the spec is now active. You then notice the
`shelf_vent_gap` value you entered is wrong (15mm instead of 10mm
— typo). What do you do?

> Two recoveries depending on impact: (a) if no MOs have confirmed
> since the activation, draft a corrected spec, raise a follow-on
> ECO, and apply — the broken spec gets superseded after seconds
> of "production." (b) If MOs have already confirmed and run with
> the wrong vent gap, raise an ECO to re-activate the previous
> spec immediately (stops the bleeding), then raise a follow-on
> with the corrected values. Document both ECOs with chatter
> referencing each other.

**4.** A PLM-Approver who isn't on your team clicks Activate
directly on a draft cut spec without an ECO. You discover it during
a Monday review. What do you do?

> Open the now-active spec. Raise an ECO retroactively
> (target_kind=cut_spec, cut_spec_id=this spec), explain in the
> description what should have happened, walk through the stages
> with the approver explicitly named, and apply. The audit trail
> catches up. Use the incident to retrain the approver — the
> Activate button is a footgun and exists only for emergencies.

**5.** You're trying to test the new product end-to-end in a staging
database. You activate the new cut spec in staging, but production
is still on the old one. A planner asks *"are operators going to see
the new constants?"* What's the answer?

> Only in staging. Cut spec is a database-scoped record — staging
> has its own `southbrook.cut.spec` table. When the ECO is applied
> in production, that database's spec activates and production
> operators see the new constants on the next MO confirm. There is
> no automatic staging-to-production replication; the ECO must be
> applied in each database. The pre-prod test in staging is
> deliberate — it lets you verify constants before they hit the
> shop.

---

## What this lesson does NOT cover

- Cut spec model fundamentals — every field, the activation
  mechanics in detail — lesson 4.2.
- How operators read the cut spec at their stations — lesson 1.7.
- ECO fundamentals (raising, approving, applying) — lesson 4.1.
- The BoM that will read these constants — that's lesson 11.4.
- Per-product BoM overrides — covered in lesson 11.4.
- New attribute values for cut-related customer choices — lesson
  11.5 and lesson 5.4.
- The ProductGraph release flow (which does **not** fire on cut
  spec activation) — lesson 11.8.
- Cut spec scoping per product — a product gap; file a ticket if
  your environment routinely needs per-product cut constants.
