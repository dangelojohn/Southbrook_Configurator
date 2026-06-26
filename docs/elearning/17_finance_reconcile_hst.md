---
course: 17
chapter: 17.33
title: Finance — Reconcile HST Input and Output
duration: 3
audience: Controller filing HST
jtbd: reconcile hst input and output
department: Finance / Accounting
custom_modules: southbrook_finance_pack
---

# Finance — Reconcile HST Input and Output

## When you use this

Quarterly (or monthly if your filing frequency is monthly). Canada CRA
filing — you owe HST collected minus HST paid.

## Where this lives

**Finance → HST Return** (`menu_finance_hst_return`).

## The 4-step flow

1. **New HST Return.** Pick `period_start` + `period_end`. Click *Pull*.
   The `southbrook.hst.return` record auto-fills from `account.move.line`
   filtered to the HST tax accounts.
2. **Review the breakdown.** Three sections:
   - Output HST (collected from customers)
   - Input HST (paid to suppliers, recoverable)
   - Net (output - input = remit to CRA)
3. **Spot-check the top 5 input + 5 output lines.** Common errors:
   personal expense charged to corporate, supplier missing HST registration
   number.
4. **Submit.** Locks the return + posts the remittance journal entry to
   *HST Payable*.

## What gets filed where

The platform does NOT auto-file to CRA — you submit through CRA's
business portal manually. The Southbrook return gives you:

- The exact dollar amounts to type in
- The breakdown for the supporting documentation
- Audit-trail link from each amount to source journal lines

## Common gotchas

- **Input HST higher than expected** — check for capital asset purchases
  that should have been split between current and capital input tax
  credits.
- **Output HST doesn't match POS** — Big-box channel sometimes
  reverse-charges; verify those invoices separately.
- **Period covers a rate change** — January 2027 ON rate change applied
  prospectively; mid-period invoices may use both rates.

## Deep dive

→ Course 19 (Finance Pack — to be authored)
