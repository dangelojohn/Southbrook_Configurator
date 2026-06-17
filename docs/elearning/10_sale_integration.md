---
course: 10 — Configurator Deep Dive
chapter: 10.4
title: Sale Flow Integration — How a Configured Product Lands on a Quote
duration: 40 minutes
audience: Estimator who wants to understand pricing + developer who needs to extend the sale.order.line.
prereqs: Course 5 (5.1, 5.2). Lesson 10.1 (architecture) + 10.3 (session state).
custom_modules: product_configurator_sale, website_product_configurator, southbrook_estimating, southbrook_configurator_ux
---

# Sale Flow Integration — How a Configured Product Lands on a Quote

## Who this lesson is for

You're an estimator who's seen the channel-pricelist switcher work
and wants to know **why** it works — what's happening in the code
when a Richwood partner becomes a retail walk-in and the price
changes without re-running the configurator. Or you're a dev who's
been asked to "make the line carry an extra field so the cut-spec
gets snapshotted at commit time" and you need to know which method
to override. Either way, this lesson is the sale-side bridge: from
the `product.config.session` that the wizard produces, all the way
to the `sale.order.line` the estimator sees on the quote.

## Where this lives on the site

The estimator's primary surface:

> **Sales → Quotations** — every draft order. Each line either is or
> isn't configurable depending on `product_id.config_ok`.

The configurable trigger is everywhere a configurable product
appears:

> Any `sale.order.line` whose product is `config_ok = True` shows a
> **Configure** button and a **Reconfigure** button. Internally these
> map to `action_config_start()` (on `sale.order`) and
> `reconfigure_product()` (on `sale.order.line`).

The customer-facing portal:

> **`/my/southbrook/order-builder/<id>`** — where the v2 chip UI
> `Add to Quote` lands after commit. Not the e-commerce
> `/shop/cart`. The decision was locked in CLAUDE.md Phase 2 (Decision
> A) — configured lines go to the Order Builder, not the website_sale
> cart.

## What your screen shows

A `sale.order.line` for a configured cabinet carries the OCA-extended
fields:

- **`product_id`** — the materialised `product.product` variant
  (created by `session.create_get_variant`).
- **`config_ok`** — related field from `product_id.config_ok`. Tells
  the UI to render Configure / Reconfigure buttons.
- **`config_session_id`** — Many2one to `product.config.session`.
  The session that produced this line; one done session per line,
  reusable for reconfigure-spawned new sessions.
- **`custom_value_ids`** — related from `config_session_id.custom_value_ids`.
  Surfaces free-text custom values (engraving, dimensions) onto
  the line.
- **`price_unit`** — **overridden**: reads `config_session_id.price`
  (the configurator-resolved price) instead of the native variant
  list_price. This is the single most load-bearing override in the
  bridge — it's how Maple's +10% lands on the quote.

The order header carries the channel resolution:

- **`pricelist_id`** — set from `partner_id.property_product_pricelist`,
  which Southbrook computes from `partner.channel` (Dealer / Tradesperson
  / KD / Big-Box / Refacing / Retail per Q1 lock).
- The `southbrook_estimating` overlay adds zone aggregation and the
  stage pipeline (Draft → Estimating → Approval → Confirmed → In
  Production).

## Your daily flow

You build quotes; behind every click is one of four bridge code
paths. Knowing which makes you faster at debugging "the price is
wrong" or "the line isn't carrying the right session."

**1. Adding a new configured line via the Order Builder.**

You hit **Add Cabinet** on the order. The picker (filtered by
`config_ok=True AND sale_ok=True`) shows configurable templates. You
pick "Vanity 24in Elegance Fluted" (your Lesson 10.2 work). Odoo:

1. Inserts a draft `sale.order.line` with `product_id = <template's
   default variant or False>` and `product_uom_qty = 1`.
2. Because `config_ok = True` on the product, the UI doesn't
   auto-confirm — instead it surfaces a Configure button.
3. You hit Configure. `sale.order.line.action_config_start` — wait,
   no: on the line, the action is `sale.order.action_config_start`,
   which is the **header-level** entry point. The line-level entry is
   `reconfigure_product`. The first-config flow uses
   `product.template.create_config_wizard(model_name='product.configurator.sale', extra_vals={...})`
   under the hood.
4. The wizard opens (the OCA backend wizard, generated dynamically
   from `attribute_line_ids`). You step through the 11 attributes.
