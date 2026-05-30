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

        Geometric constants (BOX_TH, BACK_TH, RABBET, DOOR_TH, DOOR_REVEAL)
        intentionally re-imported from mrp_bom module so the same named
        constants drive both cut list and 3D placement. If a future workbook
        update changes BOX_TH from 15.875mm to something else, both layers
        update without divergence.
        """
        from . import mrp_bom as _mb

        BOX_TH = _mb.BOX_TH
        BACK_TH = _mb.BACK_TH
        RABBET = _mb.RABBET
        DOOR_TH = _mb.DOOR_TH
        DOOR_REVEAL = _mb.DOOR_REVEAL

        W = cab["width_mm"]
        H = cab["height_mm"]
        D = cab["depth_mm"]
        door_count = cab["door_count"]
        inside_w = W - 2 * BOX_TH

        panels = []

        # ---- Sides: vertical, full height, full depth, BOX_TH thick.
        panels.append({
            "name": "side_L",
            "dims": {"width": BOX_TH, "height": H, "depth": D},
            "pos":  {"x": -(W - BOX_TH) / 2, "y": H / 2, "z": -D / 2},
        })
        panels.append({
            "name": "side_R",
            "dims": {"width": BOX_TH, "height": H, "depth": D},
            "pos":  {"x": (W - BOX_TH) / 2, "y": H / 2, "z": -D / 2},
        })

        # ---- Top + bottom: horizontal, captured between sides.
        panels.append({
            "name": "top",
            "dims": {"width": inside_w, "height": BOX_TH, "depth": D},
            "pos":  {"x": 0, "y": H - BOX_TH / 2, "z": -D / 2},
        })
        panels.append({
            "name": "bottom",
            "dims": {"width": inside_w, "height": BOX_TH, "depth": D},
            "pos":  {"x": 0, "y": BOX_TH / 2, "z": -D / 2},
        })

        # ---- Back panel: rabbet-captured.
        back_w = inside_w + 2 * RABBET
        back_h = (H - 2 * BOX_TH) + 2 * RABBET
        panels.append({
            "name": "back",
            "dims": {"width": back_w, "height": back_h, "depth": BACK_TH},
            "pos":  {"x": 0, "y": H / 2, "z": -D + BACK_TH / 2},
            "material": "back",
        })

        # ---- Shelf (optional).
        shelf = cut.get("shelf")
        if shelf is not None:
            shelf_y = H / 2  # mid-height for Phase 1; height-aware in Phase 3.
            panels.append({
                "name": "shelf",
                "dims": {"width": shelf[0], "height": BOX_TH, "depth": shelf[1]},
                "pos":  {"x": 0, "y": shelf_y, "z": -(D + BACK_TH) / 2 + 6},
                "material": "shelf",
            })

        # ---- Doors.
        if door_count == 1:
            door_w = W - 2 * DOOR_REVEAL
            door_h = H - 2 * DOOR_REVEAL
            panels.append({
                "name": "door",
                "dims": {"width": door_w, "height": door_h, "depth": DOOR_TH},
                "pos":  {
                    "x": 0,
                    "y": H / 2,
                    "z": DOOR_TH / 2 + DOOR_REVEAL,
                },
                "material": "door",
            })
        elif door_count == 2:
            half_w = (W - 3 * DOOR_REVEAL) / 2
            door_h = H - 2 * DOOR_REVEAL
            for sign in (-1, 1):
                panels.append({
                    "name": f"door_{1 if sign < 0 else 2}",
                    "dims": {"width": half_w, "height": door_h, "depth": DOOR_TH},
                    "pos":  {
                        "x": sign * (half_w / 2 + DOOR_REVEAL / 2),
                        "y": H / 2,
                        "z": DOOR_TH / 2 + DOOR_REVEAL,
                    },
                    "material": "door",
                })

        # ---- Camera framing — 3/4 view, slightly elevated.
        cam_position = [W * 1.4, H * 1.25, D * 1.8]
        cam_target = [0, H / 2, -D / 2]

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
                "max": [W / 2, H, DOOR_TH + DOOR_REVEAL],
            },
        }
