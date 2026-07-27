---
course: 10 — Configurator Deep Dive
chapter: 10.2
title: Setting Up a New Configurable Product — End-to-End
duration: 50 minutes
audience: Product admin who owns the cabinet catalog. You add new SKUs every few months as Southbrook adds a series or a vendor changes a door style.
prereqs: Course 5 (5.1, 5.2). Lesson 10.1 (architecture). You know what an attribute_line is and which addon owns the rule engine.
custom_modules: product_configurator, product_configurator_sale, product_configurator_mrp, southbrook_estimating, southbrook_configurator_ux
---

# Setting Up a New Configurable Product — End-to-End

## Who this lesson is for

You're the product admin who owns the catalog. Sales has just told
you Southbrook is launching a new line — say, a 24-in vanity in the
Elegance series with a fluted door style nobody has seen before. Your
job is to take that requirement and walk it through the configurator
stack until an estimator can open the Order Builder, drop a line, hit
Configure, and price the new product correctly. This lesson is the
complete checklist. No shortcuts. Six stages, one product to ship.

## Where this lives on the site

Three menu paths cover 90% of the work:

> **Sales → Configurable Products → Configurable Templates** — the
> 12 cabinet templates + ~40 expanded catalog templates. Where the new
> SKU's `product.template` record lives.

> **Sales → Configuration → Attributes** — every `product.attribute`
> and its values. Where new attribute values get added.

> **Sales → Configuration → Configuration Rules** — every
> `product.config.line`. Where you author exclusions + construction
> rules.

A fourth, for proofing:

> **Sales → Configurable Products → Configuration Sessions** — every
> session ever created. You'll create test sessions here as you
> validate the new product.

## What your screen shows

The end state — what an estimator sees after you finish:

- A new line in the Order Builder's product picker (filtered by
  `config_ok = True`).
- A Configure button on the new line that opens the wizard with the
  right attribute_lines in the right order.
- Live pricing reflecting the new attribute values' `price_extra` and
  any base list_price.
- The 4 Southbrook rules + any new rule you wrote firing as expected.
- The customer-facing `/shop/<slug>` page rendering the new template
  in the v2 chip UI (if `is_published = True`).
- A BoM auto-generated on commit, with the right component lines.

The work to get there is six staged passes, in order. Skipping any
one means the next won't work.

## Your daily flow

**Stage 1 — Gather the spec.**

Before opening Odoo, write down:

- `default_code` — the SKU prefix (e.g. `SB-VANITY-24-EL-FLUT`). This
  is your XML id seed too.
- `name` — the display name (e.g. "Vanity 24in Elegance Fluted").
- Which attributes apply (subset of Family, Width, Series, Box
  Material, Door Style, Finish, Hinge Side, Finished Sides, Gables,
  Handle, Accessories — plus any derived like Family Subtype, Door
  Count).
