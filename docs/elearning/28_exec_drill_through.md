---
course: 28
chapter: 28.4
title: Exec Dashboard Module — Drill-Through Wiring
duration: 6
audience: Developer implementing tile drill-through
prereqs: Lessons 28.1-28.3
custom_modules: southbrook_exec_dashboard
---

# Exec Dashboard Module — Drill-Through Wiring

## What drill-through means

Click a tile → land on the source data filtered to what the tile
showed. E.g. click "Open NCRs: 12" → NCR list filtered to open.

## The 3 components

1. **drill_action** — the XML id of the target action
2. **drill_domain** — filter pre-applied
3. **drill_context** — additional context (active_tab, group_by, etc.)

## Action handler

```python
def onTileClick(tile) {
    if (!tile.drill_action) return;
    
    this.action.doAction(tile.drill_action, {
        additionalContext: tile.drill_context || {},
        domain: tile.drill_domain || [],
    });
}
```

The `action` service handles routing to the target.

## Pre-applied filter

When the target action loads, the filter shows as a pill at the
top of the search bar. User can clear it to see all records.

## Examples

### Quality tile → NCR list filtered to open

```python
return {
    ...,
    "drill_action": "southbrook_quality.action_southbrook_ncr",
    "drill_domain": [("state", "in", ["open", "quarantine"])],
}
```

### Sales tile → SOs from yesterday

```python
return {
    ...,
    "drill_action": "sale.action_quotations",
    "drill_domain": [("date_order", ">=", yesterday)],
    "drill_context": {"search_default_filter_done": 1},
}
```

### Maintenance tile → breakdown alerts grouped by equipment

```python
return {
    ...,
    "drill_action": "southbrook_cmms_wms.action_breakdown_alerts",
    "drill_context": {
        "search_default_group_by_equipment": 1,
        "search_default_filter_open": 1,
    },
}
```

## When the target action doesn't exist

Common scenarios:
- Module not installed (e.g. southbrook_quality)
- Action XML id renamed

Defensive handling:

```python
@api.model
def get_dashboard_data(self):
    tiles = self.search([])
    visible_tiles = []
    for tile in tiles:
        data = json.loads(tile.last_value_json or "{}")
        # Verify drill action exists
        if data.get("drill_action"):
            try:
                self.env.ref(data["drill_action"])
            except ValueError:
                data["drill_action"] = None  # Disable click
        visible_tiles.append(data)
    return visible_tiles
```

## Group-by + chart on drill-through

For tiles that drill to a graph view, use `view_type`:

```python
return {
    ...,
    "drill_action": "southbrook_quality.action_southbrook_ncr",
    "drill_context": {
        "search_default_group_by_severity": 1,
        "view_type": "graph",
    },
}
```

## Common mistakes + how to recover

- **"Drill click does nothing"** — drill_action XML id doesn't
  exist. Verify via *Settings → Technical → Actions*.
- **"Filter not pre-applied"** — drill_domain syntax wrong. Must
  be Odoo-domain list, not string.
- **"User sees error: NotFound"** — action exists but user's
  group can't access. Check ACL.

## Quiz

**Q1.** Tile click → drill_action. What service routes the
action?

> `action` service (`useService("action")`). Calls `doAction()`.

**Q2.** drill_domain format?

> Odoo domain list: `[("state", "=", "open"), ...]`. Same as
> Python domain.

**Q3.** Target action doesn't exist. User clicks. Effect?

> NotFound error popup. Defensively disable click + remove
> drill_action via env.ref check.

**Q4.** Drill to graph view — how?

> Set `drill_context = {"view_type": "graph"}`.

**Q5.** Multiple tiles drill to same action with different
filters. Issue?

> No — same action can take different domains. Each tile's
> drill is independent.
