# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Estimating — Website",
    "summary": "The customer-facing one-page kitchen configurator on "
               "southbrookcabinetry.space (Phase 2 + Phase 3 deliverable).",
    "version": "19.0.1.9.0",
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
        # Phase 2 commit 1 — /kitchen-planner customer route + template.
        "views/kitchen_planner_template.xml",
        # G1 + G2 (2026-06-01) — public Southbrook homepage at /.
        "views/homepage_template.xml",
        # G4 + G5 + G6 + G8 (2026-06-01) — branded auth pages
        # (login/signup chrome) + project-name field on signup.
        "views/auth_template.xml",
        # 2026-06-02 — fix 500 on /shop/<slug> caused by upstream
        # OCA website_product_configurator chaining .currency_id on a
        # potentially non-singleton pricelist recordset. Override
        # swaps to website.currency_id (singleton, always available).
        "views/shop_configurator_currency_fix.xml",
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
            # Phase 3 Sprint A1 — vendored @font-face declarations
            # for Roboto Flex + JetBrains Mono. MUST load before the
            # design tokens so subsequent SCSS sees the families
            # already declared. Air-gapped (no Google Fonts CDN).
            "southbrook_estimating_website/static/src/scss/fonts.scss",
            # Step 2 (2026-06-01) — shared Signature Series design
            # tokens, loaded FIRST after fonts. Cross-addon path
            # because the website depends on the estimating addon
            # (which owns the design spine). See
            # docs/CUSTOMER_TO_MANUFACTURING_FLOW.md §5.
            "southbrook_estimating/static/src/scss/_southbrook_design_tokens.scss",
            # Phase 2.5 — Three.js library back-ported from
            # southbrook_estimating Track 1. Same vendored r160 bundle.
            "southbrook_estimating/static/lib/three/three.min.js",
            "southbrook_estimating/static/lib/three/OrbitControls.js",
            "southbrook_estimating_website/static/src/scss/portal_root.scss",
            # G1 + G2 (2026-06-01) — homepage hero + features SCSS.
            "southbrook_estimating_website/static/src/scss/homepage.scss",
            # Phase 2 commit 1 — kitchen-planner three-pane SCSS.
            # Loads AFTER portal_root.scss so the :root tokens defined
            # there are available to .o_kp_* selectors.
            "southbrook_estimating_website/static/src/scss/planner.scss",
            # Order matters: KitchenViewport class is imported by
            # portal_boot, so it must load first.
            "southbrook_estimating_website/static/src/js/kitchen_viewport.esm.js",
            "southbrook_estimating_website/static/src/js/portal_boot.esm.js",
            # Phase 2 commit 2 — OWL <KitchenPlanner/> boot for
            # /kitchen-planner customer route. Independent of
            # portal_boot.esm.js (each bootstrap finds its own
            # mount-point div and returns early if absent on the
            # current page).
            "southbrook_estimating_website/static/src/js/planner_boot.esm.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
