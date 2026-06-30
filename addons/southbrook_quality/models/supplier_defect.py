# SPDX-License-Identifier: LGPL-3.0-only
"""Supplier defect record.

Tracks a defect against a vendor (purchase order or receipt), with cost
impact and an action to alert the buyer of the related PO.
"""

from odoo import _, api, fields, models


class SouthbrookSupplierDefect(models.Model):
    _name = "southbrook.quality.supplier_defect"
    _description = "Southbrook Supplier Defect"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(
        string="Reference",
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _("New"),
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Vendor",
        required=True,
        domain=[("is_company", "=", True)],
        tracking=True,
    )
    product_id = fields.Many2one("product.product", string="Product")
    purchase_order_id = fields.Many2one("purchase.order", string="Purchase Order")
    quantity_defective = fields.Float(string="Qty Defective", required=True)
    quantity_received = fields.Float(string="Qty Received", required=True)
    defect_rate = fields.Float(
        string="Defect Rate",
        compute="_compute_defect_rate",
        store=True,
        digits=(12, 6),
    )
    defect_type = fields.Selection(
        [
            ("dimension", "Dimensional"),
            ("surface", "Surface Defect"),
            ("hardware", "Hardware"),
            ("finish", "Finish"),
            ("assembly", "Assembly"),
            ("material", "Material"),
            ("other", "Other"),
        ],
        required=True,
        default="other",
    )
    description = fields.Text(string="Description")
    cost_impact = fields.Monetary(
        string="Cost Impact",
        currency_field="currency_id",
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                seq = self.env["ir.sequence"].next_by_code(
                    "southbrook.quality.supplier_defect"
                )
                vals["name"] = seq or _("New")
        return super().create(vals_list)

    @api.depends("quantity_defective", "quantity_received")
    def _compute_defect_rate(self):
        for rec in self:
            if rec.quantity_received:
                rec.defect_rate = rec.quantity_defective / rec.quantity_received
            else:
                rec.defect_rate = 0.0

    def action_alert_buyer(self):
        """Post a chatter message addressed to the PO buyer (or the vendor
        contact if no PO is linked)."""
        for rec in self:
            recipient = (
                rec.purchase_order_id.user_id
                if rec.purchase_order_id and rec.purchase_order_id.user_id
                else self.env.user
            )
            body = _(
                "Supplier defect %(name)s logged against %(vendor)s "
                "(rate %(rate).2f%%). Please review.",
                name=rec.name,
                vendor=rec.partner_id.display_name,
                rate=rec.defect_rate * 100.0,
            )
            partner_ids = [recipient.partner_id.id] if recipient.partner_id else []
            rec.message_post(
                body=body,
                partner_ids=partner_ids,
                subtype_xmlid="mail.mt_comment",
            )
        return True
