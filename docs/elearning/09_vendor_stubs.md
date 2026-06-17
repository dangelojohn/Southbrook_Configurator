---
course: 9 — ProductGraph
chapter: 9.3
title: Vendor Stubs & Approved Vendor List
duration: 30 minutes
audience: Purchasing team + PLM engineer
prereqs: Lesson 9.1 (overview), basic understanding of Approved Vendor List (AVL) concept
custom_modules: product_graph_base (stubs), product_graph_vendor (AVL extension)
---

# Vendor Stubs & Approved Vendor List

## Who this lesson is for

You're either (a) a purchasing buyer who needs to know which vendors
the engineering team has *qualified* for a part before raising a PO,
or (b) a PLM engineer who's about to disqualify a vendor that's gone
EOL and needs to understand the workflow downstream of that decision.

There are two flavours of "vendor" in ProductGraph and the distinction
matters a lot:

- **Vendor stubs** — model-only records in `product_graph_base`. No UI,
  no menus, no procurement hooks. They reserve the schema path and are
  what the MCP sidecar's read tools query. (Decision D3, Phase 1.)
- **Vendor governance / AVL** — full lifecycle in
  `product_graph_vendor`. Adds qualification state machine, decision
  audit log, AVL display on every item, UI menus. (Phase 2.)

Both live in the **standalone ProductGraph platform**. The Southbrook
bridge addon does not extend them at all — Southbrook reads but does
not author vendor data.

## Where this lives on the site

If `product_graph_vendor` is installed (the AVL feature):

> **Manufacturing → ProductGraph → Vendors**
> **Manufacturing → ProductGraph → Vendor Parts**
> **Manufacturing → ProductGraph → Vendors → [pick vendor] →
> Qualification Log tab**

On any item, vendor data appears as:

> **Manufacturing → ProductGraph → Items → [pick item] → Approved
> Sources tab**

If only `product_graph_base` is installed, the models exist but no
menus do. You can still query them via the REST API and the MCP
sidecar's `list_vendors` / `vendor_for_item` tools (see
`mcp/src/product_graph_mcp/tools/vendor.py`).

## What your screen shows

**On the vendor form (`pg.vendor`):**

- **Vendor Name** (`name`) — required.
- **Vendor Code** (`code`) — `_code_unique` constraint. Stable
  short identifier.
- **Linked Partner** (`partner_id`) — many2one to `res.partner`,
  `ondelete='restrict'`. Optional in Phase 1, populated in Phase 2.
- **Qualification State** (`state`) — 5-state lifecycle:
  `unqualified → probationary → qualified → suspended → disqualified`.
  Tracking enabled. The valid forward transitions are locked in
  `VENDOR_TRANSITIONS` (see `pg_vendor.py` in
  `product_graph_vendor/models/`):
  ```
  unqualified  → probationary, disqualified
  probationary → qualified, suspended, disqualified
  qualified    → suspended, disqualified
  suspended    → qualified, disqualified
  disqualified → (terminal)
  ```
- **Qualified On** (`qualified_on`) — auto-stamped first time the
  vendor reaches `qualified`.
- **Qualified By** (`qualified_by_id`) — user who pulled the trigger.
- **Re-qualify By** (`qualification_expires_on`) — re-qualification
  cadence target. **Not enforced** in Phase 1 — flagged on the form
  only.
- **Approved** (`is_approved`) — denormalised convenience flag, kept in
  sync with `state == 'qualified'` via compute.
- **Qualification Log** (`qualification_ids`, one2many to
  `pg.vendor.qualification`) — append-only audit row per transition.
  Cannot be edited or deleted (write/unlink overrides raise UserError).
- **Cross-References** (`vendor_part_ids`, one2many to
  `pg.vendor.part`) — every item this vendor is approved to supply.

**On the vendor part form (`pg.vendor.part`):**

- **Engineering Item** (`item_id`) — many2one to `pg.item`,
  `ondelete='cascade'`.
- **Vendor** (`vendor_id`) — many2one to `pg.vendor`,
  `ondelete='restrict'`.
- **Vendor Part Number** (`vendor_part_number`) — what the vendor calls
  this part.
