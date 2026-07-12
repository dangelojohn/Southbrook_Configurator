# SPDX-License-Identifier: LGPL-3.0-only
"""Coordinate-contract compliance for the cabinet mesh builders.

Makes COORDINATE_CONTRACT.md ENFORCEABLE, not just documented: every builder
must consume all four placement fields (x/y/z_position_in + rotation_deg)
with no coordinate overloading. Implemented as a LIVING LEDGER so it is
useful today (mid-migration) and turns into a hard gate automatically:

  * a debt-free (migrated) builder MUST consume all four — hard-enforced;
  * a builder may omit ONLY the fields listed in its known migration debt;
  * dropping a field a builder currently uses (missing > debt) FAILS —
    catching regressions and any NEW coordinate reinterpretation;
  * if a builder quietly becomes compliant, its stale debt entry FAILS —
    forcing the ledger to shrink (auto-signals the renderer migrated it).

As the renderer coordinate-model unification migrates each builder, shrink
its _KNOWN_DEBT entry to set(); full enforcement then turns on for it.

PR3.0 (2026-07-12) update: `wall_cabinet.esm.js` and `other_cabinets.esm.js`
now correctly consume `y_position_in` for mount-height/elevation (was
misreading `z_position_in` as height — the matrix's riskiest finding).
Their debt entries move from "y unread" to "z unread" (z is now correctly
left at 0/unused by the legacy back-wall render path pending PR3.1's
dispatch unification) — this is a debt *swap*, not a payoff, and is
intentional here. The ledger's own file-level substring check cannot by
itself prove PLACEMENT correctness (a masked gap the coordinate-contract
matrix's evidence appendix calls out explicitly for this file), so
`TestWallMountHeightSemantics` below adds real behavioral assertions on
top of it, exercising the actual writer end to end.
"""
import os
from contextlib import contextmanager
from unittest.mock import MagicMock

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.southbrook_kitchen_3d_configurator.controllers import (
    main as ctrl_main,
)

_REQUIRED = ("x_position_in", "y_position_in", "z_position_in", "rotation_deg")

# Fields each builder does NOT yet consume, pending the renderer coordinate-
# model unification (see COORDINATE_CONTRACT.md, "Known migration debt").
_KNOWN_DEBT = {
    "base_cabinet.esm.js":   {"y_position_in", "z_position_in", "rotation_deg"},
    # PR3.0: y_position_in is now correctly consumed as mount-height/
    # elevation (wbY). z_position_in is not read by the legacy back-wall
    # path (it is contractually 0 there; PR3.1's central group transform
    # already handles it for rotated/side-wall placement) — still debt.
    "wall_cabinet.esm.js":   {"z_position_in", "rotation_deg"},
    # PR3.0: buildOtherCabinet / buildEndCapPanel likewise now read
    # y_position_in (y0) instead of misreading z as height.
    # buildFillerPanel still reads neither (separate, pre-existing gap).
    "other_cabinets.esm.js": {"z_position_in", "rotation_deg"},
}


class TestCoordinateContractCompliance(TransactionCase):

    def _read(self, fname):
        path = os.path.join(os.path.dirname(__file__), "..", "static", "src",
                            "js", "canvas", fname)
        with open(path) as fh:
            return fh.read()

    def _missing(self, fname):
        src = self._read(fname)
        return {f for f in _REQUIRED if f not in src}

    def test_builders_conform_to_coordinate_contract(self):
        for fname, debt in _KNOWN_DEBT.items():
            missing = self._missing(fname)
            regressed = missing - debt
            self.assertEqual(
                regressed, set(),
                "%s dropped contract field(s) %s not in known debt — a "
                "coordinate regression (COORDINATE_CONTRACT.md)"
                % (fname, sorted(regressed)))
            if not debt:
                self.assertEqual(
                    missing, set(),
                    "%s is debt-free but omits %s" % (fname, sorted(missing)))

    def test_central_placement_consumes_all_fields(self):
        # Placement (x/y/z_position_in + rotation_deg) is applied CENTRALLY in
        # KitchenCanvas._placeCabinetGroup per the contract; builders build in
        # a local frame and let the group carry the world transform. This
        # asserts the central transform consumes all four contract fields —
        # the real conformance signal now that per-builder placement is gone.
        path = os.path.join(os.path.dirname(__file__), "..", "static", "src",
                            "js", "canvas", "kitchen_canvas.esm.js")
        with open(path) as fh:
            src = fh.read()
        for field in _REQUIRED:
            self.assertIn(field, src,
                          "central placement (kitchen_canvas) omits %s" % field)

    def test_no_stale_debt_entries(self):
        """A builder that quietly became compliant leaves a stale debt entry.
        Fail so the ledger is shrunk (this is how the renderer migration
        auto-turns-on enforcement per builder)."""
        stale = []
        for fname, debt in _KNOWN_DEBT.items():
            now_used = debt - self._missing(fname)
            if now_used:
                stale.append((fname, sorted(now_used)))
        self.assertEqual(
            stale, [],
            "stale migration-debt entries — builder now consumes these; "
            "remove from _KNOWN_DEBT: %s" % stale)


