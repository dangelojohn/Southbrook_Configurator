# SPDX-License-Identifier: LGPL-3.0-only
"""Subscription pricing tiers — Marathon Channel / Direct / Enterprise.

The Marathon Channel tier is the partner-discounted SKU loaded for shops
arriving through the Marathon Hardware reseller relationship; it carries
`marathon_rebate_eligible=True` so the rebate ledger picks them up.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class KitchenForgeSubscriptionPlan(models.Model):
    _name = "kitchenforge.subscription.plan"
    _description = "KitchenForge Subscription Plan"
    _order = "sequence, monthly_usd"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True, index=True, copy=False,
        help="Stable machine code (e.g. 'marathon_channel', 'direct', "
             "'enterprise'). Used by Stripe + provisioner to look up the "
             "plan independently of display name.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    monthly_usd = fields.Float(
        string="Monthly (USD)", required=True,
        help="Sticker price per month for month-to-month billing.")
    annual_usd = fields.Float(
        string="Annual (USD)",
        help="Sticker price per year for annual prepay. Usually monthly*10.")
    max_seats = fields.Integer(
        string="Max Seats", default=5,
        help="Hard cap on `kitchenforge_core.group_kitchenforge_user` "
             "members for tenants on this plan. 0 means unlimited.")
    max_active_projects = fields.Integer(
        string="Max Active Projects", default=20,
        help="Hard cap on concurrent `project.project` records flagged "
             "as kitchen builds. 0 means unlimited.")
    marathon_rebate_eligible = fields.Boolean(
        string="Marathon Rebate Eligible",
        default=False,
        help="When true, tenants on this plan participate in the "
             "kitchenforge_marathon rebate ledger.")
    description = fields.Text()
    tenant_ids = fields.One2many(
        "kitchenforge.tenant", "plan_id", string="Subscribers")
    subscriber_count = fields.Integer(
        compute="_compute_subscriber_count", store=False)

    _sql_constraints = [
        ("code_uniq", "unique(code)",
         "Subscription plan code must be unique."),
    ]

    @api.depends("tenant_ids")
    def _compute_subscriber_count(self):
        for rec in self:
            rec.subscriber_count = len(rec.tenant_ids)

    @api.constrains("monthly_usd", "annual_usd")
    def _check_non_negative(self):
        for rec in self:
            if rec.monthly_usd < 0 or rec.annual_usd < 0:
                raise ValidationError(_("Plan pricing cannot be negative."))
