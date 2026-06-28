import math

from odoo import http
from odoo.http import request


class SouthbrookKitchenConfiguratorController(http.Controller):

    # ── Products catalogue ───────────────────────────────────────────────────────
    @http.route(
        "/southbrook_kitchen/configurator/products",
        type="json", auth="user", methods=["POST"],
    )
    def products(self, partner_id=False):
        """Return all cabinet products available to the configurator.

        D3 — when partner_id is supplied, prices reflect the partner's
        channel pricelist (Dealer/Tradesperson/etc.). Also returns the
        resolved channel metadata so the UI can show a "Channel:
        Dealer -50%" badge alongside the catalog. Without partner_id
        falls back to product.lst_price (retail).
        """
        products = request.env["product.product"].search([
            ("product_tmpl_id.southbrook_is_cabinet", "=", True),
            ("sale_ok", "=", True),
        ], order="product_tmpl_id.southbrook_cabinet_type, default_code, name")
        partner = self._browse_partner(partner_id)
        pricelist = self._resolve_pricelist(partner)
        return {
            "channel": self._channel_meta(partner, pricelist),
            "products": [self._product_payload(p, pricelist, partner) for p in products],
        }

    # ── Layout calculation ───────────────────────────────────────────────────────
    @http.route(
        "/southbrook_kitchen/configurator/layout",
        type="json", auth="user", methods=["POST"],
    )
    def layout(self, room_width_in=12, room_depth_in=24, room_height_in=96,
               partner_id=False, filler_strategy="split"):
        """
        Compute the cabinet fill for the given room dimensions.

        Returns a dict with:
          room        — echoed dimensions
          items       — list of cabinet placement records
          summary     — counts, totals, remainder
          channel     — pricelist metadata (D3)
          error       — non-empty string if no products configured

        D3 — partner_id (optional) drives channel-pricelist resolution
        so per-item prices and the summary total reflect Dealer /
        Tradesperson / KD / etc. discounts. Falls back to retail when
        no partner is supplied.
        """
        env = request.env
        base = self._first_product(env, "base")
        wall = self._first_product(env, "wall")

        partner = self._browse_partner(partner_id)
        pricelist = self._resolve_pricelist(partner)

        if not base or not wall:
            return {
                "error": (
                    "No cabinet products configured. "
                    "Open Southbrook Kitchen > Cabinet Products and add at least "
                    "one Base Cabinet and one Wall Cabinet."
                ),
                "items": [],
                "summary": {"base_count": 0, "wall_count": 0, "total": 0,
                             "price": 0.0, "remainder_in": 0.0},
                "room": {"width_in": float(room_width_in),
                         "depth_in": float(room_depth_in),
                         "height_in": float(room_height_in)},
                "channel": self._channel_meta(partner, pricelist),
            }

        module_w = base.product_tmpl_id.southbrook_width_in or 24.0
        rw = float(room_width_in)
        n  = max(0, int(math.floor(rw / module_w)))
        remainder = rw - n * module_w

        # Cabinet dimensions for placement
        base_h = base.product_tmpl_id.southbrook_height_in or 34.5
        wall_h = wall.product_tmpl_id.southbrook_height_in or 30.0
        ctr_t  = 1.5    # countertop thickness (in)
        gap    = 18.0   # clearance between counter surface and wall cab bottom
        wall_z = base_h + ctr_t + gap   # bottom of wall cabinet

        items = []
        for i in range(n):
            x = i * module_w
            items.append(self._layout_item(base, i, x, 0.0, 0.0,    pricelist, partner))
            items.append(self._layout_item(wall, i, x, 0.0, wall_z, pricelist, partner))

        # D7 — Smart filler placement. Honors the chosen filler_strategy:
        #  split: half-width filler at each end (default; pushes bases by half)
        #  left:  single filler at x=0 (push all bases right by remainder)
        #  right: single filler at x = n * module_w (right end)
        #  scribe: no filler (carpenter scribes end cabinet on site)
        filler_strategy = (filler_strategy or "split").lower()
        if filler_strategy not in ("split", "left", "right", "scribe"):
            filler_strategy = "split"
        if remainder >= 1.0 and filler_strategy != "scribe":
            if filler_strategy == "split":
                half = remainder / 2.0
                # Shift bases + walls right by `half` so the left filler
                # sits at x=0 cleanly.
                for it in items:
                    if it["cabinet_type"] in ("base", "wall"):
                        it["x_position_in"] = it["x_position_in"] + half
                lf = self._make_filler(env, half, 0.0,
                                        "filler-L", pricelist, partner)
                rf = self._make_filler(env, half, n * module_w + half,
                                        "filler-R", pricelist, partner)
                if lf: items.append(lf)
                if rf: items.append(rf)
            elif filler_strategy == "left":
                for it in items:
                    if it["cabinet_type"] in ("base", "wall"):
                        it["x_position_in"] = it["x_position_in"] + remainder
                lf = self._make_filler(env, remainder, 0.0,
                                        "filler-L", pricelist, partner)
                if lf: items.append(lf)
            else:   # right
                rf = self._make_filler(env, remainder, n * module_w,
                                        "filler-R", pricelist, partner)
                if rf: items.append(rf)

        cabinet_price = sum(it["price"] for it in items
                             if it["cabinet_type"] not in ("filler",))
        filler_price  = sum(it["price"] for it in items
                             if it["cabinet_type"] == "filler")

        return {
            "room": {
                "width_in":  rw,
                "depth_in":  float(room_depth_in),
                "height_in": float(room_height_in),
            },
            "items": items,
            "summary": {
                "base_count":      n,
                "wall_count":      n,
                "total":           n * 2,
                # Backward compat: 'price' kept as cabinet total. The
                # UI can now show filler as a separate breakdown row.
                "price":           cabinet_price,
                "cabinet_price":   cabinet_price,
                "filler_price":    filler_price,
                "remainder_in":    round(remainder, 2),
                "filler_strategy": filler_strategy,
                "snap_hint":       self._snap_hint(rw, module_w),
            },
            "channel": self._channel_meta(partner, pricelist),
            "error": "",
        }

    # ─── D7 — filler helpers ────────────────────────────────────────────────────
    def _make_filler(self, env, width_in, x, key, pricelist, partner):
        """Build a single filler item at position x, width prorated."""
        filler = self._first_product(env, "filler")
        if not filler:
            return None
        fp = self._product_payload(filler, pricelist, partner)
        # Prorate price by actual filler width vs the catalog standard
        # width. Avoids over-charging for a 0.5" filler at the price of
        # a 6" panel.
        std_w = float(fp.get("width_in") or width_in or 1.0)
        if std_w <= 0:
            std_w = 1.0
        prorated = (fp.get("price") or 0.0) * (max(width_in, 0.5) / std_w)
        fp.update({
            "layout_key":    key,
            "x_position_in": x,
            "y_position_in": 0.0,
            "z_position_in": 0.0,
            "width_in":      width_in,
            "cabinet_type":  "filler",
            "price":         round(prorated, 2),
        })
        return fp

    def _snap_hint(self, rw, module_w):
        """When rw is 1-6 inches away from a module-clean total, suggest
        the nearest clean width so the rep can avoid filler altogether."""
        if not module_w or module_w <= 0:
            return None
        # Floor count
        n_floor = int(rw // module_w)
        clean_lo = n_floor * module_w
        clean_hi = (n_floor + 1) * module_w
        gap_lo = rw - clean_lo
        gap_hi = clean_hi - rw
        if gap_lo == 0:
            return None
        # Suggest hi (stretch) if rw is close enough to hi; else lo (shrink)
        if 0 < gap_hi <= 6.0:
            return {"target_width": clean_hi,
                    "delta":         round(gap_hi, 2),
                    "direction":     "expand"}
        if 0 < gap_lo <= 6.0:
            return {"target_width": clean_lo,
                    "delta":         round(-gap_lo, 2),
                    "direction":     "shrink"}
        return None

    # ── Save design ──────────────────────────────────────────────────────────────
    @http.route(
        "/southbrook_kitchen/configurator/save",
        type="json", auth="user", methods=["POST"],
    )
    def save_design(self, name, room, items, partner_id=False, design_id=False):
        """
        Persist (or update) a KitchenDesign and its layout lines.

        Pass design_id to overwrite an existing record.

        D4 — auto-names new designs (no design_id, no real name) using
        the customer + room dims + date so the design tree view doesn't
        fill with "New Kitchen Design" collisions.
        """
        Design = request.env["southbrook.kitchen.design"]
        room_w = room.get("width_in",  12)
        room_d = room.get("depth_in",  24)
        room_h = room.get("height_in", 96)
        if not design_id and (not name or name.strip() in (
            "", "Kitchen Design", "New Kitchen Design", "Untitled Kitchen",
        )):
            name = self._auto_name(self._browse_partner(partner_id), room_w, room_d)
        vals = {
            "name":           name or "Kitchen Design",
            "partner_id":     partner_id or False,
            "room_width_in":  room_w,
            "room_depth_in":  room_d,
            "room_height_in": room_h,
            "state":          "configured",
        }

        if design_id:
            design = Design.browse(int(design_id))
            design.write(vals)
            design.cabinet_line_ids.unlink()
        else:
            design = Design.create(vals)

        for seq, item in enumerate(items, start=1):
            product = request.env["product.product"].browse(int(item["product_id"]))
            tmpl    = product.product_tmpl_id
            request.env["southbrook.kitchen.design.line"].create({
                "design_id":      design.id,
                "sequence":       seq * 10,
                "product_id":     product.id,
                "quantity":       1,
                "price_unit":     product.lst_price,
                "cabinet_type":   tmpl.southbrook_cabinet_type,
                "width_in":       item.get("width_in",  tmpl.southbrook_width_in or 24.0),
                "height_in":      item.get("height_in", tmpl.southbrook_height_in or 34.5),
                "depth_in":       item.get("depth_in",  tmpl.southbrook_depth_in or 24.0),
                "x_position_in":  item.get("x_position_in", 0),
                "y_position_in":  item.get("y_position_in", 0),
                "z_position_in":  item.get("z_position_in", 0),
            })

        return {
            "id":   design.id,
            "name": design.display_name,
        }

    # ── Helpers ──────────────────────────────────────────────────────────────────
    def _first_product(self, env, cabinet_type):
        return env["product.product"].search([
            ("product_tmpl_id.southbrook_is_cabinet",    "=", True),
            ("product_tmpl_id.southbrook_cabinet_type",  "=", cabinet_type),
            ("sale_ok", "=", True),
        ], limit=1)

    def _layout_item(self, product, index, x, y, z, pricelist=False, partner=False):
        payload = self._product_payload(product, pricelist, partner)
        payload.update({
            "layout_key":    "%s-%d" % (payload["cabinet_type"], index + 1),
            "x_position_in": x,
            "y_position_in": y,
            "z_position_in": z,
        })
        return payload

    def _product_payload(self, product, pricelist=False, partner=False):
        tmpl = product.product_tmpl_id
        price = self._channel_price(product, pricelist, partner)
        return {
            "product_id":    product.id,
            "template_id":   tmpl.id,
            "name":          product.display_name,
            "sku":           product.default_code or "",
            "cabinet_type":  tmpl.southbrook_cabinet_type,
            "width_in":      tmpl.southbrook_width_in  or 24.0,
            "height_in":     tmpl.southbrook_height_in or 34.5,
            "depth_in":      tmpl.southbrook_depth_in  or 24.0,
            "material":      tmpl.southbrook_material   or "white_melamine",
            "door_style":    tmpl.southbrook_door_style or "shaker",
            "price":         price,
            "list_price":    product.lst_price,
            "available_qty": product.qty_available,
            "bom_available": tmpl.southbrook_bom_available,
            "image_url":     "/web/image/product.product/%d/image_128" % product.id,
            "asset_url":     tmpl.southbrook_3d_asset_url or "",
        }

    # ─── D3 — channel pricelist resolution ──────────────────────────────────────
    # Centralise partner/pricelist plumbing so /products + /layout
    # share the same resolver and the UI gets a single channel-meta
    # block to render the topbar badge.

    def _browse_partner(self, partner_id):
        if not partner_id:
            return request.env["res.partner"]
        try:
            pid = int(partner_id)
        except (TypeError, ValueError):
            return request.env["res.partner"]
        if pid <= 0:
            return request.env["res.partner"]
        return request.env["res.partner"].sudo().browse(pid).exists()

    def _resolve_pricelist(self, partner):
        # Reuses the canonical southbrook_estimating dispatcher so the
        # configurator's live preview matches the price the Order
        # Builder + spec sheet PDF will charge. Falls back to retail
        # when no partner.
        SaleOrder = request.env["sale.order"]
        if hasattr(SaleOrder, "_resolve_channel_pricelist"):
            try:
                return SaleOrder._resolve_channel_pricelist(partner)
            except Exception:
                pass
        # Fallback if southbrook_estimating isn't installed: partner's
        # property pricelist, else the env default.
        if partner:
            pl = partner.property_product_pricelist
            if pl:
                return pl
        return request.env["product.pricelist"].search([], limit=1)

    def _channel_price(self, product, pricelist, partner):
        if not pricelist:
            return product.lst_price
        try:
            # v19 unified API: pricelist._get_product_price(product, qty, partner)
            return pricelist._get_product_price(product, 1.0, partner or False)
        except Exception:
            return product.lst_price

    def _channel_meta(self, partner, pricelist):
        # Compact dict the UI renders into a topbar badge.
        channel = (partner and partner.channel) or "retail"
        # Best-effort tier suffix for tradesperson.
        suffix = ""
        if channel == "tradesperson" and partner:
            tier = getattr(partner, "tradesperson_tier", False)
            if tier:
                suffix = " T%s" % tier
        return {
            "partner_id":     (partner and partner.id) or False,
            "partner_name":   (partner and partner.display_name) or "",
            "channel":        channel,
            "channel_label":  self._CHANNEL_LABELS.get(channel, channel.title()) + suffix,
            "pricelist_id":   (pricelist and pricelist.id) or False,
            "pricelist_name": (pricelist and pricelist.display_name) or "",
            "currency_id":    (pricelist and pricelist.currency_id.id) or False,
            "currency_symbol": (pricelist and pricelist.currency_id.symbol) or "$",
        }

    _CHANNEL_LABELS = {
        "retail":       "Retail",
        "dealer":       "Dealer -50%",
        "tradesperson": "Contractor",
        "kd":           "KD",
        "bigbox":       "Big-Box",
        "refacing":     "Refacing",
    }

    # ─── D4 — auto-name + per-user sticky room defaults ─────────────────────────
    @http.route(
        "/southbrook_kitchen/configurator/user_defaults",
        type="json", auth="user", methods=["POST"],
    )
    def user_defaults(self, save=False, width=None, depth=None, height=None):
        """Read or write the current user's preferred room dimensions.

        Stored as ir.config_parameter keyed by uid so each rep gets
        their own sticky defaults; no res.users schema bump required.
        """
        ICP = request.env["ir.config_parameter"].sudo()
        uid = request.env.uid
        keys = {
            "w": "southbrook_kitchen.default_room_width_in.%d"  % uid,
            "d": "southbrook_kitchen.default_room_depth_in.%d"  % uid,
            "h": "southbrook_kitchen.default_room_height_in.%d" % uid,
        }
        if save:
            if width  is not None: ICP.set_param(keys["w"], str(width))
            if depth  is not None: ICP.set_param(keys["d"], str(depth))
            if height is not None: ICP.set_param(keys["h"], str(height))

        def _read(k, default):
            try:
                return float(ICP.get_param(keys[k], default))
            except Exception:
                return default
        return {
            "width":  _read("w", 12),
            "depth":  _read("d", 24),
            "height": _read("h", 96),
        }

    def _auto_name(self, partner, room_w, room_d):
        from odoo import fields as _fields
        today = _fields.Date.context_today(request.env.user).strftime("%Y-%m-%d")
        pname = (partner and partner.display_name) or "Walk-in"
        return "%s - %dx%d - %s" % (pname, int(room_w or 0), int(room_d or 0), today)
