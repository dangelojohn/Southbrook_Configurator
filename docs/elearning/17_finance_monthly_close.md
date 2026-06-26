---
course: 17
chapter: 17.32
title: Finance — Run the Monthly Close
duration: 5
audience: Controller doing the month-end close
jtbd: run the monthly close
department: Finance / Accounting
custom_modules: southbrook_finance_pack
---

# Finance — Run the Monthly Close

## When you use this

The 1st-of-the-month ritual. Closes the books for the prior month so
financial statements can be generated.

## The 7-step Southbrook close

Native Odoo handles steps 1-4; Southbrook layers add 5-7.

1. **Reconcile bank statements.** *Accounting → Bank → Reconcile*. Every
   unreconciled line cleared.
2. **Reconcile AR + AP.** *Accounting → Customers / Vendors → Reconciliation*.
3. **Close inventory variances.** *Inventory → Operations → Inventory
   Adjustments → Validate*. Posts COGS journal entries.
4. **Run depreciation.** *Accounting → Operations → Depreciation* (native
   asset model) and **Finance → Asset Register** for the
   Southbrook CCA pack (lesson 17.34).
5. **Reconcile WIP.** *Finance → WIP Report*. The
   `southbrook_finance_pack` view rolls open MOs by cost; reconcile the
   total against GL WIP account.
6. **HST filing prep.** *Finance → HST Return* (lesson 17.33).
7. **Lock the period.** *Accounting → Configuration → Fiscal Years* →
   close the month.

## What to check before locking

- All journals posted (no drafts)
- WIP balance matches Finance Pack report ± $1
- HST input + output reconcile to the period's tax journal
- No NCRs in `scrap` state without a scrap journal entry

## Common gotchas

- **WIP off by more than $1** — usually an open MO with a backdated
  consumption. Open *Finance → WIP Report* and drill to the offending
  MO.
- **Depreciation doubled** — Native + Finance Pack both ran. The pack
  is supposed to skip native-tracked assets; cross-check by asset_id.
- **Tax journal mismatch** — usually a credit note posted to the wrong
  period. Re-open period, fix, re-close.

## Deep dive

→ Course 19 (Finance Pack — to be authored)
