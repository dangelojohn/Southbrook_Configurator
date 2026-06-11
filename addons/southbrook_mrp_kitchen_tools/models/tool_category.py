# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.tool.category — hierarchical tool / consumable classification.

The category drives policy decisions across the whole module:

* ``tool_family`` is the broad shape: saw_blade / cnc_router_bit /
  drill_bit / screw / adhesive / abrasive / spray_equipment / clamp /
  jig_fixture / lubricant / safety_ppe / etc. 32 families cover the
  whole kitchen / cabinet shop floor.
* ``directness`` is how the cost / control flow treats the item:
  direct_production_tool (consumed against a work order),
  direct_consumable, indirect_tool, indirect_consumable,
  maintenance_supply, safety_supply, spare_part.
* The policy booleans (``reusable``, ``consumable``, ``requires_stock``,
  ``requires_lot_tracking``, ``requires_maintenance``,
  ``requires_sharpening``, ``requires_calibration``,
  ``requires_cleaning``, ``has_expiry_date``, ``hazardous``,
  ``msds_required``) become defaults on every product attached to the
  category. Commit 4 reads them when deciding whether to block a work
  order on availability.

Categories are hierarchical (``parent_id`` / ``child_ids`` /
``complete_name``) so the data seed can ship a 3-level tree mirroring
the build brief sections A..K (Cutting Tools → Saw Blades → Panel Saw
Blades etc.).
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


# ─── Selection sources — also referenced from product_template.py ──────────
TOOL_FAMILY_SELECTION = [
    ("saw_blade", "Saw Blade"),
    ("cnc_router_bit", "CNC Router Bit"),
    ("drill_bit", "Drill Bit"),
    ("boring_bit", "Boring Bit"),
    ("countersink", "Countersink"),
    ("fastening_tool", "Fastening Tool"),
    ("fastener", "Fastener"),
    ("screw", "Screw"),
    ("adhesive", "Adhesive"),
    ("glue", "Glue"),
    ("abrasive", "Abrasive"),
    ("sanding_consumable", "Sanding Consumable"),
    ("finishing_tool", "Finishing Tool"),
    ("finishing_consumable", "Finishing Consumable"),
    ("spray_equipment", "Spray Equipment"),
    ("measuring_tool", "Measuring Tool"),
    ("layout_tool", "Layout Tool"),
    ("clamp", "Clamp"),
    ("jig_fixture", "Jig / Fixture"),
    ("hand_tool", "Hand Tool"),
    ("power_tool", "Power Tool"),
    ("pneumatic_tool", "Pneumatic Tool"),
    ("cutting_tool", "Cutting Tool"),
    ("polishing_tool", "Polishing Tool"),
    ("cleaning_supply", "Cleaning Supply"),
    ("lubricant", "Lubricant"),
    ("grease", "Grease"),
    ("oil", "Oil"),
    ("maintenance_supply", "Maintenance Supply"),
    ("spare_part", "Spare Part"),
    ("safety_ppe", "Safety / PPE"),
    ("packaging_tool", "Packaging Tool"),
    ("packaging_consumable", "Packaging Consumable"),
    ("other", "Other"),
]

DIRECTNESS_SELECTION = [
    ("direct_production_tool", "Direct Production Tool"),
    ("direct_consumable", "Direct Consumable"),
    ("indirect_tool", "Indirect Tool"),
    ("indirect_consumable", "Indirect Consumable"),
    ("maintenance_supply", "Maintenance Supply"),
    ("safety_supply", "Safety Supply"),
    ("spare_part", "Spare Part"),
]