- **Preferred Source** (`is_preferred`) — boolean, at most one per item
  (enforced by `_check_one_preferred_per_item` constraint in
  `product_graph_vendor`).
- **Source Rank** (`rank`, default 10) — lower = preferred. Tie-breaker
  when no `is_preferred` is set.
- **Vendor Qualified** (`is_qualified`) — related, `store=True`.
  Tracks the parent vendor's approval status.
- **Minimum Order Quantity** (`moq`, default 1.0)
- **Unit Price Hint** (`unit_price_hint`)
- **Lead Time (days)** (`lead_time_days`)
- **Currency** (`currency_id`)
- **Notes** (`notes`) — free text
- **Unique** — `(item_id, vendor_id, vendor_part_number)` is unique.

**On any item (`pg.item`) with `product_graph_vendor` installed:**

- **Approved Sources** (`vendor_part_ids`) — one2many to vendor parts.
- **Primary Source** (`primary_vendor_part_id`) — computed: the
  preferred-flagged source, falling back to the lowest-rank qualified
  vendor-part.
- **Primary Vendor** (`primary_vendor_id`) — related, store=True.
- Smart button **Approved Sources** opens the list filtered to this
  item.

## Your daily flow

**1. Onboarding a new vendor (purchasing + engineering, joint).**

- **Manufacturing → ProductGraph → Vendors → Create.**
- Fill `name`, `code` (stable handle, e.g. `BLUM_AT`).
- Link `partner_id` to the matching `res.partner` so the accounting
  side stays connected.
- New vendor lands in `state='unqualified'`.
- Approver clicks **Move to Probationary** (`action_to_probationary`)
  once paperwork is in order. Engineer can now create vendor-parts.
- Approver clicks **Qualify** (`action_qualify`) once the parts pass
  PPAP / qualification testing. `qualified_on` and `qualified_by_id`
  are stamped automatically. A row appears in the Qualification Log.
  The `is_approved` compute flips to True.

**2. Adding an approved source on a part (engineer).**

- Open the `pg.item` for the part (e.g. a 110° hinge).
- Switch to **Approved Sources tab**.
- Click *Create*:
  - Pick the qualified `pg.vendor`.
  - Enter their `vendor_part_number` (e.g. `BLUM-71B3550`).
  - Set `moq`, `unit_price_hint`, `lead_time_days`.
  - Mark `is_preferred = True` if this is the go-to source.
- Save. The `(item, vendor, vendor_part_number)` triple must be unique.
- The item's `primary_vendor_part_id` recomputes immediately.

**3. EOL response (engineer + purchasing).**

When a vendor announces a part is end-of-life:

- Open the affected `pg.vendor.part`.
- DON'T delete it — that erases history. Set `active = False` instead.
- The item's `primary_vendor_part_id` recomputes; if there's another
  qualified-and-active source, it takes over. If not, the item now has
  no primary source — downstream consumers (PO suggestions, MRP
  re-orders) lose their default.
- If you want a hard signal that the *vendor itself* is gone:
  - Open the `pg.vendor`.
  - Click **Suspend** (`action_suspend`) for a recoverable issue, or
    **Disqualify** (`action_disqualify`) for permanent removal. Both
    require a comment (passed via context
    `default_qualification_comment`). The comment lands on the
    Qualification Log row.
  - Every related `pg.vendor.part` loses `is_qualified` (it's
    related-stored to `vendor_id.state` qualified).

**4. Audit query — "what items use Vendor X?"**

Open the vendor record. The **Cross-References** tab lists every
`pg.vendor.part` where `vendor_id = X`. Each row's `item_id` is the
engineering item. Two computed counts on the vendor make this fast:

- `vendor_part_count` — number of `pg.vendor.part` rows.
- `item_count` — DISTINCT `pg.items` (one part can have many
  vendor-parts, but item_count is the distinct count).

Or via the MCP sidecar: `vendor_for_item(part_number)` returns the
approved-sources list for one item; `list_vendors(state='qualified')`
returns the qualified list.

## Common mistakes + how to recover

**"I tried to disqualify a vendor without a comment and got a
ValidationError."**

