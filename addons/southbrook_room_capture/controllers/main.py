# SPDX-License-Identifier: LGPL-3.0-only
"""JSON-RPC endpoint backing AI-assisted room capture.

One route: POST /southbrook/api/order/<order_id>/room/analyze-photos.

Mirrors the pattern in addons/southbrook_estimating_website/controllers/
room_api.py + main.py exactly:
  * ownership resolved via `_SouthbrookOrderAccessMixin._southbrook_resolve_order`
    (AccessError -> forbidden, MissingError -> not_found);
  * type="json", auth="user", methods=["POST"];
  * handlers return plain dicts, success shape {"ok": True, ...},
    error shape {"error": "<code>", "detail": "<msg>"};
  * every ORM op is .sudo() (ownership already checked at this layer).

This controller NEVER creates southbrook.room / .wall / .constraint
records and NEVER creates ir.attachment — uploaded photo bytes exist
only as local Python variables for the life of this request; they are
decoded, size/mime-validated, handed to
southbrook.room.capture.analyze(), and then simply go out of scope.
The AI estimate is a suggestion for the EXISTING Room Setup wizard to
pre-fill; persistence still requires a human to review + submit
through the wizard, which validates via
southbrook.room.validate_geometry exactly as for hand-typed geometry.
"""
import base64
import logging
import time

from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

from odoo.addons.southbrook_estimating_website.controllers.main import (
    _SouthbrookOrderAccessMixin,
)

_logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Upload validation constants. Kept in sync with (but independent of)
# southbrook.room.capture's own limits — this controller is the first
# line of defense so a malformed/oversized/wrong-mime payload never
# even reaches the model layer.
# ----------------------------------------------------------------------
_MAX_IMAGES = 5
_MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB pre-downscale cap per image
_ALLOWED_MIMES = {"image/jpeg", "image/jpg", "image/png"}

# ----------------------------------------------------------------------
# Per-user outbound rate limiter — adapted from the in-process sliding-
# window limiter in addons/southbrook_qr_kit/controllers/floor_action.py
# (_RATE_BUCKETS / _rate_limit_check), keyed on request.env.user.id
# instead of source IP (this route is authenticated, unlike the public
# QR floor actions).
# ----------------------------------------------------------------------
_RATE_WINDOW_SEC_DEFAULT = 3600
_RATE_LIMIT_DEFAULT = 20
_RATE_CAP = 4096
_RATE_BUCKETS = {}


def _rate_limit_params():
    """Read window + limit from ir.config_parameter. Defaults: 20
    requests / 3600 s / user."""
    try:
        Param = request.env["ir.config_parameter"].sudo()
        window = int(Param.get_param(
            "southbrook_room_capture.rate_window_sec",
            str(_RATE_WINDOW_SEC_DEFAULT)))
        limit = int(Param.get_param(
            "southbrook_room_capture.rate_limit",
            str(_RATE_LIMIT_DEFAULT)))
    except Exception:  # noqa: BLE001
        window, limit = _RATE_WINDOW_SEC_DEFAULT, _RATE_LIMIT_DEFAULT
    window = max(1, min(window, 24 * 3600))
    limit = max(1, min(limit, 10_000))
    return window, limit


def _rate_limit_check(key):
    """Return True if `key` (a user id) is within budget, False if it
    exceeded. Side effect: bumps the counter on True. Bounded to
    _RATE_CAP distinct keys; LRU-trims when full."""
    if not key:
        return True  # don't block requests with no identifiable key
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


class SouthbrookRoomCaptureApi(_SouthbrookOrderAccessMixin, http.Controller):
    """AI room-capture JSON-RPC endpoint."""

    @http.route(
        "/southbrook/api/order/<int:order_id>/room/analyze-photos",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def southbrook_api_room_analyze_photos(
        self, order_id, images=None, scale_reference=None, **kw,
    ):
        try:
            self._southbrook_resolve_order(order_id)
        except MissingError:
            return {"error": "not_found"}
        except AccessError:
            return {"error": "forbidden"}

        if not _rate_limit_check(request.env.user.id):
            return {"error": "rate_limited"}

        if not isinstance(images, list) or not images:
            return {
                "error": "invalid",
                "detail": "images must be a non-empty list (max %d)."
                          % _MAX_IMAGES,
            }
        if len(images) > _MAX_IMAGES:
            return {
                "error": "invalid",
                "detail": "At most %d images are allowed." % _MAX_IMAGES,
            }

        validated_images = []
        for idx, item in enumerate(images):
            if isinstance(item, dict):
                data = item.get("data")
                mime = (item.get("mime") or item.get("mimetype") or "").lower().strip()
            elif isinstance(item, str):
                data = item
                mime = ""
            else:
                return {
                    "error": "invalid",
                    "detail": "images[%d] must be a base64 string or a "
                              "{data, mime} object." % idx,
                }
            if not data:
                return {
                    "error": "invalid",
                    "detail": "images[%d] is missing data." % idx,
                }

            payload = data
            if isinstance(payload, str) and payload.startswith("data:"):
                try:
                    header, payload = payload.split(",", 1)
                except ValueError:
                    return {
                        "error": "invalid",
                        "detail": "images[%d] has a malformed data URI." % idx,
                    }
                if ";base64" not in header:
                    return {
                        "error": "invalid",
                        "detail": "images[%d]: only base64 data URIs are "
                                  "supported." % idx,
                    }
                if not mime:
                    try:
                        mime = header.split(":", 1)[1].split(";", 1)[0].lower()
                    except IndexError:
                        mime = ""

            try:
                raw = base64.b64decode(payload, validate=False)
            except Exception:  # noqa: BLE001
                return {
                    "error": "invalid",
                    "detail": "images[%d] is not valid base64." % idx,
                }
            if not raw:
                return {
                    "error": "invalid",
                    "detail": "images[%d] decoded to empty data." % idx,
                }
            if not mime:
                mime = "image/jpeg"
            if mime not in _ALLOWED_MIMES:
                return {
                    "error": "invalid",
                    "detail": "images[%d] has an unsupported mime type %r."
                              % (idx, mime),
                }
            if len(raw) > _MAX_IMAGE_BYTES:
                return {
                    "error": "invalid",
                    "detail": "images[%d] exceeds the %d-byte size cap."
                              % (idx, _MAX_IMAGE_BYTES),
                }
            validated_images.append({"data": raw, "mime": mime})

        Capture = request.env["southbrook.room.capture"].sudo()
        try:
            result = Capture.analyze(
                validated_images, scale_reference=scale_reference)
        except Exception as exc:  # noqa: BLE001 — never 500, never leak
            # Log a message with NO image data — just the order id and
            # the exception text.
            _logger.warning(
                "southbrook_room_capture: analyze() raised for order "
                "%s: %s", order_id, exc,
            )
            return {
                "error": "upstream_error",
                "detail": "AI room analysis failed.",
            }

        if not result.get("ok"):
            return {
                "error": result.get("error", "upstream_error"),
                "detail": result.get("detail", ""),
            }

        estimate = result["estimate"]
        return {
            "ok": True,
            "estimate": estimate,
            "existing_room": Capture._estimate_to_existing_room(estimate),
            "low_confidence": bool(result.get("low_confidence")),
        }
