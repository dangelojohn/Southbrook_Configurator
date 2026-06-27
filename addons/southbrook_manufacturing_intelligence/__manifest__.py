# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Manufacturing Intelligence",
    "summary": "Cut, production, assembly, and install checks for Southbrook MRP.",
    "author": "Southbrook Kitchens / OdooIQ",
    "license": "LGPL-3",
    "category": "Manufacturing",
    "version": "19.0.3.2.0",
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
        # W010 — split unified Ready Queue into Ready-to-Release
        # (kanban) + Blocked (list with next-action surfaced).
        # Lives here because the domain + view reference x_mi_*
        # fields owned by this addon (the parent menu lives in
        # southbrook_mrp_pm).
        "views/mo_ready_queue_split.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
