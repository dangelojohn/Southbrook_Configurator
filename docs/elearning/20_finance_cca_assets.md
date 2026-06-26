---
course: 20
chapter: 20.3
title: Controller — CCA Depreciation and Asset Register
duration: 13
audience: Controller doing CCA depreciation at year-end (or month-end if monthly basis)
prereqs: Lesson 20.1 (menu + close), basic understanding of CRA tax depreciation
custom_modules: southbrook_finance_pack
---

# Controller — CCA Depreciation and Asset Register

## Who this lesson is for

You're the controller doing CCA depreciation for the T2 (corporate)
tax return. CCA — Capital Cost Allowance — is the Canadian tax-side
depreciation. This is distinct from accounting depreciation (which
hits financial statements) — for now we'll focus on the CCA side
since that's what the Finance Pack adds.

## Where this lives on the site

**Finance → Asset Register** (`menu_finance_asset`).
**Finance → CCA Class** (`menu_finance_cca_class`) — master.

## What your screen shows

### Asset Register list view
- Columns: `name`, `purchase_date`, `cca_class_id`,
  `original_cost`, `current_ucc` (undepreciated capital cost),
  `last_cca_year`
- Decoration-warning: assets where `last_cca_year < current_year - 1`
  (missed an annual compute)
- Decoration-muted: assets with `disposal_date IS NOT NULL`

### Asset form view
- Identification: `name`, `description`, `purchase_date`
- Cost: `original_cost`, `linked_journal_id`
- Classification: `cca_class_id`, `cca_rate` (auto from class)
- Depreciation state:
  - `current_ucc` — read-only, computed from history
  - `last_cca_year` — last year computed
  - `accumulated_cca` — total taken
- *History* tab: `southbrook.finance.cca_entry` rows showing
  year-by-year compute
- *Action buttons*: *Compute CCA* (current year), *Dispose*

### CCA Class form view (mostly read-only)
- `code` (e.g. "Class 8")
- `name` (e.g. "General office equipment")
- `rate` (e.g. 20%)
- `half_year_rule` boolean
- `description` (CRA examples)

## CCA in plain terms

- CCA is a **declining-balance** method (for most classes)
- Each year you claim a percentage of the remaining `current_ucc`
- The percentage = `cca_class_id.rate`
- Year-of-acquisition: **half-year rule** applies — you can only
  claim 50% of the normal CCA in the first year
- The math reduces `current_ucc` each year until you dispose of
  the asset

### Common CCA classes for a cabinet shop

| Class | Rate | What it covers | Example |
|---|---|---|---|
| Class 8 | 20% | General equipment | Office furniture, dust collectors |
| Class 10 | 30% | Motor vehicles, computers | Delivery van |
| Class 12 | 100% | Small tools < $500 | Drill bits, jigs |
| Class 50 | 55% | Computers + software | Servers, laptops |
| Class 53 | 50% | Manufacturing & processing equipment | CNC routers, edge banders |

(2026 rates per CRA T2 Schedule 8; verify with your accountant.)

## The annual compute

### When to compute
- Year-end is the canonical time (immediately after closing
  December)
- Some controllers compute monthly to recognise the tax expense
  evenly — that works too
- The CCA `compute_cca` action is **idempotent within a year** —
  running twice for the same year doesn't double-count

### The flow

1. **Verify the year**: which fiscal year are you computing for?
   Year-end month + your company's year-end define this.

2. **Open the Asset Register**, sort by `last_cca_year`.

3. **For each asset where `last_cca_year < current_year`**:
   - Click *Compute CCA*
   - Wizard shows: `ucc_start`, `cca_claimed`, `ucc_end`
   - Confirm

4. **Bulk compute**: select multiple → Action → *Compute CCA for
   Year*

5. **Post the journal entries**: each compute creates a CCA entry
   record; the totals roll up to a single journal entry per CCA
   class per period. Posting is automatic but can be deferred if
   you want to review first.

### The math, step by step

Example: Class 50 (55% rate), $4,000 original cost, year of
acquisition.

- `ucc_start = $4,000` (= original_cost in year 1)
- Half-year rule: claimable = $4,000 × 50% = $2,000
- CCA: $2,000 × 55% = **$1,100**
- `ucc_end = $4,000 - $1,100 = $2,900`

