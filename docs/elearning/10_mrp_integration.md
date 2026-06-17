---
course: 10 — Configurator Deep Dive
chapter: 10.5
title: MRP Flow Integration — From Configured Variant to Manufacturing Order
duration: 45 minutes
audience: Production planner who watches BoMs land in Manufacturing + developer who needs to extend the BoM rollup.
prereqs: Course 5 (5.1). Lessons 10.1 (architecture), 10.3 (sessions), 10.4 (sale flow). Native Odoo MRP basics (you can confirm an MO).
custom_modules: product_configurator_mrp, southbrook_estimating
---

# MRP Flow Integration — From Configured Variant to Manufacturing Order

## Who this lesson is for

You're a production planner: a confirmed sale.order has just landed
in your queue and you need to know why one configured cabinet shows
up with 23 BoM lines and another shows 6 — when nobody changed the
template. Or you're a developer: the team has asked you to add a
fifth construction-rule case where a 36-in cabinet gets an extra
shelf-support cleat in the BoM, and you don't know whether that
belongs in `southbrook_estimating` or `product_configurator_mrp`.
Either way: this lesson is the MRP-side bridge. From the
`product.config.session` to the `mrp.bom` and finally the
`mrp.production` MO.

## Where this lives on the site

The MO and BoM list views:

> **Manufacturing → Operations → Manufacturing Orders** — every MO,
> draft → confirmed → done. Configurable MOs carry a Configure
> button on the line per the `product_configurator_mrp` overlay.

> **Manufacturing → Products → Bills of Materials** — every BoM.
> Configurable templates can have a **parent BoM** (one with
> `product_id = False`) that acts as the rollup template, plus
> per-variant BoMs created automatically on commit.

The configuration-set catalog (rarely visited but load-bearing):

> **Manufacturing → Configuration → BoM Line Configuration Sets** —
> `mrp.bom.line.configuration.set` records. Each is a named group of
> conditional BoM lines keyed by attribute values. This is the magic
> that lets one parent BoM serve many variants.

## What your screen shows

A configured variant's BoM has the standard `mrp.bom` fields plus
the configurator extensions:

- **`product_tmpl_id`** — the template (configurable). Required.
- **`product_id`** — the specific variant. Set on per-variant BoMs
  (the auto-created ones from `create_get_bom`). Empty on the
  template's parent BoM.
- **`bom_line_ids`** — the components. Each `mrp.bom.line` can carry
  a `config_set_id` linking to a `mrp.bom.line.configuration.set`
  for conditional inclusion.
- **`config_ok`** — related field from `product_tmpl_id.config_ok`.
  Stored so MRP queries can filter on it without joining.

A `mrp.bom.line.configuration.set` carries:

- **`name`** — e.g. "Maple-on-Contemporary" — a description.
- **`configuration_ids`** — One2many to `mrp.bom.line.configuration`.
  Each child is a single rule pattern.
- **`bom_line_ids`** — One2many back: the BoM lines that reference
  this set.

A `mrp.bom.line.configuration` carries:

- **`value_ids`** — Many2many `product.attribute.value`. The set of
  attribute values that must ALL be in the variant's picks for the
  parent line to apply.

The MO (`mrp.production`) overlay adds:

- **`config_ok`** — stored related from `product_id.config_ok`.
- **`config_session_id`** — Many2one to the session that produced
  this MO's product. Lets you trace back from a shop-floor MO to
  the original wizard configuration.
- **`custom_value_ids`** — related One2many surfacing the session's
  custom values onto the MO.

The MO also exposes Configure / Reconfigure buttons (model
methods `action_config_start` and `reconfigure_product`) — these
let a production engineer re-spawn the wizard for a
configurable product on the production side. Use case:
"engineering needs to swap the door style on this MO before it
goes to production" — Reconfigure spawns a new session, commits a
new variant, updates the MO's product_id.

## Your daily flow

You don't author BoM logic every day — but when you do, three
patterns cover most of the work.

**1. Setting up a parent BoM with configuration sets.**

You're adding a new template (Lesson 10.2 work) and you want the
BoM to be dynamic — e.g. "if Door Style = Five-Piece Woodgrain, add
2× side stiles; if Slab, skip them."

- Navigate to **Manufacturing → Products → Bills of Materials → New**.
- `product_tmpl_id` = your new template. `product_id` = **leave
  empty** — this is the parent BoM.
- Add bom_line_ids for every component the template **can**
  contribute.
