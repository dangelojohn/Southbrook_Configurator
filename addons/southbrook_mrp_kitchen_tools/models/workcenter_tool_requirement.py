# SPDX-License-Identifier: LGPL-3.0-only
"""mrp.workcenter.tool.requirement — what a work center NEEDS in its crib.

One row per (work_center, tool_category) saying "the saw cell needs at
least 1 of any saw_blade category at all times to be considered ready".
The readiness check in commit 4 enumerates these rows and confirms the
required count of available assets sits in the linked crib.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class WorkcenterToolRequirement(models.Model):
    _name = "southbrook.workcenter.tool.requirement"
    _description = "Work Center Tool Requirement"
    _order = "workcenter_id, sequence, id"
    _rec_name = "display_name"

    workcenter_id = fields.Many2one(
        "mrp.workcenter",
        string="Work Center",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    display_name = fields.Char(
        compute="_compute_display_name", store=True,
    )

    tool_category_id = fields.Many2one(
        "southbrook.tool.category",
        string="Tool Category",
        ondelete="restrict",
        help="Either a category (any asset of this family meets the "
             "requirement) OR a specific product (commit 3 — for now "
             "the category is sufficient).",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Specific Tool Product",
        domain="[('product_tmpl_id.x_southbrook_is_tool', '=', True)]",
        ondelete="restrict",
        help="When set, only assets of this product satisfy the "
             "requirement. Use sparingly — most requirements should "
             "key on category to allow asset substitution.",
    )

    quantity = fields.Integer(default=1, required=True)
    is_mandatory = fields.Boolean(
        default=True,
        help="When true, the readiness check BLOCKS the work order if "
             "the requirement is not met. When false, the readiness "
             "check WARNS only — operator can continue.",
    )
    notes = fields.Text()

    _sql_qty_positive = models.Constraint(
        "CHECK(quantity >= 1)",
        "Required quantity must be at least 1.",
    )

    # api.constrains on (tool_category_id, product_id) doesn't fire on
    # create when neither field is in vals, so we mirror the rule as a
    # Python check that runs on the workcenter_id field (which is
    # required and always present in vals).
    @api.constrains("workcenter_id", "tool_category_id", "product_id")
    def _check_category_or_product(self):
        for rec in self:
            if not rec.tool_category_id and not rec.product_id:
                raise ValidationError(_(
                    "Each tool requirement must specify either a tool "
                    "category or a specific product."
                ))

    @api.depends("workcenter_id", "tool_category_id", "product_id", "quantity")
    def _compute_display_name(self):
        for rec in self:
            target = (
                rec.product_id.display_name
                or rec.tool_category_id.complete_name
                or _("(no target)")
            )
            rec.display_name = "%s × %d @ %s" % (
                target, rec.quantity,
                rec.workcenter_id.display_name or _("(no workcenter)"),
            )
