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
            "columns": [],
            "rows": [],
            "detail": {},
            "total": 0,
            "provenance": PROVENANCE,
        }

    @api.model
    def _categories(self):
        """Rail tree with descendant-inclusive product counts.

        Counts are computed with ONE read_group over product.template rather
        than a query per category — 101 categories would otherwise mean 101
        queries on every catalog load.
        """
        Category = self.env["southbrook.tool.category"]
        cats = Category.search([])
        if not cats:
            return []

        # Odoo 17+ grouping API: _read_group returns a list of tuples,
        # (group_value, *aggregates). The old public read_group is gone.
        grouped = self.env["product.template"]._read_group(
            [("x_southbrook_tool_category_id", "in", cats.ids)],
            groupby=["x_southbrook_tool_category_id"],
            aggregates=["__count"],
        )
        direct = {cat.id: count for cat, count in grouped if cat}

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
