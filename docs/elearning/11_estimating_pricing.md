---
course: 11 — Creating a New Product End-to-End
chapter: 11.6
title: Setting Up Pricing for the New Product
duration: 35 minutes
audience: Estimator + Sales Manager assigning the new SKU's base price, zone overrides, channel multipliers, tax mapping, and signing off on the first test quote
prereqs: Lesson 11.5 (configurator wired and publishable), Lesson 5.2 (estimating a quote — Order Builder flow, channel resolution, signature spec sheet), Lesson 5.1 (configurator basics — how `price_extra` attaches to attribute values), Lesson 8 (pricing fundamentals across the six channels — retail, dealer, tradesperson, KD, big-box, refacing)
custom_modules: southbrook_estimating, product_configurator_sale
---

# Setting Up Pricing for the New Product

## Who this lesson is for

You're the estimator who'll be quoting this SKU starting next week,
working with the sales manager who has the authority to set the
base price. The configurator (lesson 11.5) is wired and the BoM
(lesson 11.4) is complete — both feed pricing, but neither *sets*
it. Today you fill in the price master row, decide whether the SKU
needs zone-specific overrides, confirm the six channel pricelists
apply correctly, map the right tax, and run a sign-off quote.

This lesson does **not** re-cover the Order Builder UI, the
signature spec sheet, the channel resolution mechanics, or the
dealer 50%-off math. That's lesson 5.2 and Course 8. This lesson is
the **per-product pricing setup** for a brand-new SKU.

## Where this lives on the site

> **Sales → Configurable Products → Configurable Templates →
> \<your new template\>**

The base price lives on the template (`list_price` field on
`product.template`). Channel pricing derives from this through the
six pricelists. Per-attribute-value price extras live on:

> **Sales → Configuration → Attributes → \<attribute\> →
> Values → \<value\>**

…with the `price_extra` field on
`product.template.attribute.value`. And the pricelist data is at:

> **Sales → Configuration → Pricelists**

The six pricelists are seeded by
`addons/southbrook_estimating/data/pricelists.xml` — *do not edit
them per-product*. You may add per-product price-item overrides
within an existing pricelist if the SKU needs it.

For the test quote:

> **Southbrook Estimating → Order Builder**

For the tax mapping (rare per-product change; usually inherited):

> **Accounting → Configuration → Taxes** (admin) and
> **the template form's** *Accounting* **tab** for per-product
> assignment.

## What your screen shows

The `product.template` form, *General Information* + *Sales* tabs:

- **Sales Price** (`list_price`) — the base retail price. This is
  the **anchor**; every channel pricelist multiplies or
  fixed-offsets from this. Get this wrong and every quote is
  wrong.
- **Cost** (`standard_price`) — the rolled-up cost from the BoM
  components and operation costs. Computed by Odoo from the BoM if
  cost_method is right; check via *Update Cost from BoM* if needed.
- **Sales** tab → **Customer Taxes** (`taxes_id`) — the
  sale-side tax. For Southbrook this is almost always *GST 5%*
  (Canadian context); the default fiscal-position handling on
  `res.partner` re-maps for tax-exempt or out-of-province
  customers.

The `product.template.attribute.value` join form:

- **Attribute** + **Value** — the binding pair.
- **Extra Price** (`price_extra`) — additive to `list_price` when
  this value is selected on a configuration session. Examples:
  *Maple box +$45*, *Soft-close hinge +$8 per door*, *Glass-front
  door +$95*.
- **Lead Time Extra** (`lead_time_extra` on
  `product.attribute.value` itself, not the join) — additive
  days to the cabinet's `mrp` lead time. *Maple box +14 days*.

The six channel pricelists
(`southbrook_estimating/data/pricelists.xml`):

| Pricelist | Mechanic | Set per-product? |
|---|---|---|
| Retail | base — your `list_price` | No |
| Dealer | `list_price * 0.50` | No (pure data rule) |
| Tradesperson | Cost × 1.05 → tiered discount 25/30/35% | No (resolved by `tradesperson_tier`) |
| KD | ~46% of retail | No |
| Big-Box | fixed $65/$98 | Maybe — per-product fixed overrides allowed |
| Refacing | per-SF, 35% margin target | Yes — refacing-margin-target rule |

The `product.pricelist.item` form (only relevant if you need a
per-product override):

- **Applies on**: pick *Product*; reference your template.
- **Computation**: *Fixed Price* (for big-box overrides) or
  *Formula* (for refacing-margin-target).
- **Refacing margin target**
  (`is_refacing_margin_target` on `product.pricelist.item`,
  see `southbrook_estimating/models/product_pricelist.py:19`) —
  tick this on for refacing-pricelist items; the
  `_compute_refacing_price()` method computes price live to hit
  the `REFACING_TARGET_MARGIN = 0.35` constant.

