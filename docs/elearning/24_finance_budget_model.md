---
course: 24
chapter: 24.5
title: Finance Pack — Budget Model and Pivot View
duration: 7
audience: Developer working on budget logic or pivot reporting
prereqs: Lesson 24.1
custom_modules: southbrook_finance_pack
---

# Finance Pack — Budget Model and Pivot View

## The model

```python
class SouthbrookFinanceBudget(models.Model):
    _name = "southbrook.finance.budget"
    _description = "Budget Line"
```

Fields:

```python
fiscal_year     = fields.Integer(required=True, index=True)
department      = fields.Many2one("hr.department", required=True)
account_id      = fields.Many2one("account.account", required=True)
budget_amount   = fields.Float(required=True)
actual_amount   = fields.Float(compute="_compute_actual", store=False)
variance        = fields.Float(compute="_compute_variance", store=False)
variance_pct    = fields.Float(compute="_compute_variance", store=False)
```

## Actual computation

```python
@api.depends("fiscal_year", "department", "account_id")
def _compute_actual(self):
    for b in self:
        amls = self.env["account.move.line"].search([
            ("account_id", "=", b.account_id.id),
            ("date", ">=", f"{b.fiscal_year}-01-01"),
            ("date", "<=", f"{b.fiscal_year}-12-31"),
            ("parent_state", "=", "posted"),
            ("analytic_distribution", "ilike",
             str(b.department.id) + ":"),
        ])
        b.actual_amount = sum(aml.balance for aml in amls)
```

(Department-budget mapping via `analytic_distribution` JSON.
Native Odoo native budget mechanism.)

## Variance computation

```python
@api.depends("budget_amount", "actual_amount")
def _compute_variance(self):
    for b in self:
        b.variance = b.actual_amount - b.budget_amount
        b.variance_pct = (
            b.variance / b.budget_amount * 100
            if b.budget_amount else 0)
```

## Pivot view

The pivot view groups by department row × account column with
budget + actual + variance measures:

```xml
<record id="view_budget_pivot" model="ir.ui.view">
    <field name="name">southbrook.finance.budget.pivot</field>
    <field name="model">southbrook.finance.budget</field>
    <field name="arch" type="xml">
        <pivot string="Budget vs Actuals">
            <field name="department" type="row"/>
            <field name="account_id" type="col"/>
            <field name="budget_amount" type="measure"/>
            <field name="actual_amount" type="measure"/>
            <field name="variance" type="measure"/>
        </pivot>
    </field>
</record>
```

## Annual budget upload

Excel/CSV import via native data import. Map columns to
`fiscal_year`, `department`, `account_id`, `budget_amount`.

For programmatic seeding:

```python
def seed_budget_year(self, year, csv_path):
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            self.create({
                "fiscal_year": year,
                "department": self.env["hr.department"].search(
                    [("name", "=", row["department"])]).id,
                "account_id": self.env["account.account"].search(
                    [("code", "=", row["account_code"])]).id,
                "budget_amount": float(row["amount"]),
            })
```

## Common mistakes + how to recover

- **"Actual doesn't match GL"** — analytic_distribution JSON
  format mismatch. Verify the department's analytic account is
  configured correctly.
- **"Variance shows huge negative"** — actual exceeds budget. Not
  a bug; that's the point of the report.
- **"Budget rows from prior years pollute pivot"** — pivot view
  has no default fiscal_year filter. Add `fiscal_year` filter
  to the action's domain.

## Quiz

**Q1.** Pivot view rows by department, cols by account. To add
quarters as a third dimension?

> Add `period` field (computed from `account.move.line.date`).
> Then pivot can group by `period` as col1 + account as col2.

**Q2.** Actual amount queries `account.move.line`. Why filter
`parent_state = 'posted'`?

> Draft entries aren't final; their amounts aren't authoritative.

**Q3.** Budget for fiscal year 2027 added in early 2026. Effect?

> Variance shows actual_amount = 0 (no 2027 entries yet) versus
> budget. Shows the future plan; nothing wrong.

**Q4.** Two departments with same account, budget total $10k each.
Pivot shows the account column = $20k?

> No — pivot aggregates the rows. If you filter to one department,
> shows that one's $10k. Total without filter sums to $20k. Pivot
> respects current filter.

**Q5.** Add a "rolling 12 month actual" measure. Approach?

> New computed field that queries the last 12 months instead of
> the fiscal year. Add to pivot as a measure.
