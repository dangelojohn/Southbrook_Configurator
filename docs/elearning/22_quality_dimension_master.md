---
course: 22
chapter: 22.5
title: Quality Module — Dimension Master and Version Control
duration: 7
audience: Developer or admin maintaining the dimension master
prereqs: Lesson 22.1
custom_modules: southbrook_quality
---

# Quality Module — Dimension Master and Version Control

## The model

```python
class SouthbrookQualityDimension(models.Model):
    _name = "southbrook.quality.dimension"
    _description = "Quality Dimension Master Spec"
    _inherit = ["mail.thread"]
```

Fields:

```python
name        = fields.Char(required=True)
description = fields.Text()
nominal     = fields.Float(required=True, digits=(12, 4))
usl         = fields.Float(required=True, digits=(12, 4))
lsl         = fields.Float(required=True, digits=(12, 4))
unit_of_measure = fields.Many2one("uom.uom", required=True)
applicable_workcenter_ids = fields.Many2many("mrp.workcenter")
sample_frequency = fields.Selection([
    ("per_hour", "Per Hour"),
    ("per_50_units", "Per 50 Units"),
    ("per_shift", "Per Shift"),
    ("per_day", "Per Day"),
], default="per_50_units")
is_critical = fields.Boolean(default=False)
```

## Version control via chatter

Every write to `nominal`, `usl`, `lsl`, `sample_frequency`,
`is_critical` is tracked in the chatter via `mail.thread`.
Historical values are derived from chatter history.

This is a deliberate simplification. A full version-control model
(with explicit `dimension_revision` records, effectivity dates,
ECO links) was considered + deferred. The chatter trail is
sufficient for audit; explicit versioning is v1.1 if needed.

## Effectivity windows

If you change USL/LSL today, all NEW SPC samples are evaluated
against the new limits. All EXISTING samples were evaluated at
their creation time (`is_in_control` is stored, not lazy).

This means a chart will look discontinuous around the change date —
old samples on old math, new samples on new math. Document the
change in the chatter so anyone reading the chart understands.

## Adding a dimension

Two paths:

### XML (recommended for shipped defaults)

```xml
<record id="dimension_panel_thickness_18mm" model="southbrook.quality.dimension">
    <field name="name">Panel Thickness 18mm Board (SB-CNC-BORE)</field>
    <field name="nominal">18.0</field>
    <field name="usl">18.2</field>
    <field name="lsl">17.8</field>
    <field name="unit_of_measure" ref="uom.product_uom_millimeter"/>
    <field name="applicable_workcenter_ids" eval="[(4, ref('mrp.mrp_workcenter_5'))]"/>
    <field name="sample_frequency">per_50_units</field>
    <field name="is_critical" eval="True"/>
</record>
```

### UI (for shop-floor additions)

*Quality → Dimensions → New*. Quality manager or curator role.

## Linking dimensions to products

Dimensions can be associated with `product.template` via an m2m
extension:

```python
class ProductTemplate(models.Model):
    _inherit = "product.template"
    
    quality_dimension_ids = fields.Many2many(
        "southbrook.quality.dimension",
        string="Quality Dimensions",
    )
```

This drives the SPC plan — when a product is being made, the
applicable dimensions are auto-suggested for sampling.

## Common mistakes + how to recover

- **"Changed USL but old chart still shows old limit"** — limits
  cached client-side; reload. New samples will use new limits.
- **"Dimension archived but old samples still exist"** — archiving
  preserves data; the dimension just doesn't show in search.
  Samples remain queryable via direct SQL.
- **"Critical flag toggled but Western Electric rules didn't
  rerun"** — only new samples re-evaluate. Old samples retain
  their original `is_in_control` value.

## Quiz

**Q1.** USL changed from 5.2 to 5.1 today. Existing samples with
value 5.15 — in control or out?

> Their `is_in_control` was stored at create time using old limits.
> Out of new spec but still showing `is_in_control = True` (from
> old math). To re-evaluate, run a one-time script:
> `samples.filtered(...).write({'is_in_control': ...})`.

**Q2.** Dimension archived. Search still returns it?

> No — search excludes `active=False` by default. Toggle
> *Show Archived* to see.

**Q3.** Dimension's `is_critical` toggled true. Control limits
recompute on what?

> Next sample creation. Critical = 2σ; old samples stay on 3σ math.

**Q4.** Dimension linked to 3 workcenters via m2m. SPC samples
from a 4th workcenter (not in the m2m). Allowed?

> Yes — the m2m is advisory. The platform doesn't reject samples
> from non-listed workcenters. Documentation suggests the m2m =
> "where this dimension applies" for SPC planning purposes.

**Q5.** Where in code is `is_in_control` computed?

> `southbrook.quality.spc_sample._compute_in_control()`. Called
> on every create + write to `measured_value`.
