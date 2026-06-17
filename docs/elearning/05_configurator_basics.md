---
course: 5 — Estimating + Configurator
chapter: 5.1
title: Configurator Basics — Attributes, Exclusions, Construction Rules
duration: 30 minutes
audience: New estimator. You've used Odoo Sales but never configured a cabinet through `product_configurator` before.
prereqs: Basic Odoo navigation. You can find Sales, open a draft quote, and edit an order line.
custom_modules: product_configurator, product_configurator_sale, southbrook_estimating
---

# Configurator Basics — Attributes, Exclusions, Construction Rules

## Who this lesson is for

You're a brand-new Southbrook estimator. Today is the first time you'll
hear the word "attribute" used in a technical sense — and probably the
last time you'll see a kitchen quote written on a spreadsheet. The
Southbrook stack runs every cabinet through the OCA `product_configurator`
engine, layered with the 4 Southbrook business rules. This lesson is the
vocabulary you need before you can build a quote in lesson 5.2. No
clicking yet — just the words, the model behind the words, and how a
kitchen gets decomposed into the records that drive everything downstream.

## Where this lives on the site

You won't use the configurator directly from a menu. You drive it from a
sale order line. But the vocabulary lives under three menus you should
recognise:

> **Southbrook Estimating → Order Builder** — where you'll spend 90% of your day.

> **Sales → Configurable Products → Configurable Templates** — the 12 cabinet
> templates plus the ~40 expanded catalog templates (`product.template` with
> `config_ok = True`).

> **Sales → Configuration → Configuration Rules** — the rule catalog
> (`product.config.line` records — the business rules from §3.4 of
> `docs/Southbrook_Excel_to_Odoo_Mapping.md`).

The third menu is read-only for you; an admin maintains it. You should
recognise the records when you see one.

## What your screen shows

Three concepts; learn them in order.

- **Attribute** (`product.attribute`) — *a question the configurator asks*.
  Southbrook ships 11 user-facing attributes plus 3 derived ones. Every
  cabinet asks the same 11 questions in the same order: Family, Width,
  Series, Box Material, Door Style, Finish, Hinge Side, Finished Sides,
  Gables, Handle, Accessories. Plus the derived ones (Family Subtype on
  the corner cabinet, Door Count behind the scenes, Accessory Type on
  the accessory template). Each attribute carries a `display_type`
  (`radio`, `select`, `color`, `pills`, `multi`, `image`) that controls
  how the wizard renders it.
