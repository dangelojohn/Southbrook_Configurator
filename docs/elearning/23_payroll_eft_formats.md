---
course: 23
chapter: 23.3
title: Payroll CA Module — EFT Format Support and Bank Adapters
duration: 9
audience: Developer adding a new bank format or debugging EFT generation
prereqs: Lesson 23.1
custom_modules: southbrook_payroll_ca
---

# Payroll CA Module — EFT Format Support and Bank Adapters

## The EFT generator

`eft_generator.py` produces the bank-specific file format. The
strategy pattern lets multiple formats coexist.

## Supported formats

| Bank | Format | Extension | Adapter |
|---|---|---|---|
| RBC | ACH 80-byte | `.aba` | `_format_rbc_ach()` |
| TD | EFT | `.efx` | `_format_td_efx()` |
| BMO | Direct Deposit | `.txt` | `_format_bmo_dd()` |
| Scotiabank | eDeposit CSV | `.csv` | `_format_scotia_csv()` |
| CIBC | ACH | `.dat` | `_format_cibc_ach()` |
| National | EFT | `.txt` | `_format_nbc_eft()` |

## Top-level method

```python
def generate_eft_file(self, run_id):
    run = self.env["hr.payslip.run"].browse(run_id)
    bank_format = run.company_id.eft_format  # selection field
    
    if bank_format == "rbc":
        content = self._format_rbc_ach(run)
        ext = "aba"
    elif bank_format == "td":
        content = self._format_td_efx(run)
        ext = "efx"
    # ... etc.
    else:
        raise UserError(_("Unsupported EFT format: %s") % bank_format)
    
    attachment = self.env["ir.attachment"].create({
        "name": f"southbrook_payroll_{run.pay_date}_{bank_format}.{ext}",
        "type": "binary",
        "res_model": "hr.payslip.run",
        "res_id": run.id,
        "datas": base64.b64encode(content.encode("utf-8")),
    })
    return attachment
```

## RBC ACH 80 format

Fixed-width 80-character lines, three record types:

```
Header (record type "A")
  Position 1:1       = "A"
  Position 2:10      = originator transit
  Position 11:18     = file creation date YYYYMMDD
  ...

Detail (record type "D"), one per recipient
  Position 1:1       = "D"
  Position 2:10      = recipient transit
  Position 11:23     = recipient account number
  Position 24:33     = amount (10 digits, no decimal — cents)
  ...

Trailer (record type "Z")
  Position 1:1       = "Z"
  Position 2:11      = control total
  Position 12:18     = record count
  ...
```

## Adding a new format

To add HSBC support:

### Step 1: Adapter method

```python
def _format_hsbc(self, run):
    """Generate HSBC EFT file."""
    lines = []
    # Header
    lines.append(self._build_hsbc_header(run))
    # Details
    for slip in run.slip_ids.filtered(lambda s: s.net_wage > 0):
        emp_bank = slip.employee_id.bank_account_id
        if not emp_bank:
            raise UserError(_("Employee %s missing bank info") %
                            slip.employee_id.name)
        lines.append(self._build_hsbc_detail(slip, emp_bank))
    # Trailer
    lines.append(self._build_hsbc_trailer(run))
    return "\n".join(lines)
```

### Step 2: Wire into the selection

```python
class ResCompany(models.Model):
    _inherit = "res.company"
    
    eft_format = fields.Selection(
        selection_add=[("hsbc", "HSBC EFT")],
        ondelete={"hsbc": "set default"},
    )
```

### Step 3: Wire into top-level dispatch

Add the `elif bank_format == "hsbc"` branch.

### Step 4: Test with a known input

HSBC's spec doc has sample files. Run the generator with a known
input + compare output byte-by-byte.

## Recovery format

The summary CSV is generated alongside every bank file:

```python
def _format_summary_csv(self, run):
    """Always-emitted summary for the controller's records."""
    rows = [["employee", "transit", "account", "amount", "method"]]
    for slip in run.slip_ids:
        bank = slip.employee_id.bank_account_id
        method = "EFT" if bank else "CHEQUE"
        rows.append([
            slip.employee_id.name,
            bank.transit if bank else "",
            bank.acc_number if bank else "",
            slip.net_wage,
            method,
        ])
    return self._csv_format(rows)
```

## Common mistakes + how to recover

- **"Bank rejected: invalid format"** — wrong format selected on
  company. Verify `res.company.eft_format` matches your bank.
- **"Bank rejected: posting date in past"** — `run.pay_date` was
  past the bank's accept-by date. Reschedule the pay date,
  regenerate.
- **"One recipient missing from file"** — that employee has no
  `bank_account_id`. They get a cheque (in the summary CSV)
  instead.
- **"Amount format wrong (decimal vs cents)"** — different banks
  use different conventions. RBC uses cents (no decimal); some
  others use dollars.dd. Bug in the adapter.

## Quiz

**Q1.** Why ship a summary CSV alongside every bank file?

> The CSV is human-readable for the controller's records, and
> includes employees on cheque (no EFT). Audit trail.

**Q2.** Adapter raised UserError for missing bank info. What
should happen?

> File generation should NOT abort. Mark the employee as cheque,
> proceed with the remainder. Currently `_format_rbc_ach()`
> raises; should be enhanced to skip + warn.

**Q3.** Bank format on company changes mid-run. Effect?

> Regenerate fires the new format. Previous file (if attached) is
> stale; discard.

**Q4.** Adding a 7th bank format: where minimum?

> 3 places: adapter method, ResCompany selection_add, top-level
> dispatch elif.

**Q5.** Output file is encoded UTF-8 but the bank requires
ASCII-only. Effect?

> May or may not work depending on the bank's parser. Test
> first. If failing, add `content.encode("ascii", "replace")`.
