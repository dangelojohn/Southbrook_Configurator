# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook REST API",
    "summary": "Stateless /api/v1/* surface implementing the G6 contract "
               "(docs/api_contracts/flutter_odoo_contract.md). The Flutter "
               "app + any future web SPA wire against this.",
    "description": """
Southbrook REST API
====================

Implements every endpoint from G6 (schema 'southbrook.flutter.api.v1'):

  POST   /api/v1/auth/login                       — issue an API key
  GET    /api/v1/me                               — authenticated profile
  GET    /api/v1/kitchen-projects                 — list user's projects
  GET    /api/v1/kitchen-projects/<id>            — project detail
  POST   /api/v1/kitchen-projects/<id>/photos     — multipart upload + analyze
  GET    /api/v1/kitchen-projects/<id>/concepts   — list design options
  POST   /api/v1/kitchen-projects/<id>/concepts/<opt_id>/select
  POST   /api/v1/kitchen-projects/<id>/approve

Auth: X-Api-Key header on every endpoint except /auth/login.

Idempotency: any POST may pass Idempotency-Key. Replays within
config_parameter `southbrook.api.idempotency_ttl_hours` (default 24)
return the original status code + body.

Error envelope per G6 §4: stable machine `error` code + locale-aware
`message` + optional `details` payload.

Every response (success AND error) includes a `schema` field literal
matching `southbrook.flutter.api.v1` so the client can detect server
upgrades.

Schema versioning: a future v2 lands at /api/v2/* side-by-side; v1
remains live for at least one Phase cycle per the contract §6.
""",
    "author": "Southbrook Kitchens / OdooIQ",
    "license": "LGPL-3",
    "category": "Manufacturing",
    "version": "19.0.1.0.0",
    "depends": [
        "base",
        "mail",
        "southbrook_kitchen_workspace",
        "southbrook_ai_design",
        # Phase 4 Sprint 1 — Accucutt cut-list bridge endpoints
        # (/api/v1/cutlist/<id>/envelope + /nesting-result) read sb.cutlist.
        "southbrook_kitchen_mrp",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/config_parameters.xml",
        "views/southbrook_api_key_views.xml",
        "views/southbrook_api_menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
