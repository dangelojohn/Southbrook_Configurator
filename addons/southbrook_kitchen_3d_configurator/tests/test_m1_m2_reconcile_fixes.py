# SPDX-License-Identifier: LGPL-3.0-only
"""Regression tests for two 2026-07-06 fixes:

M1 — `southbrook.kitchen.design._compute_totals` (models/kitchen_design.py)
    used to depend ONLY on `cabinet_line_ids.*` + `room_width_in`. When
    cabinets are added directly onto the linked sale.order's lines
    (bypassing "Generate Layout"), `cabinet_line_ids` stays empty and the
    summary card showed "0 cabinets / $0.00" even though the order has
    real cabinet lines. Fix: depend on the order's cabinet-line fields too,
    and fall back to summing the order's own cabinet product lines when
    the design has no configurator-authored lines of its own.

M2 — `southbrook.design.reconcile._reconcile_one` (models/reconcile.py)
    used to gate room creation only on `design.room_id`, never checking
    whether `design.sale_order_id.room_ids` already had one. A stray/
    abandoned design (default room_width_in=12) that later gains a
    sale_order_id matching an order that already has a real, wizard-built
    room would get a brand-new duplicate placeholder room. Fix: reuse the
    order's existing room instead of creating a second one.

Style follows the sibling `test_save_design_acl.py` / `test_track_b_end_
to_end.py` (TransactionCase, fresh test-only fixtures, no reliance on
demo/live data).
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook",
        "southbrook_kitchen_3d_configurator", "rec_d_idempotency")
class TestM1DesignTotalsOrderFallback(TransactionCase):
    """M1 — design summary falls back to the order's cabinet lines."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Design = cls.env["southbrook.kitchen.design"]
        cls.Template = cls.env["product.template"]
        cls.Partner = cls.env["res.partner"]
        cls.SaleOrder = cls.env["sale.order"]

        cls.partner = cls.Partner.create({
            "name": "M1 Test Customer",
            "email": "m1.customer@southbrook.test",
        })

        cls.cabinet_tmpl = cls.Template.create({
            "name": "M1 Base Cabinet",
            "type": "consu",
            "sale_ok": True,
            "list_price": 500.0,
        })
        cls.cabinet_tmpl.write({
            "southbrook_is_cabinet": True,
            "southbrook_cabinet_type": "base",
            "southbrook_width_in": 24.0,
        })
        cls.cabinet_variant = cls.cabinet_tmpl.product_variant_id

        # A non-cabinet product on the same order — must NOT be counted.
        cls.noncabinet_tmpl = cls.Template.create({
            "name": "M1 Non-Cabinet Product",
            "type": "consu",
            "sale_ok": True,
            "list_price": 20.0,
        })
        cls.noncabinet_variant = cls.noncabinet_tmpl.product_variant_id

    def test_01_empty_design_lines_falls_back_to_order_cabinet_lines(self):
        """Order has 3x cabinet lines, design.cabinet_line_ids is empty ->
        the summary card must report the order's cabinet count/price, not
        zero."""
        order = self.SaleOrder.create({
            "partner_id": self.partner.id,
            "order_line": [
                (0, 0, {
                    "product_id": self.cabinet_variant.id,
                    "product_uom_qty": 3,
                    "price_unit": 500.0,
                }),
                (0, 0, {
                    "product_id": self.noncabinet_variant.id,
                    "product_uom_qty": 5,
                    "price_unit": 20.0,
                }),
            ],
        })
        design = self.Design.create({
            "name": "M1 Empty-lines Design",
            "partner_id": self.partner.id,
            "sale_order_id": order.id,
            "room_width_in": 120,
            "room_depth_in": 96,
            "room_height_in": 96,
        })
        self.assertFalse(
            design.cabinet_line_ids,
            "test setup assumption: design has no configurator lines",
        )
        self.assertEqual(
            design.total_cabinets, 3,
            "total_cabinets must reflect the order's cabinet-product "
            "lines when the design's own cabinet_line_ids is empty",
        )
        self.assertAlmostEqual(
            design.estimated_price, 1500.0,
            msg="estimated_price must sum the order's cabinet-product "
                "line subtotals (3 x $500), excluding the non-cabinet "
                "line",
        )
        self.assertEqual(design.base_count, 3)
        self.assertEqual(design.wall_count, 0)

    def test_02_design_with_own_lines_ignores_order_fallback(self):
        """When cabinet_line_ids is populated, the summary must keep using
        the design's own lines (Generate Layout / drag-editor authority is
        unchanged) even if the linked order also has cabinet lines."""
        order = self.SaleOrder.create({
            "partner_id": self.partner.id,
            "order_line": [
                (0, 0, {
                    "product_id": self.cabinet_variant.id,
                    "product_uom_qty": 9,
                    "price_unit": 500.0,
                }),
            ],
        })
        design = self.Design.create({
            "name": "M1 Own-lines Design",
            "partner_id": self.partner.id,
            "sale_order_id": order.id,
            "room_width_in": 120,
            "room_depth_in": 96,
            "room_height_in": 96,
        })
        self.env["southbrook.kitchen.design.line"].create({
            "design_id": design.id,
            "product_id": self.cabinet_variant.id,
            "quantity": 1,
            "price_unit": 500.0,
            "cabinet_type": "base",
            "origin": "configurator",
            "width_in": 24.0,
            "height_in": 34.5,
            "depth_in": 24.0,
        })
        design.invalidate_recordset()
        self.assertEqual(
            design.total_cabinets, 1,
            "design's own cabinet_line_ids must remain authoritative "
            "over the order fallback when it is non-empty",
        )
        self.assertAlmostEqual(design.estimated_price, 500.0)

    def test_03_no_linked_order_still_reports_zero(self):
        """No sale_order_id and no cabinet_line_ids -> zero, not an
        error (regression guard against a crash on an empty recordset)."""
        design = self.Design.create({
            "name": "M1 No-order Design",
            "partner_id": self.partner.id,
            "room_width_in": 120,
            "room_depth_in": 96,
            "room_height_in": 96,
        })
        self.assertEqual(design.total_cabinets, 0)
        self.assertEqual(design.estimated_price, 0.0)


