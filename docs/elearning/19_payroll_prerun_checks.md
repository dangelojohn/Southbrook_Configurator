---
course: 19
chapter: 19.2
title: Payroll Admin — Pre-Run Checks (Timesheets, New Hires, Terminations)
duration: 12
audience: Payroll administrator preparing for Wednesday's run pull
prereqs: Lesson 19.1 (menu + cadence)
custom_modules: southbrook_payroll_ca, hr, hr_timesheet
---

# Payroll Admin — Pre-Run Checks (Timesheets, New Hires, Terminations)

## Who this lesson is for

You're the payroll admin on Wednesday morning of payroll week. Before
you click *Pull* on the new payroll run, this lesson is the 12-minute
checklist of what could go wrong and how to catch it.

## Where this lives on the site

Spread across three menu trees:

- **Timesheets → All Timesheets** (native)
- **Employees → Employees** (native)
- **Employees → Contracts** (native) AND **Payroll → Contracts**
  (`menu_southbrook_payroll_contracts`)

## What your screen shows

### Timesheet status query
- `state = draft` filter — anyone still draft = problem
- Group by `employee_id` — see who has 0 hours logged
- Filter by `date >= period_start AND date <= period_end`

### Employee record sanity
- `active = True` — inactive employees skipped by Pull
- `contract_id.state = running` — the contract must be active
- `private_banking_info` populated — for EFT direct deposit
- `tax_credit_amount` — TD1 federal value
- `provincial_tax_credit_amount` — TD1 provincial value
- `sin` — Social Insurance Number (encrypted at rest)

### Contract record sanity
- `wage` — hourly rate or salary base
- `wage_type` — fixed / hourly / commission
- `date_start` ≤ `period_end` AND (date_end IS NULL OR date_end >=
  period_start) — only contracts overlapping the period get pulled
- `pay_frequency = bi_weekly` — must match the run

## The 5-check pre-run

### Check 1: Timesheets fully approved
- *Timesheets → To Approve* — count should be zero by Wednesday AM
- If supervisors are behind, nudge them. Don't pull a run with draft
  timesheets — hourly employees will get $0 gross.
- For salaried employees, timesheets are optional (they get the
  fixed `wage` regardless), but verify the supervisor still
  reviewed.

### Check 2: New hires
- *Employees → Employees* filter `hire_date >= period_start`
- For each new hire:
  - Contract is in `running` state? (HR often forgets this step.)
  - TD1 federal + provincial filled? (Defaults are *single, no
    dependants*; under-withholds if employee has more credits.)
  - Bank info filled? (No bank info = no EFT line = paper cheque
    or delay.)
  - SIN entered? (Mandatory for CRA reporting.)

### Check 3: Terminations
- *Employees → Employees* filter `active = False` AND
  `last_pay_date >= period_start`
