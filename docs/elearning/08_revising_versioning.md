---
course: 8 — Estimating Deep Dive
chapter: 8.6
title: Revising + Versioning — Quote Revisions, the parent_order_id Chain, and Customer Rejection Handling
duration: 45 minutes
audience: Estimator. The customer is going to change their mind. This lesson is how to handle "I want to change the island" without losing the audit trail of the original quote, and how to walk the chain backwards when the customer asks "what was version 1 again?"
prereqs: Lesson 5.2, Lesson 8.1 (architecture), Lesson 8.2 (Order Builder walkthrough), Lesson 8.4 (handoff — to understand what's lost between versions if you Confirm too early)
custom_modules: southbrook_estimating
---

# Revising + Versioning — Quote Revisions, the parent_order_id Chain, and Customer Rejection Handling

## Who this lesson is for

You're the estimator. The customer just emailed: "We've reconsidered
the island — can you do a version with a 5-foot island instead of
6-foot, and lose the pantry?" Without versioning, you'd edit the
quote and lose the original. With versioning, you click Duplicate
as Draft, edit the new version, and both stay traceable.

This lesson is the NF6 Image Floor pattern — how to chain v1 → v2 →
v3 → … without breaking the audit trail, what gets cloned and what
gets reset, and how to handle the customer-rejection case (they
walk away after v2).

## Where this lives on the site

The Duplicate-as-Draft entry point:

> **(any order form) Stat Buttons → Duplicate as Draft**

The button is injected by xpath (3) in `views/sale_order_views.xml`
into the `button_box`, calls `action_duplicate_as_draft`, and is
gated by `groups="sales_team.group_sale_salesman"`.

The version field is invisible to most users — it lives behind
`groups="base.group_no_one"` (developer mode only) but renders the
Parent Order link near the customer block when present.

The ancestry chain walker (used by the customer portal timeline):

> `sale.order._southbrook_history_chain(max_depth=20)` — Python
> method, no menu surface.

## What your screen shows

When you click Duplicate as Draft on order `SO00123` (v1):

1. The form refreshes onto a new order — `SO00124` (v2).
2. The order's name carries " (v2)" suffix in the breadcrumb (set
   by the action's `name` field).
3. The state shows `draft`.
4. A "Parent Order" link appears near the customer block — readonly,
   pointing back at `SO00123`. (Only visible when `parent_order_id`
   is non-empty.)
5. All order lines copied from v1 — same products, same zones, same
   quantities, same prices. (Pricing is re-resolved at line level
   using the current pricelist — see "Common mistakes" if a customer
   was switched between versions.)
6. The chatter shows "Created from SO00123" implicit via Odoo's
   standard copy log.
7. The `version` field reads 2 (visible only in developer mode by
   default).

When you walk back via the chain helper (typically from the customer
portal timeline):

```python
order._southbrook_history_chain(max_depth=20)
```

Returns a list of dicts, newest first. Each dict carries: `id`,
`name`, `version`, `state`, `amount_total`, `date_order`,
`is_current`. The customer portal renders this as a timeline of
"v3 (current) — $58,200 — confirmed" / "v2 — $54,100 — superseded
draft" / "v1 — $61,500 — superseded draft".

## Your daily flow

**1. Customer requests a revision.**

The customer comes back. Most common reasons:
- Dimensions changed ("we measured again, the wall is 8 feet not
  7 feet — add a cabinet").
- Materials changed ("the husband wants Maple boxes throughout").
- Scope changed ("drop the island, we don't have the floor space").
- Pricing pushback ("can you do the contractor series on the
  perimeter and signature only on the island?").
- Design rethink ("we want a wider sink base + smaller pantry").

If the revision is **trivial** (one cabinet's finish swapped),
edit the line in place and re-print. Don't version. The version
chain is for substantive revisions — anything where the customer
might later ask "what was the original price?"

If the revision is **substantive**, duplicate. The bar: "if I were
asked in 3 months what we changed, would I want a record?"

**2. Duplicate as Draft.**

Open the most recent version (likely v1, the original):

> Stat buttons → **Duplicate as Draft**

The button calls `action_duplicate_as_draft`:

```python
new_order = self.copy({
    "parent_order_id": self.id,
    "version": self.version + 1,
    "state": "draft",
})
return {"type": "ir.actions.act_window", ...}
```

— so:
- `state` is forced to `draft` (even if the original was `sent` or
  `sale`).
- `parent_order_id` points to the original.
- `version` is incremented (v1 → v2, v2 → v3, etc.).
- All order_lines copy via Odoo's standard `_inherit_copy`
  mechanism. Configurator session references on lines copy too —
  but see Common Mistakes for the variant-sharing trap.

The form auto-navigates to the new draft.

**3. Edit the new version.**

Walk the changes:
- Delete lines the customer dropped.
- Add new lines (with Configure as needed).
- Edit existing lines (zone, qty, attribute reconfiguration).
- Verify the pricelist still resolves correctly (if the customer
  switched channel, the new pricelist applies; the original v1
  retains its frozen pricelist).

**4. Send the new version.**

Generate the new Signature Spec Sheet PDF, send to the customer.
The PDF shows the new version number (`o.version` is rendered next
to the Reference) so the customer can tell v2 from v1 at a glance.

**5. Loop back as needed.**

If the customer comes back AGAIN, duplicate the most recent version
(v2 → v3). The chain extends. Image Floor's observed pattern is
v3 as the high-water mark — beyond that, the conversation has
fundamentally drifted and someone (usually the customer's spouse)
needs to be involved.

**6. Confirmation — what happens to the chain.**

When the customer signs off on v3 and you Confirm:
- v3's state moves to `sale`. MOs spawn from v3's lines.
- v1 and v2 remain in `draft` (or `cancel` if you canceled them
  during the conversation — see step 7).
- `southbrook.order.analytics.capture(v3)` writes one analytics row
  pointing to v3.
- v1's and v2's analytics rows (if any) are independent — they
  weren't confirmed, they weren't captured. The analytics is per-
  confirmed-version, not per-chain.

The history chain stays walkable forever. The customer portal can
render the full v1 → v2 → v3 timeline. Internal audit can trace
every revision.

**7. Customer rejection — when the chain doesn't get confirmed.**

Customer says "we're going with another vendor" after v2. What you
do depends on policy:
- **Best practice**: leave v1 and v2 in `draft`. Both are
  searchable in the Order Builder list with the standard state
  filter. Their chain is preserved for post-mortem analysis ("what
  did we quote?").
- **Tidy policy**: cancel v2. State moves to `cancel`. Still
  searchable, but excluded from the default `state in ('draft',
  'sent')` Order Builder filter. The chain is still walkable
  because `parent_order_id` is a Many2one not a domain filter.
- **Aggressive cleanup**: cancel v1 too. Same logic — chain
  walkable, not visible in default list.

Don't delete. Deletion is destructive; the audit trail vanishes.
Even in the rejection case, the data is worth keeping for the
analytics model (channel rejection patterns, dropout-version
distribution).

**8. Walking the chain.**

When the customer comes back 6 months later asking "what was v2's
price again?":

```python
# Find the most recent version on this customer's account
latest = self.env["sale.order"].search(
    [("partner_id", "=", customer.id), ("parent_order_id", "!=", False)],
    order="version desc",
    limit=1,
)
# Walk back
chain = latest._southbrook_history_chain(max_depth=20)
for entry in chain:
    print(f"v{entry['version']}: {entry['name']} — "
          f"${entry['amount_total']} ({entry['state']})")
```

The chain comes back newest first. The `is_current` flag marks the
node corresponding to `latest`.

## Common mistakes + how to recover

**"I duplicated v1 → v2, edited a line on v2, and v1's line also
changed."**

`copy()` deep-clones the SO lines, so the order_line records are
distinct. But `product.product` variants are SHARED by ID. If you
edited the variant's attribute values via the product form (not
via the Configure button on the line), both v1 and v2 see the
change — they reference the same variant.

Recovery: re-Configure the affected line on v2 to materialise a
NEW variant. The new variant inherits v2's line; v1's line still
points to the original variant (now altered) — which is an audit
problem you'll need to handle case-by-case.

Future protection: only edit attribute values through the Configure
wizard, never through the product.product form.

**"I duplicated and the customer was switched between versions —
the new version's prices look weird."**

If you change the customer on v2, the `_onchange_partner_id_southbrook_pricelist`
fires and rewrites `pricelist_id`. Lines reprice. v1's pricing is
NOT affected — it's frozen on v1's order, which still references
the original customer.

If you wanted v2 to carry the same customer + pricing as v1, don't
change the customer. The customer link copies along with the
duplicate.

**"I duplicated v3 → v4 from v3, but the chain shows v4 → v3 → v1,
skipping v2."**

The duplicate command sets `parent_order_id = self.id` where `self`
is the source. If you duplicated from v3, parent is v3. The chain
walker reads `parent_order_id` recursively — so v4 → v3 → v3's
parent. If v3's parent was v1 (because you duplicated v1 → v3 by
mistake, skipping v2), the chain reflects that.

Fix: open v3, set its `parent_order_id` to v2 explicitly (developer
mode, group_no_one access). The walker re-runs cleanly. Then audit
why v3 was duplicated from v1 — likely the rep opened the wrong
order to duplicate.

**"I confirmed v1, customer wants v2, I duplicated v1 → v2 → and
v1's MOs are still in Manufacturing."**

Right — Confirm spawns MOs. Cancelling v1 (via state → cancel)
will cancel the MOs upstream (the standard Odoo flow). If those
MOs have already started production, you can't cancel them — they
need to finish, and v2 effectively becomes a separate order. The
customer pays for both.

Best practice: don't Confirm v1 if the customer is in negotiation.
Confirm only when the customer has signed off. The `southbrook_submitted_date`
milestone (set by the portal "Request a Price" action) is the
"customer has submitted for pricing" timestamp; Confirm is the
"customer has signed and we're going to build it" commitment.

**"The chain walker returned 20 entries and then stopped."**

`max_depth=20` is a defensive limit against pathological cycles.
If your actual chain is deeper than 20, something is wrong —
inspect for a cycle (e.g. v3.parent = v2 AND v2.parent = v3, which
shouldn't happen but could after a manual edit). The `seen` set
guard inside the walker prevents infinite loops; the depth limit
is the secondary safety net. Production never sees deeper than 5;
20 is comfortable.

**"I duplicated and the new version has the ILLUSTRATIVE SEED
banner."**

The banner is gated on `context.get('seed_mode_canonical', False)`
— if the context is missing the flag, the banner shows. The
duplicate action's act_window descriptor doesn't carry context
forward by default. If you were operating under
`seed_mode_canonical=True` context, that context drops when the
duplicate opens. This is a UI quirk, not a data issue. Refresh the
page or open via the menu to restore proper context.

## What the system is doing behind the scenes

`action_duplicate_as_draft` uses Odoo's standard `copy()` mechanism
with three overrides:
- `parent_order_id = self.id` — the back-link.
- `version = self.version + 1` — auto-increment.
- `state = 'draft'` — force-reset so a confirmed source still
  produces a draft target.

Odoo's standard `copy()` handles deep-clone of `order_line`,
including the variant references. Variants are NOT cloned — they're
shared (this is the trap explained above; the safety mechanism is
to use the Configure button on the duplicate to materialise fresh
variants).

The `_southbrook_history_chain` method is a simple iterative walker:

```python
def _southbrook_history_chain(self, max_depth=20):
    chain = []
    seen = set()
    cur = self
    while cur and cur.id not in seen and len(chain) < max_depth:
        seen.add(cur.id)
        chain.append({...})
        cur = cur.parent_order_id
    return chain
```

The `seen` set is the cycle guard; the depth limit is the secondary
guard. Both are belt-and-suspenders.

The customer portal renders this list as a vertical timeline. The
node with `is_current=True` is highlighted. Each node carries
`amount_total` and `state` so the customer can compare versions
at a glance.

When a version is confirmed, `southbrook.order.analytics.capture`
writes a row for THAT version only. The analytics model has no
notion of "chain head" — each confirmed version is its own
analytics row. If you query analytics for a customer, you'll see
ONE row per confirmed version (typically just one row total because
typically only the final version gets confirmed; but if the customer
confirms v1, then comes back and confirms v3 instead, you'd have
two rows for that customer).

The `parent_order_id` field uses `ondelete='set null'` — if you
delete a parent order, the child's link becomes null (the chain
breaks at that point). This is by design — preserves the child as
a standalone record even if the parent vanishes. But it means you
should NEVER delete a parent if you care about chain integrity;
cancel instead.

## Quiz (5 questions, applied)

**1.** A customer is on v3 of a quote. v1 was $61,500, v2 was
$54,100, v3 is $58,200. The customer rejects v3 and says "let me
think." Two weeks later they come back wanting to confirm v2's
spec. What do you do?

> Don't confirm v2 directly — its pricing is two weeks old and may
> not reflect current cost. Instead: Duplicate v2 as Draft → creates
> v4 with parent_order_id=v2. v4 inherits v2's lines but re-resolves
> the pricelist at current rates (which may have changed if cost or
> channel agreements moved). Verify v4's total matches what the
> customer was quoted on v2 (allowing for any cost drift); if not,
> explain the delta to the customer. Then send v4 for signature.
> The chain reads v4 → v2 → v1.

**2.** You duplicated v1 → v2, but on v1's product form (not via
the configurator) you changed the Finish from Walnut to Maple to
respond to a quick customer request. v2 was already saved. What
happened?

> Both v1's line and v2's line reference the SAME variant — you
> just changed a shared variant from Walnut to Maple. Now both
> orders' Signature Spec Sheets show Maple — including v1, which
> the customer signed off on as Walnut. Audit problem.
> Recovery: re-Configure v1's line to materialise a fresh Walnut
> variant (so v1 owns its own variant going forward). Re-Configure
> v2's line if Maple was actually intended for v2; otherwise also
> revert to Walnut. Future: do not edit attribute values via the
> product form — always via the Configure wizard.

**3.** A customer's chain shows v1 → v2 → v3 in the portal. You
expected v4 (you just duplicated). What's broken?

> Either (a) the duplicate failed silently — check the chatter for
> the new order's create entry; (b) you didn't end up on v4's form
> after duplicate (the action's `target: current` should land you
> there, but if your browser blocked the navigation, the new draft
> exists but you're still looking at v3); (c) `_southbrook_history_chain`
> on v3 walks v3 → v2 → v1, not v3 → v4 (forward) — the chain is
> backward-only by design. Open the Order Builder list, filter by
> customer + version desc — v4 will be there if it was created.

**4.** Customer confirms v2 (not v3). v3 still exists in draft. Six
months later, can the customer's portal show v3 in the timeline?

> Yes. `_southbrook_history_chain` is parent-only, walks back from
> the current node. But if you call it from v3, you get v3 → v2 →
> v1. If you call from v2 (the confirmed one), you get v2 → v1
> only. Whether v3 appears on the customer portal depends on which
> node the portal renders FROM. If the portal renders the confirmed
> order's chain, v3 isn't included. If the portal renders all
> orders for the customer with a parent link to the chain root, v3
> can be visible. Today's customer portal renders the most recent
> order's chain — so v3 (the most recent) → v2 → v1. v2 is shown
> as the confirmed one in the timeline.

**5.** You want to add a "Why this version" note field that
captures the customer's reason for each revision. Where do you
add it, and what's the audit consideration?

> Add `southbrook_revision_reason` (Char or Text) to `sale.order`
> in `models/sale_order.py`. Add a t-set or a small field in the
> view (XPath after the version field). On Duplicate, the field
> resets to blank (Odoo's standard `copy()` defaults).
> Audit consideration: the field is per-order, not per-line. If
> the revision spans many line changes, the rep writes a summary
> ("customer dropped island, requested Maple boxes throughout").
> The chatter is the source of truth for line-level audit; this
> field is the headline. Don't make it `readonly=False after
> creation` — that allows post-hoc rewrites and undermines audit.

---

## What this lesson does NOT cover

- The Order Builder UI walkthrough — lesson 8.2.
- Pricing mechanics across versions — lesson 8.3 (each version
  applies its current pricelist; pricing is NOT frozen per version
  until Confirm).
- The Quote → MO handoff — lesson 8.4 (relevant only when a
  version gets confirmed).
- Report generation per version — lesson 8.5 (each version
  generates its own Signature Spec Sheet with its version number).
- General Odoo `copy()` mechanics — Odoo's own ORM docs.
- Customer portal UX — Course 6 (Customer Touchpoints).
- The Hermes platform's recommendation flow for revisions — see
  the Hermes spec.