- **Value** (`product.attribute.value`) — *one possible answer to one
  question*. Width has 10 values: `9 in`, `12 in`, `15 in`, `18 in`,
  `21 in`, `24 in`, `27 in`, `30 in`, `33 in`, `36 in`. Series has 4:
  Contractor, Contemporary, Elegance, Signature. Each value carries
  `sequence` (display order), and Southbrook-specific values carry
  `value_inches` / `value_mm` (Width) or `lead_time_extra` (Maple box
  carries `14.0` — that's the "+2 weeks" rule). An attribute without
  values is not selectable; an attribute_line on a template without at
  least one value will fail install (NF19).
- **Attribute Line** (`product.template.attribute.line`) — *which
  attributes apply to which cabinet*. The Vanity template has 11
  attribute_lines; the Worktop template has 4 (it doesn't care about
  Hinge Side). The configurator only asks the questions on the template's
  attribute_lines, in the sequence on the attribute record. If you don't
  see "Family Subtype" on a base cabinet, it's because there's no
  attribute_line for it on `base_1dr` — it's scoped to the corner
  template only (Q23(b)).

Now the two things that turn picks into business rules:

- **Exclusion / Domain Rule** (`product.config.line` + `product.config.domain`)
  — *X plus Y is forbidden on this template*. Southbrook calls these the
  "4 configurator rules" from `Southbrook_Excel_to_Odoo_Mapping.md` §3.4.
  Each rule is one or more `product.config.line` records linking a
  cabinet template, an attribute_line, a list of value_ids that get
  blocked, and a `domain_id` (the trigger condition — e.g.
  `domain_series_is_contractor` triggers when Series=Contractor). The
  rule engine reads these records at every pick and disables the
  forbidden options in real time.
- **Construction Rule** — *X selected implies Y placed at line N*. In
  Southbrook this is the same `product.config.line` machinery but used
  to ADD lines instead of restrict them. Example: pick Maple as Box
  Material → +10% price extra + 14 day lead time bump → the line is
  added to the BoM through `product_configurator_mrp` at MO creation.
  You don't see a construction rule in a separate UI; you see its
  effect in the price and the BoM preview.

## Your daily flow

You won't author rules. You'll *recognise* them when they fire. The
mental model: you pick an option, you see something disabled or
something repriced, and you should be able to say which rule fired and
why.

**1. Understanding decomposition.**

A kitchen design lands as a *list of cabinets*. There is no "kitchen"
object in the database — there's a `sale.order` and a list of
`sale.order.line` records, one line per cabinet. Each line points at a
`product.product` (a configured variant), which points at a
`product.template` (one of the 12 Q8 cabinet templates plus the ~40
expanded catalog templates). The line carries:

- `product_id` — the configured variant
- `product_uom_qty` — usually 1 (one cabinet = one line; a kitchen with
  18 cabinets has 18 lines)
- `zone` — Base Run / Wall / Tall / Island / Accessory / Other (Q21)
- `price_subtotal` — the line price, after the pricelist resolves the
  channel + tier

**2. Understanding the 11 questions.**

Every cabinet (except Worktop / Accessory) is asked the same 11 in this
order:

| Seq | Attribute | What it answers |
|-----|-----------|----------------|
| 1 | Family (`attr_family`) | What kind of cabinet — Wall / Base / Drawer Bank / Sink / Tall / Corner / Vanity / Worktop / Accessory |
| 2 | Family Subtype (`attr_family_subtype`) | Corner only — Standard or Bi-fold |
| 10 | Width (`attr_width`) | 9–36 in, in 3-in increments |
| 20 | Series (`attr_series`) | Contractor / Contemporary / Elegance / Signature |
| 30 | Box Material (`attr_box_material`) | White Melamine or Maple (+10% / +2 wk) |
| 40 | Door Style (`attr_door_style`) | Thermofoil Slab White / Five-Piece Woodgrain / Custom (Signature) |
| 50 | Finish (`attr_finish`) | White / Maple Stain / Cherry Stain / Walnut Stain / Custom |
| 60 | Hinge Side (`attr_hinge_side`) | LH / RH / N/A |
| 70 | Finished Sides (`attr_finished_sides`) | None / Left / Right / Both |
| — | Door Count (`attr_door_count`, derived, hidden Q22(a)) | 1 or 2 — set automatically by Width rule |

The `sequence` field on each attribute drives the wizard's question
order. You don't change it; you read it left-to-right top-to-bottom.

**3. Recognising an exclusion fire.**

You pick Series → Contractor on a base cabinet. The Door Style picker
greys out Five-Piece Woodgrain and Custom (Signature), leaving only
Thermofoil Slab — White available. That's Rule 1 (series → door style)
firing. The reason is encoded in the `product.config.line` record
`rule1_series_is_contractor_door_style_base_1dr` — the template `base_1dr`,
attribute_line `attr_line_base_1dr_door_style`, restricting `value_ids`
to `value_door_thermofoil_slab_white` when domain `domain_series_is_contractor`
is satisfied. The sales-rep UI shows the option disabled with a tooltip;
the customer-facing UI shows the option absent (so the customer never
sees "Five-Piece Woodgrain is disabled because you picked Contractor" —
they see a shorter list).

**4. Recognising a construction-rule fire.**

You pick Box Material → Maple on any cabinet. The price jumps by 10%
and the line's lead-time delta jumps by 14 days. That's Rule 2 (box
material → series + lead time) firing. You see it in the BoM preview
tab: the wood-panel line items reference maple cores; the
`mrp.bom.produce_delay` carries the extra 14 days.

**5. The 4 Southbrook rules, end to end:**

| # | Rule | Trigger | Effect |
|---|------|---------|--------|
| 1 | Series → Door Style | Series = Contractor | Only Thermofoil Slab White door style; others disabled |
| 1 | Series → Door Style | Series = Elegance | Only Five-Piece Woodgrain; others disabled |
| 2 | Box Material → Series | Box Material = Maple | Available only on Contemporary + Elegance; +10% + 14 days |
| 3 | Width → Door Count | Width ∈ {9, 12, 15, 18, 21 in} | Door Count = 1 (forced) |
| 3 | Width → Door Count | Width ∈ {24, 27, 30, 33, 36 in} | Door Count = 2 (forced) |
| 4 | Family → Soft-close | Corner template with Family Subtype = Bi-fold | Soft-close hinge option HIDDEN entirely |

Rules 1–3 are *exclusions* (they disable values); Rule 4 is a
*construction rule with negative effect* (it hides an entire
attribute_line). All four are declarative — there is **zero**
`if series == "contractor"` in `models/`. Grep it yourself.

## Common mistakes + how to recover

**"I'm staring at the wizard and the Door Style picker is empty — no
options at all."**

You picked an incompatible Series → Box Material combination. Most
likely Series = Contractor (forces Thermofoil Slab White) and an earlier
admin removed Thermofoil Slab White from the value catalog. Open
**Sales → Configuration → Attributes** and check that
`value_door_thermofoil_slab_white` still exists and is active. If yes,
your session is stale — close the wizard and re-open it. If no, escalate
to your admin: the catalog is broken.

**"I picked Series = Contractor and Box Material = Maple, and the
system let me, but the Door Style picker is empty."**

Rule 2 should have blocked Maple on Contractor — that combo is invalid.
What probably happened: the rule_completion.xml in `southbrook_configurator_ux`
hasn't loaded (Phase 1 rule gap). The OCA rule engine isn't seeing the
Contractor + Maple exclusion. Tell your admin to run
`-u southbrook_configurator_ux` and re-test. Meanwhile, change Box
Material back to White Melamine.

**"The wizard skipped the Family Subtype question entirely on a corner
cabinet."**

Family Subtype is scoped to the corner template via its attribute_line
(`attr_line_corner_family_subtype`). If you don't see it, you're not
on the corner template (`corner`) — you're on a base or vanity template
that got mislabelled "Corner" in the catalog. Cancel the session, return
to the order line, change the product to one whose default_code starts
with `SB-CORNER`, and reconfigure.

**"I picked Width = 30 in and the Door Count is showing 1, not 2."**

Rule 3 should force Door Count = 2 for widths 24+. Most likely cause:
your variant was already created at Width = 18 in (1 door) and you
edited the Width attribute on the line without re-running the
configurator. Click the Configure button on the line again — the
session re-runs Rule 3 and Door Count flips to 2. The price will
adjust by one extra door + hinge set in the BoM rollup.

**"The customer says they want a Five-Piece Woodgrain door on a
Contractor cabinet."**

You can't sell that combination. It's Rule 1 hard-blocked. Options:
(a) upsell them to Contemporary or Elegance series — Five-Piece is
available there; (b) explain that Contractor is the entry-level
thermofoil-only series and Five-Piece is on the wood-door series; (c)
if they insist, the only way is a Signature custom door (`value_door_custom`)
which any series allows but carries a manual price quote.

## What the system is doing behind the scenes

The OCA `product_configurator` machinery is essentially a state machine
on a `product.config.session` record, which lives until the user
finishes (state = `done`) and a `product.product` variant is
materialised. Each pick is a write to `session.value_ids` (an
`product.attribute.value` set). Every write triggers
`validate_configuration()`, which:

1. Loads all `product.config.line` records whose `product_tmpl_id`
   matches the template.
2. For each, evaluates the `domain_id`'s `compute_domain()` — does the
   current value_ids set satisfy the trigger condition?
3. If yes, the line's `value_ids` becomes the *allowed* value set on
   that attribute_line; everything else is disabled.

That's it. The whole rule engine is a domain-evaluation loop. Adding a
5th Southbrook rule means adding (a) one or more `product.config.domain`
records for the trigger, and (b) one `product.config.line` record per
cabinet template the rule applies to — no Python. Grep the codebase for
`if series ==` and you'll find zero hits inside `southbrook_estimating/models/`.
That's the design contract.

The construction-rule side (Maple → +10% / +14 days) reads
`product.attribute.value.lead_time_extra` and `product.template.attribute.value.price_extra`
during BoM rollup (`product_configurator_mrp.mrp.bom._compute`). Same
mechanism, just on the price/lead-time axis instead of the
allowed-values axis.

When the wizard ends and you click "Add to Quote", three things happen:

- A `product.product` variant is created (or reused if the same
  combination exists) — `create_variant='dynamic'` on every Southbrook
  attribute (Q6).
- A `sale.order.line` is created on your draft order, with the
  variant's price flowing through the channel-resolved pricelist.
- The `product.config.session` record moves to state `done`. You can
  re-open it from the line via the Configure button if you need to
  edit.

## Quiz (5 questions, applied)

**1.** You open a fresh draft order, add a cabinet line for `base_1dr`,
launch the configurator, and pick Series = Contractor. You then click
the Door Style picker. What do you see, and why?

> Only Thermofoil Slab — White is selectable. Five-Piece Woodgrain and
> Custom (Signature) are disabled. This is Rule 1 (series → door style)
> firing via the `domain_series_is_contractor` domain and the
> `rule1_series_is_contractor_door_style_base_1dr` `product.config.line`
> record restricting allowed values on `attr_line_base_1dr_door_style`.

**2.** A customer wants a 30-in Maple base cabinet with Elegance series.
You pick Width = 30 in, Series = Elegance, Box Material = Maple. The
price jumps and the line shows a "2 weeks extra" badge. Walk through
which rules fired and which records carry their effects.

> Rule 3 (Width → Door Count) auto-forced Door Count = 2 because Width
> is in the wide band (≥24 in) — value comes from `value_width_30`
> via `domain_width_wide`. Rule 2 (Box Material → Series + extras)
> didn't *block* anything (Elegance allows Maple) but applied
> `value_box_maple.lead_time_extra = 14.0` to the BoM and the +10%
> price-extra on the maple PTAV.

**3.** You're configuring a corner cabinet. You set Family Subtype =
Bi-fold. The Accessories picker no longer shows "Soft-Close Hinge Kit".
Why?

> Rule 4 (family → soft-close) hides — not just disables — the
> soft-close option entirely on bi-fold corners. The
> `domain_family_subtype_bifold` trigger fires, and the
> `product.config.line` record on `attr_line_corner_accessories` restricts
> the allowed value_ids to exclude the soft-close kit. Bi-fold corner
> hardware mechanically cannot run soft-close hinges.

**4.** Your admin asks: "I want to add a 5th rule — Tall cabinets can't
ship in Big-Box channel because they don't fit standard pallets." Where
does that rule live and what records change?

> It's a `product.config.line` rule, not Python. Author it as: a new
> `product.config.domain` for "Family is Tall" (which already exists
> as the Family attribute restriction); a `product.config.line` per
> tall template (`tall_pantry`, `tall_oven`) whose
> `domain_id` triggers on the partner's channel — but careful, the
> rule engine reads variant values, not partner fields. Channel
> filtering is a `sale.order` validation, not a configurator
> exclusion. So: this rule belongs in a `sale.order` constraint
> (`_constrains`), NOT in the configurator. The admin asked the
> wrong layer.

**5.** A new estimator asks "where do I edit Width values to add 42 in?"
What do you tell them, and why is the answer load-bearing?

> Go to **Sales → Configuration → Attributes → Width** and add a new
> `product.attribute.value` with name "42 in", `value_inches=42`,
> `value_mm=1067`, `sequence=11`. But also: edit each cabinet
> template's `attr_line_<sku>_width` to include the new value_id, and
> add Rule 3 width-band coverage for 42 (probably wide-band, so add
> `value_width_42` to `domain_width_wide` line). Then re-test the
> configurator — if you don't, the value will appear in the picker
> but Door Count won't auto-set on 42 (Rule 3 doesn't know about it),
> and the BoM math will fall back to 36-in geometry. The lesson:
> adding a value isn't one record — it's at least three.

## What this lesson does NOT cover

- How to build an actual quote — that's lesson 5.2.
- The Marathon hardware catalog (per-carcass hardware resolution) —
  lesson 5.3.
- The Southbrook configurator UX deltas vs OCA stock — lesson 5.4.
- BoM rollup and MO release — Production track (Course 2).
- The 3D Kitchen Preview tab in the Order Builder — Phase 3 material,
  out of scope today.
- General OCA `product_configurator` administration (creating new
  attributes from scratch, authoring domain records, etc.) — the OCA
  module's own docs at
  https://github.com/OCA/product-configurator are the source of truth.
