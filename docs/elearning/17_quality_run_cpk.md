---
course: 17
chapter: 17.31
title: Quality — Run a Cpk Calculation on a Feature
duration: 2
audience: Quality manager doing capability analysis
jtbd: run a cpk calculation on a feature
department: Quality
custom_modules: southbrook_quality
---

# Quality — Run a Cpk Calculation on a Feature

## When you use this

You have enough SPC samples (lesson 17.29) on a specific dimension to ask
"is this process capable?" Cpk tells you yes / no with one number.

## Where this lives

**Quality → Cpk** (`menu_southbrook_quality_cpk`).

## The 2-step flow

1. **New Cpk Report.** Pick the `dimension_id`. The report pulls all
   `southbrook.quality.spc_sample` rows for that dimension over the past
   `period_days` (default 30).
2. **Click *Compute*.** Returns:
   - `mean` — sample mean
   - `stdev` — sample standard deviation
   - `cp` — process capability (USL - LSL) / 6σ
   - `cpk` — process capability index, min((USL-mean)/3σ, (mean-LSL)/3σ)

## Reading Cpk

- **Cpk < 1.0** — process is producing some out-of-spec parts; not
  capable
- **1.0 ≤ Cpk < 1.33** — marginal; consider tightening
- **1.33 ≤ Cpk < 1.67** — capable
- **Cpk ≥ 1.67** — six-sigma capable; the gold standard

If Cpk says "not capable" but you're not seeing scrap, your spec might be
wider than reality. Verify USL/LSL with engineering before declaring a
process problem.

## Common gotchas

- **Cpk is negative** — process mean is outside the spec entirely.
  Re-check the dimension master before assuming the worst.
- **Cpk says capable but you're getting scrap** — drift may be occurring
  within the period. Look at SPC chart for shifts.

## Deep dive

→ Course 18 (Quality Module — to be authored)