@contextmanager
def _stubbed_request(env, user=None):
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
        "southbrook_kitchen_3d_configurator", "coordinate_contract")
class TestWallMountHeightSemantics(TransactionCase):
    """PR3.0 — placement-SEMANTICS assertions, not field-name presence.

    `test_coordinate_contract.py`'s ledger above can only prove a field
    NAME appears somewhere in a builder file — it cannot prove a wall
    cabinet's mount height actually lands in y_position_in, or that
    z_position_in is actually 0 for a back-wall upper (the matrix's own
    evidence appendix flags this as a real, undetected gap). This class
    closes that gap by exercising the real writer
    (controllers/main.py's /layout route) end to end and asserting on
    the emitted values.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmpl_base = cls.env["product.template"].create({
            "name": "Coord-Contract Base Cabinet",
            "type": "consu",
            "sale_ok": True,
            "list_price": 500.0,
        })
        cls.tmpl_base.southbrook_is_cabinet = True
        cls.tmpl_base.southbrook_cabinet_type = "base"
        cls.tmpl_base.southbrook_width_in = 24.0
        cls.tmpl_base.southbrook_height_in = 34.5

        cls.tmpl_wall = cls.env["product.template"].create({
            "name": "Coord-Contract Wall Cabinet",
            "type": "consu",
            "sale_ok": True,
            "list_price": 350.0,
        })
        cls.tmpl_wall.southbrook_is_cabinet = True
        cls.tmpl_wall.southbrook_cabinet_type = "wall"
        cls.tmpl_wall.southbrook_height_in = 30.0

    def _controller(self):
        return ctrl_main.SouthbrookKitchenConfiguratorController()

    def test_layout_endpoint_writes_wall_mount_height_into_y_with_z_flush(self):
        """A back-wall upper's D8-computed mount height must land in
        y_position_in; z_position_in must be 0 (flush to the back wall)
        — the canonical semantics this PR migrates to. Pre-PR3.0 this
        writer emitted (y=0, z=mount_height); asserting the opposite
        here is the writer-side red-before-green pin."""
        controller = self._controller()
        with _stubbed_request(self.env):
            result = controller.layout(room_width_in=48, room_depth_in=96,
                                        room_height_in=96)
        self.assertEqual(result.get("error", ""), "")
        wall_items = [it for it in result["items"]
                      if it["cabinet_type"] == "wall"]
        base_items = [it for it in result["items"]
                      if it["cabinet_type"] == "base"]
        self.assertTrue(wall_items, "expected at least one wall item")
        self.assertTrue(base_items, "expected at least one base item")

        for it in wall_items:
            self.assertGreater(
                it["y_position_in"], 0,
                "wall cabinet mount height must live in y_position_in "
                "(canonical elevation field), got y=%r" % it["y_position_in"])
            self.assertEqual(
                it["z_position_in"], 0.0,
                "a back-wall upper's z_position_in must be 0 (flush to "
                "the back wall) post-PR3.0, got z=%r" % it["z_position_in"])

        # Base (floor-standing) cabinets are unaffected: floor-flush,
        # y=0 and z=0, as before this migration.
        for it in base_items:
            self.assertEqual(it["y_position_in"], 0.0)
            self.assertEqual(it["z_position_in"], 0.0)

    def test_layout_endpoint_wall_mount_height_matches_d8_alignment(self):
        """The numeric mount-height VALUE is unchanged by this migration
        — only which field carries it. Confirms y_position_in equals the
        same D8 to_ceiling-alignment computation the old code used to
        put in z_position_in (base_h + ctr_t + gap, or ceiling-relative)."""
        controller = self._controller()
        with _stubbed_request(self.env):
            result = controller.layout(
                room_width_in=48, room_depth_in=96, room_height_in=96,
                wall_cab_top_alignment="to_ceiling",
            )
        self.assertEqual(result.get("error", ""), "")
        wall_items = [it for it in result["items"]
                      if it["cabinet_type"] == "wall"]
        self.assertTrue(wall_items)
        expected_y = 96.0 - 30.0  # room_height_in - wall_h (to_ceiling)
        for it in wall_items:
            self.assertAlmostEqual(it["y_position_in"], expected_y, places=2)
            self.assertEqual(it["z_position_in"], 0.0)

    def test_generate_standard_layout_writes_wall_mount_height_into_y(self):
        """PR3.0 side-finding: `_generate_standard_layout` (the
        "Regenerate standard layout" button, action_generate_layout) is
        a THIRD writer independent of the /layout HTTP route and the
        _KITCHEN_TEMPLATE_PRESETS starter data — found while auditing
        every consumer of z_position_in in this module, beyond the PR3
        coordinate-contract matrix's original (renderer-file-scoped)
        review. It previously called self._create_line(wall_product,
        seq, x, 0.0, 54.0) — the same y=0/z=mount-height legacy shape.
        Fixed in lockstep; this pins the canonical (y=54, z=0) output."""
        design = self.env["southbrook.kitchen.design"].create({
            "name": "Generate-layout PR3.0 test",
            "room_width_in": 48, "room_depth_in": 96, "room_height_in": 96,
        })
        design._generate_standard_layout()
        wall_lines = design.cabinet_line_ids.filtered(
            lambda l: l.cabinet_type == "wall")
        base_lines = design.cabinet_line_ids.filtered(
            lambda l: l.cabinet_type == "base")
        self.assertTrue(wall_lines)
        self.assertTrue(base_lines)
        for wl in wall_lines:
            self.assertEqual(wl.y_position_in, 54.0)
            self.assertEqual(wl.z_position_in, 0.0)
        for bl in base_lines:
            self.assertEqual(bl.y_position_in, 0.0)
            self.assertEqual(bl.z_position_in, 0.0)


@tagged("post_install", "-at_install", "southbrook",
        "southbrook_kitchen_3d_configurator", "coordinate_contract")
class TestVerticalCollisionCheckPostMigration(TransactionCase):
    """PR3.0 side-finding — `_check_production_ready`'s "wall-cab
    vertical extent inside a tall's vertical extent" check
    (models/kitchen_design.py, was labelled Z_AXIS_COLLISION) read
    z_position_in as the vertical extent, the SAME "z-as-height"
    convention the PR3 coordinate-contract matrix flags for the
    renderer builders — just in a validation method the matrix's
    renderer-only review scope never examined.

    Left unfixed, migrating wall.z_position_in -> 0 without also fixing
    this reader would have collapsed BOTH wall and tall vertical
    references to 0, making every x-overlapping wall+tall pair falsely
    report a blocking collision on production-readiness check — a
    regression that would have shipped invisibly on the very first
    straight kitchen with a tall cabinet. Fixed in lockstep (now reads
    y_position_in, code renamed VERTICAL_COLLISION since it no longer
    means "along Z").
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "PR3.0 Vertical Collision Test Customer",
            "email": "kitchen3d.vcollision@southbrook.test",
        })
        cls.tmpl_wall = cls.env["product.template"].create({
            "name": "VCollision Wall Cabinet", "type": "consu",
            "sale_ok": True, "list_price": 350.0,
        })
        cls.tmpl_wall.southbrook_is_cabinet = True
        cls.tmpl_wall.southbrook_cabinet_type = "wall"
        cls.product_wall = cls.tmpl_wall.product_variant_id

        cls.tmpl_tall = cls.env["product.template"].create({
            "name": "VCollision Tall Cabinet", "type": "consu",
            "sale_ok": True, "list_price": 900.0,
        })
        cls.tmpl_tall.southbrook_is_cabinet = True
        cls.tmpl_tall.southbrook_cabinet_type = "tall"
        cls.product_tall = cls.tmpl_tall.product_variant_id

    def _design(self):
        return self.env["southbrook.kitchen.design"].create({
            "name": "Vertical collision test",
            "partner_id": self.partner.id,
            "room_width_in": 96, "room_depth_in": 96, "room_height_in": 96,
        })

    def _line(self, design, cabinet_type, product, x, y, height, width=18.0):
        return self.env["southbrook.kitchen.design.line"].create({
            "design_id": design.id, "product_id": product.id,
            "cabinet_type": cabinet_type,
            "layout_key": "%s-vcoll-%s" % (cabinet_type, x),
            "origin": "configurator",
            "x_position_in": x, "y_position_in": y, "z_position_in": 0.0,
            "width_in": width, "height_in": height, "depth_in": 12.0,
            "quantity": 1, "price_unit": 300.0,
        })

    def test_no_false_collision_when_short_tall_sits_below_elevated_wall(self):
        """Canonical post-PR3.0 shapes: a 54"-tall cabinet (vertical
        span 0-54) does NOT collide with a wall cabinet mounted at
        y=66 (span 66-96), even though they overlap on X and both used
        to read z_position_in=0 pre-fix (which WOULD have falsely
        collided)."""
        design = self._design()
        self._line(design, "tall", self.product_tall, x=0, y=0.0, height=54.0)
        self._line(design, "wall", self.product_wall, x=6, y=66.0, height=30.0)
        issues = design._check_production_ready()
        codes = {i["code"] for i in issues}
        self.assertNotIn(
            "VERTICAL_COLLISION", codes,
            "false-positive vertical collision: %s" % issues,
        )

    def test_genuine_vertical_overlap_still_detected(self):
        """Sanity check the fix didn't neuter the collision detector: a
        tall cabinet reaching into a wall cabinet's real vertical span
        must still be flagged."""
        design = self._design()
        self._line(design, "tall", self.product_tall, x=0, y=0.0, height=84.0)
        self._line(design, "wall", self.product_wall, x=6, y=66.0, height=30.0)
        issues = design._check_production_ready()
        codes = {i["code"] for i in issues}
        self.assertIn(
            "VERTICAL_COLLISION", codes,
            "expected a genuine vertical overlap to be flagged: %s" % issues,
        )
