# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook FreeCAD Bridge",
    "summary": "Odoo side of the FreeCAD render pipeline — MO → render job → "
               "CAD attachments + status, plus the G1 BoM-contents safety gate.",
    "description": """
Southbrook FreeCAD Bridge (Module 2 — Odoo side)
=================================================

Wires the manufacturing-order lifecycle into the FreeCAD bridge service:

* Server action on mrp.production confirm posts a render job to the bridge.
* /plm/cad_callback controller receives ir.attachment IDs + status from the
  bridge and writes them back onto the MO.
* mrp.production gains x_cad_status / x_cad_attachment_ids / x_plm_eco_id.
* Kanban shop-floor view shows colour-coded CAD-status badges.
* Manager group gets a "Regenerate CAD" action button.

Hard gates:

* G1 (BoM-contents) — tests/test_bom_contents.py asserts that the BoM
  produced by the configurator's create_get_bom matches the canonical
  panel formulas in shared/southbrook_dims.py (mounted at /srv/shared and
  importable via PYTHONPATH). G1 must pass before this module deploys
  anything.
* G2 (CLOSED 2026-06-09) — Peter Tuschak signed off the 7 panel formulas.
* G2a (OWNER-CONFIRM) — even with G1 green, the bridge POST + MO confirm
  server action stay inert until the project owner gives explicit go-ahead.
* G5 (FreeCAD-runtime) — services/freecad_bridge must expose freecadcmd
  headless before render-related tests count as passing.

The bridge SERVICE itself lives in services/freecad_bridge/ outside the
addons tree.
""",
    "author": "Southbrook Kitchens / OdooIQ",
    "license": "LGPL-3",
    "category": "Manufacturing",
    "version": "19.0.0.1.0",
    "depends": [
        "mrp",
        "product",
        "mail",
        "southbrook_estimating",
        "southbrook_plm",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/system_parameters.xml",
        "views/mrp_production_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
