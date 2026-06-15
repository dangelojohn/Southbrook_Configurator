# SPDX-License-Identifier: LGPL-3.0-only
from odoo import api, fields, models


class MarathonChannelConfig(models.Model):
    """Per-tenant Marathon channel config. Singleton on the database.

    Holds: branding flag, rebate rate, telemetry webhook URL, default
    Marathon partner reference. Lets a shop turn the Marathon
    integration on/off without code change.
    """

    _name = "kitchenforge.marathon.channel.config"
    _description = "KitchenForge Marathon Channel Config"
    _rec_name = "display_name"

    active = fields.Boolean(default=True)
    enabled = fields.Boolean(
        string="Marathon Channel Enabled",
        default=True,
        help="Master switch. When off, Marathon SKUs lose their default-bias, "
             "telemetry stops, and auto-RFQ is suppressed.")
    branded = fields.Boolean(
        string="Co-Branded Mode",
        default=False,
        help="When true, the agent surface and dealer portal display "
             "'KitchenForge powered by Marathon' branding.")
    rebate_per_cabinet_usd = fields.Float(
        string="Rebate / cabinet (USD)",
        default=8.0,
        help="Amount Marathon credits per Marathon-spec'd cabinet on a "
             "confirmed sale order. Reconciled monthly via rebate ledger.")
    telemetry_webhook_url = fields.Char(
        string="Telemetry Webhook URL",
        help="POST URL on Marathon's side that receives spec.event payloads "
             "in near-real-time. Optional — events persist locally regardless.")
    marathon_partner_id = fields.Many2one(
        "res.partner",
        string="Marathon Partner",
        help="Vendor partner used as the destination for auto-RFQs. "
             "Defaults to the seeded Marathon Hardware partner record.")
    minimum_rfq_amount = fields.Float(
        string="Min RFQ Amount",
        default=0.0,
        help="Skip auto-RFQ generation below this amount (avoid noise on "
             "single-knob orders).")
    display_name = fields.Char(compute="_compute_display_name", store=True)

    @api.depends("enabled", "branded")
    def _compute_display_name(self):
        for rec in self:
            parts = ["Marathon Channel"]
            if rec.enabled:
                parts.append("(on)")
            else:
                parts.append("(off)")
            if rec.branded:
                parts.append("• co-branded")
            rec.display_name = " ".join(parts)

    @api.model
    def get_active(self):
        """Return the singleton config row, creating it if missing."""
        cfg = self.search([("active", "=", True)], limit=1)
        if not cfg:
            partner = self.env.ref(
                "southbrook_hardware_catalog.partner_marathon_hardware",
                raise_if_not_found=False)
            cfg = self.create({
                "marathon_partner_id": partner.id if partner else False,
            })
        return cfg
