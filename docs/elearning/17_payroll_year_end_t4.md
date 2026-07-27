---
course: 17
chapter: 17.40
title: Payroll — Run Year-End T4 Generation
duration: 4
audience: Payroll administrator doing T4 season (January-February)
jtbd: run year-end t4 generation
department: Payroll / HR
custom_modules: southbrook_payroll_ca
---

# Payroll — Run Year-End T4 Generation

## When you use this

January each year. Every Canadian employee needs a T4 slip by the last
day of February covering the prior calendar year's earnings.

## Where this lives

**Payroll → T4 Slips** (`menu_southbrook_payroll_t4`).

## The 5-step flow

1. **Verify all of last year is closed.** No payroll runs in `draft`
   state for the year you're filing.
2. **Generate T4s.** *Generate T4s for Year* action. Pick the year.
   Platform creates one `southbrook.payroll.t4` per employee active in
   that year.
3. **Spot-check 3 slips.** Pick one full-year hourly, one salaried, one
   partial-year (hire or termination during the year). Verify:
   - Box 14 (employment income) = sum of all gross pay
   - Box 16 (CPP contributions)
   - Box 18 (EI premiums)
   - Box 22 (income tax)
   - Box 24 (EI insurable earnings)
   - Box 26 (CPP/QPP pensionable earnings)
4. **Generate the T4 Summary.** Roll-up of all employees; matches the
   total amounts remitted to CRA across the year.
5. **File with CRA.** Two paths:
   - **XML upload** to CRA via the *T4 Internet File Transfer* portal —
     platform's *Export XML* gives you the envelope
   - **Paper** — print the T4 Summary + T4 slips; mail

## Distribute to employees

- Portal: employees see their T4 on `/my/payroll`. Email notification on
  generation.
- Paper: print + mail by Feb 28 (Mar 1 if Feb 28 is a weekend).

## Common gotchas

- **Box 14 doesn't match the General Ledger wages account** — the GL
  may include benefits not in T4 Box 14; reconcile via the T4 Summary
  audit pack.
- **Box 24 / 26 maxed out for high earners** — that's correct; CPP +
  EI have annual maximums. Don't manually edit.
- **T4 doesn't include the December bonus** — only payroll runs with
  `pay_date` in the year count. A December-period bonus paid in January
  goes on next year's T4.
- **Amended T4 needed** — use *T4A* (amended) — don't edit the original.

## Deep dive

→ Course 20 (Payroll CA — to be authored)
