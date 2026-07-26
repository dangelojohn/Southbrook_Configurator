# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    sb_material_po_auto_confirm = fields.Boolean(
        related="company_id.sb_material_po_auto_confirm", readonly=False)
    sb_material_po_auto_confirm_max_amount = fields.Monetary(
        related="company_id.sb_material_po_auto_confirm_max_amount",
        readonly=False, currency_field="currency_id")
