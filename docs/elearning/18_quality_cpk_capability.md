---
course: 18
chapter: 18.4
title: Quality Inspector — Cpk and Process Capability Analysis
duration: 12
audience: Quality manager doing weekly capability review
prereqs: Lesson 18.3 (SPC sampling), basic understanding of standard deviation
custom_modules: southbrook_quality
---

# Quality Inspector — Cpk and Process Capability Analysis

## Who this lesson is for

You're the quality manager doing the weekly capability review. You've
got 30+ SPC samples on each of your top dimensions and you want to know
"is this process capable of meeting spec?" One number tells you: Cpk.

## Where this lives on the site

**Quality → Cpk** (`menu_southbrook_quality_cpk`).

## What your screen shows

### Cpk list view
- Decoration-success: `cpk ≥ 1.33` (capable)
- Decoration-warning: `1.0 ≤ cpk < 1.33` (marginal)
- Decoration-danger: `cpk < 1.0` (not capable)
- Sort by `cpk` ascending shows the trouble dimensions first.

### Cpk form view
- `dimension_id` — what was analysed
- `period_days` — lookback window (default 30)
- `sample_count` — count of SPC samples in the period
- `mean` — sample mean (auto)
- `stdev` — sample standard deviation (auto)
- `cp` — process capability `(USL - LSL) / 6σ`
- `cpk` — process capability index `min((USL-mean)/3σ, (mean-LSL)/3σ)`
- `cpk_lower`, `cpk_upper` — the two sides of the min
- `computed_at` — when last computed
- Notebook tab *Sample List* — the SPC samples that went into the math

## Your weekly capability review

A typical Friday afternoon, 30 minutes:

1. **Open *Quality → Cpk*** sorted by `cpk` ascending.
2. **Review the top 5 dimensions with `cpk < 1.33`**. These are the
   ones to watch.
3. **For each, open the report**:
   - Read `sample_count` — if < 30, the math is noisy; don't act yet.
   - Read `mean` vs `nominal` — is the process centred? If not,
     adjust upstream (toolpath, fixture, operator method).
   - Read `cpk_lower` vs `cpk_upper` — if one side is much worse,
     that's the side at risk; investigate.
4. **Decide actions** for each — three buckets:
   - Centre the process (engineering / operator)
   - Reduce variation (maintenance / material)
   - Loosen the spec (engineering decision — only with good reason)
5. **Post to Plant GM** via Hermes. The MI engine surfaces low-Cpk
   dimensions automatically but the manager benefit reading them
   weekly with context.

## Reading Cpk

```
Cpk < 1.0      → producing some out-of-spec parts (math says so)
1.0 ≤ Cpk < 1.33 → marginal; one shift could push to defect
1.33 ≤ Cpk < 1.67 → capable; the safe zone
Cpk ≥ 1.67    → six-sigma capable; the gold standard
```

Cpk treats both sides of the spec separately. A process can be
"capable" overall but lopsided — `cpk_upper = 1.5` and
`cpk_lower = 0.9` means you're fine on the high side and at risk on
the low side. The low side is what'll fail first.

## When Cpk says "not capable" but you're not seeing scrap

This is the most common Cpk question. Three possibilities:

1. **Spec is wider than reality.** The engineering drawing says
   `±0.2mm` but you can hold `±0.1mm` easily. Cpk math thinks you
   *could* produce defects given the spec, but you're not getting
   close to the spec limits. Action: verify the spec with
   engineering. Maybe tighten the spec to match reality — but then
   Cpk will get worse because variation hasn't changed.

2. **Defects are escaping detection.** You're not finding the
   out-of-spec parts because your inspection cadence misses them.
   Action: inspect more, or improve detection methods.

3. **Cpk math is wrong.** Could be: SPC samples taken under non-
   representative conditions (right after warm-up only); sample
   period too short for true variation; tool calibration drifting
   during the period. Action: investigate sampling protocol.

## When Cpk says "capable" but you're getting scrap

Also possible:

1. **Process drifted within the period.** Cpk is an average over the
   period. If the process started fine and ended bad, the average
   looks OK. Look at the SPC chart for trend (lesson 18.3 rule 4).
