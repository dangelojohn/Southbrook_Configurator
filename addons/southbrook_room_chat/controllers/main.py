# SPDX-License-Identifier: LGPL-3.0-only
"""JSON-RPC endpoint backing the conversational AI room-builder chat.

One route: POST /southbrook/api/order/<order_id>/room/chat.

Mirrors addons/southbrook_room_capture/controllers/main.py exactly:
  * ownership resolved via `_SouthbrookOrderAccessMixin._southbrook_resolve_order`
    (AccessError -> forbidden, MissingError -> not_found);
  * type="json", auth="user", methods=["POST"];
  * handlers return plain dicts, success shape {"ok": True, ...},
    error shape {"error": "<code>", "detail": "<msg>"};
  * per-user in-process sliding-window rate limiter, own config namespace.

This controller never creates southbrook.room / .wall / .constraint
records — southbrook.room.chat.agent only ever mutates a JSON draft on
southbrook.room.chat.session. Persistence still requires a human to review
+ submit through the existing Room Setup wizard, which validates via
southbrook.room.validate_geometry exactly as for hand-typed geometry.
"""
import logging
import time

from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

from odoo.addons.southbrook_estimating_website.controllers.main import (
    _SouthbrookOrderAccessMixin,
)

_logger = logging.getLogger(__name__)

_RATE_WINDOW_SEC_DEFAULT = 3600
_RATE_LIMIT_DEFAULT = 60  # chat turns are cheaper individually than a
                          # photo analysis but there are more of them per
                          # session, hence a higher default than
                          # southbrook_room_capture's 20/hour.
_RATE_CAP = 4096
_RATE_BUCKETS = {}


def _rate_limit_params():
    try:
        Param = request.env["ir.config_parameter"].sudo()
        window = int(Param.get_param(
            "southbrook_room_chat.rate_window_sec",
            str(_RATE_WINDOW_SEC_DEFAULT)))
        limit = int(Param.get_param(
            "southbrook_room_chat.rate_limit",
            str(_RATE_LIMIT_DEFAULT)))
    except Exception:  # noqa: BLE001
        window, limit = _RATE_WINDOW_SEC_DEFAULT, _RATE_LIMIT_DEFAULT
    window = max(1, min(window, 24 * 3600))
    limit = max(1, min(limit, 10_000))
    return window, limit


def _rate_limit_check(key):
    """Same in-process sliding-window limiter as
    southbrook_room_capture/controllers/main.py (adapted from
    southbrook_qr_kit's floor_action.py). Returns True if `key` is within
    budget, False if it exceeded. Bounded to _RATE_CAP distinct keys."""
    if not key:
        return True
    window, limit = _rate_limit_params()
    now = int(time.time())
    if len(_RATE_BUCKETS) >= _RATE_CAP:
        for k in list(_RATE_BUCKETS.keys()):
            head, _cnt = _RATE_BUCKETS[k]
            if now - head > window:
                _RATE_BUCKETS.pop(k, None)
        if len(_RATE_BUCKETS) >= _RATE_CAP:
            items = sorted(_RATE_BUCKETS.items(), key=lambda kv: kv[1][0])
            for k, _v in items[:_RATE_CAP // 2]:
                _RATE_BUCKETS.pop(k, None)
    head, cnt = _RATE_BUCKETS.get(key, (now, 0))
    if now - head > window:
        _RATE_BUCKETS[key] = (now, 1)
        return True
    if cnt + 1 > limit:
        return False
    _RATE_BUCKETS[key] = (head, cnt + 1)
    return True


class SouthbrookRoomChatApi(_SouthbrookOrderAccessMixin, http.Controller):
    """AI room-chat JSON-RPC endpoint."""

    @http.route(
        "/southbrook/api/order/<int:order_id>/room/chat",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def southbrook_api_room_chat(self, order_id, message=None, reset=False, **kw):
        try:
            self._southbrook_resolve_order(order_id)
        except MissingError:
            return {"error": "not_found"}
        except AccessError:
            return {"error": "forbidden"}

        if not _rate_limit_check(request.env.user.id):
            return {"error": "rate_limited"}

        if not reset and (not isinstance(message, str) or not message.strip()):
            return {"error": "invalid", "detail": "message is required."}

        Agent = request.env["southbrook.room.chat.agent"].sudo()
        try:
            result = Agent.handle_turn(order_id, message, reset=bool(reset))
        except Exception as exc:  # noqa: BLE001 — never 500, never leak
            _logger.warning(
                "southbrook_room_chat: handle_turn raised for order %s: %s",
                order_id, exc,
            )
            return {"error": "upstream_error", "detail": "AI room chat failed."}

        if not result.get("ok"):
            return {
                "error": result.get("error", "upstream_error"),
                "detail": result.get("detail", ""),
            }

        return {
            "ok": True,
            "reply": result["reply"],
            "room": result["room"],
        }
