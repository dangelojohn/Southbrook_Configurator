# SPDX-License-Identifier: LGPL-3.0-only
"""Audit log for MCP tool invocations.

One row per invoke, regardless of outcome. Latency + status here lets the
Integrations Snapshot MI tile compute rate-limited / error counts without
walking server logs.
"""
from odoo import fields, models


class SouthbrookIntegrationsMcpCallLog(models.Model):
    _name = "southbrook.integrations.mcp_call_log"
    _description = "MCP Tool Call Log"
    _order = "create_date desc, id desc"

    tool_id = fields.Many2one(
        "southbrook.integrations.mcp_tool",
        ondelete="set null",
        index=True,
    )
    caller_persona = fields.Char(
        index=True,
        help="Persona / source of the call (`mcp_server`, `odoo_user`, etc).",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Invoked By",
        index=True,
        ondelete="set null",
        help="The authenticated principal that ran the tool — required to "
             "attribute a call to a key/user during a forensic review.",
    )
    args_json = fields.Text()
    result_size = fields.Integer()
    latency_ms = fields.Integer()
    status = fields.Selection(
        [
            ("ok", "OK"),
            ("error", "Error"),
            ("rate_limited", "Rate Limited"),
        ],
        default="ok",
        index=True,
    )
