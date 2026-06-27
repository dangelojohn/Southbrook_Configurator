---
course: 27
chapter: 27.1
title: CMMS + WMS Module — Architecture
duration: 7
audience: Developer or admin learning southbrook_cmms_wms internals
prereqs: Native Odoo Maintenance + Stock familiarity
custom_modules: southbrook_cmms_wms
---

# CMMS + WMS Module — Architecture

## The module at a glance

- Path: `addons/southbrook_cmms_wms/`
- Version: 19.0.1.0.0
- Depends on: `base`, `mail`, `mrp`, `maintenance`, `stock`,
  `purchase`, `southbrook_manufacturing_intelligence`

## Source layout

```
addons/southbrook_cmms_wms/
├── models/
│   ├── breakdown_alert.py     — operational alerts from floor
│   ├── mtbf_mttr_report.py    — capability reports
│   ├── service_contract.py    — vendor service contracts
│   ├── landed_cost_template.py — recurring oversize/freight templates
│   └── mi_engine_ext.py
├── views/
├── security/
└── data/
```

## What CMMS + WMS

- **CMMS** = Computerized Maintenance Management System. Tracks
  equipment, breakdowns, MTBF/MTTR.
- **WMS** = Warehouse Management System. Light touch on the
  warehouse side — oversize permit (for oversized cabinet
  shipping) + landed cost templates for freight.

The two are paired because:
- They share a vendor management surface
- Both touch the equipment + freight cost equation
- Combining keeps install footprint small at v1

## Install

```bash
./scripts/deploy_to_qnap.sh southbrook_cmms_wms
```

What -i does:
1. Creates the 5 main tables
2. Adds 5 menus under CMMS
3. Registers cron for MTBF/MTTR daily compute

## Cron landscape

| Cron | Schedule | Purpose |
|---|---|---|
| `cron_mtbf_mttr_compute` | daily 03:00 | Refreshes MTBF/MTTR for all equipment |

## Breakdown alert + native maintenance bridge

Southbrook's `breakdown_alert` is an OPERATIONAL log (floor
operator reports an alarm). It auto-creates a native
`maintenance.request` when dispatched — that's where the actual
WO time tracking lives.

```python
def action_dispatch(self):
    """Dispatch maintenance — creates native maintenance.request."""
    self.ensure_one()
    if self.maintenance_request_id:
        raise UserError(_("Already dispatched"))
    
    request = self.env["maintenance.request"].create({
        "name": f"Breakdown: {self.equipment_id.name}",
        "equipment_id": self.equipment_id.id,
        "request_date": fields.Date.today(),
        "maintenance_type": "corrective",
        "priority": "3" if self.severity == "critical" else "2",
    })
    self.maintenance_request_id = request.id
    self.state = "dispatched"
```

This is the integration boundary. CMMS shows the operational
alert; native shows the technician's work.

## Common mistakes + how to recover

- **"Module installed but maintenance menus disappeared"** — likely
  conflict between Southbrook + native security groups. Verify
  group_user assignment.
- **"MTBF/MTTR all zero"** — daily cron didn't run, OR no closed
  breakdowns in the period.
- **"Breakdown alert state stuck at 'dispatched'"** — `action_close`
  not called. Maintenance request may have closed but alert
  didn't sync.

## Quiz

**Q1.** Why combine CMMS + WMS in one module?

> v1 footprint efficiency. Both touch the equipment + freight
> equation; both share vendor management.

**Q2.** Breakdown alert vs maintenance.request — what's each?

> Alert is the operational notification (floor → maintenance lead).
> Maintenance.request is the work order with time tracking.

**Q3.** Daily cron does what?

> Refreshes MTBF/MTTR computed values for all active equipment.

**Q4.** What native modules depended on?

> `maintenance`, `mrp`, `stock`, `purchase`.

**Q5.** Module deployed but `Breakdown Alerts` menu doesn't show.
First check?

> User's group membership. Verify they have `group_user` AND
> nothing's excluding them.
