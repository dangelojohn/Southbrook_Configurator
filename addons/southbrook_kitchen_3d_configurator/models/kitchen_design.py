import json
import logging
import math

from odoo import api, fields, models
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


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

    # ── Archive flag ────────────────────────────────────────────────────────────
    # 2026-07-01 task #49 — enables Odoo's standard archive/unarchive UX so
    # historical designs (state=quoted/ordered) can be hidden from the
    # default list without breaking the sale.order / mrp.production audit
    # trail via unlink. tracking=True posts a chatter note on state flip
    # (mail.thread is already inherited above); ir.rule / views filter on
    # active automatically per Odoo convention.
    active = fields.Boolean(default=True, tracking=True)

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
    partner_id  = fields.Many2one("res.partner",  string="Customer", index=True)
    sale_order_id = fields.Many2one(
        "sale.order", string="Quotation", readonly=True, index=True)
    notes = fields.Text(string="Design Notes")

    # ── Recommendation D · Sprint 1 bridge field ────────────────────────
    # Points at the southbrook.room record the reconciliation cron
    # mirrors this design into. In Sprint 1 the design remains the
    # authoring record and rooms are the mirror; Sprint 2 flips the
    # direction; Sprint 3 retires this model entirely and only the
    # room + sale.order.line + product.config.session graph remains.
    room_id = fields.Many2one(
        "southbrook.room",
        string="Bridged Room",
        index=True,
        ondelete="set null",
        copy=False,
        help="Rec D Sprint 1 — non-authoring mirror onto the unified "
             "room + wall + line graph. Managed by the "
             "southbrook.design.reconcile cron. Do not set manually.",
    )

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

    # ── default_get — portal-user partner autofill ─────────────────────────────
    # 2026-07-01 task #48 — pre-select partner_id for two entry paths:
    #   (a) partner-form "Create Kitchen Design" → context carries
    #       default_partner_id already; we just honour it explicitly here
    #       so the field pre-fills without a computed default.
    #   (b) portal-user opens /my/ frontend → self.env.user.share is True
    #       and their own partner is the only sensible pre-fill (they
    #       cannot design for someone else through the portal).
    # Internal users hit neither branch — vals["partner_id"] stays empty
    # so the customer picker (Agent C's canvas) drives selection instead.
    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        if "partner_id" in fields_list and not vals.get("partner_id"):
            ctx_partner = self.env.context.get("default_partner_id")
            if ctx_partner:
                vals["partner_id"] = ctx_partner
            elif self.env.user.share:
                # Portal user (share=True) — auto-set their own partner
                vals["partner_id"] = self.env.user.partner_id.id
        return vals

    # ── unlink guard — protect quoted / ordered designs ────────────────────────
    # 2026-07-01 task #49 — prevent accidental data loss. Designs linked
    # to a sale.order or mrp.production must remain queryable for
    # auditability; users archive instead of delete.
    def unlink(self):
        protected = self.filtered(lambda d: d.state in ("quoted", "ordered"))
        if protected:
            raise UserError(
                "Cannot delete kitchen design(s): %s\n\n"
                "Designs with state 'quoted' or 'ordered' must be archived "
                "instead. Use the ⚙️ Actions menu → Archive to hide them from "
                "the default list. Archived designs remain linked to their "
                "sale.order and mrp.production records for auditability."
                % ", ".join(protected.mapped("name"))
            )
        return super().unlink()

    # ── Bulk archive action ────────────────────────────────────────────────────
    # 2026-07-01 task #49 — wired to list-view multi-select bulk action
    # by Agent B (views/kitchen_design_views.xml). Flips active=False in
    # a single write() and reloads so the archived rows drop off the
    # (active=True) default filter.
    def action_archive_bulk(self):
        self.write({"active": False})
        return {"type": "ir.actions.client", "tag": "reload"}

    # ── Recent-partners picker feed ────────────────────────────────────────────
    # 2026-07-01 task #48 — feeds the 3D canvas customer picker's
    # "Recently used" autocomplete section. Sourced from the current
    # user's own recent designs (order=write_date desc) so the rep sees
    # partners they've been working with lately without having to re-type
    # partner names. Invoked from Agent C's territory via RPC.
    # v19.0.5.6.7 — public name (no leading underscore) so the method is
    # reachable via /web/dataset/call_kw from the 3D canvas. Odoo 17+ blocks
    # RPC to `_`-prefixed methods as a security convention.
    @api.model
    def get_recent_partners_for_picker(self, limit=10):
        """Feed the 3D canvas customer picker with a recency-sorted list."""
        # Own designs first
        own_designs = self.search([
            ("create_uid", "=", self.env.uid),
            ("partner_id", "!=", False),
        ], limit=50, order="write_date desc")
        partners = own_designs.mapped("partner_id")
        # Deduplicate while preserving order
        seen, out = set(), []
        for p in partners:
            if p.id not in seen:
                seen.add(p.id)
                out.append({
                    "id": p.id,
                    "name": p.name,
                    "channel": getattr(p, "channel", None) or "",
                })
            if len(out) >= limit:
                break
        return out

    # ── Walk-in customer partner ───────────────────────────────────────────────
    # 2026-07-01 task #48 — anonymous / walk-in quote support. Called
    # by Agent C's frontend when the rep picks "Walk-in" from the
    # customer picker; returns the id of the singleton "Walk-in
    # Customer" partner (created lazily on first use). Kept as a
    # company partner + customer_rank=1 so it resolves the retail
    # pricelist correctly and shows up in customer searches.
    # v19.0.5.6.7 — public name for RPC accessibility (see get_recent_partners
    # comment above).
    @api.model
    def get_or_create_walkin_partner(self):
        Partner = self.env["res.partner"]
        walkin = Partner.search([
            ("name", "=", "Walk-in Customer"),
            ("is_company", "=", True),
        ], limit=1)
        if not walkin:
            walkin = Partner.create({
                "name": "Walk-in Customer",
                "is_company": True,
                "customer_rank": 1,
                "comment": "Generic partner for showroom walk-in quotes. "
                           "Replace with the real customer once identified.",
            })
        return walkin.id

    # ── Open linked Sale Order (Agent B smart button target) ───────────────────
    # 2026-07-01 task #48 — wire target for the "Quote" oe_stat_button on the
    # design form. If sale_order_id is unset returns a warning notification
    # instead of a broken action.
    def action_open_sale_order(self):
        self.ensure_one()
        if not self.sale_order_id:
            return {
                "type":  "ir.actions.client",
                "tag":   "display_notification",
                "params": {
                    "type":    "info",
                    "title":   "No quotation yet",
                    "message": "This design has no linked Sale Order. Click "
                               "'Create Quotation' or 'Create & Confirm →' to "
                               "create one.",
                    "sticky": False,
                },
            }
        return {
            "type":      "ir.actions.act_window",
            "res_model": "sale.order",
            "res_id":    self.sale_order_id.id,
            "views":     [(False, "form")],
            "view_mode": "form",
            "target":    "current",
        }

    # ── Reset stale quote link (safety valve) ──────────────────────────────────
    # 2026-07-02 — Design #15 currently points at S01314, a stale draft
    # from an earlier failed attempt. Re-clicking "Create Quotation" or
    # "Create & Confirm →" today would try to reuse that link's
    # downstream logic. This provides a rep-visible unlink action that
    # clears sale_order_id (design falls back to state=configured) so
    # the design can be re-quoted. Ordered designs are protected — they
    # must stay linked for the manufacturing/delivery audit trail.
    def action_reset_quote_link(self):
        """Clear the sale_order_id link and revert state to configured.

        Used when a prior "Create Quotation" left the design pointing at
        a stale draft SO the rep decided not to pursue. Does NOT delete
        the underlying sale.order — that's a separate action from the SO
        surface.
        """
        self.ensure_one()
        if self.state == "ordered":
            raise UserError(
                "Cannot reset a design that has been ordered. Ordered "
                "designs must remain linked to their sale.order for the "
                "manufacturing / delivery audit trail."
            )
        prior = self.sale_order_id
        self.write({"sale_order_id": False, "state": "configured"})
        if prior:
            self.message_post(body=(
                "Quote link reset by %s. Previously linked to: %s. "
                "Design is now free to be re-quoted."
            ) % (self.env.user.name, prior.name))
        return {"type": "ir.actions.client", "tag": "reload"}

    # ── Send linked quotation by email (UX shortcut) ───────────────────────────
    def action_send_quote_email(self):
        """Open Odoo's standard email composer prepopulated with the
        linked sale.order quotation.

        2026-07-02 UX shortcut — replaces a 3-click nav (design →
        quote → Send by Email) with a single button on the design.
        Requires sale_order_id to be set. Delegates to the standard
        sale.order.action_quotation_send which knows the correct
        email template + mail composer args.
        """
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError(
                "This design has no linked quotation yet. Click 'Create "
                "Quotation' or 'Create & Confirm →' first, then use this "
                "button to send it by email."
            )
        return self.sale_order_id.action_quotation_send()

    # ── Computed ────────────────────────────────────────────────────────────────
    # M1 fix (2026-07-06) — root cause: this compute only ever looked at
    # cabinet_line_ids (the design's own drag-editor layout). When cabinets
    # are added directly onto the linked sale.order's lines (bypassing
    # "Generate Layout"), cabinet_line_ids stays empty and the summary card
    # showed "0 cabinets / $0.00" even though the order itself has real
    # cabinet lines. Fix: depend on the order's cabinet-product line fields
    # too, and when the design has no configurator-authored lines of its
    # own, fall back to summing the linked sale.order's cabinet product
    # lines (southbrook_is_cabinet=True products only) so the summary is
    # never simply wrong. Does NOT touch cabinet_line_ids, Generate Layout,
    # or the drag-editor — this only affects the read-only summary fields.
    @api.depends(
        "cabinet_line_ids.quantity",
        "cabinet_line_ids.price_unit",
        "cabinet_line_ids.cabinet_type",
        "room_width_in",
        "sale_order_id",
        "sale_order_id.order_line.product_uom_qty",
        "sale_order_id.order_line.price_subtotal",
        "sale_order_id.order_line.product_id",
    )
    def _compute_totals(self):
        for design in self:
            lines = design.cabinet_line_ids
            if lines:
                base_lines = lines.filtered(lambda l: l.cabinet_type == "base")
                wall_lines = lines.filtered(lambda l: l.cabinet_type == "wall")
                design.base_count      = sum(base_lines.mapped("quantity"))
                design.wall_count      = sum(wall_lines.mapped("quantity"))
                design.total_cabinets  = sum(lines.mapped("quantity"))
                design.estimated_price = sum(
                    l.quantity * l.price_unit for l in lines
                )
            else:
                # No configurator-origin cabinet lines yet — fall back to
                # the linked order's own cabinet product lines so the
                # summary card reflects reality instead of showing zero.
                order_lines = design.sale_order_id.order_line.filtered(
                    lambda l: l.product_id.product_tmpl_id.southbrook_is_cabinet
                )
                base_ol = order_lines.filtered(
                    lambda l: l.product_id.product_tmpl_id.southbrook_cabinet_type == "base"
                )
                wall_ol = order_lines.filtered(
                    lambda l: l.product_id.product_tmpl_id.southbrook_cabinet_type == "wall"
                )
                design.base_count      = sum(base_ol.mapped("product_uom_qty"))
                design.wall_count      = sum(wall_ol.mapped("product_uom_qty"))
                design.total_cabinets  = sum(order_lines.mapped("product_uom_qty"))
                design.estimated_price = sum(order_lines.mapped("price_subtotal"))
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

    @api.model
    def action_open_from_sale_order(self, order_id):
        """Rec D Sprint 2c · reverse-lookup helper.

        Called by the "Open in 3D" button on sale.order form. Finds
        the linked design (via sale_order_id) and opens its
        configurator. If no design exists yet but the SO has a
        southbrook.room, delegates to room.action_open_kitchen_3d
        so the rep can still design against the room's dimensions.
        """
        order = self.env["sale.order"].browse(int(order_id or 0))
        if not order.exists():
            return False
        design = self.search([("sale_order_id", "=", order.id)], limit=1)
        if design:
            return design.action_open_configurator()
        room = order.room_ids[:1]
        if room:
            return room.action_open_kitchen_3d()
        # Neither design nor room — spin up a bare configurator.
        return {
            "type":   "ir.actions.client",
            "tag":    "southbrook_kitchen_configurator",
            "params": {
                "partner_id": order.partner_id.id if order.partner_id else False,
            },
        }

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

        # 2) Customer required — message polished 2026-07-01 task #48
        # from "Select a customer before quoting (needed for pricelist
        # resolution)." to a customer-safe phrasing that surfaces the
        # Walk-in escape hatch (the picker Agent C wires into the 3D
        # canvas resolves 'Walk-in' via _get_or_create_walkin_partner).
        if not self.partner_id:
            issues.append({
                "code":     "MISSING_CUSTOMER",
                "severity": "blocking",
                "message":  "This design needs a customer before it can become a quote. "
                            "Assign a Customer at the top of the form (or, for a walk-in, "
                            "pick 'Walk-in Customer').",
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

    # ── v19.0.5.6.12 — Template gallery (customer-onboarding) ─────────────
    # Biggest UX win for first-time users: instead of an empty canvas the
    # rep/customer picks one of four preset layouts (Empty / L / U /
    # Galley) which pre-seeds room dimensions AND (for the shaped
    # presets) fills the primary wall run with canonical cabinets from
    # southbrook_estimating. Users iterate from a starting point, not
    # from a blank page.
    #
    # Sizes below are inches to match the model's existing inch-native
    # fields (room_width_in / room_depth_in / room_height_in). The
    # room_length_mm equivalents from the design brief (3600×3000×2400 mm
    # etc.) are converted to nearest round US kitchen dimensions
    # (12'/10'/8') because Southbrook's shop floor cuts to inches.
    _KITCHEN_TEMPLATE_PRESETS = {
        "empty": {
            "name":           "Empty Room",
            "description":    "Blank canvas — 12' × 10' room, no cabinets. "
                              "Best when the customer wants full creative "
                              "control from the first click.",
            "room_width_in":  144.0,   # 3658 mm ≈ 3600 mm target
            "room_depth_in":  120.0,   # 3048 mm ≈ 3000 mm target
            "room_height_in": 96.0,    # 2438 mm ≈ 2400 mm target
            "generate_layout": False,
            "starter_cabinets": [],
        },
        "l_shape": {
            "name":           "L-Shaped Kitchen",
            "description":    "12' × 12' room with an L-run of cabinets: "
                              "long primary wall + short return leg. Classic "
                              "starter layout for corner kitchens.",
            "room_width_in":  144.0,
            "room_depth_in":  144.0,
            "room_height_in": 96.0,
            "generate_layout": True,
            # xmlids are seeded via southbrook_estimating; missing xmlids
            # degrade to a chatter warning (see _apply_kitchen_template).
            "starter_cabinets": [
                # Primary wall (y=0) — base row of 5 cabinets (24" ea)
                ("southbrook_estimating.sink_base",  "base", 24.0,  0.0, 0.0,  0),
                ("southbrook_estimating.base_2dr",   "base", 48.0,  0.0, 0.0, 10),
                ("southbrook_estimating.drawer_bank","base", 72.0,  0.0, 0.0, 20),
                ("southbrook_estimating.base_1dr",   "base", 96.0,  0.0, 0.0, 30),
                ("southbrook_estimating.corner",     "base", 120.0, 0.0, 0.0, 40),
                # Wall cabinets over primary wall (z=54")
                ("southbrook_estimating.wall_2dr",   "wall", 24.0,  0.0, 54.0, 50),
                ("southbrook_estimating.wall_2dr",   "wall", 72.0,  0.0, 54.0, 60),
                ("southbrook_estimating.wall_1dr",   "wall", 96.0,  0.0, 54.0, 70),
                # Short return leg (x=0, y offset)
                ("southbrook_estimating.tall_pantry","tall", 0.0,   30.0, 0.0, 80),
            ],
        },
        "u_shape": {
            "name":           "U-Shaped Kitchen",
            "description":    "12' × 10' room with cabinets on three walls: "
                              "prep zone + return legs. Best for busy family "
                              "kitchens and dedicated cooking work-triangles.",
            "room_width_in":  144.0,
            "room_depth_in":  120.0,
            "room_height_in": 96.0,
            "generate_layout": True,
            "starter_cabinets": [
                # Back wall (y=0) — 6 base cabinets, 24" each = 144"
                ("southbrook_estimating.base_1dr",   "base", 0.0,   0.0, 0.0,  0),
                ("southbrook_estimating.base_2dr",   "base", 24.0,  0.0, 0.0, 10),
                ("southbrook_estimating.sink_base",  "base", 48.0,  0.0, 0.0, 20),
                ("southbrook_estimating.drawer_bank","base", 72.0,  0.0, 0.0, 30),
                ("southbrook_estimating.base_2dr",   "base", 96.0,  0.0, 0.0, 40),
                ("southbrook_estimating.base_1dr",   "base", 120.0, 0.0, 0.0, 50),
                # Wall cabinets over back wall
                ("southbrook_estimating.wall_2dr",   "wall", 0.0,   0.0, 54.0, 60),
                ("southbrook_estimating.wall_2dr",   "wall", 48.0,  0.0, 54.0, 70),
                ("southbrook_estimating.wall_2dr",   "wall", 96.0,  0.0, 54.0, 80),
                # Left return leg
                ("southbrook_estimating.tall_pantry","tall", 0.0,   30.0, 0.0, 90),
                # Right return leg
                ("southbrook_estimating.tall_oven",  "tall", 120.0, 30.0, 0.0, 100),
            ],
        },
        "galley": {
            "name":           "Galley Kitchen",
            "description":    "12' × 8' narrow room with two parallel cabinet "
                              "runs. Efficient for apartments, secondary "
                              "kitchens, and butlers' pantries.",
            "room_width_in":  144.0,
            "room_depth_in":  96.0,
            "room_height_in": 96.0,
            "generate_layout": True,
            "starter_cabinets": [
                # Back run (y=0) — 6 base + 3 wall
                ("southbrook_estimating.sink_base",  "base", 0.0,   0.0, 0.0,  0),
                ("southbrook_estimating.base_2dr",   "base", 24.0,  0.0, 0.0, 10),
                ("southbrook_estimating.drawer_bank","base", 48.0,  0.0, 0.0, 20),
                ("southbrook_estimating.base_2dr",   "base", 72.0,  0.0, 0.0, 30),
                ("southbrook_estimating.base_1dr",   "base", 96.0,  0.0, 0.0, 40),
                ("southbrook_estimating.base_1dr",   "base", 120.0, 0.0, 0.0, 50),
                ("southbrook_estimating.wall_2dr",   "wall", 0.0,   0.0, 54.0, 60),
                ("southbrook_estimating.wall_2dr",   "wall", 48.0,  0.0, 54.0, 70),
                ("southbrook_estimating.wall_2dr",   "wall", 96.0,  0.0, 54.0, 80),
                # Front run (parallel, y offset — 12" gap for the aisle)
                ("southbrook_estimating.base_2dr",   "base", 24.0,  72.0, 0.0, 90),
                ("southbrook_estimating.base_2dr",   "base", 72.0,  72.0, 0.0, 100),
            ],
        },
    }

    @api.model
    def _get_preset_layout(self, preset):
        """Return the preset dict for `preset` or None if the key is
        unknown. Public helper so tests + the wizard can introspect the
        catalog without duplicating the source of truth.

        Preset keys: 'empty', 'l_shape', 'u_shape', 'galley'.
        """
        return self._KITCHEN_TEMPLATE_PRESETS.get(preset)

    def _apply_kitchen_template(self, preset):
        """Seed room dimensions + starter cabinets from a preset spec.

        Called after `create()` by the wizard. Missing cabinet xmlids
        (e.g. installs without southbrook_estimating catalog seeds) are
        skipped and reported in a single chatter note so the rep sees
        exactly which starters didn't land — the design still opens,
        just with fewer cabinets.
        """
        self.ensure_one()
        spec = self._get_preset_layout(preset)
        if not spec:
            raise UserError("Unknown kitchen template preset: %r" % preset)

        self.write({
            "room_width_in":  spec["room_width_in"],
            "room_depth_in":  spec["room_depth_in"],
            "room_height_in": spec["room_height_in"],
        })

        seeded, skipped = [], []
        Line = self.env["southbrook.kitchen.design.line"]
        for xmlid, cabinet_type, x, y, z, sequence in spec["starter_cabinets"]:
            tmpl = self.env.ref(xmlid, raise_if_not_found=False)
            if not tmpl:
                skipped.append(xmlid)
                continue
            variant = tmpl.product_variant_id
            if not variant:
                skipped.append(xmlid)
                continue
            Line.create({
                "design_id":     self.id,
                "sequence":      sequence,
                "product_id":    variant.id,
                "quantity":      1,
                "price_unit":    variant.lst_price or tmpl.list_price,
                "cabinet_type":  cabinet_type,
                "width_in":      tmpl.southbrook_width_in or 24.0,
                "height_in":     tmpl.southbrook_height_in or 34.5,
                "depth_in":      tmpl.southbrook_depth_in or 24.0,
                "x_position_in": x,
                "y_position_in": y,
                "z_position_in": z,
                "origin":        "configurator",
            })
            seeded.append(xmlid)

        # Chatter audit trail — critical for the "why did my L-shape
        # only get 3 cabinets" support ticket case.
        summary = "Applied template preset: %s" % spec["name"]
        details = []
        if seeded:
            details.append("Seeded %d starter cabinet(s)." % len(seeded))
        if skipped:
            details.append(
                "Skipped %d cabinet(s) with missing xmlids: %s"
                % (len(skipped), ", ".join(sorted(set(skipped))))
            )
        if not spec["starter_cabinets"]:
            details.append("No starter cabinets in this preset (blank canvas).")
        self.message_post(body="%s<br/>%s" % (summary, "<br/>".join(details)))

        # Move designs with starters straight to 'configured'; blank
        # canvas stays at 'draft'.
        if seeded:
            self.state = "configured"
        return {"seeded": seeded, "skipped": skipped}

    @api.model
    def action_open_template_gallery(self):
        """Open the "Start from template" wizard.

        Called from the Kitchen Designs list header button. Returns an
        ir.actions.act_window for the transient
        kitchen.design.template.picker so the rep sees the 4-preset
        radio card set instead of a blank Create form.
        """
        return {
            "type":      "ir.actions.act_window",
            "name":      "Start from Template",
            "res_model": "kitchen.design.template.picker",
            "view_mode": "form",
            "target":    "new",
            "context":   self.env.context,
        }

    # ── BOM autoseed (v19.0.5.6.0) ─────────────────────────────────────────────
    # Sprint 2d workstream that dodges the JS/canvas failure surface. The
    # goal is narrow: at quote-time, for every unique product.template on
    # the fresh SO, ensure a template-level mrp.bom stub exists. If one
    # already does, no-op — this method must be safely re-callable across
    # multiple designs that share templates.
    #
    # Panel geometry is computed via southbrook_estimating.mrp_bom.
    # _compute_panel_dimensions (the single canonical Custom Routine #1)
    # and persisted as a JSON blob on the note field until raw-material
    # product.product records exist. bom_line_ids stays empty; the shop
    # team fills it in manually or a follow-up commit wires it up.
    def _ensure_kitchen_bom(self, product_tmpl):
        """Idempotently seed a template-level mrp.bom stub.

        Returns the existing (or newly-created) mrp.bom record. Safe to
        call from a quote-time loop — repeated calls on the same
        template are no-ops.
        """
        self.ensure_one()
        if not product_tmpl:
            return self.env["mrp.bom"]

        Bom = self.env["mrp.bom"].sudo()

        # v19.0.5.6.5 (Track B P0-B, defense-in-depth) — attach the
        # Manufacture route on EVERY call, not just when we're about
        # to autoseed a new BOM. Runtime-created templates (e.g. from
        # the 3D configurator's fast-path) miss the noupdate="1"
        # canonical_catalog_routes.xml seed, so without this check
        # procurement.group would only spawn Delivery after SO
        # confirm — mrp.production would never be created. The guards
        # (raise_if_not_found=False + `if mfg_route`) let this degrade
        # silently on installs where mrp isn't loaded yet.
        mfg_route = self.env.ref(
            "mrp.route_warehouse0_manufacture", raise_if_not_found=False,
        )
        # Defense-in-depth — writes route on product.product variants (the
        # stock module defines route_ids on the variant, not the template;
        # template-level writes silently no-op in v19).
        if mfg_route:
            for variant in product_tmpl.product_variant_ids:
                if mfg_route.id not in variant.route_ids.ids:
                    variant.sudo().write({"route_ids": [(4, mfg_route.id)]})

        # Fast path — the template already carries a normal-type BOM.
        # active_test=False so we don't autoseed a duplicate on top of an
        # archived normal BOM (v19 default One2many context filters archived).
        existing = product_tmpl.with_context(active_test=False).bom_ids.filtered(
            lambda b: b.type == "normal"
        )
        if existing:
            return existing[:1]

        # Inches → mm (25.4). Templates carry the inch-native fields
        # exposed by southbrook_kitchen_3d_configurator.product_template;
        # _compute_panel_dimensions is metric per NF14.
        w_in = product_tmpl.southbrook_width_in or 24.0
        h_in = product_tmpl.southbrook_height_in or 34.5
        d_in = product_tmpl.southbrook_depth_in or 24.0
        width_mm = w_in * 25.4
        height_mm = h_in * 25.4
        depth_mm = d_in * 25.4

        ct = product_tmpl.southbrook_cabinet_type or "base"
        family_map = {
            "base":   "base",
            "wall":   "wall",
            "tall":   "tall",
            "corner": "corner",
            "filler": "accessory",
            "panel":  "accessory",
        }
        family = family_map.get(ct, "base")

        # Rule 3 (Southbrook_Excel_to_Odoo_Mapping.md §3.4) — width →
        # door count for base/wall/tall. Accessories emit no door.
        if family == "accessory":
            door_count = 0
        elif w_in >= 24.0:
            door_count = 2
        else:
            door_count = 1

        panel = Bom._compute_panel_dimensions(
            width_mm=width_mm,
            height_mm=height_mm,
            depth_mm=depth_mm,
            family=family,
            door_count=door_count,
            drawer_count=0,
            finished_sides="none",
        )

        default_code = product_tmpl.default_code or ("TMPL-%d" % product_tmpl.id)
        # v19.0.5.6.3 fix: mrp.bom has NO `note` field in Odoo v19 CE
        # (verified against official v19 mrp/models/mrp_bom.py). The panel
        # JSON was originally stashed there as a placeholder — dropped now
        # so Bom.create() no longer raises ValueError on the first-ever
        # autoseed. Panel geometry is deterministic from template dims +
        # family + door_count; the follow-up commit that materialises
        # bom_line_ids will recompute rather than re-read.
        bom = Bom.create({
            "product_tmpl_id": product_tmpl.id,
            "type":            "normal",
            "product_qty":     1.0,
            "code":            "KitchenAutoSeed-%s" % default_code,
            "bom_line_ids":    [],
        })
        _logger.info(
            "auto-seeded BOM for %s | panel=%s",
            product_tmpl.display_name,
            json.dumps(panel, default=str, sort_keys=True),
        )
        return bom

    def action_create_quotation(self):
        SaleOrder = self.env["sale.order"]
        for design in self:
            if not design.partner_id:
                raise UserError("Select a customer before creating a quotation.")
            # v19.0.5.6.4 fix — autoseed BEFORE the production-ready
            # gate. Previously (5.6.0-5.6.3) autoseed ran after SO
            # create, so the D12 MISSING_BOM gate rejected every design
            # whose cabinet template had no BOM — defeating the whole
            # point of Track B autoseed (users shouldn't have to hand-
            # create BOMs to get a quote). Now: seed missing template-
            # level BOM stubs first, then run the readiness check.
            design_templates = design.cabinet_line_ids.mapped(
                "product_id.product_tmpl_id"
            )
            for tmpl in design_templates:
                try:
                    design._ensure_kitchen_bom(tmpl)
                except UserError as e:
                    _logger.warning(
                        "BOM autoseed (pre-quote) skipped for %s on design %s: %s",
                        tmpl.display_name, design.name, e,
                    )
            # D12 — Gate on production-readiness. Refuses to spawn a
            # quote when any blocking issue (collision, missing BOM,
            # wall-cab over ceiling) would burn the customer or the
            # shop floor later. Runs AFTER autoseed so MISSING_BOM only
            # fires on templates the autoseed genuinely couldn't fix.
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

            # ── BOM autoseed (v19.0.5.6.0) ─────────────────────────────
            # For every unique product_tmpl on the fresh SO, make sure
            # a template-level mrp.bom stub exists. Idempotent per
            # _ensure_kitchen_bom. Wrapped so per-template failures
            # don't block quote creation — the D12 pre-quote
            # MISSING_BOM gate already flags absent BOMs as blocking
            # upstream, so this is defence-in-depth on the forward path.
            templates = order.order_line.mapped("product_id.product_tmpl_id")
            for tmpl in templates:
                try:
                    design._ensure_kitchen_bom(tmpl)
                except UserError as e:
                    _logger.warning(
                        "BOM autoseed skipped for %s on SO %s: %s",
                        tmpl.display_name, order.name, e,
                    )

            design.sale_order_id = order.id
            design.state = "quoted"

            # Optional confirm-immediately flow driven by the
            # "Create & Confirm →" button (context={'confirm_
            # immediately': True}). Confirms the SO in place and
            # pivots the return action from SO form to mrp.production.
            #
            # v19.0.5.6.6 fix (Track B P0-A) — wrap action_confirm in a
            # savepoint. If the Production Approval gate raises UserError
            # (southbrook_mrp_pm.sale_order.action_confirm calls
            # `_check_production_approval_gate` BEFORE super()), the
            # bare call would roll the WHOLE request transaction —
            # including the autoseeded BOMs, SO create, and design
            # state="quoted". With the savepoint, only the confirm
            # attempt reverts; everything upstream persists so the rep
            # can navigate to the SO and click Request Production.
            if self.env.context.get("confirm_immediately"):
                # 2026-07-02 UX enhancement — Sales Managers get one-click confirm.
                # The Production Approval gate exists to protect against reps accidentally
                # spawning MOs; Sales Managers already have the authority (they can tick
                # force_production_release on the SO form manually anyway). Auto-setting
                # it here just removes a redundant click. If a rep clicks the button,
                # the savepoint below still gracefully catches the gate and falls back
                # to the SO form.
                is_sales_manager = self.env.user.has_group(
                    "sales_team.group_sale_manager"
                )
                # `force_production_release` is defined by southbrook_mrp_pm
                # (Tier 5), which this Tier-3 module must NOT hard-depend on
                # (that would invert the tier order). Guard the write so the
                # configurator still creates quotations when mrp_pm isn't
                # installed — the field just isn't set in that config.
                if is_sales_manager and "force_production_release" in order._fields:
                    order.sudo().write({"force_production_release": True})
                    _logger.info(
                        "Sales Manager %s auto-set force_production_release on %s "
                        "via kitchen_design.action_create_quotation",
                        self.env.user.name, order.name,
                    )
                    order.message_post(body=(
                        "Production Approval auto-released by Sales Manager %s via "
                        "Create & Confirm → button. Standard approval gate bypass — "
                        "Sales Manager can toggle the SO's Force Production Release "
                        "field back to false if they want to route through the normal "
                        "approval flow instead."
                    ) % self.env.user.name)
                confirm_error = None
                try:
                    with self.env.cr.savepoint():
                        order.action_confirm()
                except UserError as e:
                    confirm_error = str(e)
                    _logger.warning(
                        "action_create_quotation: auto-confirm blocked "
                        "for %s: %s", order.name, confirm_error,
                    )
                    order.message_post(body=(
                        "Auto-confirm blocked: %s\n\n"
                        "Order left in draft. Use Request Production → "
                        "Approve Production before confirming."
                    ) % confirm_error)
                if confirm_error:
                    # Fall back to SO form so the rep sees the draft +
                    # chatter message + Request Production button.
                    return {
                        "type":      "ir.actions.act_window",
                        "res_model": "sale.order",
                        "res_id":    order.id,
                        "views":     [(False, "form")],
                        "view_mode": "form",
                        "target":    "current",
                    }
                Mo = self.env["mrp.production"].sudo()
                mos = Mo.search([("origin", "=", order.name)])
                if len(mos) == 1:
                    return {
                        "type":      "ir.actions.act_window",
                        "res_model": "mrp.production",
                        "res_id":    mos.id,
                        "views":     [(False, "form")],
                        "view_mode": "form",
                        "target":    "current",
                    }
                # Zero-MO or multi-MO — send to origin-filtered list.
                return {
                    "type":      "ir.actions.act_window",
                    "name":      "Manufacturing Orders (%s)" % order.name,
                    "res_model": "mrp.production",
                    "views":     [(False, "list"), (False, "form")],
                    "view_mode": "list,form",
                    "domain":    [("origin", "=", order.name)],
                    "target":    "current",
                }
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

    # ── Recommendation D · Sprint 1 bridge field ────────────────────────
    # Points at the sale.order.line the reconciliation cron mirrors
    # this design line into. See models/sale_order_line.py for the
    # target-side field surface.
    sale_order_line_id = fields.Many2one(
        "sale.order.line",
        string="Bridged Order Line",
        index=True,
        ondelete="set null",
        copy=False,
        help="Rec D Sprint 1 — non-authoring mirror onto the sale.order."
             "line slot. Managed by the southbrook.design.reconcile "
             "cron. Do not set manually.",
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


# ── v19.0.5.6.12 — Template gallery wizard ────────────────────────────────
# Transient model backing the "Start from Template" customer-onboarding
# gallery. Kept in this file (not a separate wizards/ subdir) because
# the preset catalog lives on SouthbrookKitchenDesign and the two models
# are always deployed together.
class SouthbrookKitchenDesignTemplatePicker(models.TransientModel):
    _name = "kitchen.design.template.picker"
    _description = "Kitchen Design Template Picker"

    preset = fields.Selection(
        selection=[
            ("empty",   "Empty Room · Blank Canvas"),
            ("l_shape", "L-Shaped Kitchen"),
            ("u_shape", "U-Shaped Kitchen"),
            ("galley",  "Galley Kitchen"),
        ],
        string="Layout Preset",
        required=True,
        default="l_shape",
        help="Pick a starting layout. 'Empty' just seeds room dimensions; "
             "the shaped presets also seed a starter cabinet run so you "
             "iterate from a working design instead of an empty canvas.",
    )
    preset_description = fields.Text(
        string="Description",
        compute="_compute_preset_description",
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer (optional)",
        help="Assign a customer up-front so pricing resolves against the "
             "channel pricelist immediately. Leave empty for a walk-in or "
             "showroom demo.",
    )

    @api.depends("preset")
    def _compute_preset_description(self):
        Design = self.env["southbrook.kitchen.design"]
        for rec in self:
            spec = Design._get_preset_layout(rec.preset) if rec.preset else None
            rec.preset_description = spec["description"] if spec else ""

    def action_create(self):
        """Materialise a new southbrook.kitchen.design from the picked
        preset and open the 3D configurator on it. Handles the whole
        onboarding transition in a single click.
        """
        self.ensure_one()
        Design = self.env["southbrook.kitchen.design"]
        spec = Design._get_preset_layout(self.preset)
        if not spec:
            raise UserError("Please pick a template before continuing.")

        design_vals = {
            "name":  spec["name"],
            "state": "draft",
        }
        if self.partner_id:
            design_vals["partner_id"] = self.partner_id.id
        design = Design.create(design_vals)
        design._apply_kitchen_template(self.preset)
        return design.action_open_configurator()
