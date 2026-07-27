# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Shop Floor Control (CE-native)",
    "summary": "Work-order scheduling dates, sequencing, workcenter daily "
               "load and the manufacturing-order completion gate.",
    "description": "CE-native replacement for mrp_shop_floor_control. "
                   "Preserves the API surface consumed by the costing layer "
                   "and the finite-capacity scheduling engine: _sfc_capacity, "
                   "sfc_sequence, date_planned_start_wo / "
                   "date_planned_finished_wo on both mrp.production and "
                   "mrp.workorder, _rebuild_capacity_load, "
                   "date_actual_finished_wo, qty_output_wo, and the "
                   "setup/working/teardown duration split on "
                   "mrp.workcenter.productivity. Drops the Plotly capacity "
                   "chart, the aggregate standard/actual time fields and the "
                   "capacity-check wizard, none of which had external "
                   "readers. CANNOT be installed alongside "
                   "mrp_shop_floor_control: both define the same fields on "
                   "mrp.production and mrp.workorder.",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry",
    "website": "https://southbrookcabinetry.space",
    "category": "Manufacturing",
    "depends": ["mrp", "resource"],
    "data": ["security/ir.model.access.csv", "views/shopfloor_views.xml"],
    "installable": True,
    "application": False,
    "auto_install": False,
}
