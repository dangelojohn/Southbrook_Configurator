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
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    # ------------------------------------------------------------------
    # W010 — Ready-queue split: next-action surface on the Blocked list.
    #
    # Computed (NOT stored): the list view re-computes per row on read,
    # which is what the planner wants — "why is this blocked right now?"
    # Storing would require depends-tracking on optional foreign fields
    # (x_mi_*, production_approval_state) which fan out across modules.
    # Unstored compute is cheap (≤ 6 conditionals per row) and always
    # current.
    #
    # Field-safety: every cross-addon attribute is wrapped in getattr to
    # survive the case where southbrook_manufacturing_intelligence isn't
    # installed (only the southbrook_mrp_pm dep tree includes it
    # transitively; defensive against partial installs / cold-install
    # ordering).
    # ------------------------------------------------------------------
    next_action_hint = fields.Char(
        compute="_compute_next_action_hint",
        store=False,
        help=(
            "Surfaces the dominant blocker for the planner — material "
            "vs MI vs approval. Used by the Blocked queue (W010)."
        ),
    )

    def _compute_next_action_hint(self):
        for mo in self:
            # 1. Material availability — components_availability_state
            #    (v19 modern) falls back to reservation_state (older).
            comp_state = (
                getattr(mo, "components_availability_state", False)
                or getattr(mo, "reservation_state", False)
                or ""
            )
            if comp_state and comp_state not in ("available", "assigned"):
                mo.next_action_hint = _("Awaiting material")
                continue

            # 2. MI blocked — engineering / cut-spec / CAD gate.
            mi_status = getattr(mo, "x_mi_status", False)
            if mi_status == "blocked":
                mi_next = getattr(mo, "x_mi_next_action", False)
                mo.next_action_hint = _(
                    "MI blocked: %s"
                ) % (mi_next or _("see Intelligence tab"))
                continue
            if mi_status == "review":
                mo.next_action_hint = _("MI review needed")
                continue

            # 3. Defensive — MI cron hasn't run yet but blockers exist.
            blocker_count = getattr(mo, "x_mi_blocker_count", 0) or 0
            if blocker_count > 0:
                mo.next_action_hint = _(
                    "%d MI blocker(s)"
                ) % blocker_count
                continue

            # 4. Production approval gate (W009) — last because most
            #    Southbrook MOs clear approval before material reserves.
            approval = getattr(mo, "production_approval_state", False)
            if approval and approval != "approved":
                mo.next_action_hint = _("Awaiting Production approval")
                continue

            mo.next_action_hint = False

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
