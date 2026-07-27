from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # ── Discovery flag ──────────────────────────────────────────────────────────
    southbrook_is_cabinet = fields.Boolean(
        string="Southbrook Cabinet",
        help="Marks this product as part of the Southbrook cabinet catalogue. "
             "Only marked products appear in the 3D Configurator.",
    )

    # ── Classification ──────────────────────────────────────────────────────────
    southbrook_cabinet_type = fields.Selection(
        selection=[
            ("base",   "Base Cabinet"),
            ("wall",   "Wall Cabinet"),
            ("tall",   "Tall Cabinet"),
            ("filler", "Filler Panel"),
            ("panel",  "Decorative Panel"),
            ("corner", "Corner Unit"),
            # Task 2 (kitchen templates): appliance-space stand-in products
            # (SBK-APPL-*). southbrook_is_cabinet stays False on them, so
            # they never appear in the drag catalog.
            ("appliance", "Appliance Space"),
        ],
        string="Cabinet Type",
    )

    # ── Physical dimensions ─────────────────────────────────────────────────────
    southbrook_width_in  = fields.Float(string="Width (in)",  default=24.0, digits=(6, 2))
    southbrook_height_in = fields.Float(string="Height (in)", default=34.5, digits=(6, 2))
    southbrook_depth_in  = fields.Float(string="Depth (in)",  default=24.0, digits=(6, 2))

    # ── Finish / material ───────────────────────────────────────────────────────
    southbrook_material = fields.Selection(
        selection=[
            ("white_melamine",  "White Melamine"),
            ("grey_melamine",   "Grey Melamine"),
            ("maple_veneer",    "Maple Veneer"),
            ("oak_veneer",      "Oak Veneer"),
            ("painted_mdf",     "Painted MDF"),
            ("thermoplastic",   "Thermoplastic"),
        ],
        string="Material / Finish",
        default="white_melamine",
    )
    southbrook_door_style = fields.Selection(
        selection=[
            ("slab",   "Slab"),
            ("shaker", "Shaker"),
            ("raised", "Raised Panel"),
        ],
        string="Door Style",
        default="shaker",
    )

    # ── Future 3D asset reference ───────────────────────────────────────────────
    southbrook_3d_asset_url = fields.Char(
        string="3D Asset URL (GLB/GLTF)",
        help="Optional link to a GLB or GLTF file for future photorealistic "
             "rendering. When present the configurator will substitute the box "
             "geometry with this model.",
    )

    # ── Computed helpers ────────────────────────────────────────────────────────
    southbrook_bom_available = fields.Boolean(
        string="BoM Available",
        compute="_compute_southbrook_bom_available",
        store=False,
    )

    @api.depends("bom_ids")
    def _compute_southbrook_bom_available(self):
        for tmpl in self:
            tmpl.southbrook_bom_available = bool(tmpl.bom_ids)
