# SPDX-License-Identifier: LGPL-3.0-only
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Dimension threshold (mm) above which a picking is flagged as oversize.
OVERSIZE_THRESHOLD_MM = 2400.0


def _max_dim_mm(product):
    """Return the largest of length / width / height dims on a product.product
    or its template, defensively probing field names that vary across Odoo
    builds. Returns 0.0 when nothing is available."""
    if not product:
        return 0.0
    candidates = []
    tmpl = product.product_tmpl_id if "product_tmpl_id" in product._fields else product
    for rec in (product, tmpl):
        for fname in ("product_length", "product_width", "product_height"):
            if fname in rec._fields:
                val = getattr(rec, fname, 0.0) or 0.0
                if val:
                    candidates.append(float(val))
    return max(candidates) if candidates else 0.0


class StockPickingCmms(models.Model):
    _inherit = "stock.picking"

    is_oversize_load = fields.Boolean(
        string="Oversize Load",
        compute="_compute_is_oversize_load",
        store=True,
    )
    oversize_permit_jurisdictions = fields.Char(
        string="Permit Jurisdictions",
        help="Comma-separated province codes (e.g. ON,QC,NB).",
    )
    oversize_permit_state = fields.Selection(
        [
            ("not_required", "Not Required"),
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("on_route", "On Route"),
        ],
        default="not_required",
    )
    oversize_permit_attachment_ids = fields.Many2many(
        "ir.attachment",
        relation="southbrook_cmms_picking_permit_attach_rel",
        column1="picking_id",
        column2="attachment_id",
        string="Permit Documents",
    )
    pickup_3pl_carrier = fields.Many2one(
        "res.partner",
        string="3PL Carrier",
    )
    pickup_3pl_tracking_url = fields.Char(string="3PL Tracking URL")
    is_3pl_asn = fields.Boolean(
        string="3PL ASN",
        compute="_compute_is_3pl_asn",
        store=True,
    )

    @api.depends("move_ids.product_id")
    def _compute_is_oversize_load(self):
        for picking in self:
            flagged = False
            for move in picking.move_ids:
                if _max_dim_mm(move.product_id) > OVERSIZE_THRESHOLD_MM:
                    flagged = True
                    break
            picking.is_oversize_load = flagged

    @api.depends("pickup_3pl_carrier")
    def _compute_is_3pl_asn(self):
        for picking in self:
            picking.is_3pl_asn = bool(picking.pickup_3pl_carrier)
