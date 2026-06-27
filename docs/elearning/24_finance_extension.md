---
course: 24
chapter: 24.7
title: Finance Pack — Extension Points
duration: 6
audience: Developer adding new Finance Pack capabilities
prereqs: Lessons 24.1-24.6
custom_modules: southbrook_finance_pack
---

# Finance Pack — Extension Points

## The 5 most common extensions

1. New CCA class (e.g. accelerated investment incentive)
2. New asset disposal scenario (e.g. donation)
3. New HST jurisdiction (e.g. PEI)
4. New budget dimension (e.g. project)
5. New financial report (e.g. cash flow summary)

## New CCA class

```xml
<record id="cca_class_53_accii_2025" model="southbrook.finance.cca_class">
    <field name="code">Class 53 (AccII 2025)</field>
    <field name="name">M&amp;P equipment under Accelerated 
        Investment Incentive 2025</field>
    <field name="rate">1.00</field>  <!-- 100% first year -->
    <field name="half_year_rule" eval="False"/>
    <field name="description">Accelerated incentive class for
        M&P equipment acquired between Nov 21, 2025 and 
        Dec 31, 2027. See CRA T2 Schedule 8.</field>
</record>
```

## New asset disposal: donation

Default disposal handles sale/scrap; donations are different
because proceeds = $0 but you get a charitable deduction.

```python
class SouthbrookFinanceAsset(models.Model):
    _inherit = "southbrook.finance.asset"
    
    def action_dispose_as_donation(self, donation_date, charity_id):
        self.ensure_one()
        # Apply standard disposal with proceeds = 0
        self.action_dispose(0, donation_date)
        
        # Plus: post the charitable deduction
        deduction_amount = self.current_ucc  # FMV usually
        self.env["account.move"].create({
            "journal_id": self.env.company.donation_journal_id.id,
            "ref": f"Donation - {self.name}",
            # ... DR Charitable Deduction, CR ... 
        })
        
        # Document the charity
        self.message_post(
            body=_("Asset donated to %s on %s") % (
                charity_id.name, donation_date))
```

## New HST jurisdiction: PEI

```xml
<record id="tax_pei_hst" model="account.tax">
    <field name="name">PEI HST 15%</field>
    <field name="amount">15.0</field>
    <field name="type_tax_use">sale</field>
    <field name="company_id" eval="False"/>
    <field name="tax_group_id" ref="account.tax_group_hst"/>
</record>
```

Then configure on company's `sale_hst_taxes` for PEI-resident
sales.

## New budget dimension: project

To track budget by project:

```python
class SouthbrookFinanceBudget(models.Model):
    _inherit = "southbrook.finance.budget"
    
    project_id = fields.Many2one("project.project")
```

Update the actual compute to filter by project's analytic
account:

```python
@api.depends(...)
def _compute_actual(self):
    for b in self:
        domain = [...]
        if b.project_id:
            domain.append(
                ("analytic_distribution", "ilike",
                 str(b.project_id.analytic_account_id.id) + ":"))
        amls = self.env["account.move.line"].search(domain)
        b.actual_amount = sum(aml.balance for aml in amls)
```

## New financial report: cash flow summary

```python
class SouthbrookFinanceCashFlow(models.Model):
    _name = "southbrook.finance.cash_flow"
    _auto = False
    
    period = fields.Char()
    operating_cash = fields.Float()
    investing_cash = fields.Float()
    financing_cash = fields.Float()
    net_cash = fields.Float()

# SQL view that aggregates account_move_line by cash flow category
```

QWeb report + pivot view follow standard pattern.

## What to avoid

- Don't modify the WIP SQL view — extend with a new view if you
  need different aggregation.
- Don't write to `southbrook.finance.cca_entry` directly — use
  the compute methods.
- Don't post manual journal entries for CCA — use the
  `_post_cca_journal()` helper for audit consistency.

## Quiz

**Q1.** Accelerated CCA on Class 53. Year 1 — different from
half-year rule?

> Yes — AccII typically waives half-year rule. Set
> `half_year_rule = False` on the new class record.

**Q2.** Donating an asset. Proceeds = $0 but FMV = $5k. CCA
recapture?

> Treated as proceeds = $0, so no recapture (UCC was $5k, $0 in,
> terminal loss case). But the charitable deduction = $5k
> (typically FMV) for tax purposes.

**Q3.** PEI HST rate is 15%. Why a separate tax record?

> Different jurisdictions can have different rates; `account.tax`
> records distinguish. The HST Return Pull queries by tax_line_id,
> so each tax (per jurisdiction) shows separately.

**Q4.** Budget by project — actual amount computed by project. Why
analytic_distribution?

> Native Odoo uses analytic accounts for project costing. Linking
> budgets to project requires matching the analytic distribution.

**Q5.** New cash flow report. Why a SQL view?

> Same reasoning as WIP — fully derived data, no business reason
> for a separate table. Use SQL view for read-only aggregation.
