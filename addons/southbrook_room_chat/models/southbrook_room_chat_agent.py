# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.room.chat.agent — conversational AI room-builder.

Runs a native Anthropic tool-calling loop (claude-sonnet-5 — the same model
southbrook_room_capture already uses for the same domain) so a customer can
describe their kitchen room in chat and have it built up as structured
geometry, one tool call at a time.

CRITICAL DESIGN INVARIANT, matching southbrook_room_capture exactly: tool
calls mutate an in-memory DRAFT dict only (persisted as JSON on
southbrook.room.chat.session) — this model NEVER creates or writes
southbrook.room / .wall / .constraint records. The draft is in the exact
shape southbrook.room.capture._estimate_to_existing_room() already produces,
so the frontend's existing AI-prefill path (RoomSetupWizard's idless-draft
detection, added by southbrook_room_capture) handles it with zero changes.

Two backends, selected by ir.config_parameter
`southbrook_room_chat.use_mock` (default "True" so cold installs and CI
never touch the network):

* Mock — runs a small fixed scripted tool-call sequence through the SAME
  real tool-execution code real conversations use, so tests exercise
  set_room_shape / add_wall / add_constraint / validate_current_draft
  without a network call.
* Real — calls the Anthropic Messages API with `tools`, looping on
  stop_reason == "tool_use" until the model produces a final text reply
  (bounded to _MAX_TOOL_ITERATIONS to cap runaway cost).
