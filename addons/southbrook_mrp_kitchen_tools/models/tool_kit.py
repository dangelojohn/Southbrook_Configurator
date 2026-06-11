# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.tool.kit — named set of tools issued together.

E.g. "Door Hardware Kit" — torque driver + hinge jig + 35mm bit set.
"Trim Carpentry Kit" — speed square + tape + brad nailer + safety
glasses. Useful for tool-checkout in commit 4 and for the
work-order kanban "assemble kit" action in commit 6.
"""
from odoo import _, api, fields, models


class SouthbrookToolKit(models.Model):
    _name = "southbrook.tool.kit"
    _description = "Southbrook Tool Kit"
    _order = "code, name"
    _rec_name = "display_name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    display_name = fields.Char(
        compute="_compute_display_name", store=True,
    )
    active = fields.Boolean(default=True)
    notes = fields.Text()

    workcenter_id = fields.Many2one(
        "mrp.workcenter",
        string="Default Work Center",
        ondelete="set null",
    )
    tool_crib_id = fields.Many2one(
        "southbrook.tool.crib",
        string="Default Crib",
        ondelete="set null",
    )

    line_ids = fields.One2many(
        "southbrook.tool.kit.line",
        "kit_id",
        string="Kit Components",
    )
    line_count = fields.Integer(
        compute="_compute_line_count", string="# Components",
    )

    _sql_code_unique = models.Constraint(
        "UNIQUE(code)",
        "Tool kit code must be unique.",
    )

    @api.depends("name", "code")
    def _compute_display_name(self):
        for rec in self:
            if rec.code and rec.name:
                rec.display_name = f"[{rec.code}] {rec.name}"
            else:
                rec.display_name = rec.name or rec.code or ""

    @api.depends("line_ids")
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)


class SouthbrookToolKitLine(models.Model):
    _name = "southbrook.tool.kit.line"
    _description = "Tool Kit Component"
    _order = "kit_id, sequence, id"

    kit_id = fields.Many2one(
        "southbrook.tool.kit",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)

    tool_category_id = fields.Many2one(
        "southbrook.tool.category", ondelete="restrict",
    )
    product_id = fields.Many2one(
        "product.product",
        domain="[('product_tmpl_id.x_southbrook_is_tool', '=', True)]",
        ondelete="restrict",
    )
    quantity = fields.Integer(default=1, required=True)
    notes = fields.Char()

    _sql_qty_positive = models.Constraint(
        "CHECK(quantity >= 1)",
        "Component quantity must be at least 1.",
    )
