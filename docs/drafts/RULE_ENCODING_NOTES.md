# OCA `product.config.line` — Encoding the 4 Southbrook Rules

> Reconnaissance findings from reading `addons/product_configurator/models/product_config.py`
> + the BMW 2-series demo records. Authoritative for how the four declarative rules
> from `docs/Southbrook_Excel_to_Odoo_Mapping.md` §3.4 must be expressed.
>
> **Status:** preparation, not commitment. `docs/drafts/config_rules_DRAFT.xml` is
> built from these notes. Drafts are reviewed and copied to
> `addons/southbrook_estimating/data/` only after the §10 step 5 gate opens.

---

## The three-model grammar

OCA's rule engine is split across three records that compose in a fixed pattern:

### 1. `product.config.domain` — the named *trigger*

```xml
<record id="series_is_contractor" model="product.config.domain">
    <field name="name">Contractor Series Selected</field>
</record>
```

A domain is just a name. The conditions live on its child domain.line records.

### 2. `product.config.domain.line` — *AND/OR-composed trigger conditions*

```xml
<record id="series_is_contractor_line" model="product.config.domain.line">
    <field name="domain_id" ref="series_is_contractor"/>
    <field name="attribute_id" ref="attr_series"/>
    <field name="condition">in</field>          <!-- "in" | "not in" -->
    <field name="operator">and</field>          <!-- "and" | "or" — composes with siblings -->
    <field name="value_ids" eval="[(6, 0, [ref('series_contractor')])]"/>
    <field name="sequence">1</field>            <!-- evaluation order within domain -->
</record>
```

A domain.line says "attribute IS IN values" (or NOT IN). Multiple lines on the same
domain compose via the `operator` field. A multi-condition domain fires only when
all (or any, depending on operator) of its lines match the current configurator state.

### 3. `product.config.line` — the *restriction action*

```xml
<record id="contractor_restricts_door_style_on_wall_1dr" model="product.config.line">
    <field name="product_tmpl_id" ref="southbrook.wall_1dr"/>
    <field name="attribute_line_id" ref="attr_line_wall_1dr_door_style"/>
    <field name="value_ids" eval="[(6, 0, [ref('door_thermofoil_slab_white')])]"/>
    <field name="domain_id" ref="series_is_contractor"/>
    <field name="sequence">10</field>
</record>
```

A config.line says "On THIS template, when THIS domain fires, restrict THIS
attribute-line to THESE values". It is **per-template** — Rule 1's "Contractor →
thermofoil-only" must be expressed once per template that exposes door_style.

---

## Mapping each Southbrook rule to records

### Rule 1 — Series → door style

**Restriction shape:** when series is Contractor, door_style ∈ {thermofoil_slab}.
When series is Elegance, door_style ∈ {five_piece_woodgrain}. Contemporary +
Signature expose the full catalog (no restriction).

**Records needed:**
- 1× domain `series_is_contractor` + 1× domain.line
- 1× domain `series_is_elegance` + 1× domain.line
- N× config.line per (template × restriction) — once per template that has
  door_style. Templates with door_style: 10 of 12
  (excludes `accessory`, `worktop`). So **20 config.line records**
  (10 templates × 2 restrictions).

### Rule 2 — Box material → series

**Restriction shape:** maple box only on Contemporary + Elegance. Contractor =
white_melamine only. Signature = maple only (it's the standard, no white
option per Mapping §1).

**Records needed:**
- domain `series_is_contractor` (reused from Rule 1)
- domain `series_is_signature` + domain.line
- N× config.line per (template × restriction). Templates with box_material:
  all 12.
- Restriction "Contractor → box_material ∈ {white_melamine}" × 12 templates
- Restriction "Signature → box_material ∈ {maple}" × 12 templates
- **24 config.line records.**

Contemporary + Elegance get no restriction → both options exposed naturally.

### Rule 3 — Width → door count ⚠️ NEW AMBIGUITY (Q22)

**Mapping §3.4 says:**
> Encoded as a `product.config.line` rule that sets door_count = `1 if width <= 21 else 2`.

But `product.config.line` semantics are **restrict-values**, not **set-derived-value**.
For Rule 3 to be a config.line, `door_count` must be an attribute on the template
— but it's **not** in the Q2 locked 11-attribute list.

**Two viable resolutions:**

- **(a) door_count as hidden 12th attribute.** Add `door_count` to attributes
  with values [1, 2], not user-facing (default sequence puts it last; UI hides
  it). Then Rule 3 fires as: domain "width ∈ {9,12,15,18,21}" → config.line
  "door_count ∈ {1}"; domain "width ∈ {24,27,30,33,36}" → config.line
  "door_count ∈ {2}". Multiplied per template that has doors = 10 templates ×
  2 restrictions = 20 config.line records. door_count is then consumed by
  the BoM rollup as if it were any other attribute value.