5. On Finish, the wizard's transient model writes the
   `product.config.session.value_ids`, calls `session.action_confirm`,
   which calls `session.create_get_variant` — variant is materialised
   if not already existing — and `_check_product_id` enforces the
   link.
6. The wizard returns; Odoo writes back to the sale.order.line:
   `product_id = variant`, `config_session_id = session`,
   `price_unit` recomputes via the override.

**2. Reconfiguring an existing line.**

You realise the customer wanted a different finish. You click
Reconfigure on the line. `sale.order.line.reconfigure_product()`
runs:

```python
extra_vals = {
    "order_id": self.order_id.id,
    "order_line_id": self.id,
    "product_id": self.product_id.id,
}
return self.product_id.product_tmpl_id.create_config_wizard(
    model_name="product.configurator.sale",
    extra_vals=extra_vals,
)
```

This spawns a **new** session prefilled from the existing variant.
The wizard opens with the customer's prior picks. You change Finish,
hit Finish. The new session reaches `state='done'`, materialises a
**different** variant (or finds the existing one if the picks happen
to match another variant), updates the line's
`product_id`, `config_session_id`, `price_unit`. The old session
stays at `state='done'` — you have a permanent record of the
pre-change configuration.

**3. Switching the customer (channel resolution).**

You change `partner_id` on the order header from Richwood (Dealer
channel, -35% pricelist) to Retail Walk-In. Odoo's
`sale.order.onchange_partner_id` swaps the order's `pricelist_id` to
the retail base list. Every line's `price_unit` recomputes — but the
override reads `config_session_id.price`, NOT
`product_id.list_price`. So what's the rule of thumb?

`session.price` is **base list_price + sum(picked PTAV price_extras)**
— it is a pricelist-naive number. The channel pricelist is applied
on top by Odoo's standard pricelist resolution, taking
`session.price` as the input price. **That's the locked smoke test
in CLAUDE.md §9: switching partner re-prices the line without
re-running the configurator.** It works because the override fixes
the base price; the pricelist still operates as native Odoo.

**4. Confirming the order → spawning an MO.**

Standard Odoo confirms the order (state `draft → sale`). The MO
spawn from the configurable line uses
`product_configurator_mrp/models/mrp.py:MrpProduction` — which
inherits to add `config_ok`, `config_session_id`, and `custom_value_ids`.
The MO records the session that produced the variant; Lesson 10.5
walks the BoM rollup.

## Common mistakes + how to recover

**"I changed the customer and the price didn't update."**

Three suspects:
- The line was confirmed (`sale.order.state = sale` or higher). Once
  confirmed, `_compute_price_unit` is gated; it doesn't re-fire on
  partner switch. Recovery: revert to draft (`action_draft`) or
  duplicate the order with the new customer.
- The partner doesn't have `property_product_pricelist` set. The
  channel resolution in `southbrook_estimating` reads
  `partner.channel` → resolves to a pricelist; if the partner record
  is mid-migration and the field is null, no pricelist applies and
  the line falls back to retail.
- The line's `config_session_id` is null (it was added before being
  configured, or via a non-configurator path). Without the session,
  the price-unit override no-ops and Odoo's default pricing applies
  — which may or may not reflect what you expect.

**"Re-configure spawns a new session but the old session's data is
lost."**

It isn't — the old session is still there, `state='done'`,
`product_id` pointing at the old variant. The line now points at the
new session + new variant. To audit history, browse all sessions for
the order: `env["product.config.session"].search([("user_id.partner_id",
"=", order.partner_id.id), ("write_date", ">=", order.create_date)])`.

**"A line has price_unit = 0 even though the variant has list_price = 295."**

The `_compute_price_unit` override (line 62 of
`product_configurator_sale/models/sale.py`) returns the
session's `price` if `config_session_id` is set, which can be 0 if
the session has no values picked yet. Likely the line was added but
Configure was never finished — `config_session_id` was set early in
the flow and never reached `state='done'`. Recovery: complete the
configuration via Reconfigure.

**"The 'custom value' the customer typed (their initials) shows on
the line but not on the printed PDF."**

The PDF template renders from `sale.order.line.name` or the
variant's `display_name`. Custom values are surfaced via
`_get_sale_order_line_multiline_description_variants` (line 77 of
`product_configurator_sale/models/sale.py`) — which appends them to
the description. If your PDF QWeb uses `line.name` only without
calling that helper, custom values won't print. Fix: edit the QWeb
to include `line._get_sale_order_line_multiline_description_variants()`,
or use `line.name` which is normally pre-populated with it.

