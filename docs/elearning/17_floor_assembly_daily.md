---
course: 17
chapter: 17.20
title: Floor — Assembly Daily Flow
duration: 3
audience: Assembler on SB-ASSY (parallel-jobs enabled)
jtbd: assembly daily flow
department: Production Floor
custom_modules: southbrook_mrp_kitchen_workcenters
---

# Floor — Assembly Daily Flow

## When you use this

You're at the assembly bench. Cut + banded panels + hardware kits should be
landing at your station. You assemble the carcass.

## Where this lives

**Floor Workspace → Workcenter Kanban → SB-ASSY**

(SB-ASSY has `parallel_jobs > 1` per `southbrook_mrp_pm` — you can have
multiple cabinets open simultaneously.)

## Your 5-step loop

1. **Pick a kit.** The kanban groups by *kit_id* — all panels + hardware
   for one cabinet. Scan the kit barcode.
2. **Build.** Follow the cabinet code's standard procedure (cards link to
   the cut spec + door spec).
3. **Test fit.** Confirm doors fit, drawers slide.
4. **Tap *Done*.** Posts duration; cabinet moves to SB-DOOR if it has a
   separate door-mount step, otherwise direct to finishing.
5. **Next kit.**

## Hardware lookup

If the kit is missing a part, the hardware spec is in the cut spec PDF.
SKU + brand + quantity. Most kits use Marathon-brand hardware.

## Common gotchas

- **Kit incomplete** — *Hold → Kit short*. Warehouse gets notified to
  re-pick. Note exactly which SKU is missing.
- **Hinge predrilled holes don't match the door's specified hinge** — the
  cabinet's `hinge_side` attribute may have changed via ECO after the
  panels were cut. Check the active cut spec; if it differs from your
  panel, *Hold → ECO drift*.
- **Drawer slide hits the gable** — installation note in the cut spec
  often missed; brief the next batch on the standard offset.

## Deep dive

→ Course 1 lesson 1.4 *Assembler — Your Daily Flow*
