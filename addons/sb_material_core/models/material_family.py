# SPDX-License-Identifier: LGPL-3.0-only
from odoo import api, fields, models
from odoo.exceptions import ValidationError

WEIGHT_SOURCES = [
    ("density_volume", "Density × volume (sheet/solid wood)"),
    ("density_area", "Density × area × thickness (tile/drywall/stone)"),
    ("linear_density", "Linear density kg/m (edgebanding)"),
    ("per_unit", "Weight per unit (hardware)"),
    ("none", "Not tracked (bought/subcontracted)"),
]


class MaterialFamily(models.Model):
    _name = "material.family"
    _description = "Material Family"
    _parent_store = True
    _order = "complete_name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    parent_id = fields.Many2one("material.family", ondelete="cascade", index=True)
    parent_path = fields.Char(index=True, unaccent=False)
    complete_name = fields.Char(compute="_compute_complete_name", store=True, recursive=True)
    default_weight_source = fields.Selection(WEIGHT_SOURCES, default="density_volume")
    default_waste_pct = fields.Float(string="Default Waste %", default=0.0)

    _code_uniq = models.Constraint("unique(code)", "Family code must be unique.")

    @api.depends("name", "parent_id.complete_name")
    def _compute_complete_name(self):
        for fam in self:
            fam.complete_name = (
                "%s / %s" % (fam.parent_id.complete_name, fam.name)
                if fam.parent_id else fam.name
            )

    @api.constrains("parent_id")
    def _check_parent_id_recursion(self):
        if self._has_cycle():
            raise ValidationError(
                "A material family cannot be its own ancestor.")
