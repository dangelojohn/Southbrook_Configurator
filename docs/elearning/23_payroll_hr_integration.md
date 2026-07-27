---
course: 23
chapter: 23.6
title: Payroll CA Module — Integration with Native hr.payslip
duration: 8
audience: Developer building or debugging the Southbrook ↔ native HR boundary
prereqs: Lessons 23.1, 23.2
custom_modules: southbrook_payroll_ca
---

# Payroll CA Module — Integration with Native hr.payslip

## The relationship

Southbrook doesn't replace `hr.payslip` — it extends it. The
native model:
- Stores per-employee slip data
- Houses the `compute_sheet()` machinery
- Holds the `state` machine (draft → done → cancel)
- Owns the journal entry posting

Southbrook adds:
- Canadian-specific salary rules (CPP, EI, federal+provincial tax)
- YTD tracking (`_get_ytd()` helper)
- T4 + ROE source data
- EFT file generation entry point

## Where the extensions live

```python
# In southbrook_payroll_ca/models/payroll_run.py
class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"
    
    eft_attachment_id = fields.Many2one("ir.attachment", string="EFT File")
    pay_date = fields.Date()  # for EFT posting date
    
    def action_generate_eft(self):
        attachment = self.env["southbrook.payroll.eft_generator"]\
            .generate_eft_file(self.id)
        self.eft_attachment_id = attachment
```

```python
class HrPayslip(models.Model):
    _inherit = "hr.payslip"
    
    is_manual_override = fields.Boolean()  # per-slip override flag
    ytd_snapshot = fields.Json()           # for YTD math
    
    def compute_sheet(self):
        result = super().compute_sheet()
        # post-compute: snapshot YTD for box 24/26 / next slip math
        self._snapshot_ytd()
        return result
```

## YTD math interaction

Native compute doesn't know YTD caps. Southbrook injects this via
the salary rule helper:

```python
@api.model
def _get_ytd(self, code, employee_id, year):
    """Return YTD amount for code (CPP, EI, FED_TAX, etc.) up to
    NOW for the given employee in the given year."""
    prior = self.env["hr.payslip"].search([
        ("employee_id", "=", employee_id),
        ("state", "=", "done"),
        ("date_to", "<", fields.Date.today()),
        ("date_from", ">=", f"{year}-01-01"),
    ])
    total = 0
    for slip in prior:
        for line in slip.line_ids:
            if line.code == code:
                total += line.amount
    return abs(total)  # deductions are negative
```

This is called by every CPP / EI / income tax rule.

## Override semantics

When an admin uses `manual_override`:

```python
def write(self, vals):
    """Allow overrides; track in chatter."""
    if "amount" in vals and self.manual_override:
        self.message_post(
            body=_("Manual override: %s changed from %s to %s") % (
                self.code, self.amount, vals["amount"]))
    return super().write(vals)
```

The override flag preserves the value through `compute_sheet()`
re-runs.

## Recompute behavior

If you click *Compute* twice:
- Manual overrides are PRESERVED (not recomputed)
- Auto-computed lines are RECOMPUTED from current data
- YTD snapshot updates if intermediate slips were posted

This is intentional. Allows admin to override one line + recompute
others without losing the override.

## Common mistakes + how to recover

- **"Override didn't stick across recompute"** — flag wasn't set.
  Always tick `manual_override = True` before editing the amount.
- **"YTD totals look wrong"** — prior slips may not be `state =
  done`. Only done slips count in YTD.
- **"Native hr.payslip wizard conflicts with Southbrook flow"** —
  the Southbrook flow is via `hr.payslip.run`. Don't use the
  native single-slip wizard for Canadian payroll.
- **"Journal entry posts twice"** — native + Southbrook both
  posting. Verify only one is configured to post (via
  `salary_structure.journal_id`).

## Extension hooks

Three useful hooks for downstream:

### Pre-compute hook

```python
class HrPayslip(models.Model):
    _inherit = "hr.payslip"
    
    def compute_sheet(self):
        self._pre_compute_hook()  # YOUR custom logic here
        result = super().compute_sheet()
        return result
    
    def _pre_compute_hook(self):
        """Override to add custom data before salary rules run."""
        pass
```

### Post-compute hook

```python
    def compute_sheet(self):
        result = super().compute_sheet()
        self._post_compute_hook()  # AFTER rules
        return result
```

### Per-line audit

```python
    def _create_payslip_line(self, line_vals):
        line = super()._create_payslip_line(line_vals)
        # YOUR custom logging here
        return line
```

## Quiz

**Q1.** YTD math reads from `hr.payslip.line`. Why filter to
`state = done`?

> Draft slips might still be edited; their amounts don't count
> toward YTD until posted. Filtering ensures the YTD reflects
> approved + paid history.

**Q2.** Manual override flag dropped between save + recompute.
Effect?

> Recompute overwrites the manual value with the auto-computed
> one. Flag persistence is critical. Bug if it's not persisting.

**Q3.** Same employee gets two payslips in same period (e.g.
correction). YTD math?

> Both posted → both count. CPP/EI cap math might
> double-deduct then. Don't post two slips for the same period;
> use override on the first instead.

**Q4.** Native hr.payslip wizard creates a slip outside a run.
What's missing?

> The Southbrook layer's `eft_generation` link, the `pay_date`
> field, the YTD snapshot wiring. Use runs, not individual slips.

**Q5.** New salary rule needs to access total CPP YTD. Best path?

> Use `self._get_ytd("CPP", employee_id, year)` inside the rule's
> `amount_python_compute`. The helper handles the query.
