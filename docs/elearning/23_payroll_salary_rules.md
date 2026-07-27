---
course: 23
chapter: 23.2
title: Payroll CA Module — The Salary Rule Chain
duration: 10
audience: Developer extending salary rules or debugging payroll compute
prereqs: Lesson 23.1
custom_modules: southbrook_payroll_ca
---

# Payroll CA Module — The Salary Rule Chain

## Where rules live

Two homes:

1. **Native `hr.salary.rule`** — the base records (RRSP, benefits,
   garnishments, etc.). Stored in DB; configured via Salary
   Structure.
2. **Southbrook code** — `salary_rules.py` overrides the
   computation methods for CPP / EI / income tax specifically.

## Rule execution order

When `hr.payslip.compute_sheet()` runs:

1. Loads the employee's `hr.contract.struct_id` (salary structure)
2. Loads rules in `struct_id.rule_ids` ordered by `sequence`
3. For each rule, evaluates `condition_python` (skip if False)
4. Evaluates `amount_compute` to produce a `hr.payslip.line`
5. Updates `localdict` with the result (visible to subsequent rules)

## Order matters

Southbrook structure:

```
Sequence 10  — Basic (gross from hours × rate or salary)
Sequence 20  — Overtime
Sequence 25  — Holiday pay
Sequence 30  — RRSP (pre-tax; reduces taxable income)
Sequence 40  — Pensionable Earnings (computed)
Sequence 41  — Insurable Earnings (computed)
Sequence 50  — CPP
Sequence 60  — EI
Sequence 70  — Federal Income Tax
Sequence 71  — Provincial Income Tax
Sequence 80  — Benefit deductions
Sequence 90  — Garnishments
Sequence 95  — Manual adjustments
Sequence 100 — Net Pay
```

If you add a rule, place it correctly in the sequence:
- Before CPP/EI/tax if it affects taxable/pensionable/insurable
  earnings
- After tax if it's a post-tax deduction

## CPP rule example (sequence 50)

```python
# In salary_rules.py
class HrSalaryRule(models.Model):
    _inherit = "hr.salary.rule"
    
    @api.model
    def _compute_cpp_2026(self, payslip, localdict):
        """CPP for 2026. Respects YMPE + YTD cap."""
        ytd_cpp = self._get_ytd("cpp", payslip.employee_id, 2026)
        max_cpp = (71300 - 3500) * 0.0595  # YMPE - exemption × rate
        remaining_cap = max(0, max_cpp - ytd_cpp)
        
        pensionable = localdict.get("PENSIONABLE", 0)
        period_exemption = 3500 / 26  # bi-weekly proration
        cpp_amount = max(0,
            (pensionable - period_exemption) * 0.0595)
        
        # Don't exceed YTD cap
        return min(cpp_amount, remaining_cap)
```

YTD lookup is via the `cron_roll_ytd_totals` cron-maintained
snapshot.

## Income tax (federal + provincial)

```python
def _compute_federal_tax(self, payslip, localdict):
    taxable = localdict.get("GROSS", 0) - localdict.get("RRSP", 0)
    annualised = taxable * 26
    
    # Apply TD1 credits
    td1 = payslip.employee_id.tax_credit_amount
    taxable_after_credits = max(0, annualised - td1)
    
    # Bracket lookup
    brackets = self.env["southbrook.payroll.tax_bracket"].search([
        ("effective_year", "=", 2026),
        ("jurisdiction", "=", "federal"),
    ], order="bracket_low")
    
    annual_tax = 0
    for b in brackets:
        if taxable_after_credits <= b.bracket_low:
            break
        bracket_taxable = min(taxable_after_credits, b.bracket_high) - b.bracket_low
        annual_tax += bracket_taxable * b.rate
    
    return annual_tax / 26  # Per-period
```

Provincial follows the same pattern with `jurisdiction = company's province`.

## Adding a new salary rule

To add a Charitable Giving deduction (pre-tax):

### Step 1: XML

```xml
<record id="rule_charitable_giving" model="hr.salary.rule">
    <field name="name">Charitable Giving (Pre-Tax)</field>
    <field name="code">CHARITY</field>
    <field name="sequence">35</field>  <!-- between RRSP and CPP -->
    <field name="category_id" ref="hr_payroll.DED"/>
    <field name="condition_select">python</field>
    <field name="condition_python">
        contract.charitable_giving_amount > 0
    </field>
    <field name="amount_select">code</field>
    <field name="amount_python_compute">
        result = -contract.charitable_giving_amount
    </field>
</record>
```

### Step 2: Add the contract field

```python
class HrContract(models.Model):
    _inherit = "hr.contract"
    
    charitable_giving_amount = fields.Float()
```

### Step 3: Wire to taxable income reduction

If charitable giving should reduce taxable income, add to the
`taxable` calc in `_compute_federal_tax`.

## Common mistakes + how to recover

- **"New rule didn't apply"** — `condition_python` evaluated False
  for that employee. Check the contract field has a value.
- **"Rule computed wrong amount"** — `localdict` access. Make sure
  you're reading the right key (the available keys depend on
  rules that ran before).
- **"Custom rule broke CPP / EI"** — likely sequence issue. CPP/EI
  expect specific keys (PENSIONABLE, INSURABLE) set by earlier
  rules. Don't move them.

## Quiz

**Q1.** A pre-tax deduction at sequence 25 (before RRSP at 30).
Effect on taxable income?

> Reduces it — anything before tax rules at 70/71 reduces taxable.
> Sequence 25 vs 30 doesn't matter for income tax math; both
> reduce.

**Q2.** Rule at sequence 60 (EI) reads `localdict["INSURABLE"]`.
What was set that key?

> Rule at sequence 41 (Insurable Earnings). If that rule didn't
> fire (condition False), EI gets KeyError. Defensive code uses
> `localdict.get("INSURABLE", 0)`.

**Q3.** Year-over-year: 2027 brackets needed. Add via?

> New data XML file (`tax_brackets_2027.xml`) with the bracket
> records. v1.1 will auto-import; manual until then.

**Q4.** CPP YTD cap was reached mid-period. Math returns?

> `min(period_cpp, remaining_cap) = remaining_cap`. CPP slowly
> reduces to 0 across cycles, never exceeding the annual max.

**Q5.** Add a new earning (e.g. shift differential). Sequence?

> Before sequence 30 (RRSP). It should be part of gross /
> taxable income. Probably sequence 15-20.
