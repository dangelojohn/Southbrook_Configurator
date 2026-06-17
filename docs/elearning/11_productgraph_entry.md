---
course: 11 — Creating a New Product End-to-End
chapter: 11.2
title: Entering the New Product in ProductGraph
duration: 35 minutes
audience: PLM engineer creating the first system record for a new SKU green-lit at conception
prereqs: Lesson 11.1 (conception folder green-lit), Course 9 (ProductGraph fundamentals — `pg.item`, revisions, property templates, the release gate), basic Odoo navigation in the ProductGraph backend
custom_modules: product_graph_base, product_graph_revision, product_graph_release, southbrook_plm_productgraph
---

# Entering the New Product in ProductGraph

## Who this lesson is for

You're the PLM engineer. Yesterday a designer dropped a folder
`2026-06-17_<slug>_GREEN` in the New-Product Intake share. Today you
turn that folder into the first system record — a `pg.item` in the
ProductGraph platform. From this moment on, the part has a part
number, an audit log, and a place on the hub. Everything in lessons
11.3 through 11.8 hangs off this record.

This lesson does *not* cover what ProductGraph is, why it exists, or
how the property-template system works. That's Course 9. This lesson
is the **workflow-specific delta**: how you take the conception
folder and create the corresponding ProductGraph entry, attach the
right metadata, and walk it through to the *engineering* state ready
for cut-spec authoring (lesson 11.3).

## Where this lives on the site

ProductGraph is the standalone platform — separate database, separate
URL from the main Southbrook Odoo instance. Sign in at the
ProductGraph URL with your PLM credentials, then:

> **ProductGraph → Engineering → Items**

Click *New*. The form is the standard `pg.item` form documented in
Course 9 lesson 9.2. You'll also touch:

> **ProductGraph → Configuration → Property Templates**

…to confirm the template you intend to pick exists and has the fields
your spec needs. And:

> **ProductGraph → Engineering → Items → \<your new item\> → Revisions**

…where the first `pg.revision` (revision A) is auto-created when the
item is saved.

## What your screen shows

The `pg.item` form (`/Users/naadmin/product_graph_v19/addons/product_graph_base/models/pg_item.py`):

