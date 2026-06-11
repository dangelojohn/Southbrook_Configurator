# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.tool.asset — per-instance reusable tool record.

One record per physical reusable asset (e.g. each 305mm 96T melamine
blade, each 35mm hinge boring bit, each digital caliper). The asset
carries lifecycle, condition, life-tracking, and assignment fields
that the readiness check in commit 4 reads.

When ``maintenance.equipment`` is available (which it always is on the
Southbrook stack — Maintenance is a hard dep), we wire the asset to
its equipment record via ``equipment_id``. Major shop machines stay
on ``maintenance.equipment`` directly; this model exists for the long
tail of smaller assets — blades, bits, jigs, spray guns — that don't
warrant their own equipment record but still need lifecycle tracking.

Lifecycle vs condition split:

* ``lifecycle_state`` is operational: available / in_use / checked_out
  / needs_cleaning / needs_sharpening / needs_calibration /
  under_maintenance / broken / retired / scrapped. The readiness check
  reads this — "needs_sharpening" + a sharpening-due asset blocks the
  work order.
* ``condition`` is a quality grade: excellent / good / worn / dull /
  damaged / unsafe. QC writes here when a defect roots to a tool;
  ``condition='dull'`` flips ``lifecycle_state='needs_sharpening'``
  automatically.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .product_template import (
    ESTIMATED_LIFE_UNIT_SELECTION,
    TOOL_LIFECYCLE_SELECTION,
)


CONDITION_SELECTION = [
    ("excellent", "Excellent"),
    ("good", "Good"),
    ("worn", "Worn"),
    ("dull", "Dull"),
    ("damaged", "Damaged"),
    ("unsafe", "Unsafe"),
]

# Conditions that imply a non-available lifecycle state. Used by the
# onchange + the readiness check in commit 4.
CONDITION_BLOCKS_AVAILABILITY = {"damaged", "unsafe"}
CONDITION_REQUIRES_SHARPENING = {"dull"}


