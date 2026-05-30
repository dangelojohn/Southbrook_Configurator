# Southbrook Estimating

The engine + sales-rep Order Builder for Southbrook Kitchens on Odoo 19 CE.

This addon adds the Prodboard-class estimating experience on top of the
OCA `product_configurator` v19 suite. Customers and dealers configure
cabinets; the configurator captures structured Odoo records that feed the
manufacturing chain — no spreadsheets, no re-keying.

## Status

**Phase 1 installable on a fresh Odoo 19 CE database** (verified live on
the QNAP southbrook stack 2026-05-30 — see `../../PUNCHLIST.md` NF16–NF20
for the issues caught at first live install + their fixes). Phase 2 (3D
WebGL planner + customer one-page configurator) tracked separately.

## Quick install

The short version, for the impatient:

```bash
# 1. Python dep that the OCA configurator suite needs but Odoo's
#    official Debian image does not ship — install before -i.
pip install --break-system-packages Mako

# 2. Drop all 4 addons into your addons path. They install together;
#    Odoo resolves dependency order from each manifest. Do NOT split
#    these across separate -i invocations.
odoo --addons-path=/path/to/addons \
     -d <dbname> \
     -i southbrook_estimating \
     --stop-after-init

# 3. Verify (psql):
#    name                       | state
#    product_configurator       | installed
#    product_configurator_mrp   | installed
#    product_configurator_sale  | installed
#    southbrook_estimating      | installed
```

If step 2 stops with `external dependency not met: mako`, step 1 didn't
take. Re-run `pip install Mako` inside whatever Python the Odoo process
uses (this is NOT always system Python — Docker images sometimes ship a
separate `/usr/lib/python3/dist-packages`).

## Prerequisites

### Runtime

| Component | Version | Notes |
|---|---|---|
| Odoo | **19.0 Community Edition** | Enterprise is not required and not tested. Do not run on 18.x or 17.x — view inheritance, `display_type` selection, and `mrp.bom.produce_delay` location all differ. |
| PostgreSQL | 14+ | Anything Odoo 19 supports. JSON fields require 14 minimum. |
| Python | 3.11+ | Matches Odoo 19's official Debian image. |
| Node.js | 18+ | Only for asset builds; Odoo bundles a JS toolchain internally. |

### Python packages

These do NOT come from `apt install odoo` or the official Odoo 19 Docker
image — install separately before running `-i`:

| Package | PyPI name | Why | Source |
|---|---|---|---|
| Mako templates | `Mako` (case-sensitive on some installers) | Used by `product_configurator` wizard renderer | Declared in `external_dependencies` of both this addon and `product_configurator` |

`pip install --break-system-packages Mako` works on Debian/Ubuntu
post-PEP-668. On Alpine-based images use the venv's pip.

### System packages

