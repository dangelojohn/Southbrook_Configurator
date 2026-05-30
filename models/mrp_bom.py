# SPDX-License-Identifier: LGPL-3.0-only
"""
mrp.bom extension — partial in commit 5: the lead_time_extra rollup only.

The full custom routine #1 (_compute_panel_dimensions) lands in commit 8.
This commit ships only the lead-time-bump roll-up so maple-box orders pick
up their +2 weeks at BoM creation time per Mapping section 3.5 / Q3.

NF11 reminder: lead_time_extra lives on product.attribute.value (master),
not on product.template.attribute.value (variant). The rollup walks
sale.order.line -> product.product -> product.template.attribute.value
-> product_attribute_value_id -> lead_time_extra on the master.
"""
from odoo import api, fields, models


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    southbrook_lead_time_extra = fields.Float(
        string="Southbrook Lead-Time Extra (days)",
        compute="_compute_southbrook_lead_time_extra",
        store=True,
        help=(
            "Sum of lead_time_extra across all attribute values selected "
            "on the BoM's variant. Added to produce_delay at MO creation. "
            "Maple box contributes +14 days per Mapping section 3.5."
        ),
    )

    @api.depends(
        "product_id",
        "product_id.product_template_attribute_value_ids."
        "product_attribute_value_id.lead_time_extra",
    )
    def _compute_southbrook_lead_time_extra(self):
        for bom in self:
            if not bom.product_id:
                bom.southbrook_lead_time_extra = 0.0
                continue
            extras = bom.product_id.product_template_attribute_value_ids.mapped(
                "product_attribute_value_id.lead_time_extra"
            )
            bom.southbrook_lead_time_extra = sum(extras or [0.0])

    # ------------------------------------------------------------------
    # produce_delay roll-up
    # ------------------------------------------------------------------
    # The base mrp.bom carries produce_delay on the product, not directly
    # on the BoM. We expose an effective_produce_delay that callers can read
    # to get base + southbrook bump in one. Commit 8 wires this into the MO
    # creation path.
    effective_produce_delay = fields.Float(
        string="Effective Produce Delay (days)",
        compute="_compute_effective_produce_delay",
        store=True,
    )

    @api.depends(
        "product_id.produce_delay",
        "southbrook_lead_time_extra",
    )
    def _compute_effective_produce_delay(self):
        for bom in self:
            base = bom.product_id.produce_delay if bom.product_id else 0.0
            bom.effective_produce_delay = base + bom.southbrook_lead_time_extra