- For lines that are conditional, create a
  `mrp.bom.line.configuration.set` first via **Manufacturing →
  Configuration → BoM Line Configuration Sets → New**:
  - Name it descriptively ("Five-Piece door — side stiles").
  - Add one or more `mrp.bom.line.configuration` rows, each with
    `value_ids = [<the attribute values that trigger this case>]`.
- On the BoM line, set `config_set_id = <your config set>`.
- Save.

Now: when a customer commits a configuration, `create_get_bom`
walks the parent BoM line-by-line. For each line with a `config_set_id`,
it checks each `configuration_ids` row — if the variant's picks
include ALL `value_ids` in that row, the line is included; otherwise
skipped.

**2. Forcing a BoM regeneration for a specific variant.**

You change the parent BoM (add a new line). Existing per-variant
BoMs don't auto-update — `create_get_bom` only creates a new BoM if
one doesn't already exist for the (template, variant) pair (the
`existing_bom` short-circuit at line 48 of
`product_configurator_mrp/models/product_config.py`).

To force a regen for one variant:

```bash
odoo-bin shell -d <db>
```

```python
Session = env["product.config.session"]
s = Session.browse(<session_id>)
# Delete the existing variant BoM
old_bom = env["mrp.bom"].search([
    ("product_tmpl_id", "=", s.product_tmpl_id.id),
    ("product_id", "=", s.product_id.id),
])
old_bom.unlink()
# Re-run BoM creation
s.create_get_bom(s.product_id)
env.cr.commit()
```

Or mass-regen by deleting all variant BoMs for a template:

```python
env["mrp.bom"].search([
    ("product_tmpl_id", "=", tmpl_id),
    ("product_id", "!=", False),
]).unlink()
# Next time create_get_variant runs on any session for this template,
# a fresh BoM will be built from the parent.
```

**3. Spawning the MO from a confirmed sale.order line.**

