# Southbrook Panel Digital Twin (Phase 1)

Per-panel manufacturing passport: identity (`sb.panel`), genealogy
(`sb.panel.cycle`), event stream (`sb.machine.event`). Foundation for the
optimization + AI-advisor phases. Depends only on `mrp`; touches no existing
module.

## Install (isolated test db)
1. `update_list()` (new module isn't auto-discovered), then
   `odoo -d <db> -i southbrook_panel_twin --stop-after-init`.
2. Tests: add `--test-enable --test-tags southbrook_panel_twin`.

## Demo (no machine required)
```python
mo = env["mrp.production"].create({"product_id": <panel_product>.id})
env["sb.panel"]._simulate_from_production(mo, panel_count=5, seed=99)
# open Manufacturing → Panel Twin → Panels; each panel shows its
# CUT/DRILL genealogy + scan event.
```

## Phase 5 seam
`sb.machine.event.panel_id` is optional so real DRILLTEQ telemetry can be
ingested before a panel is matched. The real transport replaces the
simulator with no schema change.
