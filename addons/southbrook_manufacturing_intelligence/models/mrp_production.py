# SPDX-License-Identifier: LGPL-3.0-only
from odoo import _, api, fields, models
from odoo.exceptions import UserError


# W025 — fai_status values. Stored compute on mrp.production driven by
# bom_id.fai_required + the existence of a passing FAI mi.check.
FAI_STATUS_VALUES = [
    ("not_required", "Not Required"),
    ("pending", "FAI Pending"),
    ("in_progress", "FAI In Progress"),
    ("passed", "FAI Passed"),
    ("failed", "FAI Failed"),
]

# W025 — MO state values for which the FAI gate should reject
# action_assign. We block 'draft' + 'confirmed' so the planner cannot
# release the MO to the shop floor; 'progress' is intentionally not in
# this list (the MO is already in motion).
FAI_GATED_STATES = frozenset({"draft", "confirmed"})


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    x_mi_status = fields.Selection(
        [
            ("ok", "OK"),
            ("review", "Review"),
            ("blocked", "Blocked"),
        ],
        string="MI Status",
        default="ok",
        copy=False,
    )
    x_mi_check_ids = fields.One2many(
        "southbrook.mi.check", "production_id", string="Manufacturing Intelligence Checks"
    )
    x_mi_blocker_count = fields.Integer(string="MI Blockers", copy=False)
    x_mi_warning_count = fields.Integer(string="MI Warnings", copy=False)
    x_mi_next_action = fields.Text(string="MI Next Action", copy=False)
    x_mi_yield_pct = fields.Float(string="MI Sheet Yield %", copy=False)
    x_mi_waste_area_m2 = fields.Float(string="MI Waste Area m2", copy=False)
    x_mi_bottleneck_workcenter_id = fields.Many2one(
        "mrp.workcenter", string="MI Bottleneck Workcenter", copy=False
    )

    # ------------------------------------------------------------------
    # W012 — deviation-waiver warranty trace
    # ------------------------------------------------------------------
    # NOT a One2many because the canonical link lives on the waiver via
    # `production_id = related(mi_check_id.production_id, store=True)`.
    # Computing a count + an act_window button is enough surface; the
    # full waiver list is reachable through the smart button click.
    deviation_waiver_count = fields.Integer(
        string="Deviation Waivers",
        compute="_compute_deviation_waiver_count",
        help="Count of southbrook.deviation.waiver records bound to "
             "this MO via their mi_check_id.production_id linkage. The "
             "load-bearing field for warranty trace 18 months out — "
             '"did we ship this cabinet with a known defect?"',
    )

    @api.depends("x_mi_check_ids", "x_mi_check_ids.deviation_waiver_id")
    def _compute_deviation_waiver_count(self):
        Waiver = self.env["southbrook.deviation.waiver"]
        for prod in self:
            prod.deviation_waiver_count = Waiver.search_count(
                [("production_id", "=", prod.id)]
            )

    def action_open_deviation_waivers(self):
        """Smart button — show every waiver bound to this MO.

        Filters live on `production_id` which is a stored related on
        the waiver itself, so the search is index-supported.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Deviation Waivers"),
            "res_model": "southbrook.deviation.waiver",
            "view_mode": "list,form",
            "domain": [("production_id", "=", self.id)],
            "context": {"default_production_id": self.id},
        }

    def action_recompute_manufacturing_intelligence(self):
        engine = self.env["southbrook.mi.engine"]
        for production in self:
            engine._recompute_production(production)
        return True

    # ------------------------------------------------------------------
    # W053 / R7.6 — 5-min sweep cron over in-flight MOs
    # ------------------------------------------------------------------
    # MI status fields (x_mi_status, x_mi_blocker_count) are stamped on
    # event-driven hooks today. Those events miss MOs whose blocking
    # input changes outside the MO record itself (a freshly-attached
    # FreeCAD render, a CAD-status flip on the cabinet, a stock-move
    # availability change). A 5-min sweep closes that staleness gap.
    #
    # IDEMPOTENT: _recompute_production only WRITES when any of
    # (x_mi_status, x_mi_blocker_count, x_mi_warning_count,
    # x_mi_next_action) actually CHANGES. See _mi_idempotent_write
    # below. A no-change recompute is a search + compare + zero
    # writes, so the cron is safe at any frequency.
    @api.model
    def _cron_mi_recompute_sweep(self):
        """Re-fire MI recompute across every in-flight MO.

        In-flight = state in ('confirmed', 'progress', 'to_close').
        Cancelled and done MOs are skipped — their MI status is
        historical.

        Calls _recompute_production per row inside a try/except so a
        single bad MO doesn't poison the whole sweep.
        """
        import logging
        _logger = logging.getLogger(__name__)

        engine = self.env["southbrook.mi.engine"]
        domain = [("state", "in", ("confirmed", "progress", "to_close"))]
        productions = self.sudo().search(domain)
        touched = 0
        for prod in productions:
            try:
                engine._recompute_production(prod)
                touched += 1
            except Exception as e:  # noqa: BLE001
                _logger.warning(
                    "W053 MI sweep: MO %s recompute failed: %s",
                    prod.display_name, e,
                )
        _logger.info(
            "W053 MI sweep: %d in-flight MOs scanned, recompute completed",
            touched,
        )
        return True

    # ------------------------------------------------------------------
    # W025 — First Article Inspection gate
    # ------------------------------------------------------------------
    # fai_status is a stored compute. Sources:
    #   * bom_id.fai_required
    #   * bom_id.fai_passing_mi_check_id
    #   * x_mi_check_ids (the FAI mi.check on THIS MO, if any)
    #
    # Stored so the manager dashboard tile (W015) can search/group on
    # it without recomputing per-render. The compute is cheap (single
    # field reads, no traversals) so the cost on bulk MO writes is
    # negligible.
    fai_status = fields.Selection(
        FAI_STATUS_VALUES,
        string="FAI Status",
        compute="_compute_fai_status", store=True, index=True,
        copy=False, tracking=True,
        help="W025 — First Article Inspection state for this MO. "
             "'not_required' (BOM has no FAI gate or has already "
             "passed), 'pending' (no FAI check yet), 'in_progress' "
             "(FAI check open), 'passed' (BOM cleared), 'failed' "
             "(FAI check at severity=blocker — MO blocked).",
    )
    fai_check_id = fields.Many2one(
        "southbrook.mi.check",
        string="FAI Check",
        compute="_compute_fai_check_id", store=True,
        copy=False,
        help="The FAI mi.check auto-created for this MO (if any). "
             "One per MO — the first category='fai' check found wins.",
    )

    @api.depends(
        "bom_id",
        "bom_id.fai_required",
        "bom_id.fai_passing_mi_check_id",
        "x_mi_check_ids",
        "x_mi_check_ids.category",
        "x_mi_check_ids.severity",
        "x_mi_check_ids.active",
    )
    def _compute_fai_check_id(self):
        for prod in self:
            # Pick the first FAI-category check on this MO — INCLUDING inactive
            # ones. action_fai_pass retires the passing check to active=False;
            # the plain One2many read applies active_test and would drop it,
            # leaving fai_check_id empty and fai_status falling back to
            # 'not_required' instead of 'passed' (L1). Read with active_test off
            # so the historical sign-off record is surfaced.
            fai_check = prod.with_context(active_test=False).x_mi_check_ids \
                .filtered(lambda c: c.category == "fai")[:1]
            prod.fai_check_id = fai_check.id if fai_check else False

    @api.depends(
        "bom_id",
        "bom_id.fai_required",
        "bom_id.fai_passing_mi_check_id",
        "fai_check_id",
        "fai_check_id.active",
        "fai_check_id.severity",
    )
    def _compute_fai_status(self):
        for prod in self:
            bom = prod.bom_id
            if not bom or not bom.fai_required:
                # Either no BOM, or BOM already cleared (or never
                # required). Distinguish "passed" from "not_required":
                # if the BOM has a passing check that points back at
                # one of OUR checks, this is the MO that signed it off.
                fai = prod.fai_check_id
                if (
                    fai
                    and bom
                    and bom.fai_passing_mi_check_id
                    and bom.fai_passing_mi_check_id == fai
                ):
                    prod.fai_status = "passed"
                else:
                    prod.fai_status = "not_required"
                continue
            # BOM still requires FAI.
            fai = prod.fai_check_id
            if not fai:
                prod.fai_status = "pending"
            elif not fai.active:
                # Check was retired without flipping the BOM flag —
                # treat as pending (re-open required).
                prod.fai_status = "pending"
            elif fai.severity == "blocker":
                prod.fai_status = "failed"
            else:
                prod.fai_status = "in_progress"

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-create a category='fai' mi.check for any MO whose BOM
        carries fai_required=True.

        Idempotent: if the MO already has a category='fai' check on
        creation (a no-op for vanilla creates, but defensive against
        re-creates from copy()/duplicate flows), we skip.

        Bypassed by context flag `_w025_skip_fai_default` for tests.
        """
        productions = super().create(vals_list)
        if self.env.context.get("_w025_skip_fai_default"):
            return productions
        Check = self.env["southbrook.mi.check"]
        for prod in productions:
            bom = prod.bom_id
            if not bom or not bom.fai_required:
                continue
            existing = prod.x_mi_check_ids.filtered(
                lambda c: c.category == "fai"
            )
            if existing:
                continue
            # sudo() because the BOM creator may belong to a group that
            # doesn't have mi.check create rights (the auto-creation is
            # a system-driven enforcement, not a user action).
            Check.sudo().create({
                "name": _("First Article Inspection — %s") % (
                    prod.display_name or prod.name or ""),
                "category": "fai",
                # severity=warning so it shows in the MI surface but
                # doesn't trip the blocker-only dashboards until an
                # inspector marks it 'failed'.
                "severity": "warning",
                "message": _(
                    "BOM %(bom)s is on its first MO since release. "
                    "Run the First Article Inspection on this cabinet "
                    "BEFORE further MOs are released to the shop. "
                    "On pass: subsequent MOs unlock automatically.",
                    bom=bom.display_name,
                ),
                "recommendation": _(
                    "Verify panel dimensions, hardware locations, edge "
                    "treatments, and door swing against the released "
                    "BOM. On pass, click 'FAI Pass' on this check."
                ),
                "production_id": prod.id,
            })
            prod.message_post(body=_(
                "<strong>FAI gate active (W025)</strong>: this MO is "
                "the first against BOM <b>%(bom)s</b>. A First Article "
                "Inspection check has been created and must pass "
                "before action_assign will release the MO.",
                bom=bom.display_name,
            ))
        return productions

    def action_assign(self):
        """Gate action_assign on FAI status (W025).

        Blocks when fai_status is pending / in_progress / failed AND
        the MO is in a state where the planner is trying to release
        it to the shop (draft, confirmed). Does NOT block MOs already
        in 'progress' — those are mid-flight and gating them would
        cause more harm than good (the FAI is for the first cabinet,
        which is by definition the one IN progress).
        """
        for mo in self:
            if mo.state not in FAI_GATED_STATES:
                continue
            if mo.fai_status in ("pending", "in_progress", "failed"):
                raise UserError(_(
                    "Cannot release MO %(name)s to the shop — First "
                    "Article Inspection is %(status)s.\n\n"
                    "Open the MI Checks tab on this MO and run the "
                    "FAI inspection. Once the first cabinet passes, "
                    "every subsequent MO against this BOM will "
                    "unlock automatically.",
                    name=mo.display_name,
                    status=dict(FAI_STATUS_VALUES).get(
                        mo.fai_status, mo.fai_status),
                ))
        return super().action_assign()
