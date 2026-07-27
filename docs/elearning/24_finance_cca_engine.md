---
course: 24
chapter: 24.2
title: Finance Pack — CCA Depreciation Engine
duration: 9
audience: Developer working on the CCA compute or disposal logic
prereqs: Lesson 24.1, Course 17 lesson 17.34
custom_modules: southbrook_finance_pack
---

# Finance Pack — CCA Depreciation Engine

## The models

```python
class SouthbrookFinanceAsset(models.Model):
    _name = "southbrook.finance.asset"
    _description = "Capital Asset (CCA-tracked)"
    _inherit = ["mail.thread"]


class SouthbrookFinanceCcaEntry(models.Model):
    _name = "southbrook.finance.cca_entry"
    _description = "Yearly CCA Compute Result"
    _order = "year desc"
```

`asset` is the long-lived master. `cca_entry` is one row per asset
per year.

## Compute flow

```python
def action_compute_cca(self):
    self.ensure_one()
    year = self._target_year()  # default current fiscal year
    
    # Skip if already computed
    if self.cca_entry_ids.filtered(lambda e: e.year == year):
        raise UserError(_("CCA already computed for %s") % year)
    
    rate = self.cca_class_id.rate
    half_year = self.cca_class_id.half_year_rule
    
    # Determine UCC start
    prev_entry = self.cca_entry_ids.sorted("year")[-1] \
                 if self.cca_entry_ids else None
    ucc_start = prev_entry.closing_ucc if prev_entry else self.original_cost
    
    # Half-year rule
    is_acquisition_year = (year == self.purchase_date.year)
    claimable_base = ucc_start * 0.5 if (is_acquisition_year and half_year) \
                     else ucc_start
    cca_claimed = claimable_base * rate
    
    ucc_end = ucc_start - cca_claimed
    
    self.env["southbrook.finance.cca_entry"].create({
        "asset_id": self.id,
        "year": year,
        "ucc_start": ucc_start,
        "cca_claimed": cca_claimed,
        "ucc_end": ucc_end,
    })
    
    self.write({"current_ucc": ucc_end, "last_cca_year": year})
    
    # Post journal entry
    self._post_cca_journal(year, cca_claimed)
```

## The journal entry

Per CCA compute, posts:
- DR: CCA Expense (per class)
- CR: Accumulated CCA (per class)

```python
def _post_cca_journal(self, year, amount):
    self.env["account.move"].create({
        "journal_id": self.env.company.cca_journal_id.id,
        "date": fields.Date(year, 12, 31),
        "ref": f"CCA {year} - {self.name}",
        "line_ids": [
            (0, 0, {
                "account_id": self.cca_class_id.cca_expense_account_id.id,
                "debit": amount,
                "name": f"CCA Class {self.cca_class_id.code}",
            }),
            (0, 0, {
                "account_id": self.cca_class_id.accumulated_account_id.id,
                "credit": amount,
                "name": f"CCA Class {self.cca_class_id.code}",
            }),
        ],
    })
```

Journal posts as `state = draft` for controller review; bulk-post
via *Accounting → Journal Entries → Post*.

## Disposal

```python
def action_dispose(self, proceeds, disposal_date):
    self.ensure_one()
    ucc_at_disposal = self.current_ucc
    
    # Determine gain/loss
    delta = proceeds - ucc_at_disposal
    
    if delta > 0:
        # Recapture (taxable income)
        journal_account = self.env.company.gain_on_disposal_account_id
    else:
        # Loss
        journal_account = self.env.company.loss_on_disposal_account_id
    
    # Post disposal journal
    # ... DR asset cost out, DR accumulated CCA out, CR/DR gain/loss
    
    self.write({
        "disposal_date": disposal_date,
        "disposal_proceeds": proceeds,
        "current_ucc": 0,
        "is_disposed": True,
    })
```

### Recapture vs terminal loss

CRA rules:
- If proceeds > UCC and class has other assets → recapture pool
- If proceeds > UCC and class has no other assets → recapture
  taxed as ordinary income
- If proceeds < UCC and class has other assets → reduces pool
  UCC (no immediate loss)
- If proceeds < UCC and class has no other assets → terminal
  loss (deductible)

The engine handles all four cases via `_compute_disposal_treatment()`.

## Common mistakes + how to recover

- **"CCA computed twice for same year"** — the guard raises
  UserError. Hit via the form button only; don't call programmatically.
- **"Wrong CCA class"** — class change re-validates the math.
  Edit class, re-compute. Prior year's entry stays at old class —
  amend the entry if needed.
- **"Disposal posted to wrong account"** — `gain_on_disposal_account_id`
  or `loss_on_disposal_account_id` misconfigured on company.
  Fix on company; the disposal journal can be re-posted.

## Quiz

**Q1.** Class 53 (50%), Year 1 of $20k asset. CCA claimed?

> Half-year: claimable = $10k. CCA = $10k × 50% = **$5,000**.

**Q2.** Class 53, Year 6 of same asset. `current_ucc = $1,200`. CCA?

> $1,200 × 50% = **$600**. UCC end = $600.

**Q3.** Asset sold Year 7 for $300. UCC = $600. Class 53 has 5
other assets. Effect?

> $300 reduces the Class 53 pool's collective UCC. No immediate
> gain or loss; depreciation continues on the remaining pool.

**Q4.** Same except Class 53 has no other assets. Effect?

> $300 proceeds, $600 UCC. Terminal loss = $300. Deductible.
> Posts to Loss on Disposal account.

**Q5.** Compute uses `self.cca_class_id.rate`. Year-over-year
class rate change?

> Current year uses current rate. Prior year entries are
> historical (not recomputed). v1.1 candidate: warn if class rate
> changes after prior computes.
