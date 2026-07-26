# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Materials — Core",
    "version": "19.0.1.1.0",
    "category": "Manufacturing",
    "summary": "Material master (extends kitchen material): family taxonomy, "
               "effective density, weight_source, per-family waste.",
    "author": "Southbrook / METISA",
    "license": "LGPL-3",
    "depends": ["southbrook_mrp_kitchen_workcenters", "product", "uom", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/material_family_data.xml",
        "data/material_seed_data.xml",
        "views/material_family_views.xml",
        "views/southbrook_kitchen_material_views.xml",
    ],
    "installable": True,
}
