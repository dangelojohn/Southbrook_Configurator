# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Estimating",
    "summary": "A Prodboard-class kitchen Order Builder on Odoo 19 CE — "
               "multi-zone grid, 6-channel pricelist, parametric BoM, "
               "Signature Spec Sheet PDF.",
    "description": """
Southbrook Estimating
=====================

The sales-rep-facing Order Builder for Southbrook Kitchens on Odoo 19.0
Community Edition, built on top of the OCA product_configurator suite.

This addon ships:

* The Order Builder backend with multi-zone grid (BASE_RUN / WALL /
  TALL / ISLAND / ACCESSORY / OTHER) and "Duplicate as Draft" action
  for iterative-design workflows.
* 11 declarative configurator attributes (plus 3 derived) seeded with
  12 cabinet templates and 65 product.config.line rule records covering
  4 business rules (series-door, box-series, width-doorcount,
  family-softclose).
* 6 channel pricelists (Retail / Dealer / Tradesperson / KD / Big-Box /
  Refacing CTHS) plus 3 tradesperson tier sub-pricelists, dispatched
  via class-level tables.
* Parametric panel-cut math via models/mrp_bom.py with NF14-documented
  geometric conventions (frameless euro construction; named constants
  swap when canonical specifications land).
* QWeb reports: Signature Spec Sheet (sale.order-bound, customer PDF),
  Shop Copy (mrp.production-bound, shop-floor companion), Door Order
  (sale.order-bound per-SO door schedule).
* The southbrook.order.analytics companion model captures channel,
  series, lifecycle timestamps, and BoM-rollup counts on every order
  confirm — the AI data spine for future forecast / quote / yield work.
* 95 automated tests including a 10-step Phase-1 smoke gate.

Dependencies
------------

This addon depends on the OCA product_configurator suite (product_configurator,
product_configurator_mrp, product_configurator_sale) which is NOT on the
Odoo Apps Store. Install from https://github.com/OCA/product-configurator
before installing this addon.

Phase scope
-----------

This is Phase 1 of a 4-phase build. The customer-facing one-page
configurator (Phase 2), the Three.js procedural 3D layer (Phase 3),
and the Accucutt cut-list bridge (Phase 4) ship in subsequent releases.

Documentation
-------------

See CHANGELOG.md for the release notes, README.md for the canonical
design-docs index, and PUNCHLIST.md for the locked-decisions trace
(referenced from every commit body by Q-number and NF-number).
""",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry",
    "maintainers": ["southbrook"],
    "website": "https://southbrookcabinetry.space",
    "support": "support@southbrookcabinetry.space",
    "category": "Sales/Configurator",
    "images": [
        "static/description/banner.png",
    ],
    #
    # See ../../CLAUDE.md for the operating brief and ../../docs/
    # for the canonical architecture, business rules, and reference
    # artifacts. README.md in this directory points to both.
    #
    "depends": [
        # OCA configurator suite (4 modules, untouched per CLAUDE.md §3)
        "product_configurator",
        "product_configurator_mrp",
        "product_configurator_sale",
        # Odoo core — sales + manufacturing + accounting + stock spine
        # per Build Spec §0 / §2.1 ("the data spine").
        "mrp",
        "sale_management",
        "stock",
        "account",
        "contacts",
        "crm",
    ],
    "data": [
        "security/ir.model.access.csv",
        # Commit 2 — seed parameters + res.partner view extension
        "data/config_parameters.xml",
        "views/res_partner_views.xml",
        # Commit 3 — configurator attribute vocabulary
        "data/attributes.xml",
        # Commit 4 — 6 channel pricelists + 3 tradesperson sub-tiers
        "data/pricelists.xml",
        # Commit 7 — 12 cabinet templates + 132 attribute_lines
        # LOAD ORDER MATTERS: templates BEFORE config_rules. The
        # product.config.line records in config_rules.xml use ref()
        # on attribute_line_ids defined in product_templates.xml. If
        # this list gets alphabetised by a future contributor, install
        # fails with "external id not found" on the rule records.
        "data/product_templates.xml",
        # Commit 5+7 — 4 rule triggers + 65 per-template config.line records
        "data/config_rules.xml",
        # Commit 9 — Order Builder views, user-prefs view, menu
        "views/sale_order_views.xml",
        "views/res_users_views.xml",
        # Commit 10 — QWeb reports (routine #6 partial)
        # Styles MUST load before the report templates that reference them
        # via t-call. If reordered, the templates fail to render.
        "reports/southbrook_report_styles.xml",
        "reports/signature_spec_sheet.xml",
        "reports/shop_copy.xml",
        "reports/door_order.xml",
    ],
    # ------------------------------------------------------------------
    # Demo data — loaded only with --demo flag.
    # All files are noupdate="1" so demo modifications during gate
    # review survive subsequent -u southbrook_estimating runs.
    # ------------------------------------------------------------------
    "demo": [
        "demo/southbrook_demo_partners.xml",
        # Orders MUST load after partners (FK refs); the function/
        # action_confirm call at the bottom fires the analytics hook.
        "demo/southbrook_demo_orders.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
