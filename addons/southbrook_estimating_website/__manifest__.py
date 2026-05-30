# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Estimating — Website",
    "summary": "The customer-facing one-page kitchen configurator on "
               "southbrookcabinetry.space (Phase 2 + Phase 3 deliverable).",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry",
    "website": "https://southbrookcabinetry.space",
    "category": "Website/eCommerce",
    #
    # Independently deployable from southbrook_estimating so:
    #   - The sales-rep backend can run without the public website addon
    #     (useful for early integration testing + dealer terminals).
    #   - Backend load is not bloated by the Three.js asset bundle.
    #
    # See ../../CLAUDE.md §3 "Why two addons, not one" for the rationale.
    #
    "depends": [
        "southbrook_estimating",
        "website_product_configurator",   # OCA — public-facing wizard base
        "portal",                          # /my/... portal layout + auth
    ],
    "data": [
        # Track 2 commit 1 — portal-route view templates.
        "security/ir.model.access.csv",
        "views/portal_template.xml",
    ],
    # Dedicated asset bundle (charter Q4 answer) so the OWL portal
    # components only load on the Order Builder route. Other portal
    # pages (/shop, /my, etc.) stay clean.
    #
    # T2C2 adds portal_boot.esm.js — the OWL bootstrap script that
    # finds the mount-point div on the portal page and mounts the
    # <OrderBuilder/> component into it.
    "assets": {
        "web.assets_frontend": [
            "southbrook_estimating_website/static/src/scss/portal_root.scss",
            "southbrook_estimating_website/static/src/js/portal_boot.esm.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
