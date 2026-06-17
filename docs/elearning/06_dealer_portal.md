---
course: 6 — Customer Touchpoints
chapter: 6.2
title: Customer Service — Dealer Portal + Channel Pricing
duration: 30 minutes
audience: Customer Service rep who handles dealer-account questions (different rep, usually, from the one who handles end-customer calls)
prereqs: Lesson 6.1 (customer portal), basic res.partner / sale.order navigation
custom_modules: southbrook_dealer_portal, southbrook_estimating, southbrook_customer_portal
---

# Customer Service — Dealer Portal + Channel Pricing

## Who this lesson is for

You're the Customer Service rep who picks up the phone when **a dealer**
calls — Image Floor, Amazing Window, Pro Finish, Richwood, or any
Tradesperson / KD / Big-Box partner. Dealers are not end customers.
They re-sell Southbrook kitchens to *their* customers, they get a
channel discount, and they have a different portal at a different URL
with different security rules. This lesson is the practical reality of
supporting that channel without leaking another dealer's order data and
without misquoting the dealer pricelist.

## Where this lives on the site

The dealer portal lives at:

> **southbrookcabinetry.space → Sign in (as a dealer-channel user) → My Account**

Direct dealer routes (only resolve for partners with
`res.partner.channel = 'dealer'`):

> **> /my/dealer/orders** — list of the dealer's own sale orders
> **> /my/dealer/production-package/<pkg_id>/kd** — KD flat-pack JSON download (Central Kitchens channel)
> **> /my/dealer/production-package/<pkg_id>/installation-pdf** — installation reference PDF (drawings + cut list + hardware schedule + KD holes)

Your back-office view of the dealer's data:

> **Sales → Orders → Orders** — filter by `partner_id` = the dealer
> **Contacts → [open the dealer] → Sales & Purchase tab → Southbrook Channel**

The Southbrook Channel group on the partner form shows the two fields
that drive everything:

- `channel` (`res.partner.channel`) — selection of `retail / dealer /
  tradesperson / kd / bigbox / refacing`.
- `tradesperson_tier` (`res.partner.tradesperson_tier`) — only meaningful
  when `channel == 'tradesperson'`; selection of `1 / 2 / 3` for the
  Tier 1 (−25%) / Tier 2 (−30%) / Tier 3 (−35%) discount cascade.

## What your screen shows

The dealer portal's order list (`/my/dealer/orders`) shows the dealer's
own sale orders only. Columns rendered by
`southbrook_dealer_portal.portal_dealer_orders_list`:

- **Order** — `name` on `sale.order` (e.g. `S00123`).
- **Date** — `date_order`.
- **State** — Odoo native `state` (`draft / sent / sale / done / cancel`).
- **Total (Dealer)** — `amount_total`, already computed against the
  dealer's pricelist. This is the column the dealer cares about.

How "the dealer's pricelist" gets resolved:

- Each dealer partner has `channel='dealer'`. Resolution happens at
  `sale.order` creation through the custom routine `_resolve_channel_
  pricelist` (the dispatcher referenced in `res_partner.py` comments)
  which maps the channel onto `pricelist_dealer` from
  `southbrook_estimating/data/pricelists.xml`. That pricelist is a
  flat `price_discount = 50` global item — every line is list price
  × 0.50 automatically.
- The retail / list column appears as a strikethrough on the spec
  sheet so the dealer can show *their* end customer the
  "before/after" pricing. The dealer sees both sides: their cost
  (the −50% dealer total) and the retail equivalent. Their own
  customer sees only the retail side.
- A **Tradesperson (Contractor)** partner is similar but uses
  `pricelist_tradesperson` and an extra tier multiplier
  (Tier 1 / 2 / 3 → 25 / 30 / 35% off the cost+5% floor). Read
  `tradesperson_tier` on the partner; if blank when channel is
  `tradesperson`, the onchange defaults it to Tier 3 (the entry tier).

What the dealer **cannot see** (and what the controller enforces):

