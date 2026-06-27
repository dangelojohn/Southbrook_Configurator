---
course: 24
chapter: 24.6
title: Finance Pack — MI Engine Integration
duration: 6
audience: Developer working on Finance signals to MI engine
prereqs: Lesson 24.1, MI engine familiarity
custom_modules: southbrook_finance_pack, southbrook_manufacturing_intelligence
---

# Finance Pack — MI Engine Integration

## What Finance surfaces to MI

Three categories of signal:

1. **WIP variance** > threshold → recommendation for controller
2. **Aged AR** > threshold (count or amount) → for sales manager
3. **HST filing deadline approaching** → for controller

## Hook implementation

```python
class MiEngineFinanceExt(models.AbstractModel):
    _inherit = "southbrook.mi.engine"
    
    @api.model
    def _check_finance_signals(self):
        """Called from the MI engine main loop."""
        self._check_wip_variance()
        self._check_aged_ar()
        self._check_hst_deadline()
    
    def _check_wip_variance(self):
        report = self.env["southbrook.finance.wip_report"]
        wip_total = sum(report.search([]).mapped("wip_value"))
        gl_balance = report.gl_balance_query(
            self.env.company.id, fields.Date.today())
        variance = abs(wip_total - gl_balance)
        threshold = self.env.company.wip_variance_threshold or 1000
        if variance > threshold:
            self._emit_recommendation(
                subject=f"WIP variance ${variance:.0f}",
                body=(f"WIP report total ${wip_total:.0f} vs GL "
                      f"${gl_balance:.0f}. Variance ${variance:.0f}. "
                      f"Recommended: investigate before month-end close."),
                persona="controller",
            )
    
    def _check_aged_ar(self):
        cutoff = fields.Date.today() - relativedelta(days=60)
        aged = self.env["account.move"].search([
            ("move_type", "=", "out_invoice"),
            ("amount_residual", ">", 0),
            ("date_due", "<", cutoff),
            ("parent_state", "=", "posted"),
        ])
        if len(aged) >= 5:  # threshold
            total_aged = sum(aged.mapped("amount_residual"))
            self._emit_recommendation(
                subject=f"AR aged 60+ : {len(aged)} customers ${total_aged:.0f}",
                ...,
                persona="sales_manager",
            )
    
    def _check_hst_deadline(self):
        next_filing = self._next_hst_deadline()
        days_until = (next_filing - fields.Date.today()).days
        if days_until <= 7:
            self._emit_recommendation(
                subject=f"HST filing due in {days_until} days",
                ...,
                persona="controller",
            )
```

## Recommendation lifecycle

1. MI engine emits → `hermes.recommendation` row, state `pending_review`
2. Persona-routed to controller / sales manager / Plant GM
3. They Apply / Modify / Reject (Course 21 lesson 21.4)
4. Audit logged on the recommendation chatter

## Dedup logic

The MI engine should dedup so the same recommendation isn't
emitted daily:

```python
def _emit_recommendation(self, subject, body, persona, **kwargs):
    # Dedup: check if a similar rec already pending
    existing = self.env["hermes.recommendation"].search([
        ("subject", "=", subject),
        ("state", "=", "pending_review"),
        ("created_at", ">", fields.Datetime.now() - relativedelta(days=1)),
    ], limit=1)
    if existing:
        return existing
    # Create new
    return self.env["hermes.recommendation"].create({...})
```

## Configuration

Per-company thresholds via system parameters or company-specific
fields:

```python
class ResCompany(models.Model):
    _inherit = "res.company"
    
    wip_variance_threshold = fields.Float(default=1000)
    aged_ar_count_threshold = fields.Integer(default=5)
    aged_ar_days_threshold = fields.Integer(default=60)
```

## Common mistakes + how to recover

- **"WIP variance recommendation fires every day"** — dedup not
  working. Recommendations from > 24h ago shouldn't trigger
  another. Check the dedup query.
- **"Recommendation persona wrong"** — the persona resolution may
  not match the Plant GM's user. Verify persona mapping in
  `southbrook_hermes`.
- **"MI engine doesn't seem to fire"** — `southbrook.mi.engine`
  cron may be off; check cron status.

## Quiz

**Q1.** WIP variance $500, threshold $1,000. Recommendation
emitted?

> No — below threshold. The MI engine remains quiet until variance
> exceeds threshold.

**Q2.** AR aged 60+: 4 customers, $50k. Threshold = 5 count.
Recommendation?

> No — below count threshold even though the dollar exposure is
> material. Threshold logic may need an `OR` clause for amount.

**Q3.** Same as Q2 but recommendation fires on amount > $30k OR
count >= 5. Logic?

> `if len(aged) >= count_threshold OR total > amount_threshold`.

**Q4.** HST deadline check returns same recommendation 7 days in a
row. Why?

> Dedup didn't fire. Each day creates a new recommendation
> because subject changes (`due in 7`, `due in 6`, etc.). Add
> dedup by base subject without the day count.

**Q5.** New Finance signal: month-end period not locked by day 7.
Where add?

> New method in `_check_finance_signals`. Subscribes to fiscal
> year state; if today > 7th and prev period unlocked, emit
> recommendation to controller.
