# SPDX-License-Identifier: LGPL-3.0-only
"""M3 (2026-07-06): cabinets added to the order but not placed on a wall
must be visible. wall.used_mm only counts lines with wall_id set, so a wall
reads "0 used (mm)" even when the order has cabinets — room.unplaced_
cabinet_count surfaces how many still need placing.
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "room_unplaced")
class TestRoomUnplacedCabinets(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "M3 Test"})
        cls.order = cls.env["sale.order"].create({"partner_id": cls.partner.id})
        tmpl = cls.env.ref("southbrook_estimating.base_1dr")
        cls.tmpl = tmpl
        cls.variant = tmpl.product_variant_ids[:1] or cls.env[
            "product.product"].create({"product_tmpl_id": tmpl.id})
        cls.room = cls.env["southbrook.room"].create({
            "name": "Test Kitchen", "order_id": cls.order.id})

    def _add_cabinet_line(self):
        return self.env["sale.order.line"].create({
            "order_id": self.order.id,
            "product_id": self.variant.id,
            "product_uom_qty": 1,
        })

    def test_unplaced_counts_cabinet_without_wall(self):
        self.assertEqual(self.room.unplaced_cabinet_count, 0)
        self._add_cabinet_line()  # no wall_id
        self.room.invalidate_recordset(["unplaced_cabinet_count"])
        self.assertEqual(
            self.room.unplaced_cabinet_count, 1,
            "a cabinet line with no wall_id must count as unplaced")

    def test_placing_on_a_wall_clears_it(self):
        line = self._add_cabinet_line()
        wall = self.env["southbrook.room.wall"].create({
            "room_id": self.room.id, "name": "North", "length_mm": 3000})
        line.wall_id = wall.id
        self.room.invalidate_recordset(["unplaced_cabinet_count"])
        self.assertEqual(
            self.room.unplaced_cabinet_count, 0,
            "once placed on a wall the cabinet is no longer unplaced")
