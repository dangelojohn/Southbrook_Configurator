# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.kitchen.operation.template — reusable operation recipes.

An operation template describes ONE step on the kitchen-shop value
stream. It carries:

  - which work center it normally runs on (and what alternatives are
    valid under load)
  - how long it takes (the duration formula)
  - what material / finish gating applies
  - what skills are required to run it
  - what documents / instructions belong on the work-order traveler
  - whether QC is required at the end and whether rework is allowed

Operation templates are the building blocks routing engineers
compose into BoM routings (mrp.routing.workcenter records). The
templates themselves are master data — once seeded, they get
referenced by many routings without copy-paste.

M2 ships 15 representative templates (Design Review through Packing).
M4 will wire them into the demo BoMs so opening an MO shows the
realistic flow.
"""
import math

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


OPERATION_CATEGORIES = [
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


QUANTITY_DRIVERS = [
    ("fixed", "Fixed (base time only)"),
    ("panel_count", "Panel Count"),
    ("sheet_count", "Sheet Count"),
    ("edge_meters", "Total Edge-Band Meters"),
    ("surface_area_m2", "Surface Area (m²)"),
    ("hole_count", "Hole Count"),
    ("hinge_count", "Hinge Count"),
    ("drawer_count", "Drawer Count"),
    ("hardware_count", "Hardware Count"),
    ("cabinet_count", "Cabinet Count"),
    ("product_qty", "Product Quantity (MO qty)"),
    ("custom", "Custom (calling code supplies value)"),
]


class SouthbrookKitchenOperationTemplate(models.Model):
    _name = "southbrook.kitchen.operation.template"
    _description = "Southbrook Kitchen Operation Template"
    _order = "sequence, name"

    # ------------------------------------------------------------------
    # Identity + classification
    # ------------------------------------------------------------------
    name = fields.Char(required=True, index=True, translate=True)
    code = fields.Char(
        required=True, index=True,
        help="Stable short code used in xml_ids and routing references.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    operation_category = fields.Selection(
        OPERATION_CATEGORIES,
        required=True, index=True,
        help="High-level category — cross-checked against the target "
             "work center's x_sbk_station_type.",
    )

    # ------------------------------------------------------------------
    # Work-center routing
    # ------------------------------------------------------------------
    default_workcenter_id = fields.Many2one(
        comodel_name="mrp.workcenter",
        string="Default Work Center",
        help="Primary work center for this operation. The scheduler "
             "tries here first; falls back to alternative_workcenter_ids "
             "if the primary is overloaded or down.",
    )
    alternative_workcenter_ids = fields.Many2many(
        comodel_name="mrp.workcenter",
        relation="sbk_op_template_alt_wc_rel",
        column1="template_id", column2="workcenter_id",
        string="Alternative Work Centers",
    )

    # ------------------------------------------------------------------
    # Duration formula inputs
    # ------------------------------------------------------------------
    default_setup_time_min = fields.Float(
        string="Setup (min)", default=0.0,
        help="Time before the first unit is produced. Applied once per "
             "work order regardless of quantity.",
    )
    default_changeover_time_min = fields.Float(
        string="Changeover (min)", default=0.0,
        help="Time to swap tools / materials / colors from the previous "
             "work order. Applied once per work order.",
    )
    quantity_driver_type = fields.Selection(
        QUANTITY_DRIVERS,
        string="Quantity Driver",
        default="product_qty", required=True,
        help="Which MO/WO quantity is multiplied by minutes_per_unit. "
             "Pick the dimension that scales the work the most: panel-"
             "saw time scales by sheet_count; edge-banding by edge "
             "meters; drilling by hinge_count, etc.",
    )
    minutes_per_unit = fields.Float(
        string="Min/Unit", default=0.0,
        help="Minutes per unit of the quantity_driver_type. "
             "E.g. 6.0 min per sheet of melamine on the panel saw.",
    )
    material_adjustment_factor = fields.Float(
        string="Material Factor", default=1.0,
        help="Multiplier applied to the per-unit time component when "
             "the part's material differs from the template's "
             "default. 1.0 = no adjustment.",
    )
    finish_adjustment_factor = fields.Float(
        string="Finish Factor", default=1.0,
        help="Multiplier applied to the per-unit time component when "
             "the part's finish differs from the template's default.",
    )
    complexity_factor = fields.Float(
        string="Complexity Factor", default=1.0,
        help="Catch-all multiplier for jobs that the planner judges "
             "harder than baseline. 1.0 = standard; 1.5 = 50% slower.",
    )

    # ------------------------------------------------------------------
    # Capability gating
    # ------------------------------------------------------------------
    required_skill_ids = fields.Many2many(
        comodel_name="hr.skill",
        relation="sbk_op_template_skill_rel",
        column1="template_id", column2="skill_id",
        string="Required Operator Skills",
    )
    supported_material_ids = fields.Many2many(
        comodel_name="southbrook.kitchen.material",
        relation="sbk_op_template_material_rel",
        column1="template_id", column2="material_id",
        string="Supported Materials",
    )
    supported_finish_ids = fields.Many2many(
        comodel_name="southbrook.kitchen.finish",
        relation="sbk_op_template_finish_rel",
        column1="template_id", column2="finish_id",
        string="Supported Finishes",
    )

    # ------------------------------------------------------------------
    # Shop-floor + QC metadata
    # ------------------------------------------------------------------
    requires_qc = fields.Boolean(
        help="When True, the work-order completion gate requires at "
             "least one mi.check record before the next operation "
             "can start.",
    )
    qc_checklist = fields.Text(
        string="QC Checklist",
        help="Checklist items the QC inspector ticks off. Renders on "
             "the work-order traveler when requires_qc=True.",
    )
    required_documents = fields.Text(
        string="Required Documents",
        help="Drawings / CNC programs / instructions the operator "
             "must have on hand before starting (e.g. 'CAD drawing "
             "rev', 'CNC G-code file', 'cutting list').",
    )
    shop_floor_instruction = fields.Text(
        string="Shop-Floor Instruction",
        help="Free-form instructions for the operator. Renders on the "
             "work-order traveler.",
    )
    creates_rework_allowed = fields.Boolean(
        help="True if a failed QC on this operation can create a "
             "rework work order. False for operations where rework "
             "isn't meaningful (e.g. Packing).",
    )
    blocks_next_operation = fields.Boolean(
        default=True,
        help="True if the next operation cannot start until this one "
             "is done. False for parallel branches (e.g. carcass vs "
             "door finishing).",
    )

    notes = fields.Text()

    _sql_constraints = [
        ("name_uniq", "unique(name)", "Operation template name must be unique."),
        ("code_uniq", "unique(code)", "Operation template code must be unique."),
    ]

    # ==================================================================
    # Duration formula — the function the M4 mrp.workorder button calls.
    # ==================================================================

    @api.model
    def _safe_factor(self, value, default=1.0):
        """Return a sane multiplicative factor. None / 0 / negative
        all fall back to default so a single missing input never
        zeroes the whole formula."""
        try:
            v = float(value) if value is not None else default
        except (TypeError, ValueError):
            return default
        if v <= 0:
            return default
        return v

    def compute_expected_duration(
        self,
        driver_value=None,
        material_factor=None,
        finish_factor=None,
        complexity_factor=None,
        setup_time_min=None,
        changeover_time_min=None,
    ):
        """Return expected duration in minutes for this template.

        Per brief §9::

            expected_duration_min =
                setup + changeover
                + quantity_driver_value * minutes_per_unit
                  * material_factor * finish_factor * complexity_factor

        Rounded to the nearest minute (math.ceil so we never under-
        estimate). Never negative — the floor is 0.

        All keyword args are OPTIONAL overrides. When omitted, the
        template's own defaults are used. This is the contract M4
        relies on so mrp.workorder can pass per-WO inputs (specific
        sheet count, specific finish) without mutating the template.

        For quantity_driver_type=='fixed', driver_value is ignored —
        the result is setup + changeover only.
        """
        self.ensure_one()

        setup = max(
            setup_time_min if setup_time_min is not None
            else self.default_setup_time_min,
            0.0,
        )
        changeover = max(
            changeover_time_min if changeover_time_min is not None
            else self.default_changeover_time_min,
            0.0,
        )

        if self.quantity_driver_type == "fixed":
            total = setup + changeover
        else:
            driver = max(driver_value if driver_value is not None else 0.0, 0.0)
            per_unit = (
                driver
                * max(self.minutes_per_unit, 0.0)
                * self._safe_factor(material_factor, self.material_adjustment_factor)
                * self._safe_factor(finish_factor, self.finish_adjustment_factor)
                * self._safe_factor(complexity_factor, self.complexity_factor)
            )
            total = setup + changeover + per_unit

        # math.ceil so we never schedule less time than the formula
        # produces — a 7.2-min job takes 8 min on the planner's grid.
        return max(int(math.ceil(total)), 0)

    @api.constrains(
        "default_setup_time_min", "default_changeover_time_min",
        "minutes_per_unit",
        "material_adjustment_factor", "finish_adjustment_factor",
        "complexity_factor",
    )
    def _check_non_negative(self):
        """Setup / changeover / min-per-unit are minutes — never
        negative. Factors are multipliers — must be strictly > 0
        so the helper's _safe_factor fallback is the only path to
        a zero."""
        for tpl in self:
            for field_name in (
                "default_setup_time_min",
                "default_changeover_time_min",
                "minutes_per_unit",
            ):
                if tpl[field_name] < 0:
                    raise ValidationError(_(
                        "%s on %s must be >= 0 (got %s)."
                    ) % (field_name, tpl.name, tpl[field_name]))
            for field_name in (
                "material_adjustment_factor",
                "finish_adjustment_factor",
                "complexity_factor",
            ):
                if tpl[field_name] <= 0:
                    raise ValidationError(_(
                        "%s on %s must be > 0 (got %s)."
                    ) % (field_name, tpl.name, tpl[field_name]))
