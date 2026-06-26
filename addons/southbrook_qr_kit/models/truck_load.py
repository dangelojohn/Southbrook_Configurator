# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.truck.load — aggregate shipping.units into one truck.

A truck load is the BOL-level container. Operators scan the truck
QR at the loading bay, then beep each pallet/carton QR to mark it
loaded. The model tracks:

  - which shipping units are MANIFESTED (planned for this truck)
  - which are LOADED (actually scanned on)
  - gate the "Roll Out" action until every manifested unit is loaded
  - alert on EXTRA scans (a unit that wasn't on the BOL)

Gate behavior: roll_out_blocked is computed = any manifested unit
not yet loaded OR any loaded unit not in the manifest. Operator
sees what's missing/extra in the form and can resolve before
release.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


LOAD_STATES = [
    ("draft", "Draft"),
    ("loading", "Loading"),
    ("rolled_out", "Rolled Out"),
    ("returned", "Returned"),
]


class TruckLoad(models.Model):
    _name = "southbrook.truck.load"
    _description = "Southbrook Truck Load Manifest"
    _inherit = ["mail.thread", "mail.activity.mixin", "southbrook.qr.mixin"]
    _order = "scheduled_at desc, id desc"
    _qr_kind = "truck"

    name = fields.Char(
        default=lambda self: _("New"), required=True,
        copy=False, readonly=True, index=True,
    )
    state = fields.Selection(
        LOAD_STATES, default="draft", required=True,
        tracking=True, index=True,
    )
    truck_ref = fields.Char(
        string="Truck #", required=True, tracking=True, index=True,
        help="Truck plate / fleet number. Also encoded in the QR.",
    )
    driver_id = fields.Many2one(
        "res.users", string="Driver", tracking=True,
        help="Optional Odoo user. Many drivers won't be Odoo users; "
             "use driver_name in that case.",
    )
    driver_name = fields.Char(
        string="Driver Name", tracking=True,
        help="Free-text driver name when driver isn't an Odoo user.",
    )
    scheduled_at = fields.Datetime(
        string="Scheduled Departure", index=True, tracking=True,
        default=fields.Datetime.now,
    )
    rolled_out_at = fields.Datetime(readonly=True, copy=False, index=True)
    rolled_out_by = fields.Many2one(
        "res.users", string="Released By", readonly=True, copy=False)

    manifest_unit_ids = fields.Many2many(
        "southbrook.shipping.unit",
        "truck_load_manifest_rel",
        "load_id", "unit_id",
        string="Manifested Units",
        help="Units PLANNED to ride on this truck.",
    )
    loaded_unit_ids = fields.Many2many(
        "southbrook.shipping.unit",
        "truck_load_loaded_rel",
        "load_id", "unit_id",
        string="Loaded Units",
        help="Units actually scanned on at the loading bay.",
    )
    manifest_count = fields.Integer(
        compute="_compute_counts", store=True)
    loaded_count = fields.Integer(
        compute="_compute_counts", store=True)
    missing_count = fields.Integer(
        string="Missing", compute="_compute_counts", store=True,
        help="Manifested but not loaded.",
    )
    extra_count = fields.Integer(
        string="Extra", compute="_compute_counts", store=True,
        help="Loaded but not manifested — alert.",
    )
    roll_out_blocked = fields.Boolean(
        compute="_compute_counts", store=True,
        help="True when missing or extra > 0.",
    )

    total_weight_kg = fields.Float(
        string="Total Weight (kg)", compute="_compute_totals", store=True,
        digits=(10, 2),
    )
    oversize_count = fields.Integer(
        string="Oversize Units", compute="_compute_totals", store=True,
        help="Count of loaded units flagged oversize. Triggers permit "
             "logistics review.",
    )
    notes = fields.Text()

    @api.depends("manifest_unit_ids", "loaded_unit_ids")
    def _compute_counts(self):
        for rec in self:
            m_ids = set(rec.manifest_unit_ids.ids)
            l_ids = set(rec.loaded_unit_ids.ids)
            rec.manifest_count = len(m_ids)
            rec.loaded_count = len(l_ids)
            rec.missing_count = len(m_ids - l_ids)
            rec.extra_count = len(l_ids - m_ids)
            rec.roll_out_blocked = bool(
                (m_ids - l_ids) or (l_ids - m_ids))

    @api.depends("loaded_unit_ids",
                 "loaded_unit_ids.weight_kg",
                 "loaded_unit_ids.oversize")
    def _compute_totals(self):
        for rec in self:
            rec.total_weight_kg = sum(
                rec.loaded_unit_ids.mapped("weight_kg"))
            rec.oversize_count = len(
                rec.loaded_unit_ids.filtered("oversize"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "southbrook.truck.load") or _("TL/New")
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------
    def action_start_loading(self):
        for rec in self:
            if rec.state == "draft":
                rec.state = "loading"
                rec.message_post(body=_(
                    "Loading started by %s.") %
                    self.env.user.display_name)

    def action_load_unit(self, unit_id):
        """Mark a single unit loaded. Called from QR scan flow."""
        self.ensure_one()
        if self.state == "draft":
            self.action_start_loading()
        unit = self.env["southbrook.shipping.unit"].browse(int(unit_id))
        if not unit.exists():
            raise UserError(_("Unit id=%s not found") % unit_id)
        if unit.id in self.loaded_unit_ids.ids:
            return {"already_loaded": True,
                    "unit_name": unit.display_name,
                    "missing_count": self.missing_count,
                    "extra_count": self.extra_count}
        self.loaded_unit_ids = [(4, unit.id)]
        unit.action_mark_loaded(truck_ref=self.truck_ref)
        is_extra = unit.id not in self.manifest_unit_ids.ids
        return {
            "ok": True,
            "unit_name": unit.display_name,
            "is_extra": is_extra,
            "manifest_count": self.manifest_count,
            "loaded_count": self.loaded_count,
            "missing_count": self.missing_count,
            "extra_count": self.extra_count,
            "alert": is_extra and _("EXTRA — not on manifest!"),
        }

    def action_roll_out(self):
        for rec in self:
            if rec.roll_out_blocked:
                raise UserError(_(
                    "Cannot roll out: %(m)s missing, %(e)s extra. "
                    "Resolve manifest first.") % {
                    "m": rec.missing_count, "e": rec.extra_count})
            rec.write({
                "state": "rolled_out",
                "rolled_out_at": fields.Datetime.now(),
                "rolled_out_by": self.env.user.id,
            })
            rec.message_post(body=_(
                "Truck %(t)s rolled out by %(u)s — %(n)s units, "
                "%(w).0f kg total.") % {
                "t": rec.truck_ref or "?",
                "u": self.env.user.display_name,
                "n": rec.loaded_count,
                "w": rec.total_weight_kg or 0,
            })

    def action_return(self):
        for rec in self:
            rec.state = "returned"


class TruckLoadQrKind(models.AbstractModel):
    _name = "southbrook.qr.kind.truck"
    _inherit = "southbrook.qr.kind"
    _description = "QR Kind — Truck Load Manifest"
    _kind_name = "truck"
    _target_model = "southbrook.truck.load"

    @api.model
    def handle_action(self, record, action, params):
        if action == "load_unit":
            unit_id = (params or {}).get("unit_id")
            if not unit_id:
                from odoo.exceptions import UserError
                raise UserError(_(
                    "load_unit needs unit_id in params (the shipping "
                    "unit being scanned onto this truck)"))
            return record.action_load_unit(unit_id)
        if action == "roll_out":
            record.action_roll_out()
            return {"record_name": record.display_name,
                    "record_id": record.id, "model": self._target_model,
                    "message": _("Truck rolled out")}
        return super().handle_action(record, action, params)
