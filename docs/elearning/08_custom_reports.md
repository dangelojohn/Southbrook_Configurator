---
course: 8 — Estimating Deep Dive
chapter: 8.5
title: Custom Reports — Signature Spec Sheet, Shop Copy, Door Order
duration: 45 minutes
audience: Estimator + Production. The estimator generates the Signature Spec Sheet for the customer; production reads the Shop Copy at the work order; both feed downstream to the Door Order that goes to the supplier. This lesson is what each report does, when it's generated, what fields it pulls, and how to add a field without breaking everything else.
prereqs: Lesson 5.2, Lesson 8.1 (architecture), Lesson 8.2 (Order Builder), Lesson 8.4 (handoff)
custom_modules: southbrook_estimating
---

# Custom Reports — Signature Spec Sheet, Shop Copy, Door Order

## Who this lesson is for

The estimator generates the customer-signed Signature Spec Sheet.
The production planner prints the Shop Copy with the MO. The shop
manager batches Door Order PDFs and forwards them to the door
supplier. You're either of those three, OR the developer who's been
asked "can you add a field showing the customer's address on the
Door Order?"

This lesson covers all three reports — each with its own data
binding, its own field-mapping quirks, and its own load-order
sensitivity.

## Where this lives on the site

For the customer-facing PDF:

> **Southbrook Estimating → Order Builder → (any order) → Print →
> Signature Spec Sheet**

The same report is also available via Send-by-Email — Odoo attaches
the PDF to the email automatically.

For the shop-floor companion (MO-bound):

> **Manufacturing → Operations → Manufacturing Orders → (any MO) →
> Print → Shop Copy**

For the door supplier's schedule (SO-bound):

> **Southbrook Estimating → Order Builder → (any order) → Print →
> Door Order**

All three reports are registered via `ir.actions.report` with
`binding_type=report` so they appear in the Print menu of their
respective bound model.

## What your screen shows

The Signature Spec Sheet PDF:

- **Header strip**: "Your Southbrook Kitchen" / "Signature Spec
  Sheet" in the walnut display font + an ink-on-linen separator
  rule.
- **Customer block**: Customer name (from `o.partner_id.name`),
  Reference (`o.name` — the SO number) with version tag
  (`o.version`), Quote Date (`o.date_order` formatted as date).
- **Cabinets table**: columns Zone (translated from the selection),
  Cabinet (`line.product_id.display_name` falling back to
  `line.name`), Qty (`line.product_uom_qty`), Unit Price
  (`line.price_unit` as currency), Line Total
  (`line.price_subtotal` as currency). Zone cells append a "/
  zone_label" when zone=`other`.
- **Total row**: `o.amount_total` as currency, anchor right.
- **Disclaimer footer**: muted paragraph saying lead times and
  adjustments will be confirmed by the assigned dealer.
- **Illustrative-seed banner** (yellow): visible only when
  `ir.config_parameter southbrook.seed_mode = 'illustrative'`. You
  should NOT see this in production.

The Shop Copy PDF (MO-bound):

- **Header strip**: "Shop Copy" / MO name (`mo.name`).
- **Originating Order block**: SO name + customer (resolved via the
  NF25 chain `mo.sale_line_id.order_id` falling back to
  `mo.origin`).
- **Product + Quantity**: `mo.product_id.display_name`,
  `mo.product_qty` + UoM.
- **Effective Lead Time**: `mo.bom_id.effective_produce_delay` (with
  a muted note showing the `southbrook_lead_time_extra` bump when
  non-zero).
- **BoM table**: each `bom_line_id` shows component name, qty, UoM.
  Empty-state row when no BoM lines materialised.
- **Panel Cut List table** (Phase 4 — only renders when
  `southbrook_kitchen_mrp` is installed): pulls from
  `sb.production.package.cutlist_id.line_ids`. Columns: Panel name
  (translated), Qty, L (mm), W (mm), Thk (mm), Substrate, Grain.
- **Hardware package summary** (Phase 4): one-line muted footer
  showing hardware package name + SKU count + a pending-pricing
  flag.
- **Disclaimer footer**: muted paragraph emphasising MO-driven
  data (no spreadsheet mirror).

The Door Order PDF (SO-bound):

