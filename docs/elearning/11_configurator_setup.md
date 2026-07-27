---
course: 11 — Creating a New Product End-to-End
chapter: 11.5
title: Setting Up the Configurator Entry for the New Product
duration: 40 minutes
audience: Configurator admin attaching attributes, values, exclusions, and construction rules to a brand-new SKU's `product.template`
prereqs: Lesson 11.4 (BoM authored and attached to the `product.template`), Lesson 5.1 (configurator basics — attributes, attribute_lines, the OCA model), Lesson 5.4 (configurator UX — chip-selector layout, test sessions), Course 9 lessons on the OCA `product_configurator` engine
custom_modules: product_configurator, product_configurator_sale, product_configurator_mrp, southbrook_estimating, southbrook_configurator_ux
---

# Setting Up the Configurator Entry for the New Product

## Who this lesson is for

You're the configurator admin. Yesterday lesson 11.4 produced an
`mrp.bom` attached to a `product.template` with `config_ok = True`
but no attributes. Today you turn that empty shell into a
configurable product — picking attributes, attaching values,
authoring exclusions, writing the construction rules — and end with
a test configuration session that produces a valid SKU.

This lesson does **not** re-cover what attributes, values,
attribute_lines, and the OCA configurator model are. That's lesson
5.1. This lesson is the **new-product-specific workflow**: starting
from a blank template and ending with a publishable configurable
SKU, with all the rules and exclusions in place.

## Where this lives on the site

> **Sales → Configurable Products → Configurable Templates**

…click your new template (the one the BoM was attached to in
lesson 11.4). You'll spend the lesson on this form. You'll also
visit:

> **Sales → Configuration → Attributes**

…to confirm the attributes you need exist (you usually do not
create new ones at this stage — Southbrook's 11 attributes per Q2
of the estimating brief are seeded; new attributes are a separate
governance discussion). And:

> **Sales → Configuration → Configuration Rules**

…where `product.config.line` rules live (the four declarative
Southbrook rules from the estimating brief §5, plus any
new-product-specific exclusions you author here).

For the test session:

> **\<your template\> → Configure button** (OCA wizard)

…or the customer-facing chip-selector:

> **southbrookcabinetry.space/shop/\<slug\>**

(if `southbrook_configurator_ux` is installed — usually it is).

## What your screen shows

The `product.template` form
(`product_configurator/models/product.py:13`):

- **Configurable** (`config_ok`) — already `True` from lesson 11.4.
- **Variant Attributes** (`attribute_line_ids` →
  `product.template.attribute.line`) — the attributes the
  configurator presents to the customer/estimator. Empty on a
  fresh template.
- **Configuration Rules**
  (`config_line_ids` → `product.config.line`) — the per-template
  rule rows. Each row binds one attribute to a
  `product.config.domain` (the exclusion expression). Empty.
- **Configuration Steps**
  (`product.config.step` / `product.config.step.line`) — optional
  wizard step grouping; for chip-selector UX (`/shop/<slug>`)
  these are ignored, but the OCA backend wizard uses them.
- **Mako template name** (`mako_tmpl_name`) — the configured
  variant naming pattern. Convention:
  `[${self.attribute_value_ids.filtered(lambda v: v.attribute_id.code == 'family').name}] ${self.attribute_value_ids...}` — copy from a similar existing template.

The `product.attribute` form
(`product_configurator/models/product_attribute.py:7`):

- **Name** + **Code** — the attribute identifier (`family`,
  `width`, `series`, `box_material`, `door_style`, `finish`,
  `hinge_side`, `finished_sides`, `gables`, `handle`,
  `accessories` — the canonical 11).
- **Values** (`product.attribute.value`) — every possible value,
  each with `lead_time_extra` (days) and `value_inches` /
  `value_mm` for dimensional attributes.

The `product.config.domain` form
(`product_configurator/models/product_config.py:15`):

