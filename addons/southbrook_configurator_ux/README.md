# Southbrook Configurator UX v2

A UX redesign of the customer-facing product configurator page at
`/shop/<cabinet-slug>` (the form rendered by the OCA
`website_product_configurator` module).

This module **does not** modify either OCA addon. It inherits the
configurator QWeb template and swaps the body markup; the OCA module
keeps its current shipped state.

## Current phase: 1 — Scaffolding

What landed:

- New Odoo addon at `addons/southbrook_configurator_ux/` with the
  standard structure (manifest, views, static, tests).
- QWeb template override (`views/configurator_template.xml`) that
  replaces the body of
  `website_product_configurator.product_configurator` with the
  redesigned two-pane layout (sticky left preview + summary card,
  right chip-selector configurator).
- Static SCSS bundle (`static/src/scss/configurator.scss`) — the
  prototype's inline styles ported to a scoped sheet using
  `.sb_cfg_v2` as the root scope so nothing leaks to other portal
  pages.
- Vanilla JS bundle (`static/src/js/configurator.esm.js`) —
  prototype's behaviour ported and gated on the `#sb_cfg_v2_root`
  mount-point so the bundle no-ops on pages without the v2 markup.
- Asset registration in `__manifest__.py:assets["web.assets_frontend"]`.

Hardcoded OPTIONS / GROUPS / FINISH_COLORS preserved from the
prototype for visual fidelity. Phase 2 swaps them for real data.

## Next phases (deferred — see manifest description)

| Phase | What |
|------:|------|
| 2 | Hydrate OPTIONS from `product.attribute` / `product.attribute.value`; bind `price_extra`; server-side recalc via the configurator session controller. |
| 3 | Move disable rules into a data-driven table (extend `product.config.line` records); render the warnings from the existing rule engine. |
| 4 | xlsxwriter template generator + server-side CSV/xlsx import with row-level validation, preview, and explicit-confirm commit gate. |
| 5 | Tour test + rule-engine unit tests + ARIA/keyboard accessibility audit. |

## Install / dev cycle

```bash
# Install on a fresh DB:
odoo -d southbrook -i southbrook_configurator_ux --stop-after-init --no-http

# Upgrade after edits:
odoo -d southbrook -u southbrook_configurator_ux --stop-after-init --no-http

# Drop the asset bundle so SCSS / JS edits land on next request:
psql -U odoo southbrook -c \
  "DELETE FROM ir_attachment WHERE name LIKE 'web.assets%' OR name LIKE '/web/assets/%';"

# Hard reload the configurator page in a browser to fetch the new bundle.
```

## Uninstall

```bash
odoo -d southbrook --uninstall southbrook_configurator_ux \
  --stop-after-init --no-http
```

The `/shop/<cabinet-slug>` page returns to the original OCA layout
immediately. Nothing else is affected.

## Architecture notes

- **Mount-point guard.** The JS bundle scans for `#sb_cfg_v2_root` on
  `DOMContentLoaded`. Absent → bundle returns immediately. Present →
  the `SouthbrookConfiguratorV2` class instantiates and wires up.
- **CSS scoping.** Every selector inside `configurator.scss` is
  descendant-scoped under `.sb_cfg_v2`. The only exceptions are the
  fixed-position overlay (`.sb_cfg_overlay`) and the toast
  (`.sb_cfg_toast`) which `position: fixed` so they sit at the
  document root regardless.
- **Brand reconciliation.** The prototype's palette is captured as
  SCSS variables at the top of `configurator.scss`. Phase 2 maps
  those variables onto the Signature Series tokens from
  `southbrook_estimating/_southbrook_design_tokens.scss`. For Phase 1
  the prototype HEXes ship verbatim so the visual diff vs the
  prototype is zero.
- **Bulk tools gating.** The "Template Layout" / "Import Product"
  buttons are visible only to internal (non-portal) users via the
  `t-if="not user_id.share"` check on the bulk bar — same pattern
  the existing southbrook_estimating Order Builder uses for
  dealer-only actions.

See `CHANGELOG.md` and `__manifest__.py` for the full phase plan.
