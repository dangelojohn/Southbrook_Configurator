---
course: 11 — Creating a New Product End-to-End
chapter: 11.8
title: Production Release + Iteration
duration: 35 minutes
audience: PLM engineer + Production manager closing out the new-product introduction — taking the first-MO learnings, capitalising them into a formal ECO, walking the SKU through to ProductGraph release, and seeding the iterate-or-retire decision loop
prereqs: Lesson 11.7 (first MO complete, debrief notes captured), Lesson 4.1 (ECOs — raising, walking through stages, applying), Course 9 lessons on `pg.release` and the ProductGraph release flow, Lesson 11.2 (the `pg.item` is in `engineering` state — this lesson promotes it to `released`)
custom_modules: southbrook_plm, southbrook_plm_productgraph, product_graph_release, product_graph_base, southbrook_manufacturing_intelligence
---

# Production Release + Iteration

## Who this lesson is for

You're the PLM engineer who started this product back in lesson
11.2 and the production manager who watched its first MO yesterday.
The first run produced data — actual cycle times, scrap events,
unexpected hardware-resolver behaviour, an operator's notebook
full of *"next time we should..."*. Today you turn that data into a
formal ECO, walk it through approval, let the ECO apply propagate
to ProductGraph via the bridge, and decide: is this SKU ready for
customer orders?

This lesson is the **terminal step of new-product introduction**.
After this lesson, the SKU is either *released for customer
orders* (the normal outcome) or *parked for a second test MO* (a
common outcome on novel-construction SKUs). It also covers the
flip-side: when to formally **retire** a product — the inverse of
this whole course.

## Where this lives on the site

> **Southbrook PLM → Change Orders → New**

…for the post-MO ECO. Then:

> **ProductGraph → Engineering → Items → \<PG-ASM-NNNN\>**

…to walk the `pg.item` state from `engineering → released`.

> **ProductGraph → Engineering → Releases**

…to confirm the `pg.release` row was created by the bridge addon
and executed cleanly.

> **Kitchen Ops → MI Dashboards**

…to confirm the new cycle-time baseline lands cleanly after the
ECO applies.

## What your screen shows

The `southbrook.eco` form (lesson 4.1 covers every field; recap
for the post-MO ECO):

- **Name** (`name`) — sequence-assigned (`ECO/2026/NNNN`).
- **Title** — convention: *"Post-MO calibration for
  `PG-ASM-NNNN`"*.
- **eco_type_id** → pick a type with `target_kind = bom` (the
  primary change is a BoM revision capturing cycle-time and
  component fixes).
- **bom_id** → the BoM you authored in lesson 11.4 (version 1).
  This is the **target** BoM the ECO will copy-and-revise.
- **new_bom_id** — empty when you raise the ECO; populated when
  `_apply_bom` runs.
- **document_ids** → attach `first_mo_debrief.md` from the
  conception folder plus the MI dashboard screenshot.
- **stage_id** → the configurable ECO Kanban stage (`open` is the
  starting `state`; stages typically go *Draft → Review →
  Approved → Applied*).

The bridge-extended fields
(`/Users/naadmin/southbrook-v19cr/addons/southbrook_plm_productgraph/models/southbrook_eco.py`):

- **pg_ebom_id** — the linked ProductGraph EBOM record. For the
  first-release ECO, this links to a `pg.ebom` created by the PLM
  team in ProductGraph (Course 9 lesson 9.4 covers EBOM authoring).
- **pg_release_id** — populated when the bridge creates the
  release (read-only).
- **pg_auto_release** — boolean, default `True`. Leave on for the
  release ECO — you want the propagation to fire.

The `pg.release` form
(`/Users/naadmin/product_graph_v19/addons/product_graph_release/`)
that the bridge creates:

- **ebom_id** — the EBOM being released.
- **release_reason** — typically inherited from the ECO's
  description.
- **state** — `pending → executing → completed → failed`.

The `pg.item` form:

- **state** — `engineering` (from lesson 11.4). The
  `action_force_release` button (visible to PLM-Approvers) flips
  it to `released`. This happens **automatically** when a
  `pg.revision` for this item moves to `released` and triggers
  `_auto_release_from_revision` — but on first-release it's
  cleanest to call the action explicitly.

