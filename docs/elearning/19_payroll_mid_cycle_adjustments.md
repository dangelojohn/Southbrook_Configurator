---
course: 19
chapter: 19.5
title: Payroll Admin — Mid-Cycle Adjustments (Garnishments, RRSP, Advances)
duration: 12
audience: Payroll administrator handling unexpected payroll changes mid-period
prereqs: Lessons 19.1 + 19.2 + 19.3
custom_modules: southbrook_payroll_ca
---

# Payroll Admin — Mid-Cycle Adjustments (Garnishments, RRSP, Advances)

## Who this lesson is for

You're the payroll admin and something has to happen *this pay period*
that you didn't plan for: a court garnishment order arrived, an
employee asked to start RRSP contributions, an advance was issued
against a future paycheck, or a benefit premium changed. This lesson
walks each scenario with the right path.

## Where this lives on the site

Two adjustment paths:

- **Persistent change** — edit on `hr.contract` (Employees → Contracts)
- **One-time change** — edit on the `hr.payslip` directly while the
  run is still `draft` or `computing`

## Garnishments

### When you receive a garnishment order
- Court order arrives (usually mail or fax)
- File the order in the employee's HR documents
- Open the employee's contract → *Deductions* tab → *New*
- Pick salary rule `garnishment_court_order` (seeded)
- Set:
  - `amount_type` — fixed (most orders) or percentage
  - `amount` — the value from the order
  - `start_date`, `end_date` — order's effective window
- Save

### Wage protection cap
- Garnishments capped at **30% of net pay** per provincial wage
  protection acts (Ontario Wages Act, Family Responsibility &
  Support Arrears Enforcement Act, etc.)
- The salary rule enforces this automatically — if the order is
  for 35%, the platform pays 30% and queues the rest
- A `garnishment_remaining` field tracks the carry-forward

### Priority of multiple garnishments
- Family support orders take precedence over commercial debt
- Government tax orders (CRA, IRS) take precedence over both
- Order matters — set `sequence` field on the deduction lines
- If priorities conflict, escalate to legal counsel (not the
  platform)

## RRSP contributions (start, stop, change)

### Starting
- Employee submits a written request to HR
- Open contract → *Deductions* tab → *New*
- Pick salary rule `rrsp_employee` (pre-tax)
- Set `amount_type` + `amount`
- Set `pay_to` to the RRSP custodian (Sun Life, Manulife, etc.)
- Save

### Pre-tax mechanics
- RRSP `amount_type = pretax_percentage` reduces taxable income
- The employee gets the tax savings on every pay (vs filing season)
- Annual maximum: 18% of prior-year earned income, capped at CRA's
  annual limit ($31,560 for 2026)
- Platform tracks YTD RRSP; warns when approaching cap

### Changing
- Edit the existing deduction line; change date stamps the chatter
- Effective on the NEXT compute (current open run may need a
  *Refresh Payslips*)

### Stopping
- Set `end_date` on the deduction line
- Or set `state = inactive`

## Advances (paid before the regular cycle)

### Issuing
- Employee requests; manager approves
- *Employees → Advances → New* (if your tenant has the advances
  module enabled) OR via a manual payroll run with a single
  payslip
- Pay via direct deposit OR cheque
- Mark in HR for recovery

### Recovering
- Next regular run: add a deduction line on that employee's
  payslip — salary rule `advance_recovery`, negative amount
- Net pay reflects the deduction
- Repeat across cycles if the advance > one cycle's net pay

### What to avoid
- **Don't** book the advance as a regular bonus — bonus is
  taxable income; advance is not (until recovered).
- **Don't** forget to recover — employees forget; payroll's job
  to remember.

## Benefit premium changes

### Annual renewal (most common)
- Benefits broker provides new rates Q4
- HR enters the new rates on the benefit master record
- Effective date applies; current payslips re-compute on next *Refresh*
- Verify by spot-checking one payslip after the change

### Mid-cycle changes (rare)
- New employee mid-period: prorate the premium
- Employee promoted to a tier with different benefits: change
  effective the promotion date

## One-time payslip adjustments

When the persistent flow doesn't fit:

