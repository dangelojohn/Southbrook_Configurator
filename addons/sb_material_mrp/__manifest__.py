# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Materials — MRP",
    "version": "19.0.1.14.1",
    "category": "Manufacturing",
    "summary": "Density->weight + tiered cost sourcing on native MRP BoM/MO.",
    "license": "LGPL-3",
    "depends": [
        "sb_material_core",
        "mrp",
        "purchase",
        "purchase_stock",
        "southbrook_estimating",
    ],
    "data": [
        "views/mrp_bom_views.xml",
        "views/product_template_views.xml",
        "views/purchase_order_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
}
