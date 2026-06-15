# SPDX-License-Identifier: LGPL-3.0-only
"""White-label branding on res.company.

A single Odoo instance can host a branded surface per tenant by reading
the active company's brand fields at render time (logo, primary +
secondary colour). The `kitchenforge_tenant_id` link gives the company
back-reference to its tenant for control-plane reports.
"""
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    kitchenforge_tenant_id = fields.Many2one(
        "kitchenforge.tenant",
        string="KitchenForge Tenant",
        ondelete="set null",
        help="The control-plane tenant record this company maps to. "
             "Drives white-label branding and billing rollup.")
    kitchenforge_brand_logo = fields.Binary(
        string="Brand Logo",
        help="Override logo shown on the cabinet-shop's customer-facing "
             "configurator + portal. Falls back to the standard company "
             "logo when unset.")
    kitchenforge_brand_primary_color = fields.Char(
        string="Brand Primary Color",
        default="#1f6feb",
        help="Hex colour (e.g. '#1f6feb') used for primary CTAs on the "
             "tenant's customer-facing surface.")
    kitchenforge_brand_secondary_color = fields.Char(
        string="Brand Secondary Color",
        default="#0d1117",
        help="Hex colour used for headers + accent UI on the tenant's "
             "customer-facing surface.")
