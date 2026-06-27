---
course: 23
chapter: 23.7
title: Payroll CA Module — Customisation Patterns
duration: 7
audience: Developer extending payroll for new scenarios
prereqs: Lessons 23.1-23.6
custom_modules: southbrook_payroll_ca
---

# Payroll CA Module — Customisation Patterns

## The four most common customisations

1. New salary rule (lesson 23.2)
2. New EFT format (lesson 23.3)
3. New jurisdiction (e.g. Quebec QPP instead of CPP)
4. New benefit type (e.g. health spending account)

## New jurisdiction: Quebec

Quebec uses QPP instead of CPP. To add:

### Step 1: Add jurisdiction to tax_bracket

```python
class SouthbrookPayrollTaxBracket(models.Model):
    _inherit = "southbrook.payroll.tax_bracket"
    
    jurisdiction = fields.Selection(
        selection_add=[("QC", "Quebec")],
        ondelete={"QC": "set default"},
    )
```

### Step 2: Add QPP rule

QPP differs from CPP:
- Different rate (6.4% as of 2026)
- Different YMPE
- Different exemption

Add rule in a custom addon:

```xml
<record id="rule_qpp_2026" model="hr.salary.rule">
    <field name="name">QPP (Quebec)</field>
    <field name="code">QPP</field>
    <field name="sequence">50</field>  <!-- same as CPP -->
    <field name="condition_python">
        contract.company_id.partner_id.state_id.code == 'QC'
    </field>
    <field name="amount_python_compute">
        ytd = self._get_ytd('QPP', payslip.employee_id.id, 2026)
        max_qpp = (74900 - 3500) * 0.064  # QC YMPE - exemption × rate
        # ... etc.
    </field>
</record>
```

### Step 3: Disable CPP for Quebec employees

```xml
<record id="rule_cpp_2026" model="hr.salary.rule">
    <field name="condition_python">
        contract.company_id.partner_id.state_id.code != 'QC'
    </field>
</record>
```

Now CPP fires for non-QC employees; QPP fires for QC employees.

## New benefit type: Health Spending Account (HSA)

HSA is an employer-paid health benefit that's:
- Non-taxable to the employee (in most provinces)
- Pre-tax for box 14 calculation

### Step 1: Contract field

```python
class HrContract(models.Model):
    _inherit = "hr.contract"
    
    hsa_amount_per_period = fields.Float(string="HSA Contribution / Period")
```

### Step 2: Salary rule

```xml
<record id="rule_hsa" model="hr.salary.rule">
    <field name="name">HSA Contribution</field>
    <field name="code">HSA</field>
    <field name="sequence">25</field>  <!-- before tax calc -->
    <field name="category_id" ref="hr_payroll.BENEFITS"/>
    <field name="amount_python_compute">
        result = contract.hsa_amount_per_period
    </field>
</record>
```

### Step 3: Tax exemption

The salary rule alone doesn't reduce box 14 unless it's in a
non-taxable category. Verify the category configuration.

## New report: pay summary letter

Goal: a per-employee PDF summarizing the pay period for HR
distribution.

### Step 1: Report record

```xml
<report id="action_report_pay_summary"
        string="Pay Summary Letter"
        model="hr.payslip"
        report_type="qweb-pdf"
        file="southbrook_payroll_extensions.report_pay_summary"
        name="southbrook_payroll_extensions.pay_summary_template"/>
```

### Step 2: QWeb template

```xml
<template id="pay_summary_template">
    <t t-call="web.html_container">
        <t t-foreach="docs" t-as="o">
            <div class="page">
                <h2>Pay Summary for <t t-esc="o.employee_id.name"/></h2>
                <p>Period: <t t-esc="o.date_from"/> to <t t-esc="o.date_to"/></p>
                <table>
                    <tr><td>Gross</td><td><t t-esc="o.gross_wage"/></td></tr>
                    <tr><td>Net</td><td><t t-esc="o.net_wage"/></td></tr>
                </table>
            </div>
        </t>
    </t>
</template>
```

### Step 3: Wire button on payslip form

Available in the form's *Print* dropdown automatically.

## What to avoid

- Don't modify `tax_brackets_2026.xml` after install — the rates
  are seeded with `noupdate="1"`. Add a NEW year's data file
  instead.
- Don't override CPP/EI rule code directly — fork into a custom
  addon and extend via condition.
- Don't bypass salary rule chain for "simple" calculations. The
  chain is the audit trail.

## Quiz

**Q1.** New jurisdiction Manitoba. Add brackets via?

> Custom data XML for Manitoba in a separate addon. Include MB
> code in `jurisdiction` selection.

**Q2.** HSA payment to employee. Box 14 effect?

> Non-taxable → reduces box 14 if classified in a non-taxable
> category. Verify with `salary_rule.category_id`.

**Q3.** QPP and CPP both fire for same employee. Why?

> Condition_python on rules conflicts; one shouldn't fire. Check
> the conditions. Should be mutually exclusive on
> `state_id.code == 'QC'`.

**Q4.** Custom report works in test DB but fails in prod. Why?

> ir.actions.report record not loaded. Verify the addon was
> deployed + the data XML was loaded.

**Q5.** New benefit type stops T4 box 14 from matching GL.
Recovery?

> Verify the benefit's category. Some non-taxable benefits still
> hit GL wages account (in which case GL > box 14). May be
> correct; document the gap.
