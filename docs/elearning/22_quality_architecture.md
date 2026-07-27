---
course: 22
chapter: 22.1
title: Quality Module — Architecture and Install
duration: 8
audience: Developer or technical admin learning the southbrook_quality internals
prereqs: Python + Odoo addon development familiarity
custom_modules: southbrook_quality
---

# Quality Module — Architecture and Install

## Who this lesson is for

Developer or admin who needs to extend, debug, or customise the
`southbrook_quality` module. Not a user lesson; this is the engine
room.

## The module at a glance

- Path: `addons/southbrook_quality/`
- Version: 19.0.1.0.0 (current prod)
- License: LGPL-3
- Depends on: `base`, `mail`, `mrp`, `stock`, `account`,
  `southbrook_manufacturing_intelligence` (for MI engine
  extension)

## Source layout

```
addons/southbrook_quality/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── ncr.py                  — non-conformance record
│   ├── spc_sample.py           — statistical process control entry
│   ├── cpk_report.py           — process capability
│   ├── quality_dimension.py    — master spec
│   ├── supplier_defect.py      — supplier-side defect logging
│   └── mi_engine_ext.py        — MI engine integration
├── views/
│   ├── ncr_views.xml
│   ├── spc_views.xml
│   ├── cpk_views.xml
│   ├── quality_dimension_views.xml
│   ├── supplier_defect_views.xml
│   └── southbrook_quality_menus.xml
├── security/
│   ├── ir.model.access.csv
│   └── southbrook_quality_groups.xml
└── data/
    ├── sequence_data.xml
    └── default_dimensions.xml
```

## Install

```bash
./scripts/deploy_to_qnap.sh southbrook_quality
```

Or via the Apps menu in Odoo backend: search "Southbrook Quality" →
*Install*.

### Install dependencies

The manifest declares dependencies that must be resolved first.
`mrp` + `stock` come with native Odoo Manufacturing/Inventory.
`southbrook_manufacturing_intelligence` is a sibling Southbrook
module that must be installed before Quality.

### What -i does

1. Creates `southbrook.ncr`, `southbrook.quality.spc_sample`,
   `southbrook.quality.cpk_report`, `southbrook.quality.dimension`,
   `southbrook.quality.supplier_defect` tables
2. Adds the `mi_engine_ext` model mixin to extend the MI engine
3. Loads default sequence (`NCR/YYYY/000xx` format)
4. Loads a seed dimension master (`default_dimensions.xml`) — 5
   common cabinet-shop dimensions
5. Creates security groups
6. Adds menus + actions
7. Registers a cron at 03:30 for the supplier defect rollup

### What -u does

Same as -i but skipping data files with `noupdate="1"` (i.e. seed
dimensions are NOT re-loaded; you can edit them safely).

## v19 install gotchas

The module survived three known v19 traps; the developer should
read these before extending:

1. **`res.groups.category_id` removed** — the security XML omits
   `category_id`; uses "Module / Role" naming instead.
2. **Search view `<group expand="0" string="Group By">` removed** —
   plain `<group>` element.
3. **`_sql_constraints` deprecated** — module uses
   `_name_uniq = models.Constraint('UNIQUE(name)', '...')` style.

If you add a new model, follow these patterns or your -i will fail.

## Cron landscape

| Cron | Schedule | What it does |
|---|---|---|
| `cron_rollup_supplier_scores` | 03:30 daily | Recomputes `res.partner.defect_rate_pct` + `consolidated_score` from supplier_defect records |
| (MI engine has its own cron list; quality piggybacks via mi_engine_ext) | varies | Surfaces critical NCRs + SPC breaches as recommendations |

## Common mistakes + how to recover

- **"-u fails with 'ParseError'"** — most likely a v19 view
  validation trap. Run with
  `--log-handler=odoo.tools.convert:DEBUG` to surface the full
  ValueError.
- **"Module installed but menus don't appear"** — the user isn't in
  the `group_southbrook_quality_user` group. Add them via
  *Settings → Users*.
- **"Migration leaves orphan records after uninstall"** — the
  cleanup hook removes the cron + supplier scoring columns but
  leaves the records (audit retention). Manual cleanup via SQL if
  needed.

## What this lesson does NOT cover

- The NCR state machine internals — lesson 22.2.
- SPC math — lesson 22.3.
- Cpk compute — lesson 22.4.
- Customising — lesson 22.7.

## Quiz

**Q1.** You add a new selection value to `defect_type` on
`southbrook.ncr`. -u fails. Most likely cause?

> The new value isn't in the security CSV's row that grants access.
> Wait, no — selection values don't gate ACL. More likely: a search
> view filter references the old set, or a record rule fails. Run
> with debug logging to surface.

**Q2.** Module imports import-failed. Which module isn't
installed?

> Either `mrp`, `stock`, `account`, or
> `southbrook_manufacturing_intelligence`. Check
> `addons/southbrook_quality/__manifest__.py` `depends` list.

**Q3.** What's the default sequence format for NCRs?

> `NCR/YYYY/000xx` — defined in `data/sequence_data.xml`.

**Q4.** What's the cron schedule for supplier score rollup?

> 03:30 daily (`cron_rollup_supplier_scores`).

**Q5.** Where does the Quality module integrate with Hermes /
Fabio?

> Via `mi_engine_ext.py` — the MI engine surfaces critical NCRs as
> recommendations into the Hermes queue.
