# SPDX-License-Identifier: LGPL-3.0-only
"""Inherit southbrook.room.constraint to add kitchen-appliance + opening
metadata (swing direction, sill height, panel count, catalog template
link). Lives in southbrook_kitchen_workspace so the estimating module
stays focused on cabinet placement.

The selection_add extends constraint_type with the richer appliance
keys from the placeholder catalog so each appliance variant can have
its own architectural symbol on the floor plan (Stage B). Mapping
choices when collapse is required (e.g. range_double_oven → oven) live
in the @api.onchange below.
"""
from odoo import api, fields, models


# Mapping: product.template.kitchen_appliance_type → constraint_type.
# When a constraint snapshots from a catalog template, this picks the
# right architectural symbol. New keys (range, microwave, wine_fridge…)
# are added via selection_add below.
_TEMPLATE_TYPE_MAP = {
    "range": "range",
    "cooktop": "cooktop",
    "wall_oven": "oven",
    "wall_oven_double": "oven",
    "microwave": "microwave",
    "steam_oven": "oven",
    "speed_oven": "oven",
    "warming_drawer": "warming_drawer",
    "range_hood": "rangehood",
    "refrigerator": "fridge_space",
    "freezer": "freezer",
    "refrigerator_drawer": "fridge_space",
    "wine_fridge": "wine_fridge",
    "beverage_center": "beverage_center",
    "ice_maker": "ice_maker",
    "dishwasher": "dishwasher",
    "sink": "sink",
    "disposal": "other",
    "trash_compactor": "trash_compactor",
    "coffee_built_in": "coffee_built_in",
    "other": "other",
}


class SouthbrookRoomConstraint(models.Model):
    _inherit = "southbrook.room.constraint"

    constraint_type = fields.Selection(
        selection_add=[
            ("range", "Range"),
            ("microwave", "Microwave"),
            ("freezer", "Freezer"),
            ("wine_fridge", "Wine Fridge"),
            ("beverage_center", "Beverage Center"),
            ("warming_drawer", "Warming Drawer"),
            ("ice_maker", "Ice Maker"),
            ("trash_compactor", "Trash Compactor"),
            ("coffee_built_in", "Built-In Coffee"),
        ],
        ondelete={
            "range": "set default",
            "microwave": "set default",
            "freezer": "set default",
            "wine_fridge": "set default",
            "beverage_center": "set default",
            "warming_drawer": "set default",
            "ice_maker": "set default",
            "trash_compactor": "set default",
            "coffee_built_in": "set default",
        },
    )

    # ------------------------------------------------------------------
    # Door-specific
    # ------------------------------------------------------------------
    swing_direction = fields.Selection(
        [
            ("left", "Left-Hand"),
            ("right", "Right-Hand"),
            ("pocket", "Pocket"),
            ("sliding", "Sliding"),
            ("bifold", "Bifold"),
            ("none", "None / N/A"),
        ],
        default="none",
        help="Used by the floor-plan symbol to draw the door swing arc. "
             "Left-hand = hinged on the left looking from the room into "
             "the doorway; right-hand the opposite.",
    )

    # ------------------------------------------------------------------
    # Window-specific
    # ------------------------------------------------------------------
    panel_count = fields.Integer(
        string="Window Panel Count",
        default=1,
        help="Number of glass panels (1 single-hung, 2 double-hung / "
             "double casement, 3+ for picture / bay assemblies).",
    )

    # ------------------------------------------------------------------
    # Appliance-template link — snapshot dims from catalog when set
    # ------------------------------------------------------------------
    appliance_template_id = fields.Many2one(
        "product.template",
        string="Appliance Template",
        domain=[("is_kitchen_appliance", "=", True)],
        index=True,
        help="Pick a catalog appliance to auto-fill type + width + height. "
             "Leave blank for windows / doors / custom obstacles.",
    )

    @api.onchange("appliance_template_id")
    def _onchange_appliance_template_id(self):
        for rec in self:
            tmpl = rec.appliance_template_id
            if not tmpl:
                continue
            mapped = _TEMPLATE_TYPE_MAP.get(
                tmpl.kitchen_appliance_type, "other",
            )
            rec.constraint_type = mapped
            if tmpl.kitchen_appliance_width_mm:
                rec.width_mm = int(tmpl.kitchen_appliance_width_mm)
            if tmpl.kitchen_appliance_height_mm:
                rec.height_mm = int(tmpl.kitchen_appliance_height_mm)
            # Counter-height appliances (range, cooktop, dishwasher,
            # sink) sit on the floor; wall-mounted appliances (hood,
            # wall_oven, microwave) typically start above the worktop.
            # Defaults are conservative — the designer can fine-tune.
            if tmpl.kitchen_appliance_type in (
                "wall_oven", "wall_oven_double", "microwave",
            ) and not rec.height_from_floor_mm:
                rec.height_from_floor_mm = 900
            if tmpl.kitchen_appliance_type == "range_hood":
                rec.height_from_floor_mm = max(
                    rec.height_from_floor_mm, 1400,
                )
