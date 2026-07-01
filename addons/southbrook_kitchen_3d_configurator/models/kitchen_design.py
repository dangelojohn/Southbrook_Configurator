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

    # 2026-07-01 v19.0.4.19.0 — Kanban preview thumbnail.
    # Named x_kitchen_image (not kitchen_image) to adopt the existing
    # manual custom-field column already in the runtime DB without a
    # data migration. The pre-migrate at migrations/19.0.4.19.0/
    # deletes the ir_model_fields row so this code-defined field can
    # take ownership of the same column. fields.Image auto-creates
    # the thumbnail companions (x_kitchen_image_128/256/512/1024)
    # used by the list/kanban widgets.
    x_kitchen_image = fields.Image(
        string="Kitchen Preview",
        help="Screenshot of the 3D kitchen layout for at-a-glance identification.",
        max_width=800,
        max_height=600,
        attachment=True,
        store=True,
        copy=True,
    )

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

    # ── D8 — Wall-cabinet Z alignment + soffit ─────────────────────────────────
    soffit_height_in = fields.Float(
        string="Soffit Height (in)",
        default=84.0,
        digits=(6, 2),
        help=(
            "Bottom-of-soffit height (typical: 84\" for an 8' ceiling with a "
            "12\" soffit drop). Only consulted when wall_cab_top_alignment is "
            "'to_soffit'."
        ),
    )
    wall_cab_top_alignment = fields.Selection(
        selection=[
            ("fixed_gap",  "Fixed 18\" gap above counter"),
            ("to_ceiling", "Up to ceiling"),
            ("to_soffit",  "Up to soffit"),
        ],
        string="Wall Cabinet Top",
        default="fixed_gap",
        help=(
            "Drives the wall cabinet's Z position (bottom-of-cab).\n"
            "Fixed gap: industry standard 18\" between counter and wall-cab bottom.\n"
            "Up to ceiling: wall cab top touches ceiling (tall uppers).\n"
            "Up to soffit: wall cab top touches the soffit drop (8' ceiling specials)."
        ),
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
                "design_id":              self.id,
                "design_name":            self.name,
                "room_width_in":          self.room_width_in,
                "room_depth_in":          self.room_depth_in,
                "room_height_in":         self.room_height_in,
                "partner_id":             self.partner_id.id if self.partner_id else False,
                "filler_strategy":        self.filler_strategy or "split",
                "soffit_height_in":       self.soffit_height_in or 84.0,
                "wall_cab_top_alignment": self.wall_cab_top_alignment or "fixed_gap",
            },
        }

    # ── D12 — Production-readiness validation ──────────────────────────────────
    # Pre-quote checks that catch issues which would otherwise surface
    # in MO creation / cut-spec generation / on the shop floor. Returns
    # a flat list of {code, severity, message} dicts so the UI can
    # render them in priority order.
    #
    # Severities: blocking (refuses quote), warning (yellow), info.
    _STD_WIDTHS_IN = (6, 9, 12, 15, 18, 21, 24, 27, 30, 36, 42, 48)

    def _check_production_ready(self):
        self.ensure_one()
        issues = []

        # 1) Empty design = blocking
        if not self.cabinet_line_ids:
            issues.append({
                "code":     "EMPTY_DESIGN",
                "severity": "blocking",
                "message":  "Design has no cabinets. Add at least one before quoting.",
            })
            return issues

        # 2) Customer required
        if not self.partner_id:
            issues.append({
                "code":     "MISSING_CUSTOMER",
                "severity": "blocking",
                "message":  "Select a customer before quoting (needed for pricelist resolution).",
            })

        # 3) Collision detection per cabinet_type (skip fillers — they
        #    intentionally bridge gaps).
        by_type = {}
        for line in self.cabinet_line_ids:
            by_type.setdefault(line.cabinet_type, []).append(line)
        for ct, lines in by_type.items():
            if ct in ("filler", "panel"):
                continue
            ordered = sorted(lines, key=lambda l: l.x_position_in)
            for i in range(len(ordered) - 1):
                a, b = ordered[i], ordered[i + 1]
                if a.x_position_in + a.width_in > b.x_position_in + 0.01:
                    issues.append({
                        "code":     "CABINET_COLLISION",
                        "severity": "blocking",
                        "message":  (
                            "%s cabinets overlap at x=%.1f\": %s extends past %s start"
                        ) % (
                            ct.title(),
                            b.x_position_in,
                            a.product_id.display_name,
                            b.product_id.display_name,
                        ),
                    })

        # 4) BOM presence — required for MO generation. Check both
        #    template-level and variant-level BOMs.
        Bom = self.env["mrp.bom"]
        missing = set()
        for line in self.cabinet_line_ids:
            if line.cabinet_type in ("filler",):
                continue
            if not line.product_id:
                continue
            has_bom = Bom.sudo().search_count([
                "|",
                ("product_id", "=", line.product_id.id),
                "&",
                ("product_tmpl_id", "=", line.product_id.product_tmpl_id.id),
                ("product_id", "=", False),
            ], limit=1)
            if not has_bom:
                missing.add(line.product_id.display_name)
        if missing:
            issues.append({
                "code":     "MISSING_BOM",
                "severity": "blocking",
                "message":  "No BOM defined: %s" % ", ".join(sorted(missing)),
            })

        # 5) Non-standard widths — soft warning. Catches data-entry
        #    typos (37" instead of 36") that the shop floor can't
        #    nest cleanly.
        for line in self.cabinet_line_ids:
            if line.cabinet_type == "filler":
                continue
            if not line.width_in:
                continue
            wr = round(line.width_in)
            if abs(wr - line.width_in) < 0.01 and int(wr) not in self._STD_WIDTHS_IN:
                issues.append({
                    "code":     "NON_STANDARD_WIDTH",
                    "severity": "warning",
                    "message":  (
                        "%s is %d\" wide (non-standard; nesting/cutting may waste material)"
                    ) % (line.product_id.display_name, int(wr)),
                })

        # 6) Soffit/ceiling clearance — replicates the controller check
        #    so the form-level validate button matches the configurator.
        base_h, wall_h, ctr_t, gap = 34.5, 30.0, 1.5, 18.0
        for line in self.cabinet_line_ids:
            if line.cabinet_type == "base":
                base_h = max(base_h, line.height_in or base_h)
            elif line.cabinet_type == "wall":
                wall_h = max(wall_h, line.height_in or wall_h)
        if (self.wall_cab_top_alignment or "fixed_gap") == "to_soffit":
            eff_top = self.soffit_height_in or 0
        else:
            eff_top = self.room_height_in or 0
        # Use current wall-cab Z model for the check
        if self.wall_cab_top_alignment == "to_ceiling":
            wz = max(base_h + ctr_t + gap, (self.room_height_in or 0) - wall_h)
        elif self.wall_cab_top_alignment == "to_soffit":
            wz = max(base_h + ctr_t + gap, (self.soffit_height_in or 0) - wall_h)
        else:
            wz = base_h + ctr_t + gap
        if wz + wall_h > eff_top + 0.01 and eff_top > 0:
            issues.append({
                "code":     "WALL_CAB_EXCEEDS_CEILING",
                "severity": "blocking",
                "message":  (
                    "Wall cabinet top reaches %.1f\" but %s sits at %.1f\""
                ) % (wz + wall_h,
                     "soffit" if self.wall_cab_top_alignment == "to_soffit" else "ceiling",
                     eff_top),
            })

        # ── v19.0.4.22.0 audit P2#7 — extended production checks ──────

        # 7) Y-axis (front-back) depth collision — pairs of same-type
        #    cabs whose x AND y footprints both overlap. Catches L-run
        #    corner clashes and back-to-back islands the x-only check
        #    at (3) sees as "different runs".
        for ct, lines in by_type.items():
            if ct in ("filler", "panel"):
                continue
            for i in range(len(lines)):
                for j in range(i + 1, len(lines)):
                    a, b = lines[i], lines[j]
                    if a.x_position_in + (a.width_in or 0) <= b.x_position_in + 0.01:
                        continue
                    if b.x_position_in + (b.width_in or 0) <= a.x_position_in + 0.01:
                        continue
                    ay0, by0 = a.y_position_in or 0.0, b.y_position_in or 0.0
                    ay1 = ay0 + (a.depth_in or 0)
                    by1 = by0 + (b.depth_in or 0)
                    if ay1 <= by0 + 0.01 or by1 <= ay0 + 0.01:
                        continue
                    if (abs((a.depth_in or 0) - (b.depth_in or 0)) < 0.01
                            and abs(ay0 - by0) < 0.01):
                        continue  # pure x-clash, already flagged at (3)
                    issues.append({
                        "code":     "Y_AXIS_COLLISION",
                        "severity": "blocking",
                        "message":  (
                            "%s cabinets overlap front-back at x=%.1f\": "
                            "%s (d=%.1f\") vs %s (d=%.1f\")"
                        ) % (
                            ct.title(), a.x_position_in,
                            a.product_id.display_name, a.depth_in or 0,
                            b.product_id.display_name, b.depth_in or 0,
                        ),
                    })

        # 8) Z-axis collision — wall-cab vertical extent inside a tall's
        #    vertical extent. Bases don't clash with walls in z (they
        #    live on different run rows).
        for tall in by_type.get("tall", []):
            tx0 = tall.x_position_in
            tx1 = tx0 + (tall.width_in or 0)
            tz0 = tall.z_position_in or 0.0
            tz1 = tz0 + (tall.height_in or 0)
            for wall in by_type.get("wall", []):
                wx0 = wall.x_position_in
                wx1 = wx0 + (wall.width_in or 0)
                if wx1 <= tx0 + 0.01 or wx0 >= tx1 - 0.01:
                    continue
                wz0 = wall.z_position_in or 0.0
                wz1 = wz0 + (wall.height_in or 0)
                if wz1 <= tz0 + 0.01 or wz0 >= tz1 - 0.01:
                    continue
                issues.append({
                    "code":     "Z_AXIS_COLLISION",
                    "severity": "blocking",
                    "message":  (
                        "Wall %s (bottom %.1f\") intrudes into tall "
                        "%s (top %.1f\") at x=%.1f\""
                    ) % (
                        wall.product_id.display_name, wz0,
                        tall.product_id.display_name, tz1,
                        tall.x_position_in,
                    ),
                })

        # 9) Orphan filler — filler with no adjacent base/wall/tall
        #    within ±0.5" on either side. Fillers must bridge two
        #    cabinets, never sit alone.
        neighbours = [
            l for l in self.cabinet_line_ids
            if l.cabinet_type in ("base", "wall", "tall")
        ]
        for f in by_type.get("filler", []):
            fx0 = f.x_position_in or 0.0
            fx1 = fx0 + (f.width_in or 0)
            left = any(
                abs((c.x_position_in or 0) + (c.width_in or 0) - fx0) <= 0.5
                for c in neighbours
            )
            right = any(
                abs((c.x_position_in or 0) - fx1) <= 0.5 for c in neighbours
            )
            if not (left or right):
                issues.append({
                    "code":     "ORPHAN_FILLER",
                    "severity": "blocking",
                    "message":  (
                        "Filler %s at x=%.1f\" has no adjacent cabinet; "
                        "fillers must bridge two cabinets."
                    ) % (f.product_id.display_name, fx0),
                })

        # 10) End-cap panel adjacency — twin of the controller-side
        #     _validate_end_cap_panel_placement (controllers/main.py),
        #     escalated from WARN to BLOCKING per the audit. Follow-up:
        #     extract the pure algorithm to an @api.model classmethod
        #     so client + server share one implementation.
        panels = by_type.get("panel", [])
        if panels:
            hosts = [
                l for l in self.cabinet_line_ids
                if l.cabinet_type in ("base", "wall")
            ]
            valid_x = []
            for h in hosts:
                hx = h.x_position_in or 0.0
                hw = h.width_in or 0.0
                valid_x.append(hx + hw)   # right side of host
                for p in panels:
                    valid_x.append(hx - (p.width_in or 0))
            for p in panels:
                px = p.x_position_in or 0.0
                if not any(abs(px - v) <= 0.5 for v in valid_x):
                    issues.append({
                        "code":     "PANEL_WALL_ATTACH",
                        "severity": "blocking",
                        "message":  (
                            "End-cap panel %s at x=%.1f\" isn't adjacent "
                            "to any base/wall side face; panels can't "
                            "attach to room walls."
                        ) % (p.product_id.display_name, px),
                    })

        # 11) Unrealistic single-base width — warning (custom 60"+
        #     bases exist for eat-at-counter runs, but a 200" typo
        #     shouldn't burn the shop floor).
        for line in self.cabinet_line_ids:
            if line.cabinet_type != "base":
                continue
            if (line.width_in or 0) > 60.0:
                issues.append({
                    "code":     "UNREALISTIC_DIM",
                    "severity": "warning",
                    "message":  (
                        "%s is %.1f\" wide — over 60\" on a single base "
                        "is unusual; confirm not a typo."
                    ) % (line.product_id.display_name, line.width_in),
                })

        return issues

    def action_validate_production(self):
        """Form-button validator. Surfaces all issues in a notification
        toast — sticky if any blocking, transient otherwise."""
        self.ensure_one()
        issues = self._check_production_ready()
        if not issues:
            return {
                "type": "ir.actions.client",
                "tag":  "display_notification",
                "params": {
                    "type":    "success",
                    "title":   "Production-Ready",
                    "message": "No blocking issues. Ready to quote.",
                    "sticky":  False,
                },
            }
        blocking = [i for i in issues if i["severity"] == "blocking"]
        lines = []
        for i in issues:
            tag = "BLOCK" if i["severity"] == "blocking" else "WARN"
            lines.append("[%s] %s" % (tag, i["message"]))
        return {
            "type": "ir.actions.client",
            "tag":  "display_notification",
            "params": {
                "type":    "danger" if blocking else "warning",
                "title":   "Production check: %d issue(s)" % len(issues),
                "message": "\n".join(lines),
                "sticky":  True,
            },
        }

    # ── D11 — Enriched line name helper ────────────────────────────────────────
    # Renders a single-line spec the customer can recognise on the
    # quote: "Wall 2-Door | 24"W x 30"H x 12"D | Wall | Shaker | Maple
    # Veneer". Without this every quote line read "[BASE-24] Base
    # Cabinet" with all the config detail buried.
    def _quote_line_name(self, line):
        parts = [line.product_id.display_name]
        tmpl  = line.product_id.product_tmpl_id
        # Cabinet type label (Base / Wall / Tall / etc.)
        type_sel = dict(line._fields["cabinet_type"].selection or [])
        if line.cabinet_type:
            parts.append(type_sel.get(line.cabinet_type, line.cabinet_type).title())
        # Dimensions: drop trailing zeros from floats for readability.
        parts.append("%g\"W x %g\"H x %g\"D" % (
            line.width_in or 0, line.height_in or 0, line.depth_in or 0,
        ))
        # Door style + material from the product template.
        door_sel = dict(tmpl._fields["southbrook_door_style"].selection or [])
        mat_sel  = dict(tmpl._fields["southbrook_material"].selection or [])
        if tmpl.southbrook_door_style:
            parts.append(door_sel.get(tmpl.southbrook_door_style,
                                       tmpl.southbrook_door_style))
        if tmpl.southbrook_material:
            parts.append(mat_sel.get(tmpl.southbrook_material,
                                       tmpl.southbrook_material))
        return " | ".join(p for p in parts if p)

    # ── D11 — Duplicate-and-Open action ────────────────────────────────────────
    def action_duplicate_and_open(self):
        """Copy this design as draft and open the 3D Configurator on
        the new record. One click instead of Duplicate -> open."""
        self.ensure_one()
        copy = self.copy({"name": "%s (Copy)" % self.name, "state": "draft"})
        return copy.action_open_configurator()

    def action_create_quotation(self):
        SaleOrder = self.env["sale.order"]
        for design in self:
            if not design.partner_id:
                raise UserError("Select a customer before creating a quotation.")
            # D12 — Gate on production-readiness. Refuses to spawn a
            # quote when any blocking issue (collision, missing BOM,
            # wall-cab over ceiling) would burn the customer or the
            # shop floor later.
            issues = design._check_production_ready()
            blocking = [i for i in issues if i["severity"] == "blocking"]
            if blocking:
                msg = "\n".join("- %s" % i["message"] for i in blocking)
                raise UserError(
                    "Design isn't production-ready. Resolve these blocking "
                    "issues first:\n\n%s" % msg
                )
            # v19.0.4.22.0 audit P1#4 — Both `price_unit` AND
            # `pricelist_id` are set intentionally. The audit initially
            # flagged this as a double-discount landmine; a v19-source
            # investigation (see docs/southbrook_kitchen_audit_2026-07-01
            # .md §P1#4) proved Odoo's `_compute_price_unit` REPLACES
            # rather than stacks — an explicit `price_unit` in create()
            # is honoured and downstream recompute (from qty/partner/
            # product change) re-derives from `pricelist_id._get_
            # product_price(product, qty)` NOT from the current
            # `price_unit`. Zero arithmetic double-discount risk.
            #
            # Why keep BOTH:
            #   * `price_unit` — locks the design-time snapshot for
            #     `pricelist_refacing` customers whose pricelist has
            #     no items (priced via a Python routine, not pricelist
            #     items); a bare pricelist_id would auto-compute to
            #     `product.lst_price` (retail) — an accidental margin
            #     leak.
            #   * `pricelist_id` — needed for the rep's customer-flip
            #     workflow: swapping partner on the created SO triggers
            #     `_compute_price_unit` which re-derives from the new
            #     partner's channel. Standard Odoo semantics.
            vals = {
                "partner_id": design.partner_id.id,
                "origin":     design.name,
                "note":       design.notes or "",
                "order_line": [
                    (0, 0, {
                        "product_id":      line.product_id.id,
                        "name":            self._quote_line_name(line),
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
                "Go to Kitchen 3D Configurator > Cabinet Products and add one." % cabinet_type
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


# v19.0.4.22.0 audit P2#9 — Q21 zone lexicon (mirrors PUNCHLIST Q21
# on sale.order.line). Declared at module scope so search domains
# and future sale_order_line inheritance can reference the same list
# without duplicating the tuple.
ZONE_SELECTION = [
    ("base_run",  "Base Run"),
    ("wall",      "Wall"),
    ("tall",      "Tall"),
    ("island",    "Island"),
    ("accessory", "Accessory"),
    ("other",     "Other"),
]

_ZONE_FROM_CABINET_TYPE = {
    "base":   "base_run",
    "wall":   "wall",
    "tall":   "tall",
    "corner": "base_run",   # dominant case is base-run corner; user overrides for tall/wall corners
    "filler": "accessory",
    "panel":  "accessory",
}


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

    # ── D9 — Stable identity for non-destructive save_design ───────────────
    # layout_key matches the JS side's per-cabinet key (e.g. "base-3",
    # "wall-1", "filler-L"). origin distinguishes lines created by the
    # 3D configurator (which can be wiped + recreated on save) from
    # lines created in the backend form (which must NEVER be wiped by
    # a 3D save).
    layout_key = fields.Char(
        string="Layout Key",
        index=True,
        help="Stable identifier matching the 3D configurator's per-cabinet key.",
    )
    origin = fields.Selection(
        selection=[
            ("configurator", "3D Configurator"),
            ("manual",       "Manual / Backend"),
        ],
        string="Source",
        default="manual",
        required=True,
        help="Lines from the configurator can be replaced on re-save; "
             "manual lines are preserved across configurator saves.",
    )

    cabinet_type = fields.Selection([
        ("base",   "Base Cabinet"),
        ("wall",   "Wall Cabinet"),
        ("tall",   "Tall Cabinet"),
        ("filler", "Filler Panel"),
        ("panel",  "Decorative Panel"),
        ("corner", "Corner Unit"),
    ], required=True)

    # ── v19.0.4.22.0 audit P2#9 — Q21 zone tagging ─────────────────────
    # Mirrors the sale.order.line zone lexicon locked by PUNCHLIST Q21
    # so design lines can be aggregated per-zone in the Order Builder
    # without re-deriving from cabinet_type. Stored + indexed so it
    # groups/filters in views. readonly=False lets users override
    # (corner-wall cabinets, island bases, etc.).
    zone = fields.Selection(
        selection=ZONE_SELECTION,
        string="Zone",
        required=True,
        store=True,
        index=True,
        compute="_compute_zone",
        readonly=False,
        copy=True,
        default="base_run",
        help="Q21 zone grouping. Defaults from cabinet_type; override "
             "for island-mounted bases or corner-wall cabinets.",
    )
    zone_label = fields.Char(
        string="Zone Label",
        help="Free-text label surfaced when zone=Other "
             "(e.g. 'Butler's Pantry', 'Coffee Bar').",
    )

    width_in  = fields.Float(required=True, digits=(6, 2))
    height_in = fields.Float(required=True, digits=(6, 2))
    depth_in  = fields.Float(required=True, digits=(6, 2))

    # 3D placement coordinates (inches from room origin)
    x_position_in = fields.Float(string="X Position (in)", digits=(6, 2))
    y_position_in = fields.Float(string="Y Position (in)", digits=(6, 2))
    z_position_in = fields.Float(string="Z Position (in)", digits=(6, 2))

    # 2026-07-01 v19.0.4.20.0 — Smart-pinning (Option C).
    # `pinned` is flipped True the first time the user manually
    # drags or rotates this cabinet in the 3D configurator. Once
    # pinned, the client-side auto-pack (_recomputeLayoutFromItems)
    # and the server /layout regenerator both treat this line as
    # immovable: its x_position_in / z_position_in / rotation_deg
    # are the source of truth, and un-pinned neighbours pack around
    # it. `rotation_deg` is 0/90/180/270 (Y-axis) applied to the
    # cabinet's mesh in the scene and, when persisted, to the
    # nested BOM's rendered orientation.
    pinned = fields.Boolean(
        string="Manually Placed",
        default=False,
        copy=True,
        help="True when the user has manually dragged or rotated this "
             "cabinet; auto-layout will not move or reflow it.",
    )
    rotation_deg = fields.Float(
        string="Rotation (deg)",
        digits=(6, 2),
        default=0.0,
        copy=True,
        help="Y-axis rotation in degrees (0/90/180/270 in normal use).",
    )

    # Computed display
    position_label = fields.Char(
        string="Position",
        compute="_compute_position_label",
    )

    @api.depends("cabinet_type")
    def _compute_zone(self):
        for line in self:
            # Only backfill on empty; preserve any prior user override.
            if not line.zone:
                line.zone = _ZONE_FROM_CABINET_TYPE.get(
                    line.cabinet_type, "other",
                )

    @api.constrains("zone", "zone_label")
    def _check_zone_label_only_on_other(self):
        # Silently strip a stale label when the zone flips away from
        # 'other' — matches PUNCHLIST Q21 UX spec.
        for line in self:
            if line.zone != "other" and line.zone_label:
                line.zone_label = False

    @api.depends("cabinet_type", "x_position_in", "z_position_in")
    def _compute_position_label(self):
        type_map = {
            "base": "Base", "wall": "Wall", "tall": "Tall",
            "filler": "Filler", "panel": "Panel", "corner": "Corner",
        }
        for line in self:
            label = type_map.get(line.cabinet_type, line.cabinet_type)
            line.position_label = "%s @ X=%.0f\"" % (label, line.x_position_in)
