# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook MRP Planning (CE-native)",
    "summary": "Demand-driven requirements planning for make-to-order "
               "cabinetry: confirmed sales orders explode through BoMs into "
               "component requirements, netted against supply, released as "
               "MOs or POs.",
    "description": "CE-native replacement for the openvalue_mrp_planning_* "
                   "family. The vendor engine iterates reorder points and "
                   "filters its sales-demand path on is_storable; Southbrook "
                   "has zero reorder points and models every finished-goods "
                   "cabinet as a non-storable consumable, so a vendor run "
                   "yields zero lines (measured on production 2026-07-26). "
                   "Here demand comes from confirmed sales orders and "
                   "storability gates only netting, never demand "
                   "recognition. Requirements are reviewable; nothing is "
                   "created until a line is explicitly released, and "
                   "computing a plan never writes to mrp.production, "
                   "mrp.workorder or stock.",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry",
    "website": "https://southbrookcabinetry.space",
    "category": "Manufacturing",
    "depends": ["mrp", "sale_stock", "purchase_stock"],
    "data": [
        "security/ir.model.access.csv",
        "views/planning_views.xml",
        "views/planning_menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
