---
course: 8 — Estimating Deep Dive
chapter: 8.1
title: Estimating Architecture — The Model Topology Behind the Order Builder
duration: 45 minutes
audience: Estimator team lead + developer extending the module. Reads like a map you keep next to your monitor when something downstream "doesn't add up" and you need to know which table to inspect.
prereqs: Lesson 5.1 (Configurator basics), Lesson 5.2 (Building a quote — the surface-level walk through), basic Odoo 19 ORM literacy (`_inherit`, computed fields, `@api.depends`).
custom_modules: southbrook_estimating, product_configurator, product_configurator_sale, product_configurator_mrp, sale_mrp
---

# Estimating Architecture — The Model Topology Behind the Order Builder

## Who this lesson is for

You're either the team lead the estimators escalate to ("the BoM preview
is empty and I don't know why"), or the developer who's about to extend
`southbrook_estimating` and needs to know what's already wired before you
add another `_inherit`. Either way, you need the map: which model carries
which field, what gets recomputed when, which inheritance chain owns the
notebook page, and where the report data comes from. This lesson is that
map. It's the deepest dive in the Estimating course — every later lesson
points back here.

## Where this lives on the site

There is no single screen for "architecture." The addon root is the map:

> **`addons/southbrook_estimating/`** in the repo

Backend menus you'll exercise while reading along:

> **Southbrook Estimating → Order Builder** (top-level app drawer)
> **Sales → Orders → Order Builder** (legacy Build-Spec §2.2 placement)
> **Southbrook Estimating → Launch 3D Configurator** (NF27 shortcut)
> **Settings → Technical → Database Structure → Models** (filter
> `southbrook.*` to see the custom model surface)

## What your screen shows

You won't be on one screen — you'll be in a code editor with the addon
open. The four directories that own the architecture:

- **`models/`** — Python `_inherit` extensions + the one new model
  (`southbrook.order.analytics`). 9 files, all pure data + small
  computed fields. The custom-routine register lives here.
- **`views/`** — XML xpaths that inject Southbrook fields and tabs into
  the standard Odoo forms. 6 files; the load-bearing one is
  `sale_order_views.xml`.
- **`reports/`** — 3 QWeb PDF templates + the shared style sheet. The
  style sheet must load first.
- **`data/`** — 8 XML files seeding attributes, pricelists, templates,
  rules, and config-step buckets. Load order is significant and
  documented in `__manifest__.py`.

## Your daily flow

This isn't a daily-flow lesson in the operator sense — it's a "when
you need to debug or extend, walk these steps" flow.

**1. The model topology — what extends what.**

The Order Builder is not a new model; it's the standard `sale.order`
with Southbrook fields layered through `_inherit`:

- **`sale.order`** (extended in `models/sale_order.py`) — adds:
  - `southbrook_submitted_date` (Datetime) — set by the portal
    "Request a Price" action; the customer-visible "submitted on" chip
    in the StagePipeline.
  - `parent_order_id` (Many2one→self) + `version` (Integer) — the
    NF6 Image Floor iterative-design chain.
  - `_CHANNEL_PRICELISTS` (class-level dict) — the channel→pricelist
    xml_id table, dispatched by `_resolve_channel_pricelist`.
  - `_TRADESPERSON_TIER_PRICELISTS` (class-level dict) — tier→
    pricelist xml_id for the contractor sub-tiers.
  - `_ZONE_LAYOUT` (class-level dict) — zone→(cursor, y_floor,
    z_offset) for the 3D Kitchen Preview tab.
  - `action_confirm()` override — calls super, then
    `southbrook.order.analytics.capture(order)`.
  - `action_duplicate_as_draft()` — clones the order, links
    `parent_order_id`, increments `version`.
  - `get_kitchen_3d_payload()` — multi-cabinet 3D payload for the
    notebook viewport.
  - `_southbrook_history_chain(max_depth=20)` — version-chain walker
    for the customer portal timeline.

- **`sale.order.line`** (extended in `models/sale_order_line.py`) — adds:
  - `zone` (Selection: base_run / wall / tall / island / accessory /
    other) — drives the multi-zone grid grouping in the Order Builder
    and the spec-sheet PDF grouping.
  - `zone_label` (Char) — free-text label, visible only when
    `zone='other'`. Cleared on onchange when zone moves off `'other'`.
  - `sb_panel_count` (Integer, computed, not stored) — panel count
    rolled up live from `_compute_sb_panel_rollup`.
  - `sb_door_count` (Integer, computed, not stored) — door/drawer-
    front count.
  - `sb_width_mm` (Float, computed, not stored) — derived width.
  - `_sb_derive_dimensions()` — helper: walks variant attributes
    first, then parses `line.name` (regex `_WIDTH_INCHES_RE`,
    `_FAMILY_RE`, `_DOOR_COUNT_RE`), then falls back to family
    defaults (`_SB_DEFAULT_HEIGHT_MM` and friends).
  - `action_reconfigure()` — entry point for the click-to-edit
    behaviour in the OWL 3D viewport.

