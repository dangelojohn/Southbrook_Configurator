---
course: 17
chapter: 17.6
title: Sales — Handle a Mid-Quote Change Request
duration: 3
audience: Sales rep whose customer wants to swap a cabinet after quoting
jtbd: handle a mid-quote change request
department: Sales
custom_modules: southbrook_estimating, southbrook_plm
---

# Sales — Handle a Mid-Quote Change Request

## When you use this

Customer signs off, you confirm the SO, then they call back: *"actually make
that cabinet a 36-inch instead of 30-inch."* This is the workflow.

## Pre-confirmation (SO state = draft/sent)

No drama — open the SO, edit the line, save. Spec sheet re-prints with the
change. No ECO needed.

## Post-confirmation (SO state = sale)

This requires an Engineering Change Order (ECO) because the MO may already
be in production. The flow:

1. **Open the SO.** It now has a *Change Order* button in the header.
2. **Click it.** Opens a draft `southbrook_plm.eco` record pre-populated with
   the originating SO + the lines you want to change.
3. **Mark the lines.** Tick the cabinets affected. The ECO will show before
   / after for each.
4. **Submit.** Routes to the Designer who authors the new cut spec.
5. **Designer + Plant GM approve.** ECO transitions to *Released*.
6. **Production picks up.** Affected MOs auto-update or are scrapped + re-MO'd
   depending on workcenter state.

## Time-sensitivity rules

- **Cut spec not yet authored** (MO state = draft) → swap is free, no scrap
- **Cut spec authored, cutting not started** → swap is free; cut spec is
  re-authored
- **Cutting in progress** → scrap the partially-cut panels (logged as scrap
  on the original MO) + re-MO the changed cabinet
- **Past cutting** → escalation to Plant GM required; the change may be
  cheaper to do as a return + re-order than mid-stream

## Common gotchas

- **Customer wants the change but won't pay the upcharge** — that's a
  negotiation, not a system step. Leave the ECO in Draft until you have a
  signed addendum.
- **ECO doesn't show on the SO chatter** — check that the linked SO is on
  the ECO `origin_sale_order_id` field. Bug if missing; file a ticket.

## Deep dive

→ Course 4 lesson 4.1 *ECOs*
→ Course 8 lesson 8.6 *Revising and Versioning*
