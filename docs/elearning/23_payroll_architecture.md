---
course: 23
chapter: 23.1
title: Payroll CA Module — Architecture and Install
duration: 8
audience: Developer or admin learning southbrook_payroll_ca internals
prereqs: Python + Odoo addon dev
custom_modules: southbrook_payroll_ca
---

# Payroll CA Module — Architecture and Install

## The module at a glance

- Path: `addons/southbrook_payroll_ca/`
- Version: 19.0.1.0.0
- License: LGPL-3
- Depends on: `base`, `mail`, `hr`, `hr_payroll`, `hr_contract`,
  `account`, `southbrook_manufacturing_intelligence`

## Source layout

```
addons/southbrook_payroll_ca/
├── models/
│   ├── payroll_run.py          — extends hr.payslip.run
│   ├── tax_bracket.py          — CRA 2026 brackets
│   ├── salary_rules.py         — CPP, EI, income tax rules
│   ├── t4_slip.py              — year-end T4
│   ├── roe.py                  — Record of Employment
│   ├── certification.py        — employee certifications
│   └── eft_generator.py        — bank file generation
├── views/                       — 8 view files
├── security/
└── data/
    ├── tax_brackets_2026.xml    — CRA 2026 federal + provincial
    ├── salary_rules.xml         — RRSP, garnishment, manual, etc.
    └── sequence_data.xml
```

## Install

```bash
./scripts/deploy_to_qnap.sh southbrook_payroll_ca
```

Native `hr_payroll` is required first; it's not in CE by default
(was EE-only historically). Verify with:

```sql
SELECT name, state FROM ir_module_module WHERE name = 'hr_payroll';
```

If `hr_payroll` is missing, install it first via Apps. As of
Odoo 19, the community version of payroll is available; the
Southbrook layer extends it.

## What -i does

1. Creates Southbrook-specific tables
2. Loads 2026 CRA tax brackets (federal 5 + Ontario 5 + others
   per province)
3. Loads salary rules (CPP, EI, income tax, RRSP, garnishment,
   benefit, manual)
4. Adds the 7 menus under Payroll
5. Registers a cron at 00:30 to roll YTD totals into new payslips

## v19 install gotchas

Three traps the module dodges:

1. **`numbercall` + `doall` on ir.cron removed** — module uses the
   new `ir.cron` schema (interval_type, interval_number,
   nextcall, lastcall only).
2. **`hr_payroll_account` mixing** — native + Southbrook journal
   configuration is fragile; module declares its own journal
   defaults explicitly.
3. **Selection field extensions need ondelete** — done correctly
   throughout.

## Cron landscape

| Cron | Schedule | Purpose |
|---|---|---|
| `cron_roll_ytd_totals` | 00:30 daily | Updates YTD CPP / EI / income tax per employee |

## CRA bracket data

`southbrook.payroll.tax_bracket` holds:

```python
effective_year = fields.Integer(required=True, index=True)
jurisdiction   = fields.Selection([
    ("federal", "Federal"),
    ("ON", "Ontario"),
    ("AB", "Alberta"),
    ("BC", "British Columbia"),
    # ... + others as needed
])
bracket_low    = fields.Float()
bracket_high   = fields.Float()
rate           = fields.Float(digits=(8, 4))
```

For 2026 Ontario:
- $0 to $52,886: 5.05%
- $52,886 to $105,775: 9.15%
- $105,775 to $150,000: 11.16%
- $150,000 to $220,000: 12.16%
- $220,000+: 13.16%

(Verify exact values for the year you're computing; CRA indexes
annually.)

## Common mistakes + how to recover

- **"hr_payroll not installed"** — install from Apps before this
  module.
- **"Tax brackets missing for 2027"** — data XML only loaded for
  2026. v1.1 will ship an automated CRA-import script; for now,
  data XML for each year.
- **"Native + Southbrook computing different income tax"** —
  conflict between native `hr_payroll` rules and Southbrook
  rules. Make sure Southbrook rules sequence higher (run later)
  to take precedence.

## Quiz

**Q1.** What native module must be installed first?

> `hr_payroll`.

**Q2.** Where are CRA 2026 brackets stored?

> `southbrook.payroll.tax_bracket` records, seeded from
> `data/tax_brackets_2026.xml`.

**Q3.** What's the cron schedule for YTD rollup?

> 00:30 daily (`cron_roll_ytd_totals`).

**Q4.** v19 ir.cron schema dropped which fields?

> `numbercall` and `doall`. Use `interval_type`,
> `interval_number`, `nextcall`, `lastcall` instead.

**Q5.** For a year other than 2026, what's needed?

> A new data file with that year's brackets. Until v1.1 auto-import.