- **Name** — describe the rule (*"Contractor series → slab door
  only"*).
- **Lines** (`domain_line_ids` → `product.config.domain.line`) —
  each line: `attribute_id`, `condition` (`in` / `not in`),
  `value_ids`, `operator` (`and` / `or`).

The `product.config.line` form
(`product_configurator/models/product_config.py:162`):

- **Template** (`product_tmpl_id`) — your new template.
- **Attribute line** (`attribute_line_id`) — which attribute this
  rule restricts.
- **Allowed value(s)** (`value_ids`) — the values that *remain
  allowed* when the rule's domain matches.
- **Domain** (`domain_id`) — the trigger condition (the
  `product.config.domain` from above).

## Your daily flow

**1. Read the spec one more time (3 min):**

- Open `spec_draft.md` from the conception folder. List every
  customer-facing choice: width, height, door style, hinge side,
  finished sides, gables, handle, etc.
- Each choice maps to one Southbrook attribute. **Do not invent
  new attributes** — the 11 canonical attributes per Q2 of the
  estimating brief cover virtually all cabinet variation. If
  your spec genuinely needs a 12th attribute, escalate to the
  configurator owner first (governance discussion).

**2. Attach the attributes to the template (10 min):**

- Open the new `product.template`. *Variant Attributes* tab.
- For each attribute the spec requires:
  - *Add a line.*
  - **Attribute**: pick from the 11 canonical
    (`product.attribute`).
  - **Values** (`value_ids` on
    `product.template.attribute.line`) — pick the subset of values
    this product offers. *"Width: 18, 21, 24, 27, 30 inches"* —
    not all sizes; only the ones this SKU supports.
  - **Create Variant**: leave as the default (per the OCA
    configurator's hybrid policy — dynamic variant on confirm, Q6
    of the estimating brief).
- Save after each attribute line; the
  `_validate_attribute_lines` constraint (`product.py:41`) fires
  on save and catches coherence errors.

**3. Author exclusions as `product.config.domain` records (10 min):**

For each customer-spec rule that's a hard exclusion (i.e. *"if
attribute A is value X, then attribute B cannot be value Y"*):

- **Sales → Configuration → Configuration Rules → New Domain**.
- **Name**: describe the rule in plain English (*"9-21" cabinets
  are 1-door only"*).
- **Lines** (`domain_line_ids`) — fill the condition:
  - `attribute_id` = width
  - `condition` = `in`
  - `value_ids` = 18, 21
  - `operator` = `or` (combines with next line if any)
- Save the domain.

For the Southbrook canonical four rules (already seeded in
`addons/southbrook_estimating/data/config_rules.xml`), you do
**not** re-author — they apply to all templates. New rules you
author here are **product-specific**.

**4. Bind exclusions to the template (5 min):**

- On the template's form: *Configuration Rules* tab → *Add a
  line* (this creates `product.config.line` records).
- **Attribute line**: the attribute the rule restricts (e.g.
  *Door count*).
- **Allowed value(s)** (`value_ids`): the values that remain
  allowed when the domain matches (e.g. *1-Door*).
- **Domain**: the `product.config.domain` you just created.
- Save.

**5. Wire the construction rules (5 min):**

The four canonical Southbrook construction rules (from the
estimating brief §5) apply to every cabinet automatically — they
live in `addons/southbrook_estimating/data/config_rules.xml`. You
do **not** re-author them. They are:

- *Contractor series → slab door only.*
- *Maple box → Contemporary or Elegance series only* (`+10%` price,
  `+2 weeks` lead time).
- *9-21" → 1-door; 24-36" → 2-door.*
- *Bi-fold corner → no soft-close hinge.*

What you **may** author here are *product-specific* construction
rules — for example, *"the new floating shelf SKU requires gable
support"*. These are additional `product.config.line` records on
the new template.

**6. Set the BoM-to-attribute mapping (3 min):**

The `product_configurator_mrp` module bridges attribute selections
to BoM modifications at MO confirm time. For most cabinets, the
mapping is the OCA default — no extra config needed. For cabinets
where an attribute meaningfully changes the BoM (e.g. *Door style:
slab vs five-piece* changes the door blank product), you need to
add explicit BoM-line attribute-value bindings on the
`mrp.bom.line` form (the *Apply on Variants* field). Lesson 5.1
covers this in detail.

**7. Configure the Mako template (3 min):**

The `mako_tmpl_name` on `product.template` defines how the
configured variant is named. Copy the pattern from a similar
existing template (e.g. `southbrook.base_1dr`). The pattern
references attribute values; the resulting variant name shows up
on `sale.order.line.product_id.display_name`.

**8. Test the configuration (10 min):**

The OCA configurator backend wizard:

- On the template form, click *Configure* (smart button — OCA
  default). The wizard opens, presenting attributes in step order.
- Walk through every attribute combination. For each:
  - Pick a value.
  - Confirm the rule-excluded values are correctly disabled.
  - Confirm price updates (the configurator session updates
    `product.config.session` price on each selection).
- At the end, click *Finish*. A new `product.product` variant is
  created.

The Southbrook chip-selector (lesson 5.4):

- Open `southbrookcabinetry.space/shop/<slug>` in an incognito
  browser.
- Walk the same path. The chip-selector is the customer-facing UX
  and uses the same `product.config.session` records under the
  hood. The `ConfiguratorV2` OWL component drives the UI.
- If `state.disabledValueIds` doesn't grey out the right values,
  your domain expressions are wrong — go back to step 3.

**9. Publish (2 min):**

- On the template form, confirm **Can be Sold** is on.
- For the customer-facing site, *Website → Published* toggle.
- The template is now selectable in the Order Builder (lesson
  5.2) and visible on the public site.

**10. Hand-off to lesson 11.6 (1 min):**

- Slack the estimator:
  *"Configurator wired for `southbrook.<xml_id>`; ready for
  pricing review."*

## Common mistakes + how to recover

**"I created a new attribute because the spec needed something the
canonical 11 don't cover."**

Roll it back. Creating a 12th attribute fragments the configurator
data model; every existing report, dashboard, and
`product_configurator_sale` integration assumes the canonical 11.
The real path: (a) the spec value fits an existing attribute under
a slightly looser interpretation — use the existing attribute; or
(b) the spec value is truly new — file a 12th-attribute proposal to
the configurator owner. The estimating brief Q2 is the canonical
list; deviating without governance is technical debt.

**"My `product.config.domain` rule disables the value I wanted to
keep allowed, not the other way around."**

The semantics of `product.config.line.value_ids` is *"these values
remain allowed when the domain matches"*. Common confusion: people
think it's *"these values are excluded"*. **Recovery**: invert your
domain (use `not in` instead of `in`, or vice versa), or flip the
value list. The OCA documentation (lesson 5.1) has the canonical
explanation.

**"The chip-selector greys out everything after I pick the first
value."**

Your domain expressions are too restrictive — the combination of
your new rule and the existing four canonical rules leaves no
allowed values. **Recovery**: walk through each rule, identify
which one over-restricts (the chip-selector UI shows the rule
reason on hover for grey chips), and loosen.

**"I authored a product-specific construction rule that contradicts
one of the canonical four."**

The configurator does not detect rule contradictions — both rules
fire, and the result is no allowed values. **Recovery**: identify
the contradiction. If your product-specific rule is right (the
canonical rule is wrong for this product), file a configurator-
owner ticket — overriding the canonical four is a governance
discussion, not a config tweak. Usually the right resolution is to
remove your rule and accept the canonical behaviour.

**"The Mako template name produces variant names like `[False]
None None`."**

The template references attribute values that don't exist on this
template, or attribute codes that aren't bound. **Recovery**: copy
the Mako pattern from a similar existing template (e.g.
`southbrook.base_1dr`), substitute the attribute code references
that match the attributes you've actually attached, and re-test by
creating a new variant.

**"I configured everything and tested it. A week later the
estimator says new orders for this SKU are throwing
`validate_configuration() failed`."**

Something changed downstream — usually a canonical rule was
updated and your product-specific rules no longer compose
cleanly. **Recovery**: re-run a test session in the OCA wizard.
The wizard reports which rule fired the validation failure. Adjust
the offending `product.config.line` (yours, not the canonical
one), test, save.

## What the system is doing behind the scenes

When you attach an attribute line to the template:

- A row in `product.template.attribute.line`
  (`product_attribute.py:160`) is created with `product_tmpl_id`,
  `attribute_id`, `value_ids`.
- The `_validate_attribute_lines` constraint
  (`product.py:41`) ensures every value referenced is actually a
  child of the attribute.
- No variants are created yet — variant creation is deferred to
  the first `product.config.session` that confirms (the "dynamic
  variant" pattern, Q6).

When you create a `product.config.domain`:

- A row in `product.config.domain` is created.
- Each line creates a `product.config.domain.line` row with
  `attribute_id`, `condition`, `value_ids`, `operator`.
- The domain is evaluated at attribute-value-selection time by
  the OCA configurator engine, building up a Python domain
  expression on the fly.

When a configurator session runs:

- A `product.config.session` row is created
  (`product_config.py:344`).
- Each customer selection writes to `session.value_ids` and
  triggers re-evaluation of all `config_line_ids` rules.
- Disallowed values get added to `state.disabledValueIds` (the OWL
  `ConfiguratorV2` state — lesson 5.4).
- `validate_configuration()` runs at *Confirm*; if any rule fails,
  it raises and the session won't produce a variant.
- On success, `session.create_get_variant()` is called — it
  either returns an existing variant matching the value set or
  creates a new one (dynamic variant policy).

When the variant is created and a `sale.order` confirms with that
variant on a line:

- `product_configurator_sale` writes
  `sale.order.line.product_config_session_id` linking the line to
  the configuration session — so the estimator can re-open it.
- `product_configurator_mrp` reads the variant's attribute values
  and modifies the rolled-up `mrp.bom` accordingly (e.g. swaps the
  door blank product if the door style changed).
- Lesson 11.6 (estimating + pricing) takes over from here.

## Quiz (5 questions, applied)

**1.** Your new SKU is a floating corner shelf. The spec says
*width 12-24", finish material only, no door, no hardware, gable
support required*. Which attributes do you attach, and which do you
**skip**?

> Attach: `family` (=accessory), `width`, `finish`,
> `finished_sides`. Skip: `door_style`, `hinge_side`, `handle`,
> `series`, `box_material` (the shelf isn't a box-carcass product),
> `gables`. Add a product-specific construction rule:
> *"gable support required when family=accessory and
> sub-family=floating_shelf"* — but better yet, encode "gable
> support is built into the BoM" rather than as a customer-facing
> attribute. Customer-facing attributes are choices the customer
> can make; non-choices belong in the BoM.

**2.** You attach the `width` attribute with values 18, 21, 24, 27,
30. The canonical *9-21" → 1-door; 24-36" → 2-door* rule applies.
What happens when a customer picks width=24"?

> The canonical rule fires. The `door_count` attribute's allowed
> values are restricted to 2-Door. The chip-selector greys out
> 1-Door. The customer cannot pick 1-Door on a 24" cabinet. You
> didn't author this rule — it's seeded in
> `southbrook_estimating/data/config_rules.xml` — but it applies to
> every template that includes the `width` and `door_count`
> attributes, including yours.

**3.** You finish configurator setup and test the OCA wizard. It
works. The chip-selector at `/shop/<slug>` shows all chips greyed
out from the start. What's wrong?

> The OWL component (`ConfiguratorV2`) loads
> `state.disabledValueIds` from the server. If everything is grey,
> the server thinks every value is disabled — almost always means
> an XML data file failed to load (rules misconfigured, attribute
> not attached). Check the browser console for the OWL state
> object; check the Odoo server log for module load errors.
> Lesson 5.4 has the full recovery flow.

**4.** Your new SKU has a `door_style` attribute with values *slab,
five-piece, glass-front*. The cabinet's BoM line for *Door blank*
points at a single product (slab MDF). What do you do?

> Add three `mrp.bom.line` rows, one per door-style value, each
> with the correct door blank substrate product and the *Apply on
> Variants* field set to the matching attribute value.
> `product_configurator_mrp` reads this at MO rollup and includes
> only the line(s) matching the selected variant. Alternatively,
> if all three door styles use the same blank substrate but differ
> in routing operations, the BoM line stays single and the
> operation changes — depends on how the door is built. Lesson 5.1
> covers the BoM/attribute binding patterns.

**5.** A week after publish, the estimator says the new template
isn't appearing in the Order Builder catalog. What do you check?

> Three things: (a) `config_ok = True` on the template (should be);
> (b) the template is in a category visible to the estimator's user
> group (Order Builder filters); (c) `sale_ok = True` on
> `product.template` (the "Can be Sold" flag). If all three are
> right and it's still missing, check whether the product is
> archived — `active = False` hides it from the catalog even if
> everything else is right.

---

## What this lesson does NOT cover

- Configurator fundamentals (attributes, values, attribute_lines,
  rules) — lesson 5.1.
- Customer-facing chip-selector UX details, OWL component
  internals, test session wiring — lesson 5.4.
- The four canonical Southbrook construction rules — covered in
  lesson 5.1 and seeded in `southbrook_estimating/data/`.
- BoM modifications driven by attribute values — lesson 5.1.
- The `validate_configuration()` runtime — lesson 5.1.
- Pricing (price extra per attribute value, channel multipliers,
  pricelists) — lesson 11.6.
- The `southbrook_configurator_ux` bulk-import wizard — lesson
  5.4.
