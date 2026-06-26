---
course: 18
chapter: 18.3
title: Quality Inspector — SPC Sampling Discipline
duration: 15
audience: Quality inspector running SPC sampling, quality manager setting policy
prereqs: Lessons 18.1 (menu orientation) + 18.2 (NCR lifecycle)
custom_modules: southbrook_quality
---

# Quality Inspector — SPC Sampling Discipline

## Who this lesson is for

You're either running SPC sampling at a workcenter today, or you're the
quality manager deciding what features to sample, how often, and what to
do when the chart goes out of control. This lesson covers both seats.

## Where this lives on the site

**Quality → SPC** (`menu_southbrook_quality_spc`) — sample entry.
**Quality → Dimensions** (`menu_southbrook_quality_dimensions`) —
master spec the inspector is sampling against.

## What your screen shows

### SPC list view
- Decoration-success: last sample inside control limits
- Decoration-warning: trending toward limit (Western Electric rule 1)
- Decoration-danger: latest sample outside control limit OR rule 1-4
  breach

### SPC form view
- `dimension_id` — what's being measured (FK to `quality.dimension`)
- `workcenter_id` — where measured (FK to `mrp.workcenter`)
- `measured_value` — your reading
- `sample_size` — usually 5 or 10
- `taken_at` — datetime (auto from create_date)
- `operator_id` — who took it (defaults to current user)
- **Chart preview** — last 20 samples with UCL/LCL/centre line

### Dimension form view
- `name` — descriptive ("panel thickness on SB-CNC-BORE 18mm board")
- `nominal` — target value
- `usl`, `lsl` — engineering spec limits (mandatory)
- `unit_of_measure` — mm, inches, etc.
- `applicable_workcenter_ids` (m2m) — which workcenters this applies
  to
- `sample_frequency` — selection: per_hour / per_50_units / per_shift /
  per_day
- `is_critical` — boolean; critical dimensions get tighter UCL/LCL
  (2σ instead of 3σ)

## Your daily flow

### Inspector — taking samples

1. **Walk the floor** at the cadence the dimension master prescribes.
   Per_50_units means count to 50 cuts on SB-CNC-BORE, then sample.
2. **Measure** with the right tool (calipers, gauge block, etc.).
   Critical dimensions need calibrated tools; check calibration date
   on the tool.
3. **Enter sample**. *Quality → SPC → New*. Dimension auto-narrows
   to the workcenter you're at if you set context. Save.
4. **Read the chart**. New point lands. If it's the first time you've
   seen amber or red on this dimension today, escalate.

### Manager — setting policy

1. **Decide what to sample**. Not every dimension; pick the ones that
   matter to function or aesthetics. Start with 5-10 dimensions per
   workcenter.
2. **Set `sample_frequency`**. Tight enough to catch drift, loose
   enough to be feasible. Per_50_units is the most common starting
   point.
3. **Define `usl` / `lsl`** in millimetres. These should match the
   engineering drawing exactly. If you don't have an engineering
   drawing, get one before sampling — Cpk against a guessed spec is
   noise.
4. **Mark `is_critical` carefully**. Critical = 2σ control limits =
   more alarms = more interruptions. Don't critical-flag everything;
   reserve it for features that fail at the customer.

## Reading the chart

The chart's the whole point. Here's how to read it:

- **Centre line** — historical mean of all samples in the period
- **UCL / LCL** — control limits (3σ for normal, 2σ for critical)
- **USL / LSL** — engineering spec (wider than UCL/LCL usually)

**The 4 Western Electric rules** the platform watches for:

1. One point outside ±3σ
2. Two of three consecutive points outside ±2σ (same side)
3. Four of five consecutive points outside ±1σ (same side)
4. Nine consecutive points on one side of the centre line

Any rule breach triggers `decoration-danger` on the SPC list view + an
MI engine notification (the manager sees it in *Quality → MI Tiles*).

## When the chart goes out of control

**Step 1: Don't panic.** Out-of-control doesn't mean out-of-spec. It
means the process has shifted from its historical norm. The cabinet
coming off the line may still be inside USL/LSL.