## Your daily flow

**1. Cost roll-up sanity check (5 min):**

- Open the new `product.template`. Confirm `standard_price` is
  populated from the BoM (lesson 11.4 should have left this
  computed; if it's still 0.00, click *Update Cost from BoM* — or
  on the BoM form, *Update* button).
- If cost looks wildly off, the BoM is wrong or the component
  costs are stale. Stop here and escalate to the BoM author.

**2. Set `list_price` with the sales manager (10 min):**

- Compute the target retail using the sales manager's standard
  margin (typically *cost × 2.5 to 3.0* for cabinets — varies by
  family). The sales manager owns this number, not you.
- The sales manager and you agree on the `list_price` together.
  Write the number in the conception folder's `scope.md`
  alongside the cost so future estimators can see the margin
  intent.
- Set `list_price` on the template. Save.

**3. Add per-attribute-value price extras (10 min):**

For each attribute value that costs more than the base
configuration:

- **Sales → Configuration → Attributes → \<attribute\> →
  Values → \<value\>**.
- Find the join row matching your template (the join is
  `product.template.attribute.value`, not the raw
  `product.attribute.value`).
- Set **Extra Price** (`price_extra`). Examples from existing
  cabinets:
  - *Maple box* → `+10%` of base — codify as percentage in
    `price_extra` is **not** native Odoo; what you do is set a
    flat dollar amount equal to 10% of `list_price` at the
    current price. This means re-checking when `list_price`
    changes — file a ticket if your environment needs
    percentage-based extras (not in v1).
  - *Soft-close hinge upgrade* → flat dollar per door.
  - *Glass-front door* → flat dollar substitution.
- Save each value.

**4. Confirm channel multipliers resolve (5 min):**

The six channel pricelists are data — they apply to every
template without per-template configuration. Test:

- **Southbrook Estimating → Order Builder → New**.
- Set customer = *Demo Tradesperson Tier 3* (the locked Q7 smoke-
  test partner — `res.partner.channel = tradesperson`,
  `tradesperson_tier = 3` → −35%).
- Add a line for the new SKU.
- Confirm the line price is `list_price * 0.65` (retail minus
  35%). If yes, channel resolution works. If no, the partner is
  on the wrong channel or the pricelist seed didn't load.
- Swap customer to a *Demo Dealer* (`channel = dealer`). Confirm
  line price is `list_price * 0.50`.
- Swap customer to a *Demo Retail* (`channel = retail`). Confirm
  line price is `list_price`.

**5. Zone overrides (3 min — usually skipped):**

The Order Builder supports multi-zone orders
(`sale.order.line.zone` field — Q21: `base_run / wall / tall /
island / accessory / other`). Zone overrides are **not** common
for a single SKU — zones are an order-level concept, not a
product-level one. A new SKU generally enters every zone it can
naturally fit (a base SKU enters `base_run` and `island`, a wall
SKU enters `wall`, an accessory enters `accessory`).

If your new SKU is genuinely zone-restricted (e.g. *island
peninsula end-cap only fits in `island`*), document that in the
conception folder's `scope.md` and tell the estimating team
verbally. There is no enforcement field on the SKU — the estimator
chooses the zone manually.

**6. Tax mapping (2 min — usually default):**

- *Sales* tab → **Customer Taxes**.
- Default is the company default (*GST 5%* for Southbrook
  Canada). Almost always correct.
- The fiscal position on `res.partner` re-maps for tax-exempt
  (e.g. status-Indian customers) or out-of-province orders.
- **You do not need to touch this** unless the SKU has special
  tax treatment (e.g. tax-exempt parts — extremely rare for
  cabinetry).

**7. Big-box per-product override (2 min — usually skipped):**

If the new SKU will be sold through the Big-Box channel:

- **Sales → Configuration → Pricelists → Big-Box Wholesale**.
- *Items* tab → *Add*.
- **Applies on**: *Product*; reference your template.
- **Computation**: *Fixed Price*.
- **Fixed Price**: $65 cost / $98 retail (per the channel
  economics).

Most new SKUs do **not** sell through Big-Box (which carries a
fixed small catalog). Skip this step unless the conception folder
explicitly green-lit Big-Box distribution.

**8. Refacing per-product override (2 min — usually skipped):**

If the new SKU will be sold through the Refacing channel:

- **Sales → Configuration → Pricelists → Refacing (CTHS)**.
- *Items* tab → *Add*.
- **Applies on**: *Product*; reference your template.
- **Refacing margin target** (`is_refacing_margin_target`) → On.
- The `_compute_refacing_price()` method
  (`southbrook_estimating/models/product_pricelist.py:19`)
  computes price live to hit the 35% target margin against
  current `standard_price`.

