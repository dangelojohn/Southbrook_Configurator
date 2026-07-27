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


# ── Task 2: resolver + parametric fit + instantiation ─────────────────────
# Appended below both model classes so the file reads models-first. The
# heavy lifting (poses, corners, fillers) belongs to action_auto_arrange /
# kitchen_layout_engine — nothing here computes geometry.

from odoo.exceptions import UserError  # noqa: E402
from odoo.addons.southbrook_estimating.models import kitchen_layout_engine  # noqa: E402

_APPLIANCE_PRODUCT_XMLID = {
    "range": "southbrook_kitchen_3d_configurator.product_tmpl_appl_range",
    "fridge": "southbrook_kitchen_3d_configurator.product_tmpl_appl_fridge",
    "dishwasher": "southbrook_kitchen_3d_configurator.product_tmpl_appl_dishwasher",
    "hood": "southbrook_kitchen_3d_configurator.product_tmpl_appl_hood",
}


class SouthbrookKitchenTemplateResolve(models.Model):
    _inherit = "southbrook.kitchen.template"

    # -- resolver ------------------------------------------------------
    def _resolve_slot(self, slot, width_in):
        """Map a template slot to a concrete product.product.

        Precedence: hard pin > archetype link (+width match) >
        cabinet_type + exact width > EMPTY RECORDSET (= unresolved; the
        caller creates a visible placeholder — honesty contract: never a
        silent substitute, never a dropped slot). Appliance slots resolve
        to the SBK-APPL-* stand-in for their appliance_type.
        """
        self.ensure_one()
        Product = self.env["product.product"]
        if slot.cabinet_type == "appliance":
            xmlid = _APPLIANCE_PRODUCT_XMLID.get(slot.appliance_type or "")
            tmpl = xmlid and self.env.ref(xmlid, raise_if_not_found=False)
            return tmpl.product_variant_id if tmpl else Product
        if slot.product_id:
            return slot.product_id
        if slot.archetype_id:
            tmpls = self.env["product.template"].search([
                ("x_prodboard_archetype_id", "=", slot.archetype_id.id),
                ("southbrook_is_cabinet", "=", True),
            ])
            if tmpls:
                # Prefer a width match when the archetype maps to several.
                exact = tmpls.filtered(
                    lambda t: abs((t.southbrook_width_in or 0.0) - width_in) < 0.51)
                return (exact[:1] or tmpls[:1]).product_variant_id
            return Product  # archetype known, no linked product -> unresolved
        # Last rung: cabinet_type + exact width among flagged cabinets.
        tmpls = self.env["product.template"].search([
            ("southbrook_is_cabinet", "=", True),
            ("southbrook_cabinet_type", "=", slot.cabinet_type),
        ])
        exact = tmpls.filtered(
            lambda t: abs((t.southbrook_width_in or 0.0) - width_in) < 0.51)
        return exact[:1].product_variant_id if exact else Product

    # -- parametric fill math (spec §Parametric fill math) --------------
    def parametric_fit(self, cabinet_count=None, module_width_in=None,
                       appliance_widths=None):
        """Pure math: bound the count, size every slot, trim/grow modules.

        Returns {"ok", "message", "count", "n_max", "module_width_in",
        "slots": [(slot, width_in), ...]}. UI-grade bound only — the
        AUTHORITATIVE fit check stays LayoutCapacityExceeded at
        auto-arrange time (single source of truth for geometry).
        """
        self.ensure_one()
        module_w = float(module_width_in or self.default_module_width_in or 24.0)
        appliance_widths = appliance_widths or {}
        wall_len = float(self.default_room_width_in or 0.0)
        corner_in = kitchen_layout_engine._CORNER_FOOTPRINT_MM / 25.4

        slots = self.line_ids.sorted(lambda s: (s.wall, s.run_seq, s.sequence))
        base_like = slots.filtered(
            lambda s: s.cabinet_type in ("base", "tall") and not s.product_id
            or (s.cabinet_type in ("base", "tall") and s.repeat_ok))
        corner_claims = corner_in * len(slots.filtered(
            lambda s: s.cabinet_type == "corner"))
        fixed = 0.0
        for s in slots:
            if s.cabinet_type == "appliance":
                fixed += float(appliance_widths.get(
                    s.appliance_type or "", s.nominal_width_in or 0.0))
            elif s.cabinet_type in ("wall", "corner"):
                continue  # wall tier / engine-claimed
            elif not s.repeat_ok and (s.nominal_width_in or s.product_id):
                fixed += float(
                    s.nominal_width_in
                    or s.product_id.product_tmpl_id.southbrook_width_in
                    or module_w)
        usable = wall_len - corner_claims - fixed
        n_max = int(usable // module_w) if module_w > 0 else 0
        repeat_slots = slots.filtered(
            lambda s: s.repeat_ok and s.cabinet_type in ("base", "tall"))
        floor_slots = slots.filtered(
            lambda s: s.cabinet_type not in ("wall", "corner"))
        n_fixed_modules = len(floor_slots.filtered(
            lambda s: s.cabinet_type != "appliance")) - len(repeat_slots)
        count = cabinet_count if cabinet_count is not None else (
            n_fixed_modules + len(repeat_slots))
        min_count = max(self.min_cabinet_count or 1, n_fixed_modules)
        cap = n_fixed_modules + max(n_max, 0)
        if count > cap:
            return {"ok": False, "count": count, "n_max": cap,
                    "module_width_in": module_w, "slots": [],
                    "message": (
                        "%(tpl)s cannot fit %(count)d cabinets of %(w)g\" in a "
                        "%(room)g\" room (max %(cap)d with the chosen appliance "
                        "sizes). Reduce the count or module width — the room "
                        "is never grown automatically." % {
                            "tpl": self.name, "count": count, "w": module_w,
                            "room": wall_len, "cap": cap})}
        if count < min_count:
            return {"ok": False, "count": count, "n_max": cap,
                    "module_width_in": module_w, "slots": [],
                    "message": "%s needs at least %d cabinets." % (
                        self.name, min_count)}
        n_repeat_needed = count - n_fixed_modules
        if n_repeat_needed > 0 and not repeat_slots:
            return {"ok": False, "count": count, "n_max": cap,
                    "module_width_in": module_w, "slots": [],
                    "message": "%s has no repeatable slot to grow the run." %
                               self.name}
        out = []
        for s in slots:
            if s.cabinet_type == "appliance":
                out.append((s, float(appliance_widths.get(
                    s.appliance_type or "", s.nominal_width_in or 0.0))))
            elif s.cabinet_type == "corner":
                continue  # engine inserts corners; slot is a preference only
            elif s.repeat_ok:
                for _n in range(max(n_repeat_needed, 0) or 0):
                    out.append((s, s.nominal_width_in or module_w))
                if n_repeat_needed <= 0:
                    # trimmed away entirely (count == fixed modules)
                    continue
            else:
                out.append((s, float(
                    s.nominal_width_in
                    or (s.product_id.product_tmpl_id.southbrook_width_in
                        if s.product_id else 0.0)
                    or module_w)))
        return {"ok": True, "message": "", "count": count, "n_max": cap,
                "module_width_in": module_w, "slots": out}

    # -- instantiation ---------------------------------------------------
    def action_instantiate(self, partner_id=False, cabinet_count=None,
                           module_width_in=None, appliance_widths=None):
        """Create a draft design from this template and let the EXISTING
        auto-arrange engine derive every pose/corner/filler. Savepoint-
        atomic: a failed fit leaves nothing behind (no silent room growth).
        """
        self.ensure_one()
        fit = self.parametric_fit(cabinet_count, module_width_in,
                                  appliance_widths)
        if not fit["ok"]:
            raise UserError(fit["message"])
        Design = self.env["southbrook.kitchen.design"]
        Line = self.env["southbrook.kitchen.design.line"]
        unresolved_tmpl = self.env.ref(
            "southbrook_kitchen_3d_configurator.product_tmpl_unresolved_slot")
        with self.env.cr.savepoint():
            design = Design.create({
                "name": self.name,
                "partner_id": partner_id or False,
                "room_width_in": self.default_room_width_in,
                "room_depth_in": self.default_room_depth_in,
                "room_height_in": self.default_room_height_in,
                "filler_strategy": self.default_filler_strategy,
                "wall_cab_top_alignment": self.default_wall_cab_top_alignment,
            })
            for idx, (slot, width_in) in enumerate(fit["slots"]):
                product = self._resolve_slot(slot, width_in)
                is_unresolved = not product
                if is_unresolved:
                    product = unresolved_tmpl.product_variant_id
                tmpl = product.product_tmpl_id
                Line.create({
                    "design_id": design.id,
                    "sequence": (idx + 1) * 10,
                    "product_id": product.id,
                    "quantity": 1,
                    "price_unit": 0.0 if is_unresolved else (
                        product.lst_price or tmpl.list_price or 0.0),
                    "cabinet_type": slot.cabinet_type,
                    "zone": _ZONE_FROM_CABINET_TYPE.get(
                        slot.cabinet_type, "other"),
                    "width_in": width_in,
                    "height_in": tmpl.southbrook_height_in or 34.5,
                    "depth_in": tmpl.southbrook_depth_in or 24.0,
                    "wall": slot.wall,
                    "run_seq": slot.run_seq,
                    "origin": "configurator",
                    "layout_role": "canonical",
                    "layout_key": "tpl-%s-%s-%d" % (
                        self.code, slot.slot_code, idx),
                    "template_slot_code": slot.slot_code,
                    "appliance_type": slot.appliance_type or False,
                    "is_unresolved": is_unresolved,
                })
            corner_slots = self.line_ids.filtered(
                lambda s: s.cabinet_type == "corner")
            try:
                design.action_auto_arrange(sync=True)
            except kitchen_layout_engine.LayoutCapacityExceeded as e:
                raise UserError(
                    "This template does not fit a %g\" x %g\" room with the "
                    "chosen count/widths (%s). Reduce the cabinet count or "
                    "module width — the room is never grown automatically."
                    % (design.room_width_in, design.room_depth_in, e)) from e
            design.state = "configured"
            design.message_post(body=(
                "Instantiated from template %s (%s): %d slot(s), %d "
                "unresolved%s." % (
                    self.name, self.code, len(fit["slots"]),
                    len(design.cabinet_line_ids.filtered("is_unresolved")),
                    "; corner preference expressed by %d template slot(s) — "
                    "corner geometry is engine-derived" % len(corner_slots)
                    if corner_slots else "")))
        return design
