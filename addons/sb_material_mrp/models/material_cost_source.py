# SPDX-License-Identifier: LGPL-3.0-only
from odoo import api, fields, models


class MaterialCostSource(models.AbstractModel):
    _name = "material.cost.source"
    _description = "Material cost-sourcing cascade resolver"

    @api.model
    def _resolve(self, product, qty):
        """Return the best available unit price for `product`, with provenance.

        Cascade order: vendor (Purchasing supplierinfo) -> manual (material
        master manual price) -> online stub. The online tier is an honest,
        flagged placeholder (Phase-5 wires real research) — never present it
        as a trusted number.
        """
        company = self.env.company

        # Tier 1 - vendor: current supplierinfo price for the requested qty.
        seller = product._select_seller(quantity=qty)
        if seller and seller.price:
            return {
                "unit_price": seller.price,
                "currency_id": (seller.currency_id or company.currency_id).id,
                "tier": "vendor",
                "provenance": "vendor · %s" % seller.partner_id.display_name,
                "dated": fields.Date.context_today(self),
            }

        # Tier 2 - manual: a manual price on the resolved material master.
        material = product._resolve_material()
        if material and material.manual_unit_price:
            return {
                "unit_price": material.manual_unit_price,
                "currency_id": company.currency_id.id,
                "tier": "manual",
                "provenance": "manual",
                "dated": fields.Date.context_today(self),
            }

        # Tier 3 - online stub (Phase-5 wires real research); flagged, zero.
        return {
            "unit_price": 0.0,
            "currency_id": company.currency_id.id,
            "tier": "online",
            "provenance": "online est. (unset)",
            "dated": False,
        }