"""
import json
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

LAYOUT_SHAPES = (
    "straight", "l_shape", "u_shape", "galley", "g_shape",
    "island", "peninsula", "custom",
)
CONSTRAINT_TYPES = (
    "window", "door", "sink", "cooktop", "oven", "dishwasher",
    "rangehood", "fridge_space", "power_outlet", "structural_post",
    "other",
)

_TOOL_SCHEMAS = [
    {
        "name": "set_room_shape",
        "description": (
            "Set the overall room layout shape and/or ceiling height. "
            "Call this as soon as the user describes the room's shape "
            "(e.g. 'L-shaped', 'straight run', 'U-shaped')."),
        "input_schema": {
            "type": "object",
            "properties": {
                "layout_shape": {
                    "type": "string", "enum": list(LAYOUT_SHAPES),
                },
                "ceiling_height_mm": {"type": "integer"},
            },
        },
    },
    {
        "name": "add_wall",
        "description": (
            "Add a new wall to the room with a given length in "
            "millimetres. Call once per wall the user describes."),
        "input_schema": {
            "type": "object",
            "properties": {
                "length_mm": {"type": "integer"},
                "name": {
                    "type": "string",
                    "description": (
                        "Optional label, e.g. 'Wall A'. Auto-generated "
                        "if omitted."),
                },
            },
            "required": ["length_mm"],
        },
    },
    {
        "name": "update_wall",
        "description": (
            "Update an existing wall's length and/or name by its "
            "0-based index (the order walls were added in)."),
        "input_schema": {
            "type": "object",
            "properties": {
                "wall_index": {"type": "integer"},
                "length_mm": {"type": "integer"},
                "name": {"type": "string"},
            },
            "required": ["wall_index"],
        },
    },
    {
        "name": "remove_wall",
        "description": (
            "Remove a wall by its 0-based index. Also removes any "
            "constraints (windows/doors/etc.) on that wall."),
        "input_schema": {
            "type": "object",
            "properties": {"wall_index": {"type": "integer"}},
            "required": ["wall_index"],
        },
    },
    {
        "name": "add_constraint",
        "description": (
            "Add a door, window, sink, appliance, or other fixed "
            "feature to a wall, positioned by distance from the left "
            "edge of that wall."),
        "input_schema": {
            "type": "object",
            "properties": {
                "wall_index": {"type": "integer"},
                "constraint_type": {
                    "type": "string", "enum": list(CONSTRAINT_TYPES),
                },
                "distance_from_left_mm": {"type": "integer"},
                "width_mm": {"type": "integer"},
                "height_mm": {"type": "integer"},
                "height_from_floor_mm": {"type": "integer"},
                "notes": {"type": "string"},
            },
            "required": [
                "wall_index", "constraint_type",
                "distance_from_left_mm", "width_mm",
            ],
        },
    },
    {
        "name": "remove_constraint",
        "description": (
            "Remove a constraint from a wall by its 0-based index "
            "within that wall's own constraint list."),
        "input_schema": {
            "type": "object",
            "properties": {
                "wall_index": {"type": "integer"},
                "constraint_index": {"type": "integer"},
            },
            "required": ["wall_index", "constraint_index"],
        },
    },
    {
        "name": "validate_current_draft",
        "description": (
            "Check the current draft geometry for blocking problems "
            "(e.g. a window that doesn't fit on its wall). Call this "
            "after any material change before telling the user "
            "everything is set."),
        "input_schema": {"type": "object", "properties": {}},
    },
]

_SYSTEM_PROMPT_HEADER = (
    "You are helping a customer describe their kitchen room in a chat so "
    "it can be captured as structured geometry for a cabinet estimate. "
    "Call the provided tools to reflect exactly what the user describes: "
    "set the room shape, add/update/remove walls, and add/remove "
    "constraints (windows, doors, sinks, appliances, etc.) as they come "
    "up. All lengths are in millimetres.\n\n"
    "If something is ambiguous or you're missing a number you need (e.g. "
    "a wall length), ask a short clarifying question in plain text "
    "instead of guessing. After any material change, call "
    "validate_current_draft — if it reports errors, explain the problem "
    "in plain language and suggest a fix rather than silently leaving it "
    "broken. Keep replies short and conversational.\n\n"
    "Current draft state (JSON):\n"
)


class SouthbrookRoomChatAgent(models.AbstractModel):
    """env['southbrook.room.chat.agent'] — Claude tool-calling room builder."""
    _name = "southbrook.room.chat.agent"
    _description = "Southbrook AI Room Chat Agent"

    _ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
    _MODEL = "claude-sonnet-5"  # matches southbrook_room_capture's choice
    _TIMEOUT = 60.0
    _MAX_TOOL_ITERATIONS = 6
    _MAX_TRANSCRIPT_TURNS = 20  # bound context growth across a long chat
    _MAX_MESSAGE_CHARS = 4000

    _TOOL_FUNCS = {
        "set_room_shape": "_tool_set_room_shape",
        "add_wall": "_tool_add_wall",
        "update_wall": "_tool_update_wall",
        "remove_wall": "_tool_remove_wall",
        "add_constraint": "_tool_add_constraint",
        "remove_constraint": "_tool_remove_constraint",
        "validate_current_draft": "_tool_validate_current_draft",
    }

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    @api.model
    def _use_mock(self):
        val = self.env["ir.config_parameter"].sudo().get_param(
            "southbrook_room_chat.use_mock", "True")
        return str(val).strip().lower() in ("1", "true", "yes", "on")

    # ------------------------------------------------------------------
    # Coercion helpers (mirrors southbrook.room.capture's conventions)
    # ------------------------------------------------------------------
    @staticmethod
    def _coerce_int(value, default=None):
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return default

    # ------------------------------------------------------------------
    # Tool implementations — pure functions over the draft dict. NEVER
    # touch the ORM except _tool_validate_current_draft, which only
    # READS via the existing classmethod (no writes).
    # ------------------------------------------------------------------
    def _tool_set_room_shape(self, draft, layout_shape=None, ceiling_height_mm=None):
        if layout_shape is not None:
            if layout_shape not in LAYOUT_SHAPES:
                return {"ok": False, "error": "invalid layout_shape: %r" % layout_shape}
            draft["layout_shape"] = layout_shape
        if ceiling_height_mm is not None:
            coerced = self._coerce_int(ceiling_height_mm)
            if coerced is None or coerced <= 0:
                return {"ok": False, "error": "ceiling_height_mm must be a positive number"}
            draft["ceiling_height_mm"] = coerced
        return {
            "ok": True,
            "layout_shape": draft.get("layout_shape"),
            "ceiling_height_mm": draft.get("ceiling_height_mm"),
        }

    def _tool_add_wall(self, draft, length_mm, name=None):
        coerced = self._coerce_int(length_mm)
        if coerced is None or coerced <= 0:
            return {"ok": False, "error": "length_mm must be a positive number"}
        idx = len(draft["walls"])
        wall_name = name if isinstance(name, str) and name.strip() else (
            "Wall %s" % chr(ord("A") + (idx % 26)))
        draft["walls"].append({
            "name": wall_name,
            "length_mm": coerced,
            "wall_order": (idx + 1) * 10,
            "constraints": [],
        })
        return {"ok": True, "wall_index": idx, "name": wall_name, "length_mm": coerced}

    def _tool_update_wall(self, draft, wall_index, length_mm=None, name=None):
        walls = draft["walls"]
        idx = self._coerce_int(wall_index)
        if idx is None or not (0 <= idx < len(walls)):
            return {"ok": False, "error": "wall_index out of range"}
        if length_mm is not None:
            coerced = self._coerce_int(length_mm)
            if coerced is None or coerced <= 0:
                return {"ok": False, "error": "length_mm must be a positive number"}
            walls[idx]["length_mm"] = coerced
        if isinstance(name, str) and name.strip():
            walls[idx]["name"] = name
        return {"ok": True, "wall_index": idx}

    def _tool_remove_wall(self, draft, wall_index):
        walls = draft["walls"]
        idx = self._coerce_int(wall_index)
        if idx is None or not (0 <= idx < len(walls)):
            return {"ok": False, "error": "wall_index out of range"}
        walls.pop(idx)
        return {"ok": True}

    def _tool_add_constraint(self, draft, wall_index, constraint_type,
                              distance_from_left_mm, width_mm,
                              height_mm=None, height_from_floor_mm=None,
                              notes=None):
        walls = draft["walls"]
        idx = self._coerce_int(wall_index)
        if idx is None or not (0 <= idx < len(walls)):
            return {"ok": False, "error": "wall_index out of range"}
        if constraint_type not in CONSTRAINT_TYPES:
            return {"ok": False, "error": "invalid constraint_type: %r" % constraint_type}
        # distance_from_left_mm=0 is a legitimate value (flush against the
        # wall's left edge) — it must NOT be indistinguishable from a
        # missing/non-numeric value defaulting to 0, or a model call with
        # an unset distance silently reports success at the wrong
        # position. Reject explicitly instead of coercing to a default.
        distance = self._coerce_int(distance_from_left_mm)
        if distance is None or distance < 0:
            return {"ok": False, "error": "distance_from_left_mm must be a non-negative number"}
        width = self._coerce_int(width_mm)
        if width is None or width <= 0:
            return {"ok": False, "error": "width_mm must be a positive number"}
        if height_mm is None:
            height = 0
        else:
            height = self._coerce_int(height_mm)
            if height is None or height < 0:
                return {"ok": False, "error": "height_mm must be a non-negative number"}
        if height_from_floor_mm is None:
            height_from_floor = 0
        else:
            height_from_floor = self._coerce_int(height_from_floor_mm)
            if height_from_floor is None or height_from_floor < 0:
                return {"ok": False, "error": "height_from_floor_mm must be a non-negative number"}
        constraint = {
            "constraint_type": constraint_type,
            "distance_from_left_mm": distance,
            "width_mm": width,
            "height_mm": height,
            "height_from_floor_mm": height_from_floor,
            "notes": notes if isinstance(notes, str) else "",
        }
        walls[idx].setdefault("constraints", []).append(constraint)
        return {
            "ok": True, "wall_index": idx,
            "constraint_index": len(walls[idx]["constraints"]) - 1,
        }

    def _tool_remove_constraint(self, draft, wall_index, constraint_index):
        walls = draft["walls"]
        w_idx = self._coerce_int(wall_index)
        if w_idx is None or not (0 <= w_idx < len(walls)):
            return {"ok": False, "error": "wall_index out of range"}
        constraints = walls[w_idx].get("constraints", [])
        c_idx = self._coerce_int(constraint_index)
        if c_idx is None or not (0 <= c_idx < len(constraints)):
            return {"ok": False, "error": "constraint_index out of range"}
        constraints.pop(c_idx)
        return {"ok": True}

    def _tool_validate_current_draft(self, draft):
        walls_payload = [{"length_mm": w.get("length_mm")} for w in draft["walls"]]
        constraints_payload = []
        for wi, w in enumerate(draft["walls"]):
            for c in w.get("constraints", []):
                cp = dict(c)
                cp["wall_index"] = wi
                constraints_payload.append(cp)
        errors = self.env["southbrook.room"].validate_geometry(
            walls_payload, constraints_payload, draft.get("ceiling_height_mm"))
        return {"ok": True, "valid": not errors, "errors": errors}

    def _execute_tool(self, draft, name, args):
        if not isinstance(args, dict):
            args = {}
        method_name = self._TOOL_FUNCS.get(name)
        if method_name is None:
            return {"ok": False, "error": "unknown_tool", "tool": name}
        try:
            return getattr(self, method_name)(draft, **args)
        except TypeError as exc:
            return {"ok": False, "error": "invalid_arguments", "detail": str(exc)}

    # ------------------------------------------------------------------
    # Anthropic call
    # ------------------------------------------------------------------
    @api.model
    def _build_system_prompt(self, draft):
        return _SYSTEM_PROMPT_HEADER + json.dumps(draft)

    @api.model
    def _call_anthropic(self, system_prompt, messages, api_key):
        try:
            import httpx  # lazy import — addon installs without it (mock mode)
        except ImportError as exc:
            raise RuntimeError(
                "httpx is required to call the real Anthropic backend; "
                "install it or set southbrook_room_chat.use_mock=True"
            ) from exc

        body = {
            "model": self._MODEL,
            "max_tokens": 2048,
            "system": system_prompt,
            "messages": messages,
            "tools": _TOOL_SCHEMAS,
            # Same M2 fix southbrook_room_capture applies: claude-sonnet-5
            # runs adaptive thinking by default, which would eat into this
            # loop's max_tokens budget; {"type": "disabled"} is accepted on
            # Sonnet 5. No temperature/top_p — Sonnet 5 rejects non-default
            # sampling params.
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
            # Log status only — never the body (could echo the prompt back).
            _logger.warning(
                "southbrook_room_chat: Anthropic HTTP %s", resp.status_code)
            raise RuntimeError("Anthropic HTTP %s" % resp.status_code)
        return resp.json()

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
                "detail": "The AI declined to continue this conversation.",
            }
        content = raw_response.get("content")
        if not isinstance(content, list):
            return {
                "ok": False, "error": "malformed_response",
                "detail": "Anthropic response had no content.",
            }
        return {"ok": True, "content": content, "stop_reason": stop_reason}

    # ------------------------------------------------------------------
    # Mock backend — runs a small FIXED tool-call script through the real
    # tool-execution code (not a shortcut around it), so tests exercise
    # set_room_shape / add_wall / add_constraint / validate_current_draft
    # without any network access. Ignores the user's actual message text;
    # it demonstrates the multi-turn tool loop deterministically, it does
    # not simulate real language understanding.
    # ------------------------------------------------------------------
    _MOCK_SCRIPT = [
        {"name": "set_room_shape",
         "input": {"layout_shape": "straight", "ceiling_height_mm": 2400}},
        {"name": "add_wall", "input": {"name": "Wall A", "length_mm": 3600}},
        {"name": "add_constraint",
         "input": {"wall_index": 0, "constraint_type": "window",
                   "distance_from_left_mm": 1200, "width_mm": 900,
                   "height_mm": 1200, "height_from_floor_mm": 900}},
        {"name": "validate_current_draft", "input": {}},
    ]
    _MOCK_FINAL_TEXT = (
        "Got it — I've set up a straight wall, about 12 feet long, with a "
        "window. Let me know if that's right or if you'd like to add more!"
    )

    @api.model
    def _mock_model_response(self, step_index):
        if step_index < len(self._MOCK_SCRIPT):
            step = self._MOCK_SCRIPT[step_index]
            return {
                "stop_reason": "tool_use",
                "content": [{
                    "type": "tool_use",
                    "id": "mock_%d" % step_index,
                    "name": step["name"],
                    "input": step["input"],
                }],
            }
        return {
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": self._MOCK_FINAL_TEXT}],
        }

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    @api.model
    def handle_turn(self, order_id, message, reset=False):
        """Run one chat turn for the given order. Returns
        {"ok": True, "reply": <str>, "room": <draft dict>} or
        {"ok": False, "error": "<code>", "detail": "<msg>"}. Never raises."""
        Session = self.env["southbrook.room.chat.session"].sudo()
        session = Session.get_or_create_for_order(order_id)

        if reset:
            session.reset()
            draft = session.get_draft()
            return {
                "ok": True,
                "reply": "Starting over — tell me about your kitchen.",
                "room": draft,
            }

        if not isinstance(message, str) or not message.strip():
            return {"ok": False, "error": "invalid", "detail": "message is required."}
        if len(message) > self._MAX_MESSAGE_CHARS:
            return {
                "ok": False, "error": "invalid",
                "detail": "message exceeds the %d character cap."
                          % self._MAX_MESSAGE_CHARS,
            }

        draft = session.get_draft()
        transcript = session.get_transcript()[-self._MAX_TRANSCRIPT_TURNS:]

        use_mock = self._use_mock()
        api_key = None
        if not use_mock:
            api_key = self.env["southbrook.room.capture"]._get_api_key()
            if not api_key:
                return {
                    "ok": False, "error": "not_configured",
                    "detail": "Anthropic API key is not configured.",
                }

        messages = [{"role": t["role"], "content": t["content"]} for t in transcript]
        messages.append({"role": "user", "content": message})

        final_text = ""
        iterations = 0
        mock_step = 0
        while iterations < self._MAX_TOOL_ITERATIONS:
            iterations += 1
            if use_mock:
                raw_response = self._mock_model_response(mock_step)
            else:
                system_prompt = self._build_system_prompt(draft)
                try:
                    raw_response = self._call_anthropic(system_prompt, messages, api_key)
                except Exception as exc:  # noqa: BLE001 — never raise to caller
                    _logger.warning(
                        "southbrook_room_chat: Anthropic call failed: %s", exc)
                    return {
                        "ok": False, "error": "upstream_error",
                        "detail": "The AI service is unavailable.",
                    }

            parsed = self._parse_response(raw_response)
            if not parsed["ok"]:
                return parsed

            content = parsed["content"]
            stop_reason = parsed["stop_reason"]
            text_parts = [
                b.get("text", "") for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            ]
            if text_parts:
                final_text = "\n".join(text_parts)

            if stop_reason != "tool_use":
                break

            tool_use_blocks = [
                b for b in content
                if isinstance(b, dict) and b.get("type") == "tool_use"
            ]
            if not use_mock:
                messages.append({"role": "assistant", "content": content})
            tool_results = []
            for block in tool_use_blocks:
                result = self._execute_tool(
                    draft, block.get("name"), block.get("input") or {})
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.get("id"),
                    "content": json.dumps(result),
                })
            if not use_mock:
                messages.append({"role": "user", "content": tool_results})
            mock_step += 1
        else:
            if not final_text:
                final_text = (
                    "I've made some updates — let me know if you'd like "
                    "to adjust anything."
                )

        session.set_draft(draft)
        session.append_turn("user", message)
        session.append_turn("assistant", final_text)

        return {"ok": True, "reply": final_text, "room": draft}