- **Header strip**: "Door Order" / SO name / customer name.
- **Per-line door table**: columns Cabinet, Series, Door Style,
  Finish, Hinge, Doors (count), W (mm), H (mm). Series, Door Style,
  Finish, Hinge Side are pulled from the variant's attribute values
  via `product_template_attribute_value_ids.filtered(...)`. Width
  uses `line.sb_width_mm`. Height is computed by a small heuristic
  on `line.name` (wall → 760, tall/pantry → 2100, else 720). Door
  count uses `line.sb_door_count`.
- **Doors by Series footer**: aggregates total doors per Series,
  rendered as a small table. The aggregation logic is inline
  QWeb `t-set series_totals dict` accumulation in the template.
- **Disclaimer**: per-SO scope, multi-order batched aggregation
  deferred to a separate report.

## Your daily flow

**1. Signature Spec Sheet — the estimator-customer interface.**

When you generate it:

> **(order form) Print → Signature Spec Sheet**

Or send it: `Send by Email` — Odoo attaches the PDF automatically.

The PDF is generated at click time from `report_signature_spec_sheet_doc`.
Data binding is `sale.order`, so the report sees `o = sale.order`
record. Every field read is read from the live SO at print time —
there's no snapshot. If you print, then edit lines, then re-print,
you get the updated numbers.

The customer signs the PDF (in-person, e-sign, or scanned
return-fax). The signed PDF gets attached to the order's chatter as
an audit artifact.

**2. Shop Copy — the production-line companion.**

The planner prints this for the work order:

> **(MO form) Print → Shop Copy**

Data binding is `mrp.production`. The report resolves
`mo.sale_line_id.order_id` (NF25 — the canonical chain) to get the
SO/customer context. Falls back to `mo.origin` (free-text SO name)
when `sale_line_id` is absent (manual MOs, demo fixtures).

The Effective Lead Time field shows the cabinet's planned production
duration including the maple +14 day extra (or any other lead-time
extras the variant carries). The shop floor uses this to plan
sequencing.

The Panel Cut List section only renders when the planner has run
the `sb.production.package.generate_from_mo()` action (from
`southbrook_kitchen_mrp`). Without that, the cut list section is
silently skipped — the QWeb uses `env.get('sb.production.package')`
which returns None when the module isn't installed, and the t-if
short-circuits cleanly.

**3. Door Order — batched supplier handoff.**

When the planner is ready to forward to the door supplier:

> **(order form) Print → Door Order**

Data binding is `sale.order`. The report pulls per-line door specs
+ aggregates a totals-by-series footer (because the supplier's
ordering form is organised by series — each series has its own
door catalog).

Per-SO scope is a Phase-1 simplification. Multi-order batch
aggregation across all open SOs ("send Wednesday's batch") is a
deferred report — file a ticket if the supplier reaches a point
where per-SO PDFs become unwieldy.

**4. Adding a field to one of the reports — the safe path.**

You'll be asked. The safe sequence:

a. Identify which report. Signature Spec Sheet is `sale.order`-bound;
   Shop Copy is `mrp.production`-bound; Door Order is `sale.order`-
   bound. The bound model determines what `o` (or `mo`) is.

b. Identify the source of the data. If it's a field on the bound
   model, simply `<span t-out="o.field_name"/>`. If it's on a related
   record (e.g. partner address on Door Order), it's
   `<span t-out="o.partner_id.street"/>`.

c. Add the field to the template at the right place. Use the
   existing CSS classes (`sb-muted`, `sb-rule`, `sb-zone-header`,
   `sb-total-row`, `sb-right`) — these are defined in
   `southbrook_report_styles.xml` and ensure visual consistency.

d. Test on at least one draft and one confirmed record. Phantom
   data (e.g. an order with no lines) should NOT crash the
   render — guard with `t-if`.

e. NEVER reorder the manifest's `data` list. The styles file MUST
   load before the report files (xpath references depend on it).
   If you alphabetise, you break everything.

## Common mistakes + how to recover

**"The Signature Spec Sheet PDF crashes with a 500 error."**

The QWeb template references a field that doesn't exist on the
record. Open the Odoo log and find the QWeb evaluation error. Most
common causes:
1. A new field was added but the seed didn't backfill — the field
   is `None` and `t-out` crashes. Fix: guard with `t-if`.
2. The styles template wasn't loaded — the data list got
   alphabetised. Fix: restore `southbrook_report_styles.xml` to
   precede the report files.