Working as designed. `action_suspend` and `action_disqualify` both
require a comment (passed via context
`default_qualification_comment`). The reason is audit integrity — a
"why" must be recorded on the `pg.vendor.qualification` log row.
Suspension/disqualification without a justification is the single most
common audit finding.

**"I want to bring a vendor back from disqualified."**

You can't. `disqualified` is terminal in `VENDOR_TRANSITIONS`. The
intent is "this vendor is permanently removed from the AVL." If you
need them back, create a NEW `pg.vendor` record (different code, e.g.
`BLUM_AT_V2`) and qualify it from scratch. The historical disqualified
record stays for the audit trail.

**"I marked a vendor-part as preferred, but it's still not showing as
the item's primary."**

Two possibilities. (a) The vendor isn't `qualified` —
`primary_vendor_part_id` falls through `preferred` to
`qualified.sorted('rank')`; a non-qualified preferred candidate is
skipped. Check `vendor_id.state`. (b) Another vendor-part on the same
item is also `is_preferred=True`. The constraint
`_check_one_preferred_per_item` should reject the second one at write
time, but if you're seeing two it's a sign someone bypassed the
constraint with raw SQL — file a ticket.

**"I deleted a vendor record and now I have orphan vendor-parts."**

`pg.vendor.part.vendor_id` has `ondelete='restrict'`, so the delete
should have been rejected with a foreign key error. If it succeeded,
someone removed the constraint manually. The orphans will show as
`vendor_id = NULL` and will need cleanup. Don't replicate the trick.

**"I changed a vendor-part's `vendor_part_number` and the audit log
doesn't have a row."**

Correct — `pg.vendor.part` is NOT a `pg.audit.log`-tracked model.
Audit log rows fire only on `pg.item`, `pg.revision`, `pg.ebom`,
`pg.release`, and `pg.vendor` state changes. Mid-stream vendor-part
edits are tracked on the model's own `mail.thread` (chatter) but not in
the formal pg.audit.log. If this matters for your audit, file a ticket.

## What the system is doing behind the scenes

**Phase 1 is a deliberate stub.** Decision D3 in
`~/product_graph_v19/CLAUDE.md` reads:

> Model-only stubs in base: `pg.vendor` and `pg.vendor.part`. No UI, no
> procurement hooks, no menus. Reserves the schema path the same way
> `pg.asset` reserves the Digital Twin path.

This means: if you install only `product_graph_base`, the tables exist
and the REST API works, but you won't see vendors anywhere in the
Odoo UI. That's intentional — it lets the OpenBOM-mirror REST contract
ship Day 1 without dragging in the AVL workflow.

**`product_graph_vendor` (Phase 2) is what flips the switch.** It
inherits both `pg.vendor` and `pg.vendor.part` and adds:

- `mail.thread` and `mail.activity.mixin` on `pg.vendor` (so chatter
  works).
- The 5-state qualification machine + `VENDOR_TRANSITIONS` map.
- The `pg.vendor.qualification` append-only audit model.
- The smart-button menus, vendor-list views, vendor-form, AVL
  inherit views on `pg.item`.
- The `primary_vendor_part_id` compute on `pg.item`.

State transitions go through one helper, `_transition(to_state,
comment)`, which checks:

1. The acting user is in `group_pg_approver` (raises UserError otherwise).
2. The target state is in `VENDOR_TRANSITIONS[current_state]`.
3. Stamps `qualified_on` / `qualified_by_id` on first qualify.
4. Creates a `pg.vendor.qualification` row.
5. Writes a `pg.audit.log` row via `env['pg.audit.log'].sudo()._log(...)`
   with `action='state_change'`, from/to, notes (Bible R4 — all
   transitions emit audit + chatter).
6. Posts a chatter message on the vendor.

The append-only `pg.vendor.qualification` model is enforced at the ORM
level:

```python
def write(self, vals):
    raise UserError(_("Vendor qualification records are append-only and
                      cannot be edited."))
def unlink(self):
    raise UserError(_("Vendor qualification records are append-only and
                      cannot be deleted."))
```