- **`res.partner`** (extended in `models/res_partner.py`) — adds:
  - `channel` (Selection: retail / dealer / tradesperson / kd /
    bigbox / refacing) — the pricing-resolution keystone.
  - `tradesperson_tier` (Selection: 1 / 2 / 3) — meaningful only
    when channel=`tradesperson`.
  - `_onchange_channel_default_tier()` — defaults a new tradesperson
    to Tier 3 and clears tier when channel moves away from
    `tradesperson`.

- **`res.users`** (extended in `models/res_users.py`) — adds:
  - `southbrook_default_series` (Selection) — NF7, Amazing Window
    keyboard-first pattern.
  - `southbrook_order_entry_mode` (Selection: family_first /
    width_first) — NF8, Pro Finish spec-driven pattern.

- **`product.template`** (extended in `models/product_template.py`) — adds:
  - `southbrook_category` (Selection: Wall/Base/Drawer/Tall/Vanity/
    Extras) — catalog picker filter pill key.
  - `southbrook_description` (Char, translate=True) — one-sentence
    catalog card blurb.
  - `southbrook_dimensions` (Char) — display dimensions string.
  - `southbrook_icon_key` (Char) — key into the OWL `CABINET_ICONS`
    SVG map.
  - `action_southbrook_launch_3d_configurator()` — wraps OCA's
    `configure_product()` so a Southbrook header button always renders
    (NF26 mitigation for the unreliable OCA group-gated header
    button).

- **`product.attribute.value`** (extended in
  `models/product_attribute_value.py`) — adds (Q3 + Q4):
  - `value_inches` (Float) — imperial display value.
  - `value_mm` (Integer) — canonical mm value (do NOT compute one
    from the other — see the NF14 note).
  - `lead_time_extra` (Float, days) — maple box = 14.0.

- **`product.pricelist.item`** (extended in `models/product_pricelist.py`)
  — adds:
  - `is_refacing_margin_target` (Boolean) + `_compute_refacing_price`
    method — custom routine #2, the only non-declarative pricing
    rule in the addon.

- **`mrp.bom`** (extended in `models/mrp_bom.py`) — adds:
  - `_get_cut_constants()` — the load-bearing PLM seam. Returns box_th,
    back_th, rabbet, door_th, etc. `southbrook_plm.mrp_bom` overrides
    this method to read the active `southbrook.cut.spec` record. Per
    the `southbrook_plm_deploy` memory: removing this seam causes
    `AttributeError` on every BoM operation in any DB with PLM
    installed.
  - `_compute_panel_dimensions()` — custom routine #1, the parametric
    panel-cut math. Returns side_L, side_R, top, bottom, back, shelf,
    door tuples + hardware counts + edge_banding scalar.
  - `_compute_edge_banding_length()` — the Phase-1 scalar perimeter
    sum (per-edge mapping deferred to Phase 4).
  - `southbrook_lead_time_extra` (Float, stored, computed) — sum of
    `lead_time_extra` across variant attributes.
  - `effective_produce_delay` (Float, stored, computed) — base
    `produce_delay` + `southbrook_lead_time_extra`.

- **`product.config.session`** (extended in
  `models/product_config_line.py`, named the file after the historical
  NF2 hook) — adds:
  - `validate_configuration()` — pass-through override reserving the
    swap site for OCA's eventual dict-return → raise migration.
  - `get_3d_payload()` — single-cabinet 3D payload (the wizard
    viewport).
  - `_SKU_DEFAULTS` (class-level dict) — the 12 Q8 SKUs with their
    seed family/W/H/D so the first wizard render has correct
    geometry before any `value_ids` are picked.
  - `_extract_cabinet_inputs()`, `_cut_list_to_3d_payload()`,
    `_emit_doors()`, `_emit_drawer_fronts()`, `_3d_payload_worktop()`,
    `_3d_payload_accessory()` — geometry emitters per family.

- **`southbrook.order.analytics`** (new model in
  `models/southbrook_order_analytics.py`) — the AI data spine. One row
  per confirmed sale.order; captures channel, tier, dealer_id, series,
  cabinet/panel/door counts, lifecycle timestamps. `capture()` is
  idempotent.

**2. The view inheritance graph.**

