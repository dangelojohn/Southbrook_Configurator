# SPDX-License-Identifier: LGPL-3.0-only
"""
NF2 override stub for the OCA product_configurator
validate_configuration mechanism (per Build Spec section 9.1).

Upstream status (OCA v19.0.1.0.0):
  - `product.config.session.validate_configuration()` returns a dict
    `{"value": True}` on success or `{"value": False, "reason": str}`
    on rule-blocked. Brief section 2.2 ("rule reason visible to sales rep")
    works with this dict-return today.
  - There is a `# TODO: Raise ConfigurationError with reason` marker at
    `product_configurator/models/product_config.py:1500`. If OCA upstream
    converts the dict-return to a raise-with-reason pattern, this override
    is the swap point.

Current behaviour: this override is a NO-OP — it does not change the
dict-return contract. Its purpose is to RESERVE the override site so
that swapping from dict-return to raise is a single-file change in
southbrook_estimating, NOT a per-call-site fixup across the codebase.

When OCA upstream switches:
  1. Remove the super() call below.
  2. Replace with a wrapper that catches ConfigurationError, builds the
     same {"value": False, "reason": str(e)} dict, and returns it.
  3. Or invert: convert the dict-return into a raise for consumers that
     prefer exception flow.

3D viewport payload (Track 1 — Charter amendment 1):
  Method `get_3d_payload()` reads the session's value_ids, extracts
  W/H/D + family + door_count + finished_sides, calls Phase-1 routine
  #1 (mrp.bom._compute_panel_dimensions) for the cut list, and converts
  the cut list into a per-panel 3D layout for the OWL Three.js viewport.
  Same named constants drive cut list AND geometry — no fork.
"""
from odoo import api, models


class ProductConfigLine(models.Model):
    """Reserved hook for the NF2 override.

    Currently no-op. See module docstring for the swap rationale.
    """
    _inherit = "product.config.line"

    # No methods overridden today. The class declaration itself is what
    # gives southbrook_estimating priority in the inheritance chain when
    # the swap is needed.


