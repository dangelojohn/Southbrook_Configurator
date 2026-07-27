---
course: 17
chapter: 17.24
title: Maintenance — Acknowledge a Breakdown Alert
duration: 2
audience: Maintenance technician on call
jtbd: acknowledge a breakdown alert
department: Maintenance
custom_modules: southbrook_cmms_wms
---

# Maintenance — Acknowledge a Breakdown Alert

## When you use this

A floor operator (lesson 17.18 etc.) tagged an equipment alarm. An entry
landed in your queue. This is the 2-minute first-response flow.

## Where this lives

**CMMS → Breakdown Alerts** (`menu_southbrook_cmms_breakdown_alert`).

Default view is kanban grouped by state: `open → dispatched → fixed`.

## The 3-step ack

1. **Open the top alert.** Read `equipment_id`, `workcenter_id`,
   `severity`, `description`, who reported it (`reported_by`,
   `reported_at`).
2. **Click *Dispatch Maintenance*.** State → `dispatched`. Auto-creates a
   linked `maintenance.request` so native Odoo Maintenance can track the
   work order time.
3. **Walk to the machine.** The native maintenance request is now your
   work order — log parts used + duration there. The breakdown alert
   stays in `dispatched` until you close it (lesson 17.26).

## What *Block Affected MOs* does

Optional second button. Click it if you don't want production to keep
sending cabinets to the broken workcenter while you fix it. It auto-
blocks every active MO with a work order targeting `workcenter_id`.

## Common gotchas

- **Two alerts open for the same equipment** — that's allowed but messy.
  Close the duplicate; reference it in the chatter of the live one.
- **Equipment not in the dropdown** — `maintenance.equipment` master is
  missing this asset. Ask sysadmin to add it before continuing; for now,
  pick *Other* and describe in the text field.

## Deep dive

→ Course 12 lesson 12.4 *Production Release Queue* (downstream impact)
