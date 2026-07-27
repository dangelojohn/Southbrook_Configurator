---
course: 27
chapter: 27.2
title: CMMS + WMS Module — Breakdown Alert and Maintenance Bridge
duration: 8
audience: Developer working on alert/dispatch logic
prereqs: Lesson 27.1
custom_modules: southbrook_cmms_wms
---

# CMMS + WMS Module — Breakdown Alert and Maintenance Bridge

## The model

```python
class SouthbrookCmmsBreakdownAlert(models.Model):
    _name = "southbrook.cmms.breakdown_alert"
    _description = "Equipment Breakdown Alert"
    _inherit = ["mail.thread"]
```

Fields:

```python
name             = fields.Char(default=lambda s: s._make_seq())
equipment_id     = fields.Many2one("maintenance.equipment",
                                   required=True, index=True)
workcenter_id    = fields.Many2one("mrp.workcenter")
severity         = fields.Selection([
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
    ("critical", "Critical"),
])
description      = fields.Text()
reported_at      = fields.Datetime(default=fields.Datetime.now)
reported_by      = fields.Many2one("res.users",
                                   default=lambda s: s.env.user)

state = fields.Selection([
    ("open", "Open"),
    ("dispatched", "Dispatched"),
    ("fixed", "Fixed"),
], default="open")

maintenance_request_id = fields.Many2one("maintenance.request")
affected_production_ids = fields.Many2many("mrp.production")
total_downtime_min      = fields.Integer()
root_cause              = fields.Text()
parts_used_ids          = fields.Many2many("product.product")
```

## State machine

```
open ──[Dispatch]──> dispatched ──[Close]──> fixed
```

### Dispatch

```python
def action_dispatch(self):
    self.ensure_one()
    if self.maintenance_request_id:
        raise UserError(_("Already dispatched"))
    
    request = self.env["maintenance.request"].create({
        "name": f"Breakdown: {self.equipment_id.name}",
        "equipment_id": self.equipment_id.id,
        "request_date": fields.Date.today(),
        "maintenance_type": "corrective",
        "priority": "3" if self.severity in ("high", "critical") else "2",
    })
    self.maintenance_request_id = request.id
    self.state = "dispatched"
    self.message_post(body=_("Dispatched as %s") % request.name)
```

### Close

```python
def action_close(self, total_downtime_min, root_cause, parts_used_ids):
    self.ensure_one()
    self.write({
        "total_downtime_min": total_downtime_min,
        "root_cause": root_cause,
        "parts_used_ids": [(6, 0, parts_used_ids)],
        "state": "fixed",
    })
    # Native maintenance request also closes if still open
    if self.maintenance_request_id.stage_id.done is False:
        self.maintenance_request_id.stage_id = \
            self.env.ref("maintenance.stage_2")  # "Done"
```

## Block affected MOs

Optional secondary action:

```python
def action_block_affected_mos(self):
    self.ensure_one()
    # Find active MOs targeting this workcenter
    mos = self.env["mrp.production"].search([
        ("state", "in", ("confirmed", "progress")),
    ])
    affected = []
    for mo in mos:
        for wo in mo.workorder_ids:
            if wo.workcenter_id == self.workcenter_id and \
               wo.state in ("ready", "progress"):
                wo.block_reason = f"Breakdown/{self.id}"
                affected.append(mo.id)
    
    self.affected_production_ids = [(6, 0, list(set(affected)))]
    self.message_post(body=_("Blocked %d affected MOs") % len(set(affected)))
```

## Unblock affected MOs (on close)

```python
def action_unblock_affected_mos(self):
    self.ensure_one()
    for mo in self.affected_production_ids:
        for wo in mo.workorder_ids:
            if wo.block_reason == f"Breakdown/{self.id}":
                wo.block_reason = False
```

Called either explicitly OR on `action_close()` if you want
automatic unblocking.

## Common mistakes + how to recover

- **"Dispatch creates duplicate maintenance.request"** —
  `action_dispatch` guard not working. Add `if self.maintenance_request_id`
  check.
- **"Close blocked WOs still showing red"** — `action_unblock_affected_mos`
  not called. Either call it from close OR add as secondary
  action.
- **"Multiple alerts on same equipment"** — allowed but messy.
  Close duplicates referencing the live one.

## Quiz

**Q1.** What state can `action_dispatch` be called from?

> `open` only (the action is `invisible="state != 'open'"` in
> view).

**Q2.** Dispatch creates a native maintenance.request. What
priority?

> 3 (high) for high/critical severity; 2 (medium) otherwise.

**Q3.** Close logs `total_downtime_min`. Why required?

> Drives MTBF/MTTR math. Without it, capability reports are wrong.

**Q4.** Affected MOs auto-unblock on close?

> Implementation choice. Current code requires explicit
> `action_unblock_affected_mos` call. v1.1 candidate to auto-unblock.

**Q5.** Severity = critical but priority on maintenance.request
shows 3. Should it show 4?

> Native maintenance.request priority maxes at 3. Critical maps to
> 3 by design.