- **Other dealers' orders.** The list controller filters with
  `[("partner_id", "=", partner.id)]` where `partner` is
  `request.env.user.partner_id` — i.e. the logged-in dealer's own
  partner record. Per-dealer scoping is done at the **controller
  layer**: a dealer can never widen the search to include another
  dealer's sale orders, even by URL probing, because the controller
  ignores any partner argument from the request and always uses the
  authenticated user's partner.
- **The dealer-portal route at all** if they're not on the dealer
  channel. Every dealer route calls `_require_dealer()` first, which
  reads `partner.channel` and raises `AccessError(...)` if it isn't
  `'dealer'`. So a retail customer who has the URL can't load the
  dealer pages.
- **Internal cost.** The dealer sees their cost (the −50% line) and
  the retail-equivalent. They do NOT see Southbrook's own COGS, the
  margin, or the cost-plus floor on the Tradesperson channel.

What you should also know:

- The **production-package** routes (KD export + installation PDF)
  rely on the dealer naming a `pkg_id` — Phase-1 scope accepts any
  package the dealer can name (the manifest documents this as a
  scoping gap to be tightened "when Module 4 hooks the production
  package to MO + the MO ↔ SO link is mrp standard"). Until that
  tightening lands, a curious dealer with another dealer's package ID
  could theoretically download it. Watch for this in support tickets —
  if a dealer asks about a package they shouldn't know exists,
  escalate to IT.

## Your daily flow

**1. Start of shift (5 min):**

- Open *Contacts*, filter by **Southbrook Channel = Dealer**. That's
  your active dealer roster.
- Skim *Sales → Orders*, filter by partner-is-in-dealer-roster, sort
  by `date_order desc`. The dealers calling today are usually asking
  about an order placed in the last week.

**2. Per dealer call (the loop):**

When a dealer calls:

- Identify the dealer's `res.partner`. Their portal user account is
  linked via `res.users.partner_id = partner.id`; the partner is the
  authoritative key.
- Check `channel` and `tradesperson_tier` on the partner form. If
  they're calling about pricing, those two fields are the conversation:
  - `channel='dealer'` → flat −50% off retail, no tier.
  - `channel='tradesperson'`, `tradesperson_tier='3'` → Tier 3 (−35%)
    off the cost+5% floor.
  - `channel='kd'` → Central KD pricing (≈46% of retail, component
    pricing only — no assembly).
  - `channel='bigbox'` → fixed wholesale.
  - `channel='refacing'` → per-SF margin-target pricing (35% target).
- Open the order they're calling about in *Sales → Orders*. Read
  `amount_total` — that's their price. If they say "I see $X on my
  portal but you're quoting me $Y", `amount_total` is the
  authoritative number — the portal renders that value, not a
  cached one.

**3. Adding a new dealer (10 min):**

When the sales team signs a new dealer:

- Create the `res.partner` record (Contacts → Create).
- Set **Southbrook Channel** (`channel`) to `dealer`.
- For a Tradesperson, also set `tradesperson_tier` (defaults to `3`
  via the `_onchange_channel_default_tier` onchange when channel
  switches to `tradesperson`).
- *Grant Portal Access* via the native partner-form action — that
  triggers the standard portal invite email so the dealer can set
  their own password. They land on `/my/dealer/orders` after first
  login (if `channel == 'dealer'`; otherwise the dealer-only routes
  refuse them).
- Tell them their URL is
  `southbrookcabinetry.space/my/dealer/orders`. Bookmark it.

**4. Dealer-to-customer attribution (when applicable):**

When an end customer registers via a dealer's referral, the sales team
attaches the customer's `res.partner` as a contact of the dealer's
partner record (Odoo's native `parent_id` link). Phase 1 does NOT have
a first-class "attributed-by-dealer" model — attribution is captured
on the sale order's salesperson + the customer's `parent_id`. **TBD
in this addon:** there's no first-class `referred_by_dealer_id`
field; if a sales-process change requires a stronger link, raise it
to the product owner — don't fake one with a tag.

**5. End of shift (5 min):**

- Any new dealer you onboarded — confirm their portal login worked
  (check `res.users.login_date` on their user record). If never set,
  the welcome email probably went to spam; re-issue.

## Common mistakes + how to recover

**"The dealer says the price changed between yesterday and today."**

Three real causes, in order of likelihood:

1. The retail list price on `product.template.list_price` changed
   upstream — the dealer pricelist is `price_discount = 50` of list,
   so if list moved, the dealer total moved. Diagnose by opening the
   product template + checking the chatter for a recent edit.
2. The dealer's `channel` was changed on their partner record. Rare,
   but happens during channel-migration projects. Check the partner
   form's chatter for a `channel` change.
3. They're looking at an old quote from a different sale order. Ask
   for the order code (`name` on `sale.order`).

Do NOT promise the old price without checking — `amount_total` on the
order is the authoritative number.

**"The dealer says they can see another dealer's order on their
portal."**

P0 — escalate to IT. The controller filter
(`partner_id = partner.id`, using the authenticated user's partner)
should make this impossible. If it actually happened, either (a) the
dealer is logged in as the wrong `res.users` (multi-tab session
mix-up), or (b) the controller has been bypassed. Capture the screen
state on the call. Do not write to either dealer's records while
investigating.

**"The Tradesperson dealer is angry because their portal isn't loading
— it says 'This area is for Southbrook dealers only.'"**

Their `channel` is `tradesperson`, not `dealer`. The
`_require_dealer()` helper specifically checks
`partner.channel == 'dealer'` and rejects everything else. Per the
Phase-1 scope, **the dealer portal routes are only for the `dealer`
channel** — Tradespersons see their orders through the normal
`/my/orders` portal route (Odoo native), not `/my/dealer/orders`.
This is a real product gap; tell the Tradesperson "the wholesale
portal is dealer-only for now, here's your direct order link" and
log a ticket so the gap is visible.

**"The dealer downloaded the KD JSON and it's empty / missing panels."**

`export_kd_envelope()` raises `UserError` when `cutlist_id` is unset
on the production package. If the JSON downloaded fine but is
missing entries, the cutlist is probably empty too — the production
package was created without panels generated. Escalate to the
production planner (the MO probably hasn't been built yet).

**"The dealer says the installation PDF is missing the elevation
drawings — pages 2 isn't there."**

The PDF includes elevation views only when the freecad-bridge
sidecar returns SVGs (env vars `FREECAD_BRIDGE_URL` and
`FREECAD_BRIDGE_SECRET` must be set). When the bridge is unreachable
or the secret isn't configured, the PDF gracefully degrades to
text-only: cover page → cut list → hardware schedule → optional KD
holes. This isn't a bug; it's the documented degradation. Escalate
to IT to check the bridge if elevations are needed.

## What the system is doing behind the scenes

Each click on a dealer-portal route runs through this gauntlet:

1. **Authentication.** `auth="user"` on the route forces Odoo's standard
   portal login.
2. **Channel gate.** `_require_dealer()` reads
   `request.env.user.partner_id.channel` and raises `AccessError` if it
   isn't exactly `'dealer'`. So a `tradesperson` or `retail` user gets
   refused even with a valid session.
3. **Per-dealer scoping.** The orders search uses
   `[("partner_id", "=", partner.id)]` where `partner` is the
   authenticated user's partner — never a URL argument. A dealer cannot
   widen their view to another dealer's orders. The **record rule that
   enforces this at the ORM layer** is named
   `rule_portal_dealer_production_package` in
   `southbrook_dealer_portal/security/dealer_portal_security.xml`
   (Model: `sb.production.package`, Groups: `base.group_portal`).
   Note: that rule's `domain_force` is currently `[]` (Phase-1
   compromise — see the rule's XML comments); the controller filter is
   doing the real scoping work for sale orders until Module 4 wires
   MO ↔ SO ↔ package linkage and the rule can be tightened. **For sale
   orders specifically, scoping is controller-layer, not ORM-rule
   layer, in Phase 1.**
4. **Pricelist resolution.** `_resolve_channel_pricelist` runs at order
   creation, reads `partner.channel`, and maps to the right
   `product.pricelist` (`pricelist_dealer`, `pricelist_tradesperson`,
   etc.). The order line totals are recomputed against the resolved
   pricelist — switching a partner's `channel` on an existing order
   re-prices on next save.

The `channel` field is the keystone of the whole pricing model. Don't
write to it directly on a partner who's mid-flight on an active
quote — change the partner's channel mid-quote and every line
recomputes. Always create a fresh quote instead.

## Quiz (5 questions, applied)

**1.** A new Image Floor dealer sales rep calls and asks "how do I see
my orders". You go to add them. What two fields on their
`res.partner` do you set, in what order, and what triggers the
welcome email?

> Set `channel = 'dealer'` on the partner form's Sales & Purchase tab
> (Southbrook Channel group). `tradesperson_tier` stays blank — it's
> only meaningful when `channel = 'tradesperson'`. Save the partner,
> then click the partner-form's **Grant Portal Access** action (native
> Odoo). That triggers the standard portal invite email; the dealer
> sets their own password and lands on /my/dealer/orders.

**2.** A Tradesperson partner (Richwood, Tier 3) calls and says
"why am I seeing −35% off when last week I saw −25% off?" Where do
you check first?

> Open Richwood's partner form. Check `tradesperson_tier`. If it's
> `'3'`, Tier 3 is −35% off the cost+5% floor — that's correct as of
> today. The −25% they remember is Tier 1; either their tier was
> changed (check the partner chatter for a tier-change entry) or they
> were misremembering. Don't promise them −25% unless the partner
> record actually carries Tier 1.

**3.** A dealer calls and says "I'm seeing Wilson Smith's kitchen
order on my portal. I'm not Wilson Smith." What do you do, in what
order?

> P0 security incident. (1) Don't write to anything — capture screen
> state, ask the dealer to read the order number off-screen. (2) Open
> a ticket to IT with the dealer's partner ID, the order code, and
> the timestamp. (3) Ask the dealer to log out + close all browser
> tabs (multi-tab session mix-up is the most common false positive).
> The controller filter `partner_id = request.env.user.partner_id.id`
> should make true cross-dealer leakage impossible — if it actually
> happened, that filter or auth is bypassed and IT needs to look
> immediately.

**4.** A dealer downloads the installation PDF and complains "page 2
is missing — there's no elevation drawing." What do you check?

> The elevation page is rendered only when the freecad-bridge
> sidecar returns SVGs. Check the Odoo container logs for
> `elevation: bridge unreachable` or `elevation: bridge secret unset,
> skipping` — if you see either, the bridge needs IT attention. The
> PDF is documented to gracefully degrade to text-only (cover → cut
> list → hardware → optional KD holes). Tell the dealer the bridge
> is being checked, don't promise a fix on the call.

**5.** A dealer's `amount_total` on their portal reads $4,200; they
swear yesterday it was $3,800. Where do you look first?

> Open the order, then the order's chatter — any `product.template`
> price changes or `partner.channel` changes upstream are tracked.
> Most likely cause is a list-price change on one of the line items
> (dealer pricelist is `price_discount = 50` of list — if list moved,
> dealer total moved). Second likeliest is the partner's `channel`
> being changed (rare, but check). Do NOT honour the $3,800 without
> finding the change — `amount_total` on the order is authoritative.

---

## What this lesson does NOT cover

- The end-customer portal (different URL, different ACL, different
  audience) → lesson 6.1.
- How the channel pricelists are seeded
  (`southbrook_estimating/data/pricelists.xml`, the six pricelists
  per Q1 of the build brief) → estimating track, lesson 5.2 +
  `Southbrook_Excel_to_Odoo_Mapping.md` §3.4.
- Fabio's customer-communication recommendations (when the system
  flags a quiet dealer the way it flags a quiet customer) →
  lesson 6.3.
- The KD JSON envelope schema, the Central Kitchens consumer
  cabling, the FreeCAD elevation render pipeline — those are
  production / engineering topics, not CS topics.
- Native Odoo Sales workflow (quotation states, invoicing) → Odoo's
  own native eLearning track.
