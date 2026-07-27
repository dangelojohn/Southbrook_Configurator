---
course: 25
chapter: 25.6
title: Integrations Module — Adding a New Vendor Adapter
duration: 8
audience: Developer onboarding a new integration vendor
prereqs: Lessons 25.1-25.5
custom_modules: southbrook_integrations
---

# Integrations Module — Adding a New Vendor Adapter

## The pattern (in 5 steps)

1. Add a new model + table for sessions / messages / logs
2. Implement the API client (HTTP or socket)
3. Add a heartbeat for status monitoring
4. Wire MI engine integration if vendor failure is operationally
   relevant
5. Add views + menu

## A worked example: adding "Vendor X" CRM integration

Goal: sync customer records to Vendor X CRM.

### Step 1: Models

```python
# In a new addon: southbrook_integrations_vendorx
class SouthbrookIntegrationsVendorxSession(models.Model):
    _name = "southbrook.integrations.vendorx_session"
    _description = "Vendor X CRM Session"
```

Fields:

```python
name        = fields.Char(default=lambda s: s._make_seq())
state       = fields.Selection([
    ("draft", "Draft"),
    ("active", "Active"),
    ("ended", "Ended"),
    ("errored", "Errored"),
])
opened_at   = fields.Datetime()
ended_at    = fields.Datetime()
```

### Step 2: API client

```python
class SouthbrookIntegrationsVendorxClient(models.AbstractModel):
    _name = "southbrook.integrations.vendorx_client"
    
    @api.model
    def push_customer(self, partner_id):
        """Push a customer to Vendor X CRM."""
        partner = self.env["res.partner"].browse(partner_id)
        endpoint = self.env.company.vendorx_endpoint
        api_key = self.env.company.vendorx_api_key
        
        payload = {
            "external_id": partner.id,
            "name": partner.name,
            "email": partner.email,
            "phone": partner.phone,
        }
        
        response = requests.post(
            f"{endpoint}/customers",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        
        if response.status_code != 200:
            raise UserError(
                _("Vendor X rejected: %s") % response.text)
        
        return response.json()
```

### Step 3: Heartbeat

```python
@api.model
def _cron_vendorx_heartbeat(self):
    try:
        response = requests.get(
            self.env.company.vendorx_endpoint + "/health",
            timeout=5,
        )
        if response.status_code == 200:
            self._log_status("ok")
        else:
            self._log_status("error", message=response.text)
    except Exception as e:
        self._log_status("error", message=str(e))
```

Cron data:

```xml
<record id="cron_vendorx_heartbeat" model="ir.cron">
    <field name="name">Vendor X Heartbeat</field>
    <field name="model_id" ref="model_southbrook_integrations_vendorx_client"/>
    <field name="state">code</field>
    <field name="code">model._cron_vendorx_heartbeat()</field>
    <field name="interval_type">minutes</field>
    <field name="interval_number">5</field>
    <field name="active" eval="True"/>
</record>
```

### Step 4: MI engine integration

```python
class MiEngineVendorxExt(models.AbstractModel):
    _inherit = "southbrook.mi.engine"
    
    @api.model
    def _check_vendorx_signals(self):
        """Detect Vendor X outage; surface recommendation."""
        recent_pings = self.env["southbrook.integrations.vendorx_log"]\
            .search([("printed_at", ">", fields.Datetime.now() -
                                          relativedelta(minutes=15))])
        errors = recent_pings.filtered(lambda l: l.status == "error")
        if len(errors) >= 3 and len(errors) / len(recent_pings) >= 0.5:
            self._emit_recommendation(
                subject="Vendor X integration degraded",
                body=("Vendor X heartbeat failing 50%+ in last 15 min. "
                      "Check vendor status page + escalate."),
                persona="sysadmin",
            )
```

### Step 5: Views + menu

```xml
<menuitem id="menu_vendorx" name="Vendor X"
          parent="southbrook_integrations.menu_integrations_root"/>

<menuitem id="menu_vendorx_sessions" name="Sessions"
          parent="menu_vendorx"
          action="action_vendorx_sessions"/>
```

## Configuration pattern

Per-company API keys + endpoints in `res.company`:

```python
class ResCompany(models.Model):
    _inherit = "res.company"
    
    vendorx_endpoint = fields.Char(default="https://api.vendorx.com")
    vendorx_api_key = fields.Char()
```

Avoid sys-params for vendor secrets; per-company config supports
multi-tenant.

## Common mistakes + how to recover

- **"New integration but no logs"** — heartbeat cron not active.
  Check `ir.cron.active`.
- **"API key in code"** — refactor to `res.company`. Never
  hard-code secrets.
- **"MI engine doesn't fire"** — `_check_vendorx_signals` not
  hooked into the engine's main loop. Add to `_check_all`.

## Quiz

**Q1.** New vendor integration — addons/in or new addon?

> New addon. Keeps each integration isolated; lets uninstalls clean up
> per-vendor.

**Q2.** API keys storage?

> `res.company` fields. Never code.

**Q3.** Heartbeat cron interval typical?

> 5 minutes for active integrations. Less frequent for low-traffic
> ones.

**Q4.** MI engine integration mandatory?

> Only if vendor downtime impacts operations. Cosmetic integrations
> don't need MI engine.

**Q5.** Test new vendor — environment?

> Vendor's sandbox URL (most provide one) before pointing at
> production. Configure as `vendorx_endpoint = sandbox URL`.