The Order Builder is `sale.view_order_form` extended via
`view_order_form_southbrook` (in `views/sale_order_views.xml`). Each
xpath in that view does one thing:

- (1) Inject the ILLUSTRATIVE SEED banner above `//sheet`, gated on the
  `seed_mode_canonical` context flag.
- (2) After `//field[@name='partner_id']` — inject `parent_order_id`
  (readonly, invisible when absent) and `version` (readonly,
  `groups="base.group_no_one"`).
- (3) Inside `//div[@name='button_box']` — inject the stat-button
  **Duplicate as Draft** calling `action_duplicate_as_draft`.
- (4) Before `//field[@name='order_line']/list/field[@name='product_id']`
  — inject the `zone` column (optional="show") and `zone_label`
  (invisible when zone != 'other').
- (5) On `//field[@name='order_line']/list` — set
  `default_group_by="zone"` and `expand="1"` for the multi-zone
  grouping behaviour.
- (6) On the order-line `price_subtotal` — set `sum="Zone Subtotal"`
  to defend against future Odoo aggregation defaults.
- (7) Inside `//notebook` — inject a new page `kitchen_3d_preview`
  hosting the OWL `kitchen_viewport` widget at 520px height.

Plus the partner-form extension (`views/res_partner_views.xml`) which
injects a Southbrook Channel group inside the Sales tab
(`page[@name='sales_purchases']`).

Plus the user-preferences view (`views/res_users_views.xml`) for the
NF7/NF8 fields.

Plus `views/product_template_3d_launch_view.xml` — adds the **Configure
3D Southbrook** stat button (NF26) on every configurable product
template.

Plus `views/launch_3d_menu.xml` — defines the **Launch 3D
Configurator** menu item under the top-level Southbrook root (NF27).

The two top-level menus live in `sale_order_views.xml`:
`menu_southbrook_root` (top-level with web_icon) and the duplicate
`menu_southbrook_order_builder` under `sale.sale_order_menu` (NF23 —
preserves Build-Spec §2.2 placement while giving the addon main-app
drawer presence).

**3. Controller routes.**

There are **no controller routes** in `southbrook_estimating` itself.
Everything is backend-only. The customer-facing one-page configurator
ships in the companion addon `southbrook_estimating_website` (Phase 2,
not yet shipped). The "controller-side" references you'll see in test
files are aspirational — they describe behaviour expected once the
companion addon lands.

So when an estimator asks "is there a public URL for an order?", the
answer today is "via Odoo's standard portal at `/my/quotes`" — not via
a Southbrook-custom route.

**4. The report data flow.**

Three QWeb reports, three different data bindings — this catches
people:

- **`signature_spec_sheet.xml`** — bound to **`sale.order`**. Customer-
  facing PDF. The customer's signed deliverable. Reads `o.partner_id`,
  `o.name`, `o.version`, `o.date_order`, `o.order_line` (with `zone`,
  `product_id.display_name`, `product_uom_qty`, `price_unit`,
  `price_subtotal`), `o.amount_total`, `o.currency_id`. Honours
  `southbrook.seed_mode = illustrative` ir.config_parameter to show
  the demo banner.

- **`shop_copy.xml`** — bound to **`mrp.production`** (NOT sale.order).
  The shop-floor work-order companion. Pulls `mo.bom_id.bom_line_ids`,
  `mo.bom_id.effective_produce_delay`,
  `mo.bom_id.southbrook_lead_time_extra`. Resolves the originating SO
  via `mo.sale_line_id.order_id` (NF25 — the canonical link through
  `sale_mrp`; Odoo 19 dropped the legacy `mo.sale_id` shortcut).
  Falls back to `mo.origin` free-text when `sale_line_id` is empty
  (manual MOs). Phase-4 cut list pulls from
  `sb.production.package.cutlist_id.line_ids` via `env.get` so it
  no-ops when `southbrook_kitchen_mrp` isn't installed.

- **`door_order.xml`** — bound to **`sale.order`**. Door-supplier
  schedule. Loops `o.order_line` and pulls `Series`, `Door Style`,
  `Finish`, `Hinge Side` attribute values via
  `product_template_attribute_value_ids.filtered(lambda v:
  v.attribute_id.name == '<attr_name>')[:1].name`. Uses
  `line.sb_door_count` and `line.sb_width_mm` for the schedule cells.
  Aggregates a "Doors by Series" footer.

