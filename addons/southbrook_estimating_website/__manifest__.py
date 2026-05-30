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
        "website_product_configurator",   # OCA — the /kitchen-planner route base
        "portal",                          # for /my/estimates per CLAUDE.md §2.1
    ],
    "data": [],
    "assets": {},
    "installable": True,
    "application": False,
    "auto_install": False,
}
