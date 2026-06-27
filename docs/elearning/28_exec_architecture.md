---
course: 28
chapter: 28.1
title: Exec Dashboard Module — Architecture and Tile Registry
duration: 7
audience: Developer learning southbrook_exec_dashboard internals
prereqs: Native Odoo OWL familiarity helpful
custom_modules: southbrook_exec_dashboard
---

# Exec Dashboard Module — Architecture and Tile Registry

## The module at a glance

- Path: `addons/southbrook_exec_dashboard/`
- Version: 19.0.1.0.0
- Depends on: `base`, `mail`, `web`,
  `southbrook_manufacturing_intelligence`,
  `southbrook_hermes` (for Hermes tile)

## Source layout

```
addons/southbrook_exec_dashboard/
├── models/
│   ├── tile.py              — base tile model
│   ├── tile_kpi.py          — KPI/metric tiles
│   ├── tile_hermes.py       — Hermes-flagged items tile
│   └── exec_view.py         — view-side model wrapping the OWL component
├── views/
│   ├── exec_dashboard_views.xml
│   └── exec_dashboard_menus.xml
├── static/src/
│   ├── exec_dashboard.js    — OWL component
│   ├── exec_dashboard.xml   — OWL template
│   └── exec_dashboard.scss  — mobile-first styles
└── controllers/
    └── exec_api.py          — JSON endpoint for tile data
```

## Tile model

```python
class SouthbrookExecDashboardTile(models.Model):
    _name = "southbrook.exec_dashboard.tile"
    _description = "Exec Dashboard Tile"
    _order = "sequence"
```

Fields:

```python
name              = fields.Char(required=True)
tile_code         = fields.Char(required=True, index=True)
tile_type         = fields.Selection([
    ("kpi", "KPI"),
    ("trend", "Trend"),
    ("list", "List"),
    ("hermes", "Hermes Flagged"),
])
sequence          = fields.Integer()
compute_method    = fields.Char()
refresh_interval_min = fields.Integer(default=5)
last_value_json   = fields.Text()
last_computed_at  = fields.Datetime()
visible_to_group_ids = fields.Many2many("res.groups")
```

## Tile registry pattern

The `tile_code` field links to a method on a registered model.
The compute_method is resolved at runtime:

```python
def compute(self):
    """Resolve the compute_method + run."""
    self.ensure_one()
    model, method_name = self.compute_method.split(".", 1)
    if model not in self.env:
        raise UserError(_("Model %s not registered") % model)
    method = getattr(self.env[model], method_name, None)
    if not callable(method):
        raise UserError(_("Method %s not callable") % method_name)
    return method()
```

So `compute_method = "southbrook.mi.engine.get_quality_health_tile"`
resolves to that method call.

## Tile data XML

```xml
<record id="tile_quality_health" model="southbrook.exec_dashboard.tile">
    <field name="name">Quality Health</field>
    <field name="tile_code">quality_health</field>
    <field name="tile_type">kpi</field>
    <field name="sequence">10</field>
    <field name="compute_method">southbrook.mi.engine.get_quality_health_tile</field>
    <field name="refresh_interval_min">5</field>
</record>
```

## OWL view at /exec/morning

```python
class SouthbrookExecDashboardController(http.Controller):
    
    @http.route("/exec/morning", type="http", auth="user")
    def morning_briefing(self):
        return request.render(
            "southbrook_exec_dashboard.morning_briefing_template")
```

The template mounts the OWL component which queries the API.

## Common mistakes + how to recover

- **"Tile shows but value is missing"** — compute method may be
  failing. Check the tile record's chatter for errors.
- **"Tile not refreshing"** — `refresh_interval_min` may be too
  long, OR the cron isn't running.
- **"New tile not appearing"** — `visible_to_group_ids` excludes
  user. Check group membership.

## Quiz

**Q1.** What's the relationship between tile_code and compute_method?

> `tile_code` is the short label; `compute_method` is the actual
> Python-method-dotted-path that produces the value.

**Q2.** Tile model — how does it know what to render?

> `tile_type` (kpi/trend/list/hermes) drives the OWL template's
> render path.

**Q3.** Visibility per group — how enforced?

> `visible_to_group_ids` m2m. API filters tiles by user's groups.

**Q4.** Add a new tile via XML — minimum fields?

> name, tile_code, tile_type, compute_method.

**Q5.** Tile compute method errors. Effect on tile?

> `last_value_json` stays at the last successful value. UI shows
> stale data + chatter has the error log.
