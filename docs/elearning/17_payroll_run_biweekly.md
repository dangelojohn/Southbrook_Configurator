---
course: 17
chapter: 17.36
title: Payroll — Run the Bi-Weekly Payroll
duration: 5
audience: Payroll administrator
jtbd: run the bi-weekly payroll
department: Payroll / HR
custom_modules: southbrook_payroll_ca
---

# Payroll — Run the Bi-Weekly Payroll

## When you use this

Every other Friday. The bi-weekly cycle is the spine of Canadian payroll.

## Where this lives

**Payroll → Payroll Runs** (`menu_southbrook_payroll_runs`).

## The 6-step cycle

1. **Verify timesheets.** *Timesheets → Approve* — supervisors should
   have signed off by Thursday EOD. Reject any draft sheets back to
   employees with a note.
2. **New Payroll Run.** Pick `period_start` + `period_end` (Sunday to
   Saturday usually). Pick `pay_date` (the following Friday).
3. **Pull employees.** *Pull* button auto-populates with all active
   employees on a bi-weekly contract.
4. **Generate payslips.** *Compute*. For each employee:
   - Gross from timesheet hours × `hourly_rate`
   - CPP, EI, Income Tax deductions per CRA 2026 brackets
     (`southbrook.payroll.tax_bracket`)
   - Benefits + RRSP if set on `hr.contract`
   - Net pay
5. **Spot-check 3 slips.** Pick a hourly employee, a salaried employee,
   and someone with a recent change (raise, deduction). Verify numbers.
6. **Lock + post.** *Approve* on the run. Slips go to employees via the
   portal; the GL journal entry posts to expense + payable.

## Direct deposit

After approval, *Generate EFT File*. Downloads an `.aba` file (RBC,
TD, BMO bank format) for upload to your business banking portal. The
platform doesn't push to the bank directly.

## Common gotchas

- **CPP or EI cap reached mid-period** — payslip will show partial
  deductions. The `southbrook_payroll_ca` engine handles this; don't
  override manually.
- **New hire on first pay** — verify `hr.employee.tax_credit_amount` is
  set (TD1 form data); otherwise income tax over-withholds.
- **Holiday in the period** — *Compute* won't auto-add stat holiday pay
  for hourly employees. Enter via *Earnings → Other → Holiday Pay*.

## Deep dive

→ Course 20 (Payroll CA — to be authored)
