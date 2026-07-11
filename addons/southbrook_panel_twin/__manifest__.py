# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Panel Digital Twin",
    "summary": "Per-panel manufacturing passport: identity, genealogy, "
               "event stream. Foundation for optimization + AI advisor.",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry",
    "website": "https://southbrookcabinetry.space",
    "category": "Manufacturing",
    "depends": ["mrp"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "views/sb_panel_views.xml",
        "views/sb_panel_menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
