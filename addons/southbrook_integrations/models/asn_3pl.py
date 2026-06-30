# SPDX-License-Identifier: LGPL-3.0-only
"""3PL Advance Shipping Notice (EDI-214-flavoured JSON).

We do NOT ship raw EDI 856 yet (PRD Q-6 descopes the EDI suite to v2). The
ASN model captures the same payload a real X12 856 would carry plus an
oversize-load flag + permit-jurisdiction hint - cabinets above 2.4m hit
"oversize / wide load" rules in ON/QC for over-the-road moves, which the
3PL needs to know before dispatch.
"""
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Industry-rule of thumb: any single carton dim >2.4m needs an oversize
# permit on most Canadian inter-provincial routes. Conservative pre-EDI
# heuristic only; the 3PL still calls the final shot.
OVERSIZE_MM_THRESHOLD = 2400.0


class SouthbrookIntegrationsAsn3pl(models.Model):
    _name = "southbrook.integrations.asn_3pl"
    _description = "3PL Advance Shipping Notice"
    _order = "create_date desc, id desc"
    _inherit = ["mail.thread"]

    name = fields.Char(
        required=True, copy=False, readonly=True, default=lambda s: _("New"),
        tracking=True,
    )
    picking_id = fields.Many2one(
        "stock.picking",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    carrier_id = fields.Many2one(
        "delivery.carrier",
        tracking=True,
        help="3PL carrier the ASN is emitted to.",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("sent", "Sent"),
            ("acked", "Acknowledged"),
            ("shipped", "Shipped"),
            ("delivered", "Delivered"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    payload_json = fields.Text(
        compute="_compute_payload",
        store=False,
        help="JSON envelope materialised from the picking + lines on demand.",
    )
    tracking_number = fields.Char(tracking=True)
    oversize_load_flag = fields.Boolean(
        compute="_compute_oversize",
        store=True,
        help="True if any carton on this picking exceeds the oversize "
             "permit threshold (default 2400mm).",
    )
    permit_jurisdictions = fields.Char(
        help="Comma-separated province codes the load crosses if oversize "
             "(e.g. 'ON,QC'). Hint only; the 3PL files the actual permit.",
    )

    _name_uniq = models.Constraint(
        'UNIQUE(name)',
        "ASN sequence numbers must be unique.",
    )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "southbrook.integrations.asn_3pl"
                ) or _("New")
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("picking_id", "picking_id.move_ids",
                 "picking_id.move_ids.product_id",
                 "picking_id.move_ids.product_uom_qty",
                 "carrier_id", "name")
    def _compute_payload(self):
        for rec in self:
            rec.payload_json = json.dumps(rec._build_envelope(), indent=2)

    @api.depends("picking_id", "picking_id.move_ids",
                 "picking_id.move_ids.product_id")
    def _compute_oversize(self):
        """Flip the oversize flag when any product on the picking exceeds
        the dimension threshold on its product.template.

        Product dims live on ``product.template`` (length/width/height in mm
        when the user picked the metric UOM); we fall back to False if the
        fields are absent so a partial install doesn't crash the compute.
        """
        for rec in self:
            oversize = False
            for move in rec.picking_id.move_ids:
                tmpl = move.product_id.product_tmpl_id
                dims = []
                for f in ("product_length", "product_width", "product_height"):
                    if hasattr(tmpl, f):
                        dims.append(getattr(tmpl, f) or 0.0)
                if dims and max(dims) >= OVERSIZE_MM_THRESHOLD:
                    oversize = True
                    break
            rec.oversize_load_flag = oversize

    # ------------------------------------------------------------------
    # Envelope
    # ------------------------------------------------------------------
    def _build_envelope(self):
        self.ensure_one()
        picking = self.picking_id
        lines = []
        for move in picking.move_ids:
            tmpl = move.product_id.product_tmpl_id
            lines.append({
                "sku": move.product_id.default_code
                       or move.product_id.name,
                "name": move.product_id.display_name,
                "qty": move.product_uom_qty,
                "uom": move.product_uom.name if move.product_uom else "",
                "weight_kg": getattr(tmpl, "weight", 0.0) or 0.0,
                "dims_mm": {
                    "L": getattr(tmpl, "product_length", 0.0) or 0.0,
                    "W": getattr(tmpl, "product_width", 0.0) or 0.0,
                    "H": getattr(tmpl, "product_height", 0.0) or 0.0,
                },
            })
        envelope = {
            "schema": "southbrook.asn.214.v1",
            "asn": self.name,
            "picking": picking.name,
            "sender": (self.env.company.partner_id.display_name
                       if self.env.company else ""),
            "ship_to": picking.partner_id.display_name if picking.partner_id
                       else "",
            "carrier": self.carrier_id.name or "",
            "tracking_number": self.tracking_number or "",
            "oversize": self.oversize_load_flag,
            "permit_jurisdictions": self.permit_jurisdictions or "",
            "lines": lines,
        }
        return envelope

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_emit_asn(self):
        for rec in self:
            if not rec.picking_id:
                raise UserError(_("No picking linked."))
            rec.payload_json = json.dumps(rec._build_envelope(), indent=2)
            rec.state = "sent"
            rec.message_post(body=_("ASN emitted (%s lines).")
                             % len(rec.picking_id.move_ids))
        return True
