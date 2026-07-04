# SPDX-License-Identifier: LGPL-3.0-only
"""2026-07-03 QA fixes — room geometry validation + edit-mode /room/update.

Covers the defects found in the "Set Up Your Room" wizard E2E pass:
  * negative wall length must be rejected (never subtracted from total)
  * out-of-bounds constraint (distance + width > wall length) rejected
  * constraint-vs-constraint overlap flagged in the summary (warn, not block)
  * re-opening + saving an edited room UPDATES it (no duplicate / blank-out)
  * shrinking wall count deletes removed walls + unplaces their cabinets
  * the seeded Room Templates are all geometrically valid

Same harness as test_room_api.py — TransactionCase + stubbed_request.
"""
from contextlib import contextmanager
from unittest.mock import MagicMock

from odoo.tests import TransactionCase, tagged

from odoo.addons.southbrook_estimating_website.controllers import (
    room_api as ctrl_room,
    main as ctrl_main,
)


@contextmanager
def stubbed_request(env, user=None):
    saved_room = ctrl_room.request
    saved_main = ctrl_main.request
    mock = MagicMock()
    mock.env = env if user is None else env(user=user.id)
    mock.session = {}
    mock.params = {}
    ctrl_room.request = mock
    ctrl_main.request = mock
    try:
        yield mock
    finally:
        ctrl_room.request = saved_room
        ctrl_main.request = saved_main


