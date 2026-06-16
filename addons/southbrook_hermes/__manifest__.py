# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook HERMES",
    "summary": "Human-approved HERMES recommendation queue for Southbrook.",
    "description": """
Southbrook HERMES
=================

Adds a small Odoo approval boundary for the HERMES sidecar agent. External
AI/tool orchestration can submit draft recommendations through an API key, but
business changes remain gated by Odoo users who approve, reject, and apply the
recommendation.
""",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry",
    "website": "https://southbrookcabinetry.space",
    "category": "Productivity",
    "depends": [
        "mail",
        "project",
        "southbrook_api",
    ],
    "data": [
        "security/hermes_security.xml",
        "security/ir.model.access.csv",
        "views/hermes_recommendation_views.xml",
        "views/hermes_menus.xml",
    ],
    "application": True,
    "installable": True,
    "auto_install": False,
}
