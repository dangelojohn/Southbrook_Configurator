# SPDX-License-Identifier: LGPL-3.0-only
"""sb.placement.rule — data-driven rule storage for the engine.

Per G4 §7 every preference and constraint lives as a record so rules
are auditable + rev-able without a code change. The engine reads all
active rules at the start of each placement run, indexed by
(kind, theme, appliance_kind) for fast lookup."""
import json

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


RULE_KINDS = [
    ("clearance", "Appliance Clearance (C1)"),
    ("width_pref", "Theme Width Preference (C4)"),
    ("corner_pref", "Theme Corner Preference (C4)"),
    ("filler_rule", "Filler Distribution Rule"),
]

# Aligns with sb.kitchen.project.theme choices.
THEME_CHOICES = [
    ("signature", "Signature"),
    ("elegance", "Elegance"),
    ("contemporary", "Contemporary"),
    ("contractor", "Contractor"),
]

APPLIANCE_KINDS = [
    ("stove", "Stove / Range"),
    ("fridge", "Refrigerator"),
    ("dishwasher", "Dishwasher"),
    ("sink", "Sink"),
    ("microwave", "Microwave"),
    ("oven_wall", "Wall Oven"),
    ("hood", "Range Hood"),
    ("other", "Other"),
]


class SbPlacementRule(models.Model):
    _name = "sb.placement.rule"
    _description = "Southbrook Placement Rule"
    _order = "kind, priority, id"

    name = fields.Char(required=True)
    kind = fields.Selection(RULE_KINDS, required=True, index=True)
    theme = fields.Selection(THEME_CHOICES, index=True,
                              help="Restrict rule to one theme (blank = all themes).")
    appliance_kind = fields.Selection(APPLIANCE_KINDS, index=True,
                                       help="Restrict to one appliance (blank = all).")
    constraint_json = fields.Text(
        required=True,
        help="Type-specific payload. clearance: {left_mm, right_mm}. "
             "width_pref: {preferred_widths_mm: [int, ...]}. "
             "corner_pref: {first_choice, fallback}.",
    )
    priority = fields.Integer(default=100,
                               help="Lower = applied first when multiple rules match.")
    active = fields.Boolean(default=True)
    note = fields.Text()

    @api.constrains("constraint_json", "kind")
    def _check_constraint_json(self):
        for rule in self:
            try:
                payload = json.loads(rule.constraint_json or "{}")
            except json.JSONDecodeError as exc:
                raise ValidationError(_(
                    "constraint_json must be valid JSON: %s"
                ) % exc)
            if not isinstance(payload, dict):
                raise ValidationError(_(
                    "constraint_json must decode to a JSON object."
                ))
            # Per-kind semantic validation — a syntactically-valid but
            # semantically-bad rule (0/negative width, non-numeric clearance)
            # would otherwise be accepted here and only detonate later inside an
            # engine run as an unhandled 500 / infinite recursion, not a clean
            # UserError at save time. (bool is an int subclass → exclude it.)
            def _pos_num(v):
                return (isinstance(v, (int, float)) and not isinstance(v, bool)
                        and v > 0)

            def _nonneg_num(v):
                return (isinstance(v, (int, float)) and not isinstance(v, bool)
                        and v >= 0)

            if rule.kind == "width_pref":
                widths = payload.get("preferred_widths_mm")
                if widths is not None and (
                        not isinstance(widths, list)
                        or not all(_pos_num(w) for w in widths)):
                    raise ValidationError(_(
                        "width_pref preferred_widths_mm must be a list of "
                        "positive numbers."))
            elif rule.kind == "clearance":
                for k in ("left_mm", "right_mm"):
                    v = payload.get(k)
                    if v is not None and not _nonneg_num(v):
                        raise ValidationError(_(
                            "clearance %s must be a non-negative number.") % k)

    def to_dict(self) -> dict:
        self.ensure_one()
        return json.loads(self.constraint_json or "{}")
