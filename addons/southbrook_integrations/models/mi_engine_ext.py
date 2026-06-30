# SPDX-License-Identifier: LGPL-3.0-only
"""Integrations MI tiles.

Follows the southbrook_finance_pack / southbrook_payroll_ca pattern: a
concrete (non-abstract) snapshot model the dashboard reads on render.
v19 forbids inheriting an AbstractModel parent as ``models.Model``
(odoo19_abstract_model_inherit_trap), so we declare a NEW model.
"""
from datetime import timedelta

from odoo import api, fields, models


class SouthbrookIntegrationsMiTiles(models.Model):
    _name = "southbrook.integrations.mi_tiles"
    _description = "Southbrook Integrations MI Tiles (snapshot)"
    _rec_name = "label"

    label = fields.Char(default="Integrations Snapshot", required=True)

    homag_sessions_30d = fields.Integer(
        compute="_compute_tiles", string="Homag sessions (30d)",
    )
    homag_avg_discrepancy_pct = fields.Float(
        compute="_compute_tiles",
        digits=(8, 2),
        string="Avg Homag discrepancy (%)",
    )
    asn_pending_count = fields.Integer(
        compute="_compute_tiles", string="3PL ASNs pending",
    )
    mcp_calls_24h = fields.Integer(
        compute="_compute_tiles", string="MCP calls (24h)",
    )
    label_prints_24h = fields.Integer(
        compute="_compute_tiles", string="Label prints (24h)",
    )

    @api.depends("label")
    def _compute_tiles(self):
        Homag = self.env["southbrook.integrations.homag_session"]
        Asn = self.env["southbrook.integrations.asn_3pl"]
        McpLog = self.env["southbrook.integrations.mcp_call_log"]
        LabelLog = self.env["southbrook.integrations.iot_label_log"]

        now = fields.Datetime.now()
        cutoff_30d = now - timedelta(days=30)
        cutoff_24h = now - timedelta(hours=24)

        sessions_30d = Homag.search(
            [("create_date", ">=", cutoff_30d)])
        avg_disc = 0.0
        if sessions_30d:
            avg_disc = sum(sessions_30d.mapped("discrepancy_pct")) \
                       / len(sessions_30d)

        asn_pending = Asn.search_count(
            [("state", "in", ("draft", "sent", "acked"))])
        mcp_24h = McpLog.search_count(
            [("create_date", ">=", cutoff_24h)])
        labels_24h = LabelLog.search_count(
            [("create_date", ">=", cutoff_24h)])

        for rec in self:
            rec.homag_sessions_30d = len(sessions_30d)
            rec.homag_avg_discrepancy_pct = avg_disc
            rec.asn_pending_count = asn_pending
            rec.mcp_calls_24h = mcp_24h
            rec.label_prints_24h = labels_24h
