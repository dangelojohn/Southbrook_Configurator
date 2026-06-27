---
course: 24
chapter: 24.1
title: Finance Pack — Architecture and Install
duration: 7
audience: Developer or admin learning southbrook_finance_pack internals
prereqs: Native Odoo Accounting familiarity
custom_modules: southbrook_finance_pack
---

# Finance Pack — Architecture and Install

## The module at a glance

- Path: `addons/southbrook_finance_pack/`
- Version: 19.0.1.0.0
- License: LGPL-3
- Depends on: `base`, `account`, `mrp`, `stock`, `stock_account`,
  `southbrook_manufacturing_intelligence`

## Source layout

```
addons/southbrook_finance_pack/
├── models/
│   ├── asset.py              — capital asset record
│   ├── cca_class.py          — CRA class master
│   ├── cca_entry.py          — per-year compute results
│   ├── budget.py             — budget + budget pivot
│   ├── hst_return.py         — quarterly/monthly HST return
│   ├── wip_report.py         — read-only query view
│   └── mi_engine_ext.py      — MI engine integration
├── views/
├── reports/                  — QWeb reports (asset summary, etc.)
├── security/
└── data/
    ├── cca_classes.xml       — Class 8, 10, 12, 50, 53, etc.
    └── default_accounts.xml  — chart of accounts hints
```

## Install

```bash
./scripts/deploy_to_qnap.sh southbrook_finance_pack
```

Native `account` + `stock_account` are mandatory dependencies.
`mrp` is for WIP report.

## What -i does

1. Creates asset, cca_class, cca_entry, budget, hst_return tables
2. Loads CCA class master (12 standard classes — 1, 8, 10, 12,
   13, 14, 43, 50, 53, etc.)
3. Adds 6 menus under Finance
4. Creates a cron at 03:00 to refresh the WIP snapshot cache

## CCA class seed data

```xml
<record id="cca_class_8" model="southbrook.finance.cca_class">
    <field name="code">Class 8</field>
    <field name="name">General office equipment + general M&P</field>
    <field name="rate">0.20</field>
    <field name="half_year_rule" eval="True"/>
    <field name="description">Photocopiers, machinery without
        specific class. Most generic equipment defaults here.</field>
</record>

<record id="cca_class_53" model="southbrook.finance.cca_class">
    <field name="code">Class 53</field>
    <field name="name">Manufacturing &amp; processing equipment</field>
    <field name="rate">0.50</field>
    <field name="half_year_rule" eval="True"/>
    <field name="description">CNC routers, edge banders, presses
        acquired after 2015 for M&P use.</field>
</record>
```

Verify against CRA T2 Schedule 8 for the current year; rates can
change.

## Cron landscape

| Cron | Schedule | Purpose |
|---|---|---|
| `cron_wip_snapshot` | 03:00 daily | Cache the WIP report query (otherwise it's slow at month-end) |

The MI engine hooks (in `mi_engine_ext.py`) run on the MI loop's
schedule, not a Finance-specific cron.

## Account configuration

The pack relies on specific GL accounts being configured per
company:

- WIP Account (e.g. 211000) — for WIP report reconciliation
- Asset register accounts (per CCA class)
- HST Receivable / Payable
- Gain on Disposal / Loss on Disposal

Configure in *Settings → Companies → Accounts* (or via the
Accounting Configuration wizard).

## Common mistakes + how to recover

- **"Module installed but Asset Register menu empty"** — CCA class
  data file didn't load. Reinstall via `-i` (not `-u`) to
  reload `noupdate=0` data. Or seed via UI.
- **"WIP report timeout"** — query is heavy in high-MO tenants.
  Verify the `cron_wip_snapshot` ran; if not, snapshot is empty
  and live query runs.
- **"HST Return doesn't pull invoices"** — `tax_line_id` filter
  doesn't match the company's HST tax account configuration. Map
  the right accounts in the HST Return form's *Tax Accounts* tab.

## Quiz

**Q1.** Native modules required?

> `account`, `stock_account`, plus `mrp` for WIP report.

**Q2.** Where do CCA rates live?

> `southbrook.finance.cca_class` records, seeded from
> `data/cca_classes.xml`.

**Q3.** Why a cron for WIP report?

> Query is heavy; cron caches at 03:00 so users get fast reads
> during the day.

**Q4.** Asset register vs native asset model — which to use?

> Both can coexist. Native `account.asset` handles accounting
> depreciation; Southbrook handles CCA (tax). You may need to
> configure each asset twice if you want both views.

**Q5.** HST Return menu shows no records. Reason?

> No HST Return created yet, OR `state` filter hiding draft.
> Create a new return + *Pull*.
