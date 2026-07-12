# SPDX-License-Identifier: LGPL-3.0-only
"""PR2 — the `wall` field becomes part of the canonical persistence path
of the backend 3D configurator's controller layer.

Covers:
  * save_design persists an incoming item's `wall` onto the design line.
  * a missing `wall` key defaults to "back" (matches the model field's
    own default + the pre-PR2 single-run-along-the-back-wall behaviour).
  * an invalid `wall` value is rejected BEFORE any create/write happens
    (validate-all-items-first — a bad payload never partially writes).
  * load_design_lines emits `wall` in its per-line dict.
  * a NULL wall column (pre-PR2 rows, no migration) reads back as
    "back" for backward compatibility.

Design: exercise the controller methods directly with a stubbed
`request`, same pattern as the sibling `test_save_design_acl.py` /
`southbrook_estimating_website`'s `test_design_3d_add_new_wall.py`.
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
        "southbrook_kitchen_3d_configurator", "wall_persistence")
class TestWallPersistence(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner = cls.env["res.partner"].create({
            "name": "Kitchen 3D Wall Test Customer",
            "email": "kitchen3d.wall@southbrook.test",
        })
        cls.design = cls.env["southbrook.kitchen.design"].create({
            "name": "Wall-persistence test",
            "partner_id": cls.partner.id,
            "room_width_in": 120,
            "room_depth_in": 96,
            "room_height_in": 96,
        })

        # Catalog-conforming cabinet — same recipe as test_save_design_acl.py.
        cls.tmpl = cls.env["product.template"].create({
            "name": "Wall Test Cabinet",
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
    def test_save_persists_wall(self):
        """An item carrying wall='left' must land on the design line."""
        _, lines = self._save([{
            "product_id":    self.product.id,
            "layout_key":    "wall-test-1",
            "x_position_in": 0,
            "wall":          "left",
        }])
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].wall, "left")

    def test_save_missing_wall_defaults_back(self):
        """No `wall` key in the payload -> defaults to 'back'."""
        _, lines = self._save([{
            "product_id":    self.product.id,
            "layout_key":    "wall-test-2",
            "x_position_in": 0,
        }])
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].wall, "back")

    def test_save_invalid_wall_rejected(self):
        """An unrecognised wall value must be rejected with an error AND
        must not partially write — no design lines created."""
        result, lines = self._save([{
            "product_id":    self.product.id,
            "layout_key":    "wall-test-3",
            "x_position_in": 0,
            "wall":          "banana",
        }])
        self.assertIn("error", result, f"expected an error response: {result}")
        self.assertEqual(
            len(lines), 0,
            "an invalid wall value must not create/write ANY line from "
            "the payload (validate-all-items-first)",
        )

    def test_save_invalid_wall_rejects_whole_batch(self):
        """A payload mixing a valid item with an invalid one must reject
        the WHOLE batch — no partial write, even for the valid item."""
        result, lines = self._save([
            {
                "product_id":    self.product.id,
                "layout_key":    "wall-test-4a",
                "x_position_in": 0,
                "wall":          "right",
            },
            {
                "product_id":    self.product.id,
                "layout_key":    "wall-test-4b",
                "x_position_in": 30,
                "wall":          "banana",
            },
        ])
        self.assertIn("error", result, f"expected an error response: {result}")
        self.assertEqual(
            len(lines), 0,
            "one bad item in the batch must block the entire save, "
            "including the otherwise-valid item",
        )

    def test_load_design_lines_emits_wall(self):
        """load_design_lines must include 'wall' in each line's dict."""
        _, lines = self._save([{
            "product_id":    self.product.id,
            "layout_key":    "wall-test-5",
            "x_position_in": 0,
            "wall":          "right",
        }])
        self.assertEqual(len(lines), 1)
        controller = self._controller()
        with stubbed_request(self.env):
            result = controller.load_design_lines(design_id=self.design.id)
        self.assertEqual(len(result["lines"]), 1)
        self.assertEqual(result["lines"][0]["wall"], "right")

    def test_null_wall_reads_as_back(self):
        """Pre-PR2 rows with a NULL wall column (no migration) must read
        back as 'back' for backward compatibility."""
        _, lines = self._save([{
            "product_id":    self.product.id,
            "layout_key":    "wall-test-6",
            "x_position_in": 0,
            "wall":          "left",
        }])
        self.assertEqual(len(lines), 1)
        line = lines[0]
        self.env.cr.execute(
            "UPDATE southbrook_kitchen_design_line SET wall = NULL "
            "WHERE id = %s",
            (line.id,),
        )
        line.invalidate_recordset(["wall"])
        self.assertFalse(line.wall)

        controller = self._controller()
        with stubbed_request(self.env):
            result = controller.load_design_lines(design_id=self.design.id)
        self.assertEqual(len(result["lines"]), 1)
        self.assertEqual(result["lines"][0]["wall"], "back")
