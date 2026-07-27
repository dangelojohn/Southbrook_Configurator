---
course: 10 — Configurator Deep Dive
chapter: 10.1
title: Configurator Architecture — The 5-Addon Stack, Layer by Layer
duration: 45 minutes
audience: Developer extending the configurator + senior admin who owns the catalog. You know what `_inherit` means; you've installed a custom module before.
prereqs: Course 5 (lessons 5.1, 5.2, 5.4). You can configure a cabinet end-to-end through the OCA wizard and through the v2 surface.
custom_modules: product_configurator, product_configurator_sale, product_configurator_mrp, website_product_configurator, southbrook_configurator_ux
---

# Configurator Architecture — The 5-Addon Stack, Layer by Layer

## Who this lesson is for

You're a developer or senior admin who needs to **change** the
configurator — add a new attribute, write a new business rule, surface
a new field to the wizard, debug a session that won't validate. You've
done the basics in Course 5 (5.1, 5.2, 5.4) and the surface vocabulary
makes sense. Now you need the map: which addon owns which model, where
the layering breaks if you cross addons in the wrong order, what gets
loaded into the registry when you run `-u product_configurator`. This
lesson is the architecture pass — you read it once, then you stop
guessing where to put code.

## Where this lives on the site

You don't navigate to a screen to "see" the architecture — it's the
shape of the stack. But three reference points anchor everything else:

> **Sales → Configurable Products → Configurable Templates** — every
> `product.template` with `config_ok = True`. The catalog of what the
> configurator can configure.

> **Sales → Configuration → Configuration Rules** — every
> `product.config.line` record. The rule catalog.

> **Sales → Configuration → Configuration Sessions** — every
> `product.config.session` record. Every wizard visit ever, draft +
> done.

The dev shell (`odoo-bin shell -d <db>`) is where you'll spend more
time once you actually need to debug a session — see Lesson 10.3.

## What your screen shows

The 5-addon dependency graph (read top-down):

```
                 product_configurator        (OCA base)
                          │
            ┌─────────────┼─────────────────┐
            ▼             ▼                 ▼
  product_configurator_sale  product_configurator_mrp
  (sale.order bridge)        (mrp.bom bridge)
            │
            ▼
  website_product_configurator   (auto_install with sale stack)
            │
            ▼
  southbrook_configurator_ux     (Southbrook v2 overlay)
```

Each box is one addon; each arrow is a `depends` line in
`__manifest__.py`. **Read the arrows as "if you uninstall the
upstream, the downstream goes too."** Uninstall `product_configurator`
and the entire chain unloads.

What each addon adds — the **delta**:

- **`product_configurator/`** (OCA base, AGPL-3, v19.0.1.0.0). Defines
  the entire model layer. Adds `config_ok`, `attribute_line_ids` rules,
  `config_line_ids`, `config_step_line_ids`, `config_image_ids` to
  `product.template`; defines `product.config.domain`,
  `product.config.domain.line`, `product.config.line`,
  `product.config.image`, `product.config.step`,
  `product.config.step.line`, `product.config.session`,
  `product.config.session.custom.value` as **new** models. Adds the
  backend wizard at `wizard/product_configurator.py` (the `product.configurator`
  transient model) and the menu (`data/menu_configurable_product.xml`).
  No sale, no MRP, no website knowledge.
- **`product_configurator_sale/`** (auto_install on `sale_management`).
  Inherits `sale.order` to add `action_config_start()` (the Configure
  button on draft orders) and `sale.order.line` to add `config_ok`,
  `config_session_id`, `custom_value_ids` (related), plus
  `reconfigure_product()` and a price-unit override that reads
  `config_session_id.price` instead of the variant list price. Adds the
  `product.configurator.sale` transient wizard subclass at
  `wizard/product_configurator.py`. **No MRP knowledge** — sale and
  manufacturing are kept independent.
