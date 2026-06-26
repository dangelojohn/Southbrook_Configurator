---
course: 17
chapter: 17.34
title: Finance — Add an Asset and Compute CCA
duration: 3
audience: Controller registering a new capital asset
jtbd: add an asset and compute cca
department: Finance / Accounting
custom_modules: southbrook_finance_pack
---

# Finance — Add an Asset and Compute CCA

## When you use this

You bought a piece of equipment, software, or vehicle. CCA (Capital Cost
Allowance) is the Canadian tax depreciation method; the asset register
tracks it for the T2 return.

## Where this lives

**Finance → Asset Register** (`menu_finance_asset`).

## The 5-field minimum

1. **`name`** — descriptive (e.g. "HOMAG Edge Bander, replaced 2026")
2. **`purchase_date`** — when the asset was acquired
3. **`original_cost`** — pre-tax cost
4. **`cca_class_id`** — pick from `southbrook.finance.cca_class`. Common:
   Class 8 (general equipment, 20%), Class 10 (motor vehicles, 30%),
   Class 12 (small tools, 100%), Class 50 (computers, 55%).
5. **`linked_journal_id`** — the GL journal where the purchase was booked

## The half-year rule

CRA applies the *half-year rule* to year-of-acquisition depreciation.
The Southbrook compute logic respects this automatically; you don't need
to halve the rate manually.

## Annual compute

At year-end (or whenever), open the asset → *Compute CCA* button. Adds a
`southbrook.finance.cca_entry` for the year:
- `undepreciated_balance` (UCC) at start
- `cca_claimed` this year
- `closing_ucc`

These roll forward to next year's compute automatically.

## Disposal

When you sell or scrap an asset, open the asset → *Dispose*. Wizard asks
for proceeds + disposal date. Recapture / terminal loss math runs
automatically; journal entry posts to *Gain on Disposal* or *Loss on
Disposal*.

## Common gotchas

- **Original cost includes HST** — wrong. CCA base is pre-tax cost; HST
  is recovered separately as input tax credit.
- **Wrong CCA class** — common with cabinet-shop equipment. CNC routers
  are Class 53 (manufacturing & processing, 50%) NOT Class 8. Verify with
  your accountant before computing.
- **Compute ran but UCC didn't update** — recompute is idempotent within
  a year; running twice for the same year doesn't double-count.

## Deep dive

→ Course 19 (Finance Pack — to be authored)
