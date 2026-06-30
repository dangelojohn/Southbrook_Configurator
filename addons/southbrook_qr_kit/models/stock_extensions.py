# SPDX-License-Identifier: LGPL-3.0-only
"""Stock-model QR extensions.

Adds qr.mixin to stock.location, stock.picking, stock.lot so each
gets qr_image_base64 + kind handler resolution. Operator workflows
that depend on these (bin scan, receipt scan, cycle count) all use
the same pattern.
"""
from odoo import api, fields, models, _


class StockLocation(models.Model):
    _inherit = ["stock.location", "southbrook.qr.mixin"]
    _qr_kind = "loc"


class StockPicking(models.Model):
    _inherit = ["stock.picking", "southbrook.qr.mixin"]
    _qr_kind = "pick"


class StockLot(models.Model):
    _inherit = ["stock.lot", "southbrook.qr.mixin"]
    _qr_kind = "lot"


class StockMove(models.Model):
    """No QR mixin — moves are transient. But we add an inbound scan
    helper used by the bin-scan workflow."""
    _inherit = "stock.move"

    @api.model
    def _scan_quick_move(self, src_location_id, dst_location_id, product_id, qty=1.0):
        """Create + assign + validate a single stock.move in one
        call. Used by the /sb/qr/inventory/bin-scan endpoint.
        Returns the created move."""
        Move = self.env["stock.move"]
        Product = self.env["product.product"].browse(product_id).exists()
        if not Product:
            raise ValueError(_("product_id %s not found") % product_id)
        move = Move.create({
            "name": _("QR scan move: %s") % Product.display_name,
            "product_id": product_id,
            "product_uom": Product.uom_id.id,
            "product_uom_qty": qty,
            "location_id": src_location_id,
            "location_dest_id": dst_location_id,
        })
        move._action_confirm()
        move._action_assign()
        # Mark fully delivered.
        for ml in move.move_line_ids:
            ml.qty_done = ml.reserved_uom_qty or qty
        move._action_done()
        return move


# ----------------------------------------------------------------------
# Kind handlers
# ----------------------------------------------------------------------
class StockLocationQrKind(models.AbstractModel):
    _name = "southbrook.qr.kind.loc"
    _inherit = "southbrook.qr.kind"
    _description = "QR Kind — Stock Location (bin)"
    _kind_name = "loc"
    _target_model = "stock.location"


class StockPickingQrKind(models.AbstractModel):
    _name = "southbrook.qr.kind.pick"
    _inherit = "southbrook.qr.kind"
    _description = "QR Kind — Stock Picking"
    _kind_name = "pick"
    _target_model = "stock.picking"

    @api.model
    def handle_action(self, record, action, params):
        if action == "validate":
            if hasattr(record, "button_validate"):
                record.button_validate()
            return {"record_name": record.display_name,
                    "record_id": record.id, "model": self._target_model,
                    "message": _("Picking validated")}
        return super().handle_action(record, action, params)


class StockLotQrKind(models.AbstractModel):
    _name = "southbrook.qr.kind.lot"
    _inherit = "southbrook.qr.kind"
    _description = "QR Kind — Stock Lot / Serial"
    _kind_name = "lot"
    _target_model = "stock.lot"
