---
course: 17
chapter: 17.39
title: Payroll — Adjust a Deduction Mid-Cycle
duration: 2
audience: Payroll administrator handling a manual deduction change
jtbd: adjust a deduction mid-cycle
department: Payroll / HR
custom_modules: southbrook_payroll_ca
---

# Payroll — Adjust a Deduction Mid-Cycle

## When you use this

A garnishment order arrives, an employee asks to start an RRSP
contribution, or a benefit premium changes. You don't want to wait for
the next pay cycle to apply it; you also don't want to forget it for the
upcoming run.

## Two adjustment paths

- **Persistent change** (RRSP, benefits) — edit on `hr.contract`
- **One-time change** (garnishment for this pay period, advance
  recovery) — add a *Manual Earning / Deduction* line on the payslip
  directly

## The persistent flow

1. **Open employee → Contract.** *Deductions* tab.
2. **Add line.** Pick `salary_rule` (RRSP, benefit, etc.). Set
   `amount_type` (fixed / percentage) + value.
3. **Save.** Effective on the next payroll run.

## The one-time flow

1. **Open the payslip** (must be in `draft` state — before *Approve*).
2. **Lines tab → New.** Pick a *Manual* salary rule.
3. **Enter amount + sign** (deduction = negative).
4. **Save the payslip.** Recompute the run.

## Garnishment specifics

- Garnishments are protected by the wage protection act — usually capped
  at 30% of net. The salary rule enforces this; if the order asks for
  more, the platform pays the cap and queues the rest for the next pay.
- File the original garnishment order in the employee's HR documents.

## Common gotchas

- **Persistent change applies retroactively to this run** — it doesn't.
  If the run is already drafted, edit the slip directly OR re-compute
  the run after the contract edit.
- **Forgot which payslip you adjusted** — chatter on the payslip logs
  all changes; search by employee for an audit trail.
- **GL journal mismatch after manual line** — manual lines need a
  destination account; verify on save.

## Deep dive

→ Course 20 (Payroll CA — to be authored)
