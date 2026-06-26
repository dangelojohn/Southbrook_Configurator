---
course: 21
chapter: 21.3
title: Executive — OEE and Bottleneck from the Exec's View
duration: 9
audience: Owner or Plant GM reading floor health from 10,000 feet
prereqs: Lessons 21.1 + 21.2, basic Manufacturing familiarity
custom_modules: southbrook_exec_dashboard, southbrook_mes_mps, southbrook_premium_orchestration
---

# Executive — OEE and Bottleneck from the Exec's View

## Who this lesson is for

You're the owner / Plant GM. Production manager handles the day-to-day
of OEE and bottlenecks; you watch the 30,000-foot trend + make the
capacity decisions (buy a machine? add a shift? cut customer
commitments?). This lesson is the exec lens.

## Where this lives on the site

**Exec Dashboard** — for the daily glance.
**MES → Bottleneck Report** (`menu_bottleneck_report`) — for the
deeper read.
**Kitchen Ops → Workcenter Bottleneck** (`menu_kitchen_ops_workcenter_bottleneck`) — for the operational view.

## OEE 101 (the 60-second refresher)

OEE = Overall Equipment Effectiveness = **Availability × Performance × Quality**.

- **Availability** = uptime / scheduled time
  - Affected by: breakdowns, planned PM, setup, changeovers, idle
- **Performance** = actual output / theoretical output during uptime
  - Affected by: slow running, minor stops, operator pace
- **Quality** = good output / total output
  - Affected by: scrap, rework, NCR-driven holds

OEE is multiplicative — 90% × 90% × 90% = 73% (good). 80% × 80% × 80% = 51% (poor). World-class is 85%+; cabinet manufacturing typical is 60-75%.

## How the executive should think about OEE

You're not trying to fix OEE — you're trying to understand where the
*economics* live.

- **Low Availability** = you bought capacity you can't use. Either
  reduce breakdown rate (CMMS — lesson 17.24-17.27) or accept the
  capacity and plan around it.
- **Low Performance** = the machine is running but not at spec. Often
  cheap to fix (operator training, tool sharpening, lubrication).
  Usually high-ROI to improve.
- **Low Quality** = waste is high. Connect to NCR rate (lesson
  17.28). Expensive to ignore.

A 75% OEE machine running 16 hours = 12 effective hours. A 60% OEE
machine running 24 hours = 14.4 effective hours. Choosing between
shifts vs improvements is the executive question.

## Reading the bottleneck report

### Where it lives
**MES → Bottleneck Report**

### What it shows
- Workcenters listed by `utilisation_pct = demand_hours / capacity_hours`
- Decoration green / amber / red as covered in lesson 17.17
- Drill any row to see the demand breakdown by week

### The exec questions

- **Which workcenter is consistently red?** That's where capex or
  shift expansion buys you the most output.
- **What's the cost of buying a second one?** Compare against the
  margin you're leaving on the table from missed deliveries.
- **Are there non-bottleneck workcenters you can reroute work to?**
  Free flexibility before capex.

## A worked example

You read:
- SB-CNC-BORE: utilisation 105% (red)
- CNC02 (backup): utilisation 65% (green)
- SB-EDGE: utilisation 90% (amber)
- SB-ASSY: utilisation 70% (green)
- SAND/PAINT/CURE: utilisation 80%/80%/80% (green)

### Reading

SB-CNC-BORE is overcommitted; CNC02 has capacity but not the boring
head. SB-EDGE is the secondary risk.

### Decision options

1. **Reroute** boring-not-required work to CNC02 — frees SB-CNC-BORE
   for the boring jobs only. Could drop SB-CNC-BORE utilisation to
   85%.
2. **Add a shift** on SB-CNC-BORE — bigger commitment; pays back on
   sustained demand.
3. **Add a second boring head** to CNC02 (capex) — ~$30k, 4-6 weeks
   delivery, durable upside.
4. **Defer customer dates** — short-term; loses customer trust.

The choice depends on sustained demand outlook + cash position. The
report gives you the data; the decision is yours.

## Bottleneck conversations

### With Production Planner
- "What's been bottlenecked this week?"
- "What did you reroute?"
- "What dropped a customer date?"

### With Plant GM
- "Where's the chronic vs acute distinction?"
- "What's the capex case?"
- "What's the operator case (training)?"

### With Sales
- "Are we accepting orders we can't deliver?"
- "Which customers are most flexible on dates?"

### With Maintenance Lead
- "Which workcenter's downtime is driving the bottleneck?"
- "What's the PM cadence trade-off?"

## When to escalate vs accept

- **Acute** (a single week's spike) — accept; reroute + push dates
- **Chronic** (8+ weeks of red) — capex conversation
- **Cyclical** (kitchen season Q2/Q3 high) — plan ahead; add temp
  capacity ahead of season
- **Growing** (red getting deeper) — the market is telling you
  something; respond before margin erodes

## Common mistakes + how to recover

- **"I bought a second CNC last year; should be fine."** Capacity
  on paper ≠ capacity in practice. Run-rate, programmer skill,
  setup time, breakdown rate all reduce realised capacity.
  Re-check the report on the new equipment.

- **"OEE is 60%; that's bad."** Cabinet-shop benchmark is 60-75%.
  Aim for improvement, not for a number that matches a textbook.

- **"Bottleneck looks fine but customers complain about dates."**
  Bottleneck shows utilisation, not promise quality. May indicate
  estimating quotes too-aggressive dates; check Sales.

- **"Capex case for new equipment is fuzzy."** Bring the
  bottleneck report + a margin model to the conversation. The data
  cuts through opinion.

## What the system is doing behind the scenes

- **OEE per workcenter** — `mrp.workcenter` computes per shift /
  day from `productivity` records + work order outputs
- **Bottleneck report** — rolling 13-week MPS demand vs workcenter
  capacity (see Course 17 lesson 17.17 for the planner's version)
- **Exec tile of OEE / Bottleneck** — aggregated from these

## Quiz (5 questions, applied)

**Q1.** SB-CNC-BORE OEE = 60%. Availability 70%, Performance 95%,
Quality 90%. Where do you focus?

> Availability. The biggest gap. Investigate downtime causes —
> CMMS shows breakdowns; setup tracking may show transition time.
> Conversation with maintenance + production.

**Q2.** Bottleneck report shows SAND 110% utilisation for 6
straight weeks. Decision?

> Capex consideration: add a second sanding station. Sustained 110%
> is dropping customer dates. Calculate margin lost and compare to
> equipment cost. Talk to production about parallel-runnability.

**Q3.** OEE on SB-DOOR dropped from 78% to 62% over two weeks. No
single explanation jumps out. Action?

> Drill into the workcenter's productivity log. Two-week shift
> often = an operator change, a material change (different door
> stock), or a sneaky tool wear issue. Walk the line at 10am.

**Q4.** Two workcenters are red, but no customer date is missed
yet. Drop the issue?

> Don't. Red means future dates are at risk if demand sustains. Set
> calendar item to re-review in 2 weeks. Surface in next leadership
> meeting.

**Q5.** Sales pitched a big order with delivery in 4 weeks. Read
the bottleneck report. SB-CNC-BORE is at 100%. Accept the order?

> No without a plan: tell sales delivery in 6-8 weeks (real
> capacity), OR accept with reroute strategy + customer flex on
> exact date. Better to set expectations than miss them.

## What this lesson does NOT cover

- Detailed OEE math — Course 3 lesson 3.3.
- Bottleneck-scheduling specifics for the planner — Course 2 lesson
  2.3.
- Setup-time reduction (SMED) — operations engineering topic.
