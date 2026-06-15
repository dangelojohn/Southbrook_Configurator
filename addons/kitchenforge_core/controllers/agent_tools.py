# SPDX-License-Identifier: LGPL-3.0-only
"""KitchenForge Agent Tools — typed action endpoints.

Filesystem reads/writes are for navigation + property edits. Workflow actions
(instantiate a template, confirm a quote, release MOs, raise an ECO) go
through these endpoints so the LLM agent can frame them as `tool_use` calls
with strict JSON Schemas.

Each tool:
- requires X-Api-Key
- is idempotent under an Idempotency-Key header
- returns a result + the path to the affected fs object
"""
import json
import logging

from odoo import _, http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from odoo.addons.southbrook_api.controllers.main import (
    requires_api_key, supports_idempotency, _json, _error,
)

from . import _fs

_logger = logging.getLogger(__name__)


def _body() -> dict:
    raw = request.httprequest.get_data(as_text=True)
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise UserError(f"invalid JSON body: {exc}") from exc


class KitchenForgeAgentTools(http.Controller):

    @http.route("/agent/v1/tools", type="http", auth="public",
                methods=["GET"], csrf=False)
    @requires_api_key
    def list_tools(self, **_kw):
        """Return the JSON-Schema'd tool catalog for LLM tool_use."""
        return _json({
            "schema": "kitchenforge.agent.tools.v1",
            "tools": TOOL_CATALOG,
        })

    @http.route("/agent/v1/tools/instantiate", type="http", auth="public",
                methods=["POST"], csrf=False)
    @requires_api_key
    @supports_idempotency
    def tool_instantiate(self, **_kw):
        try:
            body = _body()
            tmpl = request.env["project.project"].browse(int(body["template_id"]))
            partner = request.env["res.partner"].browse(int(body["partner_id"]))
            if not tmpl.exists() or not tmpl.is_template:
                return _error("invalid_template", "template_id not found or not a template", 400)
            if not partner.exists():
                return _error("invalid_partner", "partner_id not found", 400)
            proj = tmpl.kitchenforge_instantiate(
                partner=partner,
                dims=body.get("dims") or {},
                target_date=body.get("target_date"),
                origin_channel="agent-api",
            )
            return _json({
                "ok": True,
                "project_id": proj.id,
                "project_path": f"/projects/{proj.id}.yaml",
                "sale_order_id": proj.sale_order_id.id,
                "sale_order_name": proj.sale_order_id.name,
                "quote_path": f"/projects/{proj.id}/quote.yaml",
            })
        except (UserError, ValidationError, AccessError) as exc:
            return _error("tool_failed", str(exc), 400)
        except Exception as exc:
            _logger.exception("instantiate failed")
            return _error("tool_failed", str(exc), 500)

    @http.route("/agent/v1/tools/add_zone", type="http", auth="public",
                methods=["POST"], csrf=False)
    @requires_api_key
    @supports_idempotency
    def tool_add_zone(self, **_kw):
        try:
            body = _body()
            proj = request.env["project.project"].browse(int(body["project_id"]))
            so = proj.sale_order_id
            if not so:
                return _error("no_quote", "project has no sale order", 400)
            zone = body["zone"]
            so.write({"order_line": [(0, 0, {
                "product_id": zone["product_id"],
                "product_uom_qty": zone.get("quantity", 1.0),
                "kitchenforge_zone_width_mm": zone.get("width_mm", 600),
                "kitchenforge_zone_height_mm": zone.get("height_mm", 720),
                "kitchenforge_zone_depth_mm": zone.get("depth_mm", 580),
                "kitchenforge_preselected_attrs_json": json.dumps(
                    zone.get("preselected_attribute_values") or {}),
            })]})
            return _json({
                "ok": True,
                "project_id": proj.id,
                "zones_path": f"/projects/{proj.id}/zones",
                "line_count": len(so.order_line),
            })
        except (UserError, ValidationError, AccessError) as exc:
            return _error("tool_failed", str(exc), 400)
        except Exception as exc:
            _logger.exception("add_zone failed")
            return _error("tool_failed", str(exc), 500)

    @http.route("/agent/v1/tools/confirm_quote", type="http", auth="public",
                methods=["POST"], csrf=False)
    @requires_api_key
    @supports_idempotency
    def tool_confirm_quote(self, **_kw):
        try:
            body = _body()
            proj = request.env["project.project"].browse(int(body["project_id"]))
            so = proj.sale_order_id
            if not so:
                return _error("no_quote", "project has no sale order", 400)
            if so.state == "sale":
                return _json({"ok": True, "already_confirmed": True,
                              "sale_order": so.name})
            so.action_confirm()
            return _json({
                "ok": True,
                "sale_order": so.name,
                "state": so.state,
                "mo_path": f"/projects/{proj.id}/mo",
            })
        except (UserError, ValidationError, AccessError) as exc:
            return _error("tool_failed", str(exc), 400)
        except Exception as exc:
            _logger.exception("confirm_quote failed")
            return _error("tool_failed", str(exc), 500)

    @http.route("/agent/v1/tools/release_mos", type="http", auth="public",
                methods=["POST"], csrf=False)
    @requires_api_key
    @supports_idempotency
    def tool_release_mos(self, **_kw):
        try:
            body = _body()
            proj = request.env["project.project"].browse(int(body["project_id"]))
            so = proj.sale_order_id
            if not so:
                return _error("no_quote", "project has no sale order", 400)
            MO = request.env["mrp.production"]
            mos = MO.search([
                ("sale_line_id.order_id", "=", so.id),
                ("state", "in", ["draft", "confirmed"]),
            ])
            released = []
            for mo in mos:
                if mo.state == "draft":
                    mo.action_confirm()
                if hasattr(mo, "action_assign"):
                    mo.action_assign()
                released.append({"id": mo.id, "name": mo.name, "state": mo.state})
            return _json({
                "ok": True,
                "released_count": len(released),
                "mos": released,
            })
        except (UserError, ValidationError, AccessError) as exc:
            return _error("tool_failed", str(exc), 400)
        except Exception as exc:
            _logger.exception("release_mos failed")
            return _error("tool_failed", str(exc), 500)

    @http.route("/agent/v1/tools/raise_eco", type="http", auth="public",
                methods=["POST"], csrf=False)
    @requires_api_key
    @supports_idempotency
    def tool_raise_eco(self, **_kw):
        """Author a draft ECO. Advancing it past Under Review still requires
        the southbrook_plm Approver group — Sternberg's hand-off contract."""
        try:
            body = _body()
            ECO = request.env.get("southbrook.eco")
            if ECO is None:
                return _error("plm_not_installed",
                              "southbrook_plm not available", 501)
            vals = {
                "name": body.get("title") or "Agent-authored ECO",
                "description": body.get("reason") or "",
            }
            if "target_bom_id" in body:
                vals["bom_id"] = body["target_bom_id"]
                vals["target_kind"] = "bom"
            eco = ECO.create(vals)
            return _json({
                "ok": True,
                "eco_id": eco.id,
                "stage": eco.stage_id.name if eco.stage_id else None,
                "requires_approver": True,
            })
        except (UserError, ValidationError, AccessError) as exc:
            return _error("tool_failed", str(exc), 400)
        except Exception as exc:
            _logger.exception("raise_eco failed")
            return _error("tool_failed", str(exc), 500)


