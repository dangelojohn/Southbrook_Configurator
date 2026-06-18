# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Manufacturing Intelligence",
    "summary": "Cut, production, assembly, and install checks for Southbrook MRP.",
    "author": "Southbrook Kitchens / OdooIQ",
    "license": "LGPL-3",
    "category": "Manufacturing",
    "version": "19.0.1.1.1",
    "depends": [
        "mrp",
        "southbrook_estimating",
        "southbrook_mrp_pm",
        "southbrook_kitchen_mrp",
        "southbrook_dealer_portal",
        "southbrook_freecad_bridge",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/mrp_production_views.xml",
        "views/production_package_views.xml",
        "views/manager_dashboard_views.xml",
        "views/pm_kanban_inherit.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
