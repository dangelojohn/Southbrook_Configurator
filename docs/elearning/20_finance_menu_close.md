---
course: 20
chapter: 20.1
title: Controller — Your Finance Menu and the 7-Step Monthly Close
duration: 14
audience: Controller doing the monthly close for the Southbrook books
prereqs: Native Odoo Accounting familiarity (chart of accounts, journals, reconciliation)
custom_modules: southbrook_finance_pack
---

# Controller — Your Finance Menu and the 7-Step Monthly Close

## Who this lesson is for

You're the controller doing the monthly close. Native Odoo Accounting
handles the standard journals + reconciliation; the Southbrook Finance
Pack adds the layers specific to a manufacturing shop (WIP, CCA
depreciation, HST). This lesson is the map.

## Where this lives on the site

**Finance** (root menu, `menu_finance_pack_root`).

Submenus:

| Submenu | XML id | Purpose |
|---|---|---|
| Asset Register | `menu_finance_asset` | Capital assets with CCA tracking |
| CCA Class | `menu_finance_cca_class` | Master of CCA classes + rates |
| Budget | `menu_finance_budget` | Departmental budget vs actuals |
| Budget Pivot | `menu_finance_budget_pivot` | Pivot view of budget data |
| HST Return | `menu_finance_hst_return` | Quarterly / monthly HST filing |
| WIP Report | `menu_finance_wip_report` | Work-in-progress reconciliation |
| MI Tiles | `menu_finance_mi_tiles` | Finance views of the MI dashboard |

Plus standard native menus you'll use heavily:
- **Accounting** (native) — journals, COA, reconciliation
- **Inventory → Operations → Inventory Adjustments** (native) —
  posts COGS variance
- **Inventory → Reporting → Stock Valuation** (native) — WIP roll-up
  source data

## The 7-step Southbrook monthly close

Steps 1-4 are native Odoo + GAAP standard. Steps 5-7 are the
Southbrook layer.

### Step 1: Bank reconciliation
- *Accounting → Bank → Reconciliation*
- Every line cleared — no unmatched debits / credits
- Cross-check the EFT debit for the most recent payroll (matches the
  approved run total)
- Multiple bank accounts: reconcile each

### Step 2: AR + AP reconciliation
- *Accounting → Customers → Reconciliation* + *Vendors → Reconciliation*
- Match received payments to invoices
- Match paid bills to vendor bills
- Open invoices > 60 days flagged for follow-up

### Step 3: Inventory variance close
- *Inventory → Operations → Inventory Adjustments*
- Any open adjustment ledger posted
- COGS journal entries triggered automatically by the validation
- Cross-check standard cost variances on Inventory Valuation

### Step 4: Depreciation (native + CCA)
- Native: *Accounting → Operations → Depreciation* (for assets
  using the native asset model)
- CCA: *Finance → Asset Register* (lesson 20.3 deep-dive)
- Both should post for the month being closed

### Step 5: WIP reconciliation (Southbrook layer)
- *Finance → WIP Report* (lesson 20.2)
- Roll-up of open MOs by `cost_so_far`
- Reconcile to GL WIP account; variance < $1 by close

### Step 6: HST filing prep (Southbrook layer)
- *Finance → HST Return* (lesson 20.4)
- Pull the period; review input + output breakdown
- File to CRA via the business portal

### Step 7: Period lock + audit pack
- *Accounting → Configuration → Fiscal Years*
- Close the period (locks edits to that month)
- Generate the audit pack: financial statements + supporting
  schedules (lesson 20.5)

## Your monthly cadence

| Day | What happens |
|---|---|
| 1st of month | Verify all prior-month journals posted (no drafts) |
| 2nd | Bank reconciliation done |
| 3rd | AR + AP reconciled |
| 4th | Inventory variance + depreciation posted |
| 5th | WIP reconciliation |
| 6th | HST return prepared (if quarterly month) |
| 7th | Period lock + audit pack delivered to ownership |

Typical close lands in 5-7 business days. Earlier is possible with
clean upstream data; longer if reconciliation discovers anomalies.

