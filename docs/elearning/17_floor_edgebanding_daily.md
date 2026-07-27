---
course: 17
chapter: 17.19
title: Floor — Edge Banding Daily Flow
duration: 3
audience: Edge banding operator on SB-EDGE (HOMAG)
jtbd: edge banding daily flow
department: Production Floor
custom_modules: southbrook_mrp_kitchen_workcenters
---

# Floor — Edge Banding Daily Flow

## When you use this

You're standing in front of the HOMAG edge bander. Cut panels are arriving
from CNC. You need to know which panels need which tape.

## Where this lives

**Floor Workspace → Workcenter Kanban → SB-EDGE**

## Your 4-step loop

1. **Read the edge map.** Each card shows a small graphic — the cabinet's
   panel with arrows indicating which edges need tape and what tape SKU.
2. **Load the correct tape spool.** Tape SKU shows on the card (e.g. *PVC
   White 22×1mm*); confirm against the spool barcode.
3. **Run the panels.** Feed them through with the tape edge aligned.
4. **Tap *Done*.** Same flow as cutting (lesson 17.18); duration logged.

## What the edge map fields mean

- **Top / Bottom / Left / Right** — which edges get tape
- **Tape SKU** — exact code; mismatches show on the kanban as warnings
- **Profile** — straight, radius, bevel
- **Glue temp** — set on the HOMAG; outside the system but called out on
  the card for double-check

## Common gotchas

- **Edge map says "Top + Left" but panel needs "Top + Right"** — DON'T
  band; tap *Hold → Edge map error*. Designer gets pinged. The edge map
  is derived from the cut spec + cabinet's `hinge_side` attribute.
- **Tape SKU not available** — *Hold → Material missing*. Posts to
  warehouse + auto-creates a PO request if stock is below reorder.
- **Glue line visible after banding** — quality issue. Open an inline NCR
  (lesson 17.23) so you don't ship it downstream.

## Deep dive

→ Course 1 lesson 1.2 *Edge Banding Operator — Your Daily Flow*
