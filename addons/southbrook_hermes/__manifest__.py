# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Fabio",
    "summary": "Human-approved Fabio recommendation queue for Southbrook.",
    "description": """
Southbrook Fabio
=================

Adds a small Odoo approval boundary for the Fabio sidecar agent. External
AI/tool orchestration can submit draft recommendations through an API key, but
business changes remain gated by Odoo users who approve, reject, and apply the
recommendation.
""",
    "version": "19.0.4.3.0",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry",
    "website": "https://southbrookcabinetry.space",
    "category": "Productivity",
    "depends": [
        "crm",
        "mail",
        "project",
        "southbrook_api",
        "southbrook_kitchen_workspace",
        "southbrook_os",
        # 2026-07-01 E2E audit fix — views/order_builder_chat_inject.xml
        # inherits QWeb template `southbrook_estimating_website
        # .portal_order_builder`, resolved at manifest data-load time.
        # Without this dep, -i southbrook_hermes on a DB where
        # _website is not present raises `External ID not found`.
        # southbrook_estimating_website itself depends transitively on
        # kitchen_workspace via estimating, so this widens the load-
        # order guarantee to include the website addon.
        "southbrook_estimating_website",
    ],
    # PyJWT (`import jwt`) is needed at RUNTIME for any /hermes/* or
    # /api/hermes/* endpoint that mints or verifies a token, but the helper
    # in utils/jwt_helper.py degrades to a clear RuntimeError when missing —
    # so we don't gate install on it. Install in the container before
    # exposing any of the Hermes controllers: docker exec southbrook-odoo
    # pip install PyJWT (or bake into the image).
    "data": [
        "data/fabio_partner.xml",
        "data/ir_config_parameter.xml",
        "security/hermes_security.xml",
        "security/ir.model.access.csv",
        "views/hermes_recommendation_views.xml",
        "views/hermes_question_views.xml",
        "views/hermes_menus.xml",
        "views/order_builder_chat_inject.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            # 2026-06-22 bugfix: XML BEFORE JS so the OWL templates
            # registry has `southbrook_hermes.HermesChat` populated by
            # the time autoMount() runs. The opposite ordering used to
            # race the templates loader on the Order Builder portal
            # page (manifested as
            #   `OwlError: Missing template: "southbrook_hermes.HermesChat"`
            # + `TypeError: ... reading 'add'`). The autoMount() in
            # hermes_chat.esm.js also try/catches the mount so a
            # similar race in a future bundle can't break the host
            # page — but ordering first is the cheaper fix.
            "southbrook_hermes/static/src/components/hermes_chat/hermes_chat.xml",
            "southbrook_hermes/static/src/components/hermes_chat/hermes_chat.esm.js",
            "southbrook_hermes/static/src/components/hermes_chat/hermes_chat.scss",
        ],
    },
    "application": True,
    "installable": True,
    "auto_install": False,
}
