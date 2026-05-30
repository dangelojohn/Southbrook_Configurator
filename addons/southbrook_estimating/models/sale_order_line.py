# SPDX-License-Identifier: LGPL-3.0-only
"""
sale.order.line extension — Q21 zone field.

Per Q21 locked decision (Image Floor case study NF9 confirmation):
6-value selection plus a free-text zone_label that's only visible when
zone='other'. NO separate ORM model — zone is just a field on the line.

The Order Builder view in views/sale_order_views.xml groups lines by zone
via the standard `<group expand="1" string="Zone">` pattern. The
customer-facing spec sheet (Phase 1 QWeb report, custom routine #6)
also groups by zone for the print-out.
"""
from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    zone = fields.Selection(
        selection=[
            ("base_run", "Base Run"),
            ("wall", "Wall"),
            ("tall", "Tall"),
            ("island", "Island"),
            ("accessory", "Accessory"),
            ("other", "Other"),
        ],
        string="Zone",
        default="base_run",
        help=(
            "Which kitchen zone this line belongs to. Drives the multi-zone "
            "grid in the Order Builder backend and the customer-facing "
            "spec-sheet PDF grouping. Q21 + NF9 (Richwood pattern)."
        ),
    )
    zone_label = fields.Char(
        string="Zone Label",
        help=(
            "Free-text label, visible only when zone='other'. Captures the "
            "long tail of zone names that don't fit the 5 named zones "
            "(e.g. 'Laundry', 'Mudroom', 'Bar')."
        ),
    )

    @api.onchange("zone")
    def _onchange_zone_clear_label(self):
        """Clear zone_label when leaving the 'other' zone."""
        for line in self:
            if line.zone != "other":
                line.zone_label = False

    # ------------------------------------------------------------------
    # T1C8 — Click-to-edit entry point for the OWL kitchen viewport.
    #
    # When the sales rep clicks a cabinet in the 3D Kitchen Preview
    # canvas, the OWL component raycasts the mesh to find the line id,
    # then calls this method via JSON-RPC. The returned action dict is
    # dispatched by the OWL action service — typically opening the OCA
    # configurator wizard for the line's product so the rep can
    # reconfigure the cabinet (width, family, door style, etc.).
    # ------------------------------------------------------------------
    def action_reconfigure(self):
        """Launch the OCA configurator wizard for this line.

        Returns the action dict produced by
        product.template.action_southbrook_launch_3d_configurator()
        — which itself wraps OCA's configure_product(). The wizard
        opens with the line's product pre-selected and any existing
        config_session_id reused.

        If the line has no product or no template (free-text line,
        comment, etc.), returns False so the OWL component shows a
        gentle no-op rather than crashing.
        """
        self.ensure_one()
        tmpl = (
            self.product_id.product_tmpl_id
            if self.product_id and self.product_id.product_tmpl_id
            else None
        )
        if not tmpl:
            return False
        return tmpl.action_southbrook_launch_3d_configurator()
