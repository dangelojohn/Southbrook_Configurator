# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.mi.check — kitchen-shop QC stage + defect taxonomy.

Per brief §11, this module EXTENDS the existing
southbrook.mi.check model shipped by southbrook_manufacturing_intelligence
rather than creating a parallel southbrook.kitchen.quality.check.

Existing surface (kept intact):
  name / message / recommendation / category / severity (info/warning/
  blocker) / production_id / production_package_id / active

Added here (all x_sbk_ prefixed to grep-distinguish from upstream):
  x_sbk_check_stage          which floor step the check fired at
  x_sbk_defect_type          14-value defect taxonomy
  x_sbk_defect_severity      minor / major / critical (DISTINCT from
                              the existing severity which is the MI
                              engine's info/warning/blocker triage —
                              this one is the shop-floor inspector's
                              call on the part itself)
  x_sbk_result               pass / fail / rework / hold
  x_sbk_workorder_id         the WO the inspector was checking
  x_sbk_workcenter_id        the station where the check happened
                              (related on workorder_id by default)
  x_sbk_inspector_id         the user who ran the check
  x_sbk_date_checked         when the inspection happened
  x_sbk_rework_required      Boolean — drives rework workorder creation
  x_sbk_rework_workcenter_id station the rework should be routed back to
  x_sbk_rework_workorder_id  link to the spawned rework WO (M4)
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


CHECK_STAGES = [
    ("after_cutting", "After Cutting"),
    ("after_edge_banding", "After Edge Banding"),
    ("after_cnc_drilling", "After CNC / Drilling"),
    ("after_sanding", "After Sanding"),
    ("after_painting", "After Painting"),
    ("after_assembly", "After Assembly"),
    ("hardware_check", "Hardware Check"),
    ("final_qc", "Final QC"),
    ("packing_check", "Packing Check"),
]


DEFECT_TYPES = [
    ("wrong_dimension", "Wrong Dimension"),
    ("wrong_material", "Wrong Material"),
    ("grain_direction", "Grain Direction"),
    ("edge_defect", "Edge Defect"),
    ("hole_position", "Hole Position"),
    ("finish_defect", "Finish Defect"),
    ("scratch", "Scratch"),
    ("hardware_missing", "Hardware Missing"),
    ("hardware_alignment", "Hardware Alignment"),
    ("assembly_square", "Assembly Not Square"),
    ("label_error", "Label Error"),
    ("missing_component", "Missing Component"),
    ("packaging_issue", "Packaging Issue"),
    ("other", "Other"),
]


DEFECT_SEVERITIES = [
    ("minor", "Minor (cosmetic)"),
    ("major", "Major (functional)"),
    ("critical", "Critical (unfit for delivery)"),
]


CHECK_RESULTS = [
    ("pass", "Pass"),
    ("fail", "Fail"),
    ("rework", "Rework Required"),
    ("hold", "Hold for Review"),
]


