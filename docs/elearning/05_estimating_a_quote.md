---
course: 5 — Estimating + Configurator
chapter: 5.2
title: Estimating — Building a Quote from a Kitchen Design
duration: 35 minutes
audience: Estimator. You have a customer's kitchen design in hand (Prodboard export, hand sketch, or a designer's spec sheet) and need to turn it into a priced, BoM-backed quote in Odoo.
prereqs: Lesson 5.1 (Configurator basics), basic Odoo Sales navigation.
custom_modules: southbrook_estimating, product_configurator_sale, product_configurator_mrp
---

# Estimating — Building a Quote from a Kitchen Design

## Who this lesson is for

You're the estimator who turns a customer's design into a quote. The
design lands on your desk in one of three forms: a Prodboard export, a
designer's hand sketch, or a back-of-envelope cabinet list. Your job is
to drive it through the Order Builder one cabinet at a time, watching
the configurator price each line against the customer's resolved
channel, and produce a Signature Spec Sheet PDF the customer signs off
on. By the end of this lesson you'll have built a 9-line smoke-test
order — the canonical Phase-1 gate per Q7.

## Where this lives on the site

The Order Builder lives in two places — same action, two entry points so
you can find it however you remember it:

> **Southbrook Estimating → Order Builder** (top-level app drawer entry)

> **Sales → Orders → Order Builder** (legacy Build-Spec §2.2 placement)

Both open the same action (`action_order_builder`) — a filtered
`sale.order` list scoped to `state in ('draft', 'sent')`. Click an order
to drop into the form; click "Create" to start a new one.

For the customer-facing PDF preview / send:

> **(from inside the order form)** Print → Signature Spec Sheet

## What your screen shows

The Order Builder form is the standard `sale.order` form with Southbrook
xpath additions. Top to bottom:

- **Illustrative-seed banner** (`alert alert-warning`) — visible only
  during demo / Phase-1 gate review (gated by `seed_mode_canonical`
  context). If you see this banner in production, your demo data leaked
  into a real DB — escalate.
- **Stat-button: Duplicate as Draft** (`action_duplicate_as_draft`,
  field `parent_order_id` + `version`) — the NF6 Image Floor pattern.
  Iterative-design quotes (customer comes back with edits 3 times) chain
  v1 → v2 → v3, each new version a new draft order linked back.
- **Customer block**: `partner_id`, `pricelist_id` — the customer
  drives `_resolve_channel_pricelist` which auto-fills the pricelist
  based on `partner.channel` (and `tradesperson_tier` for the
  contractor channel — NF5).
- **Parent-order link** (`parent_order_id`, readonly) — appears only
  when this order was duplicated from another.
- **Version** (`version`, default 1) — auto-incremented by Duplicate as
  Draft.
- **Order lines** — grouped by `zone` field on `sale.order.line`,
  default expanded. Zones are: Base Run / Wall / Tall / Island /
  Accessory / Other. Each zone shows a sum row of `price_subtotal`
  ("Zone Subtotal").
- **Per-line columns** in the embedded list: zone, zone_label (visible
  only when zone=other), product_id, name, product_uom_qty,
  price_unit, price_subtotal. Plus the standard Configure button
  added by `product_configurator_sale`.
- **State pipeline** (top-right): the standard Odoo `state` field on
  `sale.order` — `draft` → `sent` → `sale` → `done`, plus `cancel`
  off-pipeline. Southbrook does NOT add custom states; the
  "Draft → Estimating → Approval → Confirmed → In Production" pipeline
  from the brief maps onto Odoo's standard state values plus the
  `southbrook_submitted_date` Datetime field (set by the portal
  "Request a Price" action — G14/G17).
- **Notebook tabs**: Order Lines (standard); 3D Kitchen Preview
  (`kitchen_3d_preview` page, Track 1 — `widget="kitchen_viewport"`);
  Other Info; Customer Signature.

## Your daily flow

**1. Receive the design.**

The design lands as one of:

- A Prodboard JSON export emailed by the customer / dealer.
- A designer's PDF with a cabinet schedule (e.g. "16 base, 8 wall, 2
  tall, 1 corner — Maple box, Elegance series, Walnut Stain finish").
- A scribbled cabinet list on a service-ticket form.

Read it first. Confirm what's there: how many cabinets, what series,
what box material, any custom-finish requests, any accessories. If
anything's ambiguous, call the designer before opening Odoo —
spending 45 minutes building a quote and then re-doing it because the
customer wanted soft-close throughout is the most common pain point
of the job.

**2. Open the Order Builder and create a new order.**

> **Southbrook Estimating → Order Builder → Create**

