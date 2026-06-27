import math

from odoo import http
from odoo.http import request


class SouthbrookKitchenConfiguratorController(http.Controller):

    # ── Products catalogue ───────────────────────────────────────────────────────
    @http.route(
        "/southbrook_kitchen/configurator/products",
        type="json", auth="user", methods=["POST"],
    )
    def products(self):
        """Return all cabinet products available to the configurator."""
        products = request.env["product.product"].search([
            ("product_tmpl_id.southbrook_is_cabinet", "=", True),
            ("sale_ok", "=", True),
        ], order="product_tmpl_id.southbrook_cabinet_type, default_code, name")
        return [self._product_payload(p) for p in products]

    # ── Layout calculation ───────────────────────────────────────────────────────
    @http.route(
        "/southbrook_kitchen/configurator/layout",
        type="json", auth="user", methods=["POST"],
    )
    def layout(self, room_width_in=12, room_depth_in=24, room_height_in=96):
        """
        Compute the cabinet fill for the given room dimensions.

        Returns a dict with:
          room        — echoed dimensions
          items       — list of cabinet placement records
          summary     — counts, totals, remainder
          error       — non-empty string if no products configured
        """
        env = request.env
        base = self._first_product(env, "base")
        wall = self._first_product(env, "wall")

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
            items.append(self._layout_item(base, i, x, 0.0, 0.0))
            items.append(self._layout_item(wall, i, x, 0.0, wall_z))

        # Filler panel if there is significant remainder
        if remainder >= 1.0:
            filler = self._first_product(env, "filler")
            if filler:
                fp = self._product_payload(filler)
                fp.update({
                    "layout_key":    "filler-0",
                    "x_position_in": n * module_w,
                    "y_position_in": 0.0,
                    "z_position_in": 0.0,
                    "width_in":      remainder,  # override to actual gap
                    "cabinet_type":  "filler",
                })
                items.append(fp)

        total_price = sum(it["price"] for it in items
                          if it["cabinet_type"] not in ("filler",))

        return {
            "room": {
                "width_in":  rw,
                "depth_in":  float(room_depth_in),
                "height_in": float(room_height_in),
            },
            "items": items,
            "summary": {
                "base_count":   n,
                "wall_count":   n,
                "total":        n * 2,
                "price":        total_price,
                "remainder_in": round(remainder, 2),
            },
            "error": "",
        }

    # ── Save design ──────────────────────────────────────────────────────────────
    @http.route(
        "/southbrook_kitchen/configurator/save",
        type="json", auth="user", methods=["POST"],
    )
    def save_design(self, name, room, items, partner_id=False, design_id=False):
        """
        Persist (or update) a KitchenDesign and its layout lines.

        Pass design_id to overwrite an existing record.
        """
        Design = request.env["southbrook.kitchen.design"]
        vals = {
            "name":           name or "Kitchen Design",
            "partner_id":     partner_id or False,
            "room_width_in":  room.get("width_in",  12),
            "room_depth_in":  room.get("depth_in",  24),
            "room_height_in": room.get("height_in", 96),
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

    def _layout_item(self, product, index, x, y, z):
        payload = self._product_payload(product)
        payload.update({
            "layout_key":    "%s-%d" % (payload["cabinet_type"], index + 1),
            "x_position_in": x,
            "y_position_in": y,
            "z_position_in": z,
        })
        return payload

    def _product_payload(self, product):
        tmpl = product.product_tmpl_id
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
            "price":         product.lst_price,
            "available_qty": product.qty_available,
            "bom_available": tmpl.southbrook_bom_available,
            "image_url":     "/web/image/product.product/%d/image_128" % product.id,
            "asset_url":     tmpl.southbrook_3d_asset_url or "",
        }