- **Part number** (`part_number` on `pg.item`) — auto-assigned on
  save, format `PG-<TYPE>-NNNN` where `<TYPE>` is one of `ASM`,
  `PRT`, `BUY`, `DOC`, `SFT`, `SVC`. For a Southbrook cabinet SKU
  this is almost always `PG-ASM-NNNN` (it's an assembly). Do **not**
  pick the type carelessly — burned sequences are forever.
- **Name** (`name`) — human-readable. Convention: family + size +
  configurable axis, e.g. *Base 1-Door Sink Surround 24-36"*.
- **Description** (`description`, Html) — paste the verbatim
  customer requirement from `intake.md` of the conception folder.
  This is the only place in the platform where the customer's words
  survive end-to-end; future engineers reading this in three years
  will thank you.
- **Item type** (`item_type`) — `assembly` for a buildable cabinet.
  `purchased` if you're ever wrong and this is actually a
  buy-to-resell item; for Southbrook SKUs it should never be.
- **Category** (`category_id` → `pg.category`) — the engineering
  category. Pick one that already exists; do not create new ones
  here (that's a Course 9 admin task).
- **Tag(s)** (`tag_ids` → `pg.item.tag`) — multi-tag. At minimum
  apply `cabinet`, plus the family tag (`base` / `wall` / `tall` /
  `accessory`), plus any cross-cutting tag the conception folder
  implies (`sink`, `corner`, `floating`, …).
- **State** (`state`) — starts at `concept`. You'll move it through
  `prototype` → `engineering` over the course of lesson 11.3 and
  11.4. The release happens in lesson 11.8.
- **Property templates** (`property_template_ids` → many2many
  `pg.property.template`) — pick the template(s) whose fields match
  the spec from `spec_draft.md`. For a cabinet, that's almost
  always *Cabinet — Carcass & Door* plus *Hardware Spec*. If a
  field your spec needs isn't on any existing template, **stop and
  file a request to extend the template** — do not write the value
  into `internal_notes` and hope.
- **Responsible** (`responsible_id` → `res.users`) — you, today.
  Hand-off to a manufacturing engineer later via the revision flow.
- **Image** (`image_1920`) — drag the conception sketch in. It's
  placeholder-grade; lesson 11.4 (BoM) will replace it with the
  FreeCAD render once the BoM is real.

Smart buttons across the top: **Revisions** / **EBOMs** / **BOMs** /
**MOs** / **Assets**. On a fresh item, only *Revisions* has anything
(the auto-created revision A in `draft` state).

## Your daily flow

**1. Open the conception folder (2 min):**

- Read `intake.md`, `scope.md`, `spec_draft.md`, and `sketch.<ext>`
  end-to-end. If the spec is too vague to act on, **do not invent**
  — send it back to the designer (lesson 11.1 has the
  "spec too vague" recovery).

**2. Verify a property template fits (5 min):**

- Open **ProductGraph → Configuration → Property Templates**. Find
  the template you think fits — for a cabinet, the standard pair is
  *Cabinet — Carcass & Door* and *Hardware Spec*.
- Open the template and read its `field_ids` (the
  `pg.property.field` rows). Cross-check against
  `spec_draft.md`: does every spec bullet have a matching field?
- If yes, proceed. If no, **stop**. File a property-template-extend
  request to the PLM platform owner (the request flow is in Course
  9 lesson 9.3). Do not start the item creation if the spec can't
  land cleanly — `internal_notes` is not a substitute for a
  proper field.

**3. Create the `pg.item` (10 min):**

- ProductGraph → Engineering → Items → *New*.
- Pick **Item type = assembly**. (Pick wrong here and you can't
  fix it — `pg.item.item_type` is forbidden to change once
  released; for Southbrook SKUs it's always `assembly`.)
- Fill **Name** per convention.
- Paste **Description** verbatim from `intake.md`.
- Pick **Category** (existing).
- Apply **Tags**: `cabinet` + family + cross-cutting.
- Add **Property templates** (the pair you verified in step 2).
- Set **Responsible = you**.
- Drag the **sketch** in as `image_1920`.
- **Save.** The part number assigns now (`PG-ASM-NNNN`); revision A
  auto-creates in `draft`.

**4. Fill the first revision's property values (10 min):**

- Open the auto-created revision A (smart button → Revisions →
  click row → form).
- The `pg.revision` form shows a *Properties* tab listing every
  field from every property template you attached, as
  `pg.property.value` rows (one per field) ready for you to fill.
- Fill **every** field with the best information you have. For
  ranges (e.g. width 24-36"), the template's field type tells you
  whether to enter a range or a single representative value
  (typically range for cabinet width, single for thickness).
- Fill **`change_summary`** on the revision: *"Initial concept from
  intake folder 2026-06-17_<slug>"*. This is required to advance
  the revision state.

**5. Attach the vendor stub if any (3 min — usually skipped):**

- If the SKU implies a vendor-supplied component you haven't bought
  before (rare for cabinets — common for novel hardware), create a
  `pg.vendor` stub (`/Users/naadmin/product_graph_v19/addons/product_graph_base/models/pg_vendor.py`)
  via *Engineering → Vendors* (model-only, no menu in Phase 1 — use
  the developer-tools "Open Model" path if you must; Course 9
  lesson 9.4 documents the workaround).
- 95% of cabinet SKUs skip this step.

**6. Attach the spec sheet (5 min):**

- Back on the revision form, *Documents* tab.
- Add a `pg.document` (`document_type = spec`) and upload
  `spec_draft.md` from the conception folder. This is the first
  audit trail of the customer requirement in the system.
- Add another `pg.document` (`document_type = drawing`) with the
  sketch image.
- *Do not* attach the BoM here — that comes later from
  `southbrook_plm` via the bridge addon (see the lesson's
  *behind the scenes* section).

**7. Move the item state forward (2 min):**

- On the `pg.item` form, click *Action → Move to Prototype*. The
  item state goes `concept → prototype`. The first audit-log row
  fires. This signals to lesson 11.3 (cut-spec authoring) that the
  product is real and they can start engineering against it.
- Do **not** move to *Engineering* yet. That happens at the end of
  lesson 11.4 (BoM created) — the convention is `prototype` =
  "creating engineering artefacts," `engineering` = "engineering
  artefacts exist and are coherent."

**8. Send the hand-off (1 min):**

- One-line Slack message to the cut-spec author (often you, but
  often a different PLM engineer with cut-math expertise):
  *"`PG-ASM-NNNN` in prototype, ready for cut spec auth. Conception
  folder at `<path>`."*

## Common mistakes + how to recover

**"I picked the wrong `item_type` (purchased instead of assembly)."**

You cannot change `item_type` on a released item, but on a
`concept`/`prototype` item you can — open the form, change the field,
save. The audit log will record the change. If the part number
sequence ended up wrong as a result (e.g. you got `PG-BUY-NNNN`
when you wanted `PG-ASM-NNNN`), see the next mistake.

**"My part number prefix is wrong."**

Cannot rewrite `part_number`. The clean path is: archive this
record (`active=False`), create a new one with the right type. The
old part number is burned but no other damage. *Do this before
moving the item past `concept` state* — once you're in `prototype`,
downstream references (the BoM, the configurator) start to land and
roll-back gets expensive.

**"The property template I need doesn't exist and I can't wait for
the platform owner to add a field."**

Don't write the missing value into `internal_notes`. The
configurator (lesson 11.5) and the BoM (lesson 11.4) read from
property values; values that live only in `internal_notes` are
invisible to every downstream consumer. The right escalation is to
file the template-extend request as a P1 and use the conception
folder to capture the missing value in the interim. Cost: half a
day waiting; benefit: every future SKU using this template gets the
field for free.

**"I forgot to fill `change_summary` on revision A and now I can't
advance the revision."**

Fill it. The constraint
(`/Users/naadmin/product_graph_v19/addons/product_graph_revision/models/pg_revision.py`)
is `change_summary` required to leave `draft` — type the value, save,
then advance.

**"I attached the cut spec PDF as a `pg.document`."**

Detach it. The cut spec lives in `southbrook.cut.spec` over in the
main Southbrook database, not as a static document. Lesson 11.3
authors it there. The PLM bridge addon
(`southbrook_plm_productgraph`) is the link between them — see
behind-the-scenes.

**"Two PLM engineers created two items for the same conception
folder."**

Lesson 11.2's first action is *check no item already exists for this
intake*. If it slipped through, the convention is: keep the
lower-numbered part number (it's "wholesale" — first claim wins),
archive the higher one, post a chatter note on the survivor
explaining the merge. The conception folder's Slack channel should
have caught it; tighten that channel's etiquette.

## What the system is doing behind the scenes

When you save the `pg.item`:

- A row in `pg.item` is created with `state=concept`,
  `part_number` assigned from the ProductGraph sequence (different
  sequences per `item_type`).
- A row in `pg.revision` (revision A) is auto-created with
  `state=draft`, linked back via `item_id`.
- Each property template's `pg.property.field` rows generate
  matching `pg.property.value` rows on the revision (one per field,
  initially empty).
- The first audit-log row fires (ProductGraph audits every state
  transition; see Course 9 lesson 9.5).
- A `pg.audit.log` row records *concept created* with your user id,
  timestamp, and an empty `before` JSON.

When you click *Move to Prototype*:

- `pg.item.action_to_prototype()` runs
  (`/Users/naadmin/product_graph_v19/addons/product_graph_base/models/pg_item.py`).
- `state` flips `concept → prototype`. Another audit-log row fires.
- *No other downstream system is notified yet.* The Southbrook main
  Odoo database has no knowledge of this item — that wiring happens
  later, when the cut spec is activated (lesson 11.3) and the BoM
  is created (lesson 11.4). The bridge addon
  `southbrook_plm_productgraph` only fires on **ECO apply**
  (`southbrook.eco.action_apply` →
  `southbrook.eco._should_trigger_pg_release` → creates a
  `pg.release`); creating the `pg.item` itself is one-way upstream
  metadata.

The deliberate design: ProductGraph is the "what" (the part
identity, the property values, the audit trail); Southbrook PLM is
the "how" (the cut spec, the BoM, the ECO that ties them
together). Lesson 11.8 (release + iteration) is where the two
systems re-sync via a `pg.release` triggered by the formal release
ECO.

## Quiz (5 questions, applied)

**1.** You open the conception folder and find a green-light
`spec_draft.md` that says *"Width 18-30", height 32-42", melamine
box, slab door, soft-close hinges, finished both sides"*. Which
property templates do you attach to the `pg.item`?

> *Cabinet — Carcass & Door* (covers width range, height range, box
> material, door style, finished-sides flag) and *Hardware Spec*
> (covers hinge type, soft-close). If your installation doesn't have
> a *Hardware Spec* template, hardware values land on the
> *Cabinet — Carcass & Door* template's hardware fields instead;
> Course 9 lesson 9.2 documents the template inventory.

**2.** You picked **item_type = purchased** by mistake. You saved
the item. The part number came back `PG-BUY-0117`. You haven't
moved to prototype yet. What do you do?

> Edit the form, change `item_type` to `assembly`, save. The audit
> log records the change. The part number stays `PG-BUY-0117`
> (sequences don't rewrite). If you can't live with the wrong
> prefix, archive this record (`active=False`) and create a new
> one — clean fix, costs one burned sequence. Do this **before**
> moving to prototype, because once downstream artifacts land
> against `PG-BUY-0117`, rollback gets messy.

**3.** The designer says *"don't bother creating the `pg.item` yet,
I'm still iterating on the spec."* The conception folder is not
green-lit. What do you do?

> Wait. Lesson 11.2 fires only when the conception folder is
> renamed `*_GREEN` and the Slack hand-off has happened. Creating
> the `pg.item` early burns part numbers, pollutes the ProductGraph
> hub with concept records that may never reach prototype, and
> bypasses the conception gate that's designed to keep junk out of
> the platform.

**4.** Three months from now you discover the description on the
`pg.item` doesn't match what the customer originally asked for. The
SKU is in production. What do you do?

> Raise an ECO. ProductGraph items past `released` are
> revision-immutable; the description on `pg.item` itself is
> mutable but the change must be audited. Open a
> `southbrook.eco` (target_kind=*document*) noting the description
> correction, attach the new wording, advance through the ECO
> stages, and let `_apply_document` fire. The change appears in
> the audit log of both `southbrook.eco` and (via the bridge) the
> next `pg.release`.

**5.** You finish the revision A property values, advance to
prototype, and the cut-spec author (lesson 11.3) says *"I don't see
the item — there's no link from `southbrook.cut.spec` to the
`pg.item`."* What's going on, and what do you do?

> Nothing's wrong. `southbrook.cut.spec` has **no per-product link**
> — it's a single global active record covering the 8 NF14
> constants for the whole shop. The cut-spec author doesn't read
> from the `pg.item`; they read from the conception folder + the
> property values you filled. Lesson 11.3 covers this gotcha
> directly. The product/cut-spec link lives at the ECO level
> (`southbrook.eco.cut_spec_id`), not the product-template level.

---

## What this lesson does NOT cover

- ProductGraph fundamentals — `pg.item`, revisions, the property
  template system, the audit log — that's Course 9 (lessons 9.1
  through 9.5).
- Cut spec authoring in `southbrook.cut.spec` — that's lesson 11.3.
- Creating the `mrp.bom` for the product — that's lesson 11.4.
- The configurator entry — that's lesson 11.5.
- The release gate where `pg.item.state` flips
  `engineering → released` — that's lesson 11.8.
- The `southbrook_plm_productgraph` bridge details (how the ECO
  apply triggers a `pg.release`) — covered in lesson 11.8 and in
  Course 9 lesson 9.6.
- Vendor stub management beyond the one-line stub creation in
  step 5 — Course 9 lesson 9.4.
