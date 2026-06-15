# SPDX-License-Identifier: LGPL-3.0-only
"""Agent self-discovery manifest.

`/.well-known/ai-agent.json` lets any LLM agent (Claude, GPT, Gemini)
discover this server's filesystem + tool surface in a single request.
Modelled after the OpenAI plugin / ChatGPT actions manifest pattern, but
generalized to any model.
"""
import json

from odoo import http
from odoo.http import request


class KitchenForgeAgentManifest(http.Controller):

    @http.route(
        ["/.well-known/ai-agent.json",
         "/.well-known/kitchenforge-agent.json"],
        type="http", auth="public", methods=["GET"], csrf=False)
    def agent_manifest(self, **_kw):
        base = request.httprequest.host_url.rstrip("/")
        body = {
            "schema_version": "v1",
            "name_for_model": "kitchenforge",
            "name_for_human": "KitchenForge — Kitchen MRP",
            "description_for_human":
                "Design, quote, and manufacture kitchen cabinets end-to-end.",
            "description_for_model":
                "KitchenForge exposes a filesystem-like agent surface for kitchen "
                "cabinet design and manufacturing. Use /agent/v1/files to navigate "
                "templates, projects, catalog, and shop state; use /agent/v1/tools "
                "to take typed actions (instantiate a project from a template, add "
                "or edit cabinet zones, confirm quotes, release manufacturing "
                "orders, raise ECOs). Every write requires X-Api-Key and supports "
                "Idempotency-Key for retry safety. Read /agent/v1/tools to fetch "
                "the JSON-Schema tool catalog suitable for direct tool_use binding.",
            "auth": {
                "type": "api_key",
                "header_name": "X-Api-Key",
                "issuance": "Generated per user in the KitchenForge backend at "
                            "Users -> API Keys.",
            },
            "filesystem": {
                "base_url": f"{base}/agent/v1/files",
                "verbs": ["GET", "PUT", "HEAD"],
                "namespaces": [
                    {"path": "/templates", "writable": True,
                     "desc": "Reusable project shapes."},
                    {"path": "/projects", "writable": True,
                     "desc": "Active kitchen jobs."},
                    {"path": "/catalog", "writable": False,
                     "desc": "Cabinet, attribute, rule, hardware catalog."},
                    {"path": "/shop", "writable": False,
                     "desc": "Workcenters + live schedule."},
                ],
                "etag_concurrency": True,
            },
            "tools_url": f"{base}/agent/v1/tools",
            "magicpath_compatibility": {
                "note": "Tree shape is compatible with magicpath.ai/files-style "
                        "agent UIs: every node has a stable path, file/dir kind, "
                        "and (for files) a content payload + etag.",
            },
        }
        return request.make_response(
            json.dumps(body, indent=2),
            status=200,
            headers=[("Content-Type", "application/json")],
        )
