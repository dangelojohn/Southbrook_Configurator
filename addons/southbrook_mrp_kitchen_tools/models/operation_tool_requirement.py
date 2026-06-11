# SPDX-License-Identifier: LGPL-3.0-only
"""mrp.routing.workcenter.tool.requirement — what a specific BoM operation needs.

More granular than the work-center requirement: this row says "the
'cut sides' operation on the BoM for SB-BASE-30-2DR specifically
needs a 305mm 96T melamine blade AND a 6mm compression bit". Joins
the readiness check together with the actual MO being scheduled.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class OperationToolRequirement(models.Model):
    _name = "southbrook.operation.tool.requirement"
    _description = "Operation Tool Requirement"
    _order = "operation_id, sequence, id"
    _rec_name = "display_name"

    operation_id = fields.Many2one(
        "mrp.routing.workcenter",
        string="Operation",
        required=True,
        ondelete="cascade",
        index=True,
    )
    workcenter_id = fields.Many2one(
        "mrp.workcenter",
        related="operation_id.workcenter_id",
        store=True, readonly=True,
    )
    bom_id = fields.Many2one(
        "mrp.bom",
        related="operation_id.bom_id",
        store=True, readonly=True, index=True,
    )
    sequence = fields.Integer(default=10)
    display_name = fields.Char(
        compute="_compute_display_name", store=True,
    )

    tool_category_id = fields.Many2one(
        "southbrook.tool.category", ondelete="restrict",
    )
    product_id = fields.Many2one(
        "product.product",
        domain="[('product_tmpl_id.x_southbrook_is_tool', '=', True)]",
        ondelete="restrict",
    )

    quantity = fields.Integer(default=1, required=True)
    is_mandatory = fields.Boolean(default=True)
    consume_qty_per_unit = fields.Float(
        string="Consume per Unit",
        default=0.0,
        help="For consumables — units consumed per finished BoM unit. "
             "0.0 means reusable / no consumption. Commit 5 uses this.",
    )
    notes = fields.Text()

    _sql_qty_positive = models.Constraint(
        "CHECK(quantity >= 1)",
        "Required quantity must be at least 1.",
    )

    # Listen to the required operation_id so the constraint fires on
    # create even when neither category nor product is in vals.
    @api.constrains("operation_id", "tool_category_id", "product_id")
    def _check_category_or_product(self):
        for rec in self:
            if not rec.tool_category_id and not rec.product_id:
                raise ValidationError(_(
                    "Each operation tool requirement must specify "
                    "either a tool category or a specific product."
                ))

    @api.depends("operation_id", "tool_category_id", "product_id", "quantity")
    def _compute_display_name(self):
        for rec in self:
            target = (
                rec.product_id.display_name
                or rec.tool_category_id.complete_name
                or _("(no target)")
            )
            rec.display_name = "%s × %d on %s" % (
                target, rec.quantity,
                rec.operation_id.name or _("(no operation)"),
            )
