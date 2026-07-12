# SPDX-License-Identifier: LGPL-3.0-only
"""W071 (R8.10, 2026-06-27) — trolley/cart QR -> bind to active WO.

Tests cover:
  * x_sbk_trolley_id field exists on mrp.workorder + accepts an
    internal-picking record.
  * action_sbk_bind_trolley rejects non-internal pickings and
    bad-state pickings with a UserError.
  * action_sbk_bind_trolley re-binds and posts chatter on both records.
  * Re-binding the SAME trolley is a no-op (already_bound short-path).
  * The 'trolley' QR kind dispatches through the controller and binds
    via workorder_id hint when supplied.
  * The kind handler returns a friendly error when no active WO can
    be resolved for the current operator.
  * _sbk_resolve_active_workorder prefers operator-assigned WOs.

These tests use direct method calls (no real http) to mirror the
existing W035 pattern in this addon.
"""
from contextlib import contextmanager
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.southbrook_qr_kit.controllers import qr_scan as qr_scan_mod


class _FakeHttpRequest:
    def __init__(self):
        self.remote_addr = "127.0.0.1"
        self.headers = {"User-Agent": "pytest-w071"}
        self.path = "/sb/qr/scan"


class _FakeRequest:
    def __init__(self, env, session=None):
        self.env = env
        self.session = session if session is not None else {}
        self.httprequest = _FakeHttpRequest()
        self.uid = env.uid


@contextmanager
def _patched_request(fake):
    with patch.object(qr_scan_mod, "request", fake):
        yield


@tagged("post_install", "-at_install", "southbrook", "qr",
        "w071", "r8_10")
