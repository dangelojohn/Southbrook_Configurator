# SPDX-License-Identifier: LGPL-3.0-only
"""
sale.order.line extension — Q21 zone field.

Per Q21 locked decision (Image Floor case study NF9 confirmation):
6-value selection plus a free-text zone_label that's only visible when
zone='other'. NO separate ORM model — zone is just a field on the line.

The Order Builder view in views/sale_order_views.xml groups lines by zone
via the standard `<group expand="1" string="Zone">` pattern. The
customer-facing spec sheet (Phase 1 QWeb report, custom routine #6)
also groups by zone for the print-out.
"""
import re

from odoo import api, fields, models


# Phase 3 Sprint B2 — live-compute defaults when the variant carries no
# resolved attribute dimensions (today's demo seed). These are the
# Excel-Mapping §3.3 "default" values per attribute envelope.
_SB_DEFAULT_HEIGHT_MM = 720.0   # base cabinet standard
_SB_DEFAULT_WALL_HEIGHT_MM = 760.0
_SB_DEFAULT_TALL_HEIGHT_MM = 2100.0
_SB_DEFAULT_DEPTH_MM = 580.0     # base
_SB_DEFAULT_WALL_DEPTH_MM = 310.0
_SB_DEFAULT_TALL_DEPTH_MM = 600.0
_SB_DEFAULT_WIDTH_MM = 600.0

# Width parser: matches '24"', '24 in', '24in', '24″', '24″ ' etc.
# Group 1 is the integer inches. Crucially this works on the line.name
# strings the demo seed uses ("Base 2-Door · Contemporary · ... · 30"").
_WIDTH_INCHES_RE = re.compile(r'(\d{1,3})\s*(?:"|″|in\b|in\.\b)', re.I)

# 1 inch = 25.4 mm. Cabinet widths almost always quoted in inches in
# North America; mm if European customer. mm pattern guards either way.
_WIDTH_MM_RE = re.compile(r'(\d{2,4})\s*mm\b', re.I)

# Family parser: looks at line.name OR the variant SKU for the
# standard 5 family tokens.
_FAMILY_RE = re.compile(
    r'\b(base|wall|tall|drawer|sink|vanity|pantry|island|corner)\b', re.I,
)