class SouthbrookToolCategory(models.Model):
    _name = "southbrook.tool.category"
    _description = "Southbrook Tool / Consumable Category"
    _parent_name = "parent_id"
    _parent_store = True
    _order = "complete_name"
    _rec_name = "complete_name"

    # ─── Identity / hierarchy ─────────────────────────────────────────
    name = fields.Char(string="Name", required=True, translate=True)
    code = fields.Char(string="Code", index=True)
    complete_name = fields.Char(
        compute="_compute_complete_name", store=True, recursive=True,
    )
    parent_id = fields.Many2one(
        "southbrook.tool.category", string="Parent Category",
        ondelete="restrict", index=True,
    )
    parent_path = fields.Char(index=True, unaccent=False)
    child_ids = fields.One2many(
        "southbrook.tool.category", "parent_id", string="Sub-categories",
    )
    active = fields.Boolean(default=True)
    notes = fields.Text()

    # ─── Classification ──────────────────────────────────────────────
    tool_family = fields.Selection(
        TOOL_FAMILY_SELECTION,
        string="Tool Family",
        index=True,
        help="The broad shop-floor classification. Defaults to the parent "
             "category's family when blank.",
    )
    directness = fields.Selection(
        DIRECTNESS_SELECTION,
        string="Directness",
        index=True,
        help="How this category flows through cost and work-order control. "
             "Direct items are consumed against a specific work order; "
             "indirect items are shared overhead.",
    )

    # ─── Policy flags ────────────────────────────────────────────────
    reusable = fields.Boolean(
        string="Reusable",
        help="Items in this category are reusable assets — they get checked "
             "in/out of the tool crib rather than consumed.",
    )
    consumable = fields.Boolean(
        string="Consumable",
        help="Items in this category are issued and consumed (depleted) "
             "against work orders.",
    )
    requires_stock = fields.Boolean(
        string="Requires Stock",
        default=True,
        help="Track on-hand quantities in stock.",
    )
    requires_lot_tracking = fields.Boolean(
        string="Requires Lot Tracking",
        help="Each batch is tracked separately. Common for adhesives, "
             "glues, lacquers, paints — anything with shelf life or batch "
             "traceability.",
    )
    requires_serial_tracking = fields.Boolean(
        string="Requires Serial Tracking",
        help="Each unit is tracked individually. Common for expensive "
             "reusable assets like CNC tool holders, torque drivers, "
             "calibrated measuring tools.",
    )
    requires_maintenance = fields.Boolean(
        string="Requires Maintenance",
        help="The asset lifecycle includes recurring maintenance "
             "(sharpening, cleaning, lubrication, inspection).",
    )
    requires_sharpening = fields.Boolean(
        string="Requires Sharpening",
        help="Cutting edges that go to a sharpening service. Default for "
             "saw blades, CNC bits, drill / boring bits.",
    )
    requires_calibration = fields.Boolean(
        string="Requires Calibration",
        help="Measurement / torque tools that drift and need periodic "
             "calibration against a reference.",
    )
    requires_cleaning = fields.Boolean(
        string="Requires Cleaning",
        help="Cleaning required between operations (spray guns, glue pots, "
             "edge bander rollers).",
    )

    # ─── Expiry / hazard flags ───────────────────────────────────────
    has_expiry_date = fields.Boolean(
        string="Has Expiry Date",
        help="Material has a shelf life — readiness checks block on expired "
             "lots.",
    )
    hazardous = fields.Boolean(
        string="Hazardous",
        help="Flammable / toxic / regulated — surfaces the safety panel on "
             "work orders.",
    )
    msds_required = fields.Boolean(
        string="MSDS Required",
        help="Material Safety Data Sheet must be on file. Surfaces in QC "
             "and operator views as a documentation requirement.",
    )

    # ─── Replenishment defaults ──────────────────────────────────────
    default_uom_id = fields.Many2one(
        "uom.uom", string="Default UoM",
        help="Used when creating a new product against this category.",
    )
    default_issue_uom_id = fields.Many2one(
        "uom.uom", string="Default Issue UoM",
        help="The unit the shop floor issues — may differ from the "
             "purchase UoM (e.g. buy in kg, issue in g).",
    )
    default_reorder_min_qty = fields.Float(string="Default Min Qty")
    default_reorder_max_qty = fields.Float(string="Default Max Qty")

    # ─── Linkage defaults ────────────────────────────────────────────
    default_workcenter_ids = fields.Many2many(
        "mrp.workcenter",
        "southbrook_tool_cat_wc_rel",
        "category_id", "workcenter_id",
        string="Default Work Centers",
        help="Work centers where items in this category are typically used "
             "— pre-populates requirement records in commit 3.",
    )

    # ─── Inverse counts (read-only convenience) ─────────────────────
    product_count = fields.Integer(
        compute="_compute_product_count", string="Products",
    )

    # ──────────────────────────────────────────────────────────────────
    # Constraints
    # ──────────────────────────────────────────────────────────────────
    _sql_code_unique = models.Constraint(
        "UNIQUE(code)",
        "Tool category code must be unique.",
    )

    @api.constrains("parent_id")
    def _check_no_recursion(self):
        if self._has_cycle():
            raise ValidationError(_(
                "You cannot create recursive tool categories."))

    @api.constrains("reusable", "consumable")
    def _check_reusable_vs_consumable(self):
        for rec in self:
            if rec.reusable and rec.consumable:
                raise ValidationError(_(
                    "Category %s cannot be both reusable and consumable. "
                    "Pick one — reusable assets get checked in/out, "
                    "consumables get issued and depleted."
                ) % rec.complete_name)

    # ──────────────────────────────────────────────────────────────────
    # Compute
    # ──────────────────────────────────────────────────────────────────
    @api.depends("name", "parent_id.complete_name")
    def _compute_complete_name(self):
        for rec in self:
            if rec.parent_id:
                rec.complete_name = f"{rec.parent_id.complete_name} / {rec.name}"
            else:
                rec.complete_name = rec.name or ""

    def _compute_product_count(self):
        Product = self.env["product.template"]
        for rec in self:
            rec.product_count = Product.search_count(
                [("x_southbrook_tool_category_id", "=", rec.id)],
            )

    # ──────────────────────────────────────────────────────────────────
    # ORM helpers
    # ──────────────────────────────────────────────────────────────────
    def name_get(self):
        return [(c.id, c.complete_name) for c in self]

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        args = list(args or [])
        if name:
            recs = self.search(
                [("complete_name", operator, name)] + args, limit=limit,
            )
            return [(r.id, r.complete_name) for r in recs]
        return super().name_search(name, args, operator, limit)

    @api.onchange("parent_id")
    def _onchange_parent_inherits_family(self):
        """When the user picks a parent category, default the policy
        fields from it so admins don't have to re-type the same flags
        on every sub-category."""
        for rec in self:
            if rec.parent_id and not rec.tool_family:
                rec.tool_family = rec.parent_id.tool_family
            if rec.parent_id and not rec.directness:
                rec.directness = rec.parent_id.directness

    # ──────────────────────────────────────────────────────────────────
    # Action — view products in this category
    # ──────────────────────────────────────────────────────────────────
    def action_view_products(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Products in %s") % self.complete_name,
            "res_model": "product.template",
            "view_mode": "list,form",
            "domain": [("x_southbrook_tool_category_id", "=", self.id)],
            "context": {"default_x_southbrook_tool_category_id": self.id},
        }