What's **NOT here**:
- No `purchase.order` integration. The `primary_vendor_part_id` is
  computed and exposed, but no PO is auto-created from it. That's the
  planned `product_graph_procurement` companion's job (in-progress,
  see addons list).
- No RFQ workflow — that's `product_graph_rfq`.
- No re-qualification cadence enforcement — `qualification_expires_on`
  is a flag on the form, not a cron action.

## Quiz (5 questions, applied)

**1.** Purchasing tells you the 110° concealed hinge from Blum has been
discontinued and Blum's replacement (`71B3650`) costs 12% more. What's
the workflow?

> Don't delete the old `pg.vendor.part` — that erases history. Set the
> existing row's `active=False` (records why: "EOL per Blum notice
> 2026-06"). Create a NEW `pg.vendor.part` for the same item with
> `vendor_part_number='71B3650'`, the new `unit_price_hint`, and mark
> `is_preferred=True` if it's now the go-to. The item's
> `primary_vendor_part_id` recomputes to the new row. The
> `vendor_id.state` is still `qualified` — Blum as a vendor is fine;
> only one of their parts went EOL.

**2.** An approver tries to disqualify a vendor by going to the form
and changing the `state` selection directly to `disqualified` instead
of clicking the action button. Does it work?

> No — and that's by design. The state field is tracked but the
> `_transition` helper is where the guards live (approver-group check,
> transition validity, audit log write, chatter). Writing directly to
> `state` will fail the audit/chatter expectation and likely the
> `tracking=True` write itself will go through but produce a broken
> record (qualification log missing, audit log missing). Always use
> the action buttons (`action_suspend`, `action_disqualify`, etc.).

**3.** The MCP sidecar's `vendor_for_item` tool is called with
`part_number = 'PG-PRT-0042'`. The item has 3 vendor-parts: one
preferred and qualified (rank 10), one not-preferred but qualified
(rank 20), one not-preferred and unqualified (rank 5). Which one is
the "primary"?

> The preferred-and-qualified rank-10 one. The compute checks
> `preferred` first (and finds it), so it returns that row regardless
> of rank. The unqualified rank-5 row is filtered out
> (`primary_vendor_part_id` only considers `vendor_part_ids.filtered('active')`
> and preferred-or-qualified). The qualified rank-20 row would have
> won only if there were no preferred candidate.

**4.** You're standing up a new dev DB and install only
`product_graph_base`. A REST API consumer reports
`vendor_part_count` is always 0. Why?

> The base module ships `pg.vendor.part` as a stub but does NOT add the
> `vendor_part_ids` o2m relationship to `pg.item` — that's added by the
> `product_graph_vendor` Phase 2 inherit (`pg_item.py` in the vendor
> module). Without that addon, items have no inverse relation to
> their vendor-parts; the field literally doesn't exist on the model.
> Install `product_graph_vendor` to get the AVL view on items.

**5.** A regulator asks for the full qualification history of vendor
"Blum Austria GmbH." Where do you point them?

> Open the `pg.vendor` record. The **Qualification Log** tab
> (`qualification_ids`, one2many to `pg.vendor.qualification`) is the
> append-only audit trail: every transition with `(decision,
> decided_by_id, decided_on, comment)`. Plus the
> `pg.audit.log` rows filtered to `res_model='pg.vendor'` and
> `res_id=<this vendor's id>` for the same events as seen by the
> broader ProductGraph audit. Both are write-blocked and
> unlink-blocked at the ORM level, so the regulator's tamper concern is
> answered by design.

---

## What this lesson does NOT cover

- Property templates (engineering specs) — lesson 9.2.
- Authoring an EBOM that uses the primary vendor for cost rollup —
  lesson 9.4.
- The Procurement and RFQ companion addons (`product_graph_procurement`,
  `product_graph_rfq`) — Phase 2, out of scope here.
- ECO workflow that swaps vendors as a side effect — lesson 4.1.
- Native Odoo `product.supplierinfo` — different table, different
  authority. ProductGraph's AVL is the engineering authority; the
  Odoo `product.supplierinfo` is the purchasing-pricelist authority.
  They are NOT auto-synced in Phase 1.
