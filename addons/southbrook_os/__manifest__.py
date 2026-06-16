# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook OS",
    "summary": "Canonical, governed knowledge layer of the Southbrook platform.",
    "description": """
Southbrook OS
=============

The version-controlled description of how Southbrook works as a business.
Hand-curated canonical markdown + Odoo-generated dynamic sections, governed
through OS Revision Orders (OSROs) and published as dated snapshots.

Consumers: Hermes (RAG grounding), public viewer (v1.1), Overseer (v1.x).
""",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry / OdooIQ",
    "website": "https://southbrookcabinetry.space",
    "category": "Productivity",
    "depends": [
        "base",
        "mail",
        "product",
        "mrp",
        "southbrook_estimating",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/os_section_seed.xml",
        "data/ir_cron.xml",
    ],
    "external_dependencies": {
        "python": ["markdown", "yaml"],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