## What your screen shows

### Asset Register list
- Decoration-warning: assets with `next_compute_date < today`
- Decoration-muted: assets with `disposal_date IS NOT NULL`

### WIP Report list
- Grouped by `responsible_team` by default
- Shows `wip_value` (= cost_so_far) per open MO
- Footer: total WIP value

### HST Return form
- `period_start`, `period_end`, `state` (draft / submitted / filed)
- Three computed sections:
  - Output HST collected
  - Input HST paid (recoverable)
  - Net (output - input = remittance)

## Common mistakes + how to recover

- **"Bank rec shows $0 outstanding but month-end balance doesn't
  match bank statement."** Statement may show pending items not yet
  cleared (cheques in transit, deposit floats). Reconcile to
  cleared bank balance, not statement balance.

- **"Closing the period rejected with 'unposted journal entry'."**
  *Accounting → Journal Entries* filter `state = draft AND date IN
  period`. Find + post; retry close. (Drafts exist because someone
  saved without posting; common with manual entries.)

- **"WIP variance is $0.50."** Probably a rounding issue from
  standard cost recalculation. Acceptable; document the rounding
  cause in the close audit log.

- **"HST input higher than expected."** Check for capital asset
  purchases that should have been split between current and capital
  input tax credits. Capital ITCs go to the capital tax account, not
  current.

- **"Depreciation didn't post for a CCA asset."** Compute didn't run
  this month. Open the asset → *Compute CCA* manually. (v1.1 will
  auto-cron this.)

## What the system is doing behind the scenes

- **The Finance Pack adds models**: `southbrook.finance.asset` (CCA),
  `southbrook.finance.cca_class`, `southbrook.finance.budget`,
  `southbrook.finance.hst_return`, plus the WIP report view (no
  model — read-only query).
- **Period lock** is the native `account.move` line-level enforcement;
  Southbrook doesn't override.
- **WIP report** queries `mrp.production` with state IN
  `(confirmed, progress)` and joins to `stock.valuation` for the
  cost-so-far.
- **HST return** queries `account.move.line` filtered to the HST
  tax accounts (configurable per company).

## Quiz (5 questions, applied)

**Q1.** It's the 6th. Step 5 (WIP) is your task today. Where do you
start?

> *Finance → WIP Report*. Read the total. Cross-check to GL WIP
> account balance (*Accounting → Reporting → Trial Balance* →
> filter to the WIP account, period-end balance). Variance < $1 =
> done; > $1 = drill (lesson 20.2 walks this).

**Q2.** Closing rejected: "1 unposted journal entry." Where do you
find it?

> *Accounting → Journal Entries → All Entries* filter `state =
> draft AND date IN this period`. Should land you on 1-3 candidate
> entries. Post the legitimate ones, delete the others (rare
> orphans).

**Q3.** Plant GM asks "what was our gross margin last month?" 5
days into close. What's the most reliable answer?

> "Close isn't complete; preliminary view from *Accounting →
> Reporting → Profit & Loss* with caveat that inventory + WIP +
> depreciation aren't final until close lands on day 7." Don't
> give a number that'll change.

**Q4.** HST quarterly month: input HST is $5k, output HST is
$15k. You file for $10k remittance. Approver asks where it goes.

> CRA Business Portal — *My Business Account → File a Return → HST
> (GST/HST) Return*. The Southbrook return prep is the data;
> filing is manual.

**Q5.** Auditor asks for last quarter's adjustment journal entries
+ supporting docs. Where do you pull this?

> *Accounting → Journal Entries* filter the period; export as CSV.
> Cross-reference each to its chatter (which has docs attached as
> `ir.attachment`). The audit pack lesson (20.5) covers structured
> delivery.

## What this lesson does NOT cover

- WIP reconciliation deep-dive — lesson 20.2.
- CCA depreciation specifics — lesson 20.3.
- HST input/output details — lesson 20.4.
- Period lock + audit pack — lesson 20.5.
- Native Odoo Accounting basics (separate Odoo training).
