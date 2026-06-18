# SPDX-License-Identifier: LGPL-3.0-only
"""T2 — Door-area m² computed on the configured variant.

Door area is the load-bearing input for paint / lacquer / spray-finish
pricelist rollups. Today Southbrook prices doors per-piece; Prodboard's
catalogue surfaces a 0.423 m² figure on every cabinet detail panel
because the finish cost actually scales with surface area, not piece
count. Adding the metric lets a future pricelist rule key off it.

Computed from:
  - Width attribute pick (mm)
  - Door Count attribute pick (or derived from family default)
  - cabinet-class default height (720mm Base, 1970mm Tall, 720mm Wall —
    overridable via an explicit Height attribute pick)
  - DOOR_REVEAL = 3mm gap per door edge (from shared.southbrook_dims)

Returns 0.0 when the variant carries no configurator picks (templates
without attribute lines). Stored so reporting + pricelist rules can
domain on it.
"""
from odoo import api, fields, models


# Mirror of shared.southbrook_dims.DOOR_REVEAL — kept local so this
# module doesn't grow a runtime dependency on the shared package just
# for one constant. If the canonical reveal changes, update both.
_DOOR_REVEAL_MM = 3.0


# Class-default heights when the variant doesn't expose Height.
_DEFAULT_HEIGHT_BY_CATEGORY = {
    "Base":   720.0,
    "Drawer": 720.0,
    "Wall":   720.0,
    "Tall":   1970.0,
    "Vanity": 720.0,
}


class ProductProduct(models.Model):
    _inherit = "product.product"

    x_door_area_m2 = fields.Float(
        string="Door Area (m²)",
        compute="_compute_x_door_area_m2",
        store=True,
        digits=(8, 4),
        help="Sum of all door-face areas for this variant in m². "
             "Computed from the configurator's Width pick × "
             "(picked or class-default Height) × picked Door Count, "
             "minus a 3mm reveal per door edge. Used by paint / "
             "lacquer / spray-finish pricelist rules that scale by "
             "surface area rather than per-piece.",
    )

    @api.depends("product_template_attribute_value_ids",
                 "product_template_attribute_value_ids.product_attribute_value_id",
                 "product_tmpl_id.southbrook_category")
    def _compute_x_door_area_m2(self):
        for variant in self:
            try:
                variant.x_door_area_m2 = variant._t2_door_area_m2()
            except Exception:  # noqa: BLE001
                # Never let a malformed pick break the recompute pass —
                # the field is informational, not load-bearing.
                variant.x_door_area_m2 = 0.0

    def _t2_door_area_m2(self):
        self.ensure_one()
        picks = self.product_template_attribute_value_ids
        if not picks:
            return 0.0

        # Index picks by attribute name (case-insensitive, stripped).
        by_attr = {}
        for ptav in picks:
            attr_name = (ptav.attribute_id.name or "").strip().lower()
            value_name = (ptav.product_attribute_value_id.name or "").strip()
            by_attr[attr_name] = value_name

        width_mm = self._t2_parse_dim_mm(by_attr.get("width"))
        height_mm = self._t2_parse_dim_mm(by_attr.get("height"))
        if not height_mm:
            # Fall back to the cabinet-class default per
            # product.template.southbrook_category.
            cat = (self.product_tmpl_id.southbrook_category or "").strip()
            height_mm = _DEFAULT_HEIGHT_BY_CATEGORY.get(cat, 720.0)

        if not width_mm:
            return 0.0

        door_count = self._t2_door_count(by_attr)
        if not door_count:
            return 0.0

        # Geometric door dimensions per shared.southbrook_dims.door():
        #   1 door : (height - 2*reveal) × (width - 2*reveal)
        #   2 doors: (height - 2*reveal) × ((width - 3*reveal)/2) × 2
        door_height_mm = height_mm - 2 * _DOOR_REVEAL_MM
        if door_count == 1:
            door_width_mm = width_mm - 2 * _DOOR_REVEAL_MM
        elif door_count == 2:
            door_width_mm = (width_mm - 3 * _DOOR_REVEAL_MM) / 2.0
        else:
            # 3+ doors aren't supported by the canonical door() function;
            # estimate as (width - (n+1)*reveal) / n per door.
            door_width_mm = (
                width_mm - (door_count + 1) * _DOOR_REVEAL_MM
            ) / float(door_count)
        if door_width_mm <= 0 or door_height_mm <= 0:
            return 0.0
        total_mm2 = door_count * door_width_mm * door_height_mm
        return total_mm2 / 1_000_000.0

    @staticmethod
    def _t2_parse_dim_mm(raw):
        """'24 in' / '600mm' / '600' -> millimetres float. Returns 0 on
        unrecognised input."""
        if not raw:
            return 0.0
        s = str(raw).strip().lower().replace(",", "")
        if "(" in s:
            s = s.split("(", 1)[0].strip()
        is_inches = ("in" in s) or ('"' in s)
        s = s.replace("mm", "").replace("in", "").replace('"', "").replace(" ", "")
        try:
            n = float(s)
        except (TypeError, ValueError):
            return 0.0
        return n * 25.4 if is_inches else n

    def _t2_door_count(self, by_attr):
        explicit = by_attr.get("door count") or by_attr.get("doors")
        if explicit:
            try:
                return int(str(explicit).split()[0])
            except (TypeError, ValueError):
                pass
        # Drawer banks have zero door faces (drawer fronts aren't doors
        # for finish-area purposes — they're priced separately).
        construction = (by_attr.get("drawer construction") or "").lower()
        if construction and "drawer" in construction:
            return 0
        return 1