Year 2 (full year):
- `ucc_start = $2,900`
- CCA: $2,900 × 55% = **$1,595**
- `ucc_end = $2,900 - $1,595 = $1,305`

And so on. The asset eventually depreciates to near zero (the
remainder is written off at disposal).

## Disposal

When you sell, scrap, or trade in an asset:

1. **Open the asset → *Dispose***
2. **Wizard asks**:
   - `disposal_date`
   - `proceeds` — sale price (zero if scrapped)
   - `disposal_journal_id` — where to book the gain/loss
3. **Math fires**:
   - If `proceeds > current_ucc` → recapture (taxable)
   - If `proceeds < current_ucc` AND no remaining assets in class →
     terminal loss (deductible)
   - If `proceeds < current_ucc` AND class still has other assets
     → recapture rules pool the remaining UCC
4. **Journal entry** posts to *Gain on Disposal* or *Loss on
   Disposal*; asset marked `disposed = True`.

## Common mistakes + how to recover

- **"Original cost includes HST."** Wrong. CCA base is pre-tax
  cost. HST is a separately recoverable input tax credit; if it
  ended up in original_cost, you're under-claiming the input
  credit AND over-claiming CCA. Fix: edit the asset's
  `original_cost`; recompute.

- **"Wrong CCA class."** Common with cabinet-shop equipment. CNC
  routers are Class 53 (50%, M&P), not Class 8 (20%, general).
  Wrong class = wrong CCA for years. Fix: edit the class; if
  prior years already filed under wrong class, leave the prior
  filings — adjust going forward.

- **"Forgot to compute last year."** Open the asset; *Compute
  CCA* picks up where it left off. If you missed multiple years,
  compute each in sequence (or use the bulk compute).

- **"Asset disposed but journal didn't post."** The dispose
  wizard generates the journal entry as `draft` if your company's
  journal configuration requires manual posting. Post manually
  from the disposal record.

- **"CCA rate changed mid-year (federal accelerated investment
  incentive)."** The Finance Pack tracks current-year rates;
  accelerated incentive rules need to be configured per
  application. v1.1 will auto-detect AccII eligibility.

## What the system is doing behind the scenes

- **`southbrook.finance.asset`** holds the master + state
- **`southbrook.finance.cca_entry`** holds one row per year per
  asset; the source of truth for `current_ucc`
- **`southbrook.finance.cca_class`** is seeded master data
- **Compute** uses the class rate + the half-year rule flag
- **Disposal** posts a `account.move` to the configured gain/loss
  account; the asset is flagged but NOT deleted (audit retention)

## Quiz (5 questions, applied)

**Q1.** Bought a CNC router for $50,000 + $6,500 HST. Original
cost field?

> $50,000. HST is a separately recoverable input credit, not part
> of the CCA base.

**Q2.** Class 53 (50% rate), $20,000 original cost, year 1 (year
of acquisition). CCA amount?

> Half-year rule: claimable = $20,000 × 50% = $10,000.
> CCA = $10,000 × 50% = **$5,000**.
> `current_ucc` after = $20,000 - $5,000 = $15,000.

**Q3.** Same asset, year 5. `current_ucc = $1,200`. CCA?

> $1,200 × 50% = $600. `current_ucc` after = $600.

**Q4.** Year 6: asset is sold for $300. What posts?

> Asset's `current_ucc` going in = $600. Proceeds = $300.
> $600 > $300 → no recapture; if Class 53 has no other assets,
> $300 terminal loss is deductible; if other assets remain, the
> $300 reduces the pool's UCC.

**Q5.** Did year-end CCA compute. Edited an asset's
`cca_class_id` after. Now the prior compute looks wrong. Recovery?

> Open the asset → *History* tab → the entry for that year shows
> the wrong-class compute. Manually adjust the entry (manager
> only) OR delete it + recompute. Document the change in the
> asset's chatter.

## What this lesson does NOT cover

- Accounting depreciation (vs CCA tax depreciation) — separate
  Odoo Accounting topic.
- Asset impairment write-downs (rare).
- Specifics of accelerated investment incentive — CRA T2 Schedule 8.
- T2 corporate tax filing — accountant's job, not platform's.
