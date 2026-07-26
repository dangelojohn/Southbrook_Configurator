# SPDX-License-Identifier: LGPL-3.0-only
"""Phase 1 provider: southbrook_mrp_kitchen_tools data.

This is the ONLY file that knows about x_southbrook_* fields or
southbrook.tool.category. Phase 2's hardware provider is a sibling file.
"""
from odoo import api, models

PROVENANCE = (
    "Read-only view of the tool and consumable master. Specs are optional — "
    "an absent value is shown as a dash, never as zero."
)

GENERIC_COLUMNS = [
    {"key": "name", "label": "Description", "align": "left", "sortable": True},
    {"key": "default_code", "label": "Reference", "align": "left",
     "sortable": True},
]


class ToolsCatalogProvider(models.AbstractModel):
    _name = "tools.catalog.provider"
    _inherit = "materials.catalog.provider"
    _description = "Tools and consumables catalog provider"

    @api.model
    def _build_payload(self, scope, category_id, facets, search, offset, limit):
        category = self.env["southbrook.tool.category"].browse(
            category_id) if category_id else None
        if category is not None and not category.exists():
            return self._degrade("Unknown category: %s" % category_id, scope)
        return {
            "ok": True,
            "reason": None,
            "scope": scope,
            "categories": self._categories(),
            "facets": [],
            "columns": self._columns(category),
            "rows": [],
            "detail": {},
            "total": 0,
            "provenance": PROVENANCE,
        }

    @api.model
    def _categories(self):
        """Rail tree with descendant-inclusive product counts.

        Counts are computed with TWO efficient queries:
        - one _read_group over product.product grouped by product_tmpl_id
        - one batched read of templates to map category, joined in Python
        This counts variants (not templates) so the rail matches table rows,
        and stays O(1) queries instead of O(categories).
        """
        Category = self.env["southbrook.tool.category"]
        cats = Category.search([])
        if not cats:
            return []

        # Odoo 17+ grouping API: _read_group returns a list of tuples,
        # (group_value, *aggregates). The old public read_group is gone.
        # Count product.product (variants) grouped by template.
        variant_grouped = self.env["product.product"]._read_group(
            [("product_tmpl_id.x_southbrook_tool_category_id", "in", cats.ids)],
            groupby=["product_tmpl_id"],
            aggregates=["__count"],
        )
        # variant_grouped is list of (product.template, count) tuples.
        # Map each template to its variant count.
        tmpl_to_variant_count = {tmpl.id: count for tmpl, count in variant_grouped if tmpl}

        # Batch-read all templates once and map variant counts to categories.
        tmpl_ids = list(tmpl_to_variant_count.keys())
        templates = self.env["product.template"].browse(tmpl_ids) if tmpl_ids else []
        direct = {}
        for tmpl in templates:
            cat_id = tmpl.x_southbrook_tool_category_id.id if tmpl.x_southbrook_tool_category_id else None
            if cat_id:
                direct[cat_id] = direct.get(cat_id, 0) + tmpl_to_variant_count[tmpl.id]

        # Roll direct counts up through parent_path, so an ancestor reports
        # everything beneath it.
        rollup = dict.fromkeys(cats.ids, 0)
        for cat in cats:
            n = direct.get(cat.id, 0)
            if not n:
                continue
            for raw in (cat.parent_path or "").strip("/").split("/"):
                if raw and int(raw) in rollup:
                    rollup[int(raw)] += n

        child_ids = {c.parent_id.id for c in cats if c.parent_id}
        return [{
            "id": c.id,
            "name": c.name,
            "parent_id": c.parent_id.id or False,
            "count": rollup.get(c.id, 0),
            "has_children": c.id in child_ids,
        } for c in cats.sorted(lambda r: (r.complete_name or ""))]

    @api.model
    def _ancestor_ids(self, category):
        """Category's own id plus every ancestor id, nearest LAST.

        parent_path is '/1/7/33/' — root first, self last.
        """
        if not category:
            return []
        return [int(x) for x in (category.parent_path or "").strip("/").split("/") if x]

    @api.model
    def _columns(self, category):
        """Columns for the category, generics first, then declared ones.

        Declarations from the selected category and all its ancestors apply.
        When the same field_name is declared at two levels, the nearest
        declaration wins — a child's label overrides its ancestor's.
        """
        cols = list(GENERIC_COLUMNS)
        if not category:
            return cols
        ids = self._ancestor_ids(category)
        if not ids:
            return cols
        declared = self.env["materials.catalog.column"].search(
            [("category_id", "in", ids)])
        # Nearest declaration wins: order by depth of its category in `ids`.
        depth = {cat_id: i for i, cat_id in enumerate(ids)}
        by_field = {}
        for dec in declared.sorted(
                lambda d: (depth.get(d.category_id.id, -1), d.sequence, d.id)):
            by_field[dec.field_name] = {
                "key": dec.field_name,
                "label": dec.name,
                "align": dec.align,
                "sortable": dec.sortable,
            }
        return cols + list(by_field.values())
