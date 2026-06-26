---
course: 17
chapter: 17.22
title: Floor — Sanding and Finishing Daily Flow
duration: 3
audience: Sander or finisher on SAND, PAINT, or CURE stations
jtbd: sanding and finishing daily flow
department: Production Floor
custom_modules: southbrook_mrp_kitchen_workcenters
---

# Floor — Sanding and Finishing Daily Flow

## When you use this

You're at the finishing line. Cabinets are arriving for sand → paint →
cure (three separate stations, not one) per `southbrook_mrp_pm`.

## Where this lives

**Floor Workspace → Workcenter Kanban** then pick:

- **SAND** — manual sanding station
- **PAINT** — spray booth
- **CURE** — drying / curing rack with thermal cycle

Each station has its own kanban; you only see the one you're rostered to.

## Your loop (varies by station)

### SAND
1. Pick the top cabinet card
2. Verify the finish spec — grit progression, prep notes
3. Sand to spec
4. Tap *Done* → moves to PAINT queue

### PAINT
1. Verify the finish code on the card (must match the
   `southbrook_estimating` configurator selection)
2. Mix / load the right colour
3. Spray per the standard
4. Tap *Done* → moves to CURE queue

### CURE
1. Load into the rack with the cabinet's `cure_cycle_min` from the card
2. Run the timer
3. Tap *Done* when timer + spec match

## Common gotchas

- **Finish code on card doesn't match the colour can you have** — the
  cabinet may be using a custom finish. Verify against the Spec Sheet
  PDF on the MO. If still mismatched, *Hold → Finish discrepancy*.
- **Cabinet bypasses SAND** — some white-thermofoil-slab cabinets
  (Contractor series) skip sanding. Card will not appear in SAND queue.
- **CURE timer interrupted** — restart the cycle; do NOT tap Done early.
  The MI engine watches for short cycles and will flag.

## Deep dive

→ Course 1 lesson 1.5 *Sander / Finisher — Your Daily Flow*
