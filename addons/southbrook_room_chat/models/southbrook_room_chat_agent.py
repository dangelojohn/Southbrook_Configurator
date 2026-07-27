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

from odoo import api, fields, models

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
    # ------------------------------------------------------------------
    # v2 (2026-07-05) — customer profile gathering + service offerings +
    # CRM hand-off, mirroring the AI-agent gateway's abilities so a live
    # Southbrook designer can follow up about the customer's quote.
    # ------------------------------------------------------------------
    {
        "name": "set_customer_contact",
        "description": (
            "Record the customer's contact details as they share them. "
            "Call whenever the customer gives a name, email, or phone. "
            "Provide only the field(s) just mentioned; others are kept."),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
            },
        },
    },
    {
        "name": "set_customer_address",
        "description": (
            "Record the customer's project/site address (helps Southbrook "
            "confirm service area and prepare the quote). All parts "
            "optional; provide only what was mentioned."),
        "input_schema": {
            "type": "object",
            "properties": {
                "street": {"type": "string"},
                "city": {"type": "string"},
                "state": {"type": "string",
                          "description": "state/province name or code"},
                "zip": {"type": "string"},
                "country": {"type": "string"},
            },
        },
    },
    {
        "name": "set_project_details",
        "description": (
            "Record what the customer wants: room type, budget range, "
            "timeline, and any free-text notes about the project. "
            "Provide only the field(s) just mentioned."),
        "input_schema": {
            "type": "object",
            "properties": {
                "room_type": {"type": "string"},
                "budget_range": {"type": "string"},
                "timeline": {"type": "string"},
                "notes": {"type": "string"},
            },
        },
    },
    {
        "name": "list_cabinet_offerings",
        "description": (
            "Look up Southbrook's actual cabinet catalog — families, "
            "series, dimensions and retail list prices — to answer the "
            "customer's questions about what Southbrook offers and rough "
            "pricing. Read-only."),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "save_lead_for_followup",
        "description": (
            "Save the gathered customer + project details to Southbrook's "
            "CRM so a live designer can follow up about the quote. Call "
            "this ONCE the customer has agreed to be contacted and you "
            "have at least their name and a valid email. If required "
            "details are missing it returns what's still needed — ask for "
            "those and call again."),
        "input_schema": {"type": "object", "properties": {}},
    },
]

_SYSTEM_PROMPT_HEADER = (
    "You are Southbrook Cabinetry's friendly kitchen-design assistant, "
    "helping a customer over chat. You have TWO jobs in one natural "
    "conversation:\n\n"
    "1) BUILD THE ROOM. Turn what the customer says into structured "
    "geometry by calling the room tools (set_room_shape; add_wall / "
    "update_wall / remove_wall; add_constraint / remove_constraint). "
    "Reflect exactly what they describe — don't invent measurements.\n"
    "   • All tool lengths are in MILLIMETRES. Convert the customer's "
    "units yourself before calling a tool: feet→mm ×304.8, inches→mm "
    "×25.4 (e.g. \"12 ft\"→3658; \"10 ft 6 in\"→3200; \"118 in\"→2997). "
    "Never pass feet or inches to a tool.\n"
    "   • Map the shape to the closest of: straight, l_shape, u_shape, "
    "galley, g_shape, island, peninsula, custom. An \"L-shaped\" kitchen "
    "is l_shape with 2 walls; a \"U\" is u_shape with 3; a galley is 2 "
    "facing walls. Add one wall per physical wall the customer mentions, "
    "in order.\n"
    "   • If a number you need is missing or ambiguous (a wall length, "
    "which wall a window is on), ask ONE short, specific question rather "
    "than guessing. Don't repeat a question already answered.\n"
    "   • After any material change call validate_current_draft; if it "
    "reports errors, explain the issue plainly and propose a fix.\n\n"
    "2) GATHER THE CUSTOMER'S DETAILS so a live Southbrook designer can "
    "follow up with their quote. Woven naturally into the conversation "
    "(never an interrogation), collect their name, email, phone, project "
    "address, and what they want — budget range, timeline, room type — "
    "and record each with set_customer_contact / set_customer_address / "
    "set_project_details AS SOON as they mention it. Explain WHY once, "
    "warmly: \"so one of our designers can call you with your quote.\" "
    "Always get explicit agreement to be contacted before saving. If the "
    "customer asks what Southbrook makes or what things cost, call "
    "list_cabinet_offerings and answer from the real catalog. When you "
    "have at least a name + valid email and the customer has agreed to "
    "be contacted, call save_lead_for_followup; if it says details are "
    "missing, ask for exactly those and call it again. Never fabricate a "
    "contact detail — only record what the customer actually gives.\n\n"
    "Keep every reply short, warm and conversational.\n\n"
    "Current room draft (JSON):\n"
)


