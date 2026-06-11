# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.tool.crib — physical / organisational tool storage location.

Each work center typically has a small tool cabinet on the floor plus
a shared central tool crib for blades / bits / measuring instruments.
This model groups the per-work-center cabinets so the readiness check
in commit 4 can answer "which crib has this asset" without scanning
every stock location.

A crib MAY back onto a real ``stock.location`` for items the crib
manager wants to track in stock; if no location is set the crib is
"by hand" — assets just record their crib_id and condition.
"""
from odoo import _, api, fields, models


class SouthbrookToolCrib(models.Model):
    _name = "southbrook.tool.crib"
    _description = "Southbrook Tool Crib"
    _order = "code, name"
    _rec_name = "display_name"

    name = fields.Char(string="Name", required=True, translate=True)
    code = fields.Char(string="Code", required=True, index=True)
    display_name = fields.Char(
        compute="_compute_display_name", store=True,
    )
    active = fields.Boolean(default=True)
    notes = fields.Text()

    stock_location_id = fields.Many2one(
        "stock.location",
        string="Stock Location",
        domain="[('usage', '=', 'internal')]",
        help="Optional — when set, tool consumption against this crib "
             "writes proper stock moves. When blank, the crib is "
             "by-hand: only the asset's crib_id pointer changes.",
    )
    responsible_id = fields.Many2one(
        "res.users", string="Responsible",
        help="Crib manager — owns audit, replenishment, lifecycle.",
    )
    workcenter_ids = fields.Many2many(
        "mrp.workcenter",
        "southbrook_tool_crib_wc_rel",
        "crib_id", "workcenter_id",
        string="Serves Work Centers",
    )

    # Inverse counts ──────────────────────────────────────────────────
    asset_count = fields.Integer(
        compute="_compute_asset_count", string="Tool Assets",
    )

    _sql_code_unique = models.Constraint(
        "UNIQUE(code)",
        "Tool crib code must be unique.",
    )

    @api.depends("name", "code")
    def _compute_display_name(self):
        for rec in self:
            if rec.code and rec.name:
                rec.display_name = f"[{rec.code}] {rec.name}"
            else:
                rec.display_name = rec.name or rec.code or ""

    def _compute_asset_count(self):
        Asset = self.env["southbrook.tool.asset"]
        for rec in self:
            rec.asset_count = Asset.search_count(
                [("tool_crib_id", "=", rec.id)],
            )

    # ──────────────────────────────────────────────────────────────────
    # Action — view assets in this crib
    # ──────────────────────────────────────────────────────────────────
    def action_view_assets(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Assets in %s") % self.display_name,
            "res_model": "southbrook.tool.asset",
            "view_mode": "kanban,list,form",
            "domain": [("tool_crib_id", "=", self.id)],
            "context": {"default_tool_crib_id": self.id},
        }
