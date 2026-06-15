# SPDX-License-Identifier: LGPL-3.0-only
"""SO confirm hook: credit the Marathon rebate + draft the auto-RFQ."""
import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    kitchenforge_marathon_rebate_id = fields.Many2one(
        "kitchenforge.marathon.rebate",
        string="Marathon Rebate",
        readonly=True, copy=False)
    kitchenforge_marathon_rfq_id = fields.Many2one(
        "purchase.order",
        string="Marathon Auto-RFQ",
        readonly=True, copy=False)

    def _action_confirm(self):
        res = super()._action_confirm()
        for so in self:
            try:
                so._kitchenforge_marathon_credit_rebate()
                so._kitchenforge_marathon_draft_rfq()
            except Exception as exc:
                # Channel hooks are advisory — never block SO confirm.
                _logger.warning(
                    "marathon hooks failed for %s: %s", so.name, exc)
        return res

    def _kitchenforge_marathon_credit_rebate(self):
        self.ensure_one()
        Rebate = self.env["kitchenforge.marathon.rebate"]
        rec = Rebate.credit_for_sale(self)
        if rec:
            self.kitchenforge_marathon_rebate_id = rec.id

    def _kitchenforge_marathon_draft_rfq(self):
        """Create a draft purchase.order to Marathon carrying the Marathon
        SKUs resolved during the build (via hardware catalog resolve())."""
        self.ensure_one()
        cfg = self.env["kitchenforge.marathon.channel.config"].sudo().get_active()
        if not cfg.enabled or not cfg.marathon_partner_id:
            return False

        # Walk this SO's lines, ask the hardware catalog to resolve each
        # configured cabinet's hardware, and collect the Marathon-branded
        # results into a single PO.
        Catalog = self.env["southbrook.hardware.catalog"].sudo()
        Brand = self.env["southbrook.hardware.brand"].sudo()
        marathon = Brand.search([("name", "ilike", "marathon")], limit=1)
        if not marathon:
            return False

        # Aggregate: {product.product: qty}
        # NOTE: brand field is `x_hardware_brand_id` (stored-related from
        # product.template) per southbrook_hardware_catalog/models/product_product.py.
        agg = {}
        for line in self.order_line:
            if not line.product_id.product_tmpl_id.config_ok:
                continue
            attrs = self._kitchenforge_marathon_line_attrs(line)
            try:
                resolved = Catalog.resolve(**attrs)
            except Exception as exc:
                _logger.warning("resolve() failed for line %s: %s", line.id, exc)
                continue
            for product, qty in resolved:
                # Filter Marathon-branded only — non-Marathon SKUs are sourced
                # via the shop's normal vendor mix.
                brand = getattr(product, "x_hardware_brand_id", False)
                brand_id = brand.id if hasattr(brand, "id") else brand
                if brand_id != marathon.id:
                    continue
                agg[product] = agg.get(product, 0.0) + (qty * line.product_uom_qty)

        if not agg or sum(p.list_price * q for p, q in agg.items()) < cfg.minimum_rfq_amount:
            return False

        PO = self.env["purchase.order"]
        po = PO.sudo().create({
            "partner_id": cfg.marathon_partner_id.id,
            "origin": self.name,
            "order_line": [(0, 0, {
                "product_id": p.id,
                "name": p.display_name,
                "product_qty": q,
                "product_uom": p.uom_id.id if p.uom_id else False,
                "date_planned": fields.Datetime.now(),
                "price_unit": p.standard_price or p.list_price or 0.0,
            }) for p, q in agg.items()],
        })
        self.kitchenforge_marathon_rfq_id = po.id
        po.message_post(body=_(
            "Auto-RFQ drafted from KitchenForge SO %s. "
            "Confirm to release to Marathon.") % self.name)
        return po

    def _kitchenforge_marathon_line_attrs(self, line):
        """Translate a sale.order.line back into Catalog.resolve() kwargs.

        v0.1 PLACEHOLDER: returns conservative defaults (1 door, 0 drawers,
        1 shelf, soft-close on). The real impl walks
        `line.product_id.product_template_attribute_value_ids` and maps each
        attribute to the corresponding resolve() kwarg — see
        southbrook_estimating's `data/attributes.xml` for the 11-attribute
        schema (family, width, series, box_material, door_style, finish,
        hinge_side, finished_sides, gables, handle, accessories). Until that
        lands, the RFQ will be hardware-quantity-correct for door-bearing
        cabinets but conservative for drawer banks and pantries.
        """
        product = line.product_id
        return {
            "cabinet_family": product.product_tmpl_id.name[:32],
            "door_count": 1,
            "drawer_count": 0,
            "shelf_count": 1,
            "soft_close": True,
            "pull_finish": None,
            "pull_size_mm": 128,
            "handle_style": "pull",
            "mount_appliance": False,
        }
