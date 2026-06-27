# SPDX-License-Identifier: LGPL-3.0-only
"""W009 — Production-approval HARD GATE, defense-in-depth at MO create.

The primary gate fires at sale.order.action_confirm() (see
models/sale_order.py). This module catches the other path: MOs created
directly without going through SO confirm (manual create from the MRP
backend, OCA `product_configurator_mrp` post-confirm hooks that bypass
the SO state edge, scheduled-procurement runs from sale_mrp, etc.).

Existing MOs are unaffected — this only fires on NEW create().

Bypass: the source sale.order's force_production_release flag also
short-circuits this gate, so a manager-blessed bypass at the SO level
propagates correctly to the downstream MO creates.

If an MO has no resolvable source SO (component sub-assemblies created
by procurement.group from a non-customer route — e.g. stock
replenishment, MO from inventory rules), the gate does NOT fire. This
matches the R1 spec's "exempt MOs where procurement_group_id resolves
through a non-customer route" carve-out.
"""
from odoo import _, api, models
from odoo.exceptions import UserError


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    @api.model_create_multi
    def create(self, vals_list):
        # Resolve each pending vals to its source sale.order (if any)
        # BEFORE create — we can't introspect self because it doesn't
        # exist yet. Two backlink paths: explicit sale_line_id and the
        # origin string falling through to a name lookup.
        SaleOrder = self.env["sale.order"].sudo()
        SaleLine = self.env["sale.order.line"].sudo()
        for vals in vals_list:
            source_so = SaleOrder.browse()
            sol_id = vals.get("sale_line_id")
            if sol_id:
                sol = SaleLine.browse(sol_id).exists()
                if sol:
                    source_so = sol.order_id
            if not source_so:
                origin = (vals.get("origin") or "").strip()
                if origin:
                    source_so = SaleOrder.search(
                        [("name", "=", origin)], limit=1)
            if not source_so:
                # No resolvable customer SO → component sub-assembly /
                # stock replenishment / manual MO from inventory rules.
                # The gate intentionally does not fire here (R1 carve-
                # out). The primary SO-confirm gate already covered any
                # customer-driven path.
                continue
            if source_so.force_production_release:
                continue
            if source_so.production_approval_state == "approved":
                continue
            raise UserError(_(
                "Cannot create manufacturing order for sale order "
                "%(name)s — production approval not granted (current "
                "state: %(state)s). Approve the order via the "
                "Production Approval header buttons before triggering "
                "MO creation. Sales Managers can set Force Production "
                "Release on the order as a one-off bypass.",
                name=source_so.name,
                state=source_so.production_approval_state,
            ))
        return super().create(vals_list)
