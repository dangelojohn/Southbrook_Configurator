---
course: 26
chapter: 26.7
title: MES + MPS Module — Customisation Patterns
duration: 6
audience: Developer extending MES/MPS for new scenarios
prereqs: Lessons 26.1-26.6
custom_modules: southbrook_mes_mps
---

# MES + MPS Module — Customisation Patterns

## Common customisations

1. New forecast strategy
2. New OEE loss reason taxonomy
3. New bottleneck threshold per workcenter
4. Per-product MPS template

## New forecast strategy

Default static forecast (lesson 26.2). For history-based:

```python
class SouthbrookMesMpsMpsPeriod(models.Model):
    _inherit = "southbrook.mes_mps.mps_period"
    
    def _forecast_for(self, product_id, week_start):
        """Override: forecast from rolling 12-week historical average."""
        product = self.env["product.product"].browse(product_id)
        lookback_start = week_start - relativedelta(weeks=12)
        
        # Average actual demand from last 12 weeks
        history = self.search([
            ("product_id", "=", product_id),
            ("week_start", ">=", lookback_start),
            ("week_start", "<", week_start),
            ("state", "=", "executed"),
        ])
        
        if not history:
            return super()._forecast_for(product_id, week_start)
        
        return sum(h.actual_demand_qty for h in history) / len(history)
```

## New OEE loss reason

Native `mrp.workcenter.productivity` has a loss_id field
pointing at `mrp.workcenter.productivity.loss`. Loss types:
availability / performance / quality.

Add new loss reasons (e.g. setup vs unplanned downtime):

```xml
<record id="loss_setup_changeover" model="mrp.workcenter.productivity.loss">
    <field name="name">Setup / Changeover</field>
    <field name="loss_type">availability</field>
    <field name="manual" eval="True"/>
</record>
```

The OEE compute (lesson 26.4) already categorises by loss_type;
new losses inherit their bucket.

## Per-workcenter bottleneck threshold

Default: red = 100%. Some workcenters can run hotter safely
(e.g. high-buffer, low-bottleneck stages).

```python
class MrpWorkcenter(models.Model):
    _inherit = "mrp.workcenter"
    
    bottleneck_red_threshold = fields.Float(default=100)
    bottleneck_amber_threshold = fields.Float(default=80)
```

Update list view decoration to read from workcenter:

```xml
<list decoration-success="utilisation_pct &lt; workcenter_id.bottleneck_amber_threshold"
      decoration-warning="utilisation_pct &gt;= workcenter_id.bottleneck_amber_threshold and utilisation_pct &lt; workcenter_id.bottleneck_red_threshold"
      decoration-danger="utilisation_pct &gt;= workcenter_id.bottleneck_red_threshold">
```

(Caveat: v19 decoration syntax may not support cross-model
field reference in all cases. Test.)

## Per-product MPS template

To preset forecast + safety_stock per product:

```python
class ProductTemplate(models.Model):
    _inherit = "product.template"
    
    mps_forecast_per_week = fields.Float()
    mps_safety_stock = fields.Float()


def _safety_stock_for(self, product_id):
    return self.env["product.product"].browse(
        product_id).product_tmpl_id.mps_safety_stock or 0
```

## Common mistakes + how to recover

- **"Forecast override broke existing periods"** — override only
  affects NEW period creation. Existing periods retain their
  values. Recompute to update.
- **"Bottleneck threshold change didn't propagate to view"** —
  view didn't pick up the new threshold field. Reload view +
  refresh browser.
- **"Per-product MPS template not respected"** — `_forecast_for`
  override wasn't called. Verify the call chain.

## Quiz

**Q1.** History-based forecast on a new product (no history). 
Behaviour?

> Falls back to static forecast via `super()._forecast_for(...)`.
> Important to keep the fallback so new products don't error.

**Q2.** Add a 4th OEE loss type. Effect?

> Native model has 3 (availability / performance / quality).
> A 4th loss_type isn't supported by the OEE compute. Use one of
> the 3 existing buckets.

**Q3.** Per-workcenter threshold — pros vs cons?

> Pro: fine-grained, matches operational reality. Con: more
> config to maintain; possible inconsistency across team
> communication.

**Q4.** Override `_compute_demand` to weight recent SOs more
heavily. Approach?

> Custom decay function. Don't bypass; extend the existing
> method.

**Q5.** New product family with very different forecast pattern.
Strategy?

> Add product_template field for forecast strategy selection
> (static / history / external). Override _forecast_for to
> dispatch.
