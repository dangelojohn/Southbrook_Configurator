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
    "version": "19.0.2.0.0",
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
    "external_dependencies": {
        "python": ["jwt"],
    },
    "data": [
        "data/fabio_partner.xml",
        "data/ir_config_parameter.xml",
        "security/hermes_security.xml",
        "security/ir.model.access.csv",
        "views/hermes_recommendation_views.xml",
        "views/hermes_question_views.xml",
        "views/hermes_menus.xml",
    ],
    "application": True,
    "installable": True,
    "auto_install": False,
}
