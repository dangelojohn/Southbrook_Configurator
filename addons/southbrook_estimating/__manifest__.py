# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Estimating",
    "summary": "Engine + sales-rep Order Builder for Southbrook Kitchens "
               "(Prodboard-class one-page configurator on top of OCA "
               "product_configurator v19).",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry",
    "website": "https://southbrookcabinetry.space",
    "category": "Sales/Configurator",
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
