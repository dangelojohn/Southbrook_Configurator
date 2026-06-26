# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.shipping.unit — physical shipping units (cartons / pallets / skids).

Captures the load-out detail that BOLs + EDI 856 ASNs need:
  - dimensions for permit logistics (oversize > 7' wide)
  - contents (which products / which builder unit)
  - linked stock.picking
  - QR for driver-loading scan
  - loaded_at / loaded_by, delivered_at / delivered_by

The QR on the side of the pallet IS the manifest reference — scan
at any point in the chain (truck loading bay, jobsite, customer
verification) and the right action surfaces.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


UNIT_KINDS = [
    ("carton", "Carton"),
    ("pallet", "Pallet"),
    ("skid", "Skid"),
    ("crate", "Crate"),
    ("loose", "Loose Cabinet"),
]


UNIT_STATES = [
    ("draft", "Draft"),
    ("loaded", "Loaded on Truck"),
    ("delivered", "Delivered"),
    ("returned", "Returned"),
]


class ShippingUnit(models.Model):
    _name = "southbrook.shipping.unit"
    _description = "Southbrook Shipping Unit"
    _inherit = ["mail.thread", "mail.activity.mixin", "southbrook.qr.mixin"]
    _order = "create_date desc, id desc"
    _qr_kind = "ship"

    name = fields.Char(
        default=lambda self: _("New"), required=True,
        copy=False, readonly=True, index=True,
    )
    kind = fields.Selection(
        UNIT_KINDS, default="pallet", required=True, tracking=True)
    state = fields.Selection(
        UNIT_STATES, default="draft", required=True, tracking=True, index=True)
    picking_id = fields.Many2one(
        "stock.picking", string="Delivery", index=True, tracking=True,
        ondelete="set null",
    )
    partner_id = fields.Many2one(
        "res.partner", related="picking_id.partner_id",
        store=True, readonly=True, index=True,
    )
    builder_unit_ref = fields.Char(
        string="Builder Unit #", tracking=True, index=True,
        help="Mattamy / builder identifier (e.g. M-4521).",
    )
    product_ids = fields.Many2many(
        "product.product",
        "southbrook_shipping_unit_product_rel",
        "unit_id", "product_id",
        string="Contents",
    )
    weight_kg = fields.Float(string="Weight (kg)", digits=(8, 2))
    length_mm = fields.Float(string="Length (mm)", digits=(8, 0))
    width_mm = fields.Float(string="Width (mm)", digits=(8, 0))
    height_mm = fields.Float(string="Height (mm)", digits=(8, 0))
    oversize = fields.Boolean(
        compute="_compute_oversize", store=True,
        help="True when any dim > 2134mm (~7') — triggers oversize "
             "permit logistics flag.",
    )
    permit_jurisdictions = fields.Char(
        string="Permit Jurisdictions",
        help="Comma-separated routes/states/provinces requiring "
             "oversize permits for this unit. Auto-filled when "
             "oversize=True from the delivery address; operator can edit.",
    )
    truck_ref = fields.Char(string="Truck #", tracking=True)
    loaded_at = fields.Datetime(readonly=True, copy=False)
    loaded_by = fields.Many2one(
        "res.users", string="Loaded By", readonly=True, copy=False)
    delivered_at = fields.Datetime(readonly=True, copy=False)
    delivered_by = fields.Many2one(
        "res.users", string="Delivered By", readonly=True, copy=False)
    delivery_signature = fields.Binary(
        string="Delivery Signature",
        help="Captured by the Flutter PWA POD flow.",
    )
    delivery_photo = fields.Binary(
        string="Delivery Photo",
        help="Captured by the POD scan flow.",
    )
    notes = fields.Text()

    @api.depends("length_mm", "width_mm", "height_mm")
    def _compute_oversize(self):
        for rec in self:
            mx = max(rec.length_mm or 0, rec.width_mm or 0, rec.height_mm or 0)
            rec.oversize = mx > 2134.0  # 7 ft

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "southbrook.shipping.unit") or _("SHU/New")
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # State transitions (also exposed via QR scan actions)
    # ------------------------------------------------------------------
    def action_mark_loaded(self, truck_ref=None):
        """Operator scans pallet QR + truck QR at loading bay."""
        for rec in self:
            rec.write({
                "state": "loaded",
                "loaded_at": fields.Datetime.now(),
                "loaded_by": self.env.user.id,
                "truck_ref": truck_ref or rec.truck_ref,
            })
            rec.message_post(body=_(
                "Loaded on truck %(t)s by %(u)s.") % {
                "t": rec.truck_ref or "?",
                "u": self.env.user.display_name,
            })

    def action_mark_delivered(self, signature=None, photo=None):
        """Driver scans pallet QR + 'delivered' action at jobsite.
        Optional signature + photo captured by the Flutter PWA POD."""
        for rec in self:
            vals = {
                "state": "delivered",
                "delivered_at": fields.Datetime.now(),
                "delivered_by": self.env.user.id,
            }
            if signature:
                vals["delivery_signature"] = signature
            if photo:
                vals["delivery_photo"] = photo
            rec.write(vals)
            rec.message_post(body=_(
                "Delivered by %s. POD captured.") %
                self.env.user.display_name)
            # Sweep up: when every unit on the picking is delivered,
            # the picking is operationally done. (Don't auto-validate
            # the picking — let the warehouse operator confirm.)

    def action_mark_returned(self):
        for rec in self:
            rec.state = "returned"


class ShippingUnitQrKind(models.AbstractModel):
    _name = "southbrook.qr.kind.ship"
    _inherit = "southbrook.qr.kind"
    _description = "QR Kind — Shipping Unit"
    _kind_name = "ship"
    _target_model = "southbrook.shipping.unit"

    @api.model
    def handle_action(self, record, action, params):
        if action == "load":
            truck_ref = (params or {}).get("truck_ref")
            record.action_mark_loaded(truck_ref=truck_ref)
            return {"record_name": record.display_name,
                    "record_id": record.id, "model": self._target_model,
                    "message": _("Loaded on truck %s") % (truck_ref or "(unset)")}
        if action == "delivered":
            sig = (params or {}).get("signature")
            photo = (params or {}).get("photo")
            record.action_mark_delivered(signature=sig, photo=photo)
            return {"record_name": record.display_name,
                    "record_id": record.id, "model": self._target_model,
                    "message": _("POD captured — delivered")}
        if action == "manifest":
            # Return manifest dump — products, dims, builder unit
            return {
                "record_name": record.display_name,
                "record_id": record.id,
                "model": self._target_model,
                "message": _("Manifest dump"),
                "manifest": {
                    "builder_unit": record.builder_unit_ref,
                    "kind": record.kind,
                    "weight_kg": record.weight_kg,
                    "dims_mm": [record.length_mm, record.width_mm,
                                record.height_mm],
                    "oversize": record.oversize,
                    "products": [p.display_name for p in record.product_ids],
                    "state": record.state,
                    "truck_ref": record.truck_ref,
                },
            }
        return super().handle_action(record, action, params)
