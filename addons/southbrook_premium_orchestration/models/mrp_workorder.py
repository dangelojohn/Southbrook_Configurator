# SPDX-License-Identifier: LGPL-3.0-only
"""mrp.workorder — Phase 2.2 practical-intelligence loop.

Hooks ``button_finish`` so that when an operator closes a work order the
platform:

    1. Records a non-zero ``duration`` if the operator never punched the
       clock (prefer real start/end timestamps; fall back to the routing
       operation's expected duration).
    2. Walks the operation + work-center tool requirements, resolves
       each requirement to a concrete ``southbrook.tool.asset`` (explicit
       link when present, otherwise the in-service asset in the required
       category with the most remaining life), and writes a
       ``southbrook.workorder.tool.consumption`` ledger row. The
       consumption row's ``create`` hook in ``southbrook_mrp_kitchen_tools``
       is what actually decrements ``remaining_life_qty`` and bumps
       ``total_usage_qty`` on the asset, so this layer must NOT also write
       to those fields directly — doing so would double-debit.
    3. Schedules a "Sharpening / Replacement Due" mail.activity on the
       asset when its remaining life drops to ≤10% of estimated life.

The whole thing is idempotent: ``sbk_lifecycle_processed`` is the latch
that keeps a re-finish (the typical "Mark As Done / oops, undone / Mark
As Done" pattern) from re-debiting tool life.
"""
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# Activity summary string — also the dedup key in
# ``_sbk_maybe_raise_sharpening_activity``. Keep these two in sync.
_SHARPENING_SUMMARY = "Sharpening / Replacement Due"
_LIFE_THRESHOLD_PCT = 0.10


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    # ─── Aggregated tool consumption (Phase 2.2) ───────────────────────
    sbk_consumption_ids = fields.One2many(
        "southbrook.workorder.tool.consumption",
        "workorder_id",
        string="Tool Consumption",
        readonly=True,
    )
    sbk_consumption_total_cost = fields.Float(
        string="Tool Consumption Cost",
        compute="_compute_sbk_consumption_total_cost",
        store=False,
        help="Sum of total_cost across the work order's tool consumption "
             "ledger rows. Not stored — it's a cheap rollup over a small "
             "set and we want it to reflect uncommitted changes in the form.",
    )
    sbk_lifecycle_processed = fields.Boolean(
        string="Lifecycle Debit Recorded",
        default=False,
        copy=False,
        readonly=True,
        help="Latch that prevents button_finish from double-debiting tool "
             "life when an operator finishes the same work order twice.",
    )

    @api.depends("sbk_consumption_ids.total_cost")
    def _compute_sbk_consumption_total_cost(self):
        for wo in self:
            wo.sbk_consumption_total_cost = sum(
                wo.sbk_consumption_ids.mapped("total_cost")
            )

    # ──────────────────────────────────────────────────────────────────
    # button_finish — close the practical-intelligence loop
    # ──────────────────────────────────────────────────────────────────
    def button_finish(self):
        res = super().button_finish()
        for wo in self:
            try:
                wo._sbk_record_duration_if_zero()
                wo._sbk_debit_tool_lifecycle()
            except Exception:  # pragma: no cover — telemetry only
                _logger.warning(
                    "Southbrook lifecycle debit failed for WO %s",
                    wo.id, exc_info=True,
                )
        return res

    # ──────────────────────────────────────────────────────────────────
    # Duration backfill
    # ──────────────────────────────────────────────────────────────────
    def _sbk_record_duration_if_zero(self):
        """Backfill ``duration`` if the operator never logged time.

        Prefer real wall-clock between ``date_start`` and ``date_finished``;
        otherwise fall back to the routing operation's expected duration.
        Leaves a non-zero operator-entered duration untouched.
        """
        self.ensure_one()
        if self.duration and self.duration > 0.0:
            return
        if self.date_start and self.date_finished:
            delta_minutes = (
                self.date_finished - self.date_start
            ).total_seconds() / 60.0
            if delta_minutes > 0:
                self.duration = delta_minutes
                return
        if self.duration_expected and self.duration_expected > 0:
            self.duration = self.duration_expected

    # ──────────────────────────────────────────────────────────────────
    # Tool lifecycle debit
    # ──────────────────────────────────────────────────────────────────
    def _sbk_debit_tool_lifecycle(self):
        """Write one consumption row per (op-req ∪ wc-req) resolved asset.

        The consumption.create() hook in southbrook_mrp_kitchen_tools is
        what actually reduces asset life and bumps total_usage_qty; this
        method is just responsible for creating the ledger entries with
        the right quantity and unit cost. Idempotent via
        sbk_lifecycle_processed.
        """
        self.ensure_one()
        if self.sbk_lifecycle_processed:
            return

        WcReq = self.env["southbrook.workcenter.tool.requirement"]
        Consumption = self.env["southbrook.workorder.tool.consumption"]

        op_reqs = self._sbk_operation_tool_requirements()
        wc_reqs = (
            WcReq.search([("workcenter_id", "=", self.workcenter_id.id)])
            if self.workcenter_id else WcReq.browse()
        )

        # Op-level requirements are more specific so we process them first;
        # work-center requirements are the catch-all fallback.
        all_reqs = list(op_reqs) + list(wc_reqs)

        # produced_qty is the multiplier on per-unit consumption. Treat
        # zero/false as "at least 1 unit was produced" so a misconfigured
        # WO still debits one round of tool life.
        produced = max(self.qty_produced or 0.0, 1.0)

        # Employee link: the operator who closed the WO. Fall back to the
        # current user's employee if there's no operator on the WO.
        employee = self.env.user.employee_id

        seen_assets = set()
        created_consumption = False
        for req in all_reqs:
            asset = self._sbk_resolve_asset_for_req(req)
            if not asset or asset.id in seen_assets:
                continue
            seen_assets.add(asset.id)
            per_unit = self._sbk_qty_per_unit(req)
            consumed = per_unit * produced
            unit_cost = self._sbk_unit_cost_for_asset(asset)
            consumption = Consumption.create({
                "workorder_id": self.id,
                "asset_id": asset.id,
                "quantity": consumed,
                "unit_cost": unit_cost,
                # total_cost is a stored compute on the consumption model,
                # but we pass through anyway to keep CSV exports honest.
                "employee_id": employee.id if employee else False,
            })
            # consumption.create() already reduced remaining_life_qty,
            # bumped total_usage_qty, and stamped last_used_workorder_id.
            # We only need to maybe-raise an activity here.
            created_consumption = True
            self._sbk_maybe_raise_sharpening_activity(consumption.asset_id)

        if not created_consumption:
            _logger.warning(
                "Southbrook lifecycle debit created no consumption rows "
                "for WO %s; leaving lifecycle latch open.",
                self.id,
            )
            return

        self.sbk_lifecycle_processed = True

    # ──────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────
    def _sbk_operation_tool_requirements(self):
        """Return operation requirements for this WO.

        Generated MOs can carry cloned ``mrp.routing.workcenter`` records
        while the tool requirement remains attached to the matching
        source operation. Prefer the exact operation; when none exist,
        fall back to same operation name + workcenter so scan-driven
        finishes use the same requirement operators see in the normal UI.
        """
        self.ensure_one()
        OpReq = self.env["southbrook.operation.tool.requirement"]
        if not self.operation_id:
            return OpReq.browse()

        exact = OpReq.search([("operation_id", "=", self.operation_id.id)])
        if exact or not self.workcenter_id or not self.operation_id.name:
            return exact

        return OpReq.search([
            ("operation_id.name", "=", self.operation_id.name),
            ("workcenter_id", "=", self.workcenter_id.id),
        ])

    def _sbk_qty_per_unit(self, req):
        """Brief calls this ``qty_per_unit``; the real field on the
        operation requirement model is ``consume_qty_per_unit``. Accept
        either to keep the door open for future schema cleanup. Default
        to 1.0 so a requirement with no explicit per-unit still debits."""
        for fname in ("qty_per_unit", "consume_qty_per_unit"):
            if fname in req._fields:
                val = getattr(req, fname, 0.0) or 0.0
                if val > 0.0:
                    return val
        # Fallback: the requirement's ``quantity`` (an int representing
        # "how many of this tool the operation needs") is not a per-unit
        # multiplier — it's a count requirement. Use 1.0 here so we
        # debit exactly one round of life per produced unit.
        return 1.0

    def _sbk_resolve_asset_for_req(self, req):
        """Resolve a requirement to a concrete asset.

        Order of preference:
            1. Explicit ``tool_asset_id`` link on the requirement (used by
               the seed in B6 and by manual assignments).
            2. The in-service asset in the requirement's
               ``tool_category_id`` with the most remaining life — the
               "use the freshest blade first" heuristic.
            3. The in-service asset matching the requirement's
               ``product_id`` (specific-product requirements).

        Returns an empty recordset if nothing matches.
        """
        Asset = self.env["southbrook.tool.asset"]

        # 1) explicit link (forward-compatible — the field may not exist
        #    on every requirement variant)
        explicit = getattr(req, "tool_asset_id", False)
        if explicit:
            return explicit

        in_service = ("available", "in_use", "new")

        # 2) category-based resolution
        category = getattr(req, "tool_category_id", False)
        if category:
            candidate = Asset.search(
                [
                    ("tool_category_id", "=", category.id),
                    ("lifecycle_state", "in", in_service),
                    ("active", "=", True),
                ],
                order="remaining_life_qty desc, id asc",
                limit=1,
            )
            if candidate:
                return candidate

        # 3) specific-product resolution
        product = getattr(req, "product_id", False)
        if product:
            candidate = Asset.search(
                [
                    ("product_id", "=", product.id),
                    ("lifecycle_state", "in", in_service),
                    ("active", "=", True),
                ],
                order="remaining_life_qty desc, id asc",
                limit=1,
            )
            if candidate:
                return candidate

        return Asset.browse()

    def _sbk_unit_cost_for_asset(self, asset):
        """Pick the best available cost signal on the asset.

        The brief assumes an ``estimated_unit_cost`` field; the live model
        ships ``purchase_cost`` instead. Read whichever exists, in that
        order; default to 0.0.
        """
        for fname in ("estimated_unit_cost", "purchase_cost"):
            if fname in asset._fields:
                val = getattr(asset, fname, 0.0) or 0.0
                if val:
                    return val
        return 0.0

    def action_open_cut_spec_override_for_wo(self):
        """Open the cut-spec override form pre-bound to this work order.

        Thin proxy so the header button on mrp.workorder (declared in
        views/mrp_workorder_views.xml with type='object') resolves on the
        correct model — the actual record-construction logic lives on
        southbrook.cut.spec.override (Phase 2.3, B8)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Record Cut-Spec Deviation",
            "res_model": "southbrook.cut.spec.override",
            "view_mode": "form",
            "target": "new",
            "context": {"default_workorder_id": self.id},
        }

    def _sbk_maybe_raise_sharpening_activity(self, asset):
        """Schedule a 'Sharpening / Replacement Due' activity when the
        asset crosses the 10%-remaining threshold, deduped on summary."""
        if not asset or not asset.estimated_life_qty:
            return
        remaining = asset.remaining_life_qty or 0.0
        if remaining / asset.estimated_life_qty > _LIFE_THRESHOLD_PCT:
            return

        existing = self.env["mail.activity"].search(
            [
                ("res_model", "=", "southbrook.tool.asset"),
                ("res_id", "=", asset.id),
                ("summary", "ilike", _SHARPENING_SUMMARY),
            ],
            limit=1,
        )
        if existing:
            return
        try:
            pct = (
                (remaining / asset.estimated_life_qty) * 100.0
                if asset.estimated_life_qty else 0.0
            )
            asset.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=_SHARPENING_SUMMARY,
                note=_(
                    "Asset %(name)s dropped to %(remaining).0f of "
                    "%(estimated).0f (%(pct).0f%%). "
                    "Schedule sharpening or replacement."
                ) % {
                    "name": asset.display_name or asset.name or "(unnamed)",
                    "remaining": remaining,
                    "estimated": asset.estimated_life_qty,
                    "pct": pct,
                },
            )
        except Exception:  # pragma: no cover — telemetry only
            _logger.warning(
                "Could not schedule sharpening activity on asset %s",
                asset.id, exc_info=True,
            )
