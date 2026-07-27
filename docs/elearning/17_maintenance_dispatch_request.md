---
course: 17
chapter: 17.25
title: Maintenance — Dispatch a Preventive Maintenance Request
duration: 2
audience: Maintenance lead doing weekly PM planning
jtbd: dispatch a preventive maintenance request
department: Maintenance
custom_modules: southbrook_cmms_wms
---

# Maintenance — Dispatch a Preventive Maintenance Request

## When you use this

Weekly: you decide which preventive maintenance (PM) jobs to dispatch in
the coming week. Distinct from breakdown response — this is planned work,
not reactive.

## Where this lives

**Maintenance → Maintenance Requests** (native Odoo) AND **CMMS → Service
Contracts** (Southbrook layer for vendor-managed equipment).

## The 4-step flow

1. **List view, filter by `request_date` next 7 days + `maintenance_type =
   preventive`.**
2. **Review each request.** Verify the part inventory you'll need is on
   hand (linked through `maintenance.equipment.spare_part_ids`).
3. **Assign + schedule.** Pick a technician (`user_id`) and set the
   `schedule_date`. The MI engine will flag conflicts with active MOs on
   that equipment.
4. **Dispatch.** Action → *Dispatch*. State → `in_progress`; technician
   gets a notification.

## Coordinating with production

A PM that takes a workcenter offline for 4 hours should be visible to the
production planner. After dispatch, *Kitchen Ops → Workcenter Bottleneck*
will show the planned downtime as a darker band — planner sees this and
schedules around it.

## Service contract vs in-house

If the equipment has an active `southbrook.cmms.service_contract`, the
vendor's tech handles it. Your job is to coordinate the visit. Otherwise,
in-house tech does the work.

## Common gotchas

- **Schedule conflicts with a customer's promise date** — escalate to
  Plant GM before dispatching. The PM can usually slip a day or two.
- **Spare part inventory short** — *Hold → Parts*. Auto-creates a PO
  request to the vendor on the equipment master.

## Deep dive

→ Course 12 lesson 12.6 *MI Engine Observability*
