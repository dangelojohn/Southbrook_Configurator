---
course: 20
chapter: 20.4
title: Controller — HST Input/Output Reconciliation and Filing
duration: 12
audience: Controller filing HST returns (monthly or quarterly basis)
prereqs: Lesson 20.1 (menu + close), CRA HST filing basics
custom_modules: southbrook_finance_pack
---

# Controller — HST Input/Output Reconciliation and Filing

## Who this lesson is for

You're the controller filing HST for Southbrook (or GST for non-HST
provinces). The filing is quarterly for most businesses; monthly if
your annual taxable supplies exceed $6M; annually if under $1.5M.
This lesson covers the period reconciliation + the filing prep.

## Where this lives on the site

**Finance → HST Return** (`menu_finance_hst_return`).

Supporting:
- **Accounting → Reporting → Tax Report** (native) — Odoo's view of
  the same data
- **Accounting → Customers → Invoices** — output HST source
- **Accounting → Vendors → Bills** — input HST source

## What your screen shows

### HST Return list view
- Columns: `name`, `period_start`, `period_end`, `state`,
  `output_hst`, `input_hst`, `net_remittance`
- Decoration-info: state `draft`
- Decoration-warning: state `pending_filing`
- Decoration-success: state `filed`
- Decoration-danger: state `overdue` (passed CRA deadline)

### HST Return form view
- Header: `period_start`, `period_end`, `state`
- Three sections after *Pull*:
  - **Output HST** — collected from customers
    - Line items: invoice list with HST per line
    - Subtotal
  - **Input HST** — paid to suppliers, recoverable
    - Line items: bill list with HST per line
    - Subtotal
  - **Net** — output minus input = remittance to CRA
- Notebook tab *Audit Trail* — link each amount to source
  `account.move.line` rows
- Action buttons: *Pull*, *Submit for Review*, *Mark Filed*

## The standard flow

### 1. Open a new return
- *Finance → HST Return → New*
- Set `period_start` + `period_end` to match your filing frequency
- *Save*

### 2. Pull the data
- Click *Pull*
- Iterates `account.move.line` filtered to the HST tax accounts
  for the period
- Populates Output + Input sections
- May take 10-30 seconds in a busy month

### 3. Review (your part of the work)

This is the substance. Walk three lists:

#### Output HST review
- Read top 10 invoices by HST amount; spot-check that each was a
  taxable supply
- Look for anomalies: zero-rated sales charged HST (should be
  zero), exempt sales charged HST (should be exempt), big-box
  reverse-charge scenarios
- Check the customer's tax flag — sometimes invoices to
  HST-registered customers don't need HST charged

#### Input HST review
- Read top 10 bills by HST amount
- Spot-check eligibility — was it a business expense? Was the
  vendor HST-registered?
- Watch for personal expenses charged to corporate (common
  mistake) — those should be excluded
- Verify the vendor's HST registration number is captured

#### Capital asset purchases
- These split between "current input tax credit" and "capital
  input tax credit" categories
- Capital ITCs use the same input box but have separate accounting
  consequences; Southbrook tracks them via
  `account.account.capital_itc` flag
- Make sure they're correctly classified

### 4. File with CRA
- Submit the return online via CRA's *My Business Account → File
  a Return*
- The platform doesn't auto-file — security/control reasons
- Type in the values from the Southbrook return
- Save the CRA confirmation number

### 5. Mark filed in Odoo
- Open the HST return; click *Mark Filed*
- Enter the CRA confirmation number
- State → `filed`
- The remittance journal entry posts to *HST Payable*

### 6. Pay (if remitting)
- *Accounting → Bank → Make Payment* against the HST Payable
  balance
- Pay date = on or before CRA's due date

## Period schedule

Quarterly filers (most common at Southbrook scale):

| Period | Due date |
|---|---|
| Q1 (Jan-Mar) | April 30 |
| Q2 (Apr-Jun) | July 31 |
| Q3 (Jul-Sep) | October 31 |
| Q4 (Oct-Dec) | January 31 |

Monthly filers: end of the following month.

Late filing penalty: 1% of net tax + 0.25% per month, max 12
months. CRA also charges interest on overdue amounts.

## Common mistakes + how to recover

- **"Pulled the return; output HST is $5k lower than what we
  invoiced."** Some invoices may be in draft state or in a
  different tax account. Open *Accounting → Invoices* filter
  `state = draft` in period; verify or post. Also check that the
  HST tax account is correctly configured on each invoice line.

- **"Input HST higher than expected."** Capital asset purchases.
  These show in input but should be tracked separately as capital
  ITCs. Audit the high-value bills + verify the account.

- **"Personal expense leaked into input HST."** Edit the vendor
  bill; change the tax account to *Non-business* or exclude the
  line. Re-pull the return.

- **"CRA filing rejected: amounts don't match."** Compare
  Southbrook's return values to what you typed in CRA's portal.
  Typos. Re-file with correct values.

- **"Period covers a rate change."** Ontario HST is 13% as of
  early 2026; if a rate change applies mid-period, the platform
  pulls correctly per invoice date but you may need to verify
  invoices around the change date.

- **"I filed but forgot to mark the return as filed in Odoo."**
  Open the return; *Mark Filed*; type the CRA confirmation number.
  Journal entry posts. Audit trail intact.

## What the system is doing behind the scenes

- **HST Return model**: `southbrook.finance.hst_return` plus
  `southbrook.finance.hst_return_line` for the detail
- **Pull** queries `account.move.line` where
  `tax_line_id IN (sale_hst_taxes)` for output and
  `IN (purchase_hst_taxes)` for input
- **Mark Filed** posts a single journal entry: DR Output HST, CR
  Input HST, CR HST Payable (or DR HST Receivable if input >
  output)
- **State machine**: draft → pending_filing → filed
- **No auto-CRA submission** — security boundary; manual filing
  preserves human review

## Quiz (5 questions, applied)

**Q1.** Quarterly filer, Q1 2026 ending March 31. CRA filing
deadline?

> April 30. If you miss, late penalty + interest accrue.

**Q2.** Pulled the return; output HST = $80k, input HST = $35k.
Net = $45k. CRA portal asks for total taxable supplies. Where do
you find that?

> Odoo's native *Accounting → Reporting → Tax Report* gives total
> sales (the base on which HST was charged). Southbrook's HST
> Return only shows the tax amounts; sales base is on the tax
> report. (v1.1 candidate: add total sales to the Southbrook
> return.)

**Q3.** Reviewing input HST, you find a $1,500 ITC on a personal
laptop purchase. What do you do?

> Exclude from the input credit claim. Reverse the bill line's
> tax account designation to a non-recoverable account. Re-pull
> the return. The line becomes a personal expense (employee
> reimbursement, dividend, etc.) — separate decision with HR or
> ownership.

**Q4.** CRA assesses penalty for late filing. Where do you book it?

> *Penalties and interest* expense account. The penalty is NOT
> deductible for income tax purposes; flag the account as
> non-deductible. Conversation with your accountant for the year-
> end T2.

**Q5.** Your invoice to a US customer was billed without HST.
Pull shows it correctly with zero HST. Output HST OK?

> Yes — sales to non-residents for export are zero-rated
> (0% HST). The customer paid no HST; you collected none. Both
> sides clean.

## What this lesson does NOT cover

- Other tax filings (corporate T2, payroll source deductions) —
  separate workflows.
- Provincial sales tax for non-HST provinces (BC, SK, MB) —
  separate Odoo Accounting config.
- HST on import / customs — separate process.
- Period lock — lesson 20.5.
