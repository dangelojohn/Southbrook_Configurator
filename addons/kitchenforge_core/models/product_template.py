# SPDX-License-Identifier: LGPL-3.0-only
"""Auto-attach the `manufacture` route to configurator-marked templates so SO
confirm spawns confirmed MOs through procurement — closes the third Sternberg
plumbing (no Manufacturing-app side trip)."""
from odoo import api, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._kitchenforge_apply_manufacture_route()
        return records

    def write(self, vals):
        res = super().write(vals)
        if "config_ok" in vals or "type" in vals:
            self._kitchenforge_apply_manufacture_route()
        return res

    def _kitchenforge_apply_manufacture_route(self):
        """Idempotently attach mrp.route_warehouse0_manufacture to every
        config_ok template that doesn't already have it."""
        if not self:
            return
        route = self.env.ref(
            "mrp.route_warehouse0_manufacture", raise_if_not_found=False)
        if not route:
            return
        for rec in self:
            if rec.config_ok and route not in rec.route_ids:
                rec.route_ids = [(4, route.id)]
