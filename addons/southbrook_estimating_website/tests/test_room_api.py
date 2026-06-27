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