- **`product_configurator_mrp/`**. Inherits `mrp.production`,
  `mrp.bom`, `mrp.bom.line` to add `config_ok` + `config_session_id`.
  Defines two **new** models — `mrp.bom.line.configuration.set` and
  `mrp.bom.line.configuration` — that wire BoM lines to attribute
  values so a parent BoM can conditionally include / exclude lines per
  configuration. Inherits `product.config.session` to add
  `create_get_bom()` and override `create_get_variant()` so every new
  variant from the configurator also gets a `mrp.bom` (Lesson 10.5
  walks the rollup mechanics).
- **`website_product_configurator/`**. Inherits `product.template` to
  add `_to_markup_data()` (schema.org JSON-LD); inherits `sale.order`
  to override `_cart_update_order_line`, `_cart_find_product_line`,
  `_prepare_order_line_values` so the e-commerce cart respects
  `config_session_id`; inherits `product.config.session` to add
  `remove_inactive_config_sessions()` (the second cron — see "Behind
  the scenes" below); inherits `product.config.step.line` to add a
  per-step QWeb template field. Defines the `/configurator/...` route
  family in `controllers/main.py` and the customer portal "My
  configurations" pages in `controllers/portal.py`.
- **`southbrook_configurator_ux/`** (LGPL-3, Southbrook). Inherits the
  OCA `website_product_configurator.product_configurator` QWeb template
  via `views/configurator_template.xml` (one xpath, position="replace"
  on `//section[@id='unique_product_configurator']`). Ships the OWL
  `ConfiguratorV2` component + a separate JSON-RPC controller at
  `/southbrook/api/configurator/state|select|commit` and an import
  pipeline at `/southbrook/api/import/template|preview|commit`. Adds
  three **data** files: `tactical_price_extras.xml` (price_extra +
  weight_extra seed), `catalog_expansion.xml` (~40 catalog templates),
  `rule_completion.xml` (fills OCA `product.config.line` gaps).

## Your daily flow

You won't be installing these every day — but every change you make
follows the same layering discipline. The five most common operations
and where they belong:

**1. "I want to add a new attribute (e.g. 'Toe Kick Height')."**

The attribute itself is a `product.attribute` record. It lives in
**data**, not Python. Where?

- If the attribute is **Southbrook-specific** (every cabinet uses it,
  it's part of the brand offering) → it belongs in
  `southbrook_estimating/data/attributes.xml`.
- If it's a **generic configurator concept** (display_type extension,
  uom binding) → upstream `product_configurator/data/product_attribute.xml`,
  but you don't touch that. You'd file a PR against OCA.

You then bind the attribute to one or more templates by creating
`product.template.attribute.line` records. Those records also live in
data — usually `southbrook_estimating/data/product_templates.xml` or
the catalog-expansion in `southbrook_configurator_ux/data/catalog_expansion.xml`.

**2. "I want to add a new business rule."**

Rules are `product.config.line` records linking a template, an
attribute_line, blocked value_ids, and a domain trigger
(`product.config.domain` + lines). You author them as **XML data**,
not Python overrides. The four canonical Southbrook rules are in
`southbrook_estimating/data/config_rules.xml`; the catalog-expansion
backfills (e.g. Contemporary + Elegance allowed combinations) are in
`southbrook_configurator_ux/data/rule_completion.xml`.

The acceptance test (CLAUDE.md §9): `grep -rn 'if series ==' addons/southbrook_estimating/models/`
returns **zero** hits. Every rule is declarative.

**3. "I want to add a price extra to a value (e.g. brushed nickel pulls +$8)."**

The price extra lives on `product.template.attribute.value` — the
OCA model auto-creates one row per (template, value) pair. The value
itself is `product.attribute.value`. Set `price_extra` (and
`weight_extra` if the part adds weight). Currently seeded by
`southbrook_configurator_ux/data/tactical_price_extras.xml` as a
demo-grade backfill — this is TBD-move-to-southbrook_estimating per
the manifest comment.

**4. "I want to expose the wizard a new way (a new surface like 3D)."**

You write a **new** addon depending on `product_configurator` (for the
session model) and probably `product_configurator_sale` (to drop the
configured line on a sale.order). The OCA wizard form lives at
`wizard/product_configurator.py` — that's the backend transient. The
website v1 form lives in `website_product_configurator/views/templates.xml`
+ `controllers/main.py`. The Southbrook v2 chip-UI lives in
`southbrook_configurator_ux/static/src/js/configurator.esm.js` +
its own JSON-RPC controllers. **None of these touch the four upstream
addons in place** — they all extend via inheritance + a new asset
bundle. The CLAUDE.md §3 contract.

**5. "I want to debug why a configurator session won't validate."**

Run `odoo-bin shell -d <db>`, browse the session, call
`session.validate_configuration()`. Read the exception. The OCA
machinery is described step-by-step in Lesson 10.3, but the entry
point is always the same: a session record + its `validate_configuration()`
method (defined at `product_configurator/models/product_config.py` line
1482) on top of `values_available()` (line 1377).

## Common mistakes + how to recover

**"I added a model field on `product.config.session` in
`southbrook_estimating` but it's not appearing in the OCA wizard."**

The OCA wizard form is generated **dynamically** by
`wizard/product_configurator.py:_fields_view_get()` from the
template's `attribute_line_ids` — not from the
`product.config.session` model's `fields`. Adding a field on the
session doesn't auto-add it to the wizard. If you want it in the
wizard, you have to (a) inherit the wizard transient model
(`product.configurator`) and add the field there, AND (b) inherit the
wizard view to render it. There is no shortcut.

**"I added a new attribute and the install fails with `value_ids` empty."**

Every `product.template.attribute.line` must have at least one
`value_ids`. The Odoo 19 `_validate_layout` raises NF19 ("attribute
line has no values") at install if any line is empty. Fix: add at
least one `product.attribute.value` to the new attribute before
binding it to a template.

**"I inherited `product.config.session` in my new module and the
override isn't firing."**

Check your `depends` in `__manifest__.py`. If you forgot to depend on
`product_configurator`, Odoo loads your model in alphabetical order
and your `_inherit` finds an empty registry entry. Fix the manifest;
re-run `-u <your_addon>`.

**"I uninstalled `southbrook_configurator_ux` and the customer-facing
page broke, not just the styling."**

The OCA template was reverted — the body of
`website_product_configurator.product_configurator` is gone because
the inheritance was the body markup. The OCA stock layout comes back
**immediately**. If it didn't, check `web.assets_frontend` — a stale
asset bundle may need a `--update-assets` pass. Reinstall
`southbrook_configurator_ux` to recover.

**"I added a rule to `rule_completion.xml` and customers can still pick
the forbidden combination."**

The `product.config.line` record only fires when its `domain_id`
trigger evaluates True. Common bug: you wrote the domain with the
wrong attribute_id reference (you used the value's name string
instead of the XML id). Symptom: the rule loads, but never fires.
Fix: re-check the `<field name="attribute_id" ref="..."/>` in the
domain.line record matches the attribute you meant.

## What the system is doing behind the scenes

The five addons compose into one logical machine. The **model layering**
top-to-bottom (which addon defines what):

| Model | Defined by | Extended by |
|---|---|---|
| `product.template` (base) | `account`/`stock` | `product_configurator` (+config_ok, attribute_line_ids rules), `website_product_configurator` (+_to_markup_data) |
| `product.template.attribute.line` (base) | `product` | `product_configurator` (+default_val, +rule eval helpers) |
| `product.attribute` (base) | `product` | `product_configurator` (+required, +multi, +sequence, +uom_id, +custom_type, …) |
| `product.attribute.value` (base) | `product` | `product_configurator` (+product_id, +active, +image) |
| `product.config.domain` | `product_configurator` | — |
| `product.config.domain.line` | `product_configurator` | — |
| `product.config.line` | `product_configurator` | — |
| `product.config.image` | `product_configurator` | — |
| `product.config.step` | `product_configurator` | — |
| `product.config.step.line` | `product_configurator` | `website_product_configurator` (+website_tmpl_id, +get_website_template) |
| `product.config.session` | `product_configurator` | `product_configurator_mrp` (+sanitized_spec, +create_get_bom, override create_get_variant), `website_product_configurator` (+remove_inactive_config_sessions, +get_config_form_website_template) |
| `product.config.session.custom.value` | `product_configurator` | — |
| `product.product` | `product` | `product_configurator` (+config_name, +config_ok, +product_template_attribute_value_ids overrides) |
| `sale.order` | `sale_management` | `product_configurator_sale` (+action_config_start), `website_product_configurator` (+_cart_* overrides) |
| `sale.order.line` | `sale` | `product_configurator_sale` (+config_ok, +config_session_id, +custom_value_ids, +reconfigure_product, +_compute_price_unit) |
| `mrp.production` | `mrp` | `product_configurator_mrp` (+config_ok, +config_session_id, +custom_value_ids, +action_config_start, +reconfigure_product) |
| `mrp.bom` | `mrp` | `product_configurator_mrp` (+config_ok) |
| `mrp.bom.line` | `mrp` | `product_configurator_mrp` (+config_set_id) |
| `mrp.bom.line.configuration.set` | `product_configurator_mrp` | — |
| `mrp.bom.line.configuration` | `product_configurator_mrp` | — |

**Two GC crons run on `product.config.session`** — one is OCA's
upstream, one is the Southbrook-website extension:

- `product_configurator.ir_cron_gc_draft_sessions` — daily, calls
  `_gc_draft_sessions()`. Deletes draft sessions older than
  `ir.config_parameter product_configurator.session_gc_days` (default
  7 days). Sessions referenced by `sale.order.line.config_session_id`
  are protected (TBD: confirm by reading `_gc_draft_sessions`).
- `website_product_configurator.cron_delete_sessions_with_no_activity` —
  daily, calls `remove_inactive_config_sessions()`. Hard-coded 3-day
  threshold (not configurable), targets draft sessions only. **Notice
  the two crons disagree on threshold** — a draft session older than
  3 days gets deleted by the website cron before the OCA 7-day cron
  sees it. Lesson 10.3 covers the interplay.

**Asset bundle layering** (what JS / SCSS loads when):

- `web.assets_backend` — `product_configurator`'s form widgets +
  boolean buttons + kanban widgets + list widgets; `product_configurator_mrp`'s
  config-button mixin + list/kanban/form controllers + the
  mrp_production_views XML overlay. Backend-only.
- `web.assets_frontend` — `website_product_configurator`'s config_form
  JS + website_sale JS + config_form SCSS + tooltip SCSS, then
  `southbrook_configurator_ux`'s configurator.scss + configurator.esm.js
  (the OWL component) — in that order, because the SCSS depends on
  tokens defined upstream.
- `web.assets_tests` — `website_product_configurator`'s tour test.

The **registry boot order** at install: Odoo loads modules in
topological order. `product_configurator` first → `product_configurator_sale`
(auto_install=True so it lands once `sale_management` is present) +
`product_configurator_mrp` → `website_product_configurator` →
`southbrook_estimating` → `southbrook_configurator_ux`. If you break
the topology (e.g. circular `depends`) the registry refuses to load
and `odoo-bin` raises `KeyError`.

## Quiz (5 questions, applied)

**1.** You want to add a Southbrook-specific field
`cut_spec_revision` to `product.config.session` so the BoM rollup can
freeze the spec revision at commit time. Which addon do you put the
`_inherit = 'product.config.session'` class in, and why not the OCA
base?

> Put it in `southbrook_estimating` (or a new Southbrook-side addon if
> the spec is engineering-scoped). NEVER in `product_configurator/` or
> `product_configurator_mrp/` — those are the OCA upstream, and the
> CLAUDE.md §3 contract forbids in-place edits because Southbrook must
> stay able to pull OCA updates cleanly. The reason it's not
> `southbrook_configurator_ux`: that addon is the customer-facing UX
> overlay; engineering state on the session belongs with the
> estimating engine, not the UX skin.

**2.** A junior dev adds a new `product.config.line` rule to
`southbrook_configurator_ux/data/rule_completion.xml`. They install,
test on `base_2dr`, the rule fires correctly. The next morning they
add a rule to `data/catalog_expansion.xml`. It doesn't fire on
fresh catalog templates. What did they likely get wrong?

> Load-order. The manifest's `data` list loads
> `tactical_price_extras.xml` → `catalog_expansion.xml` →
> `rule_completion.xml`. The new rule in `catalog_expansion.xml` is
> being processed BEFORE the catalog template records that it
> references — so the `product_tmpl_id` ref points at a record that
> doesn't yet exist when the rule loads, and the rule silently
> doesn't bind. Fix: move the rule into `rule_completion.xml` (which
> loads after the catalog), or split it into a 4th file that loads
> last.

**3.** A customer reports their cart shows the same configured
cabinet on two lines instead of incrementing qty. You confirm both
lines reference the same `product.product` variant. Which addon's
override is involved, and what behaviour is intentional vs. a bug?

> `website_product_configurator/models/sale_order.py:_cart_find_product_line`.
> This override filters by `config_session_id` — by design two cart
> adds with **different** sessions land on **different** lines even
> when the variant id matches, because each session can carry
> different `custom_value_ids` (a free-text engraving, an uploaded
> photo, etc.). That's intentional. The bug is if both lines have
> the SAME `config_session_id` AND the same variant — that means the
> session is being re-used twice instead of `action_confirm` locking
> it to `state='done'`. Open the session, check `state` — if it's
> still `draft`, the commit path failed quietly.

**4.** You add a new transient model `southbrook.configurator.sale.gather`
that orchestrates a multi-cabinet wizard. It depends on
`product_configurator_sale`. At install you get
`KeyError: 'product.configurator.sale'`. Diagnose.

> Your `depends` is missing `product_configurator_sale` OR
> `product_configurator_sale.auto_install` flipped to False on this
> environment so it never installed. The `product.configurator.sale`
> transient wizard model only exists once `product_configurator_sale`
> is installed. The auto_install flag depends on `sale_management`
> being present at install time. Check `Apps → Apps`, filter
> "configurator", confirm Sale is green.

**5.** Why does `product_configurator_sale` define `_compute_price_unit`
to read from `config_session_id.price` instead of letting Odoo
compute price from the variant's list price + pricelist?

> Because the configurator's price isn't just the variant's
> `list_price` — it's `list_price` + sum of all
> `product.template.attribute.value.price_extra` for the picked
> values + custom-value handling. The session computes that
> aggregate in `get_cfg_price()` and caches it in `session.price`.
> If sale.order.line fell back to native Odoo pricing it would lose
> the +10% Maple, +$8 brushed nickel, +$x custom engraving extras.
> The override is what makes the channel pricelist resolve against
> the **configured** price, not the bare list price.

---

## What this lesson does NOT cover

- Configurator basics (attributes, values, exclusions) — Course 5,
  Lesson 5.1.
- Setting up a new configurable product from scratch — Lesson 10.2.
- The session state machine + debugging stuck sessions — Lesson 10.3.
- Sale-flow integration in depth (channel pricing, line snapshots) —
  Lesson 10.4.
- MRP-flow integration in depth (BoM rollup, configuration sets) —
  Lesson 10.5.
- The v2 UX OWL component internals — Lesson 10.6.
- Common gotchas + recovery patterns — Lesson 10.7.
- General OCA `product_configurator` administration — the OCA module's
  own docs at https://github.com/OCA/product-configurator.
