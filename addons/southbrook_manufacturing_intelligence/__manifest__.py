# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Manufacturing Intelligence",
    "summary": "Cut, production, assembly, and install checks for Southbrook MRP.",
    "author": "Southbrook Kitchens / OdooIQ",
    "license": "LGPL-3",
    "category": "Manufacturing",
    "version": "19.0.3.4.0",
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
        # W012 — sequence MUST load before any view that defaults a
        # waiver name (the wizard creates records on submit).
        "data/deviation_waiver_sequence.xml",
        # W053 / R7.6 — 5-min MI recompute sweep cron.
        "data/mi_recompute_cron.xml",
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
        # W012 — engineering deviation approval flow.
        # mi_check_views EXTENDS the NCR form (declared in
        # manager_dashboard_views above) with the header button +
        # statusbar + waiver smart button. Must load AFTER its parent.
        "views/mi_check_views.xml",
        "views/deviation_waiver_views.xml",
        "views/deviation_approval_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
