# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.room.capture — AI-assisted room geometry estimation.

Calls the Anthropic Messages API (vision) with 1-5 downscaled room
photos and returns a NORMALIZED geometry estimate. This model NEVER
creates southbrook.room / .wall / .constraint records, NEVER writes
image bytes to ir.attachment or disk, and NEVER logs image data.
Persistence always goes through the EXISTING "Set Up Your Room" wizard
(southbrook_estimating_website's RoomSetupWizard), which routes every
save through southbrook.room.validate_geometry — the AI output is just
a pre-fill suggestion for a human to review and correct.

Structurally mirrors addons/southbrook_ai_design/models/
southbrook_gemini_client.py (lazy `import httpx`, mock/real backend
toggle via ir.config_parameter, retry-free single-shot call with a
generous timeout) but targets Anthropic's Messages API, not Gemini.

Two backends, selected by ir.config_parameter
`southbrook_room_capture.use_mock` (default "True" so cold installs
and CI never touch the network):

* Mock — returns _MOCK_ESTIMATE, a plausible straight-wall kitchen.
* Real — POSTs to the Anthropic Messages API using the API key from
  `southbrook_room_capture.anthropic_api_key` (or the ANTHROPIC_API_KEY
  environment variable as a fallback).
"""
import base64
import io
import json
import logging
import os
import warnings

from odoo import _, api, fields, models
from odoo.tools import plaintext2html

_logger = logging.getLogger(__name__)

_SHAPE_LABELS = {
    "straight": "straight run", "l_shape": "L-shaped", "u_shape": "U-shaped",
    "galley": "galley", "g_shape": "G-shaped", "island": "island",
    "peninsula": "peninsula", "custom": "custom",
}

# ----------------------------------------------------------------------
# Domain vocabularies — MUST mirror southbrook.room / .wall / .constraint
# selection keys exactly (addons/southbrook_estimating/models/
# southbrook_room.py / southbrook_room_constraint.py) so a normalized
# estimate can always be fed through southbrook.room.validate_geometry
# and, after human review, the room/wall/constraint create calls.
# ----------------------------------------------------------------------
LAYOUT_SHAPES = (
    "straight", "l_shape", "u_shape", "galley", "g_shape",
    "island", "peninsula", "custom",
)
CONSTRAINT_TYPES = (
    "window", "door", "sink", "cooktop", "oven", "dishwasher",
    "rangehood", "fridge_space", "power_outlet", "structural_post",
    "other",
)

# JSON Schema for output_config.format (structured outputs). Every
# object below carries additionalProperties:false + a required list
# per the Anthropic structured-outputs subset (no minimum/maximum, no
# minLength/maxLength — those are enforced client-side in
# _normalize_estimate instead). Nullable scalar fields use anyOf with a
# null branch (Anthropic's supported subset includes anyOf but not
# union "type" arrays).
_ESTIMATE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "layout_shape", "ceiling_height_mm", "walls", "constraints",
        "assumptions", "warnings", "confidence",
    ],
    "properties": {
        "layout_shape": {
            "anyOf": [
                {"type": "string", "enum": list(LAYOUT_SHAPES)},
                {"type": "null"},
            ],
        },
        "ceiling_height_mm": {
            "anyOf": [{"type": "integer"}, {"type": "null"}],
        },
        "walls": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "length_mm", "confidence"],
                "properties": {
                    "name": {"type": "string"},
                    "length_mm": {"type": "integer"},
                    "confidence": {"type": "number"},
                },
            },
        },
        "constraints": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "constraint_type", "wall_index",
                    "distance_from_left_mm", "width_mm", "height_mm",
                    "height_from_floor_mm", "confidence",
                ],
                "properties": {
                    "constraint_type": {
                        "type": "string",
                        "enum": list(CONSTRAINT_TYPES),
                    },
                    "wall_index": {"type": "integer"},
                    "distance_from_left_mm": {"type": "integer"},
                    "width_mm": {"type": "integer"},
                    "height_mm": {"type": "integer"},
                    "height_from_floor_mm": {"type": "integer"},
                    "confidence": {"type": "number"},
                },
            },
        },
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
    },
}


class SouthbrookRoomCapture(models.AbstractModel):
    """env['southbrook.room.capture'] — AI room-capture caller + normalizer."""
    _name = "southbrook.room.capture"
    _description = "Southbrook AI Room Capture"

    # ------------------------------------------------------------------
    # Constants (module-level naming per spec; kept as class attributes
    # so tests can reference/patch them via the model class).
    # ------------------------------------------------------------------
    _ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
    _MODEL = "claude-sonnet-5"  # vision-capable; deliberate cost-controlled choice
    _MAX_IMAGES = 5
    _MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB pre-downscale cap per image
    # M1 fix: the byte cap above does NOT bound decoded pixel count — a
    # ~12000x12000 PNG (~144MP) can fit under 8MB on disk yet decode to
    # ~430MB in memory. Pillow only WARNS (DecompressionBombWarning) in
    # that band rather than raising, so `except Exception` in analyze()
    # never catches it. This explicit pixel-count cap is the primary
    # guard; see _downscale_image.
    _MAX_IMAGE_PIXELS = 40_000_000
    _MAX_LONG_EDGE_PX = 1568
    _TIMEOUT = 60.0
    _LOW_CONFIDENCE_THRESHOLD = 0.35
    _ALLOWED_MIMES = ("image/jpeg", "image/jpg", "image/png")
    _JPEG_QUALITY = 80

    # A plausible straight-wall kitchen: 1 wall, a window + a sink,
    # moderate confidence. Used by mock mode AND directly by tests that
    # want a known-good normalized estimate without any AI call.
    _MOCK_ESTIMATE = {
        "layout_shape": "straight",
        "ceiling_height_mm": 2400,
        "walls": [
            {"name": "Wall A", "length_mm": 3600, "confidence": 0.62},
        ],
        "constraints": [
            {
                "constraint_type": "window", "wall_index": 0,
                "distance_from_left_mm": 1200, "width_mm": 900,
                "height_mm": 1200, "height_from_floor_mm": 900,
                "confidence": 0.55,
            },
            {
                "constraint_type": "sink", "wall_index": 0,
                "distance_from_left_mm": 2000, "width_mm": 800,
                "height_mm": 200, "height_from_floor_mm": 850,
                "confidence": 0.60,
            },
        ],
        "assumptions": [
            "Assumed a single straight run based on the visible wall.",
            "Wall length estimated from typical base-cabinet module "
            "widths visible in frame.",
        ],
        "warnings": [
            "Ceiling height is an approximation; no reference object "
            "was visible for scale.",
        ],
        "confidence": 0.58,
    }

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    @api.model
    def _get_api_key(self):
        """Read the Anthropic API key from ir.config_parameter, falling
        back to the ANTHROPIC_API_KEY environment variable. Returns ""
        (never raises) when neither is set."""
        key = self.env["ir.config_parameter"].sudo().get_param(
            "southbrook_room_capture.anthropic_api_key", "")
        if key:
            return key
        return os.environ.get("ANTHROPIC_API_KEY", "") or ""

    @api.model
    def _use_mock(self):
        """ir.config_parameter southbrook_room_capture.use_mock.
        Defaults to True so a cold install / CI run never needs
        network access or a configured API key."""
        val = self.env["ir.config_parameter"].sudo().get_param(
            "southbrook_room_capture.use_mock", "True")
        return str(val).strip().lower() in ("1", "true", "yes", "on")

    @api.model
    def _room_capture_daily_cap(self):
        """Global ceiling on real (non-mock) Anthropic analyze() calls per
        day. ir.config_parameter southbrook_room_capture.max_daily_calls
        (default 500). 0 acts as a hard kill-switch — no real calls at all.

        The per-request rate limiter in the controller is PER WORKER and
        cannot see sibling workers, so a paid-API spend ceiling that every
        worker shares is enforced here instead. Bounds the cost blast-radius
        of a burst of portal self-signups hammering /room-capture/analyze."""
        ICP = self.env["ir.config_parameter"].sudo()
        try:
            return int(ICP.get_param(
                "southbrook_room_capture.max_daily_calls", "500"))
        except (TypeError, ValueError):
            return 500

    @api.model
    def _room_capture_consume_daily_quota(self):
        """Increment today's real-call counter; return True only if the call
        is within the global daily cap. Best-effort: the config-param
        read-modify-write can under-count under heavy concurrency, but as a
        COST ceiling an approximate bound is acceptable (exact accounting
        would need a shared counter store — see REVIEW_REPORT recommendation
        R1). 0 = kill-switch: no real call is ever permitted."""
        cap = self._room_capture_daily_cap()
        if cap <= 0:
            return False
        ICP = self.env["ir.config_parameter"].sudo()
        today = fields.Date.to_string(fields.Date.context_today(self))
        stamp = ICP.get_param("southbrook_room_capture.daily_call_date", "")
        if stamp != today:
            count = 0
        else:
            try:
                count = int(ICP.get_param(
                    "southbrook_room_capture.daily_call_count", "0"))
            except (TypeError, ValueError):
                count = 0
        if count >= cap:
            return False
        ICP.set_param("southbrook_room_capture.daily_call_date", today)
        ICP.set_param(
            "southbrook_room_capture.daily_call_count", str(count + 1))
        return True

    # ------------------------------------------------------------------
    # Image handling — decode + downscale. NEVER writes to disk or the
    # filestore; everything stays in memory for the life of the request.
    # ------------------------------------------------------------------
    @api.model
    def _decode_image_item(self, item):
        """Normalize one `images` list entry to (raw_bytes, mime).

        Accepts:
          * a dict {"data": <bytes|base64 str>, "mime"/"mimetype": str}
          * a bare base64 string (optionally a `data:<mime>;base64,...`
            URI) — mime defaults to image/jpeg if undeclared/unsniffable.

        Raises ValueError on anything that cannot be decoded; callers
        turn that into a graceful {"error": "invalid", ...} response.
        """
        if isinstance(item, dict):
            data = item.get("data")
            mime = (item.get("mime") or item.get("mimetype") or "").lower().strip()
        else:
            data = item
            mime = ""

        if data is None or data == "":
            raise ValueError("missing image data")

        if isinstance(data, bytes):
            return data, (mime or "image/jpeg")
        if isinstance(data, bytearray):
            return bytes(data), (mime or "image/jpeg")

        if not isinstance(data, str):
            raise ValueError("image data must be bytes or a base64 string")

        payload = data
        if payload.startswith("data:"):
            try:
                header, payload = payload.split(",", 1)
            except ValueError as exc:
                raise ValueError("malformed data: URI") from exc
            if ";base64" not in header:
                raise ValueError("only base64 data: URIs are supported")
            if not mime:
                try:
                    mime = header.split(":", 1)[1].split(";", 1)[0].lower()
                except IndexError:
                    mime = ""
        try:
            raw = base64.b64decode(payload, validate=False)
        except Exception as exc:  # noqa: BLE001 — any decode failure is "invalid"
            raise ValueError("invalid base64 image data") from exc
        if not raw:
            raise ValueError("decoded image data is empty")
        return raw, (mime or "image/jpeg")

    @api.model
    def _downscale_image(self, raw_bytes, mime):
        """Downscale/re-encode one image for the vision call.

        Never writes to disk. Returns (b64_str, media_type) where
        b64_str has no newlines (Anthropic requires a clean base64
        string) and media_type is always "image/jpeg" (we always
        re-encode, regardless of source format, so downstream code has
        exactly one media_type to handle).
        """
        try:
            from PIL import Image
        except ImportError as exc:  # pragma: no cover - Pillow is preinstalled
            raise ValueError(
                "Pillow is required to process images but is not "
                "installed"
            ) from exc

        # M1 fix — DecompressionBomb guard, part 1: open under a
        # warnings filter that promotes Pillow's own
        # DecompressionBombWarning (a warning-only signal Pillow emits
        # for large-but-not-huge images) to an exception, so it can't
        # silently slip past the `except Exception` in analyze() the
        # way a bare warning would. This is defense-in-depth; the
        # primary guard is the explicit pixel-count check below, which
        # catches everything above our OWN (much lower)
        # _MAX_IMAGE_PIXELS cap regardless of where Pillow's own
        # threshold happens to sit.
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            img = Image.open(io.BytesIO(raw_bytes))

        # M1 fix — DecompressionBomb guard, part 2 (primary guard):
        # bound decoded pixel count. The 8MB _MAX_IMAGE_BYTES cap in
        # analyze() does NOT bound this — a ~12000x12000 PNG (~144MP)
        # comfortably fits under 8MB on disk yet decodes to ~430MB in
        # memory once `.thumbnail()`/`.save()` touch it below. Guard
        # defensively in case a PIL build/version lacks .width/.height.
        # Raising ValueError here is caught by analyze()'s broad
        # `except Exception` around the downscale loop and turned into
        # a normal {"ok": False, ...} response — never an unhandled
        # exception / 500.
        width = getattr(img, "width", None)
        height = getattr(img, "height", None)
        if not isinstance(width, int) or not isinstance(height, int):
            raise ValueError("could not determine image dimensions")
        if width * height > self._MAX_IMAGE_PIXELS:
            raise ValueError(
                "image exceeds the maximum allowed pixel dimensions "
                "(%s x %s)" % (width, height)
            )

        # EXIF-transpose so a phone photo taken sideways doesn't get
        # analyzed rotated.
        try:
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img) or img
        except Exception:  # noqa: BLE001 — best-effort only
            pass

        if img.mode in ("RGBA", "LA"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            alpha = img.split()[-1]
            background.paste(img, mask=alpha)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        img.thumbnail(
            (self._MAX_LONG_EDGE_PX, self._MAX_LONG_EDGE_PX),
            Image.LANCZOS,
        )

        buf = io.BytesIO()
        img.save(buf, format="JPEG", optimize=True, quality=self._JPEG_QUALITY)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        # base64.b64encode never emits embedded newlines, but strip
        # defensively since the API requires a clean string.
        b64 = b64.replace("\n", "").replace("\r", "")
        return b64, "image/jpeg"

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------
    @api.model
    def _build_prompt(self, scale_reference=None):
        lines = [
            "You are assisting a kitchen cabinetry estimator. Analyze "
            "the attached photo(s) of a room and estimate its geometry "
            "so a human can review and correct it before anything is "
            "saved. This is a DRAFT estimate only.",
            "",
            "Extract as much usable room data as the photos support:",
            "  • layout_shape — one of: " + ", ".join(LAYOUT_SHAPES)
            + " (or null if genuinely unclear). If several photos show "
            "different walls of one room, infer the OVERALL shape (e.g. "
            "two walls meeting at a corner → l_shape) rather than "
            "treating each photo as a separate room.",
            "  • ceiling_height_mm — or null if unclear.",
            "  • walls — one entry per distinct wall you can see, in a "
            "consistent order; give each a name, length_mm, and "
            "confidence 0-1. Deduplicate: the same wall shown in two "
            "photos is ONE wall, not two.",
            "  • constraints — every fixed feature you can see: windows, "
            "doors, sink, cooktop, oven, dishwasher, rangehood, "
            "fridge_space, power_outlet, structural_post, other. For "
            "each give wall_index (0-based into your walls array), "
            "distance_from_left_mm along that wall, width_mm, height_mm, "
            "height_from_floor_mm, and confidence 0-1.",
            "",
            "Use real-world scale anchors visible in frame to calibrate "
            "sizes — standard base cabinets are ~600mm wide and ~900mm "
            "tall, a standard interior door ~800x2030mm, an outlet plate "
            "~115mm, a dishwasher/oven opening ~600mm — and note which "
            "anchor you used in `assumptions`.",
            "",
            "Also capture, in `assumptions`, brief context useful to the "
            "estimator preparing a quote: the apparent existing cabinet "
            "style/finish and rough count, visible appliance brands if "
            "legible, and the room's general condition (e.g. 'dated oak "
            "shaker uppers, ~8 doors', 'stainless GE range'). Keep each "
            "note short and factual; do NOT guess at anything not "
            "visible, and never invent a measurement.",
            "",
            "All lengths are in millimetres. Where you must estimate a "
            "dimension you can't measure directly, make your best "
            "assumption and record it in `assumptions`; record anything "
            "uncertain or ambiguous in `warnings`. Provide an overall "
            "`confidence` (0-1) for the whole estimate.",
        ]
        if scale_reference:
            lines.append("")
            lines.append(
                "A known reference measurement was provided to help "
                "calibrate scale — use it as the primary anchor: %s"
                % json.dumps(scale_reference)
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Anthropic call — isolated in its own method so tests can
    # monkeypatch it to return a canned raw response dict, exercising
    # the JSON-parsing/normalization path without any network access.
    # ------------------------------------------------------------------
    @api.model
    def _call_anthropic(self, image_blocks, api_key, scale_reference=None):
        """POST the vision request to Anthropic. Returns the raw parsed
        JSON response body (a dict). Raises on transport/HTTP errors;
        `analyze()` catches broadly and degrades gracefully. NEVER logs
        image bytes or the request/response body."""
        try:
            import httpx  # lazy import — addon installs without it (mock mode)
        except ImportError as exc:
            raise RuntimeError(
                "httpx is required to call the real Anthropic backend; "
                "install it or set southbrook_room_capture.use_mock=True"
            ) from exc

        content = []
        for block in image_blocks:
            # Image blocks MUST precede the text block per the vision
            # contract.
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": block["media_type"],
                    "data": block["data"],
                },
            })
        content.append({
            "type": "text",
            "text": self._build_prompt(scale_reference),
        })

        body = {
            "model": self._MODEL,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": content}],
            "output_config": {
                "format": {"type": "json_schema", "schema": _ESTIMATE_SCHEMA},
            },
            # M2 fix: explicitly disable thinking. claude-sonnet-5 runs
            # adaptive thinking by default when `thinking` is omitted,
            # and thinking tokens draw down the SAME max_tokens=4096
            # budget as the structured JSON output below — risking
            # truncation of a large wall/constraint list. {"type":
            # "disabled"} is accepted on Sonnet 5 (unlike Fable 5, where
            # it 400s). Deliberately still no temperature/top_p/top_k —
            # Sonnet 5 rejects non-default sampling params.
            "thinking": {"type": "disabled"},
        }
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        resp = httpx.post(
            self._ANTHROPIC_URL, json=body, headers=headers,
            timeout=self._TIMEOUT,
        )
        if resp.status_code != 200:
            # Log status only — never the body, which could echo the
            # request (and therefore the prompt) back.
            _logger.warning(
                "southbrook_room_capture: Anthropic HTTP %s",
                resp.status_code,
            )
            raise RuntimeError("Anthropic HTTP %s" % resp.status_code)
        return resp.json()

    # ------------------------------------------------------------------
    # Response parsing — never raises. Returns
    # {"ok": True, "estimate": <raw dict>} or
    # {"ok": False, "error": <code>, "detail": <msg>}.
    # ------------------------------------------------------------------
    @api.model
    def _parse_response(self, raw_response):
        if not isinstance(raw_response, dict):
            return {
                "ok": False, "error": "malformed_response",
                "detail": "Anthropic response is not a JSON object.",
            }

        stop_reason = raw_response.get("stop_reason")
        if stop_reason == "refusal":
            return {
                "ok": False, "error": "refused",
                "detail": "The AI declined to analyze these photos.",
            }

        content = raw_response.get("content")
        if not isinstance(content, list) or not content:
            # Covers both the empty-content refusal edge case (already
            # handled above via stop_reason, but a defensive second
            # check costs nothing) and any other malformed shape.
            return {
                "ok": False, "error": "malformed_response",
                "detail": "Anthropic response had no content.",
            }

        text = None
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                break
        if text is None:
            return {
                "ok": False, "error": "malformed_response",
                "detail": "Anthropic response had no text block.",
            }

        try:
            estimate = json.loads(text)
        except (ValueError, TypeError):
            return {
                "ok": False, "error": "malformed_response",
                "detail": "Anthropic response text was not valid JSON.",
            }
        if not isinstance(estimate, dict):
            return {
                "ok": False, "error": "malformed_response",
                "detail": "Anthropic response JSON was not an object.",
            }

        if stop_reason == "max_tokens":
            # Possibly truncated. It parsed cleanly (we're past the
            # json.loads above), so use it, but flag the truncation so
            # normalization/low-confidence handling can account for it.
            warnings = estimate.get("warnings")
            if not isinstance(warnings, list):
                warnings = []
            warnings.append(
                "Response may have been truncated (stop_reason=max_tokens)."
            )
            estimate["warnings"] = warnings
            estimate["confidence"] = min(
                self._coerce_confidence(estimate.get("confidence")),
                self._LOW_CONFIDENCE_THRESHOLD,
            )

        return {"ok": True, "estimate": estimate}

    # ------------------------------------------------------------------
    # Normalization helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _coerce_confidence(value, default=0.0):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return default
        return max(0.0, min(1.0, value))

    @staticmethod
    def _coerce_int(value):
        """Return an int, or None if `value` cannot be coerced."""
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return None

    @api.model
    def _normalize_estimate(self, estimate):
        """Coerce/skip malformed or missing fields; never raises.
        Returns the NORMALIZED estimate dict — the shape documented in
        the module docstring / __manifest__.py."""
        estimate = estimate if isinstance(estimate, dict) else {}

        layout_shape = estimate.get("layout_shape")
        if layout_shape not in LAYOUT_SHAPES:
            layout_shape = None

        ceiling_height_mm = self._coerce_int(estimate.get("ceiling_height_mm"))

        walls_out = []
        raw_walls = estimate.get("walls")
        if isinstance(raw_walls, list):
            for idx, w in enumerate(raw_walls):
                if not isinstance(w, dict):
                    continue
                length_mm = self._coerce_int(w.get("length_mm"))
                if length_mm is None or length_mm < 0:
                    continue
                name = w.get("name")
                if not isinstance(name, str) or not name.strip():
                    name = "Wall %s" % chr(ord("A") + (idx % 26))
                walls_out.append({
                    "name": name,
                    "length_mm": length_mm,
                    "confidence": self._coerce_confidence(w.get("confidence")),
                })

        n_walls = len(walls_out)
        constraints_out = []
        raw_constraints = estimate.get("constraints")
        if isinstance(raw_constraints, list):
            for c in raw_constraints:
                if not isinstance(c, dict):
                    continue
                constraint_type = c.get("constraint_type")
                if constraint_type not in CONSTRAINT_TYPES:
                    constraint_type = "other"
                wall_index = c.get("wall_index")
                if not isinstance(wall_index, int) or isinstance(wall_index, bool):
                    wall_index = self._coerce_int(wall_index)
                if not isinstance(wall_index, int) or not (0 <= wall_index < n_walls):
                    # Can't map onto a wall we kept — skip rather than
                    # guess a wall, per the "coerce/skip" contract.
                    continue
                distance_from_left_mm = self._coerce_int(
                    c.get("distance_from_left_mm")) or 0
                width_mm = self._coerce_int(c.get("width_mm")) or 0
                height_mm = self._coerce_int(c.get("height_mm")) or 0
                height_from_floor_mm = self._coerce_int(
                    c.get("height_from_floor_mm")) or 0
                constraints_out.append({
                    "constraint_type": constraint_type,
                    "wall_index": wall_index,
                    "distance_from_left_mm": max(0, distance_from_left_mm),
                    "width_mm": max(0, width_mm),
                    "height_mm": max(0, height_mm),
                    "height_from_floor_mm": max(0, height_from_floor_mm),
                    "confidence": self._coerce_confidence(c.get("confidence")),
                })

        def _string_list(value):
            if not isinstance(value, list):
                return []
            return [str(v) for v in value if isinstance(v, (str, int, float))]

        assumptions = _string_list(estimate.get("assumptions"))
        warnings = _string_list(estimate.get("warnings"))
        confidence = self._coerce_confidence(estimate.get("confidence"))

        return {
            "layout_shape": layout_shape,
            "ceiling_height_mm": ceiling_height_mm,
            "walls": walls_out,
            "constraints": constraints_out,
            "assumptions": assumptions,
            "warnings": warnings,
            "confidence": confidence,
        }

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    @api.model
    def analyze(self, images, scale_reference=None):
        """Analyze 1-5 room photos and return a normalized estimate.

        `images`: list of dicts {"data": <bytes|base64 str>,
        "mime": "image/jpeg"} (a bare base64 string per item is also
        accepted). `scale_reference`: optional dict describing a known
        measurement to help the model calibrate scale (e.g.
        {"object": "standard door", "height_mm": 2032}) — passed
        through as context text, not persisted.

        Returns:
          {"ok": True, "estimate": {...normalized...},
           "low_confidence": bool}
          or
          {"ok": False, "error": "<code>", "detail": "<msg>"}

        Never raises. Never persists anything. Never writes image
        bytes anywhere but transient in-memory variables for the
        duration of this call.
        """
        if not isinstance(images, list) or not images:
            return {
                "ok": False, "error": "invalid",
                "detail": "images must be a non-empty list.",
            }
        if len(images) > self._MAX_IMAGES:
            return {
                "ok": False, "error": "invalid",
                "detail": "At most %d images are allowed." % self._MAX_IMAGES,
            }

        decoded = []
        for idx, item in enumerate(images):
            try:
                raw, mime = self._decode_image_item(item)
            except ValueError as exc:
                return {
                    "ok": False, "error": "invalid",
                    "detail": "images[%d]: %s" % (idx, exc),
                }
            if mime not in self._ALLOWED_MIMES:
                return {
                    "ok": False, "error": "invalid",
                    "detail": "images[%d]: unsupported mime %r." % (idx, mime),
                }
            if len(raw) > self._MAX_IMAGE_BYTES:
                return {
                    "ok": False, "error": "invalid",
                    "detail": "images[%d]: exceeds the size cap." % idx,
                }
            decoded.append((raw, mime))

        try:
            image_blocks = []
            for raw, mime in decoded:
                b64, media_type = self._downscale_image(raw, mime)
                image_blocks.append({"data": b64, "media_type": media_type})
        except Exception as exc:  # noqa: BLE001 — never raise to the caller
            _logger.warning(
                "southbrook_room_capture: image downscale failed: %s", exc,
            )
            return {
                "ok": False, "error": "invalid",
                "detail": "One or more images could not be processed.",
            }

        if self._use_mock():
            # Deep-copy so a caller mutating the returned dict never
            # corrupts the class-level constant for subsequent calls.
            estimate = json.loads(json.dumps(self._MOCK_ESTIMATE))
        else:
            api_key = self._get_api_key()
            if not api_key:
                return {
                    "ok": False, "error": "not_configured",
                    "detail": "Anthropic API key is not configured.",
                }
            if not self._room_capture_consume_daily_quota():
                # Global daily spend ceiling reached (or kill-switch set).
                # A cross-worker bound the per-worker rate limiter can't give.
                return {
                    "ok": False, "error": "rate_limited",
                    "detail": "Daily analysis capacity reached; "
                              "please try again later.",
                }
            try:
                raw_response = self._call_anthropic(
                    image_blocks, api_key, scale_reference=scale_reference)
            except Exception as exc:  # noqa: BLE001 — never raise to caller
                _logger.warning(
                    "southbrook_room_capture: Anthropic call failed: %s", exc,
                )
                return {
                    "ok": False, "error": "upstream_error",
                    "detail": "The AI service is unavailable.",
                }
            parsed = self._parse_response(raw_response)
            if not parsed["ok"]:
                return parsed
            estimate = parsed["estimate"]

        normalized = self._normalize_estimate(estimate)
        low_confidence = (
            normalized["confidence"] < self._LOW_CONFIDENCE_THRESHOLD
            or not normalized["walls"]
        )
        return {
            "ok": True,
            "estimate": normalized,
            "low_confidence": low_confidence,
        }

    # ------------------------------------------------------------------
    # existingRoom mapping — see
    # addons/southbrook_estimating_website/static/src/js/
    # room_setup_wizard.esm.js (_hydrateWalls / _hydrateConstraints,
    # ~lines 634-664), which mirrors _serialize_room() in
    # addons/southbrook_estimating_website/controllers/room_api.py.
    #
    # ASSUMPTION FLAGGED FOR FRONTEND RECONCILIATION: RoomSetupWizard's
    # setup() computes `isEdit: !!existing` — i.e. it flips into EDIT
    # mode (and calls the /room/<id>/update endpoint on submit) as soon
    # as ANY truthy existingRoom object is passed, regardless of
    # whether that object carries an `id`. Passing the dict below as
    # `existingRoom` verbatim will therefore also set isEdit=True with
    # roomId=null/undefined (since we omit `id` — nothing is persisted
    # yet), which is very likely NOT the desired UX for a fresh AI
    # capture on a room that doesn't exist yet. The frontend PR wiring
    # this up needs to either (a) extend RoomSetupWizard to check
    # `existing && existing.id` for isEdit, or (b) pass this payload
    # through a NEW prop (e.g. `aiEstimate`) that pre-fills state.room /
    # state.walls / state.constraints WITHOUT flipping isEdit. This
    # backend PR cannot resolve that choice unilaterally — flagging it
    # here and in the PR description.
    # ------------------------------------------------------------------
    @api.model
    def _estimate_to_existing_room(self, estimate):
        """Map a NORMALIZED estimate (see `_normalize_estimate`) into
        the shape RoomSetupWizard's `existingRoom` prop / room_api.py's
        `_serialize_room()` produce, so the wizard's hydration helpers
        can consume it directly. `id` fields are omitted everywhere
        (nothing is persisted yet — see the assumption note above).
        Every wall/constraint carries an extra `confidence` key (and
        the top level carries `assumptions`/`warnings`/`confidence`)
        so a frontend PR can flag AI-estimated fields without a second
        round-trip; the current wizard code simply ignores unknown
        keys, so this is additive and safe.
        """
        walls = estimate.get("walls") or []
        constraints = estimate.get("constraints") or []

        constraints_by_wall = {}
        for c in constraints:
            constraints_by_wall.setdefault(c.get("wall_index"), []).append(c)

        out_walls = []
        for idx, w in enumerate(walls):
            wall_constraints = [
                {
                    "constraint_type": c["constraint_type"],
                    "distance_from_left_mm": c["distance_from_left_mm"],
                    "width_mm": c["width_mm"],
                    "height_mm": c["height_mm"],
                    "height_from_floor_mm": c["height_from_floor_mm"],
                    "notes": "",
                    "confidence": c["confidence"],
                }
                for c in constraints_by_wall.get(idx, [])
            ]
            out_walls.append({
                "name": w["name"],
                "length_mm": w["length_mm"],
                "wall_order": (idx + 1) * 10,
                "confidence": w["confidence"],
                "constraints": wall_constraints,
            })

        return {
            "name": "Main Kitchen",
            "room_type": "kitchen",
            "layout_shape": estimate.get("layout_shape"),
            "ceiling_height_mm": estimate.get("ceiling_height_mm") or 2400,
            "unit_preference": "mm",
            "walls": out_walls,
            "assumptions": estimate.get("assumptions") or [],
            "warnings": estimate.get("warnings") or [],
            "confidence": estimate.get("confidence") or 0.0,
        }

    # ------------------------------------------------------------------
    # CRM follow-up (2026-07-05). A serious customer photographing their
    # kitchen is a strong buying signal, so a TRUSTWORTHY capture lands a
    # crm.lead — linked to the order + partner, tagged, idempotent per
    # order — so a live Southbrook designer can follow up about their
    # quote. Carries the AI's room summary AND its contextual
    # observations (existing cabinet style, appliances, condition — the
    # extra "info about the customer" the estimator needs to prepare a
    # genuine quote). Never raises; a CRM failure must never break the
    # customer's capture.
    # ------------------------------------------------------------------
    @api.model
    def _capture_room_summary(self, estimate):
        shape = _SHAPE_LABELS.get(estimate.get("layout_shape"),
                                  estimate.get("layout_shape") or "unspecified")
        walls = estimate.get("walls") or []
        lines = ["Estimated room: %s, %d wall(s)." % (shape, len(walls))]
        for i, w in enumerate(walls):
            label = w.get("name") or ("Wall %s" % chr(ord("A") + (i % 26)))
            piece = "  - %s: ~%d mm" % (label, w.get("length_mm") or 0)
            cons = w.get("constraints") or []
            if cons:
                piece += " (" + ", ".join(
                    c.get("constraint_type", "?") for c in cons) + ")"
            lines.append(piece)
        ch = estimate.get("ceiling_height_mm")
        if ch:
            lines.append("  Ceiling: ~%d mm" % ch)
        conf = estimate.get("confidence")
        if conf is not None:
            lines.append("  AI confidence: %d%%" % int(round(float(conf) * 100)))
        return "\n".join(lines)

    @api.model
    def create_capture_followup_lead(self, order, estimate):
        """Create/update the ONE photo-capture follow-up lead for `order`
        (idempotent via order.sb_room_capture_lead_id). `order` is trusted
        (the controller resolved ownership) and `estimate` is a normalized
        estimate the caller already deemed trustworthy. Returns the lead
        or an empty recordset; never raises."""
        Lead = self.env["crm.lead"].sudo()
        try:
            partner = order.partner_id
            if not partner:
                return Lead.browse()

            details = [
                "*** " + _("AI PHOTO-CAPTURE LEAD") + " ***",
                _("A customer captured their kitchen from photos in the "
                  "Order Builder — a strong buying signal. Follow up about "
                  "their quote."),
                "",
                self._capture_room_summary(estimate),
            ]
            observations = [str(a) for a in (estimate.get("assumptions") or [])]
            if observations:
                details.append("")
                details.append(_("AI observations (for the estimator):"))
                details.extend("  • %s" % o for o in observations)
            details.append("")
            details.append(_("Order: %s") % (order.name or order.id))

            source = self.env.ref(
                "southbrook_room_capture.utm_source_room_capture",
                raise_if_not_found=False)
            medium = self.env.ref(
                "southbrook_room_capture.utm_medium_room_capture",
                raise_if_not_found=False)
            ai_tag = self.env.ref(
                "southbrook_agent_gateway.crm_tag_ai_agent",
                raise_if_not_found=False)

            vals = {
                "name": "📷 " + _("Kitchen photo capture — %s")
                        % (partner.name or _("customer")),
                "type": "lead",
                "partner_id": partner.id,
                "contact_name": partner.name,
                "email_from": partner.email or False,
                "phone": partner.phone or False,
                "description": plaintext2html("\n".join(details)),
                "source_id": source.id if source else False,
                "medium_id": medium.id if medium else False,
                "tag_ids": [(4, ai_tag.id)] if ai_tag else False,
            }
            existing = order.sb_room_capture_lead_id
            if existing:
                existing.sudo().write(vals)
                return existing
            lead = Lead.create(vals)
            order.sudo().write({"sb_room_capture_lead_id": lead.id})
            return lead
        except Exception as exc:  # noqa: BLE001 — CRM must never break capture
            _logger.warning(
                "southbrook_room_capture: follow-up lead creation failed "
                "for order %s: %s", getattr(order, "id", "?"), exc)
            return Lead.browse()