Refacing is door-and-front-only — a new full-cabinet SKU
typically does **not** apply to Refacing. Skip unless explicit.

**9. Run the test quote (10 min):**

- **Southbrook Estimating → Order Builder → New**.
- Customer: *Demo Tradesperson Tier 3* (canonical smoke-test
  partner per Q7).
- Add a line; pick your new template; click *Configure*; pick
  the most expensive plausible configuration (highest-priced
  options on every attribute).
- Confirm:
  - Line price = base × 0.65 + sum of price_extras × 0.65.
  - `sb_panel_count`, `sb_door_count`, `sb_width_mm` populate
    (the Southbrook line metadata fields on `sale.order.line`
    from `southbrook_estimating/models/sale_order_line.py`).
  - **BoM Preview tab** (well — the `kitchen_3d_preview`
    notebook page per the audit finding) shows the rolled-up BoM
    with the right components and operations.
  - Tax line reads the right tax (*GST 5%* unless overridden).
- Print the **Signature Spec Sheet** (lesson 5.2 covers the PDF
  flow).

**10. Sales-manager sign-off (3 min):**

- Email the signature spec sheet to the sales manager.
- They confirm the margin against cost, the price extras feel
  right, and the configuration on the test quote isn't
  pathological.
- Verbal approval is enough; the audit trail is the spec sheet
  PDF stored in the conception folder.

**11. Hand-off to lesson 11.7 (1 min):**

- Mark the template *Active for sale* (already is, but confirm).
- Slack the production planner:
  *"Pricing signed off on `southbrook.<xml_id>`; ready for first
  MO scheduling."*

## Common mistakes + how to recover

**"I set `list_price` and the estimator's quote came back showing
the dealer pricelist amount, not retail."**

Channel pricelists override retail when the customer's channel is
`dealer`. The Order Builder is **showing** the dealer customer's
price correctly; you set `list_price` correctly. *Verify* by
switching the customer to a `retail` channel — the price should
show the unmultiplied `list_price`. If even the retail customer's
quote shows the wrong price, your `list_price` is wrong; fix it
on the template.

**"The cost on the template says $0.00."**

The BoM cost roll-up didn't run. On the template, click *Update
Cost from BoM* (button in the *Sales* tab — may be on the BoM
form depending on Odoo version). If still $0.00, the BoM is
empty or its components have $0.00 cost. Lesson 11.4 should have
left this populated; if not, escalate to the BoM author.

**"I set a price_extra of $45 for the *Maple box* value, but the
quote is adding $45 to the retail price even when the customer is
on a dealer pricelist — I expected $22.50."**

`price_extra` on `product.template.attribute.value` adds to
*pretax retail*, then the pricelist multiplier applies. So
`(list_price + price_extra) * 0.50` = the dealer price.
Order-of-operations is right; check the math.

**"The refacing-margin target isn't computing — the price is
showing as $0.00."**

The `is_refacing_margin_target` field on the
`product.pricelist.item` must be ticked **and** the item must
apply to your product. Also confirm `standard_price` is populated
(if cost is $0, target margin of 35% on $0 is $0). And the
`_compute_refacing_price()` method (estimating addon) reads the
current cost, so a stale cost means a stale price.

**"I set per-attribute-value price extras and they applied to
*every* template that uses the attribute, not just mine."**

Then you edited the wrong row. The `price_extra` field exists on
**two** different join models in Odoo v19:
- `product.attribute.value.price_extra` — affects every template
  the value appears on.
- `product.template.attribute.value.price_extra` — affects
  *this template* only.
You want the second. Find the row via the template form's
*Variant Attributes* tab → click into the attribute line → the
values listed each have an Extra Price column. That's the
template-scoped one.

**"The test quote works for Tradesperson Tier 3 but the locked Q7
smoke test calls for switching customer between Tier 3 and retail.
When I switch, the quote doesn't re-price."**

Check `sale.order._onchange_partner_id_southbrook_pricelist`
(`southbrook_estimating/models/sale_order.py:117`) is firing.
The Q7 smoke test is the canonical regression — failures here mean
the channel-resolution onchange isn't wired. Check the developer
console for errors; the most likely cause is a customisation that
disabled the onchange.

## What the system is doing behind the scenes

When you set `list_price` and save:

- A write on `product.template.list_price` happens.
- No immediate variant updates — variants compute their price on
  the fly from `list_price + sum(price_extras)`.

When a customer is selected on a sale order:

- `sale.order._onchange_partner_id` (Odoo native) fires.
- The Southbrook override
  `_onchange_partner_id_southbrook_pricelist`
  (`sale_order.py:117`) runs, calling
  `_resolve_channel_pricelist(partner)` (line 59).
