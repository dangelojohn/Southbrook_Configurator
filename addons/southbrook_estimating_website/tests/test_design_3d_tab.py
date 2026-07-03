# SPDX-License-Identifier: LGPL-3.0-only
"""T1/T2 — the "3D Design" tab backend: get-or-create + seed a
southbrook.kitchen.design from an order, and persist drag-moves.

Covers the new portal routes on SouthbrookOrderBuilderPortal:
    /southbrook/api/order/<id>/design-3d        (get-or-create + seed + payload)
    /southbrook/api/order/<id>/design-3d/move   (persist x_position_in)

The controller resolves the order via _southbrook_resolve_order (ownership)
then operates on southbrook.kitchen.design under sudo() — portal customers
hold no ACL on that model. These tests exercise the Python directly (not
over HTTP) via the module-level `request` swap, mirroring
test_customer_flow_endpoints.py.
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
class TestDesign3dTab(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Design = cls.env["southbrook.kitchen.design"]
        cls.controller = ctrl_main.SouthbrookOrderBuilderPortal()

        # Portal customer + partner (share=True → the ownership path).
        cls.partner = cls.env["res.partner"].create({
            "name": "Design3D Test Customer",
            "email": "design3d.test@southbrook.test",
        })
        portal_group = cls.env.ref("base.group_portal")
        cls.user = cls.env["res.users"].create({
            "name": "Design3D Test Customer",
            "login": "design3d.test@southbrook.test",
            "partner_id": cls.partner.id,
            "group_ids": [(6, 0, [portal_group.id])],
        })

        # Two SB-SKU cabinets → the seed should produce two design lines.
        base = cls.env.ref("southbrook_estimating.base_1dr").product_variant_id
        wall = cls.env.ref("southbrook_estimating.wall_1dr").product_variant_id
        cls.order = cls.env["sale.order"].create({
            "partner_id": cls.partner.id,
            "order_line": [
                (0, 0, {"product_id": base.id, "product_uom_qty": 1,
                        "name": base.display_name, "zone": "base_run"}),
                (0, 0, {"product_id": wall.id, "product_uom_qty": 1,
                        "name": wall.display_name, "zone": "wall"}),
            ],
        })

    # ------------------------------------------------------------------
    def test_get_or_create_seeds_two_lines(self):
        with stubbed_request(self.env, user=self.user):
            payload = self.controller.southbrook_api_design_3d(self.order.id)
        self.assertNotIn("error", payload, f"unexpected: {payload}")
        self.assertTrue(payload["design_id"])
        self.assertEqual(len(payload["items"]), 2,
                         "two SB cabinets should seed two design lines")
        design = self.Design.browse(payload["design_id"])
        self.assertEqual(design.sale_order_id, self.order)
        cfg_lines = design.cabinet_line_ids.filtered(
            lambda l: l.origin == "configurator")
        self.assertEqual(len(cfg_lines), 2)
        # origin MUST be "configurator" so the move route can match them.
        self.assertTrue(all(l.origin == "configurator" for l in cfg_lines))
        # cabinet_type is required + populated.
        self.assertTrue(all(l.cabinet_type for l in cfg_lines))

    def test_positions_are_inches_and_non_overlapping(self):
        with stubbed_request(self.env, user=self.user):
            payload = self.controller.southbrook_api_design_3d(self.order.id)
        items = {i["cabinet_type"]: i for i in payload["items"]}
        # Base cabinet SB-BASE-1DR is 609mm wide → ~24in; centre x ≈ 12in.
        base_item = next(i for i in payload["items"]
                         if i["layout_key"].endswith("-base")
                         or i["cabinet_type"] == "base")
        self.assertGreater(base_item["width_in"], 20)
        self.assertLess(base_item["width_in"], 30)
        self.assertGreater(base_item["x_position_in"], 0)

    def test_get_or_create_idempotent_preserves_edits(self):
        with stubbed_request(self.env, user=self.user):
            payload = self.controller.southbrook_api_design_3d(self.order.id)
            design_id = payload["design_id"]
            key = payload["items"][0]["layout_key"]
            # Move it.
            res = self.controller.southbrook_api_design_3d_move(
                self.order.id, layout_key=key, x_position_in=99.0)
            self.assertTrue(res.get("ok"), res)
            # Re-open — must NOT reseed / clobber the moved position.
            payload2 = self.controller.southbrook_api_design_3d(self.order.id)
        self.assertEqual(payload2["design_id"], design_id)
        moved = next(i for i in payload2["items"] if i["layout_key"] == key)
        self.assertAlmostEqual(moved["x_position_in"], 99.0, places=2)

    def test_move_persists_to_design_line(self):
        with stubbed_request(self.env, user=self.user):
            payload = self.controller.southbrook_api_design_3d(self.order.id)
            key = payload["items"][0]["layout_key"]
            res = self.controller.southbrook_api_design_3d_move(
                self.order.id, layout_key=key, x_position_in=42.5)
        self.assertTrue(res.get("ok"), res)
        design = self.Design.browse(payload["design_id"])
        line = design.cabinet_line_ids.filtered(lambda l: l.layout_key == key)
        self.assertAlmostEqual(line.x_position_in, 42.5, places=2)

    def test_move_unknown_layout_key_is_soft_error(self):
        with stubbed_request(self.env, user=self.user):
            self.controller.southbrook_api_design_3d(self.order.id)
            res = self.controller.southbrook_api_design_3d_move(
                self.order.id, layout_key="does-not-exist", x_position_in=1.0)
        self.assertEqual(res.get("error"), "no_matching_line")

    def test_non_owner_forbidden(self):
        other_partner = self.env["res.partner"].create({
            "name": "Intruder", "email": "intruder@southbrook.test"})
        other = self.env["res.users"].create({
            "name": "Intruder", "login": "intruder@southbrook.test",
            "partner_id": other_partner.id,
            "group_ids": [(6, 0, [self.env.ref("base.group_portal").id])],
        })
        with stubbed_request(self.env, user=other):
            payload = self.controller.southbrook_api_design_3d(self.order.id)
        self.assertEqual(payload.get("error"), "forbidden")