class SouthbrookToolAsset(models.Model):
    _name = "southbrook.tool.asset"
    _description = "Southbrook Tool Asset"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"
    _rec_name = "display_name"

    # ─── Identity ───────────────────────────────────────────────────
    name = fields.Char(
        string="Asset Name",
        required=True,
        copy=False,
        tracking=True,
    )
    code = fields.Char(
        string="Asset Code",
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _("New"),
    )
    display_name = fields.Char(
        compute="_compute_display_name", store=True,
    )
    barcode = fields.Char(string="Barcode", copy=False, index=True)
    qr_code = fields.Char(string="QR Code", copy=False)
    serial_number = fields.Char(string="Serial Number", copy=False)
    active = fields.Boolean(default=True)

    # ─── Linkage ────────────────────────────────────────────────────
    product_id = fields.Many2one(
        "product.product",
        string="Catalog Product",
        domain="[('product_tmpl_id.x_southbrook_is_tool', '=', True)]",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        help="The product master this asset is an instance of. The "
             "asset inherits tool_category, family, and policy flags "
             "from the product on create.",
    )
    tool_category_id = fields.Many2one(
        "southbrook.tool.category",
        string="Tool Category",
        related="product_id.product_tmpl_id.x_southbrook_tool_category_id",
        store=True,
        readonly=True,
    )
    tool_family = fields.Selection(
        related="product_id.product_tmpl_id.x_southbrook_tool_family",
        store=True,
        readonly=True,
    )
    equipment_id = fields.Many2one(
        "maintenance.equipment",
        string="Equipment Record",
        ondelete="set null",
        index=True,
        help="Optional link to a maintenance.equipment record. Most "
             "tool assets are lightweight and don't need one; "
             "expensive / serial-tracked assets (CNC tool holders, "
             "torque drivers, calibrated meters) usually do.",
    )

    # ─── Location / assignment ──────────────────────────────────────
    tool_crib_id = fields.Many2one(
        "southbrook.tool.crib",
        string="Tool Crib",
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    workcenter_id = fields.Many2one(
        "mrp.workcenter",
        string="Default Work Center",
        ondelete="set null",
        index=True,
        tracking=True,
    )
    location_id = fields.Many2one(
        "stock.location",
        string="Stock Location",
        domain="[('usage', '=', 'internal')]",
    )
    assigned_employee_id = fields.Many2one(
        "hr.employee",
        string="Assigned Employee",
        ondelete="set null",
        tracking=True,
    )
    current_holder_id = fields.Many2one(
        "res.users",
        string="Current Holder",
        ondelete="set null",
        tracking=True,
        help="User who currently holds the asset — set on checkout, "
             "cleared on return (commit 4).",
    )

    # ─── Purchase + warranty ────────────────────────────────────────
    vendor_id = fields.Many2one(
        "res.partner",
        string="Vendor",
        domain="[('supplier_rank', '>', 0)]",
    )
    purchase_date = fields.Date(string="Purchase Date")
    purchase_cost = fields.Float(string="Purchase Cost")
    warranty_expiration_date = fields.Date(string="Warranty Expires")

    # ─── Lifecycle + condition ──────────────────────────────────────
    lifecycle_state = fields.Selection(
        TOOL_LIFECYCLE_SELECTION,
        string="Lifecycle State",
        default="available",
        required=True,
        index=True,
        tracking=True,
    )
    condition = fields.Selection(
        CONDITION_SELECTION,
        string="Condition",
        default="good",
        required=True,
        tracking=True,
    )
    is_available = fields.Boolean(
        compute="_compute_is_available",
        store=True,
        help="True when lifecycle_state is one of the ready-to-use "
             "values AND condition is not damaged / unsafe.",
    )

    # ─── Life tracking ──────────────────────────────────────────────
    remaining_life_qty = fields.Float(string="Remaining Life Qty")
    estimated_life_qty = fields.Float(string="Estimated Life Qty")
    life_unit = fields.Selection(
        ESTIMATED_LIFE_UNIT_SELECTION,
        string="Life Unit",
    )
    total_usage_qty = fields.Float(
        string="Total Usage Qty",
        default=0.0,
        readonly=True,
    )
    last_used_date = fields.Datetime(string="Last Used")
    last_used_workorder_id = fields.Many2one(
        "mrp.workorder",
        string="Last Used Work Order",
        readonly=True,
    )

    # ─── Maintenance dates ──────────────────────────────────────────
    last_sharpened_date = fields.Date(string="Last Sharpened")
    next_sharpening_due_date = fields.Date(string="Next Sharpening Due")
    last_calibrated_date = fields.Date(string="Last Calibrated")
    next_calibration_due_date = fields.Date(string="Next Calibration Due")
    last_inspected_date = fields.Date(string="Last Inspected")
    next_inspection_due_date = fields.Date(string="Next Inspection Due")
    last_cleaned_date = fields.Date(string="Last Cleaned")

    # ─── Notes ──────────────────────────────────────────────────────
    notes = fields.Text(string="Notes")
    safety_notes = fields.Text(string="Safety Notes")

    # ──────────────────────────────────────────────────────────────────
    # Constraints
    # ──────────────────────────────────────────────────────────────────
    _sql_code_unique = models.Constraint(
        "UNIQUE(code)",
        "Tool asset code must be unique.",
    )
    _sql_serial_unique_when_set = models.Constraint(
        "UNIQUE(serial_number)",
        "Serial number must be unique across tool assets.",
    )

    @api.constrains("product_id")
    def _check_product_is_tool(self):
        for rec in self:
            tmpl = rec.product_id.product_tmpl_id
            if not tmpl.x_southbrook_is_tool:
                raise ValidationError(_(
                    "Product %s is not flagged as a Southbrook tool. "
                    "Tick 'Is Southbrook Tool / Consumable' on the "
                    "product first."
                ) % rec.product_id.display_name)

    # ──────────────────────────────────────────────────────────────────
    # Compute
    # ──────────────────────────────────────────────────────────────────
    @api.depends("name", "code", "product_id.display_name")
    def _compute_display_name(self):
        for rec in self:
            parts = []
            if rec.code and rec.code != _("New"):
                parts.append(f"[{rec.code}]")
            parts.append(rec.name or rec.product_id.display_name or "")
            rec.display_name = " ".join(parts).strip()

    @api.depends("lifecycle_state", "condition")
    def _compute_is_available(self):
        ready_states = {"available", "new"}
        for rec in self:
            rec.is_available = (
                rec.lifecycle_state in ready_states
                and rec.condition not in CONDITION_BLOCKS_AVAILABILITY
            )

    # ──────────────────────────────────────────────────────────────────
    # CRUD
    # ──────────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", _("New")) == _("New"):
                vals["code"] = self.env["ir.sequence"].next_by_code(
                    "sbk.tool.asset") or _("New")
        return super().create(vals_list)

    # ──────────────────────────────────────────────────────────────────
    # Onchange — keep lifecycle + condition in sync
    # ──────────────────────────────────────────────────────────────────
    @api.onchange("condition")
    def _onchange_condition_blocks_availability(self):
        """Damaged / unsafe asset → cannot be 'available'.
        Dull asset → 'needs_sharpening' (operator can override).
        """
        for rec in self:
            if rec.condition in CONDITION_BLOCKS_AVAILABILITY \
                    and rec.lifecycle_state in ("available", "new"):
                rec.lifecycle_state = "broken"
            elif rec.condition in CONDITION_REQUIRES_SHARPENING \
                    and rec.lifecycle_state == "available":
                rec.lifecycle_state = "needs_sharpening"

    @api.onchange("product_id")
    def _onchange_product_seeds_defaults(self):
        for rec in self:
            tmpl = rec.product_id.product_tmpl_id
            if not tmpl:
                continue
            # Suggest a default name from the product if blank.
            if not rec.name and tmpl.name:
                rec.name = tmpl.name
            # Inherit estimated life from the product master.
            if not rec.estimated_life_qty and tmpl.x_southbrook_estimated_life_qty:
                rec.estimated_life_qty = tmpl.x_southbrook_estimated_life_qty
                rec.remaining_life_qty = tmpl.x_southbrook_estimated_life_qty
            if not rec.life_unit and tmpl.x_southbrook_estimated_life_unit:
                rec.life_unit = tmpl.x_southbrook_estimated_life_unit

    # ──────────────────────────────────────────────────────────────────
    # State-machine helpers (commits 4-5 call these)
    # ──────────────────────────────────────────────────────────────────
    def action_mark_in_use(self):
        for rec in self:
            rec.lifecycle_state = "in_use"
            rec.last_used_date = fields.Datetime.now()

    def action_mark_available(self):
        for rec in self:
            rec.lifecycle_state = "available"

    def action_mark_needs_sharpening(self):
        for rec in self:
            rec.lifecycle_state = "needs_sharpening"

    def action_mark_needs_calibration(self):
        for rec in self:
            rec.lifecycle_state = "needs_calibration"

    def action_mark_needs_cleaning(self):
        for rec in self:
            rec.lifecycle_state = "needs_cleaning"

    def action_mark_under_maintenance(self):
        for rec in self:
            rec.lifecycle_state = "under_maintenance"

    def action_mark_broken(self):
        for rec in self:
            rec.lifecycle_state = "broken"
            rec.condition = "damaged"

    def action_retire(self):
        for rec in self:
            rec.lifecycle_state = "retired"
            rec.active = False

    def action_scrap(self):
        for rec in self:
            rec.lifecycle_state = "scrapped"
            rec.active = False
