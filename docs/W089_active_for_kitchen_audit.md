# W089 — `x_sbk_active_for_kitchen` flag audit

**Date:** 2026-06-27
**Source roadmap item:** R2.14
**Verdict:** **NO ACTION NEEDED. CONCERN UNFOUNDED IN CURRENT PROD STATE.**

## Background

R2.14 raised the concern that operators may be unable to find their
work-orders if their workcenter has `x_sbk_active_for_kitchen=False` —
quoting "8 of 14 workcenters" as suspected configuration misses.

## Investigation

### Schema

`x_sbk_active_for_kitchen` is a Boolean on `mrp.workcenter`, defined in
`addons/southbrook_mrp_kitchen_workcenters/models/mrp_workcenter.py:212-219`:

```python
x_sbk_active_for_kitchen = fields.Boolean(
    string="Active for Kitchen Production",
    default=True,
    help="False to hide this work center from the kitchen MRP "
         "menus + filters without deactivating it for non-kitchen "
         "MOs. Useful when a station is shared with another "
         "Southbrook product line.",
)
```

Default = `True`. The field is purely **opt-out** behaviour.

### Where the flag is read

```
addons/southbrook_mrp_kitchen_workcenters/views/mrp_workcenter_views.xml:23
addons/southbrook_mrp_kitchen_workcenters/views/mrp_workcenter_views.xml:67
addons/southbrook_mrp_kitchen_workcenters/views/mrp_workcenter_views.xml:86-87
addons/southbrook_mrp_kitchen_workcenters/tests/test_m1_workcenter_fields.py
addons/southbrook_mrp_kitchen_workcenters/tests/test_m2_operation_templates.py
```

Filter usage in views/mrp_workcenter_views.xml:

```xml
<filter name="filter_sbk_active_for_kitchen" string="Kitchen Active"
        domain="[('x_sbk_active_for_kitchen', '=', True)]"/>
```

This is an **opt-in named filter** in the work-center search view — NOT
a default domain on the action. No `search_default_filter_sbk_active_for_kitchen`
context flag exists anywhere in the codebase. The operator-facing kanban
and work-order views do NOT filter on this field at all.

### Live DB probe (SSH read-only)

```
ssh admin@192.168.68.108 system-docker exec southbrook-postgres \
  psql -U odoo -d southbrook -t -c "SELECT id, name, x_sbk_active_for_kitchen,
  x_sbk_station_type, active FROM mrp_workcenter ORDER BY id"
```

Result:

| ID | Name                                    | Active for Kitchen | Station Type    | Active |
|----|-----------------------------------------|--------------------|-----------------|--------|
|  1 | Panel Saw / CNC Nesting                 | True               | cutting         | True   |
|  2 | Edge Bander                             | True               | edge_banding    | True   |
|  3 | CNC Boring                              | True               | cnc             | True   |
|  4 | Carcass Assembly                        | True               | assembly        | True   |
|  5 | Door Hanging                            | True               | assembly        | True   |
|  6 | Hardware Fitting                        | True               | hardware        | True   |
|  7 | Quality Control                         | True               | quality         | True   |
|  8 | Pack & Label                            | True               | packing         | True   |
| 11 | Door Shop                               | True               | cnc             | True   |
| 12 | Sanding Prep                            | True               | sanding         | True   |
| 13 | Paint Booth                             | True               | finishing       | True   |
| 14 | Cure/Dry Room                           | True               | finishing       | True   |
| 18 | Design Review / Production Engineering  | True               | engineering     | True   |
| 19 | CNC Router 02 (Backup)                  | True               | cnc             | True   |

**14 of 14 workcenters have `x_sbk_active_for_kitchen=True`.**

The "8 of 14 are False" premise in R2.14 is incorrect against current
prod state. Either the premise was based on a stale snapshot, or the
field was re-checked at some point between the audit and today.

## Conclusion

| Question                                                          | Answer |
|-------------------------------------------------------------------|--------|
| Are any operator cells hidden by `active_for_kitchen=False`?      | No.    |
| Is the default for new workcenters correct (True)?                | Yes.   |
| Does any view/action force `active_for_kitchen=True` in its domain? | No — only an opt-in filter chip. |
| Is the field reachable from the WC form when editing?             | Yes (line 23). |

**No source-code change required.** The R2.14 concern reflects a
risk-pattern (`opt-out flag could hide operator cells`) that is
not currently realised in the data.

## Recommendation for John

1. **No flag flips needed.** Skip the proposed remediation.
2. **Optional hardening:** if you want defence-in-depth so a future
   config drift can't silently hide a cell, you could:
   - Add a daily cron that posts a chatter warning when any
     `mrp.workcenter` has `active=True` AND `x_sbk_active_for_kitchen=False`
     AND `x_sbk_station_type IS NOT NULL`.
   - Or: drop the field entirely (`active` on the base model already
     covers the hide-from-everywhere case; this field was only useful
     for the multi-product-line scenario which is hypothetical today).
3. **Re-audit cadence:** re-run the SQL probe quarterly. If a cell
   ever flips to False, ensure it was an intentional ops decision and
   not Studio drift.

## SSH probe (for re-running)

```bash
ssh admin@192.168.68.108 "/share/CACHEDEV3_DATA/.qpkg/container-station/bin/system-docker exec southbrook-postgres psql -U odoo -d southbrook -t -c \"SELECT id, name, x_sbk_active_for_kitchen, x_sbk_station_type, active FROM mrp_workcenter ORDER BY id\""
```