**"Customer hit Add to Quote on `/shop/<slug>` but their order is
empty."**

Check `southbrook_configurator_ux/controllers/main.py:configurator_commit`
(line 568). The flow is: validate session → create_get_variant →
resolve or create the user's draft sale.order → create the line.
The most common failure point: the partner has no draft order AND
the resolve-or-create fell through to AccessError because the
partner doesn't have sale ACL on `sale.order` create. Public
visitors hit `login_required` first — but a portal user without
proper sale ACL gets a different failure. Diagnose by running the
commit path in the shell with the user as the request user
(`with_user(partner.user_ids[:1])`).

**"The line shows the right SKU but my BoM-driven cut list missed
the Maple price extra."**

The `_compute_price_unit` override reads
`config_session_id.price`, which is correct for the **quote price**.
But the BoM rollup (via `product_configurator_mrp.create_get_bom`)
reads bomline products + their costs. Maple's +10% is a price_extra
on the PTAV; it doesn't flow into the BoM as a cost line. The
quote shows +10%, the MO cost report shows the raw component cost.
**This is intentional separation** but a frequent surprise — Lesson
10.5 covers it in depth.

## What the system is doing behind the scenes

The bridge is **3 inheritance hops** plus **1 model addition**.

The **3 inheritance hops** (all in `product_configurator_sale/models/sale.py`):

```python
class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_config_start(self):
        """Header-level Configure entry — opens the
        product.configurator.sale wizard with allow_preset_selection=True
        so the user can pick a preset."""
        configurator_obj = self.env["product.configurator.sale"]
        ctx = dict(self.env.context,
                   default_order_id=self.id,
                   wizard_model="product.configurator.sale",
                   allow_preset_selection=True)
        return configurator_obj.with_context(**ctx).get_wizard_action()


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    custom_value_ids = fields.One2many(
        comodel_name="product.config.session.custom.value",
        inverse_name="cfg_session_id",
        related="config_session_id.custom_value_ids",
    )
    config_ok = fields.Boolean(
        related="product_id.config_ok", readonly=True)
    config_session_id = fields.Many2one(
        comodel_name="product.config.session")

    def reconfigure_product(self):
        wizard_model = "product.configurator.sale"
        extra_vals = {
            "order_id": self.order_id.id,
            "order_line_id": self.id,
            "product_id": self.product_id.id,
        }
        return self.product_id.product_tmpl_id.create_config_wizard(
            model_name=wizard_model, extra_vals=extra_vals)

    @api.depends("config_session_id", "tax_ids", "company_id")
    def _compute_price_unit(self):
        result = None
        for line in self:
            if line.config_session_id:
                line.price_unit = self.env["account.tax"]._fix_tax_included_price_company(
                    line.config_session_id.price,
                    line.product_id.taxes_id,
                    line.tax_ids,
                    line.company_id,
                )
            else:
                result = super()._compute_price_unit()
        return result
```

The **model addition** is the transient wizard
`product.configurator.sale` (in
`product_configurator_sale/wizard/product_configurator.py`) — a
subclass of the OCA `product.configurator` transient. Same wizard
machinery, just typed for sale.

The **website cart bridge** is in `website_product_configurator/models/sale_order.py`:
three overrides — `_cart_update_order_line`, `_cart_find_product_line`,
`_prepare_order_line_values` — that thread `config_session_id`
through the website_sale add-to-cart pathway. This is what makes the
e-commerce `/shop/cart` flow work with configurable products. The v2
Southbrook commit bypasses this entirely by writing directly to
`sale.order.line.create` in the controller — the cart bridge is
unused on the v2 path.

The **price computation** chain:

1. Wizard finish → `session.action_confirm` → `validate_configuration()` →
   `create_get_variant()`.
2. `create_get_variant` writes `state='done'`, `product_id=variant`.
3. Calling code writes `sale.order.line.config_session_id = session`.
4. `_compute_price_unit` fires (depends on `config_session_id`),
   reads `session.price`.
5. `session.price` is the computed field from `_compute_cfg_price`,
   which calls `get_cfg_price()` (line 996), which sums
   `tmpl.list_price` + sum of PTAV `price_extra` for picked values.
6. `_compute_price_unit` further wraps with
   `account.tax._fix_tax_included_price_company` to normalise
   tax-included pricing across companies.
7. Native Odoo pricelist resolution then maps `price_unit` against
   the order's `pricelist_id` for the customer-displayed price.