- **(b) door_count as computed BoM field.** Rule 3 lives in
  `models/mrp_bom.py::_compute_panel_dimensions` (or a sibling), not in
  `config_rules.xml`. The rule is enforced at BoM materialisation, not at
  configurator-selection time. The smoke test still passes (changing width
  flips the BoM line count) but the configurator UI doesn't display door_count.

**My recommendation: (a).** Rationale:
- Keeps Rule 3 declarative, matching the brief's stated requirement
- door_count is visible in the BoM preview (Brief §2.2 wants this)
- Pattern-consistent with Rules 1, 2, 4
- Custom register stays at 7 routines (no new computed field needed)

**Q22 surfaced for John ack.** Drafts assume (a); if (b) wins, drafts adjust to
move Rule 3 from `config_rules.xml` to `models/mrp_bom.py`.

### Rule 4 — Family → soft-close ⚠️ NEW AMBIGUITY (Q23)

**Restriction shape:** when family is corner-bifold, hide soft_close from the
accessories multi-select.

**But the Q2-locked family attribute values are:**
`wall / base / drawer / sink / tall / corner / vanity / worktop / accessory`

— there is no `corner_bifold` value. Mapping §3.4 references "bi-fold corner
cabinets" as a distinct family.

**Two viable resolutions:**

- **(a) Split `corner` into `corner_standard` + `corner_bifold`.** Family
  attribute grows to 10 values. Rule 4 fires on `family ∈ {corner_bifold}`.
  Acceptable but expands the family vocabulary.

- **(b) Add a `family_subtype` sub-attribute, scoped to `family=corner`.**
  Values: `standard / bifold`. Rule 4 fires on `family_subtype ∈ {bifold}`.
  More precise — keeps the 9-value family attribute clean, surfaces bi-fold
  as a sub-selection only when relevant.

**My recommendation: (b).** Rationale:
- Family stays at 9 high-level values (matches the kitchen-design vocabulary
  dealers use)
- bi-fold is a structural sub-choice of corner, not a parallel family
- Sub-attribute pattern works for future cases (e.g. drawer-bank pull-out
  vs deep-drawer)
- Forces an explicit choice in the UI for corner cabinets (good for the
  declarative-over-hidden-default principle)

**Q23 surfaced for John ack.** Drafts assume (b) and seed a `family_subtype`
attribute with the `corner` scoping; if (a) wins, drop `family_subtype` and
add `corner_bifold` to the family value list.

---

## Other findings

### `condition` operators are exactly two: `in` / `not in`

No `=`, no `!=`, no range operators. Width-band restrictions must enumerate the
band values explicitly (not "width ≤ 21" but "width IN {9, 12, 15, 18, 21}").
Acceptable for Southbrook because width values are a small fixed set.

### `operator` field composes domain.lines within a single domain

`and` (default) means all lines on the domain must match for the trigger to fire.
`or` means any single line suffices. The 4 Southbrook rules are AND-only — no
domain needs OR composition.

### Sequence matters for evaluation order

`product.config.line` has `_order = "product_tmpl_id, sequence, id"`. Default
sequence = 10. Use ascending sequences to express priority: tightest restriction
last. For Rule 2, Contractor's restriction fires before Signature's.

### Open OCA TODO at `product_config.py:1500` — NOT a blocker

The `validate_configuration` method already returns a structured `{reason: ...}`
dict on failure. The TODO is about *converting that dict-return into a raised
ConfigurationError*. Brief §2.2 ("rule reason visible to sales rep") works fine
with the dict-return — the Order Builder reads the dict and surfaces the
`reason` field on the disabled option's tooltip. **No southbrook_estimating
override needed for §2.2 compliance.** PUNCHLIST §Q18 follow-up to update.

### `product.config.line` is per-template (the N× multiplication)

There is no "global rule" pattern in OCA — every rule is anchored to a
`product_tmpl_id`. The four Southbrook rules expand to roughly:
- Rule 1: 20 records (10 templates × 2 series restrictions)
- Rule 2: 24 records (12 templates × 2 series restrictions)
- Rule 3: 20 records *(if Q22 → (a))* — door_count restriction × width band × template
- Rule 4: 1 record (only `accessory` attribute is restricted, only on bi-fold)

**Total: ~65 config.line records, ~10 domain records, ~15 domain.line records.**

Mechanical generation from a Python script may be cleaner than hand-authored
XML. Decision deferred to the §10 step 5 implementation choice — the draft XML
files spell out the records longhand so the rule set is auditable as data.
