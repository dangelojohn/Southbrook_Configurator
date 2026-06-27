---
course: 25
chapter: 25.2
title: Integrations Module — Homag iX Simulator
duration: 8
audience: Developer working with the Homag iX integration
prereqs: Lesson 25.1
custom_modules: southbrook_integrations
---

# Integrations Module — Homag iX Simulator

## What this integrates

Homag iX is the cloud platform that controls modern Homag CNC
routers + edge banders (and other Homag equipment). v1 ships a
SIMULATOR — production iX integration is v1.x.

The simulator implements:
- Session establishment (auth + handshake)
- Message exchange (nest request → nest file response)
- Status reporting

## Models

```python
class SouthbrookIntegrationsHomagSession(models.Model):
    _name = "southbrook.integrations.homag_session"
    _description = "Homag iX Session"
```

Fields:

```python
name           = fields.Char(default=lambda s: s._make_seq())
machine_id     = fields.Char()  # iX machine identifier
state          = fields.Selection([
    ("draft", "Draft"),
    ("active", "Active"),
    ("ended", "Ended"),
    ("errored", "Errored"),
], default="draft")
opened_at      = fields.Datetime()
ended_at       = fields.Datetime()
message_count  = fields.Integer(compute="_compute_msg_count")
msg_ids        = fields.One2many("southbrook.integrations.homag_msg",
                                 "session_id")
```

## Message model

```python
class SouthbrookIntegrationsHomagMsg(models.Model):
    _name = "southbrook.integrations.homag_msg"
    _order = "sent_at"
```

Fields:

```python
session_id   = fields.Many2one("...homag_session", required=True)
direction    = fields.Selection([("in", "Inbound"), ("out", "Outbound")])
msg_type     = fields.Char()  # "nest_request", "nest_response", etc.
payload_json = fields.Text()
sent_at      = fields.Datetime(default=fields.Datetime.now)
status       = fields.Selection([
    ("ok", "OK"),
    ("error", "Error"),
])
```

## Simulator flow

```python
def request_nest(self, cabinet_specs):
    """Simulate a nest request → wait for nest file response."""
    session = self._ensure_active_session()
    
    # Outbound: nest request
    out = self.env["southbrook.integrations.homag_msg"].create({
        "session_id": session.id,
        "direction": "out",
        "msg_type": "nest_request",
        "payload_json": json.dumps(cabinet_specs),
        "status": "ok",
    })
    
    # Simulate processing (in real iX: webhook back)
    nest_file = self._fake_nest_response(cabinet_specs)
    
    # Inbound: nest response
    inn = self.env["southbrook.integrations.homag_msg"].create({
        "session_id": session.id,
        "direction": "in",
        "msg_type": "nest_response",
        "payload_json": json.dumps({"nest_file": nest_file}),
        "status": "ok",
    })
    
    return nest_file
```

## Real iX integration plan (when ready)

The simulator's interface (`request_nest()` etc.) is preserved
when swapping for the real client:

```python
def request_nest(self, cabinet_specs):
    response = requests.post(
        self.env.company.homag_ix_endpoint + "/nest",
        json=cabinet_specs,
        headers={"Authorization": f"Bearer {self.api_key}"},
    )
    response.raise_for_status()
    return response.json()["nest_file"]
```

The model + session pattern survive; only the simulation logic is
replaced.

## Heartbeat cron

```python
@api.model
def _cron_homag_heartbeat(self):
    endpoint = self.env.company.homag_ix_endpoint
    if not endpoint:
        return  # Not configured
    
    try:
        response = requests.get(endpoint + "/health", timeout=10)
        if response.status_code == 200:
            self._log_heartbeat("ok")
        else:
            self._log_heartbeat("error")
    except Exception as e:
        self._log_heartbeat("error", message=str(e))
```

Three consecutive errors fire a recommendation to the Plant GM.

## Common mistakes + how to recover

- **"Sessions accumulate without ending"** — `_ensure_active_session()`
  may be creating new sessions per call. Verify it reuses an
  active one if available.
- **"Nest response too large for payload_json"** — Text field is
  unlimited but UI may truncate at display. Add a separate
  attachment field for binaries.
- **"Real iX integration fails after simulator works"** —
  authentication scheme differs. Real iX uses OAuth2; simulator
  was bearer token. Update the auth flow.

## Quiz

**Q1.** Session model state transitions?

> draft → active → ended (or errored).

**Q2.** Simulator's `request_nest()` — what's faked?

> The nest computation. Real iX runs nesting algorithm; simulator
> returns a static pre-computed nest based on the spec.

**Q3.** Heartbeat fires recommendation after how many failures?

> Three consecutive. Configurable.

**Q4.** Swap simulator for real iX — what changes?

> `request_nest()` body (HTTP call instead of fake), and config:
> set `homag_ix_endpoint` + auth credentials.

**Q5.** Message direction `in` vs `out` — from whose perspective?

> Southbrook's. `out` = sent to Homag; `in` = received from Homag.
