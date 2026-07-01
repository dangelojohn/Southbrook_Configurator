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
        # base_2dr is `create_variant='dynamic'` per Q6, so its
        # `product_variant_id` is an EMPTY recordset until a config-
        # session materialises one. Under -i (no --demo) that means
        # tests using it hit v19's accountable_required_fields check
        # (product_id NULL) AND the NOT NULL name check. Materialise
        # a straightforward test product inline instead — the wall-
        # assignment logic doesn't care about the OCA variant path.
        cls.product = cls.env["product.product"].create({
            "name": "Test Cabinet SB-BASE-2DR",
            "default_code": "SB-BASE-2DR-TEST",
            "type": "consu",
            "list_price": 500.0,
        })

    def test_unpositioned_line_does_not_break_existing_behavior(self):
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id,
            "product_id": self.product.id,
            "product_uom_qty": 1.0,
            # sale.order.line.name is NOT NULL in v19. product_variant_id
            # on Q6 dynamic templates can be empty at test-time, so
            # display_name → None → NULL. Use a static string.
            "name": "Test SB-BASE-2DR line",
        })
        self.assertFalse(line.wall_id)
        self.assertFalse(line.is_positioned)

    def test_position_a_cabinet_against_wall_a(self):
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id, "product_id": self.product.id,
            "product_uom_qty": 1.0,
            # sale.order.line.name is NOT NULL in v19. product_variant_id
            # on Q6 dynamic templates can be empty at test-time, so
            # display_name → None → NULL. Use a static string.
            "name": "Test SB-BASE-2DR line",
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
            # sale.order.line.name is NOT NULL in v19. product_variant_id
            # on Q6 dynamic templates can be empty at test-time, so
            # display_name → None → NULL. Use a static string.
            "name": "Test SB-BASE-2DR line",
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
            # sale.order.line.name is NOT NULL in v19. product_variant_id
            # on Q6 dynamic templates can be empty at test-time, so
            # display_name → None → NULL. Use a static string.
            "name": "Test SB-BASE-2DR line",
            "wall_id": self.wall_a.id, "position_from_left_mm": 100,
        })
        new_order = self.order.copy()
        new_line = new_order.order_line[0]
        self.assertFalse(new_line.wall_id, "wall_id must not propagate on copy (NF6)")
        self.assertFalse(new_line.position_from_left_mm)

    def test_no_conflict_happy_path(self):
        # Window 600mm wide at 1000mm from wall A's left corner
        self.env["southbrook.room.constraint"].create({
            "wall_id": self.wall_a.id, "constraint_type": "window",
            "distance_from_left_mm": 1000, "width_mm": 600,
        })
        # Cabinet to the LEFT of the window (0-600), no overlap with 1000-1600
        self.env["sale.order.line"].create({
            "order_id": self.order.id, "product_id": self.product.id,
            "product_uom_qty": 1.0,
            # sale.order.line.name is NOT NULL in v19. product_variant_id
            # on Q6 dynamic templates can be empty at test-time, so
            # display_name → None → NULL. Use a static string.
            "name": "Test SB-BASE-2DR line",
            "wall_id": self.wall_a.id, "position_from_left_mm": 0,
        })
        self.wall_a.invalidate_recordset(["has_conflicts"])
        self.assertFalse(self.wall_a.has_conflicts)

    def test_power_outlet_does_not_trigger_conflict(self):
        # Power outlet is intentionally excluded from collision geometry —
        # cabinets cover outlets all the time, that is fine.
        self.env["southbrook.room.constraint"].create({
            "wall_id": self.wall_a.id, "constraint_type": "power_outlet",
            "distance_from_left_mm": 200, "width_mm": 100,
        })
        self.env["sale.order.line"].create({
            "order_id": self.order.id, "product_id": self.product.id,
            "product_uom_qty": 1.0,
            # sale.order.line.name is NOT NULL in v19. product_variant_id
            # on Q6 dynamic templates can be empty at test-time, so
            # display_name → None → NULL. Use a static string.
            "name": "Test SB-BASE-2DR line",
            "wall_id": self.wall_a.id, "position_from_left_mm": 0,
        })
        self.wall_a.invalidate_recordset(["has_conflicts"])
        self.assertFalse(self.wall_a.has_conflicts)

    def test_wall_unlink_cascades_constraints(self):
        # Deleting a wall should cascade-delete its constraints AND
        # set-null the wall_id on any cabinet line that was assigned
        # to it (no orphan FKs).
        c = self.env["southbrook.room.constraint"].create({
            "wall_id": self.wall_a.id, "constraint_type": "window",
            "distance_from_left_mm": 0, "width_mm": 100,
        })
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id, "product_id": self.product.id,
            "product_uom_qty": 1.0,
            "name": self.product.display_name,
            "wall_id": self.wall_a.id, "position_from_left_mm": 1500,
        })
        c_id, line_id = c.id, line.id
        self.wall_a.unlink()
        self.assertFalse(
            self.env["southbrook.room.constraint"].browse(c_id).exists(),
            "constraint must cascade-delete with wall")
        survived_line = self.env["sale.order.line"].browse(line_id)
        self.assertTrue(survived_line.exists(), "line must survive wall delete")
        self.assertFalse(survived_line.wall_id, "wall_id must be set NULL")
