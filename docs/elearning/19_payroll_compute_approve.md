---
course: 19
chapter: 19.3
title: Payroll Admin — Compute + Approve with CRA 2026 Brackets
duration: 15
audience: Payroll administrator computing the bi-weekly run + Plant GM approving
prereqs: Lessons 19.1 (cadence) + 19.2 (pre-run checks)
custom_modules: southbrook_payroll_ca
---

# Payroll Admin — Compute + Approve with CRA 2026 Brackets

## Who this lesson is for

You've passed the pre-run checks. You're about to click *Compute* on
the run. This lesson covers what the math does, how to spot-check the
results, and what the Plant GM is looking for when they approve.

## Where this lives on the site

**Payroll → Payroll Runs → [the open run]**.

Supporting menus:
- **Payroll → Tax Brackets** (`menu_southbrook_payroll_tax_brackets`)
  — CRA 2026 federal + provincial brackets, read-only.
- **Payroll → Payslips** (`menu_southbrook_payroll_payslips`) — drill
  through to individual slips.

## What your screen shows

### Run form, Totals tab (post-compute)
- Total gross
- Total CPP (employee + employer split)
- Total EI (employee + employer split)
- Total income tax withheld (federal + provincial combined)
- Total RRSP contributions
- Total benefits (taxable + non-taxable)
- Total garnishments
- Total net pay (sum of all payslip nets)

### Payslip form (drill-through)
- *Earnings* — regular, overtime, holiday, bonus
- *Deductions* — CPP, EI, income tax, RRSP, benefits, garnishments
- *YTD Snapshot* — year-to-date CPP / EI / income tax (drives the cap
  math)

## The compute, in plain terms

The compute walks each payslip and applies salary rules in this
order:

### 1. Gross calculation
- **Hourly**: `worked_hours_total × hourly_rate` + overtime ×
  multiplier
- **Salaried**: `annual_salary / pay_periods_per_year` (26 for
  bi-weekly)
- Plus any one-time earnings (bonus, retro, holiday pay)

### 2. Pensionable + insurable earnings
- Pensionable earnings = gross minus non-pensionable (some
  benefits)
- Insurable earnings = gross minus non-insurable (RRSP, some
  benefits)

### 3. CPP (Canada Pension Plan)
- 2026 rate: 5.95% (employee + employer each)
- Annual maximum pensionable earnings (YMPE): $71,300 (2026)
- Annual basic exemption: $3,500
- Formula: `(pensionable_earnings - exemption_pro_rated) × 0.0595`
- YTD cap respected: once YTD CPP = annual max, contributions stop
- *Note: CPP2 enhancement on earnings above YMPE applies in 2026 —
  the engine handles this; you don't need to do anything*

### 4. EI (Employment Insurance)
- 2026 employee rate: 1.66%
- 2026 employer rate: 2.32% (1.4× employee)
- Annual maximum insurable earnings: $63,200 (2026)
- Formula: `insurable_earnings × 0.0166`
- YTD cap respected

### 5. Income tax (federal + provincial)
- Federal: 5 brackets (15%, 20.5%, 26%, 29%, 33%)
- Provincial (Ontario typical): 5 brackets (5.05%, 9.15%, 11.16%,
  12.16%, 13.16%)
- Brackets stored in `southbrook.payroll.tax_bracket` with
  effective_year = 2026
- Annualised gross × bracket math, then div by pay periods
- TD1 credits reduce taxable income before bracket calc

### 6. Other deductions (in order)
- RRSP (pre-tax contribution; reduces income tax for next slip)
- Benefits premiums (employee share)
- Garnishments (capped at 30% of net per wage protection)
- Manual one-time deductions

### 7. Net pay
- `net_pay = gross - cpp - ei - income_tax - rrsp - benefits -
  garnishments - other_deductions`

## Your compute + spot-check flow

1. **Click *Compute*** on the run. State → `computing`. Takes 30-90
   seconds for a 50-employee run.

2. **Wait for state → `pending_approval`**. The status bar advances
   automatically.

3. **Read the *Totals* tab**:
   - Total gross — within ±5% of last cycle?
   - Total CPP — within ±5%?
   - Total EI — within ±5%?
   - Total income tax — within ±10%?
   - Total net — within ±5%?
   - Any big delta is a red flag.

4. **Spot-check 3 payslips**:
   - **A full-period hourly**: gross = approved hours × rate?
     Deductions in line with last cycle?
   - **A full-period salaried**: gross = annual / 26? Deductions
     match prior?
   - **One with a change** (new hire, raise, deduction change):
     verify the change reflected.