class SouthbrookMiCheck(models.Model):
    _inherit = ["southbrook.mi.check", "southbrook.qr.mixin"]
    _qr_kind = "ncr"

    x_sbk_check_stage = fields.Selection(
        CHECK_STAGES,
        string="Kitchen Check Stage",
        index=True,
        help="Which step on the kitchen-shop value stream the check "
             "fired at. Drives reporting groupbys and the 'which "
             "operation produced this defect' query.",
    )
    x_sbk_defect_type = fields.Selection(
        DEFECT_TYPES,
        string="Defect Type",
        index=True,
    )
    x_sbk_defect_severity = fields.Selection(
        DEFECT_SEVERITIES,
        string="Defect Severity",
        index=True,
        help="Inspector's call on the part. minor = cosmetic that "
             "would survive customer scrutiny; major = functional "
             "(door won't shut, drawer won't slide); critical = part "
             "is unfit for delivery and must be remade.",
    )
    x_sbk_result = fields.Selection(
        CHECK_RESULTS,
        string="Check Result",
        index=True,
        help="The inspector's outcome. 'rework' creates a rework WO; "
             "'hold' parks the part until engineering reviews.",
    )

    # Work-order context.
    x_sbk_workorder_id = fields.Many2one(
        comodel_name="mrp.workorder",
        string="Work Order",
        ondelete="set null", index=True,
    )
    x_sbk_workcenter_id = fields.Many2one(
        comodel_name="mrp.workcenter",
        string="Work Center",
        related="x_sbk_workorder_id.workcenter_id",
        store=True, readonly=True, index=True,
    )
    # W049 (R7.5, 2026-06-27) — shift attribution on NCR pareto.
    # Stored related so the supervisor can group "this week's NCRs by
    # shift" without an Excel export. Empty when the WO has not
    # started or when no WO is attached — both bucketed as "Unassigned"
    # in the report (the supervisor's signal that the originating
    # shift is not yet known).
    x_sb_shift = fields.Selection(
        related="x_sbk_workorder_id.x_sb_shift",
        store=True, readonly=True, index=True,
        string="Shift",
    )
    x_sbk_inspector_id = fields.Many2one(
        comodel_name="res.users",
        string="Inspector",
        default=lambda self: self.env.user,
    )
    x_sbk_date_checked = fields.Datetime(
        string="Date Checked",
        default=fields.Datetime.now,
    )

    # W044 (R5.8, 2026-06-27) — pareto-by-operator attribution.
    #
    # JTBD: "When I'm tracking defect root cause this quarter, I want
    # to see which operator is producing the most NCRs so I can pair
    # them with the senior on the next shift." Without an operator
    # field on mi.check, the only attribution we have is
    # x_sbk_inspector_id — which credits the QC person who *found*
    # the defect, not the operator who *caused* it.
    #
    # Strategy (per W044 spec, stored-compute branch — NOT stored-related):
    #   We can't use a stored related from x_sbk_workorder_id.user_id
    #   because (a) mrp.workorder doesn't track operator-attribution
    #   directly in v19 CE — Odoo uses mrp.workcenter.productivity
    #   rows for per-block credit — and (b) the value we actually want
    #   is "who was at the bench when the part went through", which
    #   maps cleanly to the most-recent scan-log row stamped during
    #   W035 PIN-gated scanning.
    #
    # The compute walks `southbrook.qr.scan.log` for the WO's most
    # recent scan with kind='wo' and a populated employee_id, sorted
    # by create_date desc. Bounded scope: only checks where x_sbk_
    # workorder_id is set; otherwise the operator field stays empty
    # (consistent with not-applicable). Stored so the Pareto pivot/
    # graph groupby is cheap (no per-row resolver hit).
    #
    # Depends are conservative — the value can change post-create if
    # a fresh scan lands; the standard recompute hooks fire when an
    # NCR is created (scan_log already in place at that moment) and
    # when x_sbk_workorder_id is rebound (e.g. follow-up reinspection
    # spawn rebinds to the rework WO). We do NOT add scan_log as a
    # depends source — that would require depends_context tracking we
    # don't currently support, and the field is acceptable as a
    # snapshot at NCR-create time rather than continuously re-resolving.
    x_sbk_operator_who_caused_defect_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Operator (Caused Defect)",
        compute="_compute_operator_who_caused_defect",
        store=True,
        index=True,
        readonly=True,
        help="The shop-floor operator at the bench when the defect was "
             "produced — resolved from the most recent PIN-gated QR "
             "scan_log row tied to this WO. Distinct from "
             "x_sbk_inspector_id (the QC person who found the "
             "defect). Drives the pareto-by-operator NCR pivot.",
    )

    @api.depends("x_sbk_workorder_id")
    def _compute_operator_who_caused_defect(self):
        Log = self.env["southbrook.qr.scan.log"].sudo()
        for check in self:
            if not check.x_sbk_workorder_id:
                check.x_sbk_operator_who_caused_defect_id = False
                continue
            # Most recent scan-log row on this WO with employee_id set.
            # We accept any action — `wo`/`start`/`finish`/`form_open`
            # all credit the operator who was at the bench. Restricting
            # to start/finish would miss the form_open path that W035
            # also stamps and would weaken the attribution for stations
            # whose tablets read but never write WO state.
            log = Log.search([
                ("target_model", "=", "mrp.workorder"),
                ("target_id", "=", check.x_sbk_workorder_id.id),
                ("employee_id", "!=", False),
                ("result", "=", "ok"),
            ], order="create_date desc, id desc", limit=1)
            check.x_sbk_operator_who_caused_defect_id = (
                log.employee_id.id if log else False
            )

    # Rework wiring.
    x_sbk_rework_required = fields.Boolean(
        string="Rework Required",
        compute="_compute_rework_required",
        store=True, readonly=False,
        help="Computed from x_sbk_result — True when result='fail' or "
             "'rework'. Editable so the inspector can override.",
    )
    x_sbk_rework_workcenter_id = fields.Many2one(
        comodel_name="mrp.workcenter",
        string="Send Rework To",
        help="The station to route the rework WO back to. Defaults "
             "differ by defect type (paint scratch → SAND / PAINT; "
             "edge defect → EDGE; hardware misalignment → HW). The "
             "inspector can override.",
    )
    x_sbk_rework_workorder_id = fields.Many2one(
        comodel_name="mrp.workorder",
        string="Rework Work Order",
        ondelete="set null",
        help="Created when the inspector clicks 'Create Rework WO' "
             "in the form view. Linked back so the original check "
             "shows the spawned rework.",
    )

    # W043 (R5.7, 2026-06-27) — re-inspection wiring after rework
    # workorder completion.
    #
    # The original problem: action_create_rework_workorder spawns a
    # rework WO, but nothing forces a fresh inspection once the rework
    # finishes. The NCR's severity stays at 'blocker' (or whatever the
    # inspector tagged) forever, the asbuilt qc_pass compute only
    # checks rework_workorder.state == "done" (produced, not
    # inspected), and the part can ship without a second pair of eyes.
    #
    # W043 closes that loop by intercepting mrp.workorder.button_finish
    # on the rework WO: when the rework finishes, we (a) flip a state
    # field on the originating check that the asbuilt compute can read,
    # and (b) auto-create a follow-up `southbrook.mi.check` of category
    # 'production' requesting re-inspection, with `x_sbk_inspector_id`
    # explicitly set to a user OTHER than the original inspector
    # (SoD-light) and `x_sbk_originating_check_id` pointing back to
    # the parent NCR so the audit trail is one click away.
    #
    # We add a field instead of mutating `severity` because severity is
    # already a triage signal driving _order + the MI engine status —
    # repurposing it to mean 'reinspection state' would break a lot of
    # callers.
    x_sbk_reinspection_state = fields.Selection(
        [
            ("not_required", "Not Required"),
            ("pending", "Pending Re-Inspection"),
            ("passed", "Re-Inspection Passed"),
            ("failed", "Re-Inspection Failed"),
        ],
        string="Re-Inspection State",
        default="not_required",
        index=True,
        copy=False,
        help="Tracks the re-inspection requirement triggered when the "
             "rework workorder finishes. 'pending' = follow-up "
             "mi.check was auto-spawned and is waiting on an inspector "
             "who didn't sign off on this original check.",
    )
    x_sbk_reinspection_check_id = fields.Many2one(
        comodel_name="southbrook.mi.check",
        string="Follow-up Re-Inspection",
        ondelete="set null",
        readonly=True,
        copy=False,
        help="The follow-up mi.check this NCR spawned when its rework "
             "workorder finished. Idempotency anchor — re-firing on a "
             "check that already has one just opens it.",
    )
    x_sbk_originating_check_id = fields.Many2one(
        comodel_name="southbrook.mi.check",
        string="Original NCR",
        ondelete="set null",
        readonly=True,
        copy=False,
        index=True,
        help="When this record IS a re-inspection check (spawned by "
             "the rework-finish handler), points back at the NCR that "
             "kicked it off. Empty on first-time NCRs.",
    )

    # SAMI PRD INV-06 (2026-06-25) — NCR auto-quarantine.
    x_sbk_quarantine_picking_id = fields.Many2one(
        comodel_name="stock.picking",
        string="Quarantine Transfer",
        ondelete="set null",
        readonly=True,
        help="Auto-created internal transfer that moves the failed "
             "batch to the Southbrook Quarantine location. Lands in "
             "draft state so the inspector can review the qty + lot "
             "before confirming the move.",
    )
    x_sbk_quarantined_at = fields.Datetime(
        string="Quarantined At",
        readonly=True,
    )

    # --------------------------------------------------------------
    # NCR auto-quarantine (SAMI PRD INV-06, 2026-06-25)
    # --------------------------------------------------------------
    _QUARANTINE_SEVERITY_RANK = {
        "minor": 1,
        "major": 2,
        "critical": 3,
    }

    def _should_auto_quarantine(self):
        """True if this check's (result, severity) crosses the
        configured threshold and a picking hasn't been created yet."""
        self.ensure_one()
        if self.x_sbk_quarantine_picking_id or self.x_sbk_result != "fail":
            return False
        Param = self.env["ir.config_parameter"].sudo()
        threshold = (Param.get_param(
            "southbrook.ncr_quarantine.severity_threshold", "critical")
            or "critical").lower()
        threshold_rank = self._QUARANTINE_SEVERITY_RANK.get(threshold, 3)
        sev_rank = self._QUARANTINE_SEVERITY_RANK.get(
            self.x_sbk_defect_severity or "minor", 1)
        return sev_rank >= threshold_rank

    def action_quarantine_failed_batch(self):
        """Create a draft stock.picking that moves the failed batch
        to the Southbrook Quarantine location. Idempotent — re-clicking
        on a check that already has a picking just opens it."""
        self.ensure_one()
        if self.x_sbk_quarantine_picking_id:
            return self._action_open_quarantine_picking()
        wo = self.x_sbk_workorder_id
        if not wo or not wo.production_id:
            raise UserError(_(
                "Quarantine needs a linked production order — set "
                "x_sbk_workorder_id on this check first."))
        try:
            quarantine_loc = self.env.ref(
                "southbrook_mrp_kitchen_workcenters."
                "stock_location_southbrook_quarantine")
        except ValueError:
            raise UserError(_(
                "Southbrook Quarantine location is missing. "
                "Re-run module upgrade or restore data/southbrook_"
                "quarantine_location.xml."))
        mo = wo.production_id
        Picking = self.env["stock.picking"]
        Move = self.env["stock.move"]
        # Source = MO's destination location (where finished goods land)
        # OR fall back to its production location if dest isn't set.
        src_loc = (mo.location_dest_id
                   or mo.picking_type_id.default_location_dest_id
                   or self.env.ref("stock.stock_location_stock"))
        picking_type = self.env["stock.picking.type"].search([
            ("code", "=", "internal"),
            ("warehouse_id.company_id", "=", self.env.company.id),
        ], limit=1)
        if not picking_type:
            raise UserError(_(
                "No internal-transfer picking type found in the "
                "active company — configure a warehouse first."))
        picking = Picking.create({
            "picking_type_id": picking_type.id,
            "location_id": src_loc.id,
            "location_dest_id": quarantine_loc.id,
            "origin": _("NCR: %(check)s (MO %(mo)s)",
                        check=self.name or self.id, mo=mo.name),
            "company_id": self.env.company.id,
        })
        Move.create({
            "name": _("NCR quarantine: %(p)s",
                      p=mo.product_id.display_name),
            "picking_id": picking.id,
            "product_id": mo.product_id.id,
            "product_uom_qty": wo.qty_producing or 1.0,
            "product_uom": mo.product_uom_id.id,
            "location_id": src_loc.id,
            "location_dest_id": quarantine_loc.id,
            "company_id": self.env.company.id,
        })
        self.write({
            "x_sbk_quarantine_picking_id": picking.id,
            "x_sbk_quarantined_at": fields.Datetime.now(),
        })
        # Emit dashboard event — non-fatal.
        try:
            self.env["southbrook.ops.event"].emit(
                "install_risk",
                _("Quarantine transfer %(p)s drafted for MO %(mo)s "
                  "(defect: %(d)s)",
                  p=picking.name or "?",
                  mo=mo.name or "?",
                  d=dict(self._fields["x_sbk_defect_type"].selection).get(
                      self.x_sbk_defect_type, "?")),
                res_model="stock.picking",
                res_id=picking.id,
                severity="alert",
            )
        except Exception:  # noqa: BLE001
            pass
        return self._action_open_quarantine_picking()

    def _action_open_quarantine_picking(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Quarantine Transfer"),
            "res_model": "stock.picking",
            "res_id": self.x_sbk_quarantine_picking_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def write(self, vals):
        result = super().write(vals)
        # Auto-quarantine when result transitions to fail AND severity
        # crosses the threshold (default 'critical'). Wrapped in
        # try/except — quarantine MUST NEVER block the inspector from
        # saving their finding.
        if "x_sbk_result" in vals or "x_sbk_defect_severity" in vals:
            for check in self:
                if check._should_auto_quarantine():
                    try:
                        check.action_quarantine_failed_batch()
                    except Exception:  # noqa: BLE001
                        pass
        return result

    @api.depends("x_sbk_result")
    def _compute_rework_required(self):
        for check in self:
            check.x_sbk_rework_required = check.x_sbk_result in (
                "fail", "rework",
            )

    # --------------------------------------------------------------
    # NCR → rework workorder spawn (SAMI PRD #8 + #9, ~2026-06-25)
    #
    # The framework around this method has existed since M3 (defect
    # taxonomy + rework_required flag + rework_workcenter mapping).
    # Action below is the missing piece that ACTUALLY creates the
    # rework workorder. Idempotent: re-calling on a check whose
    # rework WO already exists just opens it.
    # --------------------------------------------------------------
    def action_create_rework_workorder(self):
        """Spawn a rework mrp.workorder at the rework_workcenter.

        Re-routes the failed part back to the right station per the
        defect-type → workcenter mapping. The new WO is on the SAME
        production order (no MO split), and the original check holds
        the link so an inspector can see the rework that came out of
        their NCR.
        """
        self.ensure_one()
        if self.x_sbk_rework_workorder_id:
            return self._action_open_rework_workorder()
        if not self.x_sbk_rework_required:
            raise UserError(_("This check does not require rework."))
        if not self.x_sbk_workorder_id:
            raise UserError(
                _("The original work order is required to spawn rework. "
                  "Set x_sbk_workorder_id on this check first."))
        if not self.x_sbk_rework_workcenter_id:
            raise UserError(
                _("Set 'Send Rework To' (rework workcenter) before "
                  "creating the rework work order."))
        src = self.x_sbk_workorder_id
        wc = self.x_sbk_rework_workcenter_id
        defect_label = dict(self._fields["x_sbk_defect_type"].selection).get(
            self.x_sbk_defect_type, _("defect"))
        new_wo = self.env["mrp.workorder"].create({
            "production_id": src.production_id.id,
            "product_id": src.product_id.id,
            "workcenter_id": wc.id,
            "operation_id": src.operation_id.id if src.operation_id else False,
            "name": _("Rework: %(d)s @ %(wc)s",
                      d=defect_label, wc=wc.name),
            "qty_producing": src.qty_producing or src.qty_production or 0.0,
            "state": "ready",
        })
        self.x_sbk_rework_workorder_id = new_wo.id
        # Best-effort dashboard event — non-fatal if event model missing.
        try:
            self.env["southbrook.ops.event"].emit(
                "override_flagged",
                _("Rework WO %(name)s spawned for MO %(mo)s "
                  "(defect: %(d)s → %(wc)s)",
                  name=new_wo.name or "?",
                  mo=src.production_id.name or "?",
                  d=defect_label, wc=wc.name),
                res_model="mrp.workorder",
                res_id=new_wo.id,
                severity="warn",
            )
        except Exception:  # noqa: BLE001
            pass
        return self._action_open_rework_workorder()

    def _action_open_rework_workorder(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Rework Work Order"),
            "res_model": "mrp.workorder",
            "res_id": self.x_sbk_rework_workorder_id.id,
            "view_mode": "form",
            "target": "current",
        }

    # --------------------------------------------------------------
    # W043 (R5.7, 2026-06-27) — re-inspection spawn on rework finish.
    # --------------------------------------------------------------
    def _sbk_resolve_reinspector(self):
        """Return a res.users for the re-inspection follow-up that is
        NOT the original inspector — SoD-light enforcement.

        Strategy:
          1. Look for a quality-group user other than the original
             inspector (group `southbrook_manufacturing_intelligence.
             group_southbrook_mi_quality` if it exists, otherwise the
             stock quality group, otherwise any internal user).
          2. Fall back to the production_id.responsible_id or
             mrp_workcenter.write_uid as a last resort.
          3. If absolutely no alternate user can be found (single-
             user dev / test environments), return False — the caller
             stamps the new check unassigned and the re-inspection
             state still records as 'pending'. We never assign the
             same person back to themselves.
        """
        self.ensure_one()
        original_inspector = self.x_sbk_inspector_id
        Users = self.env["res.users"]
        group_xmlids = (
            "southbrook_manufacturing_intelligence.group_southbrook_mi_quality",
            "quality.group_quality_user",
            "base.group_user",
        )
        for ref in group_xmlids:
            group = self.env.ref(ref, raise_if_not_found=False)
            if not group:
                continue
            candidate = Users.search([
                ("group_ids", "in", group.id),
                ("id", "!=", original_inspector.id if original_inspector else 0),
                ("active", "=", True),
                ("share", "=", False),
            ], limit=1)
            if candidate:
                return candidate
        # Last-ditch fallback — anyone but the original inspector.
        fallback = Users.search([
            ("id", "!=", original_inspector.id if original_inspector else 0),
            ("active", "=", True),
            ("share", "=", False),
        ], limit=1)
        return fallback or self.env["res.users"]

    def _sbk_spawn_reinspection_check(self):
        """Create the follow-up `southbrook.mi.check` requesting a
        re-inspection. Idempotent — re-calling on a check that already
        has `x_sbk_reinspection_check_id` is a no-op.

        SoD-light: the new check's `x_sbk_inspector_id` is forcibly
        assigned to a user OTHER than the one who signed off on the
        original NCR. The new check is NOT auto-passed; it carries
        x_sbk_result=False so an inspector has to act on it.
        """
        self.ensure_one()
        if self.x_sbk_reinspection_check_id:
            return self.x_sbk_reinspection_check_id
        reinspector = self._sbk_resolve_reinspector()
        defect_label = dict(
            self._fields["x_sbk_defect_type"].selection
        ).get(self.x_sbk_defect_type, _("defect"))
        followup = self.sudo().create({
            "name": _("Re-inspection: %(orig)s",
                      orig=self.name or self.id),
            "severity": "warning",
            "category": "production",
            "message": _("Re-inspect the rework for original NCR "
                         "'%(orig)s' (defect: %(d)s). Confirm the "
                         "defect is no longer present before the "
                         "part progresses.",
                         orig=self.name or self.id, d=defect_label),
            "recommendation": _("Inspect the reworked part. If it "
                                "still shows the defect, fail this "
                                "check and route again."),
            "production_id": self.production_id.id if self.production_id else False,
            "x_sbk_check_stage": self.x_sbk_check_stage,
            "x_sbk_defect_type": self.x_sbk_defect_type,
            "x_sbk_workorder_id": (
                self.x_sbk_rework_workorder_id.id
                if self.x_sbk_rework_workorder_id else False
            ),
            "x_sbk_inspector_id": reinspector.id if reinspector else False,
            "x_sbk_originating_check_id": self.id,
            "x_sbk_result": False,
        })
        self.write({
            "x_sbk_reinspection_state": "pending",
            "x_sbk_reinspection_check_id": followup.id,
        })
        # Best-effort dashboard ping — non-fatal.
        try:
            self.env["southbrook.ops.event"].emit(
                "override_flagged",
                _("Re-inspection check %(name)s spawned after rework "
                  "finish on %(orig)s (assigned to %(who)s)",
                  name=followup.name or "?",
                  orig=self.name or "?",
                  who=reinspector.name if reinspector else _("unassigned")),
                res_model="southbrook.mi.check",
                res_id=followup.id,
                severity="warn",
            )
        except Exception:  # noqa: BLE001
            pass
        return followup

    @api.onchange("x_sbk_defect_type")
    def _onchange_defect_type_suggests_rework_workcenter(self):
        """Defaulting rework_workcenter_id by defect type — the
        inspector still chooses, but a sensible default surfaces in
        the form. Mapping uses the southbrook_mrp_pm xml_ids since
        those are the stable shop-floor station refs.

        W041 (R5, 2026-06-27) — extended mapping to cover the four
        defect types that previously fell through to "no default":
          label_error       -> packing (PACK) — label is applied
                               at pack-out, so rework returns there.
          missing_component -> assembly (ASSY) — the missing part
                               needs to be installed at the assembly
                               cell, not re-cut/re-sanded.
          packaging_issue   -> packing (PACK) — re-pack the unit.
          other             -> QC — generic catch-all; QC triages.

        Existing mappings are unchanged.
        """
        mapping = {
            "scratch": "southbrook_mrp_pm.wc_sand",
            "finish_defect": "southbrook_mrp_pm.wc_paint",
            "edge_defect": "southbrook_mrp_pm.workcenter_edge",
            "hole_position": "southbrook_mrp_pm.workcenter_cnc_bore",
            "hardware_missing": "southbrook_mrp_pm.workcenter_hw",
            "hardware_alignment": "southbrook_mrp_pm.workcenter_hw",
            "assembly_square": "southbrook_mrp_pm.workcenter_assy",
            "wrong_dimension": "southbrook_mrp_pm.workcenter_saw",
            "wrong_material": "southbrook_mrp_pm.workcenter_saw",
            "grain_direction": "southbrook_mrp_pm.workcenter_saw",
            # W041 — previously-unmapped defect types.
            "label_error": "southbrook_mrp_pm.workcenter_pack",
            "missing_component": "southbrook_mrp_pm.workcenter_assy",
            "packaging_issue": "southbrook_mrp_pm.workcenter_pack",
            "other": "southbrook_mrp_pm.workcenter_qc",
        }
        ref = mapping.get(self.x_sbk_defect_type)
        if ref:
            self.x_sbk_rework_workcenter_id = self.env.ref(
                ref, raise_if_not_found=False)