class SouthbrookRoomChatAgent(models.AbstractModel):
    """env['southbrook.room.chat.agent'] — Claude tool-calling room builder."""
    _name = "southbrook.room.chat.agent"
    _description = "Southbrook AI Room Chat Agent"

    _ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
    _MODEL = "claude-sonnet-5"  # matches southbrook_room_capture's choice
    _TIMEOUT = 60.0
    # A single rich turn can fan out into many tool calls (shape + several
    # walls + constraints + validate + contact/address/project + a catalog
    # lookup + save_lead), so allow a generous loop while still bounding
    # runaway cost. Raised from 6 in v2.
    _MAX_TOOL_ITERATIONS = 12
    _MAX_TRANSCRIPT_TURNS = 20  # bound context growth across a long chat
    _MAX_MESSAGE_CHARS = 4000

    # (method_name, kind). kind selects the primary arg passed to the
    # tool: "draft" → the room draft dict; "customer" → the gathered
    # customer profile dict; "ctx" → the full turn context (draft +
    # customer + session), for tools that need the ORM / order.
    _TOOL_SPECS = {
        "set_room_shape": ("_tool_set_room_shape", "draft"),
        "add_wall": ("_tool_add_wall", "draft"),
        "update_wall": ("_tool_update_wall", "draft"),
        "remove_wall": ("_tool_remove_wall", "draft"),
        "add_constraint": ("_tool_add_constraint", "draft"),
        "remove_constraint": ("_tool_remove_constraint", "draft"),
        "validate_current_draft": ("_tool_validate_current_draft", "draft"),
        "set_customer_contact": ("_tool_set_customer_contact", "customer"),
        "set_customer_address": ("_tool_set_customer_address", "customer"),
        "set_project_details": ("_tool_set_project_details", "customer"),
        "list_cabinet_offerings": ("_tool_list_cabinet_offerings", "ctx"),
        "save_lead_for_followup": ("_tool_save_lead_for_followup", "ctx"),
    }

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    @api.model
    def _use_mock(self):
        val = self.env["ir.config_parameter"].sudo().get_param(
            "southbrook_room_chat.use_mock", "True")
        return str(val).strip().lower() in ("1", "true", "yes", "on")

    @api.model
    def _daily_cap(self):
        """Global ceiling on real (non-mock) Anthropic calls per day.
        ir.config_parameter southbrook_room_chat.max_daily_calls
        (default 1000). 0 acts as a hard kill-switch — no real call at all.

        The controller's rate limiter is PER WORKER (in-process _RATE_BUCKETS)
        and cannot see sibling workers, and each chat turn fans out up to
        _MAX_TOOL_ITERATIONS real API calls — so a paid-API spend ceiling that
        every worker shares is enforced here, counted per real call. Mirrors
        southbrook_room_capture._room_capture_daily_cap /
        southbrook_agent_gateway's per-day cap (this module reused the shared
        API key but originally dropped the cap — see REVIEW_REPORT H1)."""
        ICP = self.env["ir.config_parameter"].sudo()
        try:
            return int(ICP.get_param(
                "southbrook_room_chat.max_daily_calls", "1000"))
        except (TypeError, ValueError):
            return 1000

    @api.model
    def _consume_daily_quota(self):
        """Increment today's real-call counter; return True only if within the
        global daily cap. Best-effort: the config-param read-modify-write can
        under-count under heavy concurrency, but as a COST ceiling an
        approximate bound is acceptable (exact accounting needs a shared
        counter store — see REVIEW_REPORT R1). 0 = kill-switch."""
        cap = self._daily_cap()
        if cap <= 0:
            return False
        ICP = self.env["ir.config_parameter"].sudo()
        today = fields.Date.to_string(fields.Date.context_today(self))
        stamp = ICP.get_param("southbrook_room_chat.daily_call_date", "")
        if stamp != today:
            count = 0
        else:
            try:
                count = int(ICP.get_param(
                    "southbrook_room_chat.daily_call_count", "0"))
            except (TypeError, ValueError):
                count = 0
        if count >= cap:
            return False
        ICP.set_param("southbrook_room_chat.daily_call_date", today)
        ICP.set_param(
            "southbrook_room_chat.daily_call_count", str(count + 1))
        return True

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

    # ------------------------------------------------------------------
    # v2 — customer profile tools. Mutate the `customer` dict in place;
    # never touch the ORM (save_lead_for_followup is the one write path).
    # ------------------------------------------------------------------
    @staticmethod
    def _clean_str(value, max_len):
        if not isinstance(value, str):
            return ""
        return value.replace("\r", " ").replace("\n", " ").strip()[:max_len]

    def _missing_contact(self, customer):
        """List the still-required fields for a CRM follow-up (name +
        valid email), so the model knows exactly what to ask for."""
        missing = []
        if not customer.get("name"):
            missing.append("name")
        if not customer.get("email"):
            missing.append("email")
        return missing

    def _tool_set_customer_contact(self, customer, name=None, email=None,
                                    phone=None):
        captured = {}
        if name is not None:
            cleaned = self._clean_str(name, 120)
            if len(cleaned) >= 2:
                customer["name"] = cleaned
                captured["name"] = cleaned
        if email is not None:
            from odoo.tools import email_normalize
            normalized = email_normalize(self._clean_str(email, 254))
            if not normalized:
                return {"ok": False,
                        "error": "That email doesn't look valid — could "
                                 "you double-check it?"}
            customer["email"] = normalized
            captured["email"] = normalized
        if phone is not None:
            raw = self._clean_str(phone, 40)
            if raw:
                formatted = self.env["southbrook.agent.inquiry"].sudo() \
                    ._format_phone(raw)
                if not formatted:
                    return {"ok": False,
                            "error": "That phone number couldn't be "
                                     "validated — could you confirm it?"}
                customer["phone"] = formatted
                captured["phone"] = formatted
        return {"ok": True, "captured": captured,
                "still_needed": self._missing_contact(customer)}

    def _tool_set_customer_address(self, customer, street=None, city=None,
                                    state=None, zip=None, country=None):
        for key, val in (("street", street), ("city", city),
                         ("state_name", state), ("zip_code", zip),
                         ("country_name", country)):
            if val is not None:
                customer[key] = self._clean_str(val, 200)
        return {"ok": True}

    def _tool_set_project_details(self, customer, room_type=None,
                                   budget_range=None, timeline=None,
                                   notes=None):
        if room_type is not None:
            customer["room_type"] = self._clean_str(room_type, 200)
        if budget_range is not None:
            customer["budget_range"] = self._clean_str(budget_range, 200)
        if timeline is not None:
            customer["timeline"] = self._clean_str(timeline, 200)
        if notes is not None:
            customer["project_notes"] = self._clean_str(notes, 2000)
        return {"ok": True}

    def _tool_list_cabinet_offerings(self, ctx):
        """Compact catalog summary for the model to answer 'what do you
        offer / roughly what does it cost'. Reuses the SAME source of
        truth as the AI-agent gateway's /offerings endpoint."""
        catalog = self.env["southbrook.agent.inquiry"].sudo() \
            .offerings_catalog()
        by_cat = {}
        for c in catalog.get("cabinets", []):
            by_cat.setdefault(c["category"], []).append(c["list_price"])
        families = [{
            "category": cat,
            "count": len(prices),
            "price_from": min(prices) if prices else None,
            "price_to": max(prices) if prices else None,
        } for cat, prices in sorted(by_cat.items())]
        return {
            "ok": True,
            "currency": catalog.get("currency"),
            "series": catalog.get("series"),
            "families": families,
            "pricing_note": catalog.get("pricing_note"),
            "standard_lead_time_weeks": catalog.get(
                "standard_lead_time_weeks"),
        }

    def _tool_save_lead_for_followup(self, ctx):
        """Land the gathered profile in Contacts + CRM so a live designer
        follows up. Requires name + valid email; returns what's missing
        otherwise. Idempotent per session (updates its own lead)."""
        customer = ctx["customer"]
        missing = self._missing_contact(customer)
        if missing:
            return {"ok": False, "error": "missing_details",
                    "still_needed": missing,
                    "detail": "Ask the customer for: %s" % ", ".join(missing)}
        session = ctx["session"]
        lead = session._save_followup_lead(customer, ctx["draft"])
        return {
            "ok": True,
            "lead_reference": lead.id,
            "detail": ("Saved. A Southbrook designer will follow up about "
                       "the quote."),
        }

    def _execute_tool(self, ctx, name, args):
        if not isinstance(args, dict):
            args = {}
        spec = self._TOOL_SPECS.get(name)
        if spec is None:
            return {"ok": False, "error": "unknown_tool", "tool": name}
        method_name, kind = spec
        if kind == "draft":
            primary = ctx["draft"]
        elif kind == "customer":
            primary = ctx["customer"]
        else:  # "ctx" — the whole turn context
            primary = ctx
        try:
            return getattr(self, method_name)(primary, **args)
        except TypeError as exc:
            return {"ok": False, "error": "invalid_arguments", "detail": str(exc)}

    # ------------------------------------------------------------------
    # Anthropic call
    # ------------------------------------------------------------------
    @api.model
    def _build_system_prompt(self, draft, customer=None):
        prompt = _SYSTEM_PROMPT_HEADER + json.dumps(draft)
        if customer is not None:
            prompt += (
                "\n\nCustomer details gathered so far (JSON — don't re-ask "
                "for fields already filled):\n" + json.dumps(customer))
        return prompt

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
    # Exercises BOTH the room tools and the v2 customer-gathering /
    # offerings tools through the real executor. Deliberately does NOT
    # include save_lead_for_followup — that is the one tool with an ORM
    # write (a real crm.lead), and mock mode is the production default, so
    # scripting it would spam CRM with demo leads on every mock turn.
    _MOCK_SCRIPT = [
        {"name": "set_room_shape",
         "input": {"layout_shape": "straight", "ceiling_height_mm": 2400}},
        {"name": "add_wall", "input": {"name": "Wall A", "length_mm": 3600}},
        {"name": "add_constraint",
         "input": {"wall_index": 0, "constraint_type": "window",
                   "distance_from_left_mm": 1200, "width_mm": 900,
                   "height_mm": 1200, "height_from_floor_mm": 900}},
        {"name": "validate_current_draft", "input": {}},
        {"name": "list_cabinet_offerings", "input": {}},
        {"name": "set_customer_contact",
         "input": {"name": "Demo Customer",
                   "email": "demo.customer@example.com"}},
        {"name": "set_project_details",
         "input": {"room_type": "kitchen", "budget_range": "$10k-$15k",
                   "timeline": "next few months"}},
    ]
    _MOCK_FINAL_TEXT = (
        "Got it — I've set up a straight wall, about 12 feet long, with a "
        "window, and noted your details. A Southbrook designer can follow "
        "up whenever you're ready. Let me know if you'd like to add more!"
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
    # Internal entry point — controller-only, NOT RPC-dispatchable
    # ------------------------------------------------------------------
    # Deliberately private (leading underscore): this method sudo-reads and
    # sudo-writes the session for `order_id` WITHOUT re-checking ownership,
    # trusting its sole caller (controllers/main.py) to have already resolved
    # the order against the acting user and enforced the rate limit. A public
    # name would be call_kw-dispatchable, letting any authenticated portal user
    # invoke it against an arbitrary order_id and bypass both gates. See
    # REVIEW_REPORT H2.
    @api.model
    def _handle_turn(self, order_id, message, reset=False):
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
                "customer": session.get_customer(),
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
        customer = session.get_customer()
        # Full turn context handed to tools (draft tools read ctx["draft"],
        # customer tools ctx["customer"], CRM/offerings tools the whole ctx).
        ctx = {"draft": draft, "customer": customer, "session": session}
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
                # Global daily spend ceiling / kill-switch, counted per REAL
                # call (each turn can fan out up to _MAX_TOOL_ITERATIONS of
                # them). Cross-worker; the controller limiter is per-worker.
                if not self._consume_daily_quota():
                    if iterations == 1:
                        return {
                            "ok": False, "error": "rate_limited",
                            "detail": "Daily AI capacity reached; "
                                      "please try again later.",
                        }
                    # Mid-turn: stop looping, keep the draft built so far.
                    if not final_text:
                        final_text = (
                            "I've saved your progress. Our AI planner is at "
                            "capacity right now — please continue shortly."
                        )
                    break
                system_prompt = self._build_system_prompt(draft, customer)
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
                    ctx, block.get("name"), block.get("input") or {})
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

        # Persist BOTH the room draft and the gathered customer profile
        # (tools mutated the dicts in ctx in place).
        session.set_draft(draft)
        session.set_customer(customer)
        session.append_turn("user", message)
        session.append_turn("assistant", final_text)

        return {
            "ok": True,
            "reply": final_text,
            "room": draft,
            "customer": customer,
            # True once save_lead_for_followup has landed a CRM lead this
            # session — lets the frontend reflect "we'll be in touch".
            "lead_saved": bool(session.lead_id),
        }
