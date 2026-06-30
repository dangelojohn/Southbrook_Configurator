# SPDX-License-Identifier: LGPL-3.0-only
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SouthbrookCmmsLandedCostTemplate(models.Model):
    _name = "southbrook.cmms.landed_cost_template"
    _description = "CMMS Landed Cost Template"
    _order = "name"

    name = fields.Char(string="Name", required=True)
    freight_pct = fields.Float(string="Freight %", default=0.0)
    customs_pct = fields.Float(string="Customs %", default=0.0)
    duty_pct = fields.Float(string="Duty %", default=0.0)
    handling_pct = fields.Float(string="Handling %", default=0.0)
    default_for_vendor_ids = fields.Many2many(
        "res.partner",
        relation="southbrook_cmms_lc_template_vendor_rel",
        column1="template_id",
        column2="partner_id",
        string="Default for Vendors",
    )

    def _acquisition_value(self, picking):
        """Sum standard_price * quantity_done (or qty) across the picking's moves."""
        total = 0.0
        for move in picking.move_ids:
            qty = 0.0
            if "quantity_done" in move._fields:
                qty = move.quantity_done or 0.0
            if not qty and "quantity" in move._fields:
                qty = move.quantity or 0.0
            if not qty:
                qty = move.product_uom_qty or 0.0
            price = move.product_id.standard_price or 0.0
            total += price * qty
        return total

    def apply_to_picking(self, picking):
        self.ensure_one()
        if not picking:
            raise UserError(_("A picking must be supplied to apply a landed cost template."))
        LandedCost = self.env.get("stock.landed.cost")
        if LandedCost is None:
            raise UserError(_(
                "stock_landed_costs is not installed; cannot apply landed cost templates."))
        acquisition = self._acquisition_value(picking)
        # Locate an expense account named "Landed Cost" if present; else leave blank.
        account = self.env["account.account"].search(
            [("name", "ilike", "Landed Cost")], limit=1)
        cost_lines = []
        for pct_field, label in (
            ("freight_pct", "Freight"),
            ("customs_pct", "Customs"),
            ("duty_pct", "Duty"),
            ("handling_pct", "Handling"),
        ):
            pct = getattr(self, pct_field) or 0.0
            if not pct:
                continue
            amount = round(acquisition * (pct / 100.0), 2)
            line = {
                "name": "%s (%.2f%%)" % (label, pct),
                "price_unit": amount,
                "split_method": "by_quantity",
            }
            if account:
                line["account_id"] = account.id
            cost_lines.append((0, 0, line))
        try:
            return LandedCost.create({
                "picking_ids": [(6, 0, [picking.id])],
                "cost_lines": cost_lines,
            })
        except Exception as exc:  # noqa: BLE001
            raise UserError(_(
                "Failed to create landed cost from template '%(name)s': %(err)s",
                name=self.name, err=str(exc)))
