# SPDX-License-Identifier: LGPL-3.0-only
"""Prebuilt sample kitchen templates (Kitchen Templates T1).

southbrook.kitchen.template + southbrook.kitchen.template.line: the data
model behind "start from a prebuilt sample kitchen" instead of an empty
room. Templates carry SLOTS, not SKU pins — a resolver (T2) maps
slot -> product at instantiation time, then hands off to the existing
auto-arrange engine for all geometry. See:
docs/superpowers/specs/2026-07-27-kitchen-templates-design.md

No geometry fields live here — `wall` + `run_seq` is the whole spatial
contract; the kitchen_layout_engine (via action_auto_arrange) owns poses.
"""
from odoo import api, fields, models

# Reuse — never fork — the room lexicon and the design-line zone lexicon.
from odoo.addons.southbrook_estimating.models.southbrook_room import _LAYOUT_SHAPES
from .kitchen_design import ZONE_SELECTION, _ZONE_FROM_CABINET_TYPE


class SouthbrookKitchenTemplate(models.Model):
    _name = "southbrook.kitchen.template"
    _description = "Prebuilt Sample Kitchen Template"
    _order = "sequence, id"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True,
                        help="Stable short code (e.g. L-10X8). Referenced by the "
                             "picker's legacy-preset compat map.")
    description = fields.Text()
    layout_shape = fields.Selection(selection=_LAYOUT_SHAPES, required=True,
                                     default="straight")
    default_room_width_in = fields.Float(required=True, default=120.0, digits=(6, 2))
    default_room_depth_in = fields.Float(required=True, default=96.0, digits=(6, 2))
    default_room_height_in = fields.Float(required=True, default=96.0, digits=(6, 2))
    default_module_width_in = fields.Float(required=True, default=24.0, digits=(6, 2))
    min_cabinet_count = fields.Integer(default=1)
    max_cabinet_count = fields.Integer(
        default=0, help="0 = engine-bounded only (n_max).")
    default_filler_strategy = fields.Selection(
        [("split", "Split (both ends)"), ("right", "Right side"),
         ("left", "Left side"), ("scribe", "Scribe (no filler)")],
        default="split", required=True)
    default_wall_cab_top_alignment = fields.Selection(
        [("fixed_gap", "Fixed 18\" gap above counter"),
         ("to_ceiling", "Up to ceiling"), ("to_soffit", "Up to soffit")],
        default="fixed_gap", required=True)
    # NOTE: plain Binary, NOT fields.Image — PIL (Image's backing codec)
    # rejects SVG, and the generated top-view preview (T3) is an SVG.
    # A manual override upload therefore also has to accept SVG, so the
    # field must stay Binary for both the generated and override paths.
    thumbnail = fields.Binary(
        attachment=True,
        help="Optional manual override; the generated top-view SVG (T3) "
             "is the default preview.")
    thumbnail_filename = fields.Char()
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    notes = fields.Text()
    line_ids = fields.One2many("southbrook.kitchen.template.line",
                                "template_id", string="Slots", copy=True)

    _code_uniq = models.Constraint(
        "unique (code)",
        "Template code must be unique.",
    )


class SouthbrookKitchenTemplateLine(models.Model):
    _name = "southbrook.kitchen.template.line"
    _description = "Kitchen Template Slot"
    _order = "wall, run_seq, sequence, id"

    template_id = fields.Many2one("southbrook.kitchen.template", required=True,
                                   ondelete="cascade", index=True)
    slot_code = fields.Char(required=True,
                             help="Stable per-template slot id (SINK, RANGE, B1…).")
    cabinet_type = fields.Selection(
        [("base", "Base Cabinet"), ("wall", "Wall Cabinet"),
         ("tall", "Tall Cabinet"), ("corner", "Corner Preference"),
         ("appliance", "Appliance Space")],
        required=True, default="base",
        help="Corner slots carry a PRODUCT PREFERENCE only — the corner "
             "engine (M2 rules-as-data) owns all corner geometry. Fillers "
             "are never templated (M3 derives them).")
    zone = fields.Selection(selection=ZONE_SELECTION, compute="_compute_zone",
                             store=True, readonly=False, precompute=True)
    wall = fields.Selection(
        [("back", "Back"), ("left", "Left"),
         ("right", "Right"), ("front", "Front")],
        required=True, default="back")
    run_seq = fields.Integer(default=0)
    sequence = fields.Integer(default=10)
    nominal_width_in = fields.Float(
        default=0.0, digits=(6, 2),
        help="0 = this slot takes the parametric module width.")
    archetype_id = fields.Many2one("southbrook.cabinet.archetype",
                                    string="Archetype (preferred)")
    product_id = fields.Many2one("product.product", string="Pinned Product",
                                  help="Optional hard pin for fixed quotable BOMs; "
                                       "wins over the archetype resolver.")
    is_appliance_slot = fields.Boolean(compute="_compute_is_appliance", store=True)
    appliance_type = fields.Selection(
        [("range", "Range"), ("fridge", "Fridge"),
         ("dishwasher", "Dishwasher"), ("hood", "Hood"), ("other", "Other")])
    repeat_ok = fields.Boolean(
        default=False,
        help="When the requested cabinet count exceeds this template's module "
             "slots, slots flagged repeat_ok are cloned (in run order) to fill.")
    priority = fields.Integer(
        default=10,
        help="Drop order when the room/count shrinks — HIGHER drops first.")
    notes = fields.Char()

    @api.depends("cabinet_type")
    def _compute_zone(self):
        for line in self:
            if not line.zone:
                line.zone = ("accessory" if line.cabinet_type == "appliance"
                             else _ZONE_FROM_CABINET_TYPE.get(line.cabinet_type,
                                                               "other"))

    @api.depends("cabinet_type")
    def _compute_is_appliance(self):
        for line in self:
            line.is_appliance_slot = line.cabinet_type == "appliance"
