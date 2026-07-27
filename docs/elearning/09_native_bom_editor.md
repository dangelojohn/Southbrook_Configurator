---
course: 9 — ProductGraph
chapter: 9.4
title: The Native EBOM Editor — Authoring + Releasing to MRP
duration: 40 minutes
audience: PLM engineer authoring engineering BOMs
prereqs: Lesson 9.1 (overview), Lesson 9.2 (property templates)
custom_modules: product_graph_ebom, product_graph_release (release flow), product_graph_revision (immutability)
---

# The Native EBOM Editor — Authoring + Releasing to MRP

## Who this lesson is for

You're the PLM engineer who authors the engineering BOM for a cabinet
assembly: the list of carcass panels, hinges, drawer slides, fasteners
that go into it. You will NOT use Odoo's `mrp.bom` editor for this —
ProductGraph has its own EBOM model (`pg.ebom`) one level upstream
from `mrp.bom`. This lesson is the practical reality of using
ProductGraph's editor, the differences from Odoo's `mrp.bom` editor,
and how a successful release turns your `pg.ebom` into a working
`mrp.bom` that production can use.

This lesson is entirely on the **standalone ProductGraph platform**
side. The Southbrook bridge addon does not touch EBOMs — it only
*triggers* the release that converts them to `mrp.bom`.

## Where this lives on the site

> **Manufacturing → ProductGraph → EBOMs**

For a specific item's EBOM:

> **Manufacturing → ProductGraph → Items → [pick item] → Smart button:
> EBOMs → [pick draft EBOM]**

The Odoo-native MRP BOM editor still exists at:

> **Manufacturing → Products → Bills of Materials**

You will see `mrp.bom` records there AFTER a `pg.release` runs. **Do
not edit them directly.** Bible Rule R1 forbids any code path from
writing `mrp.bom` outside `pg.release.action_execute_release`. The
`mrp.bom` you see is a *projection* of the released `pg.ebom`;
hand-editing it diverges your engineering source of truth from your
manufacturing source of truth.

## What your screen shows

A `pg.ebom` form has three identity fields and one big list:

- **EBOM Reference** (`name`) — auto-assigned from the `pg.ebom`
  sequence. Default `New` until create.
- **Root Assembly** (`root_item_id`) — many2one to `pg.item`,
  `ondelete='restrict'`. Domain restricts to
  `item_type in ('assembly','part')` — purchased components can't be
  roots.
- **Item Revision** (`revision_id`) — many2one to `pg.revision`,
  `ondelete='restrict'`. Domain restricts to revisions of the chosen
  root item. The (root_item, revision) tuple is unique
  (`_root_revision_unique` constraint) — only one EBOM per (root,
  revision) is allowed.
- **Status** (`state`) — the 4-state lifecycle:
  `draft → review → released → superseded`. Tracking enabled.
- **EBOM Type** (`ebom_type`) — `production` or `prototype`. Production
  is the default and is what gets fed to MRP.
- **Components** (`ebom_line_ids`, one2many to `pg.ebom.line`) — the
  list of child items. Each line shows:
  - **Sequence** (`sequence`, default 10) — drives line ordering.
  - **Component** (`pg_item_id`) — the child engineering item.
    Required, `ondelete='restrict'`.
  - **Specific Revision** (`pg_revision_id`) — optional, pins to a
    specific released revision. Leave blank to use whatever the child
    item's current released revision is at release time.
  - **Part Number** (`part_number`) — related from
    `pg_item_id.part_number`, stored for grouping/search.
  - **Item State** (`item_state`) — related from `pg_item_id.state`,
    read-only. Useful to spot draft children before submitting for
    review.
  - **Quantity** (`product_qty`) — float, default 1.0.
  - **UoM** (`uom_id`) — defaults from the child item's `uom_id` via
    `_onchange_pg_item_id`.
  - **Designator** (`reference`) — free text. Examples: "R1", "C12",
    "Top Hinge", "Left Gable".
  - **Notes** (`notes`) — free text.
  - **Type** (`bom_line_type`) — `normal / phantom / optional`.
    Phantoms are sub-assemblies that explode through; optional lines
    are engineering-deferred decisions for manufacturing.
  - **Alternate Group** (`alternate_group`) — free-form tag identifying
    a set of interchangeable parts (e.g. "HINGE_GROUP").
  - **Primary in Alternate Group** (`is_primary`) — within an alternate
    group, exactly one line should be marked primary. The validate
    step warns (not blocks) on groups with !=1 primary.

