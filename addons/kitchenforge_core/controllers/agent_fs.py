# SPDX-License-Identifier: LGPL-3.0-only
"""KitchenForge Agent Filesystem HTTP controller.

Routes:
    GET  /agent/v1/files/*path     -> resolve(path)  -> dir listing or file payload
    PUT  /agent/v1/files/*path     -> write(path, body, If-Match)
    HEAD /agent/v1/files/*path     -> 200 + ETag header only

Auth: reuses the southbrook_api `X-Api-Key` header + idempotency framework.
"""
import json
import logging

from odoo import http
from odoo.http import request

from odoo.addons.southbrook_api.controllers.main import (
    requires_api_key, supports_idempotency, _json, _error, SCHEMA_VERSION,
)

from . import _fs

_logger = logging.getLogger(__name__)


class KitchenForgeAgentFS(http.Controller):

    @http.route(
        ["/agent/v1/files", "/agent/v1/files/<path:path>"],
        type="http", auth="public", methods=["GET"], csrf=False)
    @requires_api_key
    def files_get(self, path="", **_kw):
        try:
            result = _fs.resolve(request.env, "/" + path if path else "/")
        except _fs.NotFound as exc:
            return _error("not_found", str(exc), 404)
        except Exception as exc:
            _logger.exception("agent fs read failed: %s", path)
            return _error("agent_fs_error", str(exc), 500)
        headers = {}
        if result.get("kind") == "file" and result.get("etag"):
            headers["ETag"] = result["etag"]
        body = json.dumps(result)
        return request.make_response(
            body, status=200,
            headers=[("Content-Type", "application/json"),
                     *headers.items()])

    @http.route(
        ["/agent/v1/files/<path:path>"],
        type="http", auth="public", methods=["PUT"], csrf=False)
    @requires_api_key
    @supports_idempotency
    def files_put(self, path, **_kw):
        try:
            raw = request.httprequest.get_data(as_text=True)
            content = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            return _error("invalid_json", str(exc), 400)
        if_match = request.httprequest.headers.get("If-Match")
        try:
            result = _fs.write(request.env, "/" + path, content, if_match)
        except _fs.ReadOnly as exc:
            return _error("read_only", str(exc), 405)
        except _fs.NotFound as exc:
            return _error("not_found", str(exc), 404)
        except Exception as exc:
            _logger.exception("agent fs write failed: %s", path)
            return _error("agent_fs_error", str(exc), 500)
        return _json(result, status=200)

    @http.route(
        ["/agent/v1/files/<path:path>"],
        type="http", auth="public", methods=["HEAD"], csrf=False)
    @requires_api_key
    def files_head(self, path, **_kw):
        try:
            result = _fs.resolve(request.env, "/" + path)
        except _fs.NotFound:
            return request.make_response("", status=404)
        headers = []
        if result.get("etag"):
            headers.append(("ETag", result["etag"]))
        return request.make_response("", status=200, headers=headers)