5. **For new hires specifically**: open their payslip → YTD
   Snapshot. CPP / EI YTD should equal this slip's amounts (first
   payslip of the year for them).

6. **Submit for approval**. *Cog → Submit for Approval*. State →
   `pending_approval`. Plant GM gets an activity.

## What Plant GM is checking

Plant GM has 2-3 minutes; they look at:

1. **Totals tab** — top-line numbers vs last cycle.
2. **Top 3 nets** — anyone unusually high?
3. **Bottom 3 nets** — anyone unusually low (terminated employee
   with no vacation pay-out)?
4. **Any payslip with a manual override** — visible on the run's
   *Audit Log* tab.

If they approve, state → `approved`. If they reject, state stays
`pending_approval` with a chatter post — you fix + re-submit.

## Common mistakes + how to recover

- **"Total gross is 20% higher than last cycle but I didn't see
  any raises."** Likely cause: bonus paid this cycle, retro pay,
  vacation pay-out for a termination. Drill *Payslips* sorted by
  gross descending; the outliers should explain.

- **"Total income tax is 30% higher; gross only up 10%."** Could
  be: a bonus that pushed someone into a higher bracket; YTD CPP
  cap reached for several employees (CPP stops, so more income is
  taxable); a TD1 update reducing credits. Drill the affected
  slips.

- **"Net pay shows negative."** Deductions exceeded gross.
  Garnishment cap may have been bypassed; check the slip's
  garnishment line, verify ≤ 30% of net. May indicate a
  configuration error on the salary rule.

- **"CPP / EI YTD looks wrong on a new hire."** They likely worked
  elsewhere this year. They should provide a record of CPP / EI
  contributions from prior employer (T4 box 26 / 24). Enter in
  *Employee → Private Info → Prior Year YTD* before the next
  compute.

- **"Plant GM rejected with `please re-check Sam's gross`."**
  Open Sam's payslip; compare to last cycle; verify the variance
  cause is documented. Reply on the rejection chatter; resubmit.

## What the system is doing behind the scenes

- **Salary rule chain** is the workhorse. Rules are stored in
  `hr.salary.rule` with sequence ordering; the engine iterates
  in sequence applying each.
- **Bracket lookup** queries `southbrook.payroll.tax_bracket` for
  the current effective year. Stored centrally so a year-change
  is just a data update.
- **YTD math** queries prior payslips for the same employee in the
  calendar year; sums CPP, EI, income tax, gross. YTD becomes
  input for cap logic.
- **No reverse** — once computed, you can recompute (click
  *Compute* again) but individual slip edits made between are
  preserved if marked `manual_override = True`.

## Quiz (5 questions, applied)

**Q1.** Compute finished. Totals tab shows gross 8% higher than
last cycle. You don't see why. Where do you look first?

> Payslips sorted by `gross delta vs prior` descending. The top 3
> show who moved most. Then drill: bonus? retro? vacation payout?
> wage change?

**Q2.** A new hire's first payslip. CPP YTD shows the slip's own
amount; EI YTD also shows the slip's own amount. Is this right?

> Right IF the new hire had no prior employment in the calendar
> year. If they did, enter their prior YTD via *Employee →
> Private Info → Prior Year YTD* and recompute. Otherwise CPP /
> EI cap math will be wrong all year.

**Q3.** Mid-2026, a long-tenured employee's payslip shows CPP =
$0. Why?

> They hit the annual CPP cap (YMPE × rate). The 2026 cap is
> ($71,300 - $3,500) × 5.95% = $4,034.10. Once YTD CPP = $4,034.10,
> contributions stop for the rest of the year. CPP2 may still apply
> for earnings above YMPE.

**Q4.** Plant GM asks "why is X's net $0 this cycle?" You look —
indeed $0. What happened?

> Likely: gross was low (partial period), AND a fixed-amount
> deduction (benefit premium, RRSP contribution) consumed it.
> Adjust the deduction to skip this period, recompute. Or accept
> the $0 net if the employee was unpaid leave.

**Q5.** The tax brackets effective_year row for 2026 is missing
from `southbrook.payroll.tax_brackets`. Compute fails. What's the
fix?

> Plant GM or sysadmin needs to seed the 2026 brackets. The
> bracket table is data, not config; the values come from CRA's
> annual indexing. v1.1 ships a script to auto-import from CRA;
> until then, manual data XML.

## What this lesson does NOT cover

- EFT generation + bank upload — lesson 19.4.
- Mid-cycle adjustments + garnishments — lesson 19.5.
- T4 year-end — Course 17 lesson 17.40.
- Native Odoo Payroll module concepts (we layer on top of it; the
  Southbrook engine is the source of truth for CRA math).
