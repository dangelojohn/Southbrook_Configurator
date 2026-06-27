# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "southbrook_room_wall")
class TestRoomWallAssignment(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Cust"})
        cls.order = cls.env["sale.order"].create({"partner_id": cls.partner.id})
        cls.room = cls.env["southbrook.room"].create({
            "name": "K", "order_id": cls.order.id,
            "layout_shape": "l_shape",
            "wall_ids": [
                (0, 0, {"name": "A", "length_mm": 3600}),
                (0, 0, {"name": "B", "length_mm": 2400}),
            ],
        })
        cls.wall_a, cls.wall_b = cls.room.wall_ids
        cls.product = cls.env.ref("southbrook_estimating.product_base_2dr").product_variant_id

    def test_unpositioned_line_does_not_break_existing_behavior(self):
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id,
            "product_id": self.product.id,
            "product_uom_qty": 1.0,
        })
        self.assertFalse(line.wall_id)
        self.assertFalse(line.is_positioned)

    def test_position_a_cabinet_against_wall_a(self):
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id, "product_id": self.product.id,
            "product_uom_qty": 1.0,
            "wall_id": self.wall_a.id, "position_from_left_mm": 0,
        })
        self.assertTrue(line.is_positioned)
        self.wall_a.invalidate_recordset(["used_mm", "remaining_mm"])
        # sb_width_mm default 600 for base cabinet without PTAV resolution
        self.assertGreater(self.wall_a.used_mm, 0)
        self.assertEqual(
            self.wall_a.remaining_mm, self.wall_a.length_mm - self.wall_a.used_mm)

    def test_overlap_detection_with_constraint(self):
        # Window 600mm wide, starting at 1000mm from wall A's left corner
        self.env["southbrook.room.constraint"].create({
            "wall_id": self.wall_a.id, "constraint_type": "window",
            "distance_from_left_mm": 1000, "width_mm": 600,
        })
        # Cabinet starting at 900mm, 600mm wide → overlaps window (900-1500 vs 1000-1600)
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id, "product_id": self.product.id,
            "product_uom_qty": 1.0,
            "wall_id": self.wall_a.id, "position_from_left_mm": 900,
        })
        self.wall_a.invalidate_recordset(["has_conflicts"])
        self.assertTrue(self.wall_a.has_conflicts)
        # The line itself also reports conflict via order-line compute
        # (we expose this via wall.has_conflicts only — line-level conflict
        # is derived in the UI from wall conflicts intersecting position)

    def test_copy_false_on_duplicate(self):
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id, "product_id": self.product.id,
            "product_uom_qty": 1.0,
            "wall_id": self.wall_a.id, "position_from_left_mm": 100,
        })
        new_order = self.order.copy()
        new_line = new_order.order_line[0]
        self.assertFalse(new_line.wall_id, "wall_id must not propagate on copy (NF6)")
        self.assertFalse(new_line.position_from_left_mm)
