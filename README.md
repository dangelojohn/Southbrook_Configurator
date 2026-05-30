# Southbrook Estimating

The engine + sales-rep Order Builder for Southbrook Kitchens on Odoo 19 CE.

This addon adds the Prodboard-class estimating experience on top of the
OCA `product_configurator` v19 suite. Customers and dealers configure
cabinets; the configurator captures structured Odoo records that feed the
manufacturing chain — no spreadsheets, no re-keying.

## Status

**Phase 1 in progress.** See `../../CLAUDE.md` §8 for the phasing
plan and `../../PUNCHLIST.md` for current decisions / blockers.

## Dependencies

This addon depends on:

### OCA configurator suite (untouched, leave at 19.0.1.0.0)

- `product_configurator` — the wizard + restriction engine
- `product_configurator_mrp` — BoM materialisation from configurator selections
- `product_configurator_sale` — sale.order binding

### Odoo Community core

- `mrp`, `sale_management`, `stock`, `account`, `contacts`, `crm`

The companion website addon `southbrook_estimating_website` depends on
this one and adds the customer-facing one-page configurator.

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
