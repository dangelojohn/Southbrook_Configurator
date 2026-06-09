# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.gemini.client — the caller, validator, and lander.

Implements docs/api_contracts/gemini_odoo_contract.md. Two backends:
  real Gemini (when ir.config_parameter gemini.use_mock != 'True')
  mock (canned response, used by tests and offline dev).

Schema version pinned: southbrook.gemini.room_analysis.v1
"""
import base64
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


SCHEMA_VERSION = "southbrook.gemini.room_analysis.v1"
DEFAULT_PROMPT_CODE = "default_v1"

ALLOWED_APPLIANCE_KINDS = frozenset({
    "stove", "fridge", "dishwasher", "sink", "microwave",
    "oven_wall", "hood", "other",
})

PLAUSIBLE_RANGES = {
    "wall_length": (300, 15000),
    "appliance":   (100, 2000),
    "ceiling":     (1500, 4500),
}


class SouthbrookGeminiClient(models.AbstractModel):
    """env['southbrook.gemini.client'] — Gemini caller + validator."""
    _name = "southbrook.gemini.client"
    _description = "Southbrook Gemini Client"

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    @api.model
    def analyze(self, image_bytes: bytes,
                prompt_template_code: str = DEFAULT_PROMPT_CODE) -> dict:
        """Run image through Gemini (or the mock), return a validated
        payload conforming to SCHEMA_VERSION. Raises UserError on
        unrecoverable failures."""
        Template = self.env["sb.gemini.prompt.template"]
        template = Template.get_by_code(prompt_template_code)

        param = self.env["ir.config_parameter"].sudo()
        use_mock = param.get_param("gemini.use_mock", "True").lower() == "true"

        if use_mock:
            raw = self._mock_response(image_bytes)
        else:
            api_key = param.get_param("gemini.api_key", "")
            if not api_key:
                raise UserError(_(
                    "Gemini API key is not configured. Set the "
                    "`gemini.api_key` ir.config_parameter or flip "
                    "`gemini.use_mock` to True for offline development."
                ))
            raw = self._call_gemini_real(image_bytes, template, api_key)

        validated = self._validate(raw)
        # Stamp the image_hash so the lander can dedupe.
        validated["image_hash"] = "sha256:" + hashlib.sha256(image_bytes).hexdigest()
        return validated

    # ------------------------------------------------------------------
    # Mock backend — canned payload, used by tests + offline dev
    # ------------------------------------------------------------------
    @api.model
    def _mock_response(self, image_bytes: bytes) -> dict:
        """Return a canned payload that passes validation. The image
        contents are NOT inspected; the mock simulates Gemini analysing
        a typical signature-series kitchen with one stove + a sink."""
        return {
            "schema": SCHEMA_VERSION,
            "model": "mock-gemini",
            "ts": "2026-06-09T18:00:00Z",
            "image_hash": "",  # caller fills this in
            "room": {
                "sink_detected": True,
                "window_count": 1,
                "room_door_count": 1,
                "floor_area_m2_approx": 18.5,
                "ceiling_height_mm_approx": 2400,
                "wall_segments": [
                    {"id": "wall_north", "length_mm_approx": 4200,
                     "has_windows": [True], "has_doors": [False]},
                    {"id": "wall_east",  "length_mm_approx": 2800,
                     "has_windows": [False], "has_doors": [True]},
                ],
            },
            "appliances": [
                {"kind": "stove", "label": "Gas range, 30\"",
                 "wall_segment_id": "wall_north",
                 "position_pct_along_wall": 0.62,
                 "width_mm_approx": 762, "height_mm_approx": 914,
                 "depth_mm_approx": 610, "requires_clearance_mm": 30,
                 "confidence": 0.86},
                {"kind": "sink", "label": "Single-basin sink",
                 "wall_segment_id": "wall_north",
                 "position_pct_along_wall": 0.20,
                 "width_mm_approx": 762, "height_mm_approx": 220,
                 "depth_mm_approx": 460, "requires_clearance_mm": 0,
                 "confidence": 0.92},
            ],
            "dimensions_confidence": {
                "wall_lengths": 0.55,
                "appliance_widths": 0.78,
                "ceiling_height": 0.40,
            },
            "model_warnings": [],
        }

    # ------------------------------------------------------------------
    # Real Gemini backend — retries per G3 §6
    # ------------------------------------------------------------------
    @api.model
    def _call_gemini_real(self, image_bytes, template, api_key: str) -> dict:
        """POST image + prompt; retry transient failures with backoff."""
        try:
            import httpx  # imported lazily so the addon installs without it
        except ImportError as exc:
            raise UserError(_(
                "The httpx Python package is required to call the real "
                "Gemini backend. `pip install httpx` in the Odoo container, "
                "or set ir.config_parameter `gemini.use_mock = True`."
            )) from exc

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{template.model}:generateContent?key={api_key}"
        )
        body = {
            "contents": [{
                "parts": [
                    {"inline_data": {"mime_type": "image/jpeg",
                                     "data": base64.b64encode(image_bytes).decode()}},
                    {"text": template.body},
                ],
            }],
            "generationConfig": template.to_generation_config(),
        }

        backoffs = [0.25, 1.0, 4.0]
        last_exc = None
        for attempt, wait in enumerate([0] + backoffs):
            if wait:
                time.sleep(wait)
            try:
                resp = httpx.post(url, json=body, timeout=60.0)
                if resp.status_code in (401, 403):
                    raise UserError(_("Gemini auth failed (HTTP %s).") % resp.status_code)
                if resp.status_code == 429:
                    # 1 retry only on quota
                    if attempt == 0:
                        retry_after = float(resp.headers.get("Retry-After", 5))
                        time.sleep(retry_after)
                        continue
                    raise UserError(_("Gemini quota exhausted."))
                resp.raise_for_status()
                text = (resp.json()["candidates"][0]["content"]
                            ["parts"][0]["text"])
                return json.loads(text)
            except (httpx.ConnectError, httpx.ReadTimeout) as exc:
                last_exc = exc
                _logger.warning("Gemini transient error attempt=%s: %s",
                                attempt, exc)
        raise UserError(_("Gemini unavailable: %s") % last_exc)

    # ------------------------------------------------------------------
    # Validator — enforces G3 §4.1 rules
    # ------------------------------------------------------------------
    @api.model
    def _validate(self, payload: Any) -> dict:
        """Validate per G3 §4.1. Mutates the payload to clamp ranges +
        coerce unknown enums, returns the (mutated) dict. Raises
        UserError on rejections."""
        if not isinstance(payload, dict):
            raise UserError(_("Gemini response is not a JSON object."))
        if payload.get("schema") != SCHEMA_VERSION:
            raise UserError(_(
                "Gemini response schema mismatch: expected %s, got %s"
            ) % (SCHEMA_VERSION, payload.get("schema")))

        warnings = list(payload.get("model_warnings") or [])

        room = payload.get("room") or {}
        # Plausibility bounds on ceiling.
        ch = room.get("ceiling_height_mm_approx")
        if ch is not None:
            lo, hi = PLAUSIBLE_RANGES["ceiling"]
            if not (lo <= ch <= hi):
                warnings.append(f"ceiling_height_mm_approx={ch} out of range — nulled")
                room["ceiling_height_mm_approx"] = None

        # Wall segment IDs collected for the orphan-reference check.
        wall_ids = set()
        for seg in room.get("wall_segments") or []:
            wall_ids.add(seg.get("id"))
            wl = seg.get("length_mm_approx")
            if wl is not None:
                lo, hi = PLAUSIBLE_RANGES["wall_length"]
                if not (lo <= wl <= hi):
                    warnings.append(
                        f"wall {seg.get('id')} length={wl} out of range — nulled"
                    )
                    seg["length_mm_approx"] = None

        for app in payload.get("appliances") or []:
            kind = app.get("kind")
            if kind not in ALLOWED_APPLIANCE_KINDS:
                warnings.append(f"unknown appliance kind {kind!r} coerced to 'other'")
                app["kind"] = "other"
                app["notes"] = (app.get("notes") or "") + f" original_kind={kind}"

            ws_id = app.get("wall_segment_id")
            if ws_id is not None and ws_id not in wall_ids:
                raise UserError(_(
                    "Gemini response references orphan wall_segment_id "
                    "%r — analysis rejected."
                ) % ws_id)

            for field in ("width_mm_approx", "height_mm_approx", "depth_mm_approx"):
                val = app.get(field)
                if val is not None:
                    lo, hi = PLAUSIBLE_RANGES["appliance"]
                    if not (lo <= val <= hi):
                        warnings.append(
                            f"appliance {app.get('label')} {field}={val} "
                            "out of range — nulled"
                        )
                        app[field] = None

            conf = app.get("confidence")
            if conf is not None and not (0.0 <= conf <= 1.0):
                warnings.append(
                    f"appliance confidence={conf} out of [0,1] — clamped"
                )
                app["confidence"] = max(0.0, min(1.0, conf))

        dc = payload.get("dimensions_confidence") or {}
        for k, v in list(dc.items()):
            if v is not None and not (0.0 <= v <= 1.0):
                warnings.append(f"dimensions_confidence[{k}]={v} clamped")
                dc[k] = max(0.0, min(1.0, v))

        payload["model_warnings"] = warnings
        return payload
