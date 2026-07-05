# SPDX-License-Identifier: LGPL-3.0-only
"""JSON-RPC endpoints backing AI-assisted room capture + QR part lookup.

Two routes:
  * POST /southbrook/api/order/<order_id>/room/analyze-photos
  * POST /southbrook/api/order/<order_id>/scan-part

Mirrors the pattern in addons/southbrook_estimating_website/controllers/
room_api.py + main.py exactly:
  * ownership resolved via `_SouthbrookOrderAccessMixin._southbrook_resolve_order`
    (AccessError -> forbidden, MissingError -> not_found);
  * type="json", auth="user", methods=["POST"];
  * handlers return plain dicts, success shape {"ok": True, ...},
    error shape {"error": "<code>", "detail": "<msg>"};
  * every ORM op is .sudo() (ownership already checked at this layer).

analyze-photos NEVER creates southbrook.room / .wall / .constraint
records and NEVER creates ir.attachment — uploaded photo bytes exist
only as local Python variables for the life of this request; they are
decoded, size/mime-validated, handed to
southbrook.room.capture.analyze(), and then simply go out of scope.
The AI estimate is a suggestion for the EXISTING Room Setup wizard to
pre-fill; persistence still requires a human to review + submit
through the wizard, which validates via
southbrook.room.validate_geometry exactly as for hand-typed geometry.

scan-part (2026-07-04) resolves a customer/estimator's scanned
Southbrook QR (decoded client-side from the physical cabinet's
Floor-Traveler label) to its `sb.production.package`, verifies the
scanning user owns the sale order that package's line belongs to
(NOT just the route's own <order_id> — the scanned id is
attacker-controlled), and returns customer-safe part details for
the Order Lines estimate display. READ-ONLY: never creates a record,
never calls record_scan() / advances a work order — that's the
shop-floor scan endpoint in southbrook_floor_traveler, a different
route entirely. The parse + serialize logic lives in the
`southbrook.qr.part` AbstractModel (models/southbrook_qr_part.py) so
it's unit-testable without HTTP.
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


# ----------------------------------------------------------------------
# Per-user outbound rate limiter for scan-part — independent bucket +
# ir.config_parameter keys from the analyze-photos limiter above. A QR
# scan is a cheap read-only ORM lookup (no AI call), so it gets its own,
# more generous budget rather than sharing analyze-photos' quota. Same
# sliding-window algorithm as `_rate_limit_check`, deliberately
# duplicated (not parameterized) to keep each route's limiter simple to
# read and independently tunable.
# ----------------------------------------------------------------------
_SCAN_RATE_WINDOW_SEC_DEFAULT = 3600
_SCAN_RATE_LIMIT_DEFAULT = 60
_SCAN_RATE_BUCKETS = {}


def _scan_rate_limit_params():
    """Read window + limit from ir.config_parameter. Defaults: 60
    requests / 3600 s / user."""
    try:
        Param = request.env["ir.config_parameter"].sudo()
        window = int(Param.get_param(
            "southbrook_room_capture.scan_rate_window_sec",
            str(_SCAN_RATE_WINDOW_SEC_DEFAULT)))
        limit = int(Param.get_param(
            "southbrook_room_capture.scan_rate_limit",
            str(_SCAN_RATE_LIMIT_DEFAULT)))
    except Exception:  # noqa: BLE001
        window, limit = _SCAN_RATE_WINDOW_SEC_DEFAULT, _SCAN_RATE_LIMIT_DEFAULT
    window = max(1, min(window, 24 * 3600))
    limit = max(1, min(limit, 10_000))
    return window, limit


def _scan_rate_limit_check(key):
    """Return True if `key` (a user id) is within budget, False if it
    exceeded. Side effect: bumps the counter on True. Bounded to
    _RATE_CAP distinct keys; LRU-trims when full."""
    if not key:
        return True  # don't block requests with no identifiable key
    window, limit = _scan_rate_limit_params()
    now = int(time.time())
    if len(_SCAN_RATE_BUCKETS) >= _RATE_CAP:
        for k in list(_SCAN_RATE_BUCKETS.keys()):
            head, _cnt = _SCAN_RATE_BUCKETS[k]
            if now - head > window:
                _SCAN_RATE_BUCKETS.pop(k, None)
        if len(_SCAN_RATE_BUCKETS) >= _RATE_CAP:
            items = sorted(_SCAN_RATE_BUCKETS.items(), key=lambda kv: kv[1][0])
            for k, _v in items[:_RATE_CAP // 2]:
                _SCAN_RATE_BUCKETS.pop(k, None)
    head, cnt = _SCAN_RATE_BUCKETS.get(key, (now, 0))
    if now - head > window:
        _SCAN_RATE_BUCKETS[key] = (now, 1)
        return True
    if cnt + 1 > limit:
        return False
    _SCAN_RATE_BUCKETS[key] = (head, cnt + 1)
    return True


class SouthbrookRoomCaptureApi(_SouthbrookOrderAccessMixin, http.Controller):
    """AI room-capture JSON-RPC endpoint."""

    # Sane residential ceiling range for the optional scale hint (mm).
    _SB_MIN_CEILING_MM = 1500
    _SB_MAX_CEILING_MM = 4500

    @staticmethod
    def _sb_sanitize_scale_reference(scale_reference):
        """Return a safe scale_reference or None. Only a ceiling_height_mm
        inside a sane residential range survives; anything else (wrong
        type, out of range, a homeowner's '8 ft' arriving as 8) is
        dropped so the AI never gets a garbage scale anchor. Never raises."""
        if not isinstance(scale_reference, dict):
            return None
        raw = scale_reference.get("ceiling_height_mm")
        try:
            mm = int(round(float(raw)))
        except (TypeError, ValueError):
            return None
        cls = SouthbrookRoomCaptureApi
        if cls._SB_MIN_CEILING_MM <= mm <= cls._SB_MAX_CEILING_MM:
            return {"ceiling_height_mm": mm}
        return None

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
            order = self._southbrook_resolve_order(order_id)
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

        # Fail-safe scale clamp (2026-07-05): the ceiling hint is only a
        # scale AID, never authoritative. The UI now sends it from a
        # fixed dropdown (millimetres), but a crafted request could still
        # POST anything — so drop a ceiling_height_mm outside a sane
        # residential range (1.5m–4.5m) rather than feed the AI a garbage
        # scale anchor (e.g. "8" meaning feet arriving as 8mm). Never
        # errors; a bad hint is simply ignored.
        scale_reference = self._sb_sanitize_scale_reference(scale_reference)

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
        low_confidence = bool(result.get("low_confidence"))

        # CRM follow-up (2026-07-05): a TRUSTWORTHY capture (real walls +
        # not low-confidence — the same bar the frontend uses to prefill)
        # means a serious customer photographed a real kitchen, so land a
        # follow-up lead for a live designer. Idempotent per order;
        # best-effort — a CRM hiccup must never fail the capture response.
        lead_saved = False
        if estimate.get("walls") and not low_confidence:
            lead = Capture.create_capture_followup_lead(order, estimate)
            lead_saved = bool(lead)

        return {
            "ok": True,
            "estimate": estimate,
            "existing_room": Capture._estimate_to_existing_room(estimate),
            "low_confidence": low_confidence,
            "lead_saved": lead_saved,
        }

    # ------------------------------------------------------------------
    # QR part lookup (2026-07-04)
    # ------------------------------------------------------------------
    @http.route(
        "/southbrook/api/order/<int:order_id>/scan-part",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def southbrook_api_scan_part(self, order_id, payload=None, **kw):
        """Resolve a scanned Southbrook QR payload to its manufactured
        part (sb.production.package) and return customer-safe details
        for display in the Order Lines estimate.

        Request:  {"payload": "sb-package:<id>"}  (or the signed
                   "sb://pkg/<id>?t=<ts>&s=<hmac>" format).
        Response: {"ok": True, "part": {...}, "in_current_order": bool,
                   "line_id": <id or null>, "quote_number": "<S...>"}
                  or {"error": "<code>", "detail": "..."} — codes:
                  forbidden / not_found / invalid / rate_limited.

        Security: the scanned <id> is attacker-controlled, so ownership
        is checked TWICE — once for the route's own <order_id> (so an
        unauthenticated-for-this-order caller can't probe at all), and
        again for the scanned package's OWN sale order (so a customer
        who owns order A can't read another customer's part just
        because they guessed/scanned a package id from order B). Both
        checks go through the same `_southbrook_resolve_order` used
        everywhere else in this codebase — never a bespoke ACL check.
        """
        try:
            self._southbrook_resolve_order(order_id)
        except MissingError:
            return {"error": "not_found"}
        except AccessError:
            return {"error": "forbidden"}

        if not _scan_rate_limit_check(request.env.user.id):
            return {"error": "rate_limited"}

        if not isinstance(payload, str) or not payload.strip():
            return {
                "error": "invalid",
                "detail": "payload must be a non-empty string.",
            }

        QrPart = request.env["southbrook.qr.part"].sudo()
        package_id = QrPart.resolve_package_id(payload)
        if package_id is None:
            return {"error": "invalid", "detail": "unrecognized QR"}

        Package = request.env["sb.production.package"].sudo()
        package = Package.browse(package_id).exists()
        if not package:
            return {"error": "not_found"}

        # The scanned package's OWN order — NOT necessarily the route's
        # order_id. Nullable (legacy packages may carry no line).
        pkg_order = package.sale_order_line_id.order_id
        if not pkg_order:
            return {"error": "not_found"}

        # SECURITY — collapse "not yours" into "not_found" here (unlike
        # the route order_id check above, which returns forbidden). The
        # scanned package id is attacker-controlled, so distinguishing a
        # package that exists-but-isn't-yours (forbidden) from one that
        # doesn't exist (not_found) would be an existence oracle letting
        # an authed user enumerate valid package ids / production volume.
        # Both cases return not_found — no part data is ever served.
        try:
            self._southbrook_resolve_order(pkg_order.id)
        except (MissingError, AccessError):
            return {"error": "not_found"}

        resolved = QrPart.serialize(package, order_id)
        return {
            "ok": True,
            "part": resolved["part"],
            "in_current_order": resolved["in_current_order"],
            "line_id": resolved["line_id"],
            "quote_number": resolved["quote_number"],
        }

    # ------------------------------------------------------------------
    # STAFF QR scanner (2026-07-05) — installers / shipping / factory.
    #
    # Distinct from the customer scan-part above in EVERY dimension: it
    # is NOT order-scoped (staff look up ANY package), it returns FULL
    # internal detail (customer, manufacturing, shipping, scan history),
    # and it is gated to INTERNAL users only. A portal customer must
    # never reach it. Its own mobile-friendly page lives at /southbrook/
    # scan; the JSON lookup is /southbrook/api/scan/lookup.
    # ------------------------------------------------------------------
    @staticmethod
    def _sb_is_internal_user():
        user = request.env.user
        # Internal staff = member of base.group_user AND not a portal
        # share user. Public/portal users are excluded.
        return bool(
            user
            and not user._is_public()
            and not user.share
            and user.has_group("base.group_user")
        )

    @http.route(
        "/southbrook/api/scan/lookup",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def southbrook_api_scan_lookup(self, payload=None, **kw):
        """Resolve a scanned Southbrook QR to its production package and
        return FULL internal detail for staff. Internal users only."""
        if not self._sb_is_internal_user():
            return {"error": "forbidden",
                    "detail": "This scanner is for Southbrook staff."}
        if not _scan_rate_limit_check(request.env.user.id):
            return {"error": "rate_limited"}
        if not isinstance(payload, str) or not payload.strip():
            return {"error": "invalid",
                    "detail": "payload must be a non-empty string."}

        result = request.env["southbrook.qr.staff"].sudo().lookup(payload)
        if not result.get("ok"):
            return {"error": result.get("error", "lookup_failed")}
        return {"ok": True, "info": result["info"]}

    @http.route(
        "/southbrook/scan",
        type="http",
        auth="user",
        website=True,
        sitemap=False,
    )
    def southbrook_staff_scan_page(self, **kw):
        """Full-screen mobile QR scanner page for Southbrook staff. A
        portal/customer user is redirected to their portal home — this
        surface is internal-only."""
        if not self._sb_is_internal_user():
            return request.redirect("/my")
        return request.render(
            "southbrook_room_capture.staff_scan_page", {})
