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
import logging
import math

from odoo import _, models
from odoo.tools import float_round

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    _SB_OPEN_MO_STATES = ("confirmed", "progress", "to_close")

    def _sb_open_mo_bom_lines_with_scale(self):
        """Yield (bom_line, scale) for every open-MO BoM line whose
        component resolves to this template, scale = that MO's own
        product_qty relative to its BoM's base qty. Shared iteration
        used by both `_sb_open_mo_material_demand_qty` (T4's canonical
        snapshot) and `_sb_open_mo_material_demand_for_orderpoint_max`
        (I-2 fix, final review 2026-07-26) so the two never drift on
        which MOs/lines count as "open demand"."""
        self.ensure_one()
        productions = self.env["mrp.production"].search([
            ("state", "in", self._SB_OPEN_MO_STATES),
            ("bom_id.bom_line_ids.product_id.product_tmpl_id", "=", self.id),
        ])
        for prod in productions:
            bom = prod.bom_id
            base_qty = bom.product_qty or 1.0
            scale = prod.product_qty / base_qty
            lines = bom.bom_line_ids.filtered(
                lambda l: l.product_id.product_tmpl_id == self)
            for line in lines:
                yield line, scale

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
        total = 0.0
        for line, scale in self._sb_open_mo_bom_lines_with_scale():
            qty, _is_exact = line._sb_demand_qty_in_uom(to_uom)
            total += qty * scale
        return total

    def _sb_open_mo_material_demand_for_orderpoint_max(self):
        """I-2 fix (final review, 2026-07-26) -- a dimension-aware rollup
        safe to CEIL and write into `stock.warehouse.orderpoint.
        product_max_qty`, unlike the plain canonical snapshot above.

        `_sb_open_mo_material_demand_qty` honestly returns the RAW
        canonical (m2/m) number, unconverted, whenever this product's own
        purchase UoM shares no dimensional reference with the material's
        canonical demand unit (the sheet-goods norm: a m2-tracked panel
        material purchased as "Sheet"/"Each"). `action_sb_sync_orderpoint_max`
        used to `ceil()` that raw number directly into `product_max_qty`
        as if it were already in purchase units -- e.g. 7.5 m2 of demand
        silently became a MAX of "8 sheets", ~2.6x over the true ~3-sheet
        ceiling at a 2.97 m2/sheet yield.

        Returns (qty, resolved):
        - resolved True: `qty` is expressed in this product's own UoM
          (self.uom_id) and is safe for the caller to CEIL into
          product_max_qty.
        - resolved False: the demand could not be honestly expressed in
          this product's UoM and MUST NOT be written -- `qty` is the raw
          canonical number (for logging only). The caller skips this
          product (leaves any existing orderpoint's MAX untouched) rather
          than fabricate a dimensionally-wrong MAX.

        Three cases (mirrors `_sb_demand_qty_in_uom` / `suggested_purchase_qty`):
        1. No material resolves at all for this component: the native
           per_unit/none demand model already counts 1:1 in this
           product's own UoM (no dimension to convert) -- always
           resolved, using the pass-through total unchanged.
        2. A material resolves AND its canonical demand UoM shares a
           common reference with self.uom_id (e.g. the product's own UoM
           genuinely is m2/ft2/m): the native conversion via
           `_sb_demand_qty_in_uom` is a real, exact conversion --
           resolved.
        3. A material resolves but shares NO common reference with
           self.uom_id (the sheet-goods norm): consult the vendor
           `product.supplierinfo.uom_yield_qty` (same signal
           `suggested_purchase_qty` uses) -- CEIL-ready
           canonical_demand / uom_yield_qty purchase units. No seller or
           no yield recorded -- unresolved, skip; never fabricate."""
        self.ensure_one()
        to_uom = self.uom_id
        variant = self.product_variant_id
        lines_with_scale = list(self._sb_open_mo_bom_lines_with_scale())
        if not lines_with_scale:
            return 0.0, True
        material = variant._resolve_material() if variant else False
        if not material:
            # Case 1 -- no material at all: no dimension mismatch is even
            # possible, the pass-through canonical number IS the count.
            total = sum(
                line._sb_demand_qty_in_uom(to_uom)[0] * scale
                for line, scale in lines_with_scale
            )
            return total, True
        canonical_uom = material._sb_canonical_demand_uom()
        is_exact = bool(
            canonical_uom and to_uom and canonical_uom._has_common_reference(to_uom)
        )
        if is_exact:
            # Case 2 -- genuine native conversion succeeds.
            total = sum(
                line._sb_demand_qty_in_uom(to_uom)[0] * scale
                for line, scale in lines_with_scale
            )
            return total, True
        # Case 3 -- material set, no common reference: canonical_total is
        # in the material's canonical unit (m2/m), never in self.uom_id.
        canonical_total = sum(
            line.material_demand_qty * scale for line, scale in lines_with_scale
        )
        seller = variant._select_seller() if variant else False
        yield_qty = seller.uom_yield_qty if seller else 0.0
        if yield_qty <= 0.0:
            return canonical_total, False
        # Same FP-safety rounding as `suggested_purchase_qty` (M-1, final
        # review 2026-07-26): guard an exact-integer ratio (e.g. 5.94/2.97)
        # against binary float drift landing a hair above the integer and
        # over-ceiling by a whole purchase unit.
        ratio = float_round(canonical_total / yield_qty, precision_digits=4)
        return ratio, True

    def action_sb_sync_orderpoints(self, warehouse_ids=None):
        """Find-or-create a native stock.warehouse.orderpoint per warehouse
        for this material component product, and set BOTH its MIN and its
        MAX from the open-MO demand rollup (size-aware trigger, Fork-1
        Task 1). NATIVE CONFIG ASSISTED, not a bespoke reorder engine:
        this writes `product_min_qty` and `product_max_qty` (and creates
        the orderpoint row with native defaults -- trigger='auto' -- when
        none exists). `trigger` and `route_id` are left exactly as a human
        configured them on every subsequent call.

        Contract (supersedes the old MAX-only contract -- `product_min_qty`
        is NO LONGER "never touched"; see
        docs/superpowers/specs/2026-07-27-sizeaware-trigger-design.md and
        docs/superpowers/plans/2026-07-27-sizeaware-trigger.md Task 1):
        - `product_min_qty` = the converted open-MO demand rollup, computed
          ONCE per product via the existing ladder (native UoM conversion
          via `_sb_demand_qty_in_uom` -> `uom_yield_qty` CEIL -> skip+log).
          This is what makes the native procurement TRIGGER size-aware --
          the native scheduler compares on-hand/virtual qty against this
          MIN, so a bigger open-MO demand now genuinely lowers the
          reorder threshold instead of only raising the MAX ceiling.
        - `product_max_qty` = the existing MAX derivation (CEIL of the
          same rollup), clamped to be `>= product_min_qty` (MIN<=MAX
          invariant) -- unchanged in spirit from the prior MAX-only sync,
          just reusing the single rollup computed above instead of a
          second call.

        Skips (creates nothing) when the rollup is 0.0 -- no phantom
        orderpoints for products with no current open-MO demand signal.

        I-2 fix (final review, 2026-07-26), now governing BOTH min and
        max: skips -- leaving any existing orderpoint's MIN/MAX untouched
        -- when the demand cannot be honestly expressed in this product's
        own UoM (no common dimensional reference and no
        product.supplierinfo.uom_yield_qty recorded). See
        `_sb_open_mo_material_demand_for_orderpoint_max`. Never fabricates
        a dimensionally-wrong MIN or MAX."""
        warehouses = warehouse_ids or self.env["stock.warehouse"].search(
            [("company_id", "in", self.env.companies.ids)])
        Orderpoint = self.env["stock.warehouse.orderpoint"]
        touched = Orderpoint.browse()
        for tmpl in self:
            rollup, resolved = tmpl._sb_open_mo_material_demand_for_orderpoint_max()
            if not resolved:
                _logger.warning(
                    "sb_material_mrp: skipping orderpoint MIN/MAX sync for "
                    "%s -- open-MO demand (%.4f canonical units) has no "
                    "common UoM reference with %s and no "
                    "product.supplierinfo.uom_yield_qty is recorded; "
                    "leaving MIN/MAX untouched rather than writing a "
                    "dimensionally-wrong number (Phase-2b I-2 fix).",
                    tmpl.display_name, rollup, tmpl.uom_id.name,
                )
                continue
            if rollup <= 0.0:
                continue
            # Single rollup drives both MIN (the raw converted demand) and
            # MAX (its CEIL, clamped >= MIN -- trivially true since
            # ceil(x) >= x, the clamp is defensive against FP edge cases).
            target_min = rollup
            target_max = max(math.ceil(rollup), target_min)
            variant = tmpl.product_variant_id
            for wh in warehouses:
                op = Orderpoint.search([
                    ("product_id", "=", variant.id),
                    ("location_id", "=", wh.lot_stock_id.id),
                    ("company_id", "=", wh.company_id.id),
                ], limit=1)
                if op:
                    op.write({
                        "product_min_qty": target_min,
                        "product_max_qty": max(target_max, target_min),
                    })
                else:
                    op = Orderpoint.create({
                        "product_id": variant.id,
                        "location_id": wh.lot_stock_id.id,
                        "warehouse_id": wh.id,
                        "company_id": wh.company_id.id,
                        "product_min_qty": target_min,
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

    def action_sb_sync_orderpoint_max(self, warehouse_ids=None):
        """Backcompat alias -- delegates to `action_sb_sync_orderpoints`,
        which now sets BOTH product_min_qty and product_max_qty (Fork-1
        Task 1). Kept under the old name for existing callers/docs/tests
        (e.g. the auto-confirm-threshold flow) that predate the min+max
        sync."""
        return self.action_sb_sync_orderpoints(warehouse_ids)

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