class ProductConfigSession(models.Model):
    """Reserved hook for the NF2 validate_configuration override.

    Currently passes through to upstream verbatim. Locks in the override
    site so future swap is a one-file change.
    """
    _inherit = "product.config.session"

    def validate_configuration(
        self, product_tmpl_id=None, value_ids=None, custom_vals=None, final=True
    ):
        """Pass-through. See module docstring."""
        return super().validate_configuration(
            product_tmpl_id=product_tmpl_id,
            value_ids=value_ids,
            custom_vals=custom_vals,
            final=final,
        )

    # ------------------------------------------------------------------
    # 3D viewport payload — Track 1 of Phase 2 charter amendment 1.
    # ------------------------------------------------------------------
    def get_3d_payload(self):
        """Return JSON payload for the OWL cabinet viewport.

        Pipeline:
          1. Read session.value_ids; extract dimensions + family + door_count
             + finished_sides by walking attribute_id → southbrook xml_ids.
          2. Call mrp.bom._compute_panel_dimensions (Phase-1 routine #1) for
             the cut list.
          3. Translate the cut list into per-panel 3D placements.

        Coordinate system (right-handed, mm):
          X — horizontal (left ↔ right; +X is right)
          Y — vertical   (floor ↔ ceiling; +Y is up)
          Z — depth      (back ↔ front; +Z is forward, toward viewer)
        Cabinet origin sits at the centre of the floor footprint, with
        the back of the cabinet on -Z.

        Returns a dict the OWL component consumes verbatim:
          {
            "panels": [{name, dims:{width,height,depth}, pos:{x,y,z}, material?}, ...],
            "metadata": {family, door_count, width_mm, height_mm, depth_mm},
            "camera":   {target:[x,y,z], position:[x,y,z]},
            "bounds":   {min:[...], max:[...]},
          }
        """
        self.ensure_one()
        cab = self._extract_cabinet_inputs()
        cut = self.env["mrp.bom"]._compute_panel_dimensions(
            width_mm=cab["width_mm"],
            height_mm=cab["height_mm"],
            depth_mm=cab["depth_mm"],
            family=cab["family"],
            door_count=cab["door_count"],
            drawer_count=cab["drawer_count"],
            finished_sides=cab["finished_sides"],
        )
        return self._cut_list_to_3d_payload(cab, cut)

    # ---- helpers ----------------------------------------------------

    def _extract_cabinet_inputs(self):
        """Walk session.value_ids → cabinet input dict.

        When the user hasn't picked an attribute yet, falls back to a
        reasonable demo cabinet so the viewport renders something at
        first wizard open instead of an empty scene.
        """
        ref = self.env.ref
        # Defaults — demo base 1-door 24" wide, 30" tall, 24" deep.
        out = {
            "width_mm": 609,
            "height_mm": 762,
            "depth_mm": 609,
            "family": "base",
            "door_count": 1,
            "drawer_count": 0,
            "finished_sides": "none",
        }

        def attr_xml(name):
            return ref(f"southbrook_estimating.{name}", raise_if_not_found=False)

        attr_width = attr_xml("attr_width")
        attr_height = attr_xml("attr_height")
        attr_depth = attr_xml("attr_depth")
        attr_family = attr_xml("attr_family")
        attr_door_count = attr_xml("attr_door_count")
        attr_finished_sides = attr_xml("attr_finished_sides")

        for val in self.value_ids:
            attr = val.attribute_id
            if attr_width and attr == attr_width and val.value_mm:
                out["width_mm"] = val.value_mm
            elif attr_height and attr == attr_height and val.value_mm:
                out["height_mm"] = val.value_mm
            elif attr_depth and attr == attr_depth and val.value_mm:
                out["depth_mm"] = val.value_mm
            elif attr_family and attr == attr_family:
                out["family"] = (val.name or "base").lower().split()[0]
            elif attr_door_count and attr == attr_door_count:
                # Value names look like "1 Door", "2 Doors", "1", "2".
                first_token = (val.name or "1").strip().split()[0]
                try:
                    out["door_count"] = int(first_token)
                except ValueError:
                    pass
            elif attr_finished_sides and attr == attr_finished_sides:
                out["finished_sides"] = (val.name or "none").lower()
        return out

    @api.model
    def _cut_list_to_3d_payload(self, cab, cut):
        """Translate Phase-1 cut list into 3D panel placements.

        Geometric constants (BOX_TH, BACK_TH, RABBET, DOOR_TH, DOOR_REVEAL,
        TOEKICK_H, TOEKICK_FAMILIES) intentionally re-imported from mrp_bom
        module so the same named constants drive both cut list and 3D
        placement. If a future workbook update changes BOX_TH from 15.875mm
        to something else, both layers update without divergence.

        Track 1 commit 3 family dispatch:
          • worktop   — short-circuit slab (no carcass)
          • accessory — short-circuit end panel (no carcass)
          • drawer    — carcass + N drawer fronts instead of doors
          • toekick families (base/sink/tall/vanity) — carcass elevated
            by TOEKICK_H + toe-kick face panel at the floor
          • everything else — carcass + doors (Phase-1 behaviour)
        """
        from . import mrp_bom as _mb

        BOX_TH = _mb.BOX_TH
        BACK_TH = _mb.BACK_TH
        RABBET = _mb.RABBET
        DOOR_TH = _mb.DOOR_TH
        DOOR_REVEAL = _mb.DOOR_REVEAL
        TOEKICK_H = _mb.TOEKICK_H
        TOEKICK_FAMILIES = _mb.TOEKICK_FAMILIES

        W = cab["width_mm"]
        H = cab["height_mm"]
        D = cab["depth_mm"]
        door_count = cab["door_count"]
        family = cab["family"]

        # ------------------------------------------------------------------
        # Short-circuit families: no carcass, just a single slab.
        # ------------------------------------------------------------------
        if family == "worktop":
            return self._3d_payload_worktop(W, H, D)
        if family == "accessory":
            return self._3d_payload_accessory(W, H, D, BOX_TH)

        # ------------------------------------------------------------------
        # Carcass families (base / wall / sink / tall / vanity / drawer / corner).
        # Toe-kick families lift the carcass off the floor and add a recessed
        # face panel at the front-bottom. Wall + corner sit on the cabinet's
        # own bottom — no toe-kick.
        # ------------------------------------------------------------------
        has_toekick = family in TOEKICK_FAMILIES
        y0 = TOEKICK_H if has_toekick else 0   # carcass bottom y-offset
        inside_w = W - 2 * BOX_TH

        panels = []

        # ---- Sides: vertical, BOX_TH thick. For toekick families the
        #      side panels extend the full visible height (door + toekick);
        #      we approximate by keeping sides at H tall and lifting them.
        panels.append({
            "name": "side_L",
            "dims": {"width": BOX_TH, "height": H, "depth": D},
            "pos":  {"x": -(W - BOX_TH) / 2, "y": y0 + H / 2, "z": -D / 2},
        })
        panels.append({
            "name": "side_R",
            "dims": {"width": BOX_TH, "height": H, "depth": D},
            "pos":  {"x": (W - BOX_TH) / 2, "y": y0 + H / 2, "z": -D / 2},
        })

        # ---- Top + bottom: horizontal, captured between sides.
        panels.append({
            "name": "top",
            "dims": {"width": inside_w, "height": BOX_TH, "depth": D},
            "pos":  {"x": 0, "y": y0 + H - BOX_TH / 2, "z": -D / 2},
        })
        panels.append({
            "name": "bottom",
            "dims": {"width": inside_w, "height": BOX_TH, "depth": D},
            "pos":  {"x": 0, "y": y0 + BOX_TH / 2, "z": -D / 2},
        })

        # ---- Back panel: rabbet-captured.
        back_w = inside_w + 2 * RABBET
        back_h = (H - 2 * BOX_TH) + 2 * RABBET
        panels.append({
            "name": "back",
            "dims": {"width": back_w, "height": back_h, "depth": BACK_TH},
            "pos":  {"x": 0, "y": y0 + H / 2, "z": -D + BACK_TH / 2},
            "material": "back",
        })

        # ---- Shelves (1, 2, or 3) — evenly spaced inside the cavity.
        shelf = cut.get("shelf")
        shelf_count = cut.get("shelf_count", 0)
        if shelf is not None and shelf_count > 0:
            interior_h = H - 2 * BOX_TH
            spacing = interior_h / (shelf_count + 1)
            for i in range(shelf_count):
                shelf_y = y0 + BOX_TH + spacing * (i + 1)
                panels.append({
                    "name": f"shelf_{i + 1}",
                    "dims": {
                        "width": shelf[0],
                        "height": BOX_TH,
                        "depth": shelf[1],
                    },
                    "pos":  {"x": 0, "y": shelf_y, "z": -(D + BACK_TH) / 2 + 6},
                    "material": "shelf",
                })

        # ---- Toe-kick face panel: recessed ~30mm from the door plane,
        #      sits between the floor and the carcass bottom.
        if has_toekick:
            panels.append({
                "name": "toekick",
                "dims": {"width": inside_w, "height": TOEKICK_H, "depth": 18},
                "pos":  {"x": 0, "y": TOEKICK_H / 2, "z": DOOR_TH - 30},
                "material": "toekick",
            })

        # ---- Door OR drawer-front stack, depending on family.
        if family == "drawer":
            self._emit_drawer_fronts(
                panels, W, H, y0, DOOR_TH, DOOR_REVEAL,
                drawer_count=cab["drawer_count"] or door_count or 3,
            )
        else:
            self._emit_doors(panels, W, H, y0, DOOR_TH, DOOR_REVEAL, door_count)

        # ---- Camera framing — 3/4 view, slightly elevated; include the
        #      toe-kick in the framing height for base/tall/sink/vanity.
        total_h = H + y0
        cam_position = [W * 1.4, total_h * 1.25, D * 1.8]
        cam_target = [0, total_h / 2, -D / 2]

        return {
            "panels": panels,
            "metadata": {
                "family": cab["family"],
                "door_count": door_count,
                "width_mm": W,
                "height_mm": H,
                "depth_mm": D,
            },
            "camera": {"target": cam_target, "position": cam_position},
            "bounds": {
                "min": [-W / 2, 0, -D],
                "max": [W / 2, total_h, DOOR_TH + DOOR_REVEAL],
            },
        }

    # ------------------------------------------------------------------
    # _3d_payload helpers — family-specific geometry emitters (commit 3).
    # ------------------------------------------------------------------

    @api.model
    def _3d_payload_worktop(self, W, H, D):
        """Short-circuit payload for the worktop family: a single slab.

        Worktops are countertop slabs, not carcasses. Phase-1 simplified
        worktop_thickness to 25mm — when the canonical workbook lands and
        Caesarstone / quartz / butcher-block thicknesses diverge, this
        becomes attribute-driven.
        """
        worktop_th = 25
        return {
            "panels": [{
                "name": "worktop_slab",
                "dims": {"width": W, "height": worktop_th, "depth": D},
                "pos":  {"x": 0, "y": worktop_th / 2, "z": -D / 2},
                "material": "worktop",
            }],
            "metadata": {
                "family": "worktop",
                "door_count": 0,
                "width_mm": W,
                "height_mm": worktop_th,
                "depth_mm": D,
            },
            "camera": {
                "target":   [0, worktop_th / 2, -D / 2],
                "position": [W * 0.8, W * 0.5, D * 1.5],
            },
            "bounds": {
                "min": [-W / 2, 0, -D],
                "max": [W / 2, worktop_th, 0],
            },
        }

    @api.model
    def _3d_payload_accessory(self, W, H, D, BOX_TH):
        """Short-circuit payload for accessory family: a single flat panel.

        Accessory_type sub-attribute (end_panel / filler / cornice / pelmet
        / plinth, per Q8 spec) tells us which shape to emit. Phase 1 ships
        the end_panel variant only — the others land in Phase 3 polish.
        """
        return {
            "panels": [{
                "name": "end_panel",
                "dims": {"width": BOX_TH, "height": H, "depth": D},
                "pos":  {"x": 0, "y": H / 2, "z": -D / 2},
                "material": "carcass",
            }],
            "metadata": {
                "family": "accessory",
                "door_count": 0,
                "width_mm": W,
                "height_mm": H,
                "depth_mm": D,
            },
            "camera": {
                "target":   [0, H / 2, -D / 2],
                "position": [W * 2, H * 1.2, D * 1.8],
            },
            "bounds": {
                "min": [-BOX_TH / 2, 0, -D],
                "max": [BOX_TH / 2, H, 0],
            },
        }

    @api.model
    def _emit_doors(self, panels, W, H, y0, DOOR_TH, DOOR_REVEAL, door_count):
        """Append the door panel(s) for a non-drawer carcass.

        Phase-1 NF14 conventions:
          • 1-door: door spans (W − 2*DOOR_REVEAL) × (H − 2*DOOR_REVEAL).
          • 2-door: each leaf spans ((W − 3*DOOR_REVEAL)/2) × (H − 2*DOOR_REVEAL),
            with a centre reveal of DOOR_REVEAL between them.
        """
        if door_count == 1:
            panels.append({
                "name": "door",
                "dims": {
                    "width": W - 2 * DOOR_REVEAL,
                    "height": H - 2 * DOOR_REVEAL,
                    "depth": DOOR_TH,
                },
                "pos":  {"x": 0, "y": y0 + H / 2, "z": DOOR_TH / 2 + DOOR_REVEAL},
                "material": "door",
            })
        elif door_count == 2:
            half_w = (W - 3 * DOOR_REVEAL) / 2
            for idx, sign in enumerate((-1, 1), start=1):
                panels.append({
                    "name": f"door_{idx}",
                    "dims": {
                        "width": half_w,
                        "height": H - 2 * DOOR_REVEAL,
                        "depth": DOOR_TH,
                    },
                    "pos":  {
                        "x": sign * (half_w / 2 + DOOR_REVEAL / 2),
                        "y": y0 + H / 2,
                        "z": DOOR_TH / 2 + DOOR_REVEAL,
                    },
                    "material": "door",
                })

    @api.model
    def _emit_drawer_fronts(self, panels, W, H, y0, DOOR_TH, DOOR_REVEAL,
                            drawer_count):
        """Append `drawer_count` evenly-divided drawer fronts.

        Algorithm (Phase-1 simplification: all fronts the same height):
            total_face_h = H − 2*DOOR_REVEAL             (top + bottom reveals)
            front_h      = (total_face_h − (n−1)*DOOR_REVEAL) / n
            Front i (0-indexed from bottom) sits at:
              y_centre = y0 + DOOR_REVEAL + front_h/2 + i*(front_h + DOOR_REVEAL)

        Phase-3 polish: graduated front heights (deeper drawers at bottom
        per real cabinetry practice) — pulled from the BoM workbook when
        it lands.
        """
        n = max(1, int(drawer_count))
        face_w = W - 2 * DOOR_REVEAL
        front_h = (H - 2 * DOOR_REVEAL - (n - 1) * DOOR_REVEAL) / n
        for i in range(n):
            y_centre = y0 + DOOR_REVEAL + front_h / 2 + i * (front_h + DOOR_REVEAL)
            panels.append({
                "name": f"drawer_front_{i + 1}",
                "dims": {"width": face_w, "height": front_h, "depth": DOOR_TH},
                "pos":  {"x": 0, "y": y_centre, "z": DOOR_TH / 2 + DOOR_REVEAL},
                "material": "door",
            })
