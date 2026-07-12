# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for southbrook_room_chat — conversational AI room-builder backend.

Covers:
  * southbrook.room.chat.session — get-or-create, draft/transcript
    round-trip, reset.
  * southbrook.room.chat.agent (AbstractModel) — mock tool-loop
    short-circuit (exercises the REAL tool-execution code, not a
    shortcut around it), individual tool validation, the real
    (non-mock) tool_use loop via a monkeypatched `_call_anthropic`,
    malformed/failed/refused AI-call recovery, geometry-validator
    gating, no southbrook.room/.wall/.constraint side effects.
  * controllers/main.py — the single JSON-RPC route: authenticated
    access, ownership rejection, input validation, rate limiting,
    no southbrook.room side effects.

Follows the `stubbed_request` pattern established in
southbrook_room_capture/tests/test_room_capture.py: swap the `request`
LocalProxy in EVERY controller module whose code path is exercised.
`_southbrook_resolve_order`'s `request` binding lives in
southbrook_estimating_website.controllers.main (the mixin's home module),
not in this addon's own controller module, so both must be swapped.

All external AI calls are mocked:
  * Model-layer tests either rely on `use_mock=True` (the addon default
    — never touches the network) or monkeypatch
    `southbrook.room.chat.agent._call_anthropic` to return a canned raw
    Anthropic response dict.
  * Controller tests exercise the mock tool-loop short-circuit only
    (use_mock stays at its default True).

Run with:
    odoo --no-http --test-enable -u southbrook_room_chat \\
        -d <db> --stop-after-init --test-tags=southbrook_room_chat
"""
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.southbrook_room_chat.controllers import main as ctrl_chat
from odoo.addons.southbrook_estimating_website.controllers import (
    main as ctrl_main,
)


@contextmanager
def stubbed_request(env, user=None):
    """Swap `request` in both controller modules for the duration of the
    with-block. Mirrors southbrook_room_capture/tests/test_room_capture.py's
    helper."""
    saved_chat = ctrl_chat.request
    saved_main = ctrl_main.request
    mock = MagicMock()
    mock.env = env if user is None else env(user=user.id)
    mock.session = {}
    mock.params = {}
    ctrl_chat.request = mock
    ctrl_main.request = mock
    try:
        yield mock
    finally:
        ctrl_chat.request = saved_chat
        ctrl_main.request = saved_main


@tagged("post_install", "-at_install", "southbrook", "southbrook_room_chat")
class TestRoomChatSession(TransactionCase):
    """Direct tests of the southbrook.room.chat.session model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Session = cls.env["southbrook.room.chat.session"]
        cls.partner = cls.env["res.partner"].create({
            "name": "Test Customer Room Chat Session",
            "email": "test_room_chat_session@southbrook.test",
        })
        cls.order = cls.env["sale.order"].create({"partner_id": cls.partner.id})

    def test_get_or_create_creates_session(self):
        before = self.Session.search_count([("order_id", "=", self.order.id)])
        self.assertEqual(before, 0)
        session = self.Session.get_or_create_for_order(self.order.id)
        self.assertTrue(session)
        self.assertEqual(session.order_id.id, self.order.id)

    def test_get_or_create_returns_existing_singleton(self):
        first = self.Session.get_or_create_for_order(self.order.id)
        second = self.Session.get_or_create_for_order(self.order.id)
        self.assertEqual(first.id, second.id)

    def test_blank_draft_shape(self):
        session = self.Session.get_or_create_for_order(self.order.id)
        draft = session.get_draft()
        for key in (
            "name", "room_type", "layout_shape", "ceiling_height_mm",
            "unit_preference", "walls", "assumptions", "warnings",
            "confidence",
        ):
            self.assertIn(key, draft)
        self.assertEqual(draft["walls"], [])
        self.assertIsNone(draft["layout_shape"])

    def test_set_and_get_draft_roundtrip(self):
        session = self.Session.get_or_create_for_order(self.order.id)
        draft = session.get_draft()
        draft["layout_shape"] = "l_shape"
        draft["walls"].append({"name": "Wall A", "length_mm": 3000, "wall_order": 10, "constraints": []})
        session.set_draft(draft)
        reloaded = session.get_draft()
        self.assertEqual(reloaded["layout_shape"], "l_shape")
        self.assertEqual(len(reloaded["walls"]), 1)

    def test_append_turn_and_get_transcript(self):
        session = self.Session.get_or_create_for_order(self.order.id)
        session.append_turn("user", "It's an L-shaped kitchen.")
        session.append_turn("assistant", "Got it, one wall at a time.")
        transcript = session.get_transcript()
        self.assertEqual(len(transcript), 2)
        self.assertEqual(transcript[0]["role"], "user")
        self.assertEqual(transcript[1]["role"], "assistant")

    def test_reset_clears_draft_and_transcript(self):
        session = self.Session.get_or_create_for_order(self.order.id)
        draft = session.get_draft()
        draft["layout_shape"] = "u_shape"
        session.set_draft(draft)
        session.append_turn("user", "hello")
        session.reset()
        self.assertEqual(session.get_transcript(), [])
        self.assertIsNone(session.get_draft()["layout_shape"])

    def test_unique_constraint_rejects_duplicate_order_session(self):
        """Regression: the UNIQUE(order_id) constraint must exist so a
        raced create() can be caught, not silently produce two rows."""
        order2 = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.Session.create({"order_id": order2.id})
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.Session.create({"order_id": order2.id})

    def test_get_or_create_race_safe(self):
        """Regression: two callers racing for the same order must not
        both succeed in creating a session — the loser's create() must
        hit the unique constraint and be caught, resolving to the
        winner's row instead of raising or stranding an orphan."""
        order2 = self.env["sale.order"].create({"partner_id": self.partner.id})
        orig_search = type(self.Session).search
        state = {"seeded": False}

        def racy_search(rec_self, domain, **kw):
            if not state["seeded"]:
                state["seeded"] = True
                # A "concurrent" request wins the race between our
                # search-miss and our own create() call below.
                self.env["southbrook.room.chat.session"].sudo().create(
                    {"order_id": order2.id})
                return rec_self.browse([])
            return orig_search(rec_self, domain, **kw)

        with patch.object(type(self.Session), "search", racy_search):
            session = self.Session.get_or_create_for_order(order2.id)

        self.assertTrue(session)
        self.assertEqual(
            self.Session.search_count([("order_id", "=", order2.id)]), 1)


@tagged("post_install", "-at_install", "southbrook", "southbrook_room_chat")
class TestRoomChatAgentModel(TransactionCase):
    """Direct tests of the southbrook.room.chat.agent AbstractModel."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Agent = cls.env["southbrook.room.chat.agent"]
        cls.partner = cls.env["res.partner"].create({
            "name": "Test Customer Room Chat Agent",
            "email": "test_room_chat_agent@southbrook.test",
        })
        cls.order = cls.env["sale.order"].create({"partner_id": cls.partner.id})

    def _set_real_backend(self):
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("southbrook_room_chat.use_mock", "False")
        ICP.set_param(
            "southbrook_room_capture.anthropic_api_key", "sk-test-dummy")

    # ------------------------------------------------------------------
    # Mock mode — exercises the REAL tool-execution code
    # ------------------------------------------------------------------
    def test_mock_handle_turn_returns_reply_and_room(self):
        result = self.Agent._handle_turn(self.order.id, "It's an L-shaped kitchen.")
        self.assertTrue(result["ok"], msg=result)
        self.assertIn("reply", result)
        self.assertTrue(result["reply"])
        self.assertIn("room", result)

    def test_mock_populates_draft_via_tool_loop(self):
        result = self.Agent._handle_turn(self.order.id, "It's a straight run, 12 feet.")
        self.assertTrue(result["ok"], msg=result)
        room = result["room"]
        self.assertEqual(room["layout_shape"], "straight")
        self.assertEqual(room["ceiling_height_mm"], 2400)
        self.assertEqual(len(room["walls"]), 1)
        self.assertEqual(room["walls"][0]["length_mm"], 3600)
        self.assertEqual(len(room["walls"][0]["constraints"]), 1)
        self.assertEqual(room["walls"][0]["constraints"][0]["constraint_type"], "window")

    def test_mock_persists_across_turns(self):
        self.Agent._handle_turn(self.order.id, "first message")
        session = self.env["southbrook.room.chat.session"].get_or_create_for_order(self.order.id)
        transcript = session.get_transcript()
        self.assertEqual(len(transcript), 2)  # user + assistant

    def test_reset_flag_clears_session(self):
        self.Agent._handle_turn(self.order.id, "It's a straight run.")
        result = self.Agent._handle_turn(self.order.id, "", reset=True)
        self.assertTrue(result["ok"], msg=result)
        self.assertIsNone(result["room"]["layout_shape"])

    def test_empty_message_rejected(self):
        result = self.Agent._handle_turn(self.order.id, "   ")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "invalid")

    def test_message_length_cap_rejected(self):
        too_long = "x" * (self.Agent._MAX_MESSAGE_CHARS + 1)
        result = self.Agent._handle_turn(self.order.id, too_long)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "invalid")

    # ------------------------------------------------------------------
    # Individual tool validation (called directly against a fresh draft)
    # ------------------------------------------------------------------
    def _blank_draft(self):
        return self.env["southbrook.room.chat.session"].get_or_create_for_order(
            self.order.id).get_draft()

    def test_tool_set_room_shape_invalid_shape_rejected(self):
        draft = self._blank_draft()
        result = self.Agent._tool_set_room_shape(draft, layout_shape="not_a_shape")
        self.assertFalse(result["ok"])

    def test_tool_add_wall_requires_positive_length(self):
        draft = self._blank_draft()
        result = self.Agent._tool_add_wall(draft, length_mm=-100)
        self.assertFalse(result["ok"])
        self.assertEqual(draft["walls"], [])

    def test_tool_add_wall_auto_names(self):
        draft = self._blank_draft()
        result = self.Agent._tool_add_wall(draft, length_mm=3000)
        self.assertTrue(result["ok"], msg=result)
        self.assertEqual(draft["walls"][0]["name"], "Wall A")

    def test_tool_update_wall_out_of_range(self):
        draft = self._blank_draft()
        result = self.Agent._tool_update_wall(draft, wall_index=5, length_mm=1000)
        self.assertFalse(result["ok"])

    def test_tool_remove_wall_out_of_range(self):
        draft = self._blank_draft()
        result = self.Agent._tool_remove_wall(draft, wall_index=0)
        self.assertFalse(result["ok"])

    def test_tool_add_constraint_invalid_type_rejected(self):
        draft = self._blank_draft()
        self.Agent._tool_add_wall(draft, length_mm=3000)
        result = self.Agent._tool_add_constraint(
            draft, wall_index=0, constraint_type="not_a_type",
            distance_from_left_mm=100, width_mm=900)
        self.assertFalse(result["ok"])

    def test_tool_add_constraint_wall_index_out_of_range(self):
        draft = self._blank_draft()
        result = self.Agent._tool_add_constraint(
            draft, wall_index=0, constraint_type="window",
            distance_from_left_mm=100, width_mm=900)
        self.assertFalse(result["ok"])

    def test_tool_add_constraint_missing_distance_rejected(self):
        """Regression: a null/missing distance_from_left_mm must be
        REJECTED, not silently coerced to 0 — 0 is a legitimate distance
        (flush against the wall's left edge) and must not be
        indistinguishable from 'the caller never said'."""
        draft = self._blank_draft()
        self.Agent._tool_add_wall(draft, length_mm=3000)
        result = self.Agent._tool_add_constraint(
            draft, wall_index=0, constraint_type="window",
            distance_from_left_mm=None, width_mm=900)
        self.assertFalse(result["ok"])
        self.assertEqual(draft["walls"][0]["constraints"], [])

    def test_tool_add_constraint_zero_distance_is_valid(self):
        """Regression companion: an EXPLICIT distance_from_left_mm=0
        must still be accepted (it's a real, legitimate position)."""
        draft = self._blank_draft()
        self.Agent._tool_add_wall(draft, length_mm=3000)
        result = self.Agent._tool_add_constraint(
            draft, wall_index=0, constraint_type="window",
            distance_from_left_mm=0, width_mm=900)
        self.assertTrue(result["ok"], msg=result)
        self.assertEqual(draft["walls"][0]["constraints"][0]["distance_from_left_mm"], 0)

    def test_tool_add_constraint_non_numeric_distance_rejected(self):
        draft = self._blank_draft()
        self.Agent._tool_add_wall(draft, length_mm=3000)
        result = self.Agent._tool_add_constraint(
            draft, wall_index=0, constraint_type="window",
            distance_from_left_mm="not-a-number", width_mm=900)
        self.assertFalse(result["ok"])

    def test_tool_add_constraint_optional_heights_default_to_zero(self):
        draft = self._blank_draft()
        self.Agent._tool_add_wall(draft, length_mm=3000)
        result = self.Agent._tool_add_constraint(
            draft, wall_index=0, constraint_type="window",
            distance_from_left_mm=100, width_mm=900)
        self.assertTrue(result["ok"], msg=result)
        c = draft["walls"][0]["constraints"][0]
        self.assertEqual(c["height_mm"], 0)
        self.assertEqual(c["height_from_floor_mm"], 0)

    def test_tool_add_constraint_non_numeric_optional_height_rejected(self):
        draft = self._blank_draft()
        self.Agent._tool_add_wall(draft, length_mm=3000)
        result = self.Agent._tool_add_constraint(
            draft, wall_index=0, constraint_type="window",
            distance_from_left_mm=100, width_mm=900, height_mm="garbage")
        self.assertFalse(result["ok"])

    def test_tool_remove_constraint_out_of_range(self):
        draft = self._blank_draft()
        self.Agent._tool_add_wall(draft, length_mm=3000)
        result = self.Agent._tool_remove_constraint(
            draft, wall_index=0, constraint_index=0)
        self.assertFalse(result["ok"])

    # ------------------------------------------------------------------
    # Geometry gating — AI output is NOT exempt from the existing
    # validator, and never touches southbrook.room directly.
    # ------------------------------------------------------------------
    def test_validate_current_draft_flags_out_of_bounds(self):
        draft = self._blank_draft()
        self.Agent._tool_add_wall(draft, length_mm=1000)
        self.Agent._tool_add_constraint(
            draft, wall_index=0, constraint_type="window",
            distance_from_left_mm=900, width_mm=900)  # 900+900 > 1000
        result = self.Agent._tool_validate_current_draft(draft)
        self.assertTrue(result["ok"])
        self.assertFalse(result["valid"])
        self.assertTrue(result["errors"])

    def test_validate_current_draft_valid_draft_no_errors(self):
        draft = self._blank_draft()
        self.Agent._tool_add_wall(draft, length_mm=3600)
        self.Agent._tool_add_constraint(
            draft, wall_index=0, constraint_type="window",
            distance_from_left_mm=100, width_mm=900)
        result = self.Agent._tool_validate_current_draft(draft)
        self.assertTrue(result["ok"])
        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])

    def test_no_southbrook_room_records_created(self):
        before = self.env["southbrook.room"].search_count([])
        self.Agent._handle_turn(self.order.id, "It's an L-shaped kitchen with a window.")
        after = self.env["southbrook.room"].search_count([])
        self.assertEqual(before, after)

    # ------------------------------------------------------------------
    # Real-path (non-mock) recovery — forced via a mocked transport
    # ------------------------------------------------------------------
    def test_real_path_tool_loop_via_mocked_transport(self):
        """Exercise the real (non-mock) tool_use loop with a canned
        two-step Anthropic response sequence: one tool call, then a
        final text reply."""
        self._set_real_backend()
        responses = [
            {
                "stop_reason": "tool_use",
                "content": [{
                    "type": "tool_use", "id": "call_1",
                    "name": "add_wall",
                    "input": {"name": "Wall A", "length_mm": 4000},
                }],
            },
            {
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "Added a 4m wall."}],
            },
        ]
        with patch.object(
            type(self.Agent), "_call_anthropic", side_effect=responses,
        ):
            result = self.Agent._handle_turn(self.order.id, "One wall, 4 metres.")
        self.assertTrue(result["ok"], msg=result)
        self.assertEqual(result["reply"], "Added a 4m wall.")
        self.assertEqual(result["room"]["walls"][0]["length_mm"], 4000)

    def test_daily_cap_kill_switch_blocks_real_call(self):
        """max_daily_calls=0 is a hard kill-switch — _handle_turn returns
        rate_limited without ever invoking _call_anthropic."""
        self._set_real_backend()
        self.env["ir.config_parameter"].sudo().set_param(
            "southbrook_room_chat.max_daily_calls", "0")
        with patch.object(
            type(self.Agent), "_call_anthropic",
            side_effect=AssertionError("_call_anthropic must not be called"),
        ):
            result = self.Agent._handle_turn(self.order.id, "hello")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "rate_limited")

    def test_daily_cap_reached_blocks_further_turns(self):
        """Once today's real-call counter hits the cap, the next turn's
        first real call is rejected with rate_limited."""
        self._set_real_backend()
        self.env["ir.config_parameter"].sudo().set_param(
            "southbrook_room_chat.max_daily_calls", "1")
        end_turn = {
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "ok"}],
        }
        with patch.object(
            type(self.Agent), "_call_anthropic", return_value=end_turn,
        ):
            first = self.Agent._handle_turn(self.order.id, "hi")
            second = self.Agent._handle_turn(self.order.id, "hi again")
        self.assertTrue(first["ok"], msg=first)
        self.assertFalse(second["ok"])
        self.assertEqual(second["error"], "rate_limited")

    def test_daily_cap_counts_per_real_call_not_per_turn(self):
        """A turn that fans out N real calls consumes N units of quota
        (bounding the _MAX_TOOL_ITERATIONS multiplier), so a cap of 1
        stops the loop after the first call within a single turn."""
        self._set_real_backend()
        self.env["ir.config_parameter"].sudo().set_param(
            "southbrook_room_chat.max_daily_calls", "1")
        # First call asks for a tool; the loop would normally make a 2nd
        # real call to get the final reply — but the cap (1) is exhausted,
        # so the turn stops gracefully with the draft built so far.
        responses = [
            {
                "stop_reason": "tool_use",
                "content": [{
                    "type": "tool_use", "id": "c1", "name": "add_wall",
                    "input": {"name": "Wall A", "length_mm": 4000},
                }],
            },
            {  # must never be reached — cap is 1
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "should not appear"}],
            },
        ]
        with patch.object(
            type(self.Agent), "_call_anthropic", side_effect=responses,
        ):
            result = self.Agent._handle_turn(self.order.id, "one wall 4m")
        self.assertTrue(result["ok"], msg=result)
        # The tool ran (draft has the wall) but the 2nd call was capped.
        self.assertEqual(result["room"]["walls"][0]["length_mm"], 4000)
        self.assertNotEqual(result["reply"], "should not appear")

    def test_daily_cap_does_not_apply_to_mock(self):
        """The mock backend is free — the cap only gates the paid real
        call, so mock turns never consume quota."""
        self.env["ir.config_parameter"].sudo().set_param(
            "southbrook_room_chat.max_daily_calls", "0")
        result = self.Agent._handle_turn(self.order.id, "It's a straight run.")
        self.assertTrue(result["ok"], msg=result)

    def test_handle_turn_is_not_rpc_dispatchable(self):
        """H2 regression: the public `handle_turn` name must be gone (an
        RPC-reachable entry point would bypass the controller's ownership
        + rate-limit gates); only the private `_handle_turn` exists."""
        self.assertFalse(
            hasattr(type(self.Agent), "handle_turn"),
            "handle_turn must be private (_handle_turn) — a public name is "
            "call_kw-dispatchable and bypasses ownership/rate-limit gates.")
        self.assertTrue(hasattr(type(self.Agent), "_handle_turn"))

    def test_malformed_ai_response_recovered(self):
        self._set_real_backend()
        with patch.object(
            type(self.Agent), "_call_anthropic", return_value="not a dict",
        ):
            result = self.Agent._handle_turn(self.order.id, "hello")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "malformed_response")

    def test_failed_ai_call_graceful(self):
        self._set_real_backend()
        with patch.object(
            type(self.Agent), "_call_anthropic",
            side_effect=RuntimeError("Anthropic HTTP 503"),
        ):
            result = self.Agent._handle_turn(self.order.id, "hello")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "upstream_error")

    def test_refusal_stop_reason_graceful(self):
        self._set_real_backend()
        with patch.object(
            type(self.Agent), "_call_anthropic",
            return_value={"content": [], "stop_reason": "refusal"},
        ):
            result = self.Agent._handle_turn(self.order.id, "hello")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "refused")

    def test_not_configured_when_no_api_key(self):
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("southbrook_room_chat.use_mock", "False")
        ICP.set_param("southbrook_room_capture.anthropic_api_key", "")
        result = self.Agent._handle_turn(self.order.id, "hello")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "not_configured")