- What `value_ids` are allowed per attribute (the new fluted door
  needs a new `product.attribute.value` if it doesn't exist).
- Base `list_price` (the retail-channel base — channel pricelists
  resolve from this).
- Any rules: "Fluted door only on Elegance" → if Elegance is the only
  series exposed on the template, no rule needed. If multiple series
  are exposed but Fluted is restricted, that's a `product.config.line`.

**Stage 2 — Add any new attribute values.**

Navigate to **Sales → Configuration → Attributes**. Open the
attribute you need to extend (e.g. Door Style). Add a new
`product.attribute.value` row:

- `name` — "Fluted Woodgrain".
- `sequence` — drives the order it appears in the wizard pickers; pick
  a number to slot it between existing values.
- `value_inches` / `value_mm` if Width-like, `lead_time_extra` if it
  bumps lead time (Maple's 14 is the precedent).
- `html_color` if it's a color swatch.
- `image` if it's an image-display attribute.

Save. The value is now available for any template's attribute_line to
include. **Adding the value here does NOT make it appear in any
existing template's wizard** — you have to add it to each
attribute_line manually.

**Stage 3 — Create the `product.template`.**

Two paths, pick one:

- **Path A — UI.** Navigate to **Sales → Configurable Products →
  Configurable Templates**. Click "New". Fill:
  - `name`
  - `default_code`
  - `type` (almost always `consu` for cabinets — Odoo 19 collapsed
    `product` into `consu` for goods).
  - `categ_id` (internal category — `All / Saleable / Cabinets` or
    whatever your tree uses).
  - `list_price` (the retail base).
  - `config_ok` → tick. This is what makes the configurator engine
    treat it as configurable.
  - `sale_ok` → tick. So it appears in the Order Builder product
    picker.
  - `is_published` → tick if customers should see it on `/shop`.
  - `southbrook_category` → Wall / Base / Drawer / Tall / Vanity /
    Extras.
  - `southbrook_icon_key` → matches the JS `CABINET_ICONS` map keys
    (wall1, wall2, base1, base2, drawer, sink, pantry, oven, corner,
    vanity, extra, worktop).
- **Path B — XML data.** For permanent additions to the catalog,
  prefer XML so the record survives DB rebuilds. Add to
  `southbrook_configurator_ux/data/catalog_expansion.xml` (or a new
  data file if you're shipping a separate addon). Use the existing
  records as patterns. The XML id should match `default_code`
  lowercased with underscores. Re-run `-u southbrook_configurator_ux`
  to load.

Either path: confirm `config_ok = True` after save. Without it the
configurator refuses to open.

**Stage 4 — Define attribute_lines on the template.**

Open the saved template. Go to the **Attributes** tab. For each
attribute the product needs, add a `product.template.attribute.line`:

- `attribute_id` — Width / Series / etc.
- `value_ids` — the allowed `product.attribute.value` records. For
  Width on a 24-in fixed-size vanity, set value_ids to just `[24 in]`.
  For Door Style on an Elegance-only template, set value_ids to
  `[Five-Piece Woodgrain, Fluted Woodgrain]` (your new value).
- `required` — tick if the attribute is a forced choice; leave blank
  if it's optional. The OCA wizard gates progression on required.
- `default_val` — sets the initial pick. Used at session.create() to
  seed the wizard.

**Critical: every attribute_line must have at least one value**, or
v19's `_validate_layout` raises NF19 at install. If you're authoring
in XML, double-check `<field name="value_ids" eval="[(6, 0, [...])]"/>`
is non-empty.

The attribute_lines are evaluated by the configurator in
`attribute_id.sequence` order. If you need a question to come
**before** another, edit the attribute's sequence — don't try to
order the attribute_lines themselves.

**Stage 5 — Author any rules.**

If your new product needs an exclusion or construction rule beyond
the 4 canonical Southbrook rules, author one or more
`product.config.line` records. Each rule needs:

- A `product.config.domain` — the trigger. e.g. "Series IS Contractor"
  is `domain_series_is_contractor` in
  `southbrook_estimating/data/config_rules.xml`. Pattern:
  ```xml
  <record id="domain_my_new_trigger" model="product.config.domain">
    <field name="name">My trigger description</field>
  </record>
  <record id="domain_line_my_new_trigger" model="product.config.domain.line">
    <field name="domain_id" ref="domain_my_new_trigger"/>
    <field name="attribute_id" ref="attr_series"/>
    <field name="condition">in</field>
    <field name="value_ids" eval="[(6, 0, [ref('value_series_elegance')])]"/>
  </record>
  ```
- A `product.config.line` per template the rule applies to:
  ```xml
  <record id="rule_my_template_my_constraint" model="product.config.line">
    <field name="product_tmpl_id" ref="my_new_vanity_template"/>
    <field name="attribute_line_id" ref="attr_line_my_template_door_style"/>
    <field name="value_ids" eval="[(6, 0, [ref('value_door_fluted')])]"/>
    <field name="domain_id" ref="domain_my_new_trigger"/>
  </record>
  ```

The `value_ids` on the `product.config.line` is **the allowed set when
the domain fires**, not the blocked set. Picking values outside
`value_ids` is what the rule engine forbids.

Rules are evaluated in `sequence` order on the config_line — leave
blank (default 10) unless you need ordering control (Lesson 10.7).

**Stage 6 — Test, publish, and verify the BoM.**

Sub-stage 6a — open the wizard.

- Backend: Sales → Quotations → New, add the new product to a line,
  hit Configure. Walk through the wizard. Confirm the right attributes
  appear in the right order, the rules fire as you expect, the price
  updates after each pick.
- Customer-facing: `/shop/<slug-of-your-product>` while logged out.
  Confirm the v2 chip UI renders. Pick through. Confirm Add to Quote
  routes through the login flow (anonymous → signup).

Sub-stage 6b — verify the BoM.

- Open **Manufacturing → Bills of Materials**. Filter by your new
  template. The first wizard commit auto-creates a `mrp.bom` (via
  `product_configurator_mrp.create_get_bom()` — Lesson 10.5). Open
  it. Confirm the bom_lines reflect your configuration. If there's no
  BoM, the template doesn't have a parent BoM to inherit lines from —
  you may need to create one with `product_id = False` on the
  template before any variant commit.

Sub-stage 6c — verify the sale-order pricing.

- Confirm the line's price matches the expected channel-pricelist
  calculation: base list_price × channel discount + sum of price_extras
  for picked values. The most common bug is forgetting to set the
  channel's pricelist on the partner before opening the order.

Sub-stage 6d — publish + announce.

- Tick `is_published = True` if you haven't yet.
- Optional: add a `product.config.image` linking the template to a
  hero image keyed by a specific `value_ids` combination (so the
  preview pane shows different visuals as the customer picks).
- Tell sales the SKU is live.

## Common mistakes + how to recover

**"The wizard opens but the new product isn't in the product picker
on the Order Builder line."**

Three suspects: (1) `config_ok = False`, (2) `sale_ok = False`,
(3) the template's `categ_id` excludes it from the picker domain. Open
the template, fix the missing field. The Order Builder picker reads
`sale_ok = True AND config_ok = True` from configurable products.

**"I added the new Fluted door value to the Door Style attribute, but
the wizard still doesn't show it on the vanity template."**

You added the value at the **attribute** level but didn't add it to
the **attribute_line** on the specific template. Open the template,
go to the Attributes tab, edit the Door Style attribute_line, add
the Fluted value to value_ids. Save.

**"The configurator price doesn't include the +$50 I set on the
Fluted door style."**

The `price_extra` lives on `product.template.attribute.value` (the
PTAV), NOT on `product.attribute.value`. When you added the Fluted
value to the template's Door Style attribute_line, Odoo auto-created
a PTAV row for (this template, Fluted) with `price_extra = 0`. You
have to edit that PTAV to set the price extra. Backend path:
the attribute_line's `product_template_value_ids` is where they
hide. Open them, set `price_extra`, save.

**"The rule I authored isn't firing — customers can still pick the
wrong combination."**

Three suspects:
- The `product.config.line.domain_id` isn't pointing where you think.
  Open the rule record, click through to the domain — check the
  domain's lines reference the right `attribute_id`.
- The rule is bound to the wrong `attribute_line_id`. The rule
  `value_ids` are the allowed set for THAT attribute_line. If you
  bind to "Door Style" but mean "Box Material", the rule fires but
  on the wrong attribute.
- The data file load order put the rule before the template — see
  Lesson 10.1's quiz #2. Move the rule to a file that loads last.

**"The BoM didn't generate after I committed the first configured
order."**

`create_get_bom` requires either (a) a parent BoM on the template
with `product_id = False` whose lines are wired via
`mrp.bom.line.configuration.set`, OR (b) attribute values with linked
`product_id` records so each picked value contributes a BoM line via
its option-product. If neither is set up, `create_get_bom` walks both
paths and produces an empty BoM (returns False). Fix: create a
parent BoM with the canonical component list, OR link option-products
to each attribute_value.

**"I shipped the new template via XML but `-u southbrook_configurator_ux`
doesn't update the existing records in the test DB."**

XML data files load with `noupdate="1"` by default for data records.
That means re-running `-u` does NOT overwrite existing rows. To
force update, either (a) set `noupdate="0"` on the `<odoo>` element
in the data file (already the case for `rule_completion.xml`), or
(b) explicitly drop the records via `odoo-bin shell` before
re-installing.

## What the system is doing behind the scenes

When you save the new template with `config_ok = True`, Odoo:

1. Writes the `product.template` row.
2. For each attribute_line you add, writes a
   `product.template.attribute.line` row AND auto-creates a set of
   `product.template.attribute.value` (PTAV) rows — one per
   (template, value) pair in `value_ids`. Each PTAV starts with
   `price_extra = 0`, `weight_extra = 0`.
3. Because `create_variant = 'dynamic'` is set on every Southbrook
   attribute (Q6 decision in CLAUDE.md), Odoo does NOT pre-create
   variants. Variants are materialised on the first
   `session.create_get_variant()` call — that is, when the first
   customer commits a configuration.

When an estimator opens the wizard, the OCA backend (defined in
`product_configurator/wizard/product_configurator.py`) calls
`_fields_view_get` dynamically: it iterates `attribute_line_ids`
sorted by `attribute_id.sequence`, generates a transient field per
attribute (named `__attribute-<id>`), and returns a generated form
view. That's why adding an attribute_line is enough to make the
wizard ask the question — no view file to edit.

When the customer hits Add to Quote on the v2 page, the JSON-RPC
controller at
`southbrook_configurator_ux/controllers/main.py:configurator_commit`
calls `session.create_get_variant()`. That method (in
`product_configurator/models/product_config.py` line 905) calls
`validate_configuration()` first (which checks every rule),
materialises the variant if needed, and — because
`product_configurator_mrp` overrides it — also calls
`create_get_bom()` to build the matching BoM.

The price the customer sees is computed by `session.get_cfg_price()`
(line 996), which sums `product_tmpl.list_price` + each picked
value's `price_extra` from the PTAV. Channel pricelist resolution
happens later, at the sale.order.line level via
`product_configurator_sale.sale_order_line._compute_price_unit`.

## Quiz (5 questions, applied)

**1.** Sales asks you to add a new 36-in Vanity in the Elegance
series. Walk through the minimum set of records you create — by
model name — to make it show up in the Order Builder with the right
attributes.

> One `product.template` (config_ok=True, sale_ok=True,
> southbrook_category='Vanity'); 5–11 `product.template.attribute.line`
> records (Width with value `36 in`, Series with value Elegance,
> Box Material with allowed values, Door Style with allowed values,
> Finish, Hinge Side, Finished Sides, Gables, Handle, Accessories —
> whichever the vanity exposes); Odoo auto-creates the matching
> `product.template.attribute.value` (PTAV) rows for you. No new
> `product.attribute.value` records IF you reuse existing values.
> Test session → commit → confirm `product.product` (variant)
> appears + `mrp.bom` was generated.

**2.** You add a new attribute value "Brushed Brass" to the Handle
attribute. You set `price_extra = 8.0` on the value's own record.
Customers still see the new option but the price doesn't update by
$8 when they pick it. Why?

> The `price_extra` field on `product.attribute.value` is **not**
> what the configurator reads. It reads `price_extra` on
> `product.template.attribute.value` (PTAV) — the per-template
> price override. When you added Brushed Brass to the Handle
> attribute_line on each template, Odoo auto-created PTAV rows with
> `price_extra = 0`. You have to open each PTAV (one per template
> the value applies to) and set $8 explicitly. There's no single
> "set price_extra everywhere" UI; you do it once per template, or
> author it in XML.

**3.** Your new Fluted door rule fires on the Vanity template but
not on the Base 2-Door. Both templates expose the Fluted value via
their Door Style attribute_lines. What's the most likely diagnosis?

> The `product.config.line` you wrote is bound to one specific
> template via `product_tmpl_id`. Rules are NOT global — they
> apply to one template each. To enforce the rule on Base 2-Door
> as well, write a second `product.config.line` record with
> `product_tmpl_id = base_2dr` and the same domain. Pattern: one
> `product.config.domain` shared across templates + N
> `product.config.line` records (one per template).

**4.** You publish the new product and a customer reports "I picked
Series=Contractor on this vanity and the wizard let me — but
Contractor isn't supposed to be available on vanities at all." What
went wrong at template setup?

> You added the Series attribute_line with all 4 series values
> (Contractor, Contemporary, Elegance, Signature) when the vanity
> should expose only Contemporary/Elegance/Signature. Two fixes:
> (a) restrict the attribute_line's `value_ids` to just the three
> allowed series (clean — the wizard never offers Contractor);
> (b) keep all 4 values exposed but write a `product.config.line`
> rule that excludes Contractor on the vanity template (uses the
> rule engine, surfaces a "not available" reason in the OCA
> wizard). Option (a) is simpler when the restriction is permanent;
> (b) is better when it might change per channel.

**5.** You author the new template entirely in
`southbrook_configurator_ux/data/catalog_expansion.xml`. Install
runs clean. Two weeks later, a junior dev edits the template's
name in the UI directly. Next deploy, `-u` runs and the name
reverts. Diagnose + recover.

> `catalog_expansion.xml` ships data records that get loaded with
> the data semantics implied by its `<odoo>` element. If the file
> opens with `<odoo>` (default noupdate="0" for some records and
> "1" for others depending on attributes), `-u` will overwrite
> the UI-edited name with the XML's name on every reinstall.
> Two fixes: (a) update the XML to match the new name (keep
> source-of-truth in version control), or (b) add `noupdate="1"`
> to the record so `-u` skips it after first install. Pick (a)
> for sanity — UI edits to data records always drift.

---

## What this lesson does NOT cover

- Configurator basics + the 4 Southbrook rules — Course 5, Lesson
  5.1.
- The 5-addon architecture — Lesson 10.1.
- Session state debugging — Lesson 10.3.
- BoM rollup mechanics + configuration sets — Lesson 10.5.
- The v2 chip UI mounting + JSON-RPC contract — Lesson 10.6.
- Common gotchas under load (rule ordering, exclusion explosion) —
  Lesson 10.7.
- Native Odoo product administration (categories, tax mapping,
  multi-company) — Odoo's own native eLearning track.
