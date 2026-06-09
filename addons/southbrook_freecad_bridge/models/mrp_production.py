# SPDX-License-Identifier: LGPL-3.0-only
"""mrp.production extension — CAD-bridge surface.

Adds the three fields the FreeCAD bridge writes back via /plm/cad_callback:

  x_cad_status         — selection: pending | rendering | done | error
  x_cad_attachment_ids — many2many to ir.attachment for DXF/SVG/PDF/STEP
  x_plm_eco_id         — many2one to southbrook.eco linking the MO to the
                          PLM revision that governs its template BoM

Deliberately additive: no field rename, no behaviour change on existing MOs.
The Module-2 server action that POSTs render jobs to the bridge is a
separate file and is GATED off by default (G2a / owner-confirmation).
"""
from odoo import fields, models


CAD_STATUS_VALUES = [
    ("pending", "Pending"),
    ("rendering", "Rendering"),
    ("done", "Done"),
    ("error", "Error"),
]


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    x_cad_status = fields.Selection(
        CAD_STATUS_VALUES,
        string="CAD Status",
        default="pending",
        tracking=True,
        help="Lifecycle of the FreeCAD render artifacts for this MO. "
             "Set by the bridge callback after a render completes.",
    )
    x_cad_attachment_ids = fields.Many2many(
        comodel_name="ir.attachment",
        relation="mrp_production_cad_attachment_rel",
        column1="production_id",
        column2="attachment_id",
        string="CAD Artifacts",
        help="DXF (per panel), SVG/PDF shop drawing, STEP AP214 assembly. "
             "Written by the bridge via XML-RPC after a successful render.",
    )
    x_plm_eco_id = fields.Many2one(
        comodel_name="southbrook.eco",
        string="Governing ECO",
        ondelete="restrict",
        help="The PLM Engineering Change Order whose approved revision "
             "of the template BoM this MO was built against.",
    )
