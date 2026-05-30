# Southbrook Kitchen MRP V19CR

> The Estimating Application for Southbrook Cabinetry — a Prodboard-class
> kitchen Order Builder on Odoo 19.0 Community Edition.

This repository is the working tree for the Southbrook Estimating
addon (`addons/southbrook_estimating`) plus the OCA `product_configurator`
suite it depends on (3 modules bundled). It builds Phase 1 — the sales-rep
Order Builder with multi-zone grid, 6-channel pricelist resolution,
parametric BoM rollup, and QWeb reports.

Phase 2 (customer one-page configurator), Phase 3 (Three.js procedural 3D
parametric carcass layer), and Phase 4 (Accucutt cut-list bridge) are
tracked in the phasing plan but not in this snapshot.

The operating brief, locked architecture, and 21+ gating decisions live in:

- `CLAUDE.md` — operating brief and amendment history
- `PUNCHLIST.md` — locked decisions (Q1–Q21) and findings (NF1–NFx)
- `docs/SAMI_Southbrook_Odoo19_Build_Spec.md` — architecture
- `docs/Southbrook_Excel_to_Odoo_Mapping.md` — business rules
- `docs/PRODBOARD_MANIFEST.md` — UX blueprint

## Repository layout

```
addons/
├── product_configurator/         OCA v19.0.1.0.0 (bundled, untouched)
├── product_configurator_mrp/     OCA v19.0.1.0.0 (bundled, untouched)
├── product_configurator_sale/    OCA v19.0.1.0.0 (bundled, untouched)
└── southbrook_estimating/        the Phase-1 deliverable
docs/                             canonical design docs (see CLAUDE.md §1)
scripts/                          backup + deploy helpers (not yet rich)
CLAUDE.md                         the operating brief
PUNCHLIST.md                      locked decisions + findings ledger
```

The 3 OCA modules are bundled as a 19.0 port snapshot. When the upstream
OCA `19.0` branch lands officially, pull from
`https://github.com/OCA/product-configurator` and replace the bundle —
do not mix bundle + upstream sources.

## Deploy quickstart

### 1. Prerequisites

| Component | Version |
|---|---|
| Odoo | **19.0 Community Edition** (Enterprise not required, not tested) |
| PostgreSQL | 14+ |
| Python | 3.11+ |
| `Mako` PyPI package | any recent — `pip install --break-system-packages Mako` |

The Mako requirement is documented in `external_dependencies` of both
`product_configurator/__manifest__.py` and `southbrook_estimating/__manifest__.py`.
The official Odoo 19 Debian image does NOT ship it. **Install Mako before
running `-i`** or the install aborts with `external dependency not met`.

No additional system packages, no `wkhtmltopdf` extensions, no LDAP.

### 2. Drop the addons in place

```bash
# Copy or symlink all 4 addon directories into your Odoo addons path
cp -R addons/product_configurator      /path/to/odoo/addons/
cp -R addons/product_configurator_mrp  /path/to/odoo/addons/
cp -R addons/product_configurator_sale /path/to/odoo/addons/
cp -R addons/southbrook_estimating     /path/to/odoo/addons/
```

For a Docker bind-mount setup the canonical layout is:

```
/path/on/host/addons/         →  /mnt/extra-addons  (container)
```

With UID:GID `100:101` (matching the official Odoo image's `odoo` user).

### 3. Install

```bash
odoo --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons \
     -d <dbname> \
     -i southbrook_estimating \
     --stop-after-init --no-http
```

Odoo resolves the dependency chain — installing
`southbrook_estimating` cascades through the 3 OCA modules and the
Odoo-core dependencies (`mrp`, `sale_management`, `stock`, `account`,
`contacts`, `crm`). Do NOT split this into separate `-i` invocations.

### 4. Verify

```bash
psql -U odoo -d <dbname> -c \
  "SELECT name, state FROM ir_module_module
   WHERE name LIKE 'product_config%' OR name = 'southbrook_estimating'
   ORDER BY name;"
```

Expected:

```
            name            |   state
----------------------------+-----------
 product_configurator       | installed
 product_configurator_mrp   | installed
 product_configurator_sale  | installed
 southbrook_estimating      | installed
```

### 5. Open the UI

Restart the Odoo container so workers reload, then browse to:

```
https://<your-host>/odoo/login
```

Login → **Sales → Order Builder**. The smoke test sequence is documented
in `addons/southbrook_estimating/README.md` § Smoke test.

## Known install gotchas (NF1 – NF20)

Catalogued in `PUNCHLIST.md` and surfaced again in the addon README. The
short version, for the impatient:

| NF | Hits at | Fix |
|---|---|---|
| **NF1** | Module install | `pip install --break-system-packages Mako` before `-i` |
| **NF16** | Compute method runtime | `produce_delay` lives on `mrp.bom` (not `product.template`) |
| **NF18** | XML data load | `display_type='multi'` requires `create_variant='no_variant'`; `'hidden'` is not in the Odoo 19 selection |
| **NF19** | XML data load | `product.template.attribute.line` requires at least one `value_id` |
| **NF20** | View inheritance | Odoo 17+ renamed `<tree>` → `<list>`; xpath and `view_mode` must follow |

All five fixes are already in this commit — they're listed only so future
maintainers know what to look at when porting upstream changes.

## License

Each addon carries its own SPDX license header.

- `southbrook_estimating` — **LGPL-3** (matches OCA convention; permits
  commercial use of manufactured kitchens without copyleft transit).
- OCA `product_configurator{,_mrp,_sale}` — **AGPL-3** (upstream).

## Co-development notes

This codebase is co-developed with John (the human owner). The contract
is documented in `CLAUDE.md` §7 — read it before opening a PR.
Architectural changes require ack; mechanical changes (typos, manifest
bumps, lint, NF fixes) proceed without.

Every commit cites a Q-number (a locked decision) or an NF-number (a
found-during-build issue) — that's how this codebase stays forensically
traceable. Do not break the convention.