@tagged("post_install", "-at_install", "southbrook",
        "southbrook_kitchen_3d_configurator", "rec_d_idempotency")
class TestM2ReconcileRoomIdempotency(TransactionCase):
    """M2 — `_reconcile_one` must not create a second room when the
    design's sale_order_id already has one."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Design = cls.env["southbrook.kitchen.design"]
        cls.Room = cls.env["southbrook.room"]
        cls.Partner = cls.env["res.partner"]
        cls.SaleOrder = cls.env["sale.order"]
        cls.Reconcile = cls.env["southbrook.design.reconcile"]

        cls.partner = cls.Partner.create({
            "name": "M2 Test Customer",
            "email": "m2.customer@southbrook.test",
        })

    def _make_stray_design(self, order):
        """A design that mimics the reported bug scenario: default 12in
        room_width_in, a partner, and a sale_order_id — but no room_id
        of its own yet (never reconciled)."""
        return self.Design.create({
            "name": "M2 Stray Design",
            "partner_id": self.partner.id,
            "sale_order_id": order.id,
            # room_width_in left at its 12.0 default deliberately.
        })

    def test_01_reuses_existing_order_room_instead_of_duplicating(self):
        """Order already has a real, wizard-built room ("Main Kitchen").
        Reconciling a stray design pointed at the same order must link
        to that room, not create a second one."""
        order = self.SaleOrder.create({"partner_id": self.partner.id})
        main_kitchen = self.Room.create({
            "order_id": order.id,
            "name": "Main Kitchen",
        })
        design = self._make_stray_design(order)

        stats = {"mirrored": 0, "created_orders": 0, "created_rooms": 0,
                  "created_lines": 0, "divergence": 0, "errors": 0}
        self.Reconcile._reconcile_one(design, stats)

        self.assertEqual(
            design.room_id.id, main_kitchen.id,
            "design must be linked to the order's existing room",
        )
        self.assertEqual(
            stats["created_rooms"], 0,
            "no new room should have been created",
        )
        self.assertEqual(
            len(order.room_ids), 1,
            "the order must still have exactly one room after reconcile",
        )

    def test_02_running_reconcile_twice_does_not_duplicate(self):
        """Idempotency: calling `_reconcile_one` twice on the same design
        (e.g. two cron ticks, or a manual re-run) must not create a
        second room."""
        order = self.SaleOrder.create({"partner_id": self.partner.id})
        main_kitchen = self.Room.create({
            "order_id": order.id,
            "name": "Main Kitchen",
        })
        design = self._make_stray_design(order)

        stats = {"mirrored": 0, "created_orders": 0, "created_rooms": 0,
                  "created_lines": 0, "divergence": 0, "errors": 0}
        self.Reconcile._reconcile_one(design, stats)
        self.Reconcile._reconcile_one(design, stats)

        self.assertEqual(design.room_id.id, main_kitchen.id)
        self.assertEqual(len(order.room_ids), 1)

    def test_03_creates_room_when_order_genuinely_has_none(self):
        """Baseline regression guard: when the order has NO room at all,
        reconcile must still create exactly one (the original behaviour
        for the normal, non-duplicate case)."""
        order = self.SaleOrder.create({"partner_id": self.partner.id})
        design = self._make_stray_design(order)
        self.assertFalse(order.room_ids)

        stats = {"mirrored": 0, "created_orders": 0, "created_rooms": 0,
                  "created_lines": 0, "divergence": 0, "errors": 0}
        self.Reconcile._reconcile_one(design, stats)

        self.assertTrue(design.room_id)
        self.assertEqual(stats["created_rooms"], 1)
        self.assertEqual(len(order.room_ids), 1)
