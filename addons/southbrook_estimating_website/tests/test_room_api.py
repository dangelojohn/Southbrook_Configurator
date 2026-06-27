# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for the Phase 2.A Room CRUD JSON-RPC endpoints.

Targets controllers/room_api.py — the 5 endpoints landed for the
Room-First UX initiative:

    POST /southbrook/api/order/<id>/room/get
    POST /southbrook/api/order/<id>/room/create
    POST /southbrook/api/order/<id>/room/<rid>/update
    POST /southbrook/api/order/<id>/room/<rid>/wall/<wid>/constraint/add
    POST /southbrook/api/order/<id>/room/<rid>/wall/<wid>/constraint/<cid>/delete

We follow the established pattern from test_customer_flow_endpoints:
`TransactionCase` + a `stubbed_request` contextmanager that swaps the
controllers.room_api module's `request` proxy for a MagicMock whose
.env resolves to a real Odoo env. This lets us drive the controller
methods directly without standing up an HTTP context (we can't run JS
in TransactionCase, and HttpCase brings significantly more setup cost
for what is effectively pure Python).

Run with:
    odoo --no-http --test-enable -u southbrook_estimating_website \
        -d <db> --stop-after-init --test-tags=southbrook_room_api
"""
from contextlib import contextmanager
from unittest.mock import MagicMock

from odoo.tests import TransactionCase, tagged

from odoo.addons.southbrook_estimating_website.controllers import (
    room_api as ctrl_room,
)


@contextmanager
def stubbed_request(env, user=None):
    """Swap controllers.room_api.request for a MagicMock whose .env
    resolves to a real Odoo env for the duration of the with-block.
    Restores the original werkzeug LocalProxy on exit.
    """
    saved = ctrl_room.request
    mock = MagicMock()
    mock.env = env if user is None else env(user=user.id)
    mock.session = {}
    mock.params = {}
    ctrl_room.request = mock
    try:
        yield mock
    finally:
        ctrl_room.request = saved


@tagged("post_install", "-at_install", "southbrook", "southbrook_room_api")
class TestRoomApi(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "Test Customer Room API",
            "email": "test_room_api@southbrook.test",
        })
        # Owner of the order under test — internal admin (default
        # user) has full access; the share=False branch in
        # _southbrook_resolve_order short-circuits the partner check.
        cls.order = cls.env["sale.order"].create({
            "partner_id": cls.partner.id,
        })

        # A second order owned by an unrelated portal user — used to
        # verify the resolve_order guard returns `forbidden` for
        # cross-account access.
        cls.other_partner = cls.env["res.partner"].create({
            "name": "Stranger",
            "email": "stranger_room_api@southbrook.test",
        })
        cls.other_order = cls.env["sale.order"].create({
            "partner_id": cls.other_partner.id,
        })

        # A portal user attached to `partner` — share=True flips the
        # access-check branch so we exercise the partner-match path.
        portal_group = cls.env.ref("base.group_portal")
        cls.portal_user = cls.env["res.users"].create({
            "name": "Portal Customer",
            "login": "portal_room_api@southbrook.test",
            "partner_id": cls.partner.id,
            "group_ids": [(6, 0, [portal_group.id])],
        })

    # ------------------------------------------------------------------
    # /room/get
    # ------------------------------------------------------------------
    def test_room_get_when_no_room_returns_null(self):
        controller = ctrl_room.SouthbrookRoomApi()
        with stubbed_request(self.env):
            result = controller.southbrook_api_room_get(self.order.id)
        self.assertTrue(result["ok"])
        self.assertIsNone(result["room"])

    # ------------------------------------------------------------------
    # /room/create
    # ------------------------------------------------------------------
    def test_room_create_minimal(self):
        controller = ctrl_room.SouthbrookRoomApi()
        with stubbed_request(self.env):
            result = controller.southbrook_api_room_create(
                self.order.id,
                name="Test Kitchen",
                layout_shape="straight",
            )
        self.assertTrue(result.get("ok"), msg=f"unexpected: {result}")
        room = result["room"]
        self.assertEqual(room["name"], "Test Kitchen")
        self.assertEqual(room["layout_shape"], "straight")
        # Defaults applied.
        self.assertEqual(room["room_type"], "kitchen")
        self.assertEqual(room["unit_preference"], "mm")
        self.assertEqual(room["ceiling_height_mm"], 2400)
        self.assertEqual(room["walls"], [])
        # Round-trip back through /room/get.
        with stubbed_request(self.env):
            get_result = controller.southbrook_api_room_get(self.order.id)
        self.assertEqual(get_result["room"]["id"], room["id"])

    def test_room_create_with_walls_and_constraints(self):
        controller = ctrl_room.SouthbrookRoomApi()
        with stubbed_request(self.env):
            result = controller.southbrook_api_room_create(
                self.order.id,
                name="L Kitchen",
                layout_shape="l_shape",
                walls=[
                    {"name": "Wall A", "length_mm": 3600,
                     "has_upper_cabinets": True},
                    {"name": "Wall B", "length_mm": 2400,
                     "has_upper_cabinets": False},
                ],
                constraints=[
                    {"wall_index": 0, "constraint_type": "window",
                     "distance_from_left_mm": 800, "width_mm": 1200},
                    {"wall_index": 1, "constraint_type": "sink",
                     "distance_from_left_mm": 600, "width_mm": 900},
                ],
            )
        self.assertTrue(result.get("ok"), msg=f"unexpected: {result}")
        room = result["room"]
        self.assertEqual(len(room["walls"]), 2)
        wall_a, wall_b = room["walls"]
        self.assertEqual(wall_a["length_mm"], 3600)
        self.assertEqual(wall_b["length_mm"], 2400)
        self.assertEqual(len(wall_a["constraints"]), 1)
        self.assertEqual(wall_a["constraints"][0]["constraint_type"], "window")
        self.assertEqual(len(wall_b["constraints"]), 1)
        self.assertEqual(wall_b["constraints"][0]["constraint_type"], "sink")
        # has_plumbing rolls up from the sink.
        self.assertTrue(room["has_plumbing"])

    def test_room_create_idempotency_returns_existing(self):
        controller = ctrl_room.SouthbrookRoomApi()
        with stubbed_request(self.env):
            first = controller.southbrook_api_room_create(
                self.order.id,
                name="Original",
                layout_shape="straight",
            )
            second = controller.southbrook_api_room_create(
                self.order.id,
                name="Duplicate Attempt",
                layout_shape="u_shape",
            )
        self.assertTrue(first.get("ok"))
        self.assertEqual(second.get("error"), "room_already_exists")
        # Existing room is returned — caller can switch to update.
        self.assertEqual(second["room"]["id"], first["room"]["id"])
        self.assertEqual(second["room"]["name"], "Original")

    def test_room_create_unauthorized_order_returns_forbidden(self):
        controller = ctrl_room.SouthbrookRoomApi()
        # Portal user attached to `self.partner` tries to create a
        # room on `self.other_order` (owned by `self.other_partner`).
        # _southbrook_resolve_order's share=True branch fires and
        # raises AccessError → endpoint returns `forbidden`.
        with stubbed_request(self.env, user=self.portal_user):
            result = controller.southbrook_api_room_create(
                self.other_order.id,
                name="Sneaky",
                layout_shape="straight",
            )
        self.assertEqual(result.get("error"), "forbidden")

    # ------------------------------------------------------------------
    # /room/<rid>/update
    # ------------------------------------------------------------------
    def test_room_update_partial_scalars(self):
        room = self.env["southbrook.room"].create({
            "name": "Before",
            "order_id": self.order.id,
            "layout_shape": "straight",
        })
        controller = ctrl_room.SouthbrookRoomApi()
        with stubbed_request(self.env):
            result = controller.southbrook_api_room_update(
                self.order.id,
                room.id,
                name="After",
                ceiling_height_mm=2700,
            )
        self.assertTrue(result.get("ok"), msg=f"unexpected: {result}")
        room.invalidate_recordset()
        self.assertEqual(room.name, "After")
        self.assertEqual(room.ceiling_height_mm, 2700)
        # Untouched scalars retained.
        self.assertEqual(room.layout_shape, "straight")

    def test_room_update_walls_upsert(self):
        room = self.env["southbrook.room"].create({
            "name": "Upsert Test",
            "order_id": self.order.id,
            "layout_shape": "l_shape",
            "wall_ids": [
                (0, 0, {"name": "Wall A", "length_mm": 3000}),
            ],
        })
        existing_wall = room.wall_ids[0]
        controller = ctrl_room.SouthbrookRoomApi()
        with stubbed_request(self.env):
            result = controller.southbrook_api_room_update(
                self.order.id,
                room.id,
                walls=[
                    # id present → update
                    {"id": existing_wall.id, "length_mm": 3400},
                    # id absent → create
                    {"name": "Wall B", "length_mm": 2200,
                     "has_upper_cabinets": False},
                ],
            )
        self.assertTrue(result.get("ok"), msg=f"unexpected: {result}")
        room.invalidate_recordset()
        self.assertEqual(len(room.wall_ids), 2)
        existing_wall.invalidate_recordset()
        self.assertEqual(existing_wall.length_mm, 3400)
        new_wall = room.wall_ids - existing_wall
        self.assertEqual(new_wall.name, "Wall B")
        self.assertEqual(new_wall.length_mm, 2200)
        self.assertFalse(new_wall.has_upper_cabinets)

    # ------------------------------------------------------------------
    # /constraint/add
    # ------------------------------------------------------------------
    def test_constraint_add_validates_type(self):
        room = self.env["southbrook.room"].create({
            "name": "K", "order_id": self.order.id,
            "layout_shape": "straight",
            "wall_ids": [(0, 0, {"name": "A", "length_mm": 3000})],
        })
        wall = room.wall_ids[0]
        controller = ctrl_room.SouthbrookRoomApi()
        with stubbed_request(self.env):
            bad = controller.southbrook_api_constraint_add(
                self.order.id, room.id, wall.id,
                constraint_type="nonsense",
                distance_from_left_mm=100, width_mm=200,
            )
        self.assertEqual(bad.get("error"), "invalid")
        self.assertIn("constraint_type", bad.get("detail", ""))
        # Confirm a real type works.
        with stubbed_request(self.env):
            good = controller.southbrook_api_constraint_add(
                self.order.id, room.id, wall.id,
                constraint_type="window",
                distance_from_left_mm=100, width_mm=200,
            )
        self.assertTrue(good.get("ok"))
        self.assertEqual(good["constraint"]["constraint_type"], "window")

    def test_constraint_add_scoped_to_wall(self):
        # Two rooms — same order is forbidden by Phase 2.A idempotency,
        # so we stand up two separate orders (admin user has access to
        # both) and verify a wall_id from order_b can't be hit through
        # order_a's resolved order.
        order_b = self.env["sale.order"].create({
            "partner_id": self.partner.id,
        })
        room_a = self.env["southbrook.room"].create({
            "name": "A", "order_id": self.order.id,
            "layout_shape": "straight",
            "wall_ids": [(0, 0, {"name": "WA", "length_mm": 3000})],
        })
        room_b = self.env["southbrook.room"].create({
            "name": "B", "order_id": order_b.id,
            "layout_shape": "straight",
            "wall_ids": [(0, 0, {"name": "WB", "length_mm": 3000})],
        })
        wall_b = room_b.wall_ids[0]
        controller = ctrl_room.SouthbrookRoomApi()
        # Caller asks "add a constraint to order_a's room_a's wall_b
        # (which doesn't belong to it)". The scope guard catches the
        # wall_id mismatch → forbidden.
        with stubbed_request(self.env):
            result = controller.southbrook_api_constraint_add(
                self.order.id, room_a.id, wall_b.id,
                constraint_type="window",
                distance_from_left_mm=100, width_mm=200,
            )
        self.assertEqual(result.get("error"), "forbidden")

    # ------------------------------------------------------------------
    # /line/<lid>/place-on-wall  (Phase 3.A)
    # ------------------------------------------------------------------
    def test_place_on_wall_happy_path(self):
        room = self.env["southbrook.room"].create({
            "name": "Place Room",
            "order_id": self.order.id,
            "layout_shape": "straight",
            "wall_ids": [(0, 0, {"name": "Wall A", "length_mm": 3000})],
        })
        wall = room.wall_ids[0]
        # A line on the order — bare-bones, no product needed for the
        # placement smoke (wall_id + position_from_left_mm are scalars).
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id,
            "name": "Place me",
        })
        controller = ctrl_room.SouthbrookRoomApi()
        with stubbed_request(self.env):
            result = controller.southbrook_api_line_place_on_wall(
                self.order.id,
                line.id,
                wall_id=wall.id,
                position_from_left_mm=450,
            )
        self.assertTrue(result.get("ok"), msg=f"unexpected: {result}")
        # Line dict reflects the write.
        self.assertEqual(result["line"]["id"], line.id)
        self.assertEqual(result["line"]["wall_id"], wall.id)
        self.assertEqual(result["line"]["position_from_left_mm"], 450)
        self.assertTrue(result["line"]["is_positioned"])
        # Wall dict carries the live-recomputed metrics.
        self.assertIsNotNone(result["wall"])
        self.assertEqual(result["wall"]["id"], wall.id)
        self.assertIn("used_mm", result["wall"])
        self.assertIn("remaining_mm", result["wall"])
        self.assertIn("has_conflicts", result["wall"])
        # ORM-side confirmation.
        line.invalidate_recordset()
        self.assertEqual(line.wall_id.id, wall.id)
        self.assertEqual(line.position_from_left_mm, 450)

    def test_place_on_wall_unplace_via_null(self):
        room = self.env["southbrook.room"].create({
            "name": "Unplace Room",
            "order_id": self.order.id,
            "layout_shape": "straight",
            "wall_ids": [(0, 0, {"name": "Wall A", "length_mm": 3000})],
        })
        wall = room.wall_ids[0]
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id,
            "name": "Already placed",
            "wall_id": wall.id,
            "position_from_left_mm": 600,
        })
        controller = ctrl_room.SouthbrookRoomApi()
        with stubbed_request(self.env):
            result = controller.southbrook_api_line_place_on_wall(
                self.order.id,
                line.id,
                wall_id=None,
            )
        self.assertTrue(result.get("ok"), msg=f"unexpected: {result}")
        self.assertFalse(result["line"]["wall_id"])
        self.assertEqual(result["line"]["position_from_left_mm"], 0)
        self.assertFalse(result["line"]["is_positioned"])
        # Unplace → wall dict is null (no metrics to return).
        self.assertIsNone(result["wall"])
        line.invalidate_recordset()
        self.assertFalse(line.wall_id)

    def test_place_on_wall_cross_order_forbidden(self):
        # Line lives on order A; wall lives on order B's room. Caller
        # asks "place A's line on B's wall via order_a's path" — scope
        # guard must surface `forbidden` (no existence-oracle leak).
        order_b = self.env["sale.order"].create({
            "partner_id": self.partner.id,
        })
        room_b = self.env["southbrook.room"].create({
            "name": "B", "order_id": order_b.id,
            "layout_shape": "straight",
            "wall_ids": [(0, 0, {"name": "WB", "length_mm": 3000})],
        })
        wall_b = room_b.wall_ids[0]
        line_a = self.env["sale.order.line"].create({
            "order_id": self.order.id,
            "name": "Line A",
        })
        controller = ctrl_room.SouthbrookRoomApi()
        with stubbed_request(self.env):
            result = controller.southbrook_api_line_place_on_wall(
                self.order.id,
                line_a.id,
                wall_id=wall_b.id,
                position_from_left_mm=100,
            )
        self.assertEqual(result.get("error"), "forbidden")
        # And the line was NOT mutated.
        line_a.invalidate_recordset()
        self.assertFalse(line_a.wall_id)

    def test_place_returns_previous_wall_metrics(self):
        """Re-placing a line on a different wall returns both wall metrics.

        Phase 3.C.1 — when the line moves from wall A → wall B the
        response must carry `previous_wall: {...}` for A so the caller's
        floor-plan re-render shows the correct used_mm on BOTH walls
        in one round-trip.
        """
        room = self.env["southbrook.room"].create({
            "name": "Two-Wall Room",
            "order_id": self.order.id,
            "layout_shape": "l_shape",
            "wall_ids": [
                (0, 0, {"name": "A", "length_mm": 3600}),
                (0, 0, {"name": "B", "length_mm": 2400}),
            ],
        })
        wall_a = room.wall_ids[0]
        wall_b = room.wall_ids[1]
        # Line name carries the width parser's "Nmm" token so
        # sb_width_mm computes to a real value (not the 600 fallback).
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id,
            "name": "Base 800mm cabinet",
        })
        controller = ctrl_room.SouthbrookRoomApi()
        # First place on wall A — previous_wall should be null (no
        # prior wall) on this call.
        with stubbed_request(self.env):
            first = controller.southbrook_api_line_place_on_wall(
                self.order.id, line.id,
                wall_id=wall_a.id, position_from_left_mm=200,
            )
        self.assertTrue(first.get("ok"), msg=f"first place: {first}")
        self.assertEqual(first["wall"]["id"], wall_a.id)
        self.assertIsNone(first.get("previous_wall"))
        # Re-place on wall B — previous_wall must surface wall A's
        # post-move metrics so the FROM-side floor-plan tile refreshes.
        with stubbed_request(self.env):
            second = controller.southbrook_api_line_place_on_wall(
                self.order.id, line.id,
                wall_id=wall_b.id, position_from_left_mm=100,
            )
        self.assertTrue(second.get("ok"), msg=f"second place: {second}")
        self.assertEqual(second["wall"]["id"], wall_b.id)
        self.assertIsNotNone(second.get("previous_wall"))
        self.assertEqual(second["previous_wall"]["id"], wall_a.id)
        self.assertIn("used_mm", second["previous_wall"])
        self.assertIn("remaining_mm", second["previous_wall"])
        self.assertIn("has_conflicts", second["previous_wall"])

    def test_place_rejects_out_of_bounds(self):
        """Cabinet pos+width past wall length → out_of_bounds.

        Phase 3.C.1 — Phase 3.C.2a drag UX needs a clean error code so
        the modal can show "Cabinet extends past wall edge by Nmm"
        instead of letting the write proceed into an over-full wall.
        """
        room = self.env["southbrook.room"].create({
            "name": "Short Wall Room",
            "order_id": self.order.id,
            "layout_shape": "straight",
            "wall_ids": [(0, 0, {"name": "Short", "length_mm": 1000})],
        })
        wall = room.wall_ids[0]
        # "600mm" in the name → sb_width_mm computes to 600.0.
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id,
            "name": "Base 600mm cabinet",
        })
        controller = ctrl_room.SouthbrookRoomApi()
        # 500 + 600 = 1100 > 1000 → overflow by 100mm.
        with stubbed_request(self.env):
            result = controller.southbrook_api_line_place_on_wall(
                self.order.id, line.id,
                wall_id=wall.id, position_from_left_mm=500,
            )
        self.assertEqual(result.get("error"), "out_of_bounds")
        self.assertIn("100mm", result.get("detail", ""))
        # Line must NOT have been mutated.
        line.invalidate_recordset()
        self.assertFalse(line.wall_id)
        self.assertEqual(line.position_from_left_mm, 0)

    # ------------------------------------------------------------------
    # /constraint/<cid>/delete
    # ------------------------------------------------------------------
    def test_constraint_delete(self):
        room = self.env["southbrook.room"].create({
            "name": "D", "order_id": self.order.id,
            "layout_shape": "straight",
            "wall_ids": [(0, 0, {"name": "A", "length_mm": 3000})],
        })
        wall = room.wall_ids[0]
        constraint = self.env["southbrook.room.constraint"].create({
            "wall_id": wall.id,
            "constraint_type": "window",
            "distance_from_left_mm": 500,
            "width_mm": 600,
        })
        constraint_id = constraint.id
        controller = ctrl_room.SouthbrookRoomApi()
        with stubbed_request(self.env):
            result = controller.southbrook_api_constraint_delete(
                self.order.id, room.id, wall.id, constraint_id,
            )
        self.assertTrue(result.get("ok"))
        self.assertFalse(
            self.env["southbrook.room.constraint"]
            .browse(constraint_id).exists(),
            "constraint should be unlinked",
        )

    # ------------------------------------------------------------------
    # /recommend — Phase 6.1 cabinet recommendation engine.
    #
    # The recommend endpoint scores SB-* product templates against a
    # gap width and returns the top 3 fits. These tests rely on the
    # southbrook_estimating seed data (12 SB-* templates + a "Width"
    # attribute with values `9 in`...`36 in`), which is loaded as a
    # module dependency. If the seed templates ever stop carrying a
    # Width attribute, test_recommend_returns_results_for_typical_gap
    # will surface that as a "no recommendations" assertion failure
    # — better than silently passing.
    # ------------------------------------------------------------------

    def _make_room_with_wall(self):
        """Helper — create a 3000mm room+wall for recommend tests.

        Scope is required: the recommend endpoint walks
        order → room → wall before scoring, and rejects mismatches
        as forbidden. We always create the room on `self.order` so the
        controller's _southbrook_resolve_order succeeds for the admin
        user used by the tests.
        """
        room = self.env["southbrook.room"].create({
            "name": "Recommend Room",
            "order_id": self.order.id,
            "layout_shape": "straight",
            "wall_ids": [(0, 0, {"name": "A", "length_mm": 3000})],
        })
        return room, room.wall_ids[0]

    def test_recommend_returns_results_for_typical_gap(self):
        """gap_mm=900 → at least one fitting template, well-formed shape.

        Demo seed has SB-* templates with Width values 9-36 in
        (228mm-914mm). A 900mm gap fits all of them; the score should
        favour the widest fitter, with the standard-width bonus
        promoting 914mm → no, 900 isn't in STANDARD_WIDTHS_MM but
        914 isn't either. The test is intentionally lax on which
        template wins — only on the shape of the response.
        """
        room, wall = self._make_room_with_wall()
        controller = ctrl_room.SouthbrookRoomApi()
        with stubbed_request(self.env):
            result = controller.southbrook_api_recommend(
                self.order.id, room.id, wall.id,
                gap_mm=900,
                position_from_left_mm=0,
            )
        self.assertTrue(
            result.get("ok"),
            msg=f"unexpected recommend response: {result}",
        )
        self.assertEqual(result["gap_mm"], 900)
        recs = result.get("recommendations") or []
        self.assertGreater(
            len(recs), 0,
            msg=(
                "expected at least one recommendation for 900mm gap; "
                "got empty list. Check that SB-* templates seed with "
                "a Width attribute (southbrook_estimating data)."
            ),
        )
        self.assertLessEqual(
            len(recs), 3, msg="recommend must cap at top 3",
        )
        for rec in recs:
            self.assertIn("template_id", rec)
            self.assertIn("name", rec)
            self.assertIn("default_code", rec)
            self.assertIn("fitting_widths_mm", rec)
            self.assertIn("best_width_mm", rec)
            self.assertIn("score", rec)
            self.assertIsInstance(rec["fitting_widths_mm"], list)
            self.assertGreater(rec["best_width_mm"], 0)
            self.assertLessEqual(rec["best_width_mm"], 900)
        # Sorted descending by score — first card is the best fit.
        scores = [r["score"] for r in recs]
        self.assertEqual(
            scores, sorted(scores, reverse=True),
            "recommendations must be sorted by score desc",
        )

    def test_recommend_empty_for_tiny_gap(self):
        """gap_mm=100 → recommendations=[] with note=gap_too_small.

        The smallest seeded Width is 9 in ≈ 228mm; no template fits a
        100mm gap. The endpoint must return ok=True (this is NOT an
        error — the modal renders an empty-state message + Browse all
        fallback) plus the gap_too_small note for the client to key on.
        """
        room, wall = self._make_room_with_wall()
        controller = ctrl_room.SouthbrookRoomApi()
        with stubbed_request(self.env):
            result = controller.southbrook_api_recommend(
                self.order.id, room.id, wall.id,
                gap_mm=100,
                position_from_left_mm=0,
            )
        self.assertTrue(
            result.get("ok"),
            msg=f"unexpected recommend response: {result}",
        )
        self.assertEqual(result.get("recommendations"), [])
        self.assertEqual(result.get("note"), "gap_too_small")

    def test_recommend_rejects_invalid_gap_mm(self):
        """gap_mm in {0, -5, None} → error=invalid.

        Defensive guard at the controller boundary — a hand-crafted
        curl with gap_mm=0 should NOT 500 the worker and should NOT
        return an empty recommendation list (which would be ambiguous
        with the gap_too_small case).
        """
        room, wall = self._make_room_with_wall()
        controller = ctrl_room.SouthbrookRoomApi()
        for bad in (0, -5, None):
            with self.subTest(gap_mm=bad):
                with stubbed_request(self.env):
                    result = controller.southbrook_api_recommend(
                        self.order.id, room.id, wall.id,
                        gap_mm=bad,
                        position_from_left_mm=0,
                    )
                self.assertEqual(
                    result.get("error"), "invalid",
                    msg=f"gap_mm={bad!r} → {result}",
                )
