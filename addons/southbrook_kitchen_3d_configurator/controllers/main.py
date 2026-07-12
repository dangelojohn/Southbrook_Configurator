import logging
import math

from odoo import http
from odoo.http import request

# PR2 — the pure layout engine's WALLS tuple is the single source of
# truth for valid wall identifiers server-side too. Imported the same
# way models/kitchen_design.py:11 does.
from odoo.addons.southbrook_estimating.models import kitchen_layout_engine

_logger = logging.getLogger(__name__)


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
        # v19 ORM rejects dotted M2O field references in order= clauses
        # ("Invalid field property '<name>' on <model>.<m2o>") even
        # though it accepts them in domains. Sort by sortable column-
        # local fields here; the JS layer groups by cabinet_type on
        # display.
        products = request.env["product.product"].search([
            ("product_tmpl_id.southbrook_is_cabinet", "=", True),
            ("sale_ok", "=", True),
        ], order="default_code, name")
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
               partner_id=False, filler_strategy="split",
               wall_cab_top_alignment="fixed_gap", soffit_height_in=84.0):
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
            missing = []
            if not base: missing.append("Base Cabinet")
            if not wall: missing.append("Wall Cabinet")
            return {
                "error": (
                    "No %s product configured. "
                    "Tag a saleable product with 'Southbrook Cabinet' + "
                    "the matching cabinet type to populate the catalog."
                ) % " / ".join(missing),
                # D10 — structured error code + CTA so the UI can render
                # an onboarding nudge with a real button instead of a
                # bare error string.
                "error_code": "NO_CABINETS",
                "error_cta":  {
                    "label": "Open Cabinet Products",
                    "action": {
                        "type":      "ir.actions.act_window",
                        "name":      "Southbrook Cabinet Products",
                        "res_model": "product.template",
                        "view_mode": "list,form",
                        "views":     [(False, "list"), (False, "form")],
                        "domain":    [("southbrook_is_cabinet", "=", True)],
                        "target":    "current",
                        "context":   {
                            "default_southbrook_is_cabinet": True,
                            "default_sale_ok":               True,
                        },
                    },
                },
                "items": [],
                "summary": {"base_count": 0, "wall_count": 0, "total": 0,
                             "price": 0.0, "remainder_in": 0.0},
                "room": {"width_in": float(room_width_in),
                         "depth_in": float(room_depth_in),
                         "height_in": float(room_height_in)},
                "channel":  self._channel_meta(partner, pricelist),
                "warnings": [],
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
        min_z  = base_h + ctr_t + gap   # bottom of wall cabinet (industry minimum)

        # D8 — Wall-cabinet Z computed from chosen alignment mode.
        # Never drops the bottom-of-cab below the industry minimum
        # (18" above counter); the alignment mode only raises it.
        alignment = (wall_cab_top_alignment or "fixed_gap").lower()
        soffit_h  = float(soffit_height_in or 0)
        if alignment == "to_ceiling":
            wall_z = max(min_z, float(room_height_in) - wall_h)
        elif alignment == "to_soffit" and soffit_h > 0:
            wall_z = max(min_z, soffit_h - wall_h)
        else:
            alignment = "fixed_gap"
            wall_z = min_z

        # D8 — Validation: wall cab top must not exceed the effective
        # ceiling (soffit-bottom when 'to_soffit', otherwise ceiling).
        effective_ceiling = (soffit_h
            if (alignment == "to_soffit" and soffit_h > 0)
            else float(room_height_in))
        wall_top = wall_z + wall_h
        warnings = []
        if wall_top > effective_ceiling + 0.01:
            warnings.append({
                "code":     "WALL_CAB_EXCEEDS_CEILING",
                "severity": "blocking",
                "message":  (
                    "Wall cabinet top reaches %.1f\" but %s sits at %.1f\". "
                    "Either lower the wall cabinets, drop the alignment "
                    "mode, or raise the %s."
                ) % (
                    wall_top,
                    "soffit" if alignment == "to_soffit" else "ceiling",
                    effective_ceiling,
                    "soffit" if alignment == "to_soffit" else "ceiling",
                ),
            })

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
            "channel":  self._channel_meta(partner, pricelist),
            "warnings": warnings,
            "error":    "",
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
        # PR2 — validate every incoming item's `wall` BEFORE any
        # create/write happens, so a bad payload never partially
        # writes (validate-all-items-first). `wall` is a layout-domain
        # input the pure kitchen_layout_engine consumes (P0.2,
        # 2026-07-11) — an unrecognised value here would otherwise
        # silently fall back to the model field's own "back" default,
        # masking a client bug. Same error-dict shape as the /layout
        # endpoint's NO_CABINETS response.
        for item in items or []:
            wall = item.get("wall") or "back"
            if wall not in kitchen_layout_engine.WALLS:
                _logger.warning(
                    "save_design: rejected payload — invalid wall=%r "
                    "(item layout_key=%s); must be one of %s. No "
                    "design/lines were created or modified.",
                    wall, item.get("layout_key"), kitchen_layout_engine.WALLS,
                )
                return {
                    "error": "invalid_wall",
                    "detail": (
                        "wall=%r is not a recognised room wall (must "
                        "be one of %s)."
                    ) % (wall, ", ".join(kitchen_layout_engine.WALLS)),
                }

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

        # D9 — Non-destructive save. Update existing lines by
        # layout_key, create only new ones, unlink only those that
        # disappeared from the incoming set. Manual lines (added in
        # the backend form, origin='manual') are NEVER touched.
        Line = request.env["southbrook.kitchen.design.line"]
        if design_id:
            design = Design.browse(int(design_id))
            design.write(vals)
            configurator_lines = design.cabinet_line_ids.filtered(
                lambda l: l.origin == "configurator"
            )
            existing_by_key = {
                l.layout_key: l for l in configurator_lines if l.layout_key
            }
        else:
            design = Design.create(vals)
            existing_by_key = {}

        # Panel-placement rule (Southbrook domain, 2026-07-01) — enforced
        # server-side so a client that skips the JS validator still can't
        # persist an end-cap panel pinned to a room wall. Rule:
        #   • cabinet_type == "filler" — auto-placed between cabinets by
        #     /layout; may contact a wall as a consequence of bridging the
        #     gap. No validation needed.
        #   • cabinet_type == "panel"  — decorative end cap; MUST attach to
        #     the left or right side face of a base or wall cabinet in the
        #     same design. Position must equal `host.x_position_in - width`
        #     (left cap) OR `host.x_position_in + host.width` (right cap).
        # Warnings are logged AND returned in the response so the client
        # can surface a banner. Persistence is not blocked (a rep may need
        # to save mid-configuration); the visual + JS-side error is the
        # primary UX signal.
        self._validate_end_cap_panel_placement(items)

        # 2026-07-01 E2E audit — enforce the /products catalog contract
        # on the save_design payload. The client posts product_ids
        # sourced from the /products response (main.py:31-34 filters on
        # southbrook_is_cabinet=True AND sale_ok=True), but the old
        # loop just browsed whatever id the client shipped: an authed
        # user could persist configurator lines pointing at archived,
        # non-cabinet, or ACL-restricted products (implicit info-
        # disclosure once /load_design_lines mirrors them back). Use
        # search() so ir.rule + domain filter apply in one shot —
        # rejected ids are logged + skipped per-line, the rest of the
        # save proceeds. This mirrors the ACL discipline already used
        # by save_position / delete_line / load_design_lines
        # (check_access at :420 / :459 / :492).
        Product = request.env["product.product"]
        incoming_keys = set()
        for seq, item in enumerate(items, start=1):
            try:
                pid = int(item["product_id"])
            except (KeyError, TypeError, ValueError):
                _logger.warning(
                    "save_design: item[%d] missing/invalid product_id (%r); "
                    "skipping",
                    seq, item.get("product_id"),
                )
                continue
            product = Product.search([
                ("id", "=", pid),
                ("product_tmpl_id.southbrook_is_cabinet", "=", True),
                ("sale_ok", "=", True),
            ], limit=1)
            if not product:
                # Either the id doesn't exist, the caller can't read
                # it, the template isn't tagged as a Southbrook cabinet,
                # or it's not sale_ok. Reject in one branch — the
                # client never gets to distinguish "which of those"
                # (avoids existence-oracle leak; matches the
                # AccessError convention set by southbrook_estimating_
                # website/controllers/room_api.py:_get_room_scoped).
                _logger.warning(
                    "save_design: rejected product_id=%d on design=%s "
                    "(fails /products catalog contract: must be "
                    "southbrook_is_cabinet=True AND sale_ok=True AND "
                    "readable by user)",
                    pid, design.id,
                )
                continue
            tmpl    = product.product_tmpl_id
            layout_key = item.get("layout_key") or "auto-%d" % seq
            incoming_keys.add(layout_key)
            line_vals = {
                "sequence":       seq * 10,
                "product_id":     product.id,
                "quantity":       1,
                "price_unit":     item.get("price") or product.lst_price,
                "cabinet_type":   tmpl.southbrook_cabinet_type,
                "width_in":       item.get("width_in",  tmpl.southbrook_width_in or 24.0),
                "height_in":      item.get("height_in", tmpl.southbrook_height_in or 34.5),
                "depth_in":       item.get("depth_in",  tmpl.southbrook_depth_in or 24.0),
                "x_position_in":  item.get("x_position_in", 0),
                "y_position_in":  item.get("y_position_in", 0),
                "z_position_in":  item.get("z_position_in", 0),
                # v19.0.4.20.0 — Smart-pinning (Option C): persist per-line
                # manual-move + rotation so a reload restores the user's
                # placement instead of the /layout auto-generated one.
                "pinned":         bool(item.get("pinned")),
                "rotation_deg":   float(item.get("rotation_deg") or 0.0),
                "layout_key":     layout_key,
                "origin":         "configurator",
                # PR2 — persist the layout-domain wall assignment.
                # Already validated against kitchen_layout_engine.WALLS
                # above; re-derive the same default here for items that
                # omitted the key.
                "wall":           item.get("wall") or "back",
            }
            if layout_key in existing_by_key:
                existing_by_key[layout_key].write(line_vals)
            else:
                Line.create({"design_id": design.id, **line_vals})

        # Unlink configurator-origin lines that the user removed in the
        # 3D pane. Manual-origin lines are excluded from existing_by_key
        # so they survive every save.
        removed_keys = set(existing_by_key) - incoming_keys
        if removed_keys:
            stale = Line.browse([])
            for k in removed_keys:
                stale |= existing_by_key[k]
            stale.unlink()

        return {
            "id":   design.id,
            "name": design.display_name,
        }

    # ── v19.0.4.20.0 · Smart-pinning RPC surface ─────────────────────────────────
    # Three lightweight routes so the client can persist a single
    # cabinet's placement (or unlink it) without triggering the full
    # save_design write-cycle. Called on pointer-up after a drag, on
    # R-key rotation, and on Delete/Backspace.
    #
    #   /load_design_lines  → returns the design's configurator-origin
    #                         lines as {layout_key: item-dict} so the
    #                         client can rehydrate a saved manual
    #                         placement instead of throwing it away.
    #   /save_position      → writes x_position_in / y_position_in /
    #                         z_position_in / rotation_deg / pinned on
    #                         a single line, matched by layout_key.
    #   /delete_line        → unlinks a single configurator-origin
    #                         line, matched by layout_key.
    #
    # None of these touch manual-origin lines. save_position + delete_line
    # silently no-op when the target design/line isn't found or the
    # calling user lacks write access — surfacing an error would hijack
    # the drag UX.
    @http.route(
        "/southbrook_kitchen/configurator/load_design_lines",
        type="json", auth="user", methods=["POST"],
    )
    def load_design_lines(self, design_id):
        design = request.env["southbrook.kitchen.design"].browse(int(design_id or 0))
        if not design.exists():
            return {"lines": []}
        try:
            design.check_access("read")
        except Exception:
            return {"lines": []}
        lines = design.cabinet_line_ids.filtered(
            lambda l: l.origin == "configurator"
        )
        out = []
        for line in lines:
            product = line.product_id
            out.append({
                "id":             product.id,
                "product_id":     product.id,
                "product_name":   product.display_name,
                "layout_key":     line.layout_key,
                "cabinet_type":   line.cabinet_type,
                "width_in":       line.width_in,
                "height_in":      line.height_in,
                "depth_in":       line.depth_in,
                "x_position_in":  line.x_position_in,
                "y_position_in":  line.y_position_in,
                "z_position_in":  line.z_position_in,
                "rotation_deg":   line.rotation_deg,
                "pinned":         line.pinned,
                "price":          line.price_unit,
                "quantity":       line.quantity,
                # PR2 — read-side emission. NULL on pre-PR2 rows (no
                # migration) reads back as "back" for backward compat,
                # matching the model field's own default.
                "wall":           line.wall or "back",
            })
        return {"lines": out}

    @http.route(
        "/southbrook_kitchen/configurator/save_position",
        type="json", auth="user", methods=["POST"],
    )
    def save_position(self, design_id, layout_key, x_position_in=None,
                      y_position_in=None, z_position_in=None,
                      rotation_deg=None, pinned=None):
        design = request.env["southbrook.kitchen.design"].browse(int(design_id or 0))
        if not design.exists() or not layout_key:
            return {"ok": False, "reason": "not_found"}
        try:
            design.check_access("write")
        except Exception:
            return {"ok": False, "reason": "forbidden"}
        line = design.cabinet_line_ids.filtered(
            lambda l: l.origin == "configurator"
                      and l.layout_key == layout_key
        )[:1]
        if not line:
            return {"ok": False, "reason": "no_matching_line"}
        vals = {}
        if x_position_in is not None:
            vals["x_position_in"] = float(x_position_in)
        if y_position_in is not None:
            vals["y_position_in"] = float(y_position_in)
        if z_position_in is not None:
            vals["z_position_in"] = float(z_position_in)
        if rotation_deg is not None:
            vals["rotation_deg"] = float(rotation_deg) % 360.0
        if pinned is not None:
            vals["pinned"] = bool(pinned)
        if vals:
            line.write(vals)
        return {"ok": True, "id": line.id}

    @http.route(
        "/southbrook_kitchen/configurator/delete_line",
        type="json", auth="user", methods=["POST"],
    )
    def delete_line(self, design_id, layout_key):
        design = request.env["southbrook.kitchen.design"].browse(int(design_id or 0))
        if not design.exists() or not layout_key:
            return {"ok": False, "reason": "not_found"}
        try:
            design.check_access("write")
        except Exception:
            return {"ok": False, "reason": "forbidden"}
        line = design.cabinet_line_ids.filtered(
            lambda l: l.origin == "configurator"
                      and l.layout_key == layout_key
        )
        n = len(line)
        line.unlink()
        return {"ok": True, "removed": n}

    # ── Helpers ──────────────────────────────────────────────────────────────────
    def _validate_end_cap_panel_placement(self, items, tol=0.5):
        """Log a warning for any `cabinet_type == "panel"` item whose
        x_position_in does not correspond to a host cabinet's exposed
        side face.

        A valid end-cap position matches EITHER:
            host.x_position_in - panel.width_in   (left cap)
            host.x_position_in + host.width_in    (right cap)
        where host is any item with cabinet_type in ("base", "wall").

        This is warn-only (not blocking) because a sales rep may need to
        save mid-configuration. The client-side validator + the visual
        3D render are the primary UX signals. See kitchen_configurator.js
        _validateEndCapPlacement for the client twin.

        Filler panels ("filler") are auto-placed between cabinets by the
        /layout endpoint (see D7 filler strategies) and may contact a
        wall as a consequence of bridging the last gap; they do NOT
        require this validation.
        """
        panels = [it for it in (items or [])
                  if it.get("cabinet_type") == "panel"]
        if not panels:
            return
        hosts = [it for it in items
                 if it.get("cabinet_type") in ("base", "wall")]
        valid_x_positions = []
        for h in hosts:
            hx = float(h.get("x_position_in", 0) or 0)
            hw = float(h.get("width_in", 0) or 0)
            valid_x_positions.append(hx + hw)   # right side of host
            for p in panels:
                pw = float(p.get("width_in", 0) or 0)
                valid_x_positions.append(hx - pw)   # left side of host
        for p in panels:
            px = float(p.get("x_position_in", 0) or 0)
            if not any(abs(px - v) <= tol for v in valid_x_positions):
                _logger.warning(
                    "End cap panel product_id=%s layout_key=%s at "
                    "x_position_in=%s is not adjacent to any cabinet "
                    "side face. Panels must never attach to room walls; "
                    "they attach only to the left or right side of a "
                    "base or wall cabinet.",
                    p.get("product_id"), p.get("layout_key"), px,
                )

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
        payload = {
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
        # D17 — Tier-B additive: enrich with archetype taxonomy when
        # the southbrook_estimating archetype map is set. x_prodboard_
        # archetype_id is the canonical M2O to southbrook.cabinet.
        # archetype (223 records: body_class / collection / code from
        # the Prodboard manifest clone). Falls back silently when the
        # template isn't mapped to an archetype.
        # 2026-07-01 audit cleanup — southbrook_estimating became a
        # hard dep on 2026-06-28 (__manifest__.py:22-26), so
        # x_prodboard_archetype_id is guaranteed present at runtime.
        # The hasattr guard was defensive from before the manifest
        # hardened; dead code now.
        archetype = tmpl.x_prodboard_archetype_id or None
        if archetype:
            payload["archetype_code"]       = getattr(archetype, "code", "") or ""
            payload["archetype_body_class"] = getattr(archetype, "body_class", "") or ""
            payload["archetype_collection"] = getattr(archetype, "collection", "") or ""
            # Prefer the archetype-supplied canonical image when set —
            # vendor renders are richer than auto-generated thumbnails.
            canon_img = getattr(archetype, "canonical_image_url", "") or ""
            if canon_img:
                payload["archetype_image_url"] = canon_img
        return payload

    # ─── D3 — channel pricelist resolution ──────────────────────────────────────
    # Centralise partner/pricelist plumbing so /products + /layout
    # share the same resolver and the UI gets a single channel-meta
    # block to render the topbar badge.

    def _browse_partner(self, partner_id):
        """Resolve partner_id to a browsable res.partner while enforcing
        the caller's ACL + record rules. Empty recordset means 'no
        partner, use retail' — never raises so /products keeps
        rendering.

        v19.0.4.22.0 audit P1#5: pre-4.22 this method .sudo()'d the
        browse, letting any authenticated user enumerate every
        partner in the DB via /products or /layout and leak their
        .channel / pricing tier through _channel_meta +
        _resolve_pricelist. The check_access("read") gate degrades
        strangers to retail silently rather than raising (an error
        would leak existence and would break inventory rendering
        for logged-in customers whose portal_user has no partner
        access at all).
        """
        if not partner_id:
            return request.env["res.partner"]
        try:
            pid = int(partner_id)
        except (TypeError, ValueError):
            return request.env["res.partner"]
        if pid <= 0:
            return request.env["res.partner"]
        partner = request.env["res.partner"].browse(pid).exists()
        if not partner:
            return request.env["res.partner"]
        try:
            partner.check_access("read")
        except Exception:
            # Silent degrade — never raise AccessError; would leak
            # existence and would break configurator rendering.
            return request.env["res.partner"]
        return partner

    def _resolve_pricelist(self, partner):
        # Reuses the canonical southbrook_estimating dispatcher so the
        # configurator's live preview matches the price the Order
        # Builder + spec sheet PDF will charge. Falls back to retail
        # when no partner.
        # 2026-07-01 audit cleanup — southbrook_estimating is a hard
        # dep since 2026-06-28, so _resolve_channel_pricelist is
        # guaranteed present. Try/except kept as it protects against
        # partner-side data problems (missing channel, invalid tier).
        SaleOrder = request.env["sale.order"]
        try:
            return SaleOrder._resolve_channel_pricelist(partner)
        except Exception:
            pass
        # Fallback path: partner's property pricelist, else env default.
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
