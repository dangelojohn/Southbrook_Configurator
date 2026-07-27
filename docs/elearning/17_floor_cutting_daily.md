---
course: 17
chapter: 17.18
title: Floor — Cutting (CNC) Daily Flow
duration: 4
audience: CNC operator on SB-CNC-BORE or CNC02 backup
jtbd: cutting cnc daily flow
department: Production Floor
custom_modules: southbrook_mrp_kitchen_workcenters, southbrook_mrp_kitchen_tools, southbrook_plm
---

# Floor — Cutting (CNC) Daily Flow

## When you use this

You arrive at the CNC workstation, badge in, and need to know what to cut
today.

## Where this lives on the touchscreen

**Floor Workspace → Workcenter Kanban → SB-CNC-BORE** (or CNC02 backup).

## Your 5-step loop

1. **See the queue.** Today's cut list shows top-first. Each card = one
   cabinet's panels.
2. **Open the top card.** Cut spec PDF preview opens (rendered from
   `southbrook_plm.cut_spec` active record).
3. **Cut.** Run the program. The nest file is on `\\fileserver\nests\`
   under the cabinet code (Accucutt hand-off; lesson 1.3 deep dive).
4. **Tap *Done*.** Logs `mrp.workorder.duration_done` and posts a
   chatter entry on the MO.
5. **Next card.** Loop.

## When something is wrong

- **Cut spec doesn't match the panels you have** — DON'T cut. Tap
  *Hold → Cut spec mismatch*. The card moves to the Plant GM queue;
  designer gets pinged for an ECO (lesson 17.10).
- **Tool is broken / worn** — *Hold → Tool issue*. Posts to maintenance
  queue. Lesson 17.24 explains the maintenance side.
- **Machine alarms** — *Hold → Equipment alarm*. Creates a breakdown
  alert automatically; you can also raise one yourself via *Maintenance →
  Breakdown Alerts → New*.

## Common gotchas

- **Done button greyed out** — work order not in `progress` state. Tap
  *Start* first.
- **Two CNC cards open** — `southbrook_mrp_pm` allows parallel jobs on
  the workcenter if `parallel_jobs > 1`. SB-CNC-BORE is sequential
  (parallel_jobs=1); only one card should be open. If two are open,
  close the lower-priority one.
- **Backup machine (CNC02) shows different programs** — that's expected;
  CNC02 doesn't have the boring head; cabinets needing 35mm hinge bores
  must run on SB-CNC-BORE.

## Deep dive

→ Course 1 lesson 1.3 *CNC Router Operator*
