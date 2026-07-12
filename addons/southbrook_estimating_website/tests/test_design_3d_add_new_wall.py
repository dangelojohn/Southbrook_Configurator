# SPDX-License-Identifier: LGPL-3.0-only
"""Task 3 (2026-07-12 corner-resolution-geometric-rule plan) — the first
cabinet dropped on a NEW wall must never be consumed by corner resolution
on the same /design-3d/add call.

Prior bug: southbrook_api_design_3d_add() placed the new line via
_sb_place_line_on_wall, then — whenever the design's configurator cabinets
now spanned >=2 walls — unconditionally called design.action_auto_arrange()
and returned the re-laid payload instead of the plain "item" response. Since
action_auto_arrange resets to canonical and re-derives corners, the very
first cabinet on a brand-new wall (e.g. "left", with cabinets already on
"back") could be swapped away by corner resolution on the SAME request that
added it — the "vanishing cabinet" bug.

Fix: gate the walls_used>=2 -> action_auto_arrange() branch on whether the
new cabinet's wall ALREADY had >=1 configurator cabinet before this add
(the `same_wall` recordset already computed for run_seq). First cabinet on
a wall -> always the plain {"ok": True, "item": {...}} response, cabinet
stays. Second+ cabinet on an already-occupied wall -> resolution may still
run (that path must keep working, not error).
"""
from contextlib import contextmanager
from unittest.mock import MagicMock

from odoo.tests import TransactionCase, tagged

from odoo.addons.southbrook_estimating_website.controllers import main as ctrl_main


@contextmanager
def stubbed_request(env, user=None):
    saved = ctrl_main.request
    mock = MagicMock()
    mock.env = env if user is None else env(user=user.id)
    mock.session = {}
    mock.params = {}
    mock.httprequest.args = {}
    ctrl_main.request = mock
    try:
        yield mock
    finally:
        ctrl_main.request = saved


@tagged("post_install", "-at_install", "southbrook", "southbrook_design_3d")
class TestDesign3dAddNewWall(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Design = cls.env["southbrook.kitchen.design"]
        cls.controller = ctrl_main.SouthbrookOrderBuilderPortal()

        cls.partner = cls.env["res.partner"].create({
            "name": "Design3D NewWall Customer",
            "email": "design3d.newwall@southbrook.test",
        })
        portal_group = cls.env.ref("base.group_portal")
        cls.user = cls.env["res.users"].create({
            "name": "Design3D NewWall Customer",
            "login": "design3d.newwall@southbrook.test",
            "partner_id": cls.partner.id,
            "group_ids": [(6, 0, [portal_group.id])],
        })

        # Fresh, catalog-conforming cabinet template — do NOT rely on
        # demo/live-DB product refs (see test_track_b_end_to_end.py's
        # _make_cabinet_template: a shared dev DB's demo product variants
        # are not a stable fixture to build unit tests against).
        # default_code MUST match a key in product_config_line._SKU_DEFAULTS
        # — the order-seed route (_southbrook_seed_design_lines) looks the
        # product up by SKU prefix and silently skips non-matching lines.
        base_tmpl = cls.env["product.template"].create({
            "name":         "Task3 Test Base Cabinet",
            "default_code": "SB-BASE-1DR",
            "type":         "consu",
            "sale_ok":      True,
            "list_price":   500.0,
        })
        base_tmpl.write({
            "southbrook_is_cabinet":   True,
            "southbrook_cabinet_type": "base",
            "southbrook_width_in":     24.0,
            "southbrook_height_in":    34.5,
            "southbrook_depth_in":     24.0,
        })
        cls.base_product = base_tmpl.product_variant_id

        # One back-wall configurator cabinet already on the order — seeded
        # via the design get-or-create route so it lands as a "back" line,
        # exactly like a real session that already has a back run.
        cls.order = cls.env["sale.order"].create({
            "partner_id": cls.partner.id,
            "order_line": [
                (0, 0, {"product_id": cls.base_product.id,
                        "product_uom_qty": 1,
                        "name": cls.base_product.display_name,
                        "zone": "base_run"}),
            ],
        })
        with stubbed_request(cls.env, user=cls.user):
            cls.controller.southbrook_api_design_3d(cls.order.id)
        cls.design = cls.Design.search(
            [("sale_order_id", "=", cls.order.id)], limit=1)
        # Sanity: the seed produced exactly one configurator cabinet, on back.
        back_lines = cls.design.cabinet_line_ids.filtered(
            lambda l: l.origin == "configurator")
        assert len(back_lines) == 1
        assert (back_lines.wall or "back") == "back"

    # ------------------------------------------------------------------
    def test_first_cabinet_on_new_wall_is_returned_not_consumed(self):
        """First LEFT cabinet, back cabinets already present: must come
        back as the plain item response (not relaid), and must survive as
        an active line on wall=left — not be swapped away by corner
        resolution on this same call."""
        with stubbed_request(self.env, user=self.user):
            res = self.controller.southbrook_api_design_3d_add(
                self.order.id, product_id=self.base_product.id, wall="left")

        self.assertNotIn("error", res, f"unexpected error: {res}")
        # Must NOT be the relaid/auto-arrange shape.
        self.assertNotIn("relaid", res)
        self.assertIn("item", res, res)

        self.design.invalidate_recordset()
        left_lines = self.design.cabinet_line_ids.filtered(
            lambda l: l.origin == "configurator" and l.wall == "left")
        self.assertEqual(len(left_lines), 1,
                          "the new left cabinet must exist, active, on wall=left")
        self.assertTrue(left_lines.active)
        self.assertEqual(left_lines.layout_key, res["item"]["layout_key"])

        # No corner was auto-inserted by this add.
        corner_lines = self.design.cabinet_line_ids.filtered(
            lambda l: l.layout_role == "derived"
            or l.cabinet_type == "corner")
        self.assertFalse(
            corner_lines,
            "the first cabinet on a new wall must not trigger corner "
            "resolution / insert a derived corner on the same add")

        # The original back cabinet is untouched (still active, still back).
        back_lines = self.design.cabinet_line_ids.filtered(
            lambda l: l.origin == "configurator" and l.wall == "back")
        self.assertEqual(len(back_lines), 1)
        self.assertTrue(back_lines.active)

    def test_second_cabinet_on_occupied_wall_can_trigger_resolution(self):
        """With a left cabinet already present (from the first test's
        setup semantics reproduced here), adding a SECOND left cabinet is
        allowed to reach the relaid/auto-arrange path and must not error."""
        with stubbed_request(self.env, user=self.user):
            first = self.controller.southbrook_api_design_3d_add(
                self.order.id, product_id=self.base_product.id, wall="left")
            self.assertNotIn("error", first, first)

            second = self.controller.southbrook_api_design_3d_add(
                self.order.id, product_id=self.base_product.id, wall="left")

        self.assertNotIn("error", second, f"unexpected error: {second}")
        # Either shape is acceptable here (resolution is now ALLOWED, not
        # mandatory in every case), but if it took the relaid path it must
        # not have errored and must return a payload.
        if second.get("relaid"):
            self.assertIn("payload", second)
        else:
            self.assertIn("item", second)