- `_resolve_channel_pricelist` reads `partner.channel` (the
  Southbrook field on `res.partner` per
  `southbrook_estimating/models/res_partner.py:33`) and, if
  `channel == 'tradesperson'`, reads `tradesperson_tier` (line
  55) to pick from `_TRADESPERSON_TIER_PRICELISTS` map.
- The resolved pricelist id is written to
  `sale.order.pricelist_id`.
- All `sale.order.line.price_unit` re-computes from the new
  pricelist's rules against each variant's
  `(list_price + price_extras)`.

When a line's variant has price_extras:

- The variant's
  `product.product.list_price` reads
  `template.list_price + sum(price_extra for each
  template_attribute_value on this variant)`.
- The pricelist applies its multiplier to that total.

When the refacing-margin target item runs:

- The pricelist item's `_compute_refacing_price()` reads
  `self.product_tmpl_id.standard_price` (current rolled-up cost).
- Computes target price as `cost / (1 - 0.35)` to hit 35% margin.
- Returns this as the line price.

When the test quote is confirmed (you don't confirm in this
lesson — the sales manager sign-off is enough), the standard
`sale.order.action_confirm` runs; the order transitions through
the Southbrook stage pipeline
(`production_approval_state` on `sale.order`, added by
`southbrook_mrp_pm/models/sale_order.py:54` — separate from
estimating despite the conceptual proximity).

## Quiz (5 questions, applied)

**1.** You set `list_price = $400` and the Maple box value
`price_extra = $40`. A dealer customer adds the SKU with the
Maple box option. What does their quote line show?

> `(400 + 40) * 0.50 = $220`. The price extra adds to retail
> first, then the dealer multiplier of 0.5 applies. Don't try to
> apply the multiplier to the extra separately — that math gives
> $220 too in this case but it's coincidence; for non-50% channels
> the right order matters (e.g. Tier 3 tradesperson:
> `(400 + 40) * 0.65 = $286`, not `400*0.65 + 40 = $300`).

**2.** The sales manager wants the new SKU to enter the catalog at
$520 retail. The cost (from BoM rollup) is $185. What's the gross
margin?

> Gross margin = `(520 - 185) / 520 = 64.4%`. That's healthy for
> a cabinet — Southbrook's catalog typically targets 60-70% gross
> margin at retail (which becomes 20-40% at dealer after the −50%
> multiplier). If the sales manager wanted a higher list price,
> capture the rationale in `scope.md`; if they wanted lower, ask
> whether the SKU has a strategic reason to under-price.

**3.** You're asked to enable the new SKU on Big-Box. What price
do you set in the per-product Big-Box override?

> Wholesale fixed $65 cost / $98 retail — the Big-Box channel is
> a fixed-price-per-SKU channel, not a multiplier. Add the
> per-product fixed-price item on the Big-Box pricelist. Do not
> add a Big-Box override unless the channel green-lit this SKU —
> Big-Box carries a deliberately small catalog and adding random
> SKUs disrupts the channel relationship.

**4.** The test quote shows the right line price but the BoM
Preview tab is empty. The configurator session ran fine. What's
wrong?

> The BoM exists (lesson 11.4) but the *configurator-to-BoM
> bridge* (`product_configurator_mrp`) isn't picking up
> attribute-value-to-BoM-line bindings. Likely cause: the BoM
> lines don't have *Apply on Variants* configured (lesson 5.1).
> Recovery: open the BoM, set Apply on Variants for each
> attribute-dependent line, save, re-run the test session. The
> BoM Preview should now populate.

**5.** The sales manager says *"this should match the price of
`southbrook.base_2dr` at retail."* What do you do?

> Open `southbrook.base_2dr` and copy its `list_price` to your
> new template. Then walk every common attribute value (any
> attribute both templates share) and confirm the `price_extra`
> values match. The two SKUs end up priced identically at retail
> and identically through every channel. Document the deliberate
> price-parity in `scope.md` so future estimators don't drift the
> two prices apart.

---

## What this lesson does NOT cover

- Order Builder UI and the daily quoting flow — lesson 5.2.
- Channel pricelist fundamentals (retail, dealer, tradesperson
  tiers, KD, big-box, refacing) — Course 8 and lesson 5.2.
- The `_resolve_channel_pricelist` algorithm — lesson 5.2 and
  `southbrook_estimating/models/sale_order.py`.
- The Signature Spec Sheet PDF — lesson 5.2.
- Bulk-import of pricing across many SKUs — lesson 5.4
  configurator UX import wizard.
- The hardware auto-resolver pricing for per-door / per-shelf
  hardware — lesson 5.3.
- Tax fiscal-position remapping (out-of-province, status-Indian
  customers) — native Odoo accounting training, not this course.
- The first MO and what happens on the shop floor — that's
  lesson 11.7.
