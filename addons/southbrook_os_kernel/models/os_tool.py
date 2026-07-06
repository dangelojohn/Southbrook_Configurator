# SPDX-License-Identifier: LGPL-3.0-only
"""``southbrook.os.tool`` — the OS Kernel's tool registry.

Spec: docs/OS_KERNEL_SPEC.md §6. Design invariants:

* Uniqueness on ``code`` is enforced with ``models.Constraint`` (NOT the
  legacy ``_sql_constraints``, which Odoo 19 silently ignores).
* ``manifest()`` is a pure read: it never raises and only ever reports
  active rows, ordered by code.
"""
from odoo import api, fields, models


class SouthbrookOsTool(models.Model):
    _name = "southbrook.os.tool"
    _description = "Southbrook OS Kernel — Tool Registry"
    _order = "code"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    http_method = fields.Selection(
        [("GET", "GET"), ("POST", "POST")],
        default="GET",
        required=True,
    )
    path = fields.Char(required=True)
    module_name = fields.Char()
    auth = fields.Selection(
        [
            ("public", "Public"),
            ("api_key", "API key"),
            ("session", "Session"),
        ],
        default="session",
        required=True,
    )
    description = fields.Text()
    active = fields.Boolean(default=True)

    _unique_code = models.Constraint(
        "unique(code)",
        "Tool code must be unique.",
    )

    @api.model
    def manifest(self):
        """List active tools as plain dicts, ordered by code.

        Runs via sudo() (mirroring os_switch.is_on): the manifest must be
        readable by any calling feature regardless of the caller's groups —
        ACLs on this model gate direct UI access, not the API.
        """
        tools = self.sudo().search([("active", "=", True)], order="code")
        return [
            {
                "code": tool.code,
                "method": tool.http_method,
                "path": tool.path,
                "auth": tool.auth,
                "description": tool.description or "",
            }
            for tool in tools
        ]