3. The order has a line with no `product_id` (a free-text
   comment) and `line.product_id.display_name` crashes. Fix:
   guard with `or line.name` (already in the canonical template at
   line 72: `line.product_id.display_name or line.name`).

**"The Shop Copy shows 'Originating Order: —' instead of the SO."**

The MO has no `sale_line_id` AND no `origin`. Either:
1. Manual MO created via the Manufacturing form (no SO trigger).
   Set `origin` manually if you want it on the print, or leave it
   if the MO is internally-scoped (e.g. shop-floor sample).
2. `sale_mrp` failed to populate `sale_line_id` at confirm.
   Inspect via developer mode → MO record. Recovery: manually
   populate `sale_line_id` from the originating SO line.

NF25 was caught at live install — the Odoo 19 `mrp.production.sale_id`
shortcut was dropped, replaced with `sale_line_id.order_id`. If you
see a template referencing `mo.sale_id`, that's pre-NF25 code; fix
the template.

**"The Door Order shows blank cells for Series / Door Style /
Finish."**

The variant has no attribute values for Series / Door Style /
Finish. Two causes:
1. The line was added but the Configure wizard was never run — so
   the variant is a "default" variant with no attribute values.
   Re-open the line, run Configure, save.
2. The attribute is named differently than the template expects.
   The template hardcodes attribute names:
   `v.attribute_id.name == 'Series'` — if your install has renamed
   the Series attribute (e.g. to "Cabinet Series"), the filter
   misses. Either rename back or update the template.

**"I added a field showing customer email on the Door Order, but
some orders show 'False' in that cell."**

`o.partner_id.email` is None when unset, and QWeb's `t-out` renders
the Python `False` string. Guard with `t-if="o.partner_id.email"`,
or use `t-out="o.partner_id.email or ''"`.

**"The Shop Copy Panel Cut List section is missing — the rest
prints fine."**

`southbrook_kitchen_mrp` isn't installed or no
`sb.production.package` exists for this MO yet. The QWeb does
`env.get('sb.production.package')` which returns None when the
module is absent — and the t-if short-circuits. If the module IS
installed and a package SHOULD exist, run the package generator from
the MO's chatter actions, then re-print.

**"The yellow ILLUSTRATIVE SEED banner is showing in production."**

The `ir.config_parameter southbrook.seed_mode` is set to
`illustrative`. This should be `canonical` (or absent) in
production. Open Settings → Technical → Parameters → System
Parameters, find `southbrook.seed_mode`, change to `canonical`.
Investigate how `illustrative` got set (almost certainly a demo
data leak).

## What the system is doing behind the scenes

Each report is registered via two records:

1. A `<template>` element defining the QWeb HTML (with embedded
   data lookups via `t-foreach`, `t-out`, `t-if`).
2. An `ir.actions.report` record binding the template to a model
   via `binding_model_id`.

When the user clicks Print:

1. Odoo loads the action.
2. Resolves `report_name` to the template.
3. Calls the template with `docs` set to the selected record(s) and
   `env` for env access.
4. QWeb evaluates the template against the data.
5. wkhtmltopdf converts the rendered HTML to PDF.
6. The result is served as a file attachment.

