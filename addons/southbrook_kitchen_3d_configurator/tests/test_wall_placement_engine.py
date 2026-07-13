# SPDX-License-Identifier: LGPL-3.0-only
"""PR4 — backend configurator wall-aware placement.

The bug: PR1 (wall picker -> state.activeWall) + PR2 (`wall` persisted)
together let a cabinet be assigned to a non-back wall, but save_design's
`line_vals` (controllers/main.py) always persisted the raw CLIENT-computed
x/y/z/rotation (which `_addCabinetFromProduct` only ever computes for the
BACK wall — see docs/2026-07-12-renderer-contract.md). Nothing on the
backend save path consulted the pure `kitchen_layout_engine.layout(...)`
the website's `_sb_place_line_on_wall` already delegates to.

Fix: `save_design` now calls the new shared model method
`southbrook.kitchen.design._place_lines_on_wall(lines)` (PR4) for every
non-back-wall configurator line AFTER it is created/written, so the
engine's pose overwrites the client's back-wall-only guess. Back-wall
lines are left exactly as the client sent them (backward compat — the
client's back-wall packing is correct and must not change).

Covers:
  * a wall="left" item's PERSISTED pose is the ENGINE's — not the raw
    client x/z/rotation — after save_design.
  * a wall="back" (or omitted-wall) item's pose is UNCHANGED — exactly
    what the client sent, byte-for-byte.
  * save_design's response additively carries `placed` — the
    engine-updated poses for the wall lines it moved — so the client can
    apply them without a reload (PR4 task 3).

Design: exercise the controller method directly with a stubbed
`request`, same pattern as the sibling `test_wall_persistence.py`.
"""
from contextlib import contextmanager
from unittest.mock import MagicMock

from odoo.tests import TransactionCase, tagged

from odoo.addons.southbrook_kitchen_3d_configurator.controllers import (
    main as ctrl_main,
)


@contextmanager
def stubbed_request(env, user=None):
    saved = ctrl_main.request
    mock = MagicMock()
    mock.env = env if user is None else env(user=user.id)
    mock.session = {}
    mock.params = {}
    ctrl_main.request = mock
    try:
        yield mock
    finally:
        ctrl_main.request = saved


@tagged("post_install", "-at_install", "southbrook",
        "southbrook_kitchen_3d_configurator", "wall_placement_engine")
