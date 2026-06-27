---
course: 23
chapter: 23.4
title: Payroll CA Module — T4 Generation Internals
duration: 8
audience: Developer working on year-end T4 generation
prereqs: Lessons 23.1, 23.2
custom_modules: southbrook_payroll_ca
---

# Payroll CA Module — T4 Generation Internals

## The model

```python
class SouthbrookPayrollT4(models.Model):
    _name = "southbrook.payroll.t4"
    _description = "T4 Slip"
    _inherit = ["mail.thread"]
```

Fields (matching CRA T4 boxes):

```python
employee_id = fields.Many2one("hr.employee", required=True)
year        = fields.Integer(required=True)

# Box 14: Employment income
box_14_employment_income = fields.Float()
# Box 16: CPP contributions
box_16_cpp = fields.Float()
# Box 18: EI premiums
box_18_ei = fields.Float()
# Box 22: Income tax deducted
box_22_income_tax = fields.Float()
# Box 24: EI insurable earnings
box_24_ei_insurable = fields.Float()
# Box 26: CPP pensionable earnings
box_26_cpp_pensionable = fields.Float()
# ... + boxes 44, 46, 52, 55, etc.

state = fields.Selection([
    ("draft", "Draft"),
    ("generated", "Generated"),
    ("filed", "Filed"),
], default="draft")

amended_id = fields.Many2one("southbrook.payroll.t4")
# ↑ links to original if this is an amended T4
```

## Generation algorithm

```python
@api.model
def generate_t4s_for_year(self, year):
    """Create one T4 per employee active in `year`."""
    employees = self.env["hr.employee"].search([
        ("active", "=", True),
        # ... or terminated this year
    ])
    
    for emp in employees:
        # Skip if T4 already exists for this year + employee
        if self.search_count([
            ("employee_id", "=", emp.id),
            ("year", "=", year),
            ("amended_id", "=", False),
        ]):
            continue
        
        slips = self.env["hr.payslip"].search([
            ("employee_id", "=", emp.id),
            ("date_to", ">=", f"{year}-01-01"),
            ("date_from", "<=", f"{year}-12-31"),
            ("state", "=", "done"),
        ])
        
        vals = {
            "employee_id": emp.id,
            "year": year,
            "box_14_employment_income": sum(s.gross_wage for s in slips),
            "box_16_cpp": sum(
                line.amount for s in slips for line in s.line_ids
                if line.code == "CPP"),
            "box_18_ei": sum(...),
            "box_22_income_tax": sum(...),
            "box_24_ei_insurable": sum(...),
            "box_26_cpp_pensionable": sum(...),
            # ... etc.
        }
        self.create(vals)
```

The wizard `southbrook.payroll.t4.generate_wizard` is the UI
entry point.

## What box 14 includes

Box 14 (employment income) = all taxable employment income in the
year. From salary rules, this is:

- Regular wages
- Overtime
- Bonuses
- Vacation pay
- Holiday pay
- Taxable benefits (e.g. employer-paid life insurance over $25k)

EXCLUDES:
- Non-taxable benefits (e.g. health benefits to a limit)
- RRSP contributions deducted from gross (those reduce box 14)
- Pension contributions if to a registered pension plan

The salary rule's `category_id` drives inclusion. Rules in
category "Gross" + `parent_rule_id` chain to taxable income are
included.

## XML envelope for CRA filing

The `Export XML` button generates the CRA-compliant envelope:

```python
def action_export_xml(self):
    """Generate CRA T4 Internet File Transfer XML envelope."""
    root = ET.Element("T619")
    root.set("xmlns", "http://www.cra-arc.gc.ca/...")
    
    # T4Summary section
    summary = ET.SubElement(root, "T4Summary")
    # ... fields from T4 Summary record
    
    # One T4Slip per employee
    for t4 in self:
        slip = ET.SubElement(root, "T4Slip")
        ET.SubElement(slip, "sin").text = t4.employee_id.sin
        ET.SubElement(slip, "name").text = t4.employee_id.name
        ET.SubElement(slip, "EMPLYR_NM").text = self.env.company.name
        ET.SubElement(slip, "EMPLYR_BN").text = self.env.company.cra_bn
        # ... etc.
    
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
```

The XML is uploaded to CRA's T4 Internet File Transfer portal.

## Amendments

If you need to correct a T4 after filing:

1. Create a NEW T4 record (don't edit the original)
2. Set `amended_id` = original T4
3. Generate the file with corrected values + a "T4A" marker
4. CRA reconciles based on amended_id linkage

## Common mistakes + how to recover

- **"Box 14 doesn't match GL wages account"** — GL may include
  benefits not in box 14. Reconcile via the T4 Summary audit pack
  (compare salary_rule categories to GL account postings).
- **"Box 24/26 maxed for high earners"** — correct; annual CPP +
  EI maximums. Don't manually edit.
- **"Bonus paid in January went on wrong year's T4"** — payslips
  with `pay_date IN year` count for that year. A December-period
  bonus paid in January is on next year's T4.
- **"Amended T4 isn't reaching CRA"** — verify the
  `amended_id` link + the file type. CRA expects T4A as a
  separate file in some cases.

## Quiz

**Q1.** Employee on RRSP contribution all year. Effect on box 14?

> RRSP at sequence < 30 (pre-tax) reduces box 14. RRSP at
> sequence > 80 (post-tax) does not. Verify salary rule
> configuration.

**Q2.** Box 26 (CPP pensionable) — what's included?

> Gross income minus non-pensionable benefits. Per CRA's
> definition; the platform tracks per-payslip and sums for box 26.

**Q3.** December-period bonus paid in January. T4 year?

> Next year (the year of `pay_date`). Even if the bonus was
> "for" December.

**Q4.** T4 generated; need to correct. How?

> New T4 record with `amended_id` set to original. Don't edit the
> original (audit retention).

**Q5.** Where's the CRA XML envelope generated?

> `action_export_xml()` on `southbrook.payroll.t4`. Reads from
> the T4 records + company info to produce the file.
