---
course: 27
chapter: 27.7
title: CMMS + WMS Module — Adding New Equipment Types
duration: 6
audience: Developer onboarding new equipment categories
prereqs: Lessons 27.1-27.6
custom_modules: southbrook_cmms_wms
---

# CMMS + WMS Module — Adding New Equipment Types

## The pattern

New equipment doesn't usually need new models — just new records
in existing models:

1. `maintenance.equipment` — the equipment record
2. `maintenance.equipment.category` — its category
3. `maintenance.equipment.spare_part_ids` — required spares

## Adding a new equipment record

Via UI: *Maintenance → Equipment → New*.

Via XML:

```xml
<record id="equip_homag_bao_823" model="maintenance.equipment">
    <field name="name">HOMAG BAO 823 Edge Bander</field>
    <field name="category_id" ref="cat_edge_banding"/>
    <field name="serial_no">H-823-5512</field>
    <field name="assign_date" eval="time.strftime('%Y-%m-%d')"/>
    <field name="cost">120000</field>
    <field name="warranty_date" eval="(date.today() + relativedelta(years=2)).strftime('%Y-%m-%d')"/>
    <field name="period">90</field>  <!-- PM interval in days -->
</record>
```

## Equipment categories

Categories group equipment for reporting + scheduled PM:

```xml
<record id="cat_edge_banding" model="maintenance.equipment.category">
    <field name="name">Edge Banding Machines</field>
    <field name="alias_name">edge-banding-team</field>
    <field name="email_from">maintenance@southbrook.example</field>
</record>
```

Category-level PM scheduling auto-creates `maintenance.request`
records.

## Spare parts master

For each equipment, list spare parts that should be kept on hand:

```python
class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"
    
    spare_part_ids = fields.Many2many("product.product")
```

Used by:
- Spare parts inventory check (alerts when low)
- Breakdown alert's `parts_used_ids` selector

## Adding workcenter linkage

For OEE computation (Course 26), equipment needs a workcenter
link:

```python
class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"
    
    workcenter_id = fields.Many2one("mrp.workcenter",
        help="Workcenter this equipment is part of.")
```

(May already be present; if not, add.)

## Auto-creating breakdown alert from native maintenance

For requests reported via the native interface (vs floor kanban):

```python
class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"
    
    def create(self, vals):
        request = super().create(vals)
        if request.maintenance_type == "corrective" and \
           not request.equipment_id.skip_alert_sync:
            # Create paired alert
            self.env["southbrook.cmms.breakdown_alert"].create({
                "equipment_id": request.equipment_id.id,
                "workcenter_id": request.equipment_id.workcenter_id.id,
                "severity": self._severity_from_priority(request.priority),
                "description": request.description,
                "maintenance_request_id": request.id,
                "state": "dispatched",  # already dispatched at create
            })
        return request
```

## Decommissioning equipment

When equipment is sold/scrapped:

```python
def action_decommission(self):
    self.ensure_one()
    self.active = False
    # Close open alerts
    open_alerts = self.env["southbrook.cmms.breakdown_alert"].search([
        ("equipment_id", "=", self.id),
        ("state", "in", ("open", "dispatched")),
    ])
    open_alerts.write({"state": "fixed", "root_cause": "Equipment decommissioned"})
```

## Common mistakes + how to recover

- **"New equipment doesn't show in breakdown alert dropdown"** —
  `active = True` required, OR group-scoped access.
- **"PM auto-create not firing"** — `period` field unset on the
  equipment. Set the PM interval.
- **"Decommissioned equipment still in MTBF reports"** — cron
  computes for `active = True` only. Old reports persist (audit
  retention).

## Quiz

**Q1.** Add a new equipment via XML — required fields?

> name + category_id. Recommended: serial_no, assign_date,
> period (for PM).

**Q2.** Equipment without `workcenter_id` — affects OEE?

> Yes — OEE attribution may miss it. Set workcenter_id for all
> production equipment.

**Q3.** Multiple equipment in same workcenter. OEE computation?

> Native compute is per workcenter. Equipment-level OEE not
> directly computed; trace via productivity records' equipment_id.

**Q4.** Decommission equipment — prior MTBF reports?

> Stay (audit retention). Cron stops adding new ones.

**Q5.** PM interval 90 days. First PM created when?

> `assign_date + 90 days`. Maintenance creates the auto-PM
> request 14 days before due (configurable).
