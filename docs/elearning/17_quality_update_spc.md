---
course: 17
chapter: 17.29
title: Quality — Update an SPC Chart with a New Sample
duration: 3
audience: QC inspector running SPC sampling
jtbd: update an spc chart with a new sample
department: Quality
custom_modules: southbrook_quality
---

# Quality — Update an SPC Chart with a New Sample

## When you use this

You're running Statistical Process Control sampling on a workcenter (e.g.
panel thickness on SB-CNC-BORE every 50 cuts). This is the
sample-entry tutorial.

## Where this lives

**Quality → SPC** (`menu_southbrook_quality_spc`).

## The 3-step entry

1. **Pick the dimension being measured.** `quality.dimension` master record
   carries the spec (nominal, USL, LSL). New dimensions are seeded by the
   quality manager.
2. **New sample.** *New* on the SPC view. Fields:
   - `dimension_id` — the spec
   - `workcenter_id` — where measured
   - `measured_value` — your reading
   - `sample_size` — usually 5 or 10
   - `taken_at` — auto-stamps; only override if backfilling
3. **Save.** The chart auto-updates. If the new point breaches a control
   limit, the cabinet's work order kanban surfaces an alert.

## Reading the chart

- **Centre line** — historical mean
- **UCL / LCL** — upper / lower control limits (3σ)
- **USL / LSL** — engineering spec (much wider)

When a point goes outside UCL/LCL but inside USL/LSL, the process is
drifting — investigate causes BEFORE the spec is breached.

## When the process is out of control

- File an NCR linked to the affected MO(s) (lesson 17.28)
- Notify maintenance if the cause looks mechanical
- Quality manager decides whether to halt the workcenter

## Common gotchas

- **Sample saved but chart didn't update** — there's a server-side delay
  of up to 60 seconds; refresh.
- **No dimension master for what I'm measuring** — coordinate with the
  quality manager to add it; don't fudge to a similar dimension.

## Deep dive

→ Course 18 (Quality Module — to be authored)
