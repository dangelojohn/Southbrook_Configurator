# SPDX-License-Identifier: LGPL-3.0-only
"""Phase-2b Task 4 -- assist-only transparency on the native PO/RFQ line.

Both fields below are deliberately NON-STORED: they are a live snapshot of
CURRENTLY OPEN MO demand (product.template._sb_open_mo_material_demand_qty,
Task 2), which changes as MOs are confirmed/closed independently of this
PO line -- storing them would let them go stale silently. Neither field is
ever written back to product_qty, and nothing here confirms a PO (see
models/stock_rule.py, Task 5, for the one gated exception elsewhere).
"""
import math

from odoo import _, api, fields, models
from odoo.tools import float_round


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    sb_material_demand_qty = fields.Float(
        string="Open-MO Material Demand",
        compute="_compute_sb_material_suggested_note",
        digits=(12, 4),
        help="Read-only assist (Phase-2b Task 4): this line's product's "
             "rollup of material_demand_qty across currently OPEN "
             "manufacturing orders, in the material's canonical demand "
             "unit. 0.0 when the product has no resolved material or no "
             "open-MO demand. NOT the number that generated this RFQ line "
             "-- the native scheduler's trigger is still the size-blind "
             "orderpoint MIN / native BoM qty (Fork-1; see the Phase-2b "
             "plan's architecture note). This is a live, same-moment "
             "transparency snapshot, not this line's origin.",
    )
    sb_material_suggested_note = fields.Char(
        string="Material Suggestion",
        compute="_compute_sb_material_suggested_note",
        help="Assist-only, human-readable transparency note. Never writes "
             "product_qty, never confirms this PO. Empty string when the "
             "product has no resolved material or no open-MO demand -- "
             "never a fabricated suggestion.",
    )

    @api.depends("product_id", "product_uom_id", "partner_id")
    def _compute_sb_material_suggested_note(self):
        for line in self:
            line.sb_material_demand_qty = 0.0
            line.sb_material_suggested_note = ""
            tmpl = line.product_id.product_tmpl_id if line.product_id else False
            mat = tmpl.material_id if tmpl else False
            if not mat:
                continue
            demand = tmpl._sb_open_mo_material_demand_qty()
            if demand <= 0.0:
                continue
            line.sb_material_demand_qty = demand
            waste = mat._effective_waste_pct()
            gross = demand * (1.0 + waste / 100.0)
            canonical_uom = mat._sb_canonical_demand_uom()
            unit_label = canonical_uom.name if canonical_uom else _("unit(s)")
            seller = False
            if line.partner_id and line.product_id:
                seller = line.product_id._select_seller(
                    partner_id=line.partner_id,
                    uom_id=line.product_uom_id or False,
                )
            yield_qty = seller.uom_yield_qty if seller else 0.0
            po_uom_name = line.product_uom_id.name or _("unit")
            if yield_qty > 0.0:
                ratio = float_round(gross / yield_qty, precision_digits=4)
                packs = math.ceil(ratio)
                line.sb_material_suggested_note = _(
                    "Open-MO demand: %(demand).2f %(unit)s (incl. "
                    "%(waste)g%% waste) -> suggests %(packs)g %(po_uom)s "
                    "@ %(yield_qty)g %(unit)s/%(po_uom)s.",
                    demand=demand, unit=unit_label, waste=waste,
                    packs=packs, po_uom=po_uom_name, yield_qty=yield_qty,
                )
                continue
            converted, is_exact = (
                canonical_uom.sb_convert_demand_qty(gross, line.product_uom_id)
                if canonical_uom and line.product_uom_id else (gross, False)
            )
            if is_exact:
                line.sb_material_suggested_note = _(
                    "Open-MO demand: %(demand).2f %(unit)s (incl. "
                    "%(waste)g%% waste) ~= %(converted).2f %(po_uom)s "
                    "(native UoM conversion; no vendor yield recorded).",
                    demand=demand, unit=unit_label, waste=waste,
                    converted=converted, po_uom=po_uom_name,
                )
            else:
                line.sb_material_suggested_note = _(
                    "Open-MO demand: %(demand).2f %(unit)s (incl. "
                    "%(waste)g%% waste). No vendor yield recorded and no "
                    "compatible UoM conversion -- record "
                    "product.supplierinfo.uom_yield_qty for a "
                    "purchase-qty suggestion.",
                    demand=demand, unit=unit_label, waste=waste,
                )
