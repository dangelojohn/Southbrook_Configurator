import math

from odoo import api, fields, models
from odoo.exceptions import UserError


class SouthbrookKitchenDesign(models.Model):
    _name = "southbrook.kitchen.design"
    _description = "Southbrook Kitchen Design"
    # 2026-06-28 — kitchen_design_views.xml renders `<chatter/>`, which
    # invokes `_get_thread_with_access` from mail.thread on every
    # form open. Without these mixins the RPC hits AttributeError
    # and the form fails to load.
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "write_date desc, id desc"
    _rec_name = "name"

    # ── Identity ────────────────────────────────────────────────────────────────
    # D4 — default kept generic; auto-rename happens at save-time in
    # the controller using the resolved partner + room dims + date so
    # the tree view stops collecting identical "New Kitchen Design"
    # rows.
    name = fields.Char(
        string="Design Name",
        required=True,
        default="New Kitchen Design",
    )
    partner_id  = fields.Many2one("res.partner",  string="Customer")
    sale_order_id = fields.Many2one("sale.order", string="Quotation", readonly=True)
    notes = fields.Text(string="Design Notes")

    # ── Room dimensions ─────────────────────────────────────────────────────────
    room_width_in  = fields.Float(string="Room Width (in)",  default=12.0,  required=True)
    room_depth_in  = fields.Float(string="Room Depth (in)",  default=24.0,  required=True)
    room_height_in = fields.Float(string="Room Height (in)", default=96.0,  required=True)

    # ── Layout lines ────────────────────────────────────────────────────────────
    cabinet_line_ids = fields.One2many(
        "southbrook.kitchen.design.line",
        "design_id",
        string="Cabinet Layout",
        copy=True,
    )

    # ── Computed summary ────────────────────────────────────────────────────────
    total_cabinets   = fields.Integer(compute="_compute_totals", store=True)
    estimated_price  = fields.Monetary(compute="_compute_totals", store=True)
    base_count       = fields.Integer(compute="_compute_totals", store=True)
    wall_count       = fields.Integer(compute="_compute_totals", store=True)
    remainder_in     = fields.Float(
        string="Remainder (in)",
        compute="_compute_totals",
        store=True,
        digits=(6, 2),
        help="Unused wall space after filling with standard 24-in modules.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )

    # ── D7 — Filler strategy ────────────────────────────────────────────────────
    filler_strategy = fields.Selection(
        selection=[
            ("split",  "Split (both ends)"),
            ("right",  "Right side"),
            ("left",   "Left side"),
            ("scribe", "Scribe (no filler)"),
        ],
        string="Filler Strategy",
        default="split",
        help=(
            "How to distribute the un-modular remainder across the cabinet run.\n"
            "Split: two half-width fillers, one at each end (most common).\n"
            "Right/Left: one filler at the chosen end.\n"
            "Scribe: no filler — the carpenter scribes the end cabinet on site."
        ),
    )

    # ── Workflow ────────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ("draft",      "Draft"),
            ("configured", "Configured"),
            ("quoted",     "Quoted"),
            ("ordered",    "Ordered"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )

    # ── Computed ────────────────────────────────────────────────────────────────
    @api.depends(
        "cabinet_line_ids.quantity",
        "cabinet_line_ids.price_unit",
        "cabinet_line_ids.cabinet_type",
        "room_width_in",
    )
    def _compute_totals(self):
        for design in self:
            lines = design.cabinet_line_ids
            base_lines = lines.filtered(lambda l: l.cabinet_type == "base")
            wall_lines = lines.filtered(lambda l: l.cabinet_type == "wall")
            design.base_count      = sum(base_lines.mapped("quantity"))
            design.wall_count      = sum(wall_lines.mapped("quantity"))
            design.total_cabinets  = sum(lines.mapped("quantity"))
            design.estimated_price = sum(
                l.quantity * l.price_unit for l in lines
            )
            # Remainder: width minus base cabinet modules
            module_w = 24.0
            bp = design._find_cabinet_product("base", raise_if_missing=False)
            if bp:
                module_w = bp.product_tmpl_id.southbrook_width_in or 24.0
            n = max(0, int(math.floor(design.room_width_in / module_w)))
            design.remainder_in = max(0.0, design.room_width_in - n * module_w)

    # ── Actions ─────────────────────────────────────────────────────────────────
    def action_generate_layout(self):
        """Regenerate the standard 24-in module layout from room dimensions."""
        for design in self:
            design._generate_standard_layout()
        return True

    def action_open_configurator(self):
        """Open the 3D Configurator pre-loaded with this design's dimensions.

        D3 — also forwards partner_id so the configurator resolves the
        channel pricelist (Dealer/Tradesperson/etc.) for live pricing,
        instead of always showing retail.
        """
        return {
            "type": "ir.actions.client",
            "tag":  "southbrook_kitchen_configurator",
            "params": {
                "design_id":      self.id,
                "design_name":    self.name,
                "room_width_in":  self.room_width_in,
                "room_depth_in":  self.room_depth_in,
                "room_height_in": self.room_height_in,
                "partner_id":     self.partner_id.id if self.partner_id else False,
            },
        }

    def action_create_quotation(self):
        SaleOrder = self.env["sale.order"]
        for design in self:
            if not design.partner_id:
                raise UserError("Select a customer before creating a quotation.")
            vals = {
                "partner_id": design.partner_id.id,
                "origin":     design.name,
                "note":       design.notes or "",
                "order_line": [
                    (0, 0, {
                        "product_id":      line.product_id.id,
                        "name":            line.product_id.display_name,
                        "product_uom_qty": line.quantity,
                        "price_unit":      line.price_unit,
                    })
                    for line in design.cabinet_line_ids
                ],
            }
            # 2026-06-28 Tier-A — resolve the channel pricelist BEFORE
            # create so the order opens on the right pricelist (Dealer
            # −50% / Tradesperson tier-3 −35% / etc.) instead of the
            # default retail. Without this, a Dealer customer who saw
            # $1,036 in the Order Builder would see $1,594 here.
            pricelist = SaleOrder._resolve_channel_pricelist(design.partner_id)
            if pricelist:
                vals["pricelist_id"] = pricelist.id
            order = SaleOrder.create(vals)
            design.sale_order_id = order.id
            design.state = "quoted"
        return {
            "type":      "ir.actions.act_window",
            "res_model": "sale.order",
            "res_id":    self.sale_order_id.id,
            "views":     [(False, "form")],
            "view_mode": "form",
            "target":    "current",
        }

    # ── Layout engine ────────────────────────────────────────────────────────────
    def _generate_standard_layout(self):
        """Fill the wall run with base + wall cabinet pairs, plus a filler if needed."""
        base_product = self._find_cabinet_product("base")
        wall_product = self._find_cabinet_product("wall")
        module_w = base_product.product_tmpl_id.southbrook_width_in or 24.0
        n = max(0, int(math.floor(self.room_width_in / module_w)))
        remainder = self.room_width_in - n * module_w

        self.cabinet_line_ids.unlink()
        seq = 10
        for i in range(n):
            x = i * module_w
            self._create_line(base_product, seq,      x, 0.0, 0.0)
            self._create_line(wall_product, seq + 5,  x, 0.0, 54.0)
            seq += 10

        # Filler panel for remainder
        if remainder >= 1.0:
            filler = self._find_cabinet_product("filler", raise_if_missing=False)
            if filler:
                self._create_line(filler, seq, n * module_w, 0.0, 0.0, qty=1,
                                   override_width=remainder)

        self.state = "configured"

    def _find_cabinet_product(self, cabinet_type, raise_if_missing=True):
        product = self.env["product.product"].search([
            ("product_tmpl_id.southbrook_is_cabinet", "=", True),
            ("product_tmpl_id.southbrook_cabinet_type", "=", cabinet_type),
            ("sale_ok", "=", True),
        ], limit=1)
        if not product and raise_if_missing:
            raise UserError(
                "No saleable %s cabinet product found. "
                "Go to Southbrook Kitchen > Cabinet Products and add one." % cabinet_type
            )
        return product or self.env["product.product"]

    def _create_line(self, product, sequence, x, y, z, qty=1, override_width=None):
        tmpl = product.product_tmpl_id
        return self.env["southbrook.kitchen.design.line"].create({
            "design_id":      self.id,
            "sequence":       sequence,
            "product_id":     product.id,
            "quantity":       qty,
            "price_unit":     product.lst_price,
            "cabinet_type":   tmpl.southbrook_cabinet_type,
            "width_in":       override_width or tmpl.southbrook_width_in or 24.0,
            "height_in":      tmpl.southbrook_height_in or 34.5,
            "depth_in":       tmpl.southbrook_depth_in or 24.0,
            "x_position_in":  x,
            "y_position_in":  y,
            "z_position_in":  z,
        })


class SouthbrookKitchenDesignLine(models.Model):
    _name = "southbrook.kitchen.design.line"
    _description = "Southbrook Kitchen Design Line"
    _order = "sequence, id"

    design_id = fields.Many2one(
        "southbrook.kitchen.design",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence    = fields.Integer(default=10)
    product_id  = fields.Many2one("product.product", required=True, string="Cabinet Product")
    quantity    = fields.Integer(default=1, required=True)
    price_unit  = fields.Monetary(required=True, string="Unit Price")
    currency_id = fields.Many2one(related="design_id.currency_id", store=True)

    cabinet_type = fields.Selection([
        ("base",   "Base Cabinet"),
        ("wall",   "Wall Cabinet"),
        ("tall",   "Tall Cabinet"),
        ("filler", "Filler Panel"),
        ("panel",  "Decorative Panel"),
        ("corner", "Corner Unit"),
    ], required=True)

    width_in  = fields.Float(required=True, digits=(6, 2))
    height_in = fields.Float(required=True, digits=(6, 2))
    depth_in  = fields.Float(required=True, digits=(6, 2))

    # 3D placement coordinates (inches from room origin)
    x_position_in = fields.Float(string="X Position (in)", digits=(6, 2))
    y_position_in = fields.Float(string="Y Position (in)", digits=(6, 2))
    z_position_in = fields.Float(string="Z Position (in)", digits=(6, 2))

    # Computed display
    position_label = fields.Char(
        string="Position",
        compute="_compute_position_label",
    )

    @api.depends("cabinet_type", "x_position_in", "z_position_in")
    def _compute_position_label(self):
        type_map = {
            "base": "Base", "wall": "Wall", "tall": "Tall",
            "filler": "Filler", "panel": "Panel", "corner": "Corner",
        }
        for line in self:
            label = type_map.get(line.cabinet_type, line.cabinet_type)
            line.position_label = "%s @ X=%.0f\"" % (label, line.x_position_in)
