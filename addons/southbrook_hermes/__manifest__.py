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
    "version": "19.0.3.1.0",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry",
    "website": "https://southbrookcabinetry.space",
    "category": "Productivity",
    "depends": [
        "mail",
        "project",
        "southbrook_api",
        "southbrook_kitchen_workspace",
        "southbrook_os",
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
            "southbrook_hermes/static/src/components/hermes_chat/hermes_chat.esm.js",
            "southbrook_hermes/static/src/components/hermes_chat/hermes_chat.xml",
            "southbrook_hermes/static/src/components/hermes_chat/hermes_chat.scss",
        ],
    },
    "application": True,
    "installable": True,
    "auto_install": False,
}
