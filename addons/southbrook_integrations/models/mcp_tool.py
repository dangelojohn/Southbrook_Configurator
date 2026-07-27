# SPDX-License-Identifier: LGPL-3.0-only
"""MCP server tool registry - scaffolding for the Qwen-into-Odoo bridge.

This is the SECOND tool registry in the codebase. The existing
``southbrook_hermes.tools.decorator`` (process-level Python list, written by
``@hermes_tool`` decorators at import time) serves the trade-partner sidecar
on the EDGE - it's bound to short-lived JWTs and persona/tier ACL written
in Python. THIS registry is data-driven (rows in ``ir.model``), enabled at
runtime by a manager, and read-only by design. The two coexist:

- Hermes  - PERSONA-bound (trade_partner / sales_rep / mfg_manager),
            JWT-claim-bound args, T0/T1/T2 write tools, sidecar-facing.
- MCP     - MODEL-bound (one row per ``model_id`` + ``domain_json``),
            X-Api-Key-bound, READ ONLY in v1, MCP-server-facing for
            self-hosted Qwen (the future VPS target per PRD Q-4).

Deliberate design deviation from the brief: instead of a free-form
``read_fields_json`` we still serialise a list of field names but we
hard-validate them against ``ir.model.fields`` at invoke time so a typo'd
field name returns a 400 rather than crashing the ``read()`` call. This
mirrors the Hermes ``read_tools`` pattern of "only return whitelisted
columns" without depending on Hermes itself (this addon must work in
deployments where Hermes is not installed).
"""
import json
import logging
import time

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


