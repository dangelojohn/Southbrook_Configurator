# SPDX-License-Identifier: LGPL-3.0-only
"""Hermes tool: find_training.

Registers with ``southbrook_hermes.tools.decorator.TOOL_REGISTRY`` at import
time so trade-partner and internal Hermes personas can ask "how do I…?"
and get back the matching eLearning items.

Persona model
-------------

Both ``trade_partner`` and ``sales_rep`` and ``mfg_manager`` can call this —
training discovery is intentionally cross-persona. The Hermes tool dispatch
already enforces persona-bound args via the JWT, so we don't need to redo
that gating here.

Tier
----

``T0`` (read-only) — training search never mutates data.
"""
import logging

from odoo.addons.southbrook_hermes.tools.decorator import hermes_tool

_logger = logging.getLogger(__name__)


@hermes_tool(
    personas=["trade_partner", "sales_rep", "mfg_manager"],
    tier="T0",
    scope="training_catalogue",
    description=(
        "Find training material (lessons, JTBD micros, runbooks, in-app tours) "
        "matching a natural-language verb phrase like 'create a kitchen quote', "
        "'open an NCR', or 'run bi-weekly payroll'. Returns up to 5 items with "
        "URLs the caller can open in a new tab."),
)
def find_training(env, query: str, limit: int = 5):
    """Return matching training items for a JTBD-style query.

    Args:
        env: Odoo environment (passed by the @hermes_tool dispatcher).
        query: A natural-language phrase. Required.
        limit: Max items to return. Capped at 10.

    Returns:
        dict with schema, count, and items list. Each item carries
        id, name, summary, kind, url, minutes, audience, tags.
    """
    if not query or not query.strip():
        return {
            "schema": "southbrook.training.find.v1",
            "query": "",
            "count": 0,
            "items": [],
            "note": "query is required",
        }
    try:
        capped = max(1, min(int(limit or 5), 10))
    except (TypeError, ValueError):
        capped = 5
    # Do NOT sudo() — search_for_user builds its role_group_ids gate from
    # self.env.user. Under sudo that resolves to the SUPERUSER (in every group),
    # so the gate matches every item and a trade_partner persona would receive
    # internal-role-gated training. The Hermes dispatch already binds env to the
    # persona's user (request.env(user=...)), so the un-sudo'd call evaluates the
    # gate against the real caller. (search_for_user still sudo's the catalogue
    # read internally; only the gate needs the real identity.)
    Item = env["southbrook.training.item"]
    rows = Item.search_for_user(query=query, limit=capped)
    return {
        "schema": "southbrook.training.find.v1",
        "query": query,
        "count": len(rows),
        "items": rows,
    }
