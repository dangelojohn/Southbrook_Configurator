---
course: 20
chapter: 20.2
title: Controller — WIP Reconciliation Deep-Dive
duration: 15
audience: Controller in the WIP reconciliation step of the monthly close
prereqs: Lesson 20.1 (menu + close), familiarity with Odoo MRP + stock valuation
custom_modules: southbrook_finance_pack, mrp, stock_account
---

# Controller — WIP Reconciliation Deep-Dive

## Who this lesson is for

You're at step 5 of the monthly close (lesson 20.1). The WIP Report
gives you a number; the GL gives you another number. They must
reconcile — within $1 by close, ideally to the penny.

## Where this lives on the site

**Finance → WIP Report** (`menu_finance_wip_report`).

Supporting:
- **Inventory → Reporting → Stock Valuation** (native) — raw
  material side
- **Accounting → Reporting → Trial Balance** (native) — the GL WIP
  account balance
- **Manufacturing → Orders → Manufacturing Orders** (native) — drill
  into individual MOs

## What your screen shows

### WIP Report view (a list view, not a stored model)
- One row per open MO (`state IN (confirmed, progress)`)
- Columns:
  - `mo_ref` (`mrp.production.name`)
  - `product` (`product_id.display_name`)
  - `responsible_team`
  - `cost_so_far` — sum of consumed materials + applied labour +
    overhead so far
  - `cost_to_complete` — estimated remaining
  - `wip_value` — = cost_so_far for accounting purposes
- Group by `responsible_team` by default
- Footer: total `wip_value`

## The reconciliation

The math you're verifying:

```
WIP Report Total = Σ (open MO cost_so_far)
GL WIP Balance  = ledger balance of 211000-WIP (or equivalent)
Variance        = Report - GL
```

Target: |Variance| < $1.

### When variance > $1, the 5 causes

In order of frequency:

#### Cause 1: MO closed without consumption posted
- MO state moved to `done` but a consumption stock move stayed
  draft
- GL says lower than report (the cost moved out of WIP) OR higher
  (the cost stayed in WIP because the move didn't post)
- Find: open *Manufacturing → Orders → Done MOs in period*; look
  for ones with `expected_qty != qty_done`
- Fix: post the missing consumption; redo recompute

#### Cause 2: MO with backdated consumption
- A consumption was posted with `date < period_start`
- It pushed cost INTO WIP retroactively — GL captured it, but the
  report (live) may not show the same MO
- Find: *Stock → Moves* filter `date < period_start AND
  state = done AND raw_material_production_id IS NOT NULL`
- Fix: ideally reverse + re-do with correct date; in close-pressure
  mode, document + accept

#### Cause 3: Scrap not journalled
- A `stock.scrap` posted the stock-side but not the journal-side
- Causes the WIP report to be high (scrap hasn't been
  cost-removed) but GL to be correct (scrap account didn't get
  charged)
- Find: *Inventory → Operations → Scrap* in period
- Fix: post the missing journal entry via *Action → Post Journal*

#### Cause 4: Standard cost change mid-period
- A product's `standard_price` was revalued mid-period
- Existing WIP at old cost; new consumption at new cost
- Variance = revaluation amount
- Find: *Inventory → Operations → Revaluation*
- Fix: post a revaluation journal entry for the period start

#### Cause 5: Closed MO in last month with carry-over
- An MO completed in prior period but had a stock move dated
  this period
- Causes WIP to spike for one period
- Find: *Stock → Moves* filter `production_id IN (last_period
  closed MOs) AND date IN this_period`
- Fix: usually doesn't need fixing — it'll reverse itself when
  the move's other side posts

## Drilling into a variance

When the WIP report total doesn't match GL:

1. **Compare totals by team.** Group by responsible_team; the team
   with the variance localises the search.
2. **Spot-check 5 large MOs.** Open them; verify `cost_so_far` math.
   Material consumed × standard cost + labour applied + overhead.
3. **Run an MO-level CSV export.** Export the WIP report; cross-tab
   against a query on `account.move.line WHERE
   account_id = WIP_account`.
4. **Find the missing MO.** GL has lines the report doesn't, or
   vice versa.

## Common mistakes + how to recover

- **"Total report = $50k, total GL = $52k. Where's the $2k?"** Open
  the report grouped by responsible_team; find the team whose
  subtotal differs from their MO list summed. That's where the
  discrepancy lives.

- **"Variance reconciles by team but not in total."** Rounding;
  document the cause + accept.

- **"Report shows MO 1234 with `wip_value` = $1,200 but the MO is
  marked `done`."** State race condition: the report query is
  cached. Refresh; if still showing, the MO has a draft consumption
  move. Open *Stock → Moves* on the MO.

- **"GL balance is $0 but WIP report says $20k."** Likely cause:
  COGS was posted to a different account (mis-configured product
  category). Audit the `product.category.property_stock_account_*`
  fields for affected products.

- **"WIP report won't open — timeout."** Heavy query in a
  high-MO-count tenant. v1.1 ships a stored snapshot model;
  meantime, filter to a single responsible_team first.

## What the system is doing behind the scenes

- **WIP Report query**: roughly
  ```sql
  SELECT mp.name, mp.product_id, mp.responsible_team,
         SUM(sv.value) AS cost_so_far
  FROM mrp_production mp
  LEFT JOIN stock_move sm ON sm.raw_material_production_id = mp.id
       AND sm.state = 'done'
  LEFT JOIN stock_valuation_layer sv ON sv.stock_move_id = sm.id
  WHERE mp.state IN ('confirmed', 'progress')
  GROUP BY mp.id;
  ```
- The query is wrapped in an Odoo view (not stored) and surfaced
  through `southbrook_finance_pack.wip_report_view`.
- No automatic GL reconciliation — that's why this lesson exists.

## Quiz (5 questions, applied)

**Q1.** WIP Report says $73,500. GL WIP account says $73,250.
Variance = $250. First action?

> Group the report by `responsible_team`. Sum subtotals. Compare
> each team's subtotal against MO-level sums. Find the team with
> the variance; drill into that team's MOs.

**Q2.** You find one MO showing `cost_so_far = $4,200` but the GL
journal entries for that MO sum to $3,950. Cause?

> Likely scrap that didn't journal (cause #3) OR a labour cost
> applied to the MO via productivity but not yet rolled into the
> GL via the labour journal. Check both.

**Q3.** Variance is $0.07. Acceptable?

> Yes — within rounding. Document the cause as "standard cost
> rounding" in the close audit log. Move on.

**Q4.** Variance is $4,500. Day 7 of close. Pressure to lock.
Action?

> Don't lock with that big a variance. Investigate first. Spread
> the time over two days if needed; the wrong close is worse than
> a late close.

**Q5.** WIP report is fine but the GL P&L shows COGS $10k higher
than expected. Where do you check?

> Standard cost change mid-period (cause #4). Look at recent
> `product.template.standard_price` history; large changes can
> drive COGS variance even when WIP balances.

## What this lesson does NOT cover

- Specific GL account configuration (different setups across
  industries; consult Accounting basics).
- Native Odoo inventory valuation methods (FIFO vs standard cost) —
  Odoo Accounting training.
- HST input on capital purchases — lesson 20.4.
- Period lock mechanics — lesson 20.5.
