# SPDX-License-Identifier: LGPL-3.0-only
"""Buy-route helper (Phase-2 Task 5).

Assist-only: this button configures the NATIVE Odoo procurement route on
the product so the native MRP/replenishment scheduler is *permitted* to
buy the component. It does NOT create a purchase order, a purchase
requisition, or any procurement -- it only adds a route.

The native "Buy" route xml_id is grep-verified against the installed
Odoo 19 CE core (/Users/naadmin/Downloads/Official/V19C/odoo):

    addons/purchase_stock/data/purchase_stock_data.xml:
        <record id="route_warehouse0_buy" model='stock.route'>

i.e. the record lives in the `purchase_stock` module, NOT `stock` --
`stock.route_warehouse0_buy` does not exist in this core; the correct
external id is `purchase_stock.route_warehouse0_buy`. `purchase_stock`
is `auto_install: True` (depends on `stock_account` + `purchase`), and
is guaranteed present once `sb_material_mrp` is installed: `mrp` pulls
in `stock`, `purchase` pulls in `account`, `stock_account` auto-installs
from `stock`+`account`, and `purchase_stock` auto-installs from
`stock_account`+`purchase`. `raise_if_not_found=False` is kept as a
defensive guard regardless.
"""
import math

from odoo import _, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    _SB_OPEN_MO_STATES = ("confirmed", "progress", "to_close")

    def _sb_open_mo_material_demand_qty(self):
        """Rollup of material_demand_qty this template's component demands
        across currently OPEN manufacturing orders (Phase-2b Task 2) --
        scaled by each MO's own product_qty relative to its BoM's base
        qty, and expressed in this template's own UoM via the Task 1
        `_sb_demand_qty_in_uom` helper. 0.0 (never fabricated) when no
        open MO's BoM references this template as a component.

        v19 mrp "open" domain: `state not in ('done', 'cancel')` also
        matches 'draft' (not yet confirmed -- no real reservation/demand
        signal) so the tighter, explicitly-confirmed set
        ('confirmed', 'progress', 'to_close') is used instead --
        grep-verified against mrp.production's native state selection
        (draft/confirmed/progress/to_close/done/cancel).

        NOTE (architecture limitation -- see the top of the Phase-2b plan):
        this rollup feeds the orderpoint MAX only. It does NOT make the
        native scheduler's TRIGGER size-aware -- the trigger is still the
        native, size-blind product_qty on each MO's raw-material move
        (Fork-1: product_configurator_mrp writes qty=1 per component; left
        untouched)."""
        self.ensure_one()
        to_uom = self.uom_id
        productions = self.env["mrp.production"].search([
            ("state", "in", self._SB_OPEN_MO_STATES),
            ("bom_id.bom_line_ids.product_id.product_tmpl_id", "=", self.id),
        ])
        total = 0.0
        for prod in productions:
            bom = prod.bom_id
            base_qty = bom.product_qty or 1.0
            scale = prod.product_qty / base_qty
            lines = bom.bom_line_ids.filtered(
                lambda l: l.product_id.product_tmpl_id == self)
            for line in lines:
                qty, _is_exact = line._sb_demand_qty_in_uom(to_uom)
                total += qty * scale
        return total

    def action_sb_sync_orderpoint_max(self, warehouse_ids=None):
        """Find-or-create a native stock.warehouse.orderpoint per warehouse
        for this material component product, and set its MAX from the
        open-MO demand rollup. NATIVE CONFIG ASSISTED, not a bespoke
        reorder engine: this only ever writes product_max_qty (and creates
        the orderpoint row with native defaults -- trigger='auto',
        product_min_qty=0.0 -- when none exists). product_min_qty,
        trigger, and route_id are left exactly as a human configured them
        on every subsequent call.

        Skips (creates nothing) when the rollup is 0.0 -- no phantom
        orderpoints for products with no current open-MO demand signal."""
        warehouses = warehouse_ids or self.env["stock.warehouse"].search(
            [("company_id", "in", self.env.companies.ids)])
        Orderpoint = self.env["stock.warehouse.orderpoint"]
        touched = Orderpoint.browse()
        for tmpl in self:
            rollup = tmpl._sb_open_mo_material_demand_qty()
            if rollup <= 0.0:
                continue
            target_max = math.ceil(rollup)
            variant = tmpl.product_variant_id
            for wh in warehouses:
                op = Orderpoint.search([
                    ("product_id", "=", variant.id),
                    ("location_id", "=", wh.lot_stock_id.id),
                    ("company_id", "=", wh.company_id.id),
                ], limit=1)
                if op:
                    op.product_max_qty = max(target_max, op.product_min_qty)
                else:
                    op = Orderpoint.create({
                        "product_id": variant.id,
                        "location_id": wh.lot_stock_id.id,
                        "warehouse_id": wh.id,
                        "company_id": wh.company_id.id,
                        "product_max_qty": target_max,
                    })
                touched |= op
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "message": _(
                    "%s orderpoint(s) synced from open-MO demand.",
                    len(touched)),
                "sticky": False,
            },
        }

    def action_sb_set_route_buy(self):
        """Add the native Buy route to these products so the native
        scheduler can procure them (assist-only: this configures native
        procurement, it does NOT create POs). Idempotent."""
        buy = self.env.ref(
            "purchase_stock.route_warehouse0_buy", raise_if_not_found=False
        )
        if not buy:
            return False
        for tmpl in self:
            if buy.id not in tmpl.route_ids.ids:
                tmpl.route_ids = [(4, buy.id)]
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "message": _("Buy route set on %s product(s).", len(self)),
                "sticky": False,
            },
        }