@tagged("post_install", "-at_install", "southbrook", "southbrook_room_chat")
class TestRoomChatController(TransactionCase):
    """Tests of the JSON-RPC controller layer."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "Test Customer Room Chat Controller",
            "email": "test_room_chat_controller@southbrook.test",
        })
        cls.order = cls.env["sale.order"].create({"partner_id": cls.partner.id})

        cls.other_partner = cls.env["res.partner"].create({
            "name": "Stranger Room Chat",
            "email": "stranger_room_chat@southbrook.test",
        })
        portal_group = cls.env.ref("base.group_portal")
        cls.portal_user = cls.env["res.users"].create({
            "name": "Portal Stranger Room Chat",
            "login": "portal_stranger_room_chat@southbrook.test",
            "partner_id": cls.other_partner.id,
            "group_ids": [(6, 0, [portal_group.id])],
        })

        cls.controller = ctrl_chat.SouthbrookRoomChatApi()

    def setUp(self):
        super().setUp()
        # Rate-limit state is process-global; make sure earlier tests in
        # this run don't bleed into these (mirrors the isolation each
        # test method otherwise assumes).
        ctrl_chat._RATE_BUCKETS.clear()

    def test_authenticated_access_returns_reply_and_room(self):
        with stubbed_request(self.env):
            result = self.controller.southbrook_api_room_chat(
                self.order.id, message="It's an L-shaped kitchen.")
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("reply", result)
        self.assertIn("room", result)

    def test_ownership_rejection_for_non_owning_portal_user(self):
        with stubbed_request(self.env, user=self.portal_user):
            result = self.controller.southbrook_api_room_chat(
                self.order.id, message="hello")
        self.assertEqual(result.get("error"), "forbidden")

    def test_empty_message_rejected(self):
        with stubbed_request(self.env):
            result = self.controller.southbrook_api_room_chat(
                self.order.id, message="   ")
        self.assertEqual(result.get("error"), "invalid")

    def test_missing_message_rejected(self):
        with stubbed_request(self.env):
            result = self.controller.southbrook_api_room_chat(self.order.id)
        self.assertEqual(result.get("error"), "invalid")

    def test_reset_flag_works_without_message(self):
        with stubbed_request(self.env):
            result = self.controller.southbrook_api_room_chat(
                self.order.id, reset=True)
        self.assertTrue(result.get("ok"), msg=result)

    def test_rate_limit_enforced(self):
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("southbrook_room_chat.rate_limit", "2")
        ICP.set_param("southbrook_room_chat.rate_window_sec", "3600")
        with stubbed_request(self.env):
            self.controller.southbrook_api_room_chat(self.order.id, message="one")
            self.controller.southbrook_api_room_chat(self.order.id, message="two")
            result = self.controller.southbrook_api_room_chat(
                self.order.id, message="three")
        self.assertEqual(result.get("error"), "rate_limited")

    def test_no_southbrook_room_records_created_end_to_end(self):
        before = self.env["southbrook.room"].search_count([])
        with stubbed_request(self.env):
            self.controller.southbrook_api_room_chat(
                self.order.id, message="It's an L-shaped kitchen.")
        after = self.env["southbrook.room"].search_count([])
        self.assertEqual(before, after)
