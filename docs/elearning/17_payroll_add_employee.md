---
course: 17
chapter: 17.37
title: Payroll — Add a New Employee with Canadian Tax Setup
duration: 4
audience: Payroll administrator onboarding a new hire
jtbd: add a new employee with canadian tax setup
department: Payroll / HR
custom_modules: southbrook_payroll_ca
---

# Payroll — Add a New Employee with Canadian Tax Setup

## When you use this

New hire's first day. Get them into payroll before the cutoff so they
appear on the next bi-weekly run.

## The 3-record setup

1. **`hr.employee`** — name, SIN (encrypted), address, hire date,
   department, manager. *Employees → New*.
2. **`hr.contract`** — wage, pay frequency (bi-weekly), benefits,
   start_date. From the employee form: *Contracts → New*.
3. **TD1 federal + provincial** — the new hire fills these out on
   paper / portal; you enter the totals on the contract's *Tax* tab:
   - `td1_federal_amount`
   - `td1_provincial_amount`

## Bank info

For direct deposit, *Employee → Private Information → Banking*. Bank,
transit, account. Pre-validated by the payroll run before EFT file
generation.

## Activate

On the contract: *Run* → state `running`. Employee now appears in the
next payroll run pull.

## Probationary period

If you set `is_probation = True`, the platform tracks the 90-day window
and auto-pings the manager before it ends.

## Common gotchas

- **SIN starts with 9** — that's a temporary SIN (work permit). Set
  `tax_residency = 'non_resident'` if applicable; CRA withholdings
  differ.
- **Tax credit amount left at default** — they'll over-withhold income
  tax all year; refund comes at filing time. Always enter from TD1.
- **Employee added but missing from payroll run** — contract state was
  left at `draft`. Activate.

## Deep dive

→ Course 20 (Payroll CA — to be authored)
