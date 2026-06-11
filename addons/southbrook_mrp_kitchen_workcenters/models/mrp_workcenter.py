# SPDX-License-Identifier: LGPL-3.0-only
"""mrp.workcenter — kitchen-specific configuration fields.

This module ADDS kitchen-shop configuration fields. It does NOT touch
the existing `x_mi_*` (Manufacturing Intelligence: live MO state) or
`southbrook_pm_*` (PM dashboard KPIs) fields shipped by
`southbrook_manufacturing_intelligence` and `southbrook_mrp_pm`.

Naming convention: every new field uses the `x_sbk_` prefix (Southbrook
Kitchen) so it grep-distinguishes from `x_mi_*` (live MI state) and the
unprefixed core `mrp.workcenter` fields.

Bottleneck note: `x_sbk_is_bottleneck` is a CONFIGURATION flag that
identifies a work center as a CONSTRAINT in the kitchen-shop value
stream (per Theory of Constraints). It is independent of
`x_mi_bottleneck_workcenter_id` on `mrp.production`, which records the
live bottleneck FOR A SPECIFIC MO at a moment in time. Both are
useful: the planner consults `x_sbk_is_bottleneck` to know which
stations she should never overload at scheduling; the dashboard
reads `x_mi_bottleneck_workcenter_id` to see where today's queue is.
"""
from odoo import fields, models


STATION_TYPES = [
    ("engineering", "Engineering / Design Review"),
    ("cutting", "Panel Cutting"),
    ("cnc", "CNC Routing"),
    ("edge_banding", "Edge Banding"),
    ("drilling", "Drilling / Boring"),
    ("sanding", "Sanding / Surface Prep"),
    ("finishing", "Paint / Lacquer / Finishing"),
    ("countertop", "Countertop Fabrication"),
    ("assembly", "Cabinet Assembly"),
    ("hardware", "Hardware Fitting"),
    ("quality", "Quality Control"),
    ("packing", "Packing / Dispatch"),
    ("subcontract", "Subcontract / Vendor Routing"),
    ("other", "Other"),
]


class MrpWorkcenter(models.Model):
    _inherit = "mrp.workcenter"

    # ------------------------------------------------------------------
    # Identity + capability
    # ------------------------------------------------------------------
    x_sbk_station_type = fields.Selection(
        STATION_TYPES,
        string="Kitchen Station Type",
        index=True,
        help="Taxonomy the operation-template engine (M2) consults to "
             "pick a work center for a given operation. Always set on "
             "kitchen-active work centers.",
    )
    x_sbk_machine_code = fields.Char(
        string="Machine Code",
        help="Vendor model number (e.g. 'SCM Olimpic K560', "
             "'Biesse Rover B FT 1224').",
    )
    x_sbk_machine_brand = fields.Char(
        string="Machine Brand",
        help="Vendor (e.g. SCM, Biesse, Holz-Her, Felder, Festool).",
    )
    x_sbk_supported_material_ids = fields.Many2many(
        comodel_name="southbrook.kitchen.material",
        relation="sbk_workcenter_material_rel",
        column1="workcenter_id", column2="material_id",
        string="Supported Materials",
        help="Operation templates check this set before routing a job "
             "here. A CNC tooled for melamine should not be sent solid "
             "wood; populating this prevents that at the scheduling layer.",
    )
    x_sbk_supported_finish_ids = fields.Many2many(
        comodel_name="southbrook.kitchen.finish",
        relation="sbk_workcenter_finish_rel",
        column1="workcenter_id", column2="finish_id",
        string="Supported Finishes",
    )
    x_sbk_required_skill_ids = fields.Many2many(
        comodel_name="hr.skill",
        relation="sbk_workcenter_skill_rel",
        column1="workcenter_id", column2="skill_id",
        string="Required Operator Skills",
        help="Reuses Odoo's hr.skill. The shop-floor planner can cross-"
             "reference operator skills (hr.employee.employee_skill_ids) "
             "to figure out who can be assigned here.",
    )

    # ------------------------------------------------------------------
    # Capacity envelope
    # ------------------------------------------------------------------
    x_sbk_max_panel_length_mm = fields.Float(
        string="Max Panel Length (mm)",
        help="Longest panel the work center can accept on the in-feed. "
             "A 2440mm panel saw bed limits everything downstream.",
    )
    x_sbk_max_panel_width_mm = fields.Float(
        string="Max Panel Width (mm)",
        help="Widest panel the work center can accept.",
    )
    x_sbk_default_setup_time_min = fields.Float(
        string="Default Setup (min)",
        help="Minutes added per work order when a job lands fresh on "
             "this station. Operation templates (M2) can override.",
    )
    x_sbk_changeover_time_min = fields.Float(
        string="Changeover (min)",
        help="Minutes when an operation changes material/finish/tool "
             "from the previous WO. Paint-color changeover is the big "
             "case at the Booth.",
    )
    x_sbk_allows_parallel_jobs = fields.Boolean(
        help="True when the station can have multiple work orders in "
             "flight at once (e.g. Cure / Dry Room runs many panels "
             "simultaneously; the panel saw does one cut at a time).",
    )

    # ------------------------------------------------------------------
    # Planning + reporting metadata
    # ------------------------------------------------------------------
    x_sbk_is_bottleneck = fields.Boolean(
        string="Bottleneck (Configuration)",
        help="ToC-style configuration flag: True identifies this "
             "station as a structural bottleneck in the value stream. "
             "The scheduler uses this to never overload it. SEPARATE "
             "from the existing x_mi_bottleneck_workcenter_id on "
             "mrp.production, which is the LIVE bottleneck for a "
             "specific MO at a moment in time.",
    )
    x_sbk_oee_target = fields.Float(
        string="OEE Target",
        default=0.85,
        help="Overall Equipment Effectiveness target — 0.0..1.0 — used "
             "as the benchmark for KPI tiles. 0.85 = 85% (industry-"
             "standard 'world-class' threshold).",
    )

    # ------------------------------------------------------------------
    # Free-form planning notes (different audiences)
    # ------------------------------------------------------------------
    x_sbk_planning_notes = fields.Text(
        string="Planning Notes",
        help="Scheduler-facing — capacity caveats, blackout windows, "
             "lead times to onboard a new operator, etc.",
    )
    x_sbk_shop_floor_notes = fields.Text(
        string="Shop-Floor Notes",
        help="Operator-facing — setup steps, tool changes, safety call-"
             "outs. Renders on the work-order traveler.",
    )
    x_sbk_quality_notes = fields.Text(
        string="Quality Notes",
        help="QC-facing — common defect modes, inspection points, "
             "tolerances. Wired into M3's mi.check defect lookup.",
    )

    x_sbk_active_for_kitchen = fields.Boolean(
        string="Active for Kitchen Production",
        default=True,
        help="False to hide this work center from the kitchen MRP "
             "menus + filters without deactivating it for non-kitchen "
             "MOs. Useful when a station is shared with another "
             "Southbrook product line.",
    )
