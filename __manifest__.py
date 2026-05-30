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
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