@tagged("post_install", "-at_install", "southbrook", "southbrook_room_geom")
class TestRoomGeometry(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "Geom Test Customer",
            "email": "geom_test@southbrook.test",
        })
        cls.order = cls.env["sale.order"].create({
            "partner_id": cls.partner.id,
        })
        cls.controller = ctrl_room.SouthbrookRoomApi()
        cls.Room = cls.env["southbrook.room"]

    # ------------------------------------------------------------------
    # validate_geometry — pure helper (source of truth)
    # ------------------------------------------------------------------
    def test_validate_negative_wall_length(self):
        errors = self.Room.validate_geometry(
            [{"length_mm": 3000}, {"length_mm": -500}], [])
        self.assertTrue(errors)
        self.assertIn("Wall B", errors[0])

    def test_validate_out_of_bounds_constraint(self):
        # Sink @2800 + 900 wide on a 3000 wall → 700mm past the edge.
        errors = self.Room.validate_geometry(
            [{"length_mm": 3000}],
            [{"wall_index": 0, "constraint_type": "sink",
              "distance_from_left_mm": 2800, "width_mm": 900}],
        )
        self.assertTrue(errors)
        self.assertIn("700mm", errors[0])

    def test_validate_negative_ceiling(self):
        errors = self.Room.validate_geometry(
            [{"length_mm": 3000}], [], ceiling_height_mm=-100)
        self.assertTrue(any("Ceiling" in e for e in errors))

    def test_validate_clean_payload_passes(self):
        errors = self.Room.validate_geometry(
            [{"length_mm": 3600}],
            [{"wall_index": 0, "constraint_type": "window",
              "distance_from_left_mm": 300, "width_mm": 1200}],
            ceiling_height_mm=2400,
        )
        self.assertEqual(errors, [])

    def test_validate_constraint_exactly_at_edge_ok(self):
        # distance + width == wall_length is flush, not over.
        errors = self.Room.validate_geometry(
            [{"length_mm": 1800}],
            [{"wall_index": 0, "constraint_type": "sink",
              "distance_from_left_mm": 1200, "width_mm": 600}],
        )
        self.assertEqual(errors, [])

    # ------------------------------------------------------------------
    # /room/create rejects bad geometry
    # ------------------------------------------------------------------
    def test_create_rejects_negative_length(self):
        with stubbed_request(self.env):
            res = self.controller.southbrook_api_room_create(
                self.order.id, name="Bad", layout_shape="l_shape",
                walls=[{"length_mm": 3000}, {"length_mm": -500}],
            )
        self.assertEqual(res.get("error"), "invalid_geometry")
        # No room persisted.
        self.assertFalse(self.order.room_ids)

    def test_create_rejects_out_of_bounds_constraint(self):
        with stubbed_request(self.env):
            res = self.controller.southbrook_api_room_create(
                self.order.id, name="Bad", layout_shape="straight",
                walls=[{"length_mm": 3000}],
                constraints=[{"wall_index": 0, "constraint_type": "sink",
                              "distance_from_left_mm": 2800, "width_mm": 900}],
            )
        self.assertEqual(res.get("error"), "invalid_geometry")
        self.assertFalse(self.order.room_ids)

    # ------------------------------------------------------------------
    # Overlap → WARN via the summary (wall.has_constraint_overlap), not
    # a hard block. A sink beneath a window is a real possibility.
    # ------------------------------------------------------------------
    def test_overlap_flagged_not_blocked(self):
        room = self.Room.create({
            "name": "Overlap", "order_id": self.order.id,
            "layout_shape": "straight",
            "wall_ids": [(0, 0, {"name": "A", "length_mm": 3600})],
        })
        wall = room.wall_ids[0]
        self.env["southbrook.room.constraint"].create([
            {"wall_id": wall.id, "constraint_type": "window",
             "distance_from_left_mm": 1200, "width_mm": 1500},
            {"wall_id": wall.id, "constraint_type": "sink",
             "distance_from_left_mm": 1500, "width_mm": 900},
        ])
        wall.invalidate_recordset()
        self.assertTrue(wall.has_constraint_overlap)
        self.assertTrue(wall.has_conflicts)
        self.assertFalse(wall.has_constraint_out_of_bounds)

    def test_out_of_bounds_existing_data_flagged(self):
        room = self.Room.create({
            "name": "OOB", "order_id": self.order.id,
            "layout_shape": "straight",
            "wall_ids": [(0, 0, {"name": "A", "length_mm": 3000})],
        })
        wall = room.wall_ids[0]
        self.env["southbrook.room.constraint"].create({
            "wall_id": wall.id, "constraint_type": "sink",
            "distance_from_left_mm": 2800, "width_mm": 900,
        })
        wall.invalidate_recordset()
        self.assertTrue(wall.has_constraint_out_of_bounds)
        self.assertTrue(wall.has_conflicts)

    # ------------------------------------------------------------------
    # Edit mode — update an existing room, no duplicate / blank-out
    # ------------------------------------------------------------------
    def test_edit_updates_existing_no_duplicate(self):
        with stubbed_request(self.env):
            created = self.controller.southbrook_api_room_create(
                self.order.id, name="Original", layout_shape="l_shape",
                walls=[{"name": "Wall A", "length_mm": 3600},
                       {"name": "Wall B", "length_mm": 2400}],
                constraints=[{"wall_index": 0, "constraint_type": "window",
                              "distance_from_left_mm": 300, "width_mm": 1200}],
            )
        self.assertTrue(created.get("ok"), created)
        room = created["room"]
        wall_ids = [w["id"] for w in room["walls"]]
        with stubbed_request(self.env):
            updated = self.controller.southbrook_api_room_update(
                self.order.id, room["id"],
                name="Renamed",
                ceiling_height_mm=2700,
                walls=[{"id": wall_ids[0], "name": "Wall A", "length_mm": 4000},
                       {"id": wall_ids[1], "name": "Wall B", "length_mm": 2400}],
                constraints=[{"wall_index": 0, "constraint_type": "sink",
                              "distance_from_left_mm": 1800, "width_mm": 900}],
            )
        self.assertTrue(updated.get("ok"), updated)
        # Same room id — no duplicate.
        self.assertEqual(updated["room"]["id"], room["id"])
        self.assertEqual(len(self.order.room_ids), 1)
        self.assertEqual(updated["room"]["name"], "Renamed")
        self.assertEqual(updated["room"]["ceiling_height_mm"], 2700)
        # Wall A length updated in place (same wall id).
        wall_a = updated["room"]["walls"][0]
        self.assertEqual(wall_a["id"], wall_ids[0])
        self.assertEqual(wall_a["length_mm"], 4000)
        # Constraints fully replaced: the window is gone, the sink is in.
        all_constraints = [
            c for w in updated["room"]["walls"] for c in w["constraints"]]
        self.assertEqual(len(all_constraints), 1)
        self.assertEqual(all_constraints[0]["constraint_type"], "sink")

    def test_edit_shrink_walls_deletes_and_unplaces(self):
        with stubbed_request(self.env):
            created = self.controller.southbrook_api_room_create(
                self.order.id, name="Shrink", layout_shape="u_shape",
                walls=[{"name": "A", "length_mm": 3000},
                       {"name": "B", "length_mm": 2000},
                       {"name": "C", "length_mm": 3000}],
            )
        room = created["room"]
        wall_ids = [w["id"] for w in room["walls"]]
        # Place a cabinet line on wall C (the one we'll delete).
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id, "name": "On Wall C",
            "wall_id": wall_ids[2], "position_from_left_mm": 100,
        })
        with stubbed_request(self.env):
            updated = self.controller.southbrook_api_room_update(
                self.order.id, room["id"],
                layout_shape="l_shape",
                walls=[{"id": wall_ids[0], "name": "A", "length_mm": 3000},
                       {"id": wall_ids[1], "name": "B", "length_mm": 2000}],
                constraints=[],
                reconcile=True,
            )
        self.assertTrue(updated.get("ok"), updated)
        self.assertEqual(len(updated["room"]["walls"]), 2)
        # Wall C is gone.
        self.assertFalse(
            self.env["southbrook.room.wall"].browse(wall_ids[2]).exists())
        # Its cabinet line was unplaced (ondelete=set null), not deleted.
        line.invalidate_recordset()
        self.assertTrue(line.exists())
        self.assertFalse(line.wall_id)

    # ------------------------------------------------------------------
    # Regressions from the 2026-07-04 code review
    # ------------------------------------------------------------------
    def test_partial_wall_update_without_reconcile_keeps_other_walls(self):
        """Single-wall resize (no reconcile flag) must NOT delete the rest.

        Review finding: the Room Layout tab's _onPlanWallResizeEnd POSTs a
        one-wall list; the full-reconcile delete would wipe the other walls.
        """
        with stubbed_request(self.env):
            created = self.controller.southbrook_api_room_create(
                self.order.id, name="Multi", layout_shape="u_shape",
                walls=[{"name": "A", "length_mm": 3000},
                       {"name": "B", "length_mm": 2000},
                       {"name": "C", "length_mm": 3000}])
        room = created["room"]
        wids = [w["id"] for w in room["walls"]]
        with stubbed_request(self.env):
            res = self.controller.southbrook_api_room_update(
                self.order.id, room["id"],
                walls=[{"id": wids[0], "length_mm": 3400}])
        self.assertTrue(res.get("ok"), res)
        self.assertEqual(len(res["room"]["walls"]), 3)
        self.assertTrue(all(
            self.env["southbrook.room.wall"].browse(w).exists() for w in wids))
        wall_a = next(w for w in res["room"]["walls"] if w["id"] == wids[0])
        self.assertEqual(wall_a["length_mm"], 3400)

    def test_edit_preserves_height_from_floor_and_notes(self):
        """Editing a room must not wipe constraint sill height / notes."""
        with stubbed_request(self.env):
            created = self.controller.southbrook_api_room_create(
                self.order.id, name="Sill", layout_shape="straight",
                walls=[{"name": "A", "length_mm": 3600}])
        room = created["room"]
        wid = room["walls"][0]["id"]
        self.env["southbrook.room.constraint"].create({
            "wall_id": wid, "constraint_type": "window",
            "distance_from_left_mm": 300, "width_mm": 1200,
            "height_from_floor_mm": 900, "notes": "Fixed glazing"})
        with stubbed_request(self.env):
            res = self.controller.southbrook_api_room_update(
                self.order.id, room["id"], name="Sill Renamed",
                walls=[{"id": wid, "name": "A", "length_mm": 3600}],
                constraints=[{"wall_index": 0, "constraint_type": "window",
                              "distance_from_left_mm": 300, "width_mm": 1200,
                              "height_from_floor_mm": 900,
                              "notes": "Fixed glazing"}],
                reconcile=True)
        self.assertTrue(res.get("ok"), res)
        c = res["room"]["walls"][0]["constraints"][0]
        self.assertEqual(c["height_from_floor_mm"], 900)
        self.assertEqual(c["notes"], "Fixed glazing")

    def test_malformed_constraint_payload_does_not_wipe_existing(self):
        """A bad constraints payload is rejected BEFORE the unlink."""
        with stubbed_request(self.env):
            created = self.controller.southbrook_api_room_create(
                self.order.id, name="Atomic", layout_shape="straight",
                walls=[{"name": "A", "length_mm": 3600}],
                constraints=[{"wall_index": 0, "constraint_type": "window",
                              "distance_from_left_mm": 300, "width_mm": 1200}])
        room = created["room"]
        wid = room["walls"][0]["id"]
        with stubbed_request(self.env):
            res = self.controller.southbrook_api_room_update(
                self.order.id, room["id"],
                walls=[{"id": wid, "name": "A", "length_mm": 3600}],
                constraints=[
                    {"wall_index": 0, "constraint_type": "sink",
                     "distance_from_left_mm": 1800, "width_mm": 900},
                    {"wall_index": 0, "distance_from_left_mm": 100,
                     "width_mm": 200}],
                reconcile=True)
        self.assertEqual(res.get("error"), "invalid", res)
        design = self.env["southbrook.room"].browse(room["id"])
        design.invalidate_recordset()
        self.assertEqual(len(design.constraint_ids), 1)
        self.assertEqual(design.constraint_ids.constraint_type, "window")

    def test_validate_non_numeric_constraint_width(self):
        errors = self.Room.validate_geometry(
            [{"length_mm": 3000}],
            [{"wall_index": 0, "constraint_type": "sink",
              "distance_from_left_mm": 100, "width_mm": "abc"}])
        self.assertTrue(any("must be a number" in e for e in errors), errors)

    def test_shrink_wall_without_resending_constraints_flags_oob(self):
        """Resizing a wall shorter than an existing constraint is rejected
        even when the caller doesn't resend the constraint."""
        with stubbed_request(self.env):
            created = self.controller.southbrook_api_room_create(
                self.order.id, name="Shrink2", layout_shape="straight",
                walls=[{"name": "A", "length_mm": 3000}],
                constraints=[{"wall_index": 0, "constraint_type": "sink",
                              "distance_from_left_mm": 2000, "width_mm": 900}])
        room = created["room"]
        wid = room["walls"][0]["id"]
        with stubbed_request(self.env):
            res = self.controller.southbrook_api_room_update(
                self.order.id, room["id"],
                walls=[{"id": wid, "length_mm": 2500}])
        self.assertEqual(res.get("error"), "invalid_geometry", res)

    # ------------------------------------------------------------------
    # 2026-07-03 — conflict_count exposed in the /room serializer payload
    # so the Room Layout metrics table can render an exact count instead
    # of a bare boolean.
    # ------------------------------------------------------------------
    def test_room_payload_includes_conflict_count(self):
        """_serialize_room emits conflict_count per wall alongside
        has_conflicts. Overrun constraint (2800 + 600 = 3400 > 3000)
        must surface as conflict_count == 1."""
        room = self.Room.create({
            "name": "PayloadCount", "order_id": self.order.id,
            "layout_shape": "straight",
            "wall_ids": [(0, 0, {"name": "A", "length_mm": 3000})],
        })
        wall = room.wall_ids[0]
        self.env["southbrook.room.constraint"].create({
            "wall_id": wall.id, "constraint_type": "sink",
            "distance_from_left_mm": 2800, "width_mm": 600,
        })
        payload = ctrl_room._serialize_room(room)
        wall_dict = payload["walls"][0]
        self.assertIn("conflict_count", wall_dict)
        self.assertTrue(wall_dict["has_conflicts"])
        self.assertEqual(wall_dict["conflict_count"], 1)

    def test_place_on_wall_payload_includes_conflict_count(self):
        """The place-on-wall response wall dict carries conflict_count."""
        room = self.Room.create({
            "name": "PlaceCount", "order_id": self.order.id,
            "layout_shape": "straight",
            "wall_ids": [(0, 0, {"name": "A", "length_mm": 3000})],
        })
        wall = room.wall_ids[0]
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id, "name": "Place me",
        })
        with stubbed_request(self.env):
            res = self.controller.southbrook_api_line_place_on_wall(
                self.order.id, line.id, wall_id=wall.id,
                position_from_left_mm=100)
        self.assertTrue(res.get("ok"), res)
        self.assertIn("conflict_count", res["wall"])

    def test_edit_rejects_bad_geometry(self):
        with stubbed_request(self.env):
            created = self.controller.southbrook_api_room_create(
                self.order.id, name="R", layout_shape="straight",
                walls=[{"name": "A", "length_mm": 3000}],
            )
        room = created["room"]
        wid = room["walls"][0]["id"]
        with stubbed_request(self.env):
            res = self.controller.southbrook_api_room_update(
                self.order.id, room["id"],
                walls=[{"id": wid, "name": "A", "length_mm": -1}],
                constraints=[],
            )
        self.assertEqual(res.get("error"), "invalid_geometry")
        # Wall length unchanged.
        self.env["southbrook.room.wall"].browse(wid).invalidate_recordset()
        self.assertEqual(
            self.env["southbrook.room.wall"].browse(wid).length_mm, 3000)

    def test_scalar_only_update_preserves_walls(self):
        # The summary unit toggle POSTs {unit_preference} alone — it must
        # NOT wipe walls/constraints (guarded on `is not None`).
        with stubbed_request(self.env):
            created = self.controller.southbrook_api_room_create(
                self.order.id, name="R", layout_shape="straight",
                walls=[{"name": "A", "length_mm": 3000}],
            )
        room = created["room"]
        with stubbed_request(self.env):
            res = self.controller.southbrook_api_room_update(
                self.order.id, room["id"], unit_preference="imperial")
        self.assertTrue(res.get("ok"), res)
        self.assertEqual(res["room"]["unit_preference"], "imperial")
        self.assertEqual(len(res["room"]["walls"]), 1)

    # ------------------------------------------------------------------
    # Seed templates must all be geometrically valid (the L-shape overlap
    # regression that started this).
    # ------------------------------------------------------------------
    def test_seed_templates_all_valid(self):
        import json
        templates = self.env["southbrook.room.template"].search([])
        self.assertTrue(templates)
        for t in templates:
            walls = json.loads(t.walls_json or "[]")
            constraints = json.loads(t.constraints_json or "[]")
            errors = self.Room.validate_geometry(
                walls, constraints, t.ceiling_height_mm)
            self.assertEqual(
                errors, [],
                msg=f"template {t.name!r} has invalid geometry: {errors}")
            # Also assert no overlaps among its constraints per wall.
            by_wall = {}
            for c in constraints:
                by_wall.setdefault(c["wall_index"], []).append(
                    (c.get("distance_from_left_mm", 0),
                     c.get("distance_from_left_mm", 0) + c.get("width_mm", 0)))
            for wi, spans in by_wall.items():
                spans.sort()
                for i in range(1, len(spans)):
                    self.assertGreaterEqual(
                        spans[i][0], spans[i - 1][1],
                        msg=f"template {t.name!r} wall {wi} constraints overlap")