class SouthbrookIntegrationsMcpTool(models.Model):
    _name = "southbrook.integrations.mcp_tool"
    _description = "MCP Server Tool (read-only scoped query)"
    _order = "category, name"

    name = fields.Char(required=True, index=True)
    description = fields.Text()
    category = fields.Selection(
        [
            ("read", "Read"),
            ("search", "Search"),
            ("write", "Write"),
        ],
        default="read",
        required=True,
        help="v1 only ships read/search. write is reserved for v2 when the "
             "ACL story is decided.",
    )
    model_id = fields.Many2one(
        "ir.model",
        required=True,
        ondelete="cascade",
        help="Target Odoo model the tool reads from.",
    )
    model_name = fields.Char(
        related="model_id.model", store=True, readonly=True, string="Model",
    )
    domain_json = fields.Text(
        default="[]",
        help="JSON-serialised Odoo domain applied on top of every search.",
    )
    read_fields_json = fields.Text(
        default="[]",
        help="JSON-serialised list of field names returned in the result.",
    )
    enabled = fields.Boolean(default=True)
    rate_limit_per_min = fields.Integer(default=60)

    _name_uniq = models.Constraint(
        'UNIQUE(name)',
        "Tool name must be unique within the MCP registry.",
    )

    # Models a tool may NEVER target — reading these over the MCP bridge would
    # expose signing secrets / credential hashes / the user table regardless of
    # who holds the key. Defense-in-depth on top of the (now non-sudo) ACL read.
    _BLOCKED_MODELS = (
        "ir.config_parameter",
        "ir.mail_server",
        "res.users",
        "res.users.apikeys",
        "southbrook.api.key",
        "ir.model.data",
    )

    @api.constrains("model_id")
    def _check_model_not_blocked(self):
        for tool in self:
            if tool.model_name in self._BLOCKED_MODELS:
                raise UserError(_(
                    "Model '%s' cannot be exposed as an MCP tool (it carries "
                    "secrets or credentials).") % tool.model_name)

    # ------------------------------------------------------------------
    # Invocation
    # ------------------------------------------------------------------
    def invoke(self, args_json):
        """Execute a sandboxed read against ``model_id`` + ``domain_json`` +
        ``read_fields_json``. Returns the result dict; persists a row in
        ``mcp_call_log``.

        Args (``args_json``):
            ``{"limit": 50, "offset": 0}`` — both optional and clamped. A
            wire-supplied domain is deliberately NOT accepted (see below); the
            tool's own ``domain_json`` is the only scope.

        Raises:
            ``UserError`` if disabled, model missing, domain/fields invalid.
            ``AccessError`` if a write category is invoked (write is v2).
        """
        self.ensure_one()
        Log = self.env["southbrook.integrations.mcp_call_log"].sudo()
        started = time.time()
        status = "ok"
        result_size = 0
        try:
            if not self.enabled:
                status = "rate_limited"  # treated as 403 by caller
                Log.create({
                    "tool_id": self.id,
                    "user_id": self.env.uid,
                    "args_json": args_json or "{}",
                    "result_size": 0,
                    "latency_ms": 0,
                    "status": "error",
                })
                raise AccessError(_("Tool '%s' is disabled.") % self.name)
            if self.category == "write":
                raise AccessError(
                    _("Write-category MCP tools are not enabled in v1."))
            args = {}
            if args_json:
                try:
                    args = json.loads(args_json)
                except json.JSONDecodeError as exc:
                    raise UserError(_("Invalid args JSON: %s") % exc) from exc
            domain = self._parse_domain()
            # SECURITY: a caller-supplied `extra_domain` was concatenated onto
            # the curated domain and run under sudo — a boolean-oracle to
            # exfiltrate non-whitelisted fields and reshape query semantics.
            # The tool's own domain_json is the ONLY scope; wire-supplied
            # domains are not accepted.
            field_names = self._parse_fields()
            self._validate_read_fields_exist(field_names)
            # Clamp paging so a single call can't demand an unbounded read.
            limit = max(1, min(int(args.get("limit", 50)), 500))
            offset = max(0, int(args.get("offset", 0)))
            # NO sudo: the read runs as the invoking principal so record rules,
            # model ACL and company scoping apply. Reading under sudo turned the
            # endpoint into "read anything a curated tool names" regardless of
            # the caller's rights (portal user → all payroll wages; a manager →
            # ir.config_parameter secrets).
            Target = self.env[self.model_name]
            records = Target.search(domain, limit=limit, offset=offset)
            rows = records.read(field_names) if field_names \
                else records.read()
            result_size = len(rows)
            latency_ms = int((time.time() - started) * 1000)
            Log.create({
                "tool_id": self.id,
                "user_id": self.env.uid,
                "args_json": args_json or "{}",
                "result_size": result_size,
                "latency_ms": latency_ms,
                "status": "ok",
            })
            return {
                "schema": "southbrook.mcp.invoke.v1",
                "tool": self.name,
                "model": self.model_name,
                "rows": rows,
                "count": result_size,
            }
        except AccessError:
            raise
        except Exception:
            latency_ms = int((time.time() - started) * 1000)
            Log.create({
                "tool_id": self.id,
                "user_id": self.env.uid,
                "args_json": args_json or "{}",
                "result_size": result_size,
                "latency_ms": latency_ms,
                "status": "error",
            })
            raise

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _parse_domain(self):
        self.ensure_one()
        raw = self.domain_json or "[]"
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise UserError(
                _("Invalid domain JSON on tool %s: %s") % (self.name, exc)
            ) from exc
        if not isinstance(parsed, list):
            raise UserError(_("Domain must be a list."))
        # JSON has no tuples; Odoo domains accept both lists and tuples.
        return [tuple(c) if isinstance(c, list) and len(c) == 3 else c
                for c in parsed]

    def _parse_fields(self):
        self.ensure_one()
        raw = self.read_fields_json or "[]"
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise UserError(
                _("Invalid fields JSON on tool %s: %s") % (self.name, exc)
            ) from exc
        if not isinstance(parsed, list):
            raise UserError(_("Fields must be a list."))
        return parsed

    def _validate_read_fields_exist(self, field_names):
        self.ensure_one()
        if not field_names:
            return
        Target = self.env[self.model_name]
        unknown = [f for f in field_names if f not in Target._fields]
        if unknown:
            raise UserError(
                _("Unknown fields on %(m)s: %(u)s") % {
                    "m": self.model_name,
                    "u": ", ".join(unknown),
                })

    def action_test_invoke(self):
        """Backend convenience: run the tool with empty args and stash the
        result in a transient sticky notification."""
        self.ensure_one()
        try:
            result = self.invoke("{}")
        except (UserError, AccessError) as exc:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Invoke failed"),
                    "message": str(exc),
                    "type": "danger",
                    "sticky": True,
                },
            }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Invoke OK"),
                "message": _("%s rows returned.") % result["count"],
                "type": "success",
                "sticky": False,
            },
        }
