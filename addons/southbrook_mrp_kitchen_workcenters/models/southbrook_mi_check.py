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
from odoo import api, fields, models


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

    @api.depends("x_sbk_result")
    def _compute_rework_required(self):
        for check in self:
            check.x_sbk_rework_required = check.x_sbk_result in (
                "fail", "rework",
            )

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