# Door-count parser: '1-Door', '2-Door', '2 door', '3-drawer' (drawers
# count as doors for hinge/handle quantity purposes here).
_DOOR_COUNT_RE = re.compile(
    r'(\d)\s*[-– ]\s*(?:door|drawer)', re.I,
)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    zone = fields.Selection(
        selection=[
            ("base_run", "Base Run"),
            ("wall", "Wall"),
            ("tall", "Tall"),
            ("island", "Island"),
            ("accessory", "Accessory"),
            ("other", "Other"),
        ],
        string="Zone",
        default="base_run",
        help=(
            "Which kitchen zone this line belongs to. Drives the multi-zone "
            "grid in the Order Builder backend and the customer-facing "
            "spec-sheet PDF grouping. Q21 + NF9 (Richwood pattern)."
        ),
    )
    zone_label = fields.Char(
        string="Zone Label",
        help=(
            "Free-text label, visible only when zone='other'. Captures the "
            "long tail of zone names that don't fit the 5 named zones "
            "(e.g. 'Laundry', 'Mudroom', 'Bar')."
        ),
    )

    # ------------------------------------------------------------------
    # Phase 3 Sprint B2 — live-compute BoM rollup (option (b) from
    # docs/PHASE_3_PLAN.md). The demo seed creates variants without a
    # product.config.session, so the panel/door numbers can't be read
    # from session metadata. Instead we derive them from:
    #   1. variant's product_template_attribute_value_ids when present
    #   2. line.name fallback parse (width, family, door count)
    #   3. hardcoded family defaults from southbrook_dims constants
    # Closes the gate-walk D4 zero-rollup gap that PHASE_2_TRACK_2_GATE
    # documented as a known Phase-1 limitation.
    # ------------------------------------------------------------------

    sb_panel_count = fields.Integer(
        string="Panel Count",
        compute="_compute_sb_panel_rollup",
        store=False,
        help="Total panel pieces in the cabinet's cutlist (sides + top + "
             "bottom + back + shelves + door). Live-computed from "
             "variant attributes when present; falls back to parsing "
             "line.name when not (demo-seed friendly).",
    )
    sb_door_count = fields.Integer(
        string="Door Count",
        compute="_compute_sb_panel_rollup",
        store=False,
        help="Number of door/drawer fronts on this cabinet line.",
    )
    sb_width_mm = fields.Float(
        string="Width (mm)",
        compute="_compute_sb_panel_rollup",
        store=False,
        digits=(8, 1),
    )

    @api.depends(
        "product_id", "product_id.product_template_attribute_value_ids",
        "name", "product_uom_qty",
    )
    def _compute_sb_panel_rollup(self):
        for line in self:
            dims = line._sb_derive_dimensions()
            family = dims["family"]
            try:
                # Local import: panel_cut_list lives in /srv/shared via
                # PYTHONPATH. Wrap so a missing shared mount degrades
                # to (0, 0, 0) rather than crashing the order view.
                from southbrook_dims import panel_cut_list
                cut = panel_cut_list(
                    dims["width_mm"], dims["height_mm"],
                    dims["depth_mm"], family=family,
                    door_count=dims["door_count"],
                )
            except Exception:  # noqa: BLE001
                line.sb_panel_count = 0
                line.sb_door_count = 0
                line.sb_width_mm = dims["width_mm"]
                continue
            # Pieces per cabinet (single-cabinet line). Sides + top +
            # bottom + back + each shelf + each door front.
            pieces = 4 + 1  # sides L + R + top + bottom + back
            pieces += int(cut.get("shelf_count") or 0)
            if cut.get("door") and dims["door_count"]:
                pieces += int(dims["door_count"])
            qty = int(line.product_uom_qty or 1)
            line.sb_panel_count = pieces * qty
            line.sb_door_count = int(dims["door_count"]) * qty
            line.sb_width_mm = dims["width_mm"]

    def _sb_derive_dimensions(self):
        """Best-effort W/H/D + family + door_count derivation.

        Reads variant attributes first (Width, Family, Door Count if any
        of them are on the variant), then falls back to parsing the
        line's `name` string, then to hardcoded family defaults.

        Returns: dict with width_mm, height_mm, depth_mm, family,
        door_count. Never raises — callers can rely on a complete dict.
        """
        self.ensure_one()
        family = None
        width_mm = None
        door_count = None
        # 1. Variant attribute values — preferred when present.
        if self.product_id:
            for ptav in self.product_id.product_template_attribute_value_ids:
                attr_name = (ptav.attribute_id.name or "").lower()
                val_name = ptav.name or ""
                if "family" in attr_name and not family:
                    m = _FAMILY_RE.search(val_name)
                    family = m.group(1).lower() if m else val_name.lower()
                elif "width" in attr_name and not width_mm:
                    # Attribute values typically look like '24"' or '600mm'.
                    m = _WIDTH_MM_RE.search(val_name)
                    if m:
                        width_mm = float(m.group(1))
                    else:
                        m = _WIDTH_INCHES_RE.search(val_name)
                        if m:
                            width_mm = float(m.group(1)) * 25.4
                elif "door" in attr_name and not door_count:
                    m = re.search(r'\d', val_name)
                    if m:
                        door_count = int(m.group(0))
        # 2. Fall back to parsing line.name for whatever is still None.
        name = self.name or ""
        if not family:
            m = _FAMILY_RE.search(name)
            family = m.group(1).lower() if m else "base"
        # Normalize synonyms to the family enum southbrook_dims uses.
        if family in ("pantry", "tall"):
            family = "tall"
        elif family in ("drawer", "base", "sink", "island", "corner"):
            family = "base"
        elif family == "vanity":
            family = "vanity"
        elif family == "wall":
            family = "wall"
        else:
            family = "base"
        if not width_mm:
            m = _WIDTH_MM_RE.search(name)
            if m:
                width_mm = float(m.group(1))
            else:
                m = _WIDTH_INCHES_RE.search(name)
                if m:
                    width_mm = float(m.group(1)) * 25.4
        if not door_count:
            m = _DOOR_COUNT_RE.search(name)
            door_count = int(m.group(1)) if m else 1
        # 3. Final family-default fallbacks for H + D.
        if family == "wall":
            height_mm = _SB_DEFAULT_WALL_HEIGHT_MM
            depth_mm = _SB_DEFAULT_WALL_DEPTH_MM
        elif family == "tall":
            height_mm = _SB_DEFAULT_TALL_HEIGHT_MM
            depth_mm = _SB_DEFAULT_TALL_DEPTH_MM
        else:
            height_mm = _SB_DEFAULT_HEIGHT_MM
            depth_mm = _SB_DEFAULT_DEPTH_MM
        return {
            "width_mm": width_mm or _SB_DEFAULT_WIDTH_MM,
            "height_mm": height_mm,
            "depth_mm": depth_mm,
            "family": family,
            "door_count": door_count or 1,
        }

    @api.onchange("zone")
    def _onchange_zone_clear_label(self):
        """Clear zone_label when leaving the 'other' zone."""
        for line in self:
            if line.zone != "other":
                line.zone_label = False

    # ------------------------------------------------------------------
    # T1C8 — Click-to-edit entry point for the OWL kitchen viewport.
    #
    # When the sales rep clicks a cabinet in the 3D Kitchen Preview
    # canvas, the OWL component raycasts the mesh to find the line id,
    # then calls this method via JSON-RPC. The returned action dict is
    # dispatched by the OWL action service — typically opening the OCA
    # configurator wizard for the line's product so the rep can
    # reconfigure the cabinet (width, family, door style, etc.).
    # ------------------------------------------------------------------
    def action_reconfigure(self):
        """Launch the OCA configurator wizard for this line.

        Returns the action dict produced by
        product.template.action_southbrook_launch_3d_configurator()
        — which itself wraps OCA's configure_product(). The wizard
        opens with the line's product pre-selected and any existing
        config_session_id reused.

        If the line has no product or no template (free-text line,
        comment, etc.), returns False so the OWL component shows a
        gentle no-op rather than crashing.
        """
        self.ensure_one()
        tmpl = (
            self.product_id.product_tmpl_id
            if self.product_id and self.product_id.product_tmpl_id
            else None
        )
        if not tmpl:
            return False
        return tmpl.action_southbrook_launch_3d_configurator()
