---
course: 23
chapter: 23.5
title: Payroll CA Module — ROE Math and Filing
duration: 7
audience: Developer working on Record of Employment generation
prereqs: Lesson 23.1
custom_modules: southbrook_payroll_ca
---

# Payroll CA Module — ROE Math and Filing

## The model

```python
class SouthbrookPayrollRoe(models.Model):
    _name = "southbrook.payroll.roe"
    _description = "Record of Employment"
    _inherit = ["mail.thread"]
```

Fields (matching Service Canada ROE blocks):

```python
employee_id = fields.Many2one("hr.employee", required=True)
reason_code = fields.Selection([
    ("A", "A - Shortage of work / layoff"),
    ("D", "D - Illness or injury"),
    ("E", "E - Quit"),
    ("K", "K - Other"),
    ("M", "M - Dismissal"),
    ("N", "N - Leave of absence"),
    # ... ~15 more
], required=True)

last_day_worked       = fields.Date(required=True)
final_pay_period_end  = fields.Date(required=True)
expected_return_date  = fields.Date()  # blank for terminations

# Block 15A — Total insurable hours
total_insurable_hours = fields.Float(compute="_compute_block_15a")
# Block 15B — Total insurable earnings
total_insurable_earnings = fields.Float(compute="_compute_block_15b")
# Block 15C — Per-period breakdown (last 27 weeks)
breakdown_lines = fields.One2many("southbrook.payroll.roe.line", "roe_id")

state = fields.Selection([
    ("draft", "Draft"),
    ("ready", "Ready to File"),
    ("filed", "Filed with Service Canada"),
], default="draft")
```

## Block 15A: Total insurable hours

```python
@api.depends("employee_id", "last_day_worked")
def _compute_block_15a(self):
    for roe in self:
        lookback = self._roe_lookback_window(roe)
        slips = self.env["hr.payslip"].search([
            ("employee_id", "=", roe.employee_id.id),
            ("date_to", ">=", lookback),
            ("date_to", "<=", roe.last_day_worked),
            ("state", "=", "done"),
        ])
        roe.total_insurable_hours = sum(s.worked_hours_total for s in slips)
```

The lookback is **53 weeks back from last_day_worked** for hours
purposes (per Service Canada rules).

## Block 15B: Total insurable earnings

Same query; sum `gross_wage` filtered to EI-insurable earnings.

```python
def _compute_block_15b(self):
    for roe in self:
        lookback = self._roe_lookback_window(roe)
        slips = self.env["hr.payslip"].search([
            ("employee_id", "=", roe.employee_id.id),
            ("date_to", ">=", lookback),
            ("date_to", "<=", roe.last_day_worked),
            ("state", "=", "done"),
        ])
        # Insurable = gross minus non-insurable benefits
        roe.total_insurable_earnings = sum(
            line.amount for s in slips for line in s.line_ids
            if line.category_id.code == "INSURABLE")
```

## Block 15C: Per-period breakdown

Last 27 pay periods (bi-weekly = 54 weeks; weekly = 27 weeks).
Per-period breakdown enables Service Canada to compute EI weekly
amount.

```python
class SouthbrookPayrollRoeLine(models.Model):
    _name = "southbrook.payroll.roe.line"
    
    roe_id = fields.Many2one("southbrook.payroll.roe")
    period_number = fields.Integer()  # 1 = most recent
    period_start = fields.Date()
    period_end = fields.Date()
    insurable_earnings = fields.Float()
```

Auto-populated from payslips.

## ROE Web (Service Canada XML)

The `Export XML` action generates the ROE Web file:

```python
def action_export_xml(self):
    root = ET.Element("ROEWeb")
    # ... Service Canada's prescribed schema
    return ET.tostring(root)
```

Upload to ROE Web portal.

## Reason code consequences

Reason code drives the employee's EI eligibility:

- **A (layoff)** — eligible; wait period applies
- **D (illness)** — sickness benefits, separate from regular EI
- **E (quit)** — NOT eligible (unless quit with cause)
- **K (other)** — Service Canada reviews case-by-case
- **M (dismissal)** — eligibility depends on circumstances

Wrong code = wrong eligibility = employee unfairly denied benefits.
Worth getting right.

## Common mistakes + how to recover

- **"Reason code A used for what was actually E"** — employee
  applies for EI, gets initial approval, Service Canada
  investigates, denies. Issue an amended ROE with correct code.
- **"Insurable earnings look low"** — vacation pay paid out at
  termination may have been booked to wrong period; cross-check.
- **"Period breakdown missing weeks"** — gap in payslips (e.g.
  unpaid leave). Insurable hours = 0 for that period; correct.
- **"ROE Web rejects the XML"** — schema mismatch; CRA periodically
  updates the schema. Test files first with their validation tool.

## Quiz

**Q1.** Last_day_worked = 2026-06-15. Lookback window for hours?

> 53 weeks back from 2026-06-15 ≈ 2025-06-09. All payslips with
> `date_to` between 2025-06-09 and 2026-06-15.

**Q2.** Reason code wrong; ROE already filed. Recovery?

> Issue an AMENDED ROE with correct reason code. Service Canada
> tracks the amendment via `amended_id`.

**Q3.** Block 15B = 0 but employee was paid. Cause?

> The `category_id.code == "INSURABLE"` filter caught nothing.
> Salary rules' categories may not be set correctly. Check.

**Q4.** Bi-weekly pay; 27 periods in block 15C means how many
weeks of history?

> 27 × 2 = 54 weeks ≈ 1 year. Matches Service Canada's window.

**Q5.** Employee terminated; final pay was vacation payout 2
weeks AFTER last day worked. Last_day_worked field?

> The last regular working day (before vacation payout). Vacation
> payout is included in earnings but doesn't extend `last_day_worked`.