Standard Odoo 19 install. The estimating addon adds no new system-package
requirements (no `wkhtmltopdf` extension beyond the stock report stack,
no `libpq-dev` beyond Odoo's own, no LDAP).

### Odoo modules (declared in `__manifest__.py`)

Odoo will auto-install these when you `-i southbrook_estimating`:

| Module | Source | Version |
|---|---|---|
| `product_configurator` | OCA `OCA/product-configurator` 19.0 branch | 19.0.1.0.0 |
| `product_configurator_mrp` | OCA `OCA/product-configurator` 19.0 branch | 19.0.1.0.0 |
| `product_configurator_sale` | OCA `OCA/product-configurator` 19.0 branch | 19.0.1.0.0 |
| `mrp`, `sale_management`, `stock`, `account`, `contacts`, `crm` | Odoo 19 CE core | 19.0 |

The 3 OCA modules ship bundled in this repo under `addons/` — they are
NOT on the Odoo Apps Store. The bundle is a snapshot of the 18→19 port
maintained at `addons/product_configurator{,_mrp,_sale}`; pulling fresh
from upstream `https://github.com/OCA/product-configurator` (when the
19.0 branch lands officially) will also work and is the recommended path
for production. Do not mix bundle + upstream — pick one.

The companion website addon `southbrook_estimating_website` depends on
this one and adds the customer-facing one-page configurator. It is a
Phase 2 deliverable and is NOT installable in this Phase 1 snapshot.

## Known install-time gotchas (NF1 – NF20)

These were caught during live install on a fresh Odoo 19 CE DB and are
documented in full in `../../PUNCHLIST.md`. If you hit any of these on
your own install, the fix is already in this commit — no action needed.

| NF | Symptom | Root cause + fix |
|---|---|---|
| **NF1** | `UserError: external dependency not met: mako` | The OCA suite needs Mako; not in the official Odoo image. → `pip install --break-system-packages Mako` |
| **NF16** | `KeyError` on `produce_delay` field path during compute | `produce_delay` lives on `mrp.bom`, not on `product.template` or `product.product`. The `@api.depends` path was wrong; fix uses `bom.produce_delay` directly. |
| **NF18** | `CheckViolation: product_attribute_check_multi_checkbox_no_variant` | Odoo 19's `product.attribute` requires `create_variant='no_variant'` when `display_type='multi'`. Also: `display_type='hidden'` is not in the Odoo 19 selection ({radio, pills, select, color, multi, image}). |
| **NF19** | `ParseError: The attribute Finish must have at least one value` | A `product.template.attribute.line` cannot have empty `value_ids`. Phase-1 placeholder values for Finish + Handle now seeded in `data/attributes.xml`. |
| **NF20** | `ParseError: <xpath expr=".../tree">' cannot be located in parent view` | Odoo 17 renamed `<tree>` to `<list>` in view XML. All xpath in `views/sale_order_views.xml` use `/list/` now; the `view_mode` field uses `list,form`. |

## Verifying the install

Once `southbrook_estimating` shows `installed` in `ir_module_module`:

```bash
# Restart Odoo so workers reload the module
docker restart <odoo-container>

# HTTPS probe (adjust host)
curl -k https://<your-host>/web/login          # expect 200
curl -k https://<your-host>/odoo/sales         # backend Order Builder
```

Login → Sales → Order Builder. You should see a draft sale.order list
view with the southbrook columns (zone, channel, southbrook savings).
The 5 demo partners (Image Floor, Pro Finish, Richwood, Amazing Window,
Demo Tradesperson Tier 3) appear under Contacts after the demo data
loads.

## Smoke test

The locked Phase-1 smoke test (per Q7) is:

1. Open Sales → Order Builder.
2. Create a new order with customer **Demo Tradesperson (Tier 3)**.
3. Add 9 cabinet lines from the case-study (`docs/Southbrook_ImageFloor_Case_Study.md` §appendix).
4. Confirm the −35% pricelist applies automatically (channel resolution).
5. Maple-box cabinets carry +10% price extra and +2 weeks lead time.
6. BoM preview tab shows the rolled-up panel/door/hardware lines.
7. Switch the customer to a Retail walk-in — all lines re-price to list price.
8. Switch back to Tier 3 — −35% restored without re-configuring lines.

If steps 4 or 5 fail, the pricelist resolution dictionary is the suspect
(`models/sale_order.py:_TRADESPERSON_TIER_PRICELISTS`).

## Canonical design docs

Read these before changing anything in this addon:

| Doc | What it answers |
|---|---|
| `../../CLAUDE.md` | The operating brief — phasing, personas, brand boundaries |
| `../../docs/SAMI_Southbrook_Odoo19_Build_Spec.md` | Locked architecture, 7-routine custom-code register, the hybrid configurator model |
| `../../docs/Southbrook_Excel_to_Odoo_Mapping.md` | Business rules + the 4 declarative configurator rules in §3.4 |
| `../../docs/PRODBOARD_MANIFEST.md` | Data-model and UX blueprint — what we mirror and what's deliberate moat |
| `../../docs/Southbrook_ImageFloor_Case_Study.md` | Persona reference for the sales-rep Order Builder |
| `../../docs/Southbrook_Consolidated_Dataset.xlsx` | Seed data (illustrative until #8 lands) |
| `../../PUNCHLIST.md` | 21 locked decisions (Q1–Q21) + ongoing findings (NF1–NF9) |

Cite Q-numbers and NF-numbers in commit messages where decisions are
exercised — that's how this codebase stays forensically traceable to its
gating decisions.

## Custom-code surface

Per `SAMI_Southbrook_Odoo19_Build_Spec.md` §4, exactly **7 routines** in
this addon are genuinely custom code. Everything else is data,
configuration, or `_inherit` extension. Adding an 8th routine requires a
`PUNCHLIST.md` justification.

## License

LGPL-3 — matches OCA convention; permits commercial use of the addon's
output (manufactured kitchens) without copyleft transit.
