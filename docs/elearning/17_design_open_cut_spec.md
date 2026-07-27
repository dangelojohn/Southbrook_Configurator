---
course: 17
chapter: 17.9
title: Design — Open a Cut Spec for a Confirmed Order
duration: 3
audience: Designer / ECO engineer responding to a confirmed kitchen order
jtbd: open a cut spec for a confirmed order
department: Design / Engineering
custom_modules: southbrook_plm
---

# Design — Open a Cut Spec for a Confirmed Order

## When you use this

A Sales rep confirmed an SO; the release gate is now waiting on you to
author the cut spec. This is the 60-second tutorial on getting unstuck.

## Where this lives

**Engineering → PLM → Cut Specs**, or open the MO from the Release Queue
and use the *Cut Spec* notebook tab.

## The 3-step flow

1. **From the Release Queue.** *Kitchen Ops → Release Queue* → click the
   blocked MO. Right-side panel lists what's blocking. If it says *Cut spec
   missing*, click *Author Cut Spec*.
2. **Fill the required fields.** Panel dimensions, edge profiles, grain
   orientation, drilling pattern. Most fields auto-fill from the cabinet's
   configurator selections; you only edit what differs from default.
3. **Save + Activate.** Constraint `_check_single_active` (audit note #11)
   enforces one active cut spec per cabinet. The release gate clears
   automatically.

## Fields you can't change

- **Cabinet width / height / depth** — locked from the SO configurator.
- **Door style** — locked. To change, raise an ECO from the SO.
- **Box material** — locked.

You can override these via a Cut Spec Override (Kitchen Ops → Cut Spec
Overrides), which is logged separately and triggers a manager approval.

## Common gotchas

- **Cut spec authored but release gate didn't clear** — check that
  `is_active=True`. Saving as Draft doesn't satisfy the gate.
- **Two cut specs for the same cabinet** — constraint will reject save.
  Archive the old one first.
- **FreeCAD bridge renders the wrong panel** — bridge reads
  `_spec_for_bridge` from product-template defaults in Phase 1, not from
  the cut spec yet (audit note #10). Manual re-render after cut-spec save.

## Deep dive

→ Course 4 lesson 4.2 *Authoring a Cut Spec Sheet*
→ Course 1 lesson 1.7 *Reading a Cut Spec*