# ----------------------------------------------------------------------
# Tool catalog (LLM-consumable JSON Schemas — feed straight into Claude/GPT)
# ----------------------------------------------------------------------
TOOL_CATALOG = [
    {
        "name": "instantiate",
        "description": "Create a new kitchen Project from a template. Auto-generates a "
                       "draft Sale Order with cabinet zones pre-populated from the template.",
        "input_schema": {
            "type": "object",
            "required": ["template_id", "partner_id"],
            "properties": {
                "template_id": {"type": "integer",
                                "description": "project.project id where is_template=True"},
                "partner_id": {"type": "integer",
                               "description": "res.partner id of the end customer"},
                "dims": {
                    "type": "object",
                    "properties": {
                        "room_width_mm": {"type": "integer"},
                        "room_depth_mm": {"type": "integer"},
                        "ceiling_height_mm": {"type": "integer"},
                    },
                },
                "target_date": {"type": "string",
                                "description": "ISO date for handover"},
            },
        },
        "endpoint": "POST /agent/v1/tools/instantiate",
    },
    {
        "name": "add_zone",
        "description": "Add a cabinet zone (sale.order.line) to an in-flight project quote.",
        "input_schema": {
            "type": "object",
            "required": ["project_id", "zone"],
            "properties": {
                "project_id": {"type": "integer"},
                "zone": {
                    "type": "object",
                    "required": ["product_id"],
                    "properties": {
                        "product_id": {"type": "integer"},
                        "quantity": {"type": "number"},
                        "width_mm": {"type": "integer"},
                        "height_mm": {"type": "integer"},
                        "depth_mm": {"type": "integer"},
                        "preselected_attribute_values": {"type": "object"},
                    },
                },
            },
        },
        "endpoint": "POST /agent/v1/tools/add_zone",
    },
    {
        "name": "confirm_quote",
        "description": "Confirm the project's sale order. Procurement will spawn "
                       "Manufacturing Orders via the auto-applied manufacture route.",
        "input_schema": {
            "type": "object",
            "required": ["project_id"],
            "properties": {"project_id": {"type": "integer"}},
        },
        "endpoint": "POST /agent/v1/tools/confirm_quote",
    },
    {
        "name": "release_mos",
        "description": "Move all confirmed MOs on the project from confirmed to "
                       "assigned (component reservation + ready-to-build).",
        "input_schema": {
            "type": "object",
            "required": ["project_id"],
            "properties": {"project_id": {"type": "integer"}},
        },
        "endpoint": "POST /agent/v1/tools/release_mos",
    },
    {
        "name": "raise_eco",
        "description": "Author a draft Engineering Change Order against a template BoM. "
                       "Advancing past Under Review requires the southbrook_plm Approver group.",
        "input_schema": {
            "type": "object",
            "required": ["title"],
            "properties": {
                "title": {"type": "string"},
                "reason": {"type": "string"},
                "project_id": {"type": "integer"},
                "target_bom_id": {"type": "integer"},
            },
        },
        "endpoint": "POST /agent/v1/tools/raise_eco",
    },
]
