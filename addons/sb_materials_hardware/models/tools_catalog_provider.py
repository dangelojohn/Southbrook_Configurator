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
            "categories": [],
            "facets": [],
            "columns": [],
            "rows": [],
            "detail": {},
            "total": 0,
            "provenance": PROVENANCE,
        }
