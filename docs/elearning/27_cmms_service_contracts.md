---
course: 27
chapter: 27.4
title: CMMS + WMS Module — Service Contracts
duration: 6
audience: Developer working on vendor service contract logic
prereqs: Lesson 27.1
custom_modules: southbrook_cmms_wms
---

# CMMS + WMS Module — Service Contracts

## The model

```python
class SouthbrookCmmsServiceContract(models.Model):
    _name = "southbrook.cmms.service_contract"
    _description = "Service Contract (vendor-managed equipment)"
    _inherit = ["mail.thread"]
```

Fields:

```python
name           = fields.Char()
vendor_id      = fields.Many2one("res.partner", required=True)
equipment_ids  = fields.Many2many("maintenance.equipment")
contract_type  = fields.Selection([
    ("full", "Full Coverage"),
    ("preventive_only", "Preventive Only"),
    ("response_only", "Response Only"),
    ("parts_only", "Parts Only"),
])

start_date     = fields.Date(required=True)
end_date       = fields.Date(required=True)
annual_cost    = fields.Float()
response_time_hours = fields.Float(default=24)

state          = fields.Selection([
    ("draft", "Draft"),
    ("active", "Active"),
    ("expired", "Expired"),
    ("renewed", "Renewed"),
])

renewal_reminder_days = fields.Integer(default=60)
```

## Contract types

| Type | What's covered |
|---|---|
| **Full** | All maintenance + parts + breakdowns |
| **Preventive only** | Scheduled PM; breakdowns billed separately |
| **Response only** | Breakdowns; PM is in-house |
| **Parts only** | Parts at discount; labour in-house |

Drives the maintenance.request routing: full + response_only get
auto-routed to vendor; PM-only routes preventive maintenance to
vendor.

## Renewal reminder cron

```python
@api.model
def _cron_check_renewals(self):
    """Daily: find contracts expiring within renewal_reminder_days."""
    today = fields.Date.today()
    expiring = self.search([
        ("state", "=", "active"),
        ("end_date", "<=", today + relativedelta(days=60)),
        ("end_date", ">=", today),
    ])
    for c in expiring:
        days_left = (c.end_date - today).days
        if days_left <= c.renewal_reminder_days and \
           not self._already_notified(c, days_left):
            self._notify_renewal(c, days_left)
```

## Notification

```python
def _notify_renewal(self, contract, days_left):
    contract.message_post(
        body=_("Renewal due in %d days. Decide renew / negotiate / "
               "cancel.") % days_left,
        partner_ids=self.env.ref(
            "southbrook_cmms_wms.group_cmms_manager").users.partner_id.ids,
    )
    # Also emit MI recommendation
    self.env["southbrook.mi.engine"]._emit_recommendation(
        subject=f"Service contract {contract.name} renewal in {days_left} days",
        body=f"Vendor: {contract.vendor_id.name}, "
             f"annual cost: ${contract.annual_cost}",
        persona="ops_manager",
    )
```

## Linking to maintenance.request

When a breakdown is dispatched + the equipment has an active
contract:

```python
def action_dispatch(self):
    result = super().action_dispatch()
    # Check for active contract
    contract = self.env["southbrook.cmms.service_contract"].search([
        ("state", "=", "active"),
        ("equipment_ids", "in", self.equipment_id.id),
    ], limit=1)
    if contract and contract.contract_type in ("full", "response_only"):
        # Route to vendor
        self.maintenance_request_id.user_id = contract.vendor_id.user_id.id
        # Notify vendor
        contract.vendor_id.message_post(
            body=_("Breakdown dispatched: %s") % self.name)
    return result
```

## Common mistakes + how to recover

- **"Contract expired but state still active"** — `_cron_check_renewals`
  may have failed. Manual: bulk-update state on expired contracts.
- **"Renewal notification fires every day until renewed"** —
  `_already_notified` check failing. Verify dedup logic.
- **"Equipment under contract but in-house tech responded"** —
  vendor routing didn't fire OR equipment's contract link missing.

## Quiz

**Q1.** Service contract `parts_only`. Breakdown happens. Vendor
routing?

> No vendor routing — parts only doesn't include labour.
> Maintenance handles in-house. Parts ordered at vendor discount.

**Q2.** Contract expires Dec 31. `renewal_reminder_days = 60`.
First reminder?

> ~Nov 1 (60 days before).

**Q3.** Renewed via `action_renew()`. State transitions?

> active → renewed (or active stays + a new contract created
> covering next period).

**Q4.** Add a new contract type "advisory_only" (vendor consults
but doesn't dispatch). Approach?

> Add to `contract_type` Selection. Update vendor-routing logic
> to skip dispatch for advisory_only.

**Q5.** Multi-vendor contract on same equipment. Effect?

> Search returns first match (limit=1). Order matters; consider
> adding `priority` field for tie-break.
