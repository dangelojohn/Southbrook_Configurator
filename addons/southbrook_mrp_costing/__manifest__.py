# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook MRP Costing (CE-native)",
    "summary": "Standard, planned and actual manufacturing cost on the "
               "manufacturing order, with variance against plan.",
    "description": "CE-native replacement for the standard/planned/actual "
                   "cost layers of mrp_product_costing. Drops the "
                   "mrp_shop_floor_control dependency by reading native "
                   "work-order duration instead of the setup/working/teardown "
                   "split. Reports a zero-output order honestly instead of "
                   "costing it as one unit. Maintains industrial_cost as a "
                   "stored field rather than writing it only during a "
                   "financial close that is gated on unset company accounts. "
                   "Preserves the planned_direct_cost and industrial_cost "
                   "field names that Command Center and Project job-margin "
                   "scoring read. CANNOT be installed alongside "
                   "mrp_product_costing: both define the same fields on "
                   "mrp.production.",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry",
    "website": "https://southbrookcabinetry.space",
    "category": "Manufacturing",
    "depends": ["mrp", "mrp_account"],
    "data": ["views/mrp_production_views.xml"],
    "installable": True,
    "application": False,
    "auto_install": False,
}