You confirm the sale order. Native Odoo's procurement run
identifies the configurable product as `route_id = make_to_order`
or similar and spawns an MO. The MO inherits `product_id` from the
sale.order.line; the `product_configurator_mrp.mrp.production`
overlay reads `config_session_id` from the line (via the sale
overlay's `_action_confirm` flow) and sets it on the MO.

The MO's `bom_id` is resolved from the `mrp.bom` record matching
the variant (the per-variant BoM that `create_get_bom` made). Work
orders generate from `bom_id.operation_ids` per native Odoo.

## Common mistakes + how to recover

**"The first customer commit produced no BoM at all."**

`create_get_bom` (line 24 of
`product_configurator_mrp/models/product_config.py`) needs **either**
(a) a parent BoM on the template (with `product_id = False`) whose
lines may or may not have config_set_ids, OR (b) attribute values
with `product_id` linked (so each picked value contributes a BoM
line via its option-product). With neither, the function walks both
branches, finds nothing, and returns False. The variant is created
but no BoM exists. Fix: create the parent BoM with the canonical
component list. Then regen per the daily-flow #2.

**"The BoM was created but it's missing the Maple core lines."**

The parent BoM's "Maple core" line has a `config_set_id` referencing
a configuration set whose only `mrp.bom.line.configuration` row is
`value_ids = [Maple]`. The variant must have Maple picked AND the
checker uses `set.issubset` (line 88 of the same file): the
configuration's `value_ids` must be a subset of the variant's
attribute_values. So if Maple is in `value_ids` but the
`configuration` row also requires `Contemporary` (e.g. you set
`value_ids = [Maple, Contemporary]`), and the variant is Maple +
Elegance, the subset check fails and the line is skipped.

Fix: either split the config set (one config per series) or
loosen the `value_ids` to just `[Maple]`.

**"The Reconfigure button on the MO opens the wizard but commits
don't update the MO's product_id."**

The MO's `reconfigure_product` (line 38 of `product_configurator_mrp/models/mrp.py`)
spawns the wizard with `extra_vals = {"order_id": self.id,
"product_id": self.product_id.id}`. The wizard subclass
`product.configurator.mrp` handles the write-back to the MO. If
the MO is in state `confirmed` or higher, the OCA validation may
silently fail the variant swap. Recovery: cancel the MO, recreate.

**"The MO has a config_session_id but custom_value_ids shows
nothing on the shop floor printout."**

The `custom_value_ids` on the MO is a related field
(`product_configurator_mrp.mrp.production` line 19 — defined as
`fields.One2many(related="config_session_id.custom_value_ids")`).
Related O2M fields don't sync into MO-level reports automatically
because the report's QWeb usually reads `mrp.production` direct
fields. Fix the QWeb to call `production.custom_value_ids` (Odoo
resolves related O2M for reads transparently).

**"The BoM cost rollup doesn't include the +10% Maple price extra."**

Correct — and intentional. The Maple +10% is on the **sale side**
(`product.template.attribute.value.price_extra` flows into
`session.price` flows into `sale.order.line.price_unit`). The MRP
side's cost is the actual component cost — the Maple `product.product`
linked via the attribute value's `product_id`. If that product has
`standard_price = 60` and white melamine has `standard_price = 40`,
the BoM's cost reflects $60 not "+10%". The price_extra is for
**pricing**, not **costing**. They're orthogonal axes; that
separation is the OCA design intent.

**"Two variants with identical picks have different BoMs."**

`create_get_bom` has an `existing_bom` short-circuit (line 48): it
finds and reuses ANY BoM where `product_tmpl_id = X AND product_id =
variant`. If two variants share `value_ids` exactly, they should
match the same variant_id (configurator's variant-dedup). If they
don't, you've split the variant catalog — likely from a manual
variant creation outside the wizard. Audit:
`env["product.product"].search([("product_tmpl_id", "=", tmpl_id)])` —
look for duplicates with same PTAV combinations.

## What the system is doing behind the scenes

The MRP overlay is **3 inheritance hops** + **3 new models**.

**Inheritance hops** (in `product_configurator_mrp/models/mrp.py`):

- `mrp.production` gains `config_ok`, `config_session_id`,
  `custom_value_ids`, plus `action_config_start` and
  `reconfigure_product`. The Configure/Reconfigure buttons on the MO
  form.
- `mrp.bom` gains `config_ok` (stored, for filtering).
- `mrp.bom.line` gains `config_set_id` — the link to the
  configuration set.

**New models** (also in mrp.py):

- `mrp.bom.line.configuration.set` — a named container.
- `mrp.bom.line.configuration` — one rule pattern per set
  (`value_ids` = the trigger combination).

The **third inheritance hop** is on `product.config.session` itself
(`product_configurator_mrp/models/product_config.py`):

```python
class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

    def create_get_bom(self, variant, product_tmpl_id=None, values=None):
        # Short-circuit: if a BoM already exists for (tmpl, variant), return it.
        existing_bom = self.env["mrp.bom"].search([
            ("product_tmpl_id", "=", product_tmpl_id.id),
            ("product_id", "=", variant.id),
        ])
        if existing_bom:
            return existing_bom[:1]

        # Look for a parent BoM (product_id = False).
        parent_bom = self.env["mrp.bom"].search([
            ("product_tmpl_id", "=", product_tmpl_id.id),
            ("product_id", "=", False),
        ], order="sequence asc", limit=1)

        bom_lines = []
        if not parent_bom:
            # No parent — walk attribute values' option-products.
            for product in attr_products:
                # Build bom_line vals via onchange, append.
                ...
        else:
            # Walk parent BoM line-by-line.
            for parent_bom_line in parent_bom.bom_line_ids:
                if parent_bom_line.config_set_id:
                    # Conditional line — check each configuration.
                    for config in parent_bom_line.config_set_id.configuration_ids:
                        if set(config.value_ids.ids).issubset(set(attr_values.ids)):
                            # Variant has all the required values — include.
                            ...
                else:
                    # Unconditional line — always include.
                    ...
        # Create the BoM.
        ...

    def create_get_variant(self, value_ids=None, custom_vals=None):
        variant = super().create_get_variant(value_ids, custom_vals)
        self.create_get_bom(variant, product_tmpl_id=self.product_tmpl_id)
        return variant
```

This is the load-bearing override: it makes BoM generation **automatic**
on every wizard commit. Without this overlay (i.e. with only
`product_configurator` installed), variants are created without
BoMs, and the production planner has to author them by hand.

The MO spawn from sale.order doesn't go through this code — it
uses native Odoo procurement, which looks up the per-variant BoM
that `create_get_bom` already wrote. The `config_session_id` on the
MO is wired by the sale→MO procurement chain through standard Odoo
context propagation; the `product_configurator_sale` overlay sets
up the line; the MO's overlay reads the line's session and stores
it on the MO.

The **work orders** (`mrp.workorder`) are generated by native Odoo
from `bom_id.operation_ids` — the configurator has no overlay
there. If you need configurable operations (e.g. "if Maple, add a
sanding step"), you author it as standard `mrp.routing.workcenter`
records on the parent BoM and rely on the configuration_ids
mechanism for line inclusion. Operation-level configurability is
not natively supported — TBD-feature-gap.

## Quiz (5 questions, applied)

**1.** You author a parent BoM with 12 unconditional lines and 4
conditional lines (each in its own `mrp.bom.line.configuration.set`
keyed by a different attribute value). Customer A picks values that
match 2 of the 4 conditional sets. How many lines does Customer A's
auto-generated BoM contain, assuming all attribute_values link to
real option-products?

> 12 unconditional + 2 conditional = 14 lines. The unconditional
> lines always copy (their parent has no `config_set_id`); each
> conditional line is included only if at least one of its
> configuration's `value_ids` is a subset of Customer A's picks.

**2.** A configuration set has one configuration row:
`value_ids = [Maple, Contemporary]`. A variant has picks
`[Maple, Elegance, Slab Door]`. Does the line apply, and why?

> No. `set.issubset` requires ALL `value_ids` to be in the picks.
> Maple is in the picks but Contemporary is not (Elegance is) — so
> `{Maple, Contemporary}.issubset({Maple, Elegance, Slab})` is
> False. The line is skipped. If you wanted "Maple AND
> (Contemporary OR Elegance)", you'd need two configuration rows
> in the same set: `[Maple, Contemporary]` and `[Maple, Elegance]`
> — each independently checked, line included if EITHER matches.

**3.** The team adds a "Toe Kick Trim" component that should land
in the BoM only for vanity templates with Width >= 24in. Where do
you author this, and what's the trade-off vs putting the rule on
the configurator side?

> Author it on the MRP side: a `mrp.bom.line` on the vanity's
> parent BoM with `config_set_id` linked to a set whose
> configuration is `value_ids = [Width 24, Width 27, Width 30,
> Width 33, Width 36]`. Trade-off: this is BoM-only — the
> configurator wizard doesn't show the line, the customer doesn't
> see "+toe kick trim" in their price. If the trim adds cost they
> see, you'd ALSO need a PTAV `price_extra` on the relevant
> attribute_values. Two-axis change for an axis-crossing
> feature is the OCA design tax. Alternative: bind the toe-kick
> trim as an attribute (Toe Kick = Yes/No) with `price_extra` AND
> a config_set; price + BoM stay in sync.

**4.** You change the parent BoM and want every future variant of
that template to use the new structure — but you also have 14
existing per-variant BoMs from prior commits. Outline the cleanest
recovery.

> Run in shell:
> `env["mrp.bom"].search([("product_tmpl_id", "=", tmpl_id),
> ("product_id", "!=", False)]).unlink()`. This deletes all
> per-variant BoMs. The next time a session commits or
> `create_get_bom` is called for an existing variant, a fresh BoM
> is built from the new parent. Caveat: any MO currently in
> `draft` referencing one of those BoMs has its `bom_id` blanked
> (cascade) — re-open the MO and select the new BoM. MOs in
> `confirmed` or later are unaffected (they froze their BoM via
> `mrp.production.move_raw_ids` at confirm time).

**5.** A configured MO is in `confirmed` state. The customer
changes their mind on door style. You hit Reconfigure on the MO
and step through the wizard with the new pick. What happens to the
old BoM, the new BoM, and the work orders?

> The wizard creates a new session, which materialises a new
> variant (or finds an existing one matching the new picks). The
> MO's `product_id` updates to the new variant. **The old
> per-variant BoM stays in the database** — it's still linked to
> the old variant, which still exists. The new variant either has
> an existing BoM or gets one created by `create_get_bom`. The MO's
> `bom_id` typically re-resolves on save to the new variant's BoM.
> **Work orders**: native Odoo's MO state machine is the load-bearing
> piece here — `mrp.production` may or may not regenerate work orders
> on `product_id` change depending on state. Test before relying on
> it. If you need this flow routinely, build a wrapper that cancels
> the MO and creates a fresh one rather than mutating an existing
> confirmed MO.

---

## What this lesson does NOT cover

- Configurator basics — Course 5, Lesson 5.1.
- 5-addon architecture — Lesson 10.1.
- Setting up a new configurable product — Lesson 10.2.
- Session state machine — Lesson 10.3.
- Sale-flow integration (channel pricing, line snapshots) — Lesson
  10.4.
- V2 UX OWL component + JSON-RPC contract — Lesson 10.6.
- Common gotchas (rule ordering, exclusion explosion, performance) —
  Lesson 10.7.
- Native Odoo MRP (work centers, routings, procurement rules,
  scrap, backflush) — Odoo's own native eLearning track, plus
  Southbrook Course 1 (workcenters) + 2 (production planning).