After release, four extra fields are stamped:

- **Effective Date** (`effective_date`)
- **Released By** (`released_by_id`)
- **Released At** (`release_timestamp`)
- **Superseded By** (`successor_ebom_id`) — back-pointer set on the
  previous EBOM when a new one is released for the same root item.

## Your daily flow

**1. Create the EBOM (draft).**

- Open the item you're authoring for — say, the 36" base cabinet
  assembly.
- Smart button → **EBOMs → New EBOM**.
- The form auto-fills `root_item_id`. Pick the `revision_id` — must be
  a draft or review revision of the same item, on the first author.
- Save. `state = 'draft'`, name auto-assigned via `pg.ebom` sequence.

**2. Add lines.**

The editor uses Odoo's native x2many editable list (Decision D4 —
"native Odoo x2many editable list + CSV import/export + keyboard-
friendly inline reference & qty edit. NO custom OWL widget in Phase
1"). You're not getting a spreadsheet experience; you're getting Odoo
list inline editing.

- Click *Add a line*.
- Pick the child `pg_item_id` (autocomplete on part_number or name).
- Quantity, UoM (pre-filled), designator, notes.
- Press *Tab* or arrow keys to move between fields without your hand
  leaving the keyboard.
- Save.

For larger BOMs (50+ lines, e.g. a full cabinet with hardware):

- Click the **Import Lines** button (if the import wizard is enabled
  in your install) — accepts a CSV with columns `part_number, qty,
  uom, designator, notes, alternate_group, is_primary`.
- The importer matches `part_number` to `pg.item` and rejects unknown
  parts.

**3. Submit for review.**

- Click **Submit for Review** (`action_submit_for_review`).
- Authority gate: requires `group_pg_engineer`. Approvers also have
  this group transitively.