2. **Process is bi-modal.** Two distinct populations (e.g. day shift
   + night shift produce different) average to a centred mean but
   each shift is offset. Look at the histogram (form notebook).
3. **Scrap is from a different cause.** Not all scrap is dimensional.
   Check the NCRs — if defect_type is `finish` or `hardware`, those
   are outside Cpk's view.

## Common mistakes + how to recover

- **"`sample_count` is 5 and Cpk is 2.1. That's great, right?"** No
  — Cpk needs ≥30 samples for the math to be trustworthy. Five
  samples have wide confidence intervals; you'd see 0.5 just as
  easily next week. Wait for more samples.

- **"`cpk_lower` is negative."** Process mean is outside the lower
  spec entirely (mean < lsl). Halt the process until investigated.
  Filed NCRs likely.

- **"Cpk dropped from 1.5 to 0.8 in one week."** A capable process
  doesn't drop that fast unless something physical changed.
  Investigate: new operator, new material lot, machine fault. Don't
  blame the math.

- **"Engineering says my spec is wrong but won't update it."**
  Escalate to Plant GM. The Cpk report is your evidence. Without a
  correct spec, capability analysis is meaningless.

## What the system is doing behind the scenes

- **Compute** is on-demand (button) and idempotent — same period +
  same samples = same result.
- **Sample selection** is `southbrook.quality.spc_sample` filtered by
  `dimension_id` + `taken_at within period_days`. The `applicable_
  workcenter_ids` from the dimension doesn't filter; you'll see samples
  from all workcenters that take this dimension. (To split by
  workcenter, file a v1.1 ticket.)
- **Math** is straightforward Python — `mean = sum/n`,
  `stdev = sqrt(sum((x-mean)^2)/(n-1))`, then `cp`, `cpk` formulas.
- **No cron** — Cpk is computed when you click *Compute*. No nightly
  refresh. (v1.1: weekly auto-compute cron.)

## Quiz (5 questions, applied)

**Q1.** Cpk = 1.1 on a dimension. Sample count = 28. Action?

> Wait for more samples before acting. Cpk on < 30 samples has wide
> confidence; the real Cpk might be 0.8 or 1.5. Sample more, recompute
> at 30+. Marginal Cpk reports below 30 samples should be treated as
> "informational only."

**Q2.** Cpk = 0.85, no scrap reported this period. Three explanations
the lesson lists are: spec wider than reality, defects escaping
detection, math wrong. How do you tell which?

> Walk the floor. Watch the process. Measure 10 samples yourself with
> a calibrated tool, compare to the SPC operator's samples. If your
> readings match theirs, spec is probably wider than reality (check
> with engineering). If yours show wider variation, detection is
> escaping. If yours show inconsistency vs SPC entries, sampling
> protocol is broken.

**Q3.** A new dimension was added 2 weeks ago. 22 samples taken so
far. Cpk shows 1.4. Time to act?

> No — 22 samples is below the 30-sample threshold for trustworthy
> Cpk. The 1.4 is a directional signal but not actionable yet. Wait
> for 30+; if it stays around 1.4, then call the process capable.

**Q4.** Cpk_upper = 1.8, cpk_lower = 0.7. Cpk (the min) = 0.7. Action?

> Investigate the lower side specifically. The process mean is
> further from LSL than USL — likely a centering issue. Adjust
> upstream to bring mean closer to nominal. May require tool
> adjustment, fixture change, or operator method update.

**Q5.** Cpk weekly review shows 3 dimensions at Cpk < 1.0. Time to
shut down those workcenters?

> Not automatically. Cpk says the process *could* produce defects;
> the SPC chart says whether it *is*. Cross-check each: if the SPC
> shows actual out-of-spec samples in the period, halt + investigate.
> If SPC is clean (process is centred but variation is too wide for
> the spec), keep running while spec or variation is addressed.

## What this lesson does NOT cover

- SPC sampling mechanics — lesson 18.3.
- NCR creation when scrap is found — lesson 18.2.
- Supplier scoring — lesson 18.5.
- Histogram / process capability index Pp (long-term) — currently
  not computed; v1.1 candidate.
