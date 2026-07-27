# SPDX-License-Identifier: LGPL-3.0-only
"""JSON endpoints for the Training Hub.

Two routes:

- ``GET /training/recommended`` — returns the per-user recommended set,
  consumed by the IQ-Deck intranet tile (``www.odooiq.local:9443/deck/``)
  and the in-app Help systray on first open.

- ``GET /training/search?q=...&menu_id=N`` — JTBD verb-phrase search,
  consumed by the Help panel input box.

Both are ``auth='user'`` for now. If the IQ-Deck tile needs to render
without a logged-in session, we'd add a ``/training/public_recommended``
route gated by an API key (see ``southbrook_integrations`` for the
pattern) — not added in v1 because the IQ-Deck tile is intranet-only
and behind Cloudflare Access.
"""
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class SouthbrookTrainingController(http.Controller):

    def _require_internal(self):
        """These routes back the internal Help panel + the intranet IQ-Deck
        tile. Because search_for_user sudo's the catalogue read (so the model
        ACL doesn't apply), a portal/share user would otherwise read every
        un-role-gated item — including internal runbooks (the fail-open default).
        Restrict to internal users; the trade-partner path is the Hermes
        find_training tool, not these routes. Returns a 403 response or None."""
        if not request.env.user._is_internal():
            return request.make_response(
                json.dumps({"error": "forbidden"}),
                status=403,
                headers=[("Content-Type", "application/json")],
            )
        return None

    @http.route("/training/recommended", type="http", auth="user",
                methods=["GET"], csrf=False, save_session=False)
    def recommended(self, limit=8, **kwargs):
        """Return the recommendation set for the current user.

        Query params:
            ``limit`` — int, max items to return (default 8, cap 25).

        Response: JSON envelope ``{"schema": "...v1", "user_id": N,
                "count": N, "items": [...]}``.
        """
        forbidden = self._require_internal()
        if forbidden is not None:
            return forbidden
        try:
            n = max(1, min(int(limit), 25))
        except (TypeError, ValueError):
            n = 8
        items = request.env["southbrook.training.item"].sudo()\
            .with_user(request.env.user).search_for_user(query=None, limit=n)
        body = {
            "schema": "southbrook.training.recommended.v1",
            "user_id": request.env.user.id,
            "count": len(items),
            "items": items,
        }
        return request.make_response(
            json.dumps(body),
            headers=[("Content-Type", "application/json")],
        )

    @http.route("/training/search", type="http", auth="user",
                methods=["GET"], csrf=False, save_session=False)
    def search(self, q=None, menu_id=None, limit=10, **kwargs):
        """JTBD search — multi-axis ilike across name, summary, JTBD tags.

        Query params:
            ``q`` — the JTBD-style verb phrase, e.g. "create a kitchen quote".
            ``menu_id`` — optional ir.ui.menu.id to scope to pinned items
                          for that menu when present.
            ``limit`` — int, default 10, cap 25.
        """
        forbidden = self._require_internal()
        if forbidden is not None:
            return forbidden
        try:
            n = max(1, min(int(limit), 25))
        except (TypeError, ValueError):
            n = 10
        menu_int = None
        if menu_id:
            try:
                menu_int = int(menu_id)
            except (TypeError, ValueError):
                menu_int = None
        items = request.env["southbrook.training.item"].sudo()\
            .with_user(request.env.user).search_for_user(
                query=q, menu_id=menu_int, limit=n)
        body = {
            "schema": "southbrook.training.search.v1",
            "query": q or "",
            "menu_id": menu_int,
            "count": len(items),
            "items": items,
        }
        return request.make_response(
            json.dumps(body),
            headers=[("Content-Type", "application/json")],
        )