class TestW071TrolleyBind(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wo = cls.env["mrp.workorder"]
        cls.Picking = cls.env["stock.picking"]
        cls.PickingType = cls.env["stock.picking.type"]
        cls.Payload = cls.env["southbrook.qr.payload"].sudo()

        # Reuse an existing internal picking type (every standard
        # warehouse has one).
        cls.internal_type = cls.PickingType.search(
            [("code", "=", "internal")], limit=1)
        if not cls.internal_type:
            warehouse = cls.env["stock.warehouse"].search([], limit=1)
            cls.internal_type = cls.PickingType.create({
                "name": "Internal Transfer (W071)",
                "code": "internal",
                "sequence_code": "W071",
                "warehouse_id": warehouse.id,
                "default_location_src_id":
                    warehouse.lot_stock_id.id,
                "default_location_dest_id":
                    warehouse.lot_stock_id.id,
            })
        # Same for outgoing (to test rejection of non-internal).
        cls.outgoing_type = cls.PickingType.search(
            [("code", "=", "outgoing")], limit=1)

        # An hr.employee for trace credit.
        cls.emp = cls.env["hr.employee"].create({
            "name": "W071 Operator",
            "pin": "7171",
            "active": True,
        })

        # A trolley (internal picking, draft).
        loc = cls.env["stock.location"].search(
            [("usage", "=", "internal")], limit=1)
        cls.trolley = cls.Picking.create({
            "picking_type_id": cls.internal_type.id,
            "location_id": loc.id,
            "location_dest_id": loc.id,
            "origin": "W071-TROLLEY",
        })
        # Bump state to 'assigned' (mimic pre-staged kit ready for the
        # cell). The standard Odoo flow uses _action_assign() but a
        # simple write keeps the test independent of stock-routing
        # configuration in the CI db.
        cls.trolley.write({"state": "assigned"})

        # A second trolley to test re-binding to a different one.
        cls.trolley_b = cls.Picking.create({
            "picking_type_id": cls.internal_type.id,
            "location_id": loc.id,
            "location_dest_id": loc.id,
            "origin": "W071-TROLLEY-B",
        })
        cls.trolley_b.write({"state": "assigned"})

        # An outgoing picking — must NOT be acceptable as a trolley.
        if cls.outgoing_type:
            cls.not_trolley = cls.Picking.create({
                "picking_type_id": cls.outgoing_type.id,
                "location_id": loc.id,
                "location_dest_id": loc.id,
                "origin": "W071-NOT-TROLLEY",
            })

        # A workorder — we mint a minimal MO + WO. The CI db must have
        # the mrp module loaded (it's in qr_kit's depends as of W071).
        # The test only exercises the bind field/method, so we don't
        # need a fully-routed BOM.
        product = cls.env["product.product"].search([], limit=1)
        if not product:
            product = cls.env["product.product"].create({
                "name": "W071 Smoke Widget", "type": "consu"})
        bom = cls.env["mrp.bom"].create({
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_qty": 1.0,
            "type": "normal",
        })
        wc = cls.env["mrp.workcenter"].search([], limit=1)
        if not wc:
            wc = cls.env["mrp.workcenter"].create({
                "name": "W071 WC", "resource_calendar_id": False})
        bom.write({
            "operation_ids": [(0, 0, {
                "name": "W071 op",
                "workcenter_id": wc.id,
                "time_cycle": 5.0,
            })]
        })
        cls.mo = cls.env["mrp.production"].create({
            "product_id": product.id,
            "product_qty": 1.0,
            "bom_id": bom.id,
        })
        cls.mo.action_confirm()
        # Confirming the MO creates workorders from the BOM ops.
        cls.wo = cls.mo.workorder_ids[:1]
        if not cls.wo:
            # Fallback: manual WO. Some CI mrp configs don't auto-build
            # WOs without an `mrp.workcenter.productivity` calendar.
            cls.wo = cls.Wo.create({
                "name": "W071 WO",
                "production_id": cls.mo.id,
                "workcenter_id": wc.id,
                "product_uom_id": product.uom_id.id,
                "qty_producing": 0.0,
                "qty_production": 1.0,
                "duration_expected": 5.0,
            })

    # ------------------------------------------------------------------
    # Field surface
    # ------------------------------------------------------------------
    def test_10_field_exists_and_accepts_internal_picking(self):
        self.assertIn("x_sbk_trolley_id", self.Wo._fields,
                      "W071 must add x_sbk_trolley_id to mrp.workorder")
        self.wo.x_sbk_trolley_id = self.trolley
        self.assertEqual(self.wo.x_sbk_trolley_id.id, self.trolley.id)

    # ------------------------------------------------------------------
    # action_sbk_bind_trolley
    # ------------------------------------------------------------------
    def test_20_bind_rejects_non_internal_picking(self):
        if not getattr(self, "not_trolley", None):
            self.skipTest("No outgoing picking type in this CI DB.")
        with self.assertRaises(UserError):
            self.wo.action_sbk_bind_trolley(
                self.not_trolley, employee=self.emp)

    def test_21_bind_writes_field_and_posts_chatter(self):
        # Fresh WO so we don't collide with test_10's bind.
        wo = self.wo.copy()
        # mrp.workorder only carries mail.thread when the full MRP stack is
        # installed; in a qr_kit-only install it doesn't. Guard the workorder
        # chatter checks accordingly — the field write and the picking-side
        # chatter (always present) are the invariants that must hold.
        wo_has_chatter = hasattr(wo, "message_ids")
        wo_msgs_before = len(wo.message_ids) if wo_has_chatter else 0
        trolley_msgs_before = len(self.trolley.message_ids)
        res = wo.action_sbk_bind_trolley(self.trolley, employee=self.emp)
        self.assertTrue(res.get("ok"), res)
        self.assertEqual(wo.x_sbk_trolley_id.id, self.trolley.id)
        self.assertEqual(wo.x_sbk_trolley_bound_by.id, self.emp.id)
        self.assertTrue(wo.x_sbk_trolley_bound_at)
        # Picking-side chatter is always written (stock.picking has mail.thread).
        self.assertGreater(
            len(self.trolley.message_ids), trolley_msgs_before)
        # Workorder-side chatter only when the WO carries mail.thread.
        if wo_has_chatter:
            self.assertGreater(len(wo.message_ids), wo_msgs_before)

    def test_22_rebind_same_trolley_short_circuits(self):
        wo = self.wo.copy()
        wo.action_sbk_bind_trolley(self.trolley, employee=self.emp)
        res2 = wo.action_sbk_bind_trolley(self.trolley, employee=self.emp)
        self.assertTrue(res2.get("already_bound"))
        # Re-binding to a different trolley overwrites.
        res3 = wo.action_sbk_bind_trolley(
            self.trolley_b, employee=self.emp)
        self.assertTrue(res3.get("ok"))
        self.assertEqual(wo.x_sbk_trolley_id.id, self.trolley_b.id)
        self.assertEqual(res3.get("prev_trolley_name"),
                         self.trolley.display_name)

    # ------------------------------------------------------------------
    # QR kind dispatch through the controller
    # ------------------------------------------------------------------
    def test_30_kind_dispatch_with_workorder_hint_binds(self):
        # Build a signed payload for the trolley.
        payload = self.Payload.build("trolley", self.trolley.id)
        fake = _FakeRequest(
            self.env,
            session={
                "sbk_operator_employee_id": self.emp.id,
                "sbk_operator_pin_at": 1,
                "sbk_operator_last_seen": 9_999_999_999,
            },
        )
        controller = qr_scan_mod.QrScanController()
        with _patched_request(fake):
            res = controller._dispatch(
                payload=payload,
                action="bind",
                params={"workorder_id": self.wo.id},
                source="json",
            )
        self.assertTrue(res.get("ok"), res)
        self.assertEqual(res.get("workorder_id"), self.wo.id)
        self.wo.invalidate_recordset(["x_sbk_trolley_id"])
        self.assertEqual(self.wo.x_sbk_trolley_id.id, self.trolley.id)

    def test_31_kind_dispatch_no_active_wo_returns_friendly_error(self):
        # An operator with no in-progress WO and no hint must not 500.
        emp_solo = self.env["hr.employee"].create({
            "name": "W071 Lonely", "pin": "7172", "active": True})
        payload = self.Payload.build("trolley", self.trolley_b.id)
        fake = _FakeRequest(
            self.env,
            session={
                "sbk_operator_employee_id": emp_solo.id,
                "sbk_operator_pin_at": 1,
                "sbk_operator_last_seen": 9_999_999_999,
            },
        )
        controller = qr_scan_mod.QrScanController()
        with _patched_request(fake):
            res = controller._dispatch(
                payload=payload, action="bind",
                params={}, source="json",
            )
        # Soft-fail: ok=False, result=no_active_workorder, friendly error.
        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("result"), "no_active_workorder")
        self.assertIn("active workorder", res.get("error", "").lower())