- For each termination:
  - Vacation pay paid out on the payslip? (Required by the relevant
    province's ESA.)
  - ROE drafted? (5-day deadline starts at pay period end; lesson
    17.38.)
  - Contract end date set? (If not, they'll continue pulling — even
    though `active = False` filters them, the contract drives some
    YTD math.)

### Check 4: Wage changes
- *Payroll → Contracts* filter `wage_change_date >= period_start`
- For each contract with a recent wage change:
  - Effective date is within the period? (If yes, the payslip
    needs to split — old wage for days before, new wage for days
    after.)
  - The change was approved? (Confirm with HR + manager.)

### Check 5: Leave types affecting pay
- Unpaid leave reduces hours for hourly + may reduce salary for
  salaried (depends on contract).
- Paid leave (vacation, sick) is paid at regular rate.
- Statutory holidays: extra pay differential; ESA varies by
  province.
- *Time Off → Leaves* filter date range — review.

## Spot-check after Pull

After clicking *Pull*, before *Compute*, look at the payslip list:

- **Total count** — does it match active bi-weekly employees minus
  terminations + new hires?
- **Hourly employees** — do their hours look right? Open one or two,
  cross-check against the approved timesheet.
- **Salaried employees** — does their gross match (base wage / pay
  periods per year × applicable periods)?
- **Random sample** — pick 3 random employees; open their payslip;
  verify earnings + deductions look like last cycle.

If anything's off, you can delete the payslip (or the whole run) and
re-pull after fixing the upstream record.

## Common mistakes + how to recover

- **"Pulled with draft timesheets. Hourly employees have 0 hours."**
  Don't compute. Open *Timesheets → To Approve*, get the supervisor
  to approve, then on the run click *Refresh Payslips* (or delete +
  re-pull).

- **"New hire was missing from the pull."** Their `hr.contract` is
  `draft`, not `running`. Activate the contract (state change), then
  *Refresh Payslips* on the run.

- **"Terminated employee was in the pull and got paid for a future
  date."** Their contract `date_end` is unset OR
  `last_pay_date > date_end`. Set `date_end` on the contract,
  delete that payslip from the run, recompute.

- **"Holiday pay missing on hourly slips."** *Compute* doesn't
  auto-add stat holiday pay for hourly. Add via *Earnings → New →
  Holiday Pay* on each affected slip. (Salary employees get it as
  part of base.)

- **"Salaried employee on unpaid leave got full salary."** The
  contract didn't have an `unpaid_leave_reduction = True` flag.
  Adjust the payslip's *Earnings → Salary* line manually + post
  the reason in the chatter.

## What the system is doing behind the scenes

- **Pull** queries `hr.contract` joined to `hr.employee`:
  ```sql
  contract.state = 'running'
    AND contract.pay_frequency = 'bi_weekly'
    AND employee.active = True
    AND contract.date_start <= period_end
    AND (contract.date_end IS NULL OR contract.date_end >= period_start)
  ```
- One `hr.payslip` row per matched contract, linked to the run.
- For hourly contracts, Pull also fetches approved timesheet hours
  in the period and stores them on the slip's `worked_hours_total`.
- Salaried contracts get a synthetic `worked_hours_total` based on
  contract's `weekly_hours` × period_weeks.

## Quiz (5 questions, applied)

**Q1.** Wednesday morning. Supervisor X hasn't approved their team's
timesheets. Their team is 12 people. Do you pull anyway?

> No. If you pull, those 12 hourly employees get 0 gross or wrong
> gross. Nudge X, wait for approval, then pull. If X is out and
> the period is hard-blocked, escalate to Plant GM for delegate
> approval.

**Q2.** New hire started Monday of this pay period. Pull doesn't
include them. Why?

> Their contract is likely still `draft`. HR forgot to activate
> when they finished onboarding. Open the contract, set
> `state = running`, then *Refresh Payslips* on the run.

**Q3.** Terminated employee. Last day was Friday of LAST pay period.
ROE deadline?

> 5 days from last day worked. Last Friday + 5 days = Wednesday this
> week. You need to issue the ROE today (lesson 17.38).

**Q4.** Wage change effective Wednesday of the pay period. How is
the slip computed?

> The platform's salary rule respects the contract's
> `wage_change_date`. Days before use old wage, days from change
> forward use new. Verify by opening the slip → *Earnings* should
> show a split line for that period.

**Q5.** Holiday Monday in this period. Hourly employee's timesheet
shows 0 hours for that day. Do you owe them holiday pay?

> Probably yes per provincial ESA. Add via *Earnings → New → Holiday
> Pay* with the regular rate × stat hours. Verify with HR if
> employee meets the eligibility threshold (some provinces require
> certain hours worked in the qualifying period).

## What this lesson does NOT cover

- The compute math + CRA 2026 brackets — lesson 19.3.
- EFT file generation — lesson 19.4.
- Mid-cycle adjustments — lesson 19.5.
- New employee onboarding flow — Course 17 lesson 17.37.
- ROE filing — Course 17 lesson 17.38.