All three reports `t-call="southbrook_estimating.southbrook_report_styles"`
which defines the CSS variables (`--southbrook-walnut`, `-sky`,
`-linen`, etc. — currently TBD-marked per NF15 until the Signature
Series spec book lands as artifact #7).

The manifest data list orders this critically:
`southbrook_report_styles.xml` must precede `signature_spec_sheet.xml`,
`shop_copy.xml`, and `door_order.xml`. If a contributor alphabetises
the data list, the templates fail to render. The same load-order
discipline applies to `product_templates.xml` before `config_rules.xml`
(the rules reference attribute_line_ids on templates).

## Common mistakes + how to recover

**"I added a new model `southbrook.thing` and the install crashes
with `model not found` from another module's view."**

The `__manifest__.py` `data` list order is load-bearing. If you added
a view that references a model from another module that loads after
yours, install fails. Move your model's data to the right point in
the load list, or add a dependency to your manifest. The estimating
addon's `data` list is heavily commented — read the comments before
inserting new entries.

**"I added a field to `sale.order.line` and the BoM Preview tab is
now empty for every order."**

Computed fields that touch order_line and use `store=False` recompute
on access. If your new field's `@api.depends` chain raises, the line
silently returns an empty value. Inspect the Odoo log for a compute-
error stack from `_compute_sb_panel_rollup` or wherever the new field
landed. The fix is almost always a guard against missing
`product_id` or a missing variant attribute.

**"I want to add a fifth pricelist tier for tradesperson and the
auto-resolution doesn't pick it up."**

Three places to update simultaneously:
1. `res.partner.tradesperson_tier` selection (`models/res_partner.py`)
   — add `("4", "Tier 4 (-40%)")`.
2. `_TRADESPERSON_TIER_PRICELISTS` dict on `SaleOrder` (`models/
   sale_order.py`) — add `"4": "southbrook_estimating.pricelist_
   tradesperson_tier_4"`.
3. `data/pricelists.xml` — add the new pricelist + item record.

Forget one and the install succeeds but the resolution silently falls
back. The dispatcher is intentionally simple (table-driven) so
extensions are mechanical.

**"The Shop Copy PDF crashes with `AttributeError: 'super' object has
no attribute '_get_cut_constants'`."**

Someone refactored `mrp.bom` and dropped the
`_get_cut_constants()` method from `southbrook_estimating`. The
`southbrook_plm.mrp_bom._get_cut_constants` override calls `super()`
expecting the method to exist on the estimating addon. Per the
`southbrook_plm_deploy` memory: this seam was restored 2026-06-11
after exactly this regression. Re-add the method (lines ~72-89 of
`models/mrp_bom.py`) and verify with a confirmed MO BoM compute.

**"I added a new attribute and the view shows it but the rule that
restricts it isn't firing."**

`product.config.line` rules in `data/config_rules.xml` are keyed on
domain triggers. If your new attribute isn't covered by an existing
domain, you need to add a new `product.config.domain` +
`product.config.domain.line` pair AND a `product.config.line` record
referencing them. Then the OCA configurator wizard will enforce it.
The four canonical rules are: series→door (R1), box→series (R2),
width→door_count (R3), family_subtype→soft_close (R4).

## What the system is doing behind the scenes

When you save a new Order Builder record, the write hits several
layers in sequence:

1. **`sale.order` write** — Odoo writes `partner_id`, `pricelist_id`
   (already resolved by the onchange), `order_line` (with `zone`,
   `zone_label`, `product_id`, `product_uom_qty`).
2. **`_onchange_partner_id_southbrook_pricelist`** — triggered by the
   partner pick during entry, sets `pricelist_id`.
3. **`_compute_sb_panel_rollup`** — fires on access to
   `sb_panel_count`, `sb_door_count`, `sb_width_mm` per line. Walks
   variant attributes → falls back to `line.name` regex → falls back
   to family defaults.
4. On Confirm — **`action_confirm` override**: calls `super()` (which
   triggers `sale_mrp` to create `mrp.production` records), then
   `Analytics.capture(order)` writes one
   `southbrook.order.analytics` row.
5. The `mrp.production` records, when their BoMs are accessed, run
   `_compute_effective_produce_delay` which depends on
   `produce_delay` + `southbrook_lead_time_extra` (which itself
   depends on the variant's `product_template_attribute_value_ids.
   product_attribute_value_id.lead_time_extra`).

When the customer opens the 3D Kitchen Preview tab, the OWL
component calls `sale.order.get_kitchen_3d_payload()` via JSON-RPC.
That method loops `order_line`, looks up each line's SKU in
`_SKU_DEFAULTS`, calls `mrp.bom._compute_panel_dimensions` per
cabinet, then concatenates panels with per-zone X cursors (ground /
wall / island / other) and zone-specific Y floors (wall at 1400mm,
worktop at 762mm, etc.) into a single `panels` array with a
`metadata.lines` lookup keyed by line id for hover tooltips.

The PLM seam (`_get_cut_constants`) is what makes the math swap to
the active cut spec when `southbrook_plm` is installed. With no PLM
addon, the seam returns the NF14 baseline constants (BOX_TH=15.875,
DOOR_TH=18.0, etc.) declared at module-level in `models/mrp_bom.py`.
With PLM installed, the override returns the active
`southbrook.cut.spec` record's `constants_dict()`. Either way, the
same `_compute_panel_dimensions` math runs — the constants flow
through.

## Quiz (5 questions, applied)

**1.** Your estimator says "I added a Zone field on the order-line
list view and now the Subtotal at the bottom of each zone is the same
number for every zone." What did they break, and where do you look?

> They turned off `default_group_by="zone"` on the embedded list
> when they edited the view, or set it incorrectly. The grouping
> behaviour comes from xpath (5) in `views/sale_order_views.xml`
> setting `default_group_by="zone"` and `expand="1"` on
> `//field[@name='order_line']/list`. The per-zone subtotal comes from
> xpath (6) which sets `sum="Zone Subtotal"` on `price_subtotal`. If
> the grouping is off, every "zone" row shows the same total
> (because there is no grouping, just one big sum).

**2.** You're extending the addon with a new "show kitchen materials
summary" tab. Where in the inheritance graph does it go, and what's
the load-order risk?

> A new `<page>` injected inside `//notebook` via xpath in
> `sale_order_views.xml` (mirror the pattern of the
> `kitchen_3d_preview` page injection — same xpath pattern). The
> load-order risk: if your tab references a field on `sale.order` or
> `sale.order.line` that you also add in a new module, your view
> must load AFTER the model definition AND AFTER any other view
> that the field's xpath depends on. The estimating addon's
> `__manifest__.py` data list comments are the canonical guide.

**3.** Shop Copy PDF prints but the "Originating Order" row shows the
plain `mo.origin` string instead of the SO number-and-customer pair.
What's going on?

> The MO was created without a `sale_line_id` — either a manually-
> created MO, a demo fixture, or a sale_mrp wiring failure. The Shop
> Copy template (line ~40) does `t-set="so" t-value="mo.sale_line_id.
> order_id"` and falls back to `mo.origin or '—'` when `so` is empty.
> NF25 documented this. The recovery is to set `sale_line_id` on the
> MO if you know the originating SO line, or to accept the
> degraded display for manual MOs.

**4.** A developer asks "where does `southbrook_lead_time_extra` come
from on the BoM, and how does it become +2 weeks for maple box?"

> The chain: maple box's `product.attribute.value` has
> `lead_time_extra = 14.0` (set in `data/attributes.xml` per Q3).
> When a variant is materialised with maple box, the variant's
> `product_template_attribute_value_ids.product_attribute_value_id.
> lead_time_extra` is 14.0. `mrp.bom.southbrook_lead_time_extra`
> (computed, stored) sums those across all variant attributes:
> `bom.product_id.product_template_attribute_value_ids.mapped("...
> .lead_time_extra")`. `effective_produce_delay = produce_delay +
> southbrook_lead_time_extra` is what the Shop Copy displays.

**5.** Your team asks "is `southbrook.order.analytics` part of the
custom-routine register, and can I add an aggregation method to it?"

> Per the docstring in `southbrook_order_analytics.py`: NF1 carve-out
> — this model does NOT count against the 7-routine custom register
> in Build Spec §4. The register lists business-logic files. The
> analytics model is a thin schema + rollup-from-existing-fields
> capture hook (no decision-making, no math beyond
> `Counter.most_common()`). If you add a method that computes
> anything beyond rollup-from-existing-fields, that's the trigger to
> revisit the boundary — file it in PUNCHLIST.

---

## What this lesson does NOT cover

- The day-to-day estimator workflow — Lesson 5.2 (intro) and lessons
  8.2 (deep dive on the entry flow) and 8.3 (deep dive on pricing).
- The quote → MO handoff including the cut-spec snapshot — lesson 8.4.
- Report-by-report deep dive (when each is generated, what fields
  populate what cells) — lesson 8.5.
- Versioning + duplication mechanics — lesson 8.6.
- The OCA `product_configurator` internals — its own upstream docs
  cover that; we only extend.
- The companion `southbrook_estimating_website` addon (Phase 2,
  customer-facing one-page configurator) — not yet shipped.
- The Hermes trade-partner platform built on top of the Order Builder
  — `docs/superpowers/specs/2026-06-16-southbrook-os-and-hermes-platform-design.md`
  is authoritative for that surface.