- Pre-check: EBOM must have at least one line, else UserError("EBOM X
  has no lines.").
- State flips `draft → review`. Audit log row written with
  `action='state_change'`. Chatter message posted.

**4. Validate (optional but recommended).**

- Click **Validate** (`action_validate`). This runs the same checks
  the release will run, WITHOUT changing state. Returns a dict
  `{ok, errors, warnings}`. Use it as a pre-flight.
- Validation checks:
  - **All child items must be released.** Non-released children are
    listed as errors (this is the cross-model gate, EBOM Bible §10).
  - **Recursion.** A root item appearing in its own descendants is an
    error — that's a circular BOM. Phase 1's check is shallow
    (top-level duplicate of the root); deeper cycles are caught by the
    closure rebuild.
  - **Alternate group integrity.** Groups with !=1 primary line are
    warnings (release proceeds; planner picks at MO time).

**5. Release.**

- Click **Release** (`action_release`).
- Authority gate: requires `group_pg_approver`. Engineers can't
  self-release.
- Runs the validation; releases only if `validation['ok']` is True.
- Finds the previous active released EBOM for the same root_item and
  marks it `superseded` + sets `successor_ebom_id`. Clears its
  closure rows.
- Stamps `effective_date = today`, `released_by_id`, `release_timestamp`.
- Writes a `pg.audit.log` row with `action='state_change'`,
  `from_state='review'`, `to_state='released'`.
- **Rebuilds the closure** via
  `self.env['pg.ebom.closure']._build_for_ebom(rec)` — every
  (ancestor, descendant, depth) row for the BOM tree, the same pattern
  as `pg.relationship.closure`. This is what makes
  `where_used` / `bom_explode` queries fast at MCP/REST time.

The EBOM is now `released` and IMMUTABLE — the `write` override
blocks all field changes except the small `_MUTABLE_ON_LOCKED` set
(`state`, `active`, chatter fields).

**6. Release to MRP (separate step).**

Releasing the EBOM does NOT create a `mrp.bom`. That's a separate
`pg.release` flow:

- From the released EBOM, click **Release to MRP** (opens the
  `pg.release` wizard) — or create a `pg.release` programmatically
  with `ebom_id = your_ebom.id, release_reason = "Reason text"` and
  call `release.action_execute_release()`.
- The release flow is the only writer of `mrp.bom` (Bible R1). See
  lesson 9.6 for the Southbrook bridge that runs this for you on ECO
  apply.

## Differences from Odoo's `mrp.bom` editor

The native MRP BOM editor has:

- Variants (`bom_id.product_id` vs `product_tmpl_id`)
- Routings (`operation_ids`)
- Byproducts (`byproduct_ids`)
- Product type filtering

ProductGraph's EBOM is **upstream** of all that:

| ProductGraph EBOM | Odoo `mrp.bom` |
|---|---|
| `root_item_id` — the engineering item | `product_tmpl_id` — the product template |
| `revision_id` — explicit engineering revision | (no concept of revision) |
| 4-state lifecycle with approver gate | No state |
| Closure-materialised where-used | Live recursive query |
| Property-driven lines (read property values off child revisions) | Variant-driven lines (read attribute values off variants) |
| Immutable after release | Editable anytime |
| Audit-logged transitions | None |
| `alternate_group` for substitute parts | `byproduct_ids` and operation alternatives |

The two are connected via the release: `pg.release.mrp_bom_id` is the
`mrp.bom` that was minted from this EBOM. The closure is what powers
multi-hop "what cabinets use this hinge" without walking the tree at
read time.

## How the EBOM syncs to `mrp.bom` via the bridge

The Southbrook bridge addon (`southbrook_plm_productgraph`) is the
mechanism by which an ECO closure triggers an EBOM release:

1. Engineer raises an ECO in `southbrook_plm`.
2. ECO has `pg_ebom_id = your_released_ebom.id` set and
   `pg_auto_release = True`.
3. ECO state moves through draft → approved → applied.
4. `action_apply` runs. **After** the PLM side does its job (state
   change, kind dispatch, `applied_date` stamp), the bridge runs:
   ```python
   release = self.env["pg.release"].create({
       "ebom_id": self.pg_ebom_id.id,
       "release_reason": f"Southbrook ECO {self.name}: {self.title}",
   })
   release.action_execute_release()
   ```
5. The release runs the full mint-mrp.bom flow (validate, ensure
   product, freeze open MOs on previous BOM, create new mrp.bom,
   archive previous, write release outcome, audit, notify).
6. `eco.pg_release_id` is set to the new `pg.release.id`; chatter
   message posted on the ECO.

If the release fails, the ECO **stays applied** (Manufacturing
Governance §8). The bridge does NOT roll back the ECO — that would
corrupt the PLM audit trail. A chatter note flags the failure and the
Approver retries from the EBOM form.

## Conflict resolution if both sides edit

Phase 1's conflict story is **simple by design**:

- The released `pg.ebom` is immutable. You cannot edit it.
- The `mrp.bom` is editable in the Odoo UI, but Bible R1 forbids it.
- If someone edits the `mrp.bom` manually:
  - The `pg.release` record's `mrp_bom_id` still points at the now-
    drifted BOM. There is no automatic re-sync.
  - Next release for the same product will archive the drifted BOM
    (via `archive_previous_bom=True` on the next release) and mint a
    fresh one from the new EBOM, so the drift is auto-corrected on
    the NEXT release.
  - In between, the manufacturing team is following a BOM that
    diverges from engineering intent.
- The right workflow when you find drift: open a new draft revision
  on the root item, copy the changes from the modified `mrp.bom` into
  a new `pg.ebom`, release it. The next `pg.release` will replace the
  drifted `mrp.bom` cleanly.

Phase 2 plans a re-sync gate, but it's out of scope here.

## Common mistakes + how to recover

**"I added a line for a child item but `action_release` fails saying
'Non-released child items: …'."**

The cross-model gate (EBOM Bible §10). All children must be in
`released` state before the parent EBOM can release. Two paths:
release each child first (boring but correct), or remove the child
from the EBOM if it's not actually a real component yet.

**"I tried to add a child item that's the same as the root. The
validation flagged it."**

Working as designed — `action_validate` flags top-level recursion. A
root item appearing as its own immediate child is a circular BOM. The
deeper case (root appears as a grandchild via a phantom) is caught by
the closure rebuild on release.

**"I released an EBOM with an alternate group that has two primaries.
Why didn't the release fail?"**

Alternate-group primary integrity is a **warning**, not an error.
`action_validate` returns it as a warning string but doesn't add it to
`errors`. Release proceeds; the planner picks which alternate to use at
MO time (Phase 1 has no auto-substitution per Mfg Governance §6 Rule
4.1). If you want this to block release, file a ticket.

**"I tried to edit a line on a released EBOM and got a
UserError about immutability."**

Working as designed. `pg.ebom.line._check_ebom_writable` blocks all
writes/unlinks when the parent EBOM is `released` or `superseded`. To
change the BOM, create a new revision of the root item, create a new
`pg.ebom` against that revision, modify lines there, release it. The
old EBOM auto-supersedes.

**"I released an EBOM and the `mrp.bom` didn't appear."**

EBOM release does NOT create `mrp.bom`. It transitions the EBOM state
and rebuilds the closure. To create the `mrp.bom` you need a separate
`pg.release` against the released EBOM. The bridge addon does this
automatically on ECO apply; manual is a wizard click or programmatic
`pg.release.create() → action_execute_release()`.

**"My EBOM is in `review` state and I want to add a line. The form
seems editable but my save did nothing."**

Lines can be edited in `draft` and `review` states. If your save
appeared to do nothing, check whether (a) you have
`group_pg_engineer`, (b) the line's child `pg_item_id` is actually
released — if not, the inline error might be silenced. Click
**Validate** to see the full diagnostic.

## What the system is doing behind the scenes

The release flow (`action_execute_release` on `pg.release`) is the
9-step process the EBOM hands off to:

1. **Validate** — every child line item is in `released` state and
   has a linked `product.product` (or `create_product_if_missing` is
   on so we mint one).
2. **Ensure product** — if the root item doesn't have a
   `product.product`, create one with `default_code = part_number`.
3. **Collect previous BOM** — search active `mrp.bom` for the same
   product template.
4. **Freeze open MOs** on the previous BOM — Manufacturing Governance
   §1 (MG-1). They go into `frozen_mo_ids` and `frozen_mo_count`.
5. **Create new `mrp.bom`** — THE ONLY PLACE in the codebase this
   happens (Bible R1). One `mrp.bom` header + N `mrp.bom.line` rows
   from the EBOM's `ebom_line_ids`.
6. **Archive previous** — set old `mrp.bom.active = False`
   (MG-5).
7. **Write release outcome** — `state='completed'`, `mrp_bom_id`,
   `product_id`, `release_timestamp`, `released_by_id`. This write
   uses `_pg_release_bypass=True` context to bypass the immutability
   guard on completed releases.
8. **Audit** — `pg.audit.log` row with `action='release'`,
   from/to/notes/payload (payload includes ebom_id, revision_id,
   mrp_bom_id, product_id, frozen_mo_count,
   incompatible_with_previous).
9. **Notify** — chatter post + subscribe the manufacturing group.

The entire run is inside `with self.env.cr.savepoint():`. Any
exception triggers a rollback inside the savepoint, the catch block
writes `state='failed'` and `failure_reason`, writes an audit row,
and re-raises. This is MG-8 — atomic savepoint ensures failure leaves
no partial `mrp.bom`.

The closure (`pg.ebom.closure`) is rebuilt per EBOM by
`_build_for_ebom`. Closure rows are `(ebom_id, ancestor_id,
descendant_id, depth)` tuples; queries like "find all assemblies that
use part X" become a one-domain search instead of a recursive walk.

## Quiz (5 questions, applied)

**1.** You author a `pg.ebom` for the 36" base cabinet, add 14
lines (panels, hinges, slides, fasteners). Two of the panel items are
still in `engineering` state. You click **Submit for Review**. What
happens?

> Submit succeeds — the engineer-state check is only "EBOM has at
> least one line." The non-released children fail at the
> next step: **Release** runs `action_validate` and fails with
> "Non-released child items: …". You have two options: release each
> non-released panel item (and its revision) first, or roll back the
> EBOM to `draft` (`action_reject_to_draft`, approver only) and remove
> those lines.

**2.** An engineer asks "I edited a `mrp.bom` line directly in
Manufacturing because the cabinet was missing a fastener. Did I just
break something?"

> Bible Rule R1 yes — `mrp.bom` is supposed to be written only by
> `pg.release.action_execute_release`. Your edit is now drift. Next
> `pg.release` for the same product will archive your drifted BOM and
> mint a fresh one from the released EBOM, silently overwriting your
> change. Right fix: create a new revision of the cabinet item, new
> draft `pg.ebom`, add the fastener line, submit, release, then
> release-to-MRP. The next manufacturing order picks up the corrected
> EBOM AND your change is preserved engineering-side.

**3.** Two engineers race: both create a draft `pg.ebom` for the same
(root_item, revision). What stops the duplicate?

> The `_root_revision_unique` constraint —
> `UNIQUE(root_item_id, revision_id)` — at the DB level. The second
> create raises an IntegrityError surfaced as a UserError. There's no
> Phase 1 collaborative-editing protection beyond that; whoever lost
> the race needs to either edit the existing draft or wait for the
> next revision.

**4.** A released EBOM has 6 lines, one with `alternate_group =
'HINGE_GROUP'` containing 3 alternates, one primary. A production
order based on the mrp.bom is in progress. The PLM engineer creates a
new revision, swaps the primary alternate to a different vendor's
hinge, and releases a new EBOM. What happens to the in-progress MO?

> The new `pg.release` finds the active `mrp.bom` for the product,
> calls `_freeze_open_mos(old_bom)`, the in-progress MO goes into the
> release's `frozen_mo_ids` (MG-1). The MO is NOT modified — it
> finishes against the old BOM/old hinge. The new `mrp.bom` becomes
> the active one for the next MO. The release record's
> `frozen_mo_count` shows the count; the audit log payload records
> which MOs were frozen.

**5.** You released an EBOM and the closure rebuild took 8 seconds
(usually sub-second). What might be going on?

> Either (a) very deep BOM tree (>5 levels of nesting) — closure
> rebuild is O(active edges) which compounds with depth, or (b) the
> rebuild ran inside a slow transaction with lots of contended locks.
> Check `_logger` output from `pg.ebom.closure._build_for_ebom`. If
> it's a one-time thing, ignore. If it's persistent, consider whether
> the EBOM should be split — a flatter tree is faster to maintain and
> easier to reason about for the manufacturing team. Bible R6 doesn't
> limit depth, but engineering convention is "no more than 4 levels
> below the top assembly."

---

## What this lesson does NOT cover

- The `pg.release` flow internals — covered in this lesson but the
  failure-mode detail is part of Bible §3 and Manufacturing
  Governance §8.
- The MCP `validate_ebom` / `simulate_release` / `bom_explode` tools
  — lesson 9.5.
- The Southbrook bridge wrapper around `action_apply` — lesson 9.6.
- ECO state machine that drives `apply` — lesson 4.1.
- Cut spec authoring against released BOMs — lesson 4.2.
- Native Odoo MRP BOM editor — covered by Odoo's own training.
