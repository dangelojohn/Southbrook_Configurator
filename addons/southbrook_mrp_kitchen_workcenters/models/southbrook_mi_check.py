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
    _inherit = "southbrook.mi.check"

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
    x_sbk_inspector_id = fields.Many2one(
        comodel_name="res.users",
        string="Inspector",
        default=lambda self: self.env.user,
    )
    x_sbk_date_checked = fields.Datetime(
        string="Date Checked",
        default=fields.Datetime.now,
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

    @api.onchange("x_sbk_defect_type")
    def _onchange_defect_type_suggests_rework_workcenter(self):
        """Defaulting rework_workcenter_id by defect type — the
        inspector still chooses, but a sensible default surfaces in
        the form. Mapping uses the southbrook_mrp_pm xml_ids since
        those are the stable shop-floor station refs."""
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
        }
        ref = mapping.get(self.x_sbk_defect_type)
        if ref:
            self.x_sbk_rework_workcenter_id = self.env.ref(
                ref, raise_if_not_found=False)
