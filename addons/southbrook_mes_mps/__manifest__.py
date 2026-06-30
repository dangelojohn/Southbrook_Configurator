# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook MES & MPS",
    "summary": (
        "Hand-rolled MPS (rolling 13-week) + OEE per workcenter + live "
        "Bottleneck Report (CE-native, no Enterprise mrp_mps or "
        "mrp_workorder dep)"
    ),
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry / OdooIQ",
    "category": "Manufacturing/MES",
    "depends": [
        "base",
        "mail",
        "mrp",
        "stock",
        "sale",
        "southbrook_kitchen_mrp",
        "southbrook_mrp_kitchen_workcenters",
        "southbrook_manufacturing_intelligence",
    ],
    "data": [
        "security/groups.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "data/cron_oee_daily.xml",
        "data/cron_bottleneck_daily.xml",
        "views/mps_period_views.xml",
        "views/workcenter_capacity_views.xml",
        "views/oee_snapshot_views.xml",
        "views/bottleneck_report_views.xml",
        "views/mi_engine_ext_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
}
