---
course: 17
chapter: 17.38
title: Payroll — Issue a Record of Employment
duration: 3
audience: Payroll administrator processing a termination or leave
jtbd: issue a record of employment
department: Payroll / HR
custom_modules: southbrook_payroll_ca
---

# Payroll — Issue a Record of Employment

## When you use this

Employee leaves (quit, fired, laid off) or starts an unpaid leave of
absence. Service Canada requires the ROE within 5 calendar days. CRA fines
for late filing.

## Where this lives

**Payroll → ROEs** (`menu_southbrook_payroll_roe`).

## The 4-field minimum

1. **`employee_id`** — pick from active or recently terminated employees
2. **`reason_code`** — A (shortage of work), D (illness), E (quit), K
   (other), M (dismissal), N (leave), and ~15 more
3. **`last_day_worked`** — last paid working day
4. **`expected_return_date`** — for leaves, blank for terminations

## Auto-derived fields

The platform pulls these from the past 52 weeks of payroll data:
- Total insurable earnings (last 53 weeks of payslips)
- Total insurable hours
- Pay periods breakdown

## Filing

Two paths:
- **ROE Web** (Service Canada portal) — generate the XML envelope via the
  ROE form's *Export* button; upload manually. Faster.
- **Paper** — print the form; mail it. Slower but works if ROE Web is down.

## Common gotchas

- **Reason code wrong** — common error: "K - Other" gets used when the
  real reason is "A - Shortage" (layoff). Wrong code affects employee's
  EI eligibility. Verify before submitting.
- **Insurable hours look low** — vacation pay paid out at termination
  may have been booked to the wrong period. Verify the payslip pull
  matches your manual count ± 1 hour.
- **Returning employee never filed** — they'll be denied EI mid-claim.
  Apologise + file ASAP; Service Canada is usually understanding for
  first-time errors.

## Deep dive

→ Course 20 (Payroll CA — to be authored)