class TestWallPlacementEngine(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner = cls.env["res.partner"].create({
            "name": "Kitchen 3D Wall-Placement Test Customer",
            "email": "kitchen3d.wallplacement@southbrook.test",
        })
        cls.design = cls.env["southbrook.kitchen.design"].create({
            "name": "Wall-placement-engine test",
            "partner_id": cls.partner.id,
            "room_width_in": 120,
            "room_depth_in": 96,
            "room_height_in": 96,
        })

        # Catalog-conforming cabinet — same recipe as test_wall_persistence.py.
        # No southbrook_width_in override -> controller default (24.0in),
        # which the test relies on to predict the engine's exact pose.
        cls.tmpl = cls.env["product.template"].create({
            "name": "Wall-Placement Test Cabinet",
            "type": "consu",
            "sale_ok": True,
            "list_price": 500.0,
        })
        cls.tmpl.southbrook_is_cabinet = True
        cls.tmpl.southbrook_cabinet_type = "base"
        cls.product = cls.tmpl.product_variant_id
        assert cls.product, "expected auto-created variant"

    def _controller(self):
        return ctrl_main.SouthbrookKitchenConfiguratorController()

    def _save(self, items, design_id=None):
        controller = self._controller()
        with stubbed_request(self.env):
            result = controller.save_design(
                name=self.design.name,
                room={"width_in": 120, "depth_in": 96, "height_in": 96},
                items=items,
                partner_id=self.partner.id,
                design_id=self.design.id if design_id is None else design_id,
            )
        lines = self.env["southbrook.kitchen.design.line"].search([
            ("design_id", "=", self.design.id),
            ("origin", "=", "configurator"),
        ])
        return result, lines

    # ------------------------------------------------------------------
    def test_left_wall_cabinet_gets_engine_pose_not_client_pose(self):
        """A wall='left' cabinet's persisted pose must be the ENGINE's
        (x near the wall face, z advancing along the run, rotation_deg
        90 for the left wall) — NOT the raw client x/z/rotation, which
        `_addCabinetFromProduct` only ever computes correctly for the
        back wall."""
        client_garbage_x = 999.0
        result, lines = self._save([{
            "product_id":     self.product.id,
            "layout_key":     "wallplace-left-1",
            # A client-computed BACK-wall x (garbage on a left wall) plus
            # rotation_deg=0 (also wrong for "left" — the engine must
            # overwrite both).
            "x_position_in":  client_garbage_x,
            "y_position_in":  0,
            "z_position_in":  0,
            "rotation_deg":   0,
            "wall":           "left",
        }])
        self.assertNotIn("error", result, result)
        self.assertEqual(len(lines), 1)
        line = lines[0]
        self.assertEqual(line.wall, "left")

        # The engine's left-wall placement: 24in-wide cabinet, base_run
        # zone (cross_offset=0, y_floor=0), first (only) cabinet on the
        # wall -> centre = width/2 = 12in along Z; x sits at the wall
        # face (cross_offset=0); rotation_deg=90 (left wall).
        self.assertAlmostEqual(line.rotation_deg, 90.0, places=2)
        self.assertAlmostEqual(line.x_position_in, 0.0, places=2)
        self.assertAlmostEqual(line.z_position_in, 12.0, places=2)
        self.assertAlmostEqual(line.y_position_in, 0.0, places=2)
        # The raw client garbage must NOT have survived.
        self.assertNotAlmostEqual(line.x_position_in, client_garbage_x, places=2)

    def test_back_wall_cabinet_pose_is_left_alone(self):
        """A wall='back' cabinet keeps EXACTLY the pose the client sent —
        the engine must not touch back-wall lines (backward compat: the
        client's own back-wall packing is correct and must not change)."""
        result, lines = self._save([{
            "product_id":     self.product.id,
            "layout_key":     "wallplace-back-1",
            "x_position_in":  42.0,
            "y_position_in":  0.0,
            "z_position_in":  0.0,
            "rotation_deg":   0.0,
            "wall":           "back",
        }])
        self.assertNotIn("error", result, result)
        self.assertEqual(len(lines), 1)
        line = lines[0]
        self.assertEqual(line.wall, "back")
        self.assertAlmostEqual(line.x_position_in, 42.0, places=2)
        self.assertAlmostEqual(line.z_position_in, 0.0, places=2)
        self.assertAlmostEqual(line.rotation_deg, 0.0, places=2)

    def test_omitted_wall_defaults_to_back_and_is_left_alone(self):
        """No `wall` key at all -> defaults to 'back' (test_wall_persistence
        already covers the default itself); this test guards that the
        PR4 engine-placement call does NOT fire for it either."""
        result, lines = self._save([{
            "product_id":     self.product.id,
            "layout_key":     "wallplace-noball-1",
            "x_position_in":  17.0,
            "y_position_in":  0.0,
            "z_position_in":  0.0,
            "rotation_deg":   0.0,
        }])
        self.assertNotIn("error", result, result)
        self.assertEqual(len(lines), 1)
        line = lines[0]
        self.assertEqual(line.wall, "back")
        self.assertAlmostEqual(line.x_position_in, 17.0, places=2)

    def test_save_response_includes_placed_poses_for_wall_lines(self):
        """save_design's response additively carries `placed`: the
        engine-updated pose for each non-back-wall line it moved, keyed
        by layout_key, so the client can apply it live without a
        reload (PR4 task 3). A back-wall line must NOT appear in it."""
        result, lines = self._save([
            {
                "product_id":     self.product.id,
                "layout_key":     "wallplace-mixed-left",
                "x_position_in":  999.0,
                "wall":           "left",
            },
            {
                "product_id":     self.product.id,
                "layout_key":     "wallplace-mixed-back",
                "x_position_in":  5.0,
                "wall":           "back",
            },
        ])
        self.assertNotIn("error", result, result)
        self.assertIn("placed", result, result)
        placed_by_key = {p["layout_key"]: p for p in result["placed"]}
        self.assertIn("wallplace-mixed-left", placed_by_key)
        self.assertNotIn("wallplace-mixed-back", placed_by_key)

        left_line = lines.filtered(
            lambda l: l.layout_key == "wallplace-mixed-left")
        placed = placed_by_key["wallplace-mixed-left"]
        self.assertAlmostEqual(placed["x_position_in"], left_line.x_position_in, places=2)
        self.assertAlmostEqual(placed["z_position_in"], left_line.z_position_in, places=2)
        self.assertAlmostEqual(placed["rotation_deg"], left_line.rotation_deg, places=2)

    def test_second_save_reflects_run_seq_progression_on_wall(self):
        """Two cabinets added to the left wall in the same save must
        NOT overlap — the engine packs them one after another along the
        wall's run (z advancing), exactly as it already does for the
        website's /design-3d/add path. (save_design does not accept a
        `run_seq` key from the payload — order falls out of creation/
        sequence order, same as every other configurator-origin line.)"""
        result, lines = self._save([
            {
                "product_id":     self.product.id,
                "layout_key":     "wallplace-run-1",
                "wall":           "left",
            },
            {
                "product_id":     self.product.id,
                "layout_key":     "wallplace-run-2",
                "wall":           "left",
            },
        ])
        self.assertNotIn("error", result, result)
        self.assertEqual(len(lines), 2)
        l1 = lines.filtered(lambda l: l.layout_key == "wallplace-run-1")
        l2 = lines.filtered(lambda l: l.layout_key == "wallplace-run-2")
        # First cabinet centres at 12in; second starts where the first
        # ends (24in) and centres at 36in.
        self.assertAlmostEqual(l1.z_position_in, 12.0, places=2)
        self.assertAlmostEqual(l2.z_position_in, 36.0, places=2)
        self.assertAlmostEqual(l1.rotation_deg, 90.0, places=2)
        self.assertAlmostEqual(l2.rotation_deg, 90.0, places=2)