**Step 2: File an NCR if appropriate.** If `measured_value` is
outside USL or LSL (not just UCL/LCL), the affected cabinets are
out-of-spec. NCR them (lesson 18.2).

**Step 3: Investigate.** Common drift causes:
- Tool wear (CNC bits, edge tape spool)
- Material lot change (different supplier batch)
- Operator change (different technique)
- Environmental (humidity, temp)
- Machine calibration drift

**Step 4: Document.** Post the investigation to the SPC sample's
chatter so the next inspector reads it before re-sampling.

## Common mistakes + how to recover

- **"I forgot to take a sample on schedule. Should I take two now?"**
  No. Take one now, note the gap in the chatter. Backfilling samples
  with the same timestamp distorts the chart.

- **"I sampled but entered the wrong dimension."** Edit the
  `dimension_id` on the sample row. The chart will refresh on the
  correct dimension. Caveat: if you've already triggered an alert on
  the wrong dimension, that alert's now orphaned — clear it manually.

- **"Sample is `5.001 mm` but I'm using a tool with 0.01 precision.
  Enter `5.001` or `5.00`?"** Use the tool's actual precision. Fake
  precision invents data; the chart will lie to you.

- **"`usl` and `lsl` aren't filled on the dimension I'm trying to
  sample."** Stop sampling. The chart's math is broken without these.
  Quality manager fills them before sampling resumes.

- **"Dimension master changed mid-period (new USL/LSL)."** Old samples
  are still on the old chart math; new samples will be on new math.
  The chart will look discontinuous. This is expected; document the
  spec change date in the dimension's chatter.

## What the system is doing behind the scenes

- **Sample create** writes to `southbrook.quality.spc_sample`. A
  computed field `is_in_control` is set at create time based on the
  current control limits.
- **Control limits** are computed from the last `period_samples`
  (default 30) on this `dimension_id + workcenter_id` combo. Recomputed
  on every sample create.
- **Rule breach** fires `southbrook.quality.mi_engine_ext.check_spc()` —
  posts a recommendation to the MI engine for Hermes routing.
- **Chart render** is a `web_widget` OWL component reading the last 20
  samples + control limits. Caches 60s in the browser.

## Quiz (5 questions, applied)

**Q1.** You're sampling panel thickness on SB-CNC-BORE per 50 units.
You missed the sample at unit 50; you're now at unit 110. Do you take
2 samples or 1?

> One sample now. Note the gap (units 50-100 unsampled) in the chatter.
> Two retroactive samples distort the chart's temporal pattern.

**Q2.** A sample lands at `4.8mm` on a dimension with `nominal=5.0mm`,
`usl=5.2mm`, `lsl=4.9mm`. Chart goes red. What's wrong?

> `4.8 < lsl (4.9)`. The sample is out of spec AND out of control. File
> an NCR on the affected MO (any cabinet cut since the last good
> sample). Investigate tool wear or calibration immediately.

**Q3.** Western Electric rule 4 (nine consecutive points on one side
of the centre line) triggered, but every point is inside spec. Action?

> Investigate drift cause (lesson body lists common ones). No NCR if
> nothing's out of spec. Document findings in the dimension's chatter
> + check whether the centre line should be recomputed (process has
> shifted).

**Q4.** A new dimension was added to the master last week. There are
only 5 samples on it. Cpk asks for ≥30. What's the right action?

> Sample more before computing Cpk. Cpk on 5 samples is statistically
> unreliable. Wait for ≥30 (lesson 18.4 explains why) before computing.

**Q5.** Your gauge tool's last calibration was 6 months ago. The
quality manual says recalibrate every 90 days. Latest sample looks
fine. Do you log it?

> File a *handling*-type NCR on the cabinet you'd been measuring,
> severity = major. Pull the tool from service. Don't log the sample
> as authoritative; the measurement may be wrong. Note the tool
> calibration lapse in the NCR chatter.

## What this lesson does NOT cover

- Cpk math + when to act on it — lesson 18.4.
- NCR lifecycle (rework / scrap / accept) — lesson 18.2.
- Supplier scoring — lesson 18.5.
- Calibration tracking — currently outside the platform (paper log);
  v1.1 calibration record planned.
