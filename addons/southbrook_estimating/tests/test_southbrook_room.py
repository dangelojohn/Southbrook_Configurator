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

    def test_action_open_southbrook_room_single(self):
        room = self.env["southbrook.room"].create({
            "name": "Solo", "order_id": self.order.id,
        })
        action = self.order.action_open_southbrook_room()
        self.assertEqual(action.get("res_id"), room.id)
        self.assertIn(("False", "form"), [(str(v[0]), v[1]) for v in action.get("views", [])])

    def test_action_open_southbrook_room_multi(self):
        self.env["southbrook.room"].create({"name": "A", "order_id": self.order.id})
        self.env["southbrook.room"].create({"name": "B", "order_id": self.order.id})
        action = self.order.action_open_southbrook_room()
        self.assertEqual(action.get("domain"), [("order_id", "=", self.order.id)])
        # v19 always seeds res_id=0 in act_window dicts; the semantic
        # check is that no specific record is being singled-out for
        # form-view landing. Treat 0/False as "not pinned".
        self.assertIn(action.get("res_id"), (0, False, None))

    def test_room_count_compute(self):
        self.assertEqual(self.order.room_count, 0)
        self.env["southbrook.room"].create({"name": "X", "order_id": self.order.id})
        self.order.invalidate_recordset(["room_count"])
        self.assertEqual(self.order.room_count, 1)

    def test_room_ids_copy_false_on_duplicate(self):
        self.env["southbrook.room"].create({
            "name": "Original", "order_id": self.order.id,
        })
        new_order = self.order.copy()
        self.assertEqual(
            len(new_order.room_ids), 0,
            "room_ids must not propagate on copy (NF6 — v2 starts with fresh measurement)")

    # ------------------------------------------------------------------
    # Phase 5 — Customer Spec Sheet PDF helpers (to_summary_dict + to_svg).
    # ------------------------------------------------------------------

    def test_to_svg_returns_svg_for_configured_room(self):
        room = self.env["southbrook.room"].create({
            "name": "Kitchen-PDF",
            "order_id": self.order.id,
            "layout_shape": "l_shape",
            "wall_ids": [
                (0, 0, {"name": "WallA", "length_mm": 3600}),
                (0, 0, {"name": "WallB", "length_mm": 2400}),
            ],
        })
        self.env["southbrook.room.constraint"].create({
            "wall_id": room.wall_ids[0].id,
            "constraint_type": "window",
            "distance_from_left_mm": 800,
            "width_mm": 900,
        })
        svg = room.to_svg()
        self.assertTrue(svg.startswith("<svg"),
                        "to_svg must return a valid SVG root element")
        self.assertIn("3600", svg,
                      "wall length label must appear in the rendered SVG")
        # Window marker colour (Sky) should appear in the SVG markup.
        self.assertIn("#5E8FBE", svg,
                      "window constraint colour must be rendered")
        self.assertIn("Window", svg,
                      "window type label must appear in the SVG")

    def test_to_svg_returns_placeholder_for_no_walls(self):
        room = self.env["southbrook.room"].create({
            "name": "Empty",
            "order_id": self.order.id,
        })
        svg = room.to_svg()
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("no walls", svg.lower(),
                      "empty-room placeholder must mention 'no walls'")

    def test_to_summary_dict_shape_with_constraints(self):
        room = self.env["southbrook.room"].create({
            "name": "Summary-Test",
            "order_id": self.order.id,
            "layout_shape": "l_shape",
            "wall_ids": [
                (0, 0, {"name": "A", "length_mm": 3600}),
                (0, 0, {"name": "B", "length_mm": 2400}),
            ],
        })
        self.env["southbrook.room.constraint"].create({
            "wall_id": room.wall_ids[0].id,
            "constraint_type": "sink",
            "distance_from_left_mm": 1200,
            "width_mm": 900,
        })
        room.invalidate_recordset(["has_plumbing", "constraint_count"])
        summary = room.to_summary_dict()
        self.assertIn("name", summary)
        self.assertIn("walls", summary)
        self.assertIn("constraints", summary)
        self.assertTrue(summary["plumbing"],
                        "sink constraint must flip plumbing flag")
        self.assertEqual(len(summary["walls"]), 2)
        self.assertEqual(len(summary["constraints"]), 1)
        self.assertEqual(summary["constraints"][0]["type_label"], "Sink")
        self.assertEqual(summary["shape_label"], "L-Shape")

    # ------------------------------------------------------------------
    # Phase 6.2 — Room Templates library seed.
    # ------------------------------------------------------------------

    def test_room_templates_seed_present(self):
        """4 seed room templates should be loaded with parsable JSON."""
        import json
        templates = self.env["southbrook.room.template"].search([])
        self.assertGreaterEqual(len(templates), 4,
                                "expected at least 4 seed templates")
        for t in templates:
            walls = json.loads(t.walls_json or "[]")
            constraints = json.loads(t.constraints_json or "[]")
            self.assertIsInstance(walls, list)
            self.assertIsInstance(constraints, list)
            if t.layout_shape:
                # Walls list non-empty for templates with a shape
                self.assertGreater(len(walls), 0, f"{t.name}: empty walls_json")
