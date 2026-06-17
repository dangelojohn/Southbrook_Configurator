---
course: 8 — Estimating Deep Dive
chapter: 8.3
title: Pricing Deep Dive — Zones, Channels, Tradesperson Tiers, and the Resolution Dispatcher
duration: 50 minutes
audience: Estimator + Sales Manager. The estimator needs to know which price gets quoted and why; the sales manager needs to know how the 50%-off dealer math actually works (and where it doesn't), so they can explain it to a contractor on the phone without consulting code.
prereqs: Lesson 5.1 (Configurator basics), Lesson 5.2 (intro), Lesson 8.1 (architecture overview), Lesson 8.2 (Order Builder walkthrough)
custom_modules: southbrook_estimating, product_configurator
---

# Pricing Deep Dive — Zones, Channels, Tradesperson Tiers, and the Resolution Dispatcher

## Who this lesson is for

You're the estimator quoting a kitchen, OR the sales manager
explaining to a Tier 2 contractor why their cabinet number is what
it is. Either way, you need to know:
- What `channel` combines with what `tradesperson_tier` to drive
  which pricelist.
- How the dealer 50%-off math actually works — and the cases it
  doesn't apply.
- Per-line vs per-order discounts and when each is appropriate.
- How taxes flow through.
- Where `zone` enters pricing (spoiler: it doesn't, but it enters
  reporting and grouping).

This is the lesson that lets you answer "why is my number that
number?" in real time.

## Where this lives on the site

The pricelists themselves:

> **Sales → Configuration → Pricelists**

The partner side of the pricing equation:

> **Contacts → (pick partner) → Sales tab → Southbrook Channel**

The pricelist resolution at order time:

> **Southbrook Estimating → Order Builder → (any draft order) →
> Pricelist field** (auto-resolved from `partner_id.channel` by the
> onchange)

The refacing margin-target computation:

> **Sales → Configuration → Pricelists → Refacing (CTHS)**
> (`is_refacing_margin_target` on pricelist items, custom routine #2)

## What your screen shows

In the Pricelists list view you'll see six base pricelists plus three
tradesperson-tier sub-pricelists — nine records total:

1. **Retail (List Price)** — `pricelist_retail`. Base pricelist; no
   item records (uses the product's `list_price` directly).
2. **Dealer (-50%)** — `pricelist_dealer`. One global item:
   `compute_price='formula'`, `base='list_price'`, `price_discount=50`,
   `price_round=0.01`.
3. **Contractor (Tiered)** — `pricelist_tradesperson`. Base
   contractor pricelist with a single global "Cost x 1.05 floor"
   item: `compute_price='formula'`, `base='standard_price'`,
   `price_markup=5`, `price_round=0.01`.
4. **Contractor Tier 1 (-25%)** — `pricelist_tradesperson_tier_1`.
   One item: `base='pricelist'`,
   `base_pricelist_id=pricelist_tradesperson`, `price_discount=25`.
   So tier 1 = -25% off the cost+5% floor.
5. **Contractor Tier 2 (-30%)** — `pricelist_tradesperson_tier_2`.
   Same mechanic, `price_discount=30`.
6. **Contractor Tier 3 (-35%)** — `pricelist_tradesperson_tier_3`.
   Same mechanic, `price_discount=35`. This is the Q7 smoke-test
   target.
7. **Central KD (Knock-Down Components)** — `pricelist_kd`. One
   global item: `base='list_price'`, `price_discount=54` (so price
   = ~46% of retail).
8. **Big-Box Wholesale** — `pricelist_bigbox`. One global item:
   `compute_price='fixed'`, `fixed_price=98.00`, `price_round=0.01`.
   Every SKU is exactly CAD $98 regardless of list price. This is
   the contractual wholesale agreement.
9. **Refacing (CTHS)** — `pricelist_refacing`. Items intentionally
   empty in seed data; computed live by `_compute_refacing_price`
   targeting 35% margin off `standard_price`.

All 9 pricelists carry `currency_id = base.CAD` per the README
("Southbrook is Canadian — Vaughan/Concord, ON").

## Your daily flow

**1. Pricelist resolution at order create / customer switch.**

The chain (read top to bottom):

a. You set or change `partner_id` on a `sale.order`.

b. `_onchange_partner_id_southbrook_pricelist` fires (a Southbrook
   override; the standard Odoo onchange also fires).

c. It calls `order._resolve_channel_pricelist(partner)` — custom
   routine #3.

d. The dispatcher reads `partner.channel`. If channel is empty, falls
   back to `_FALLBACK_PRICELIST_XML_ID` = `pricelist_retail`.

e. If channel == "tradesperson", calls
   `_resolve_tradesperson_pricelist(partner)` which reads
   `partner.tradesperson_tier` and looks it up in the class-level
   `_TRADESPERSON_TIER_PRICELISTS` dict. If tier is missing, logs a
   `_logger.warning` (NOT an exception) and falls back to the base
   `pricelist_tradesperson` (cost+5% floor with no tier discount).

f. For any other channel, looks up the channel key in
   `_CHANNEL_PRICELISTS` dict and `env.ref`s the xml_id.

g. Returns the `product.pricelist` record and writes it to
   `order.pricelist_id`.

So the resolution is a pure table lookup: channel → xml_id, plus
the one sub-dispatcher for tradesperson tiers. No business rules
encoded in code — all the actual math lives in the pricelist item
records.

**2. How the math actually computes per line.**

When a line's `price_unit` is computed, Odoo's standard pricelist
mechanic runs:

- For **Retail**: no items, so `price_unit = product.list_price` (+
  any `price_extra` from variant attribute values).
- For **Dealer**: the global formula item kicks in: `price_unit =
  product.list_price * (1 - 0.50)` rounded to 0.01. Maple's
  `+10%` price_extra is included BEFORE the discount, so a $1000
  cabinet with Maple becomes $1100 list → $550 dealer.
- For **Contractor Tier 3**: the chained pricelist mechanic kicks
  in:
  1. Base pricelist (`pricelist_tradesperson`) computes
     `floor_price = product.standard_price * 1.05`.
  2. Tier 3 pricelist (`pricelist_tradesperson_tier_3`) does
     `base='pricelist', base_pricelist_id=pricelist_tradesperson,
     price_discount=35` — so `price_unit = floor_price * (1 - 0.35)`.
  3. Net effective: `price_unit = standard_price * 1.05 * 0.65 =
     standard_price * 0.6825`. So Tier 3 sells at 68.25% of cost
     (margin-erosion floor protection).
- For **KD**: `price_unit = list_price * (1 - 0.54) = 46% of list`.
- For **Big-Box**: `price_unit = 98.00` regardless of product.
- For **Refacing**: `_compute_refacing_price(product, ...)` returns
  `round(cost / (1 - 0.35), 2)` — so a $200-cost door sells at
  $307.69, hitting exactly 35% margin
  `(307.69 - 200) / 307.69 = 0.35`. The math: `price = cost / (1 -
  margin)` is the standard markup-from-margin formula.

**3. The Maple-box +10% interaction.**

Maple box carries `price_extra = +10%` on the
`product.attribute.value` (attached via the template attribute line).
The +10% lands BEFORE the channel multiplier, because Odoo's standard
pricelist flow computes `list_price + sum(price_extra)` as the input
to the formula. So:

- A retail $1000 SB-BASE-2DR with Maple = $1100.
- Same with Dealer (-50%) = $550.
- Same with Tier 3 contractor: depends on `standard_price`, NOT on
  list_price + price_extra — because Tier 3 uses `base='standard_price'`.

This is a frequent source of confusion: **the +10% Maple extra
applies to channels that use `base='list_price'` (Retail, Dealer, KD,
KD-derived) but NOT to channels using `base='standard_price'`
(Contractor, all tiers)**. For contractor pricing, the Maple cost
delta has to be baked into the variant's `standard_price` (cost) —
which it is, set seed-side. Confirm with the test fixtures in
`tests/test_pricelists_routing.py`.

**4. Per-line vs per-order discounts.**

You have three discount mechanisms:

- **Pricelist-level** — set automatically by the channel resolution.
  This is the "discount" everyone thinks of first. Applies to
  every line.
- **Line `discount` field** — standard Odoo per-line discount. Use
  this when you want to apply a one-off concession to a specific
  cabinet ("$50 off this corner because of the install issue").
  Stored on the order_line.
- **Per-order discount line** — manually add a service-product line
  with a negative price ("Goodwill discount", "Loyalty discount").
  This affects the order total but not individual line prices.

**Prefer the pricelist mechanism whenever the discount is policy-
driven** (channel, tier, volume break). Use the line `discount`
field for one-off concessions on a single cabinet. Use a discount
line for whole-order concessions ("First Order Discount, $200 off").
Audit clarity follows from this convention.

**5. How taxes flow.**

Standard Odoo flow — no Southbrook-custom tax routing:

- Product taxes (`product.taxes_id`) → flow to line tax via
  `_get_computed_taxes`.
- Partner fiscal position (`partner.property_account_position_id`)
  → maps tax rules (e.g. "tax-exempt for out-of-province" or
  "GST/HST swap"). Set on the partner; flows automatically to the
  order via `_onchange_partner_id`.
- Tax is computed on `price_subtotal` post-pricelist, post-discount.
  Channel pricelist mechanics run BEFORE tax calc.

For an Ontario customer, the standard cascade is HST 13% on the
`price_subtotal` of each line. For an out-of-province dealer with
exemption, the fiscal position maps it to zero-rated.

**6. Where `zone` enters pricing.**

It doesn't. `zone` is purely for grouping in the Order Builder and
the customer-facing PDF (Signature Spec Sheet groups by zone). No
zone-based pricelist rule exists. If you need to price an island
cabinet differently from a base run cabinet, that's a separate
catalog product (or a variant-level price_extra), NOT a zone field.

## Common mistakes + how to recover

**"I quoted a Tier 3 contractor and the price came out the same as
retail."**

Three suspects, in order of probability:

1. The partner's `channel` is blank or set to `retail` (default).
   Open the partner, set `channel = 'tradesperson'` AND
   `tradesperson_tier = '3'`, save. Then switch the order's
   `partner_id` away and back to trigger the onchange.
2. The partner has `channel = 'tradesperson'` but no
   `tradesperson_tier`. The `_resolve_tradesperson_pricelist` falls
   back to `pricelist_tradesperson` (the base, cost+5% floor with NO
   tier discount). The Odoo log shows the warning. Set the tier.
3. The order's `pricelist_id` was manually overridden to retail.
   Reset it to the contractor tier pricelist directly.

**"I quoted a Dealer customer for a Maple cabinet and the Dealer
discount didn't seem to apply to the Maple +10%."**

That's the correct math. Maple +10% applies BEFORE the Dealer
discount, so $1000 → $1100 → $550. If the customer expected $500
(50% off the un-extra'd $1000), explain that Maple is a +10% premium
that gets discounted alongside the base price, and Dealer pricing
doesn't waive that premium.

**"I quoted a Big-Box customer 22 SB-BASE-1DR cabinets, each $98.
Customer says it was $85 last month."**

Don't change prices unilaterally. Possible causes:
1. The `fixed_price` on `pricelist_bigbox_item_global` was edited
   between then and now (audit by `Settings → Technical → Audit
   Trail` if enabled).
2. The customer's prior order had a custom pricelist override on
   `pricelist_id` (open the prior order, check the field).
3. The customer remembers a non-invoice number (e.g. pallet-net,
   per-unit-net-of-shipping).

Escalate to sales management for the contractual answer. If
approved, apply the discount via the line `discount` field or a
separate discount line — DON'T edit the pricelist (every other
Big-Box order would see the change).

**"I built a refacing quote and the price seems too low."**

The refacing pricelist computes price from `standard_price` to hit
35% margin: `price = cost / (1 - 0.35) = cost * 1.538`. If the
product's `standard_price` is zero (common seed data issue), the
method falls back to `product.list_price`. Check the product's cost
in the inventory tab. The seed data may need backfilling for
refacing-eligible products.

**"I want to give a one-off 5% discount on a single line."**

Use the line's standard `discount` field (in the order_line; may
require enabling discounts under Sales → Configuration → Settings).
DO NOT create a new pricelist or override `price_unit` — both leave
no audit trail. The `discount` field is logged on the line and
flows to the QWeb reports without surgery.

## What the system is doing behind the scenes

The `_resolve_channel_pricelist` dispatcher is a pure dict-based
lookup. Its critical sources of truth:

- `_CHANNEL_PRICELISTS = {"retail": "...pricelist_retail", "dealer":
  "...pricelist_dealer", "kd": "...pricelist_kd", "bigbox":
  "...pricelist_bigbox", "refacing": "...pricelist_refacing"}`
- `_TRADESPERSON_TIER_PRICELISTS = {"1": "...tier_1", "2":
  "...tier_2", "3": "...tier_3"}`
- `_FALLBACK_PRICELIST_XML_ID = "...pricelist_retail"`

If you add a new channel:
1. Add the Selection value on `res.partner.channel`.
2. Create the pricelist record in `data/pricelists.xml`.
3. Add one row to `_CHANNEL_PRICELISTS`.

Three lines of code; the dispatcher does the rest. This is
intentional — the channel matrix is data, not logic, per Build Spec
§6.

The refacing margin-target method (custom routine #2):

```python
def _compute_refacing_price(self, product, quantity, partner=False, date=False):
    cost = product.standard_price or 0.0
    if cost <= 0.0:
        return product.list_price
    return round(cost / (1.0 - REFACING_TARGET_MARGIN), 2)
```

`REFACING_TARGET_MARGIN = 0.35`. The method is invoked by the
pricelist engine when the pricelist item has `compute_price='code'`
— though in the seed data the refacing pricelist's items are empty
(the method is reserved for when CTHS reactivates as a channel; the
template is in place).

For Odoo's standard pricelist chain (`base='pricelist'` items), the
engine recursively computes the parent pricelist's price first, then
applies the child pricelist's discount. So Tier 3 = (cost × 1.05) ×
(1 - 0.35). This is the contractor margin-erosion safeguard: even at
Tier 3 (deepest discount), the contractor still pays above raw cost
(cost × 0.6825 > cost when cost > 0; but Southbrook's margin
becomes negative because cost > selling price). Reality check on the
floor: contractors near Tier 3 are unprofitable unless they're
buying volume that justifies the loss-leader.

When channel switches, `_onchange_partner_id_southbrook_pricelist`
rewrites `pricelist_id`. The lines' `price_unit` recomputes via
Odoo's standard `_compute_price_unit` reading the new pricelist. No
Southbrook code in that path.

Per-line dollars in the spec sheet PDF come from `line.price_subtotal`
(post-pricelist, post-discount, pre-tax). Per-order total comes from
`order.amount_total` (post-tax). Both are standard Odoo fields.

## Quiz (5 questions, applied)

**1.** A Tier 2 contractor and a Tier 3 contractor both buy 10 SB-
BASE-2DR cabinets. Tier 2 quotes $7,500, Tier 3 quotes $6,800. The
contractors compare notes and ask "why such a small difference for
5% extra discount?" What's the math?

> Both prices are off the SAME cost+5% floor. Tier 2 = floor × 0.70;
> Tier 3 = floor × 0.65. The difference is 5% of the floor, not 5%
> of retail. Example: if floor = $1,071 per cabinet (cost $1,020 ×
> 1.05), Tier 2 = $750/cabinet × 10 = $7,500; Tier 3 = $696/cabinet
> × 10 = $6,963. The 5% discount delta is 5% of $1,071 = $54/cabinet,
> $540 across 10 cabinets — exactly the gap they observed (modulo
> rounding). The floor is what makes the deltas smaller than 5% of
> retail would suggest.

**2.** A dealer (50% off) is buying 8 Maple-box wall cabinets. The
list price per wall cabinet is $700; Maple adds +10%. What does each
line price out at, and what's the total?

> Per line: `list × (1 + 0.10) × (1 - 0.50) = 700 × 1.10 × 0.50 =
> $385`. Eight lines: $3,080 subtotal. The Maple +10% applies before
> the Dealer discount because both ride on the standard
> `list_price` base. Tax (HST 13% for an ON dealer with no fiscal
> position override): $400.40. Total: $3,480.40.

**3.** You change a customer from Retail to Tier 3 contractor on a
12-line order. Eleven lines reprice. One doesn't. Why?

> That one line has `price_unit` manually overridden (you or someone
> typed in the price field directly), breaking the pricelist link.
> Recovery options: (a) reset the line's `price_unit` to zero, then
> change quantity to force a recompute; (b) delete and re-add the
> line; (c) duplicate the order (it'll re-resolve cleanly from the
> partner). The line's `discount` field is independent — it survives
> repricing and is the safer way to apply per-line concessions.

**4.** A refacing customer's quote is showing $0 per door. What's
the most likely root cause?

> The product's `standard_price` is zero. The
> `_compute_refacing_price` method has the guard: if `cost <= 0.0`,
> return `product.list_price` — so if the product's list price is
> ALSO zero, the line shows $0. Set a real `standard_price` on the
> refacing product templates (Sales Cost field on the product form,
> Inventory tab). Seed-data oversight; common on cold-installed DBs.

**5.** A sales manager asks "can we add a 'Wholesale Tier 4 at -40%'
for our new pool-builder contractor relationship?" What do you do?

> Three coordinated changes (no code logic — just data):
> 1. `models/res_partner.py` — add `("4", "Tier 4 (-40%)")` to
>    `tradesperson_tier` selection.
> 2. `models/sale_order.py` — add `"4":
>    "southbrook_estimating.pricelist_tradesperson_tier_4"` to the
>    `_TRADESPERSON_TIER_PRICELISTS` dict.
> 3. `data/pricelists.xml` — add the new `pricelist_tradesperson_tier_4`
>    record + a `product.pricelist.item` with
>    `base='pricelist', base_pricelist_id=pricelist_tradesperson,
>    price_discount=40`.
> Verify with a smoke test: create a partner at the new tier, run a
> 9-line quote, confirm the total is ~40% below the cost+5% floor.

---

## What this lesson does NOT cover

- The Order Builder UI walkthrough — lesson 8.2.
- Where the pricing data ultimately ends up in MOs / cut specs —
  lesson 8.4.
- How the PDF reports format pricing — lesson 8.5.
- Versioning and quote-revision pricing carryover — lesson 8.6.
- Standard Odoo pricelist mechanics — Odoo's own documentation.
- The customer-facing one-page configurator pricing display — Phase
  2, not yet shipped.
- Volume-break pricing — supported by Odoo's standard
  `min_quantity` field on pricelist items but no Southbrook seeds
  ship today.
