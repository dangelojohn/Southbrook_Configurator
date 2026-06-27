---
course: 26
chapter: 26.2
title: MES + MPS Module — MPS Period and Rolling 13-Week Generator
duration: 9
audience: Developer working on MPS period generation logic
prereqs: Lesson 26.1
custom_modules: southbrook_mes_mps
---

# MES + MPS Module — MPS Period and Rolling 13-Week Generator

## The model

```python
class SouthbrookMesMpsMpsPeriod(models.Model):
    _name = "southbrook.mes_mps.mps_period"
    _description = "MPS Period (Weekly)"
    _inherit = ["mail.thread"]
```

Fields:

```python
name              = fields.Char(default=lambda s: s._make_name())
product_id        = fields.Many2one("product.product", required=True)
product_tmpl_id   = fields.Many2one(related="product_id.product_tmpl_id")
week_start        = fields.Date(required=True, index=True)
year              = fields.Integer(compute="_compute_year_week", store=True)
week_number       = fields.Integer(compute="_compute_year_week", store=True)

forecast_qty         = fields.Float()
safety_stock         = fields.Float()
actual_demand_qty    = fields.Float(compute="_compute_demand", store=True)
planned_supply_qty   = fields.Float(compute="_compute_supply", store=True)
to_supply_qty        = fields.Float(compute="_compute_to_supply", store=True)

state = fields.Selection([
    ("draft", "Draft"),
    ("approved", "Approved"),
    ("executed", "Executed"),
], default="draft")
```

## Year + week from date

```python
@api.depends("week_start")
def _compute_year_week(self):
    for p in self:
        if p.week_start:
            iso = p.week_start.isocalendar()
            p.year = iso[0]
            p.week_number = iso[1]
```

ISO week numbering — week 1 is the week containing the first
Thursday of January.

## Demand computation

```python
@api.depends("product_id", "week_start")
def _compute_demand(self):
    for p in self:
        week_end = p.week_start + timedelta(days=6)
        sos = self.env["sale.order"].search([
            ("state", "in", ["sale", "done"]),
            ("commitment_date", ">=", p.week_start),
            ("commitment_date", "<=", week_end),
        ])
        p.actual_demand_qty = sum(
            line.product_uom_qty
            for so in sos
            for line in so.order_line
            if line.product_id == p.product_id)
```

Demand from confirmed sale orders with commitment_date in the
period. Not pending forecasts; only committed.

## Supply computation

```python
@api.depends("product_id", "week_start")
def _compute_supply(self):
    for p in self:
        week_end = p.week_start + timedelta(days=6)
        mos = self.env["mrp.production"].search([
            ("product_id", "=", p.product_id.id),
            ("date_planned_start", ">=", p.week_start),
            ("date_planned_start", "<=", week_end),
            ("state", "not in", ["draft", "cancel"]),
        ])
        p.planned_supply_qty = sum(mos.mapped("product_qty"))
```

Supply from confirmed/in-progress MOs scheduled in the period.

## To-supply

```python
@api.depends("forecast_qty", "actual_demand_qty",
             "planned_supply_qty", "safety_stock")
def _compute_to_supply(self):
    for p in self:
        demand = max(p.forecast_qty, p.actual_demand_qty)
        p.to_supply_qty = max(0,
            demand + p.safety_stock - p.planned_supply_qty)
```

Uses the larger of forecast or actual demand — covers both
"haven't sold yet but will" and "already sold more than forecast"
scenarios.

## Rolling 13-week generator

```python
@api.model
def action_generate_rolling_13_weeks(self, product_id):
    """For a product, ensure 13 weeks ahead have MPS periods."""
    today = fields.Date.today()
    # Find the current ISO week's Monday
    current_monday = today - timedelta(days=today.weekday())
    
    for offset in range(13):
        week_start = current_monday + timedelta(weeks=offset)
        existing = self.search([
            ("product_id", "=", product_id),
            ("week_start", "=", week_start),
        ], limit=1)
        if not existing:
            self.create({
                "product_id": product_id,
                "week_start": week_start,
                "forecast_qty": self._forecast_for(product_id, week_start),
                "safety_stock": self._safety_stock_for(product_id),
            })
```

Idempotent — calling twice in a week doesn't duplicate.

## Forecast strategy

v1 uses a static forecast from the product's `mps_forecast_per_week`
field. v1.1 candidate: history-based forecasting.

```python
def _forecast_for(self, product_id, week_start):
    """Static forecast from product field."""
    product = self.env["product.product"].browse(product_id)
    return product.product_tmpl_id.mps_forecast_per_week or 0
```

## State transitions

### Approve

```python
def action_approve(self):
    self.write({"state": "approved"})
    # Trigger native MRP via procurement
    for p in self.filtered(lambda x: x.to_supply_qty > 0):
        self.env["procurement.group"].run([
            self.env["procurement.group"].Procurement(
                p.product_id, p.to_supply_qty, ...)])
```

### Mark Executed

Manual (or by cron after week_end passes).

```python
def action_mark_executed(self):
    self.write({"state": "executed"})
```

## Common mistakes + how to recover

- **"Generated periods but no demand showing"** — sale orders
  weren't filtered correctly. Verify `commitment_date` is set on
  the SOs.
- **"Forecast = 0 for all periods"** — `mps_forecast_per_week`
  unset on product template. Set + regenerate.
- **"Approval triggered no MOs"** — procurement.group config
  issue. Verify product routes (manufacture vs buy).

## Quiz

**Q1.** ISO week 1 of 2026 starts when?

> Dec 29 2025 (Monday) — week containing first Thursday (Jan 1
> 2026, which is the first Thursday since the year starts on
> Thursday).

**Q2.** Demand calc uses `commitment_date`, not `date_order`. Why?

> Commitment date = when customer was promised. That's when
> production needs to deliver, not when the order was placed.

**Q3.** Forecast vs actual demand — which used for to_supply?

> `max(forecast, actual)`. Larger of the two. Conservative —
> ensures coverage if actuals exceed forecast.

**Q4.** Rolling 13 weeks: today is week 25. What weeks are
covered?

> Week 25 through week 37 (current Monday + 12 weeks).

**Q5.** Approve fires native procurement run. What happens?

> Procurement.group runs for each approved period with
> to_supply > 0. Creates draft MOs (or POs for purchased products)
> per the demand.
