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

W019 — Today's Plan planner-home grouping.

`today_plan_section` is a computed (NOT stored) Selection that fuses
the existing material-availability, MI-status, and approval signals
into four planner-actionable buckets:

  - overdue       : past date_deadline, not yet done
  - ready_now     : material available + MI ok + approved, due today
                    or tomorrow
  - at_risk       : due within 3 days but material missing OR MI
                    blocked OR approval pending
  - long_horizon  : due > 3 days out — no morning action needed

Unstored compute because the inputs change frequently (cron sweeps
re-fire MI status every 5 min; material availability rolls forward
on every stock move); a stored field would either be perpetually
stale or burn writes. The 4-bucket switch is ~8 cheap reads per row,
and the dashboard kanban renders the relevant slice only.
"""
from datetime import timedelta

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

    # ------------------------------------------------------------------
    # W019 — Today's Plan section bucket
    # ------------------------------------------------------------------
    today_plan_section = fields.Selection(
        [
            ("overdue", "Overdue"),
            ("ready_now", "Ready Now"),
            ("at_risk", "At Risk"),
            ("long_horizon", "Long Horizon"),
        ],
        compute="_compute_today_plan_section",
        store=False,
        help=(
            "Planner-home bucket fusing material availability, MI "
            "status, approval gate, and due date into a single bucket "
            "for the Today's Plan kanban (W019)."
        ),
    )

    @api.depends(
        "date_deadline",
        "state",
    )
    def _compute_today_plan_section(self):
        # Cross-addon fields (components_availability_state, x_mi_*,
        # production_approval_state) are NOT in @api.depends because
        # they may not exist when this addon installs alone. The compute
        # uses getattr to stay defensive. Triggers fire on date_deadline
        # / state changes — for the others, the W053 5-min MI sweep +
        # the existing approval write hooks force a re-read on display.
        today = fields.Date.context_today(self)
        for mo in self:
            if mo.state in ("done", "cancel", "draft"):
                # Done / cancelled / draft MOs do not belong in any
                # planner-action bucket. Return False -> excluded by
                # the kanban grouping domain.
                mo.today_plan_section = False
                continue

            deadline = mo.date_deadline
            deadline_date = (
                fields.Datetime.context_timestamp(mo, deadline).date()
                if deadline else False
            )

            # Bucket 1 — Overdue. Past deadline still wins regardless
            # of MI / material — that's the planner's "fire-first" lane.
            if deadline_date and deadline_date < today:
                mo.today_plan_section = "overdue"
                continue

            # Resolve the three blocker signals.
            comp_state = (
                getattr(mo, "components_availability_state", False)
                or getattr(mo, "reservation_state", False)
                or ""
            )
            material_ok = (not comp_state) or comp_state in (
                "available", "assigned")
            mi_status = getattr(mo, "x_mi_status", False) or "ok"
            mi_blocker_count = getattr(mo, "x_mi_blocker_count", 0) or 0
            mi_ok = mi_status == "ok" and mi_blocker_count == 0
            approval = getattr(
                mo, "production_approval_state", False) or "approved"
            approval_ok = approval == "approved"
            all_clear = material_ok and mi_ok and approval_ok

            # Bucket 4 — Long horizon: due > 3 days out (or undated)
            # and nothing is preventing it from going. Out of today's
            # planner action surface.
            if (not deadline_date) or deadline_date > today + timedelta(days=3):
                # Long horizon ONLY when nothing is gating it. If the
                # MO is blocked even on a long horizon, surface it in
                # at-risk so the planner can chase it down early.
                if all_clear:
                    mo.today_plan_section = "long_horizon"
                else:
                    mo.today_plan_section = "at_risk"
                continue

            # Within the 3-day window. Ready iff all clear, at-risk
            # otherwise.
            if all_clear:
                mo.today_plan_section = "ready_now"
            else:
                mo.today_plan_section = "at_risk"

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
