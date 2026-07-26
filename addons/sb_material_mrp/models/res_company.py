# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    sb_material_po_auto_confirm = fields.Boolean(
        string="Auto-Confirm Material RFQs Below Threshold",
        default=False,
        help="Fork-3 (Materials Phase-2 spec, delivered Phase-2b Task 5): "
             "when a draft RFQ the native scheduler generates for a "
             "material component's Buy route + orderpoint is at or under "
             "the amount threshold below, confirm it automatically. "
             "DEFAULT OFF. This is the ONLY place in the Southbrook "
             "Materials modules that calls purchase.order.button_confirm() "
             "-- everywhere else the suggestion is assist-only.",
    )
    sb_material_po_auto_confirm_max_amount = fields.Monetary(
        string="Auto-Confirm Max Amount",
        currency_field="currency_id",
        default=0.0,
        help="Double-gated with the toggle above: a PO auto-confirms only "
             "when the toggle is on AND its amount_total is <= this AND "
             "this is > 0. Leaving this at 0.0 keeps auto-confirm inert "
             "even if the toggle is accidentally left on.",
    )
