# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "southbrook_room")
class TestSouthbrookRoom(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Test Customer"})
        cls.order = cls.env["sale.order"].create({"partner_id": cls.partner.id})

    def test_create_minimal_room(self):
        room = self.env["southbrook.room"].create({
            "name": "Main Kitchen",
            "order_id": self.order.id,
        })
        self.assertEqual(room.order_id, self.order)
        self.assertEqual(room.unit_preference, "mm")
        self.assertEqual(room.ceiling_height_mm, 2400)
        self.assertFalse(room.layout_complete)

    def test_layout_complete_requires_shape_plus_two_walls(self):
        room = self.env["southbrook.room"].create({
            "name": "L-Kitchen",
            "order_id": self.order.id,
            "layout_shape": "l_shape",
            "wall_ids": [
                (0, 0, {"name": "Wall A", "length_mm": 3600}),
                (0, 0, {"name": "Wall B", "length_mm": 2400}),
            ],
        })
        self.assertTrue(room.layout_complete)
        self.assertEqual(room.total_linear_mm, 6000)
        self.assertEqual(room.wall_count, 2)

    def test_layout_incomplete_when_wall_has_zero_length(self):
        room = self.env["southbrook.room"].create({
            "name": "Half-set",
            "order_id": self.order.id,
            "layout_shape": "straight",
            "wall_ids": [(0, 0, {"name": "Wall A", "length_mm": 0})],
        })
        self.assertFalse(room.layout_complete)

    def test_has_plumbing_when_sink_constraint_present(self):
        room = self.env["southbrook.room"].create({
            "name": "Plumb",
            "order_id": self.order.id,
            "layout_shape": "straight",
            "wall_ids": [(0, 0, {"name": "A", "length_mm": 3000})],
        })
        wall = room.wall_ids[0]
        self.env["southbrook.room.constraint"].create({
            "wall_id": wall.id,
            "constraint_type": "sink",
            "distance_from_left_mm": 1200,
            "width_mm": 900,
        })
        room.invalidate_recordset(["has_plumbing", "constraint_count"])
        self.assertTrue(room.has_plumbing)
        self.assertEqual(room.constraint_count, 1)

    def test_room_cascade_deletes_walls_and_constraints(self):
        room = self.env["southbrook.room"].create({
            "name": "Doomed",
            "order_id": self.order.id,
            "wall_ids": [(0, 0, {"name": "A", "length_mm": 3000})],
        })
        wall = room.wall_ids[0]
        self.env["southbrook.room.constraint"].create({
            "wall_id": wall.id,
            "constraint_type": "window",
            "distance_from_left_mm": 500,
            "width_mm": 600,
        })
        wall_id, room_id = wall.id, room.id
        room.unlink()
        self.assertFalse(self.env["southbrook.room.wall"].browse(wall_id).exists())
        self.assertFalse(self.env["southbrook.room"].browse(room_id).exists())

    def test_unit_preference_round_trip(self):
        room = self.env["southbrook.room"].create({
            "name": "Imp", "order_id": self.order.id, "unit_preference": "imperial",
        })
        self.assertEqual(room.unit_preference, "imperial")