The **`southbrook_estimating` overlay** — the Order Builder — adds
zone aggregation and the stage pipeline on top of `sale.order`. It
does NOT replace the bridge above; it sits next to it. Zone is a
free-text + selection field on `sale.order.line` per Q21; the stage
pipeline is `southbrook_submitted_date` + a state machine on the
order header.

## Quiz (5 questions, applied)

**1.** An estimator builds a 12-line quote against Richwood (Dealer
channel). They click on the partner field, switch to a Retail walk-in.
The total drops by less than expected — they were anticipating a
50% jump, got 35%. What's likely happening?

> The partner switch is firing `_compute_price_unit` via the
> `config_session_id` dependency chain on every line — each line's
> price_unit recomputes from `session.price`. But the
> session.price is base + PTAV extras, NOT discounted. The
> pricelist applies on top. If the Retail pricelist is in the
> middle of being authored (some items have items rules, some
> don't), only the items with matching `product.pricelist.item`
> rules get retail pricing; the others fall through to the
> session.price unchanged. Audit the retail pricelist; ensure
> every configurable cabinet template has a coverage rule.

**2.** You add a new field `cut_spec_version` to `sale.order.line`
in `southbrook_estimating`. You want it to be set automatically at
commit time from the session's variant's spec. Where do you put the
write?

> Override `sale.order.line._compute_price_unit` (or add a new
> compute on `cut_spec_version` with `@api.depends('config_session_id',
> 'config_session_id.product_id')`). The
> `southbrook_configurator_ux/controllers/main.py:configurator_commit`
> path also explicitly calls a hook
> `line._capture_southbrook_version_snapshots()` if it exists —
> that's the canonical extension point for commit-time snapshots
> (see line 740 in the controller). Implement that method on
> `sale.order.line` in `southbrook_estimating`; the controller
> calls it for free, with a non-fatal try/except wrapper.

**3.** A configured line on a confirmed order shows
`config_session_id = False`. The variant looks right. What
happened, and is it recoverable?

> Likely the order was confirmed via a code path that bypassed
> the wizard — e.g. duplicated from an older order, or imported.
> The variant carries the PTAV values; the session record never
> existed for this line. Recoverable only if you create a new
> session retroactively (browse template, create session, write
> value_ids from the variant's PTAVs, action_confirm with the
> existing variant). Easier: tell the estimator to Reconfigure
> the line, which spawns a fresh session prefilled from the
> variant.

**4.** A customer commits a configuration on `/shop` and the
controller log shows `session.action_confirm failed on session 873`.
The line was created. What's the user-facing impact, and what
cleanup do you run?

> The variant + line exist with correct product_id and price; the
> session stays draft with no product_id. The customer sees their
> quote correctly. Operational impact: the session won't be
> retrievable as a `done` audit trail; the next GC cron sweeps it
> in 3-7 days. Cleanup: in the shell, find the session
> (`Session.search([("user_id", "=", customer_user.id),
> ("state", "=", "draft"), ("write_date", ">=", order.create_date)])`)
> and either complete it manually (`session.action_confirm(product_id=
> line.product_id)`) for a clean audit trail, or let GC clean it
> up.

**5.** You're asked to make the configurable line carry a
"DesignedBy" field linking to the designer (a `res.users`) who
authored the configuration. The customer's user must be visible
only at the order level; the designer is who clicked through the
wizard. Where do you store it?

> On `sale.order.line` directly. Add a `designed_by_user_id`
> Many2one field on `sale.order.line` in `southbrook_estimating`.
> Wire it via the controller's commit path or via the OCA wizard's
> finish step — `session.user_id` is the designer in your case
> (the user driving the wizard), so on commit you write
> `line.designed_by_user_id = session.user_id`. Don't store on the
> session — sessions can be re-used across users in some flows
> (reconfigure spawned from a shared variant). Line-level binds
> the attribution to the actual line you're auditing.

---

## What this lesson does NOT cover

- Configurator vocabulary basics — Course 5, Lesson 5.1.
- 5-addon architecture — Lesson 10.1.
- Setting up a new configurable product — Lesson 10.2.
- Session state machine — Lesson 10.3.
- MRP integration (BoM rollup, MO creation, configuration sets) —
  Lesson 10.5.
- V2 UX OWL internals (the `/state|/select|/commit` JSON-RPC
  contract) — Lesson 10.6.
- Common gotchas (rule ordering, exclusion explosion, performance) —
  Lesson 10.7.
- Native Odoo sale.order pipeline, pricelists, taxes, multi-company —
  Odoo's own native eLearning track.