The shared style template (`southbrook_report_styles`) is included
via `t-call` at the top of each report template. The CSS variables
(`--southbrook-walnut`, `-sky`, `-linen`, `-ink`, `-rule-color`,
`-muted`) are currently TBD-marked per NF15 — the canonical hex
values are gated on the Signature Series spec book PDF (artifact
#7). When that lands, the swap is one file's worth of edits.

The reports honour the `southbrook.seed_mode` ir.config_parameter:
when set to `illustrative`, the Signature Spec Sheet renders the
yellow banner at top. This is for Phase-1 gate review only — the
production deployment should have the parameter unset or set to
`canonical`.

The Door Order's series-totals footer is computed inline via QWeb's
`t-set` and dict accumulation:

```xml
<t t-set="series_totals" t-value="{}"/>
<t t-foreach="o.order_line" t-as="ln">
  <t t-set="sv" t-value="ln.product_id.product_template_attribute_value_ids
       .filtered(lambda v: v.attribute_id.name == 'Series')[:1].name or 'Unknown'"/>
  <t t-set="cur" t-value="series_totals.get(sv, 0)"/>
  <t t-set="series_totals" t-value="dict(series_totals, **{sv: cur + (ln.sb_door_count or 0)})"/>
</t>
```

— a Python-style dict.update in QWeb's restricted Jinja-like
syntax. This is the right place for one-off aggregations; for
multi-report aggregations, lift to a Python method on `sale.order`.

The Shop Copy's Phase 4 Panel Cut List section uses defensive
env.get so installs without `southbrook_kitchen_mrp` don't crash:

```xml
<t t-set="PkgModel" t-value="env.get('sb.production.package')"/>
<t t-set="pkg" t-value="PkgModel.sudo().search([('mo_id', '=', mo.id)],
                                                limit=1) if PkgModel is not None else False"/>
<t t-if="pkg and pkg.cutlist_id">
  ... cut list rows ...
</t>
```

— if `PkgModel` is None or no package exists, the t-if short-
circuits cleanly. Standard pattern for cross-module optional
sections.

## Quiz (5 questions, applied)

**1.** A customer asks for the spec sheet to include their delivery
address. Where do you add it, and what do you guard against?

> Open `reports/signature_spec_sheet.xml`. Add inside the customer
> block (after Quote Date):
> ```xml
> <strong>Delivery Address:</strong>
> <span t-out="o.partner_shipping_id.contact_address" t-if="o.partner_shipping_id"/>
> ```
> Guard: orders where partner_shipping_id is False (rare, but
> possible for walk-in orders without a separate shipping contact).
> The `t-if` skips the row cleanly.

**2.** The production planner prints a Shop Copy and the BoM table
shows "No BoM lines materialised." The MO has product_qty = 4.
What's wrong, and what does the message tell you?

> The MO's `bom_id` is set but `bom_line_ids` is empty. Either
> (a) the BoM was created but has no component lines (broken seed);
> (b) the BoM lookup picked a generic BoM that legitimately has no
> components. Inspect: open the MO, look at the BoM, check its
> `bom_line_ids`. If empty, edit the BoM to add the right
> component products (panels, hardware, edge banding). The message
> is informational — the report doesn't fail, it just tells the
> floor "your BoM is empty, fix that."

**3.** The Door Order PDF shows all lines under Series = "Unknown"
in the totals footer. What does that mean?

> None of the variants carry a Series attribute value. Either:
> (a) Configurator wasn't run on any line (use the wizard); (b)
> the attribute is named differently than "Series" in this install
> (check `data/attributes.xml` — attr_series with name "Series").
> The template's filter
> `v.attribute_id.name == 'Series'` is exact-match. If the name was
> translated or changed, the filter misses everything → fallback
> "Unknown" populates.

**4.** You add a "Last Modified By" field to the Signature Spec
Sheet (`o.write_uid.name`). It works fine on most orders but
crashes on one. What's the cause?

> The order has `write_uid = False` — possible if created
> programmatically via a system user that was later deleted, or
> an order created via a script that bypassed the standard create
> hook. `o.write_uid.name` then crashes because you're accessing
> `.name` on a False / empty record. Guard:
> `<span t-out="o.write_uid.name" t-if="o.write_uid"/>` or
> `<span t-out="(o.write_uid.name or 'System')"/>`.

**5.** A developer needs to extend the Shop Copy to show a
QR-code for the SO link. Where do they put it, and what's the
gotcha with the binding model?

> Add the QR-code rendering inside the Originating Order block of
> `reports/shop_copy.xml`. Use Odoo's standard `barcode` widget via
> `<img t-att-src="'/report/barcode/QR/' + (so.name or mo.origin
> or '')"/>`. The gotcha: `o` in this template is `mrp.production`
> not `sale.order` — referencing `o.name` would give the MO name,
> not the SO. The SO is in the `so` variable resolved earlier by
> the t-set chain. Always check `t-foreach`'s loop variable name
> before assuming what `o` means — Shop Copy uses `mo`, the other
> two use `o`.

---

## What this lesson does NOT cover

- Order Builder UI walkthrough — lesson 8.2.
- Pricing mechanics — lesson 8.3.
- The Quote → MO handoff — lesson 8.4 (this lesson assumes the MO
  exists).
- Versioning / revisions — lesson 8.6.
- QWeb general syntax — Odoo's own docs.
- wkhtmltopdf configuration / page-break behaviour — sysadmin
  concern.
- The customer-facing one-page configurator PDF — Phase 2, not
  yet shipped.
- The Hermes platform's conversation transcripts — separate
  reporting surface in `southbrook_hermes`.
