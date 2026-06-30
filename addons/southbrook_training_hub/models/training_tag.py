# SPDX-License-Identifier: LGPL-3.0-only
"""Typed tags for training items.

Four kinds (selection field, not subclasses, because Odoo selection
filtering beats polymorphism for the search box and the kanban filters):

- ``role`` — sales rep, planner, designer, operator, …
- ``module`` — southbrook_quality, southbrook_estimating, …
- ``jtbd`` — verb-phrase, e.g. "create a kitchen quote", "open an NCR".
- ``department`` — sales, production, quality, finance, …
- ``course`` — auto-created from the seeded ``slide.channel`` titles.

The ``jtbd`` kind is the differentiator vs Odoo's stock tag model:
JTBD tags are how users find content in the moment ("I want to ___").
"""
from odoo import api, fields, models


KIND_SELECTION = [
    ("role", "Role"),
    ("module", "Module"),
    ("jtbd", "Job To Be Done"),
    ("department", "Department"),
    ("course", "Course"),
]


class SouthbrookTrainingTag(models.Model):
    _name = "southbrook.training.tag"
    _description = "Southbrook Training Tag"
    _order = "kind, sequence, name"

    name = fields.Char(required=True, index=True)
    kind = fields.Selection(KIND_SELECTION, required=True, default="role")
    sequence = fields.Integer(default=10)
    description = fields.Text()
    color = fields.Integer(default=0)
    item_ids = fields.Many2many(
        "southbrook.training.item",
        "southbrook_training_item_tag_rel",
        "tag_id",
        "item_id",
        string="Items",
    )
    item_count = fields.Integer(
        compute="_compute_item_count", store=False)

    _name_kind_uniq = models.Constraint(
        'UNIQUE(name, kind)',
        "Tag name must be unique within its kind.",
    )

    @api.depends("item_ids")
    def _compute_item_count(self):
        for tag in self:
            tag.item_count = len(tag.item_ids)

    def name_get(self):
        result = []
        for tag in self:
            kind_label = dict(KIND_SELECTION).get(tag.kind, tag.kind)
            result.append((tag.id, f"[{kind_label}] {tag.name}"))
        return result