## Your daily flow

**1. Gather the debrief inputs (5 min):**

- Open `first_mo_debrief.md` from the conception folder
  (created end of lesson 11.7).
- Open the MI dashboards from the post-run morning.
- Read the Hermes Console recommendations filed against the test
  MO: `slow_workorder`, `scrap_event`, `cut_spec_audit`,
  `materials_blocked`. Mark each with disposition: *act on*,
  *ignore (first-run noise)*, *defer (single sample insufficient)*.
- List the changes to make. Typical first-release ECO bundle:
  - **Cycle-time revision** on 1-3 operations (based on actual vs
    planned at the operations that showed >20% variance).
  - **BoM-line correction** for any hardware the auto-resolver got
    wrong (or the configurator-to-BoM bridge missed).
  - **Routing tweak** if the operations sequence needs to change
    (e.g. insert a `SAND` pass that wasn't on the original BoM).
  - **Cut spec audit** if scrap or panel issues implied the
    constants need revisiting (almost always the answer is *no, the
    SKU needs per-product BoM overrides instead* — lesson 11.3).

**2. Raise the post-MO ECO (10 min):**

- **Southbrook PLM → Change Orders → New**.
- **Title**: *"Post-MO calibration for `PG-ASM-NNNN`"*.
- **eco_type_id**: pick a `target_kind = bom` type.
- **bom_id**: the existing BoM (version 1).
- **description**: bullet the changes. Cite the specific MI
  recommendation IDs and the operator's notebook page. Be
  specific — *"`SB-EDGE` cycle time 12→18 min based on test MO
  actual of 17.2 min plus 1-min margin"* is auditable; *"adjust
  cycle times"* is not.
- **document_ids**: attach `first_mo_debrief.md` and the MI
  screenshot.
- **pg_ebom_id**: confirm linked to the right ProductGraph EBOM.
- **pg_auto_release**: leave on.
- *Save*. State is `open`.

**3. Author the revised BoM (varies — 30-60 min):**

The ECO doesn't itself revise the BoM — when `_apply_bom` runs, it
*copies* the source BoM with `southbrook_version + 1` and archives
the original. You need to provide the revisions on a **duplicate**
of the BoM, which becomes the apply target.

- Open the current BoM (version 1). Duplicate it (Odoo native
  duplicate). The duplicate is `southbrook_version` 0 initially —
  the `_apply_bom` flow bumps it.
- Make the revisions on the duplicate: cycle time updates,
  component line fixes, routing changes.
- Save.
- Back on the ECO, set **new_bom_id** = your revised duplicate.
  (Or wait for `_apply_bom` to do this automatically — depends on
  the ECO type's setup. Lesson 4.1 covers the variant.)

**4. Walk the ECO through approval (varies — hours to days):**

The ECO stages enforce sign-off. For the post-MO ECO the typical
flow is:

- *Draft → Review*: the PLM engineer (you) advances after the
  revised BoM is ready.
- *Review → Approved*: the production manager reviews the
  revisions, confirms they match the debrief, signs off.
- *Approved → Applied*: the PLM-Approver clicks *Apply*.
  `action_apply` dispatches to `_apply_bom`, which:
  - Copies the revised BoM with `southbrook_version + 1`.
  - Archives the original BoM (`active=False`).
  - Writes the new BoM's id back to `southbrook.eco.new_bom_id`.
  - Posts chatter on both the ECO and the new BoM.

**5. Confirm the ProductGraph bridge fired (5 min):**

After ECO apply, the bridge addon
(`southbrook_plm_productgraph`) runs
`_should_trigger_pg_release()` and, if true, creates a
`pg.release` on the linked `pg.ebom`:

- Open the ECO. **pg_release_id** should now be populated.
- Click through to the `pg.release` form. State should be
  `completed` (or `executing` if you're fast).
- If state is `failed`, the bridge errored — read the chatter on
  the `pg.release` record for the cause. Common causes:
  - The `pg.ebom` linked on the ECO isn't `released` in
    ProductGraph (it needs to be a real, releasable EBOM, not a
    draft).
  - The ProductGraph database is unreachable (the bridge runs
    in-process but reads/writes against the standalone
    ProductGraph schema — check the `product_graph_release`
    addon is installed and the system parameters are right).
- Failures **do not roll back the ECO** (per the bridge's
  defensive contract). Fix the bridge issue and re-create the
  `pg.release` manually if needed.

**6. Promote `pg.item` to `released` (3 min):**

In ProductGraph:

- Open `PG-ASM-NNNN`.
- Click **Action → Move to Released** (`action_force_release` on
  `pg.item`).
- State flips `engineering → released`. Audit-log row fires.
- The `pg.item.product_id` field is set to the
  `product.product` representing the new SKU's
  **first dynamic variant** (the OCA configurator's variant
  policy — Q6 of the estimating brief). This is the ProductGraph-
  to-Southbrook linkage that becomes permanent at release.

**7. Decide: ship to customers, or run a second test MO? (5 min):**

The decision criterion:

- If the first MO's cycle times, scrap, and hardware-resolver
  behaviour all came out within ±10% of planned **and** the
  revised BoM should close even that gap → **ship to customers**.
- If any of those came out >20% off plan and the revisions are
  speculative ("we *think* this will fix it") → **run a second
  test MO** before shipping.
- The production manager owns this decision; the PLM engineer
  advises.

**Shipping to customers:**

- Confirm the `product.template` is *active for sale* and
  *published* on the website (if customer-facing).
- Brief the sales team: *"`southbrook.<xml_id>` is live. Here's
  the SKU brief: \[link to conception folder + signature spec
  sheet from lesson 11.6\]."*
- The first customer order will follow Course 5 + Course 2
  flows; no further new-product effort.

**Running a second test MO:**

- Loop back to lesson 11.7 step 2. Schedule a second internal
  MO. The new BoM (version 2) is what the second MO runs against.
- After the second MO, repeat this lesson — but the second post-
  MO ECO almost always bundles smaller revisions, and the
  decision usually flips to *ship*.

**8. The audit trail (2 min):**

Confirm the audit trail is complete. The new SKU should now have:

- **ProductGraph audit log** — every state transition on
  `pg.item` (`concept → prototype → engineering → released`)
  and every release on `pg.revision`.
- **Southbrook ECO history** — every ECO that has modified the
  BoM or cut spec (`southbrook_eco_history_ids` smart button on
  `mrp.bom`).
- **Cut spec supersession chain** — if any cut spec changes
  fired during the introduction (lesson 11.3).
- **MI baseline** — the new SKU's cycle-time baseline rolls into
  the MI dashboards as a new product line.
- **Conception folder** — frozen with all the artifacts. The
  folder gets one final filename change:
  `2026-06-17_<slug>_GREEN_RELEASED`. The folder is now
  read-only and part of the project archive.

**9. Hand-off to ongoing operations (1 min):**

- Slack the sales team + production manager + estimator:
  *"`PG-ASM-NNNN` / `southbrook.<xml_id>` released; conception
  folder archived; happy to take customer orders."*

## When to retire a product (the inverse)

The same machinery runs in reverse when a SKU is retiring:

- Raise an ECO with `target_kind = document` describing the
  retirement rationale (no longer profitable, vendor stopped
  supplying a key material, replaced by a successor SKU,
  customer demand died).
- Sign off through the stages.
- On apply, set `product.template.sale_ok = False` (no new
  customer orders).
- Optionally set `active = False` after the last in-flight order
  ships (the SKU disappears from search but its history remains).
- In ProductGraph, move the `pg.item` state via `action_to_service`
  → `action_to_obsolete`. State sequence: `released → service →
  obsolete`. The audit log captures the retirement.

The retirement flow uses the same ECO + ProductGraph machinery as
release — the difference is the disposition (`obsolete` vs
`released`).

## Common mistakes + how to recover

**"I applied the ECO and the bridge failed — no `pg.release` was
created."**

The ECO is still applied; the BoM is still revised; only the
ProductGraph propagation didn't fire. **Recovery**: open the
linked `pg.ebom` directly in ProductGraph, manually create a
`pg.release` (Course 9 lesson 9.4 documents this), and call
`action_execute_release()`. The audit gap is small (the manual
release records the same provenance as the bridge would have).
File a P2 ticket for the bridge failure so it doesn't repeat.

**"The revised BoM passed approval but the cycle time on `SB-EDGE`
still came in at 18 min on the first customer order — same as the
first test MO."**

Then the cycle time you put in the ECO was right and the first MO
wasn't an artefact. **Recovery**: nothing to do — the BoM is now
calibrated. The customer order's cycle is on-plan. The first MO's
12-min estimate was wrong from PLM; the revised 18-min estimate is
correct. Good. The variance gap closed.

**"I promoted `pg.item` to `released` before the ECO applied, and
now the post-MO BoM revisions can't propagate because ProductGraph
treats the item as immutable."**

ProductGraph items in `released` state are **revision-immutable**
(meaning `pg.revision` rows can't be edited), but the bridge
addon's `_should_trigger_pg_release` creates a **new** `pg.release`
on the `pg.ebom`, which is a different record than `pg.revision`.
Releases *can* happen on a released item. **Recovery**: nothing —
the bridge should still fire. If it doesn't, the cause is
elsewhere (probably the `pg.ebom` reference is wrong on the ECO).

**"The customer placed an order against the new SKU on day 1 and
we discovered a small bug — wrong default value on an attribute.
Do we ECO it, or fix-in-place?"**

ECO it. The new SKU is in production; fix-in-place is a habit
from pre-release engineering and you've left that phase. The
attribute default value is a `product.template.attribute.value`
record — raise an ECO with `target_kind = rule` (or `document` if
the change is purely informational), walk through approval (fast-
track for cosmetics), apply. Six months from now an auditor will
ask *"why does this attribute default to X and not Y?"* and the
ECO is your answer.

**"The MI baseline didn't update after the BoM revision."**

The MI engine reads from historical work-order durations. A
single-MO baseline is high-variance; the MI engine deliberately
defers committing a baseline until 3-5 MOs have completed. *Wait
for more MOs*; the baseline lands automatically. If after 5 MOs the
baseline still isn't reflecting the revised cycle time, file a
ticket — usually it's a deeper MI bug, not anything you did.

**"I want to retire the product but it has 12 customer orders
in-flight."**

Set `sale_ok = False` (no new orders). Leave `active = True`.
The in-flight orders complete normally. When the last order
ships, set `active = False`. In ProductGraph, move the `pg.item`
to `service` (not `obsolete`) — the *service* state is for
products no longer sold but still under support. Move to
`obsolete` only when the last customer warranty has expired.

## What the system is doing behind the scenes

When the ECO applies:

- `southbrook.eco.action_apply()`
  (`southbrook_plm/models/southbrook_eco.py`) dispatches on
  `target_kind`. For `bom`, calls `_apply_bom`.
- `_apply_bom` calls `self.bom_id.copy({'southbrook_version':
  self.bom_id.southbrook_version + 1, 'active': True})` and
  archives the original (`self.bom_id.active = False`).
- The new BoM's id is written to `self.new_bom_id`.
- Chatter rows on both BoMs and the ECO record the apply event.

When `_should_trigger_pg_release()` returns true (the bridge):

- `southbrook_plm_productgraph/models/southbrook_eco.py` extends
  `action_apply` to, after the super call, create a `pg.release`
  with `ebom_id = self.pg_ebom_id` and `release_reason =
  self.title`.
- `pg.release.action_execute_release()` runs:
  - Reads the EBOM's lines.
  - Updates the underlying `mrp.bom` references (for the bridge
    case where ProductGraph mirrors the BoM).
  - State flows `pending → executing → completed`.
- The ProductGraph audit log fires.

When `pg.item.action_force_release()` runs
(`product_graph_base/models/pg_item.py`):

- `state` flips `engineering → released`.
- `released_date` set to `fields.Date.today()`.
- `product_id` is set to the matching `product.product` record
  (the first dynamic variant).
- Audit-log row.

The ProductGraph release is **one-way** (D1 in the ProductGraph
decisions). Future Southbrook BoM revisions propagate **up** to
ProductGraph via the bridge; ProductGraph doesn't push state
**down** to Southbrook. This is deliberate — Southbrook is the
operational source of truth, ProductGraph is the engineering
master.

When the MI engine processes the second-and-later MOs:

- Per-station cycle times accumulate.
- After 3-5 MOs, a baseline lands in the MI engine and the new
  SKU shows up on the cycle-time variance dashboards.
- The dashboards now treat the SKU as a known product, not a
  first-run novelty.

## Quiz (5 questions, applied)

**1.** The first MO completed yesterday. The actual cycle times
were within 5% of planned. There were no scrap events. Hardware
auto-resolution worked. The operator notebook is empty. Do you
need the post-MO ECO?

> Yes — a minimal one. Even a "no changes needed" outcome
> deserves an ECO that records the *decision* to leave the BoM
> as-is, with the first-MO data attached. Future auditors will
> ask *"why was version 1 of this BoM also the version that went
> to customers?"* The minimal ECO is the answer:
> *"Post-MO calibration — first MO clean, no revisions"*. Apply
> with `pg_auto_release = True` so ProductGraph still gets the
> release.

**2.** The ECO applied but you notice `pg_release_id` is empty —
the bridge didn't fire. The ECO state is `applied`. What do you
check first?

> Three things in order: (a) `pg_ebom_id` on the ECO — is it
> populated? If empty, the bridge had nothing to release against.
> (b) `pg_auto_release` — is it `True`? If False, the bridge
> deliberately skipped. (c) `_should_trigger_pg_release()`'s
> internal logic — likely it requires the EBOM to be in a
> `released` state in ProductGraph; if the EBOM is in
> `draft`, the bridge no-ops. The fix is on the ProductGraph
> side: release the EBOM, then re-trigger.

**3.** The production manager wants to run a second test MO
before shipping to customers. The post-MO ECO has applied
(BoM is now version 2). What do you do for the second MO?

> Loop back to lesson 11.7 step 2. Schedule a second internal MO
> against the *Demo — First MO* partner (or a new sandbox
> partner *Demo — Second MO* for clarity). The MO uses
> BoM version 2 automatically because `_apply_bom` archived
> version 1. Run it. Repeat the debrief. If clean, the next
> post-MO ECO is trivially small and you ship to customers
> after.

**4.** Three months after release, you're retiring the SKU
because the vendor stopped supplying the door substrate. The
SKU has 4 in-flight customer orders. What do you do?

> (a) Set `sale_ok = False` on the template — no new orders
> accepted. (b) Leave `active = True` so the 4 in-flight orders
> complete normally. (c) Raise an ECO with
> `target_kind = document` describing the retirement (vendor
> reason, customer-comm plan). (d) Move `pg.item` from
> `released → service` (not `obsolete` — there are still
> in-flight orders). (e) After the last order ships,
> `active = False` and `pg.item → obsolete`. The MI dashboards
> stop showing the SKU as actively measured; the audit trail
> is complete.

**5.** Six months after release, a customer service rep finds a
small typo in the SKU's customer-facing description on the
website. What's the right channel to fix it?

> An ECO. `target_kind = document`. Title:
> *"Description typo fix for `southbrook.<xml_id>`"*. The actual
> fix (editing `product.template.description_sale`) takes 10
> seconds; the ECO walking through approval takes a day. The
> ECO is the *audit trail*, not the *work*. Yes, this feels like
> overkill for a typo. It is overkill. It is also correct —
> auditors don't distinguish typos from material changes when
> they ask "who changed this and why?". The ECO is the answer
> for both cases.

---

## What this lesson does NOT cover

- ECO fundamentals (raising, walking through stages, applying) —
  lesson 4.1.
- The first MO mechanics (scheduling, release gate, shop-floor
  monitoring) — lesson 11.7.
- Cut spec activation via ECO — lesson 11.3 and lesson 4.2.
- ProductGraph release fundamentals — Course 9 lesson 9.4.
- The `pg.item` state machine in detail — Course 9 lesson 9.2.
- The `pg.ebom` model and how it relates to `mrp.bom` — Course
  9 lesson 9.4.
- MI engine internals — Course 3.
- Customer-side communications about new SKU launches or
  retirements — Course 6.
- The first customer order flow — Course 5 + Course 2 (the
  SKU has graduated from new-product introduction).
- Cross-product migration when a new SKU replaces an old one
  (the *successor SKU* path) — covered by ECO chaining,
  documented in the conception folder when relevant.
