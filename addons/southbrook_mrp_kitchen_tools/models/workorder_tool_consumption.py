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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "sbk.workorder.tool.consumption") or _("New")
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
