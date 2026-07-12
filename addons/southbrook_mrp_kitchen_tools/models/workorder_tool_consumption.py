# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.workorder.tool.consumption — record one tool/consumable use against a workorder.

Reusable asset usage: one row per (workorder, asset) showing how much
life was consumed (e.g. cuts, holes, minutes). Reduces remaining_life_qty
and bumps total_usage_qty on the asset.

Consumable product usage: one row per (workorder, product) showing the
quantity consumed. Adjacent to (or merged with) the existing mrp move
for the consumable — the consumption row is the asset-side mirror.

The MO/cost rollup in commit 6 reads from this table to allocate tool
cost and consumable cost to the manufacturing order.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class WorkorderToolConsumption(models.Model):
    _name = "southbrook.workorder.tool.consumption"
    _description = "Work Order Tool Consumption"
    _order = "create_date desc, id desc"

    name = fields.Char(
        string="Reference", required=True, copy=False, readonly=True,
        default=lambda self: _("New"),
    )
    workorder_id = fields.Many2one(
        "mrp.workorder",
        string="Work Order",
        required=True, ondelete="cascade", index=True,
    )
    production_id = fields.Many2one(
        "mrp.production",
        related="workorder_id.production_id",
        store=True, readonly=True,
    )
    workcenter_id = fields.Many2one(
        "mrp.workcenter",
        related="workorder_id.workcenter_id",
        store=True, readonly=True,
    )
    asset_id = fields.Many2one(
        "southbrook.tool.asset",
        string="Reusable Asset",
        ondelete="restrict",
        index=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Consumable Product",
        domain="[('product_tmpl_id.x_southbrook_is_tool', '=', True)]",
        ondelete="restrict",
    )
    quantity = fields.Float(string="Quantity Consumed", default=0.0)
    unit_cost = fields.Float(string="Unit Cost", default=0.0)
    total_cost = fields.Float(
        string="Total Cost",
        compute="_compute_total_cost", store=True,
    )
    employee_id = fields.Many2one(
        "hr.employee",
        string="Operator",
        ondelete="set null",
    )
    notes = fields.Text()

    @api.depends("quantity", "unit_cost")
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = rec.quantity * rec.unit_cost

    @api.constrains("quantity", "unit_cost")
    def _check_nonnegative(self):
        # A NEGATIVE quantity was the real integrity hole: it flowed into
        # _apply_to_asset_life as `remaining_life - quantity` (INCREASING
        # remaining life → silently "un-wearing" a dull blade back over its
        # threshold) and `total_usage + quantity` (decreasing usage), and
        # produced a negative total_cost that reduced the MO's rolled-up cost.
        for rec in self:
            if rec.quantity < 0:
                raise ValidationError(_(
                    "Quantity consumed cannot be negative."))
            if rec.unit_cost < 0:
                raise ValidationError(_("Unit cost cannot be negative."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "sbk.workorder.tool.consumption") or _("New")
            # Source unit_cost from the consumable's cost when the caller
            # didn't supply one, rather than defaulting to 0.0 (which zeroed
            # the MO cost rollup). Explicit non-zero values are preserved.
            if not vals.get("unit_cost") and vals.get("product_id"):
                product = self.env["product.product"].browse(
                    vals["product_id"])
                vals["unit_cost"] = product.standard_price or 0.0
        recs = super().create(vals_list)
        recs._apply_to_asset_life()
        return recs

    def _apply_to_asset_life(self):
        """When a reusable-asset row is created, reduce remaining_life
        and bump total_usage; auto-flip the asset to needs_sharpening
        when remaining_life crosses zero."""
        for rec in self:
            if not rec.asset_id or not rec.quantity:
                continue
            asset = rec.asset_id
            asset.total_usage_qty = (asset.total_usage_qty or 0.0) + rec.quantity
            if asset.remaining_life_qty:
                new_remaining = asset.remaining_life_qty - rec.quantity
                asset.remaining_life_qty = max(0.0, new_remaining)
                if new_remaining <= 0:
                    if asset.lifecycle_state == "in_use":
                        asset.lifecycle_state = "needs_sharpening"
            asset.last_used_date = fields.Datetime.now()
            asset.last_used_workorder_id = rec.workorder_id.id

    def unlink(self):
        """Inverse of ``_apply_to_asset_life`` — when a consumption row
        is deleted, restore the life and usage it took from the asset.

        Surfaced by the P8 rollback 2026-06-18: ``create()`` decrements
        ``remaining_life_qty`` and bumps ``total_usage_qty`` but
        ``unlink()`` left them where they were, so deleting a consumption
        row left the asset permanently depleted. Any test scan, mistaken
        debit, or manual cleanup of consumption ledger entries silently
        burned real asset life.

        Inverse semantics:

        * ``total_usage_qty`` — genuine inverse, clamped at 0.
        * ``remaining_life_qty`` — add back the quantity, clamped at
          ``estimated_life_qty`` if known (else uncapped).
        * ``lifecycle_state`` — **deliberately untouched.** Flipping
          back from ``needs_sharpening`` to ``in_use`` would mask
          legitimate state transitions (e.g. asset was sharpened
          between create and unlink). Operators set lifecycle state
          explicitly; this method only reverses what create() did
          numerically.
        * ``last_used_workorder_id`` / ``last_used_date`` — if the
          deleted row was the asset's most-recent consumption (i.e. the
          field points at that row's WO), fall back to the next-most-
          recent remaining consumption; clear when none remain.
        """
        # Snapshot the inverse-relevant state BEFORE super().unlink()
        # removes the records — fields become unreadable after delete.
        snapshots = [
            {
                "consumption_id": rec.id,
                "asset_id": rec.asset_id.id if rec.asset_id else False,
                "workorder_id": rec.workorder_id.id if rec.workorder_id else False,
                "quantity": rec.quantity or 0.0,
            }
            for rec in self
        ]
        res = super().unlink()
        Asset = self.env["southbrook.tool.asset"]
        for snap in snapshots:
            if not snap["asset_id"] or not snap["quantity"]:
                continue
            asset = Asset.browse(snap["asset_id"]).exists()
            if not asset:
                continue
            # Inverse 1: total_usage_qty
            asset.total_usage_qty = max(
                0.0, (asset.total_usage_qty or 0.0) - snap["quantity"])
            # Inverse 2: remaining_life_qty (clamp at estimated_life_qty
            # if set, else uncapped — restoring beyond original is
            # safer than leaving the asset under-credited).
            new_remaining = (asset.remaining_life_qty or 0.0) + snap["quantity"]
            if asset.estimated_life_qty:
                new_remaining = min(new_remaining, asset.estimated_life_qty)
            asset.remaining_life_qty = new_remaining
            # Inverse 3: last_used_workorder_id / last_used_date — only
            # touch when this consumption row was the most-recent.
            if (asset.last_used_workorder_id
                    and asset.last_used_workorder_id.id == snap["workorder_id"]):
                next_recent = self.search(
                    [("asset_id", "=", asset.id)],
                    order="create_date desc, id desc", limit=1,
                )
                if next_recent:
                    asset.last_used_workorder_id = next_recent.workorder_id.id
                    asset.last_used_date = next_recent.create_date
                else:
                    asset.last_used_workorder_id = False
                    asset.last_used_date = False
        return res