- **Customer** (`partner_id`) — pick the customer. If they don't exist
  yet, create them inline; before saving make sure their **Southbrook
  Channel** (`channel`) is set correctly:
  - `retail` — walk-in, no discount
  - `dealer` — −50% (Richwood, Image Floor, etc.)
  - `tradesperson` — Contractor Pricing, requires `tradesperson_tier`
    (1 = −25%, 2 = −30%, 3 = −35%)
  - `kd` — Central KD (component-only, ≈46% of retail)
  - `bigbox` — fixed $98/SKU wholesale
  - `refacing` — CTHS per-SF pricing
- **Pricelist** auto-resolves via `_resolve_channel_pricelist` (custom
  routine #3 — `models/sale_order.py`). You can override manually if
  the customer is mid-conversion (e.g. retail walk-in negotiating
  dealer terms).
- Save.

**3. Per cabinet (the loop).**

For each cabinet in the design:

- Click **Add a line** on Order Lines.
- Pick a product: type "SB-" and pick from the 12 locked Q8 templates
  plus the ~40 catalog-expansion templates. The 12 anchors:
  `SB-WALL-1DR`, `SB-WALL-2DR`, `SB-BASE-1DR`, `SB-BASE-2DR`,
  `SB-DRAWER`, `SB-SINK-BASE`, `SB-TALL-PANTRY`, `SB-TALL-OVEN`,
  `SB-CORNER`, `SB-VANITY`, `SB-ACCESSORY`, `SB-WORKTOP`.
- Set **Zone** for the line: Base Run / Wall / Tall / Island /
  Accessory / Other. If Other, fill **Zone Label** (free-text — e.g.
  "Laundry", "Mudroom", "Bar"). Lines auto-group by zone in the form.
- Click the row's **Configure** button (from `product_configurator_sale`).
  The wizard opens. Walk the 11-attribute flow from lesson 5.1.
- When the wizard's done, the line's `price_unit` shows the resolved
  price for that variant against the customer's pricelist.
- Repeat. A typical mid-range kitchen has 18–25 lines.

**4. Hardware and install lines.**

Cabinets are configured; you still need:

- **Hardware lines** — most hardware is resolved automatically per
  carcass via the `southbrook.hardware.catalog.resolve()` service
  (lesson 5.3). Manual hardware lines you add yourself: an
  upgraded handle / pull, a customer-supplied appliance pull, a
  specialty hinge. Add as a regular order line with the
  Marathon-cataloged `product.product`.
- **Install / labour lines** — service products (e.g. `INST-DAY`,
  `DELIVERY-GTA`). Not configurable; just add the SKU and quantity.
- **Filler / end-panel lines** — accessory family on
  `SB-ACCESSORY` with `accessory_type` sub-attribute (end_panel /
  filler / cornice / pelmet / plinth).

**5. Verify the BoM preview.**

Open the **BoM Preview** tab (when wired through Phase 3 — today, look
at the line-level computed fields):

- `sb_panel_count` — total carcass panels on the line
- `sb_door_count` — door / drawer fronts on the line
- `sb_width_mm` — derived width

If a line shows `sb_panel_count = 0`, the variant lacks attribute
values *and* the line name doesn't parse. Most likely you skipped the
configurator on that line — open the Configure button and walk the
wizard.

**6. Switch the customer (Q7 smoke-test step).**

The locked Phase-1 smoke test:

- Customer set to **Demo Tradesperson (Tier 3)** → all lines reprice at
  −35% (against cost+5% floor). Maple-box cabinets carry the +10% /
  +2 weeks delta.
- Switch to a Retail walk-in customer → all lines reprice to list
  price *without* reconfiguring any line.
- Switch back to Tier 3 → −35% restored.

That's the channel-pricelist resolver doing its job. If a line *doesn't*
reprice, its `pricelist_id` is hard-set instead of inherited from the
order — escalate.

**7. Generate the Signature Spec Sheet.**

> **Print → Signature Spec Sheet** (`signature_spec_sheet.xml`)

The PDF report (custom routine #6, QWeb template) groups lines by zone,
shows pricing, totals, and is styled to match the Signature Series
book. This is the customer-signed document.

Sister reports:

- **Shop Copy** (`shop_copy.xml`) — printed for the shop floor after
  confirmation; bound to `mrp.production` not `sale.order`.
- **Door Order** (`door_order.xml`) — per-SO door schedule for the
  door supplier.

**8. Customer sign-off and confirm.**

- Send the Spec Sheet PDF (Send by Email button → state `sent`).
- Customer signs, returns the signed PDF.
- Open the order, click **Confirm** → state `sale`. This triggers
  `action_confirm` → captures `southbrook.order.analytics` (NF1 AI data
  spine), and if MRP is wired, creates the `mrp.production` records.
- State will move to `done` once the MOs ship and invoicing closes.

The full state machine: **`draft` → `sent` → `sale` → `done`** (plus
`cancel` off-pipeline). These are the verbatim Odoo `sale.order.state`
values. The `southbrook_submitted_date` Datetime field is set when the
customer (or you on their behalf) clicks "Request a Price" through the
portal — that's the "submitted for pricing" milestone the customer-
facing timeline shows.

## Common mistakes + how to recover

**"I built 18 lines, switched the customer from a Tier 3 contractor to
a retail walk-in, and the lines didn't reprice."**

The pricelist on the order was overridden manually. Open the order's
**Pricelist** field — if it shows "Retail (List Price)" but the lines
are still at Tier 3 numbers, the lines' `price_unit` was manually set,
breaking the pricelist link. Recovery: click each line's price field
and press the recompute icon (or update qty and back). For 18 lines,
faster to right-click an empty area and "Update Prices" if the action
is available, or duplicate the order and re-configure cleanly.

**"I clicked Confirm and the order moved to `sale` state, but no MO
was created."**

The `mrp.bom` rollup is empty because no line had configured variants
with a BoM relation. Verify: open the order, look at a line's BoM
preview — if it's empty, you skipped the Configure button on that line.
Recovery: cancel the order (state `cancel`), reset to draft, walk
every line through the configurator, confirm again. Alternative for one
or two unconfigured lines: open the line, click Configure, set picks,
save — the BoM rollup re-evaluates on save.

**"I picked Demo Tradesperson Tier 3 as the customer but the price is
the same as retail."**

Two suspects: (1) the partner has `channel = 'tradesperson'` but no
`tradesperson_tier` set — `_resolve_tradesperson_pricelist` falls back
to the base contractor pricelist (cost+5% floor, no tier discount, logs
a soft warning); (2) the partner's `channel` field is blank/retail.
Open the partner record, set `channel = 'tradesperson'` and
`tradesperson_tier = '3'`, save. The order won't auto-reprice — switch
customer to someone else and back to trigger the onchange.

**"The customer wants Maple boxes throughout but two of the cabinets are
Contractor series."**

Rule 2 (Box Material → Series) blocks Maple on Contractor. Three
options: (a) upsell those two cabinets to Contemporary or Elegance (the
cheapest series that allows Maple — Contemporary is the natural step
up); (b) accept White Melamine on the two Contractor cabinets and Maple
on the rest (the customer may not notice — Contractor's painted
thermofoil finish hides the box edges); (c) tell the customer Maple
boxes aren't compatible with Contractor and let them decide. **Do not**
try to override the rule manually — there's no UI for that, and you'd
break the BoM math.

**"I duplicated an order as draft, edited a few lines, and the original
order's lines also changed."**

That should not happen — `copy()` deep-clones the lines. If it did, one
of the lines was actually a configured variant whose
`product_template_attribute_value_ids` you edited on the variant record
(not on the order line). The variant is shared across both orders.
Recovery: re-configure the affected lines on the duplicate so a new
variant is materialised. Future protection: only edit attribute values
through the Configure wizard, never through the product.product form.

**"The Signature Spec Sheet PDF doesn't render — I get a 500 error."**

The `reports/signature_spec_sheet.xml` template depends on
`reports/southbrook_report_styles.xml` loading first (per the
`__manifest__.py` `data` ordering — don't alphabetise). If a contributor
reordered the list, the spec sheet breaks. Check
`southbrook_estimating/__manifest__.py` — `southbrook_report_styles.xml`
must precede `signature_spec_sheet.xml`. If correct, look at the Odoo
log for the QWeb error message; typically a missing field reference on
the order or the partner.

## What the system is doing behind the scenes

When you create an order and pick a customer, two onchange hooks fire:

- `_onchange_partner_id_southbrook_pricelist` (`models/sale_order.py`) —
  reads `partner.channel` (and `tradesperson_tier`) and writes
  `pricelist_id` to the resolved pricelist record. Lookup tables:
  `_CHANNEL_PRICELISTS` (5 simple channels) and
  `_TRADESPERSON_TIER_PRICELISTS` (3 tiers). Fallback:
  `pricelist_retail`.
- Standard Odoo `_onchange_partner_id` — copies billing / shipping
  addresses, fiscal position.

When you click Configure on a line, `product_configurator_sale` launches
the OCA wizard, creates / reuses a `product.config.session` (state
`draft`), and walks the user through `value_ids` picks. On finish, a
`product.product` variant is materialised (or reused — `create_variant='dynamic'`)
and bound to the line.

When you click **Confirm**, the override in `models/sale_order.py`
`action_confirm` runs:

1. `super().action_confirm()` — standard Odoo: state → `sale`,
   creates `mrp.production` records via `sale_mrp` (the bridge addon
   we explicitly depend on — NF25).
2. `southbrook.order.analytics.capture(order)` — creates an
   analytics row capturing channel, predominant series, dealer (if
   channel = `dealer`), cabinet/panel/door counts. Idempotent — safe
   to reconfirm.

Three QWeb reports are registered:

- `signature_spec_sheet.xml` — customer-bound PDF, the document
  the customer signs (custom routine #6 partial).
- `shop_copy.xml` — `mrp.production`-bound shop-floor companion.
- `door_order.xml` — per-SO door schedule for the door supplier.

The `Duplicate as Draft` action chains orders via `parent_order_id` and
auto-increments `version`. The `_southbrook_history_chain(max_depth=20)`
helper walks the chain newest-first for the customer-portal timeline.

## Quiz (5 questions, applied)

**1.** You receive a Prodboard export with 9 cabinets — the canonical
Q7 smoke-test list. The customer is a Tier 3 contractor (Richwood). You
build the order, all 9 lines configured, prices look right. You then
switch the customer to a Retail walk-in. What do you expect to see, and
what does it confirm?

> Every line repricing upward to list price *without* needing to
> reconfigure anything (no Configure-button clicks required). This
> confirms `_resolve_channel_pricelist` is wiring the pricelist
> correctly via the `_onchange_partner_id_southbrook_pricelist` hook,
> and that the `pricelist_id` on the order is propagating to each line's
> `price_unit` recompute. If a line doesn't reprice, its `price_unit`
> was manually overridden — recovery is to reset that line's price.

**2.** A customer changes their mind mid-quote — twice. You end up with
v1, v2, v3 of the same kitchen. Where does the v3 record carry its
ancestry, and how do you walk it back?

> `parent_order_id` (Many2one back to v2 on v3, v1 on v2). Version is
> auto-incremented by `action_duplicate_as_draft` (3 on v3, 2 on v2,
> 1 on v1). Use the helper `_southbrook_history_chain(max_depth=20)` to
> walk newest-first; the v3 form also shows a Parent Order link near
> the partner block. The original v1 is kept in `draft` / `cancel`
> state as the historical record.

**3.** You confirm an order with 14 cabinet lines. No MOs appear in
Manufacturing. What's the most likely root cause?

> One or more cabinets weren't configured — the line was added but the
> Configure wizard never ran on it, so the variant has no
> attribute values and no BoM lineage. The `mrp.production` records
> are created by `sale_mrp` based on the line's variant + BoM; an
> unconfigured variant has nothing for `sale_mrp` to act on.
> Verification: open each line, check the BoM preview / `sb_panel_count`
> — zero = unconfigured. Reset to draft, configure, reconfirm.

**4.** You hit Print → Signature Spec Sheet and get a 500. The Odoo log
shows `'name' field not found on res.partner`. What's the actual cause,
and the fix?

> The QWeb template is referencing a partner field that doesn't exist
> on the current `res.partner` record — possibly an extension field
> from another module the report assumed was installed. Open
> `reports/signature_spec_sheet.xml`, grep for `partner_id.<fieldname>`,
> cross-reference with `res.partner` fields. Most likely the addon that
> defines the missing field needs to be installed, or the template
> needs a guard `t-if="order.partner_id.<field>"` to skip when absent.
> Escalate to your admin — this is a report bug, not a data bug.

**5.** A Big-Box customer (channel = `bigbox`) asks for a quote on 22
SB-BASE-1DR cabinets. You build the order, every line shows $98.00 in
`price_unit`. Total is $2,156. The customer says "that's wrong, you
quoted me $85/cabinet last month." Where do you look?

> The Big-Box pricelist (`pricelist_bigbox`) sets a fixed $98.00 per
> SKU per Q1. If the customer was quoted $85 last month, either (a)
> a previous custom pricelist override was used on that order (look
> at the old order's `pricelist_id` field); (b) the pricelist item
> was edited between then and now (`pricelist_bigbox_item_global`'s
> `fixed_price` value); (c) the customer is misremembering, or
> referring to net-of-pallet pricing not invoice pricing. Don't lower
> the price unilaterally — escalate to sales management for the
> contractual answer, then if approved, override the line's
> `price_unit` and add a discount note.

## What this lesson does NOT cover

- The configurator vocabulary itself (attributes / exclusions /
  construction rules) — lesson 5.1.
- Hardware catalog and per-carcass hardware resolution — lesson 5.3.
- The Configurator UX v2 surface (chip selectors, live preview, OWL
  component) — lesson 5.4.
- The customer-facing one-page configurator (Phase 2 — not yet
  shipped).
- The 3D Kitchen Preview tab — Phase 3 surface, behaviour subject to
  change.
- General Odoo Sales workflow (sending quotes, invoicing,
  delivery) — Odoo's own training site.
- MRP / production planning — Course 2 (Production Planning).