### Manual earning
- Open the payslip in `draft` state
- *Earnings* tab → *New*
- Salary rule `manual_earning` (seeded)
- Amount + description
- Save — recompute applies

### Manual deduction
- Same flow, *Deductions* tab → *New*
- Salary rule `manual_deduction`
- Negative if it's reducing (most cases)
- Description mandatory

### Override of a computed value
- Open the line you want to override (e.g. `cpp_employee`)
- Tick `manual_override = True`
- Edit the value
- Recompute respects the override
- The chatter logs that a manual override occurred — auditors notice

## Common mistakes + how to recover

- **"I added an RRSP deduction but it didn't apply to the run that's
  already computed."** Click *Refresh Payslips* on the run. Then
  recompute. (The deduction added to the contract doesn't
  automatically flow back to in-flight payslips.)

- **"Garnishment was over the 30% cap."** Platform paid 30%, queued
  the remainder. Next cycle, the queued amount adds to the next
  cycle's garnishment. Court may need to be notified that full order
  amount can't be met from one pay; usually OK because next-cycle
  pickup is standard.

- **"Forgot to recover an advance from 3 paychecks ago."** Add a
  recovery deduction now for the original advance amount. Employee
  may need to be informed before the cheque; conversation matters
  here. Don't try to take the recovery on a future cycle without
  telling them.

- **"Manual override changed CPP but bank rejected the EFT."**
  Bank doesn't care about CPP override — it only sees net pay.
  Check the recipient's account info instead.

- **"RRSP YTD exceeded the cap."** Platform should have warned;
  if it didn't (configuration), the over-contribution stays on
  the slip but employee will face a CRA tax penalty. Talk to them;
  if recoverable, reduce next slip's contribution.

## What the system is doing behind the scenes

- **Salary rules** are sequenced; persistent contract deductions
  resolve into a `hr.payslip.line` per rule per run.
- **Manual override** sets `quantity` or `amount` directly on the
  computed `hr.payslip.line`, bypassing the salary rule's formula
  for that one slip.
- **Wage protection cap** is enforced in the `garnishment_court_order`
  salary rule's Python code; the carry-forward field
  `garnishment_remaining` is stored on `hr.contract`.
- **Refresh Payslips** triggers re-pull of contract deductions
  without recomputing the existing payslip lines. Then *Compute*
  re-runs the rules with the new deductions.

## Quiz (5 questions, applied)

**Q1.** Court order arrives Wednesday for $400/period. Employee's
typical net pay is $1,000. What does the slip show?

> Garnishment of $300 (= 30% × $1,000 net). $100 carries forward
> to next cycle as `garnishment_remaining`. Employee's net pay
> $700 this cycle.

**Q2.** Employee asks to start RRSP at 5% of gross, effective
immediately. Run is already computed but not approved. What's the
fastest path?

> Open contract → add RRSP deduction at 5% pretax. Effective today.
> *Refresh Payslips* on the open run. *Compute* again. Plant GM
> approval covers the updated values.

**Q3.** $500 advance was issued 4 weeks ago. Recovery was supposed
to be 4 × $125. You forgot all four cycles. Today's the fifth.
Approach?

> Talk to employee first — discuss recovery plan. Then add $500
> single-cycle deduction OR spread over future cycles, depending
> on what employee can afford. Document the conversation in the
> payslip chatter.

**Q4.** Benefit premium changed Jan 1. Today is Jan 5; Q1 run is
in flight. Premium on payslip is still old. Why?

> The change wasn't propagated to the contract; it stayed on the
> benefit master record. Edit the employee's contract → benefit
> line → update amount. *Refresh + Compute*.

**Q5.** You overrode CPP on one slip to $0 because employee hit
the cap. Subsequently saw the YTD wasn't actually capped. Recovery?

> Untick `manual_override = True` on that line. Recompute. Slip
> goes back to the computed value. Audit-log shows the override
> existed; reviewer can ask why; document the reason in chatter.

## What this lesson does NOT cover

- T4 year-end reporting of these deductions — Course 17 lesson 17.40.
- Native Odoo salary rule editor (only Plant GM / sysadmin should
  touch).
- New benefit plan onboarding (HR's job; payroll consumes the result).
