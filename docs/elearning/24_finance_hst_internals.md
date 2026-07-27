---
course: 24
chapter: 24.4
title: Finance Pack — HST Return Internals
duration: 7
audience: Developer working on HST return logic or tax account configuration
prereqs: Lesson 24.1, native Odoo Tax setup
custom_modules: southbrook_finance_pack
---

# Finance Pack — HST Return Internals

## The model

```python
class SouthbrookFinanceHstReturn(models.Model):
    _name = "southbrook.finance.hst_return"
    _description = "HST Return"
    _inherit = ["mail.thread"]
```

Fields:

```python
name           = fields.Char(default=lambda s: s._make_name())
period_start   = fields.Date(required=True)
period_end     = fields.Date(required=True)
state          = fields.Selection([
    ("draft", "Draft"),
    ("pending_filing", "Pending Filing"),
    ("filed", "Filed"),
], default="draft")

output_hst     = fields.Float(compute="_compute_amounts", store=True)
input_hst      = fields.Float(compute="_compute_amounts", store=True)
net_remittance = fields.Float(compute="_compute_amounts", store=True)

line_ids       = fields.One2many(
    "southbrook.finance.hst_return.line", "return_id")
cra_confirmation = fields.Char()
filed_date     = fields.Date()
```

## Pull algorithm

```python
def action_pull(self):
    self.ensure_one()
    self.line_ids.unlink()
    
    # HST tax accounts (configured per company)
    sale_taxes = self.env.company.sale_hst_taxes
    purchase_taxes = self.env.company.purchase_hst_taxes
    
    # Output side: sale invoice tax lines in period
    output_lines = self.env["account.move.line"].search([
        ("date", ">=", self.period_start),
        ("date", "<=", self.period_end),
        ("tax_line_id", "in", sale_taxes.ids),
        ("parent_state", "=", "posted"),
    ])
    
    # Input side: purchase bill tax lines in period
    input_lines = self.env["account.move.line"].search([
        ("date", ">=", self.period_start),
        ("date", "<=", self.period_end),
        ("tax_line_id", "in", purchase_taxes.ids),
        ("parent_state", "=", "posted"),
    ])
    
    # Create return lines
    for ml in output_lines:
        self.line_ids.create({
            "return_id": self.id,
            "category": "output",
            "move_line_id": ml.id,
            "amount": abs(ml.balance),
        })
    for ml in input_lines:
        self.line_ids.create({
            "return_id": self.id,
            "category": "input",
            "move_line_id": ml.id,
            "amount": abs(ml.balance),
        })
```

## Compute totals

```python
@api.depends("line_ids.amount", "line_ids.category")
def _compute_amounts(self):
    for r in self:
        r.output_hst = sum(
            l.amount for l in r.line_ids if l.category == "output")
        r.input_hst = sum(
            l.amount for l in r.line_ids if l.category == "input")
        r.net_remittance = r.output_hst - r.input_hst
```

## Mark filed

```python
def action_mark_filed(self, cra_confirmation):
    self.ensure_one()
    self.write({
        "state": "filed",
        "cra_confirmation": cra_confirmation,
        "filed_date": fields.Date.today(),
    })
    self._post_remittance_journal()

def _post_remittance_journal(self):
    """Post the period remittance journal entry."""
    # DR Output HST, CR Input HST, CR HST Payable (or DR HST Receivable)
    ...
```

## Tax account configuration

Each company needs:

```python
class ResCompany(models.Model):
    _inherit = "res.company"
    
    sale_hst_taxes = fields.Many2many(
        "account.tax",
        relation="company_sale_hst_taxes_rel",
        domain="[('type_tax_use', '=', 'sale')]",
    )
    purchase_hst_taxes = fields.Many2many(
        "account.tax",
        relation="company_purchase_hst_taxes_rel",
        domain="[('type_tax_use', '=', 'purchase')]",
    )
    hst_receivable_account_id = fields.Many2one("account.account")
    hst_payable_account_id = fields.Many2one("account.account")
```

Configure in *Settings → Companies → Tax & HST*.

## Capital ITC handling

Capital input tax credits (on asset purchases) are special — they
land in the same input pool but track separately for asset
register purposes.

The model adds:

```python
class SouthbrookFinanceHstReturnLine(models.Model):
    _name = "southbrook.finance.hst_return.line"
    
    is_capital_itc = fields.Boolean(
        compute="_compute_is_capital_itc", store=True)


@api.depends("move_line_id.account_id")
def _compute_is_capital_itc(self):
    for line in self:
        line.is_capital_itc = (
            line.move_line_id.account_id.is_capital_account)
```

## Common mistakes + how to recover

- **"Output HST too low"** — invoices in draft. Filter
  account.move where state = draft in period.
- **"Input HST includes personal expenses"** — common mistake;
  bill the personal expense to non-business account, or set
  vendor's tax exemption.
- **"Mark filed but no journal entry"** — `_post_remittance_journal`
  may have failed silently. Check chatter for posting error.

## Quiz

**Q1.** Tax lines for output filter on?

> `tax_line_id IN sale_hst_taxes` AND `parent_state = posted` AND
> date in period.

**Q2.** Why exclude draft account.move?

> Drafts can still be edited; their amounts aren't authoritative
> until posted.

**Q3.** Capital ITC vs current ITC — same input box?

> Same box on CRA filing; tracked separately for asset register.
> `is_capital_itc` flag distinguishes.

**Q4.** Mark filed posts the journal. Posting fails. State?

> State stays `pending_filing` or rolls back. The mark_filed
> action should be transactional. Check the implementation.

**Q5.** Rate change mid-period. Effect on Pull?

> Pull is by invoice date. Invoices before rate change use old
> rate; after, new rate. Math handled correctly per invoice.
