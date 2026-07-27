# SPDX-License-Identifier: LGPL-3.0-only
"""P8 — Floor Traveler: QR payload, traveler-PDF integration, scan log,
no-duplicate-telemetry.

The audit's load-bearing acceptance is the "exactly once" guarantee on
tool-consumption debit — verified here by asserting that a simulated
scan -> record_scan -> mrp.workorder.button_finish call writes one (and
only one) entry in the scan log per WO advance.
"""
import json

from odoo.tests.common import HttpCase, TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "floor_traveler", "p8")
class TestP8FloorTraveler(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Bypass the MO availability gate (southbrook_premium_orchestration
        # blocks mo.action_confirm() when component moves can't be fully
        # reserved). _make_package_with_tool_required_wo() builds an MO
        # from a BoM without seeding stock quants, so the gate fires with
        # "Cannot confirm — N component move(s) cannot be fully reserved".
        # The gate is correct for production and stays ON elsewhere; the
        # bypass is scoped to this test class only.
        cls.env["ir.config_parameter"].sudo().set_param(
            "southbrook.mo_availability_gate.enabled", "0",
        )
        cls.Package = cls.env["sb.production.package"]
        cls.MO = cls.env["mrp.production"]
        cls.Cutlist = cls.env["sb.cutlist"]
        cls.Hardware = cls.env["sb.hardware.package"]
        cls.Product = cls.env["product.product"]
        cls.Bom = cls.env["mrp.bom"]
        cls.Asset = cls.env["southbrook.tool.asset"]
        cls.Crib = cls.env["southbrook.tool.crib"]
        cls.OpReq = cls.env["southbrook.operation.tool.requirement"]
        cls.Consumption = cls.env["southbrook.workorder.tool.consumption"]
        cls.category = cls.env.ref(
            "southbrook_mrp_kitchen_tools.cat_blade_melamine")

    def _make_package(self):
        product = self.Product.create({
            "name": "P8 test product",
            "type": "consu", "is_storable": True,
        })
        mo = self.MO.create({
            "product_id": product.id, "product_qty": 1.0,
        })
        cutlist = self.Cutlist.create({"mo_id": mo.id})
        hardware = self.Hardware.create({"mo_id": mo.id})
        return self.Package.create({
            "mo_id": mo.id,
            "cutlist_id": cutlist.id,
            "hardware_package_id": hardware.id,
            "state": "ready",
        })

    def _make_package_with_tool_required_wo(self):
        wc = self.env["mrp.workcenter"].create({
            "name": "P8 scan saw",
            "code": "P8-SAW",
        })
        crib = self.Crib.create({
            "code": "P8-SCAN-CRIB",
            "name": "P8 scan crib",
        })
        # Use a FRESH category, not the seeded cat_blade_melamine — the seed
        # ships an asset in that category, and the consumption resolver picks
        # by category, so a shared category makes it resolve the seeded asset
        # (asset(1)) instead of this test's asset.
        category = self.env["southbrook.tool.category"].create({
            "name": "P8 Scan Test Blades",
            "code": "P8-SCAN-CAT",
        })
        tool_product = self.Product.create({
            "name": "P8 scan panel saw blade",
            "default_code": "P8-SCAN-BLADE",
            "type": "consu",
            "x_southbrook_is_tool": True,
            "x_southbrook_is_reusable_tool": True,
            "x_southbrook_tool_category_id": category.id,
        })
        asset = self.Asset.create({
            "name": "P8 scan blade asset",
            "product_id": tool_product.id,
            "tool_crib_id": crib.id,
            "workcenter_id": wc.id,
            "lifecycle_state": "available",
            "condition": "good",
            "estimated_life_qty": 100.0,
            "remaining_life_qty": 100.0,
            "life_unit": "cuts",
            "purchase_cost": 3.0,
        })
        finished = self.Product.create({
            "name": "P8 scan finished cabinet",
            "type": "consu",
            "is_storable": True,
        })
        component = self.Product.create({
            "name": "P8 scan component",
            "type": "consu",
            "is_storable": True,
        })
        bom = self.Bom.create({
            "product_tmpl_id": finished.product_tmpl_id.id,
            "product_qty": 1.0,
            "bom_line_ids": [(0, 0, {
                "product_id": component.id,
                "product_qty": 1.0,
            })],
            "operation_ids": [(0, 0, {
                "name": "P8 scan cut panels",
                "workcenter_id": wc.id,
                "time_cycle_manual": 1.0,
            })],
        })
        mo = self.MO.create({
            "product_id": finished.id,
            "product_qty": 1.0,
            "bom_id": bom.id,
        })
        # Bypass the premium_orchestration MO availability gate — no component
        # stock is staged and this test exercises the scan/consumption loop.
        mo.with_context(bypass_availability_gate=True).action_confirm()
        wo = mo.workorder_ids[:1]
        wo.qty_produced = 1.0
        self.OpReq.create({
            "operation_id": wo.operation_id.id,
            "tool_category_id": category.id,
            "quantity": 1,
            "consume_qty_per_unit": 1.0,
        })
        cutlist = self.Cutlist.create({"mo_id": mo.id})
        hardware = self.Hardware.create({"mo_id": mo.id})
        package = self.Package.create({
            "mo_id": mo.id,
            "cutlist_id": cutlist.id,
            "hardware_package_id": hardware.id,
            "state": "ready",
        })
        return package, wo, asset

    # ------------------------------------------------------------------
    # Acceptance — QR encodes the package id
    # ------------------------------------------------------------------
    def test_qr_payload_encodes_package_id(self):
        pkg = self._make_package()
        self.assertEqual(pkg.qr_payload, "sb-package:%s" % pkg.id,
                         "QR payload must encode the package id verbatim")

    # ------------------------------------------------------------------
    # Acceptance — record_scan appends to log (no-WO case is graceful)
    # ------------------------------------------------------------------
    def test_record_scan_appends_log_without_wo(self):
        pkg = self._make_package()
        # No work orders on the MO -> no WO advancement, but the scan
        # event is still recorded.
        pkg.record_scan(workcenter_code="PANEL-SAW-01")
        log = json.loads(pkg.x_scan_log_json or "[]")
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["workcenter"], "PANEL-SAW-01")
        self.assertIsNone(log[0]["wo_id"])

    # ------------------------------------------------------------------
    # Acceptance — multiple scans accumulate; no duplicates per call
    # ------------------------------------------------------------------
    def test_multiple_scans_accumulate(self):
        pkg = self._make_package()
        pkg.record_scan(workcenter_code="PANEL-SAW")
        pkg.record_scan(workcenter_code="EDGE-BANDER")
        pkg.record_scan(workcenter_code="CNC")
        log = json.loads(pkg.x_scan_log_json or "[]")
        self.assertEqual(len(log), 3,
                         "each record_scan call appends exactly one entry "
                         "(no duplicate telemetry from the audit's load-"
                         "bearing acceptance)")
        codes = [e["workcenter"] for e in log]
        self.assertEqual(codes, ["PANEL-SAW", "EDGE-BANDER", "CNC"])

    # ------------------------------------------------------------------
    # Acceptance — record_scan calls the EXISTING button_finish path
    # *exactly once* per scan. This is the audit's load-bearing
    # "no duplicate telemetry" criterion: we must not re-implement the
    # tool-consumption debit, only route a scan event through it.
    # ------------------------------------------------------------------
    def test_record_scan_calls_button_finish_exactly_once(self):
        from unittest.mock import patch
        pkg = self._make_package()
        # Stub _sbk_next_workorder to return a recordset whose
        # button_finish is a no-op we can count. Using patch.object on
        # the model class is the canonical Odoo unit-test seam — same
        # pattern the existing test_mi_engine uses.
        FakeWO = self.env["mrp.workorder"]
        # Create a stand-in WO via direct ORM. Real MRP setup
        # (routing/workcenter) is heavyweight; here we just need the
        # record reference + button_finish hook.
        wc = self.env["mrp.workcenter"].create({
            "name": "P8-test wc", "code": "P8WC",
        })
        wo = FakeWO.create({
            "name": "P8-test wo",
            "workcenter_id": wc.id,
            "production_id": pkg.mo_id.id,
            "product_uom_id": pkg.mo_id.product_uom_id.id,
        })
        # Force the WO into a state record_scan will pick up.
        wo.state = "progress"
        with patch.object(
            type(wo), "button_finish", autospec=True,
            return_value=True,
        ) as finish_mock:
            pkg.record_scan(workcenter_code="P8WC")
        self.assertEqual(
            finish_mock.call_count, 1,
            "record_scan must call mrp.workorder.button_finish exactly "
            "once per scan — the audit's no-duplicate-telemetry criterion")

    def test_record_scan_creates_one_consumption_and_logs_workcenter(self):
        pkg, wo, asset = self._make_package_with_tool_required_wo()

        pkg.record_scan()

        consumptions = self.Consumption.search([
            ("workorder_id", "=", wo.id),
        ])
        self.assertEqual(
            len(consumptions), 1,
            "scan-driven finish must create one tool consumption row")
        self.assertEqual(consumptions.asset_id, asset)
        self.assertEqual(consumptions.quantity, 1.0)
        self.assertTrue(wo.sbk_lifecycle_processed)

        log = json.loads(pkg.x_scan_log_json or "[]")
        self.assertEqual(log[-1]["wo_id"], wo.id)
        self.assertEqual(
            log[-1]["workcenter"], wo.workcenter_id.name,
            "scan log should fall back to the finished WO's workcenter")

        pkg.record_scan()
        consumptions_after_second_scan = self.Consumption.search([
            ("workorder_id", "=", wo.id),
        ])
        self.assertEqual(
            len(consumptions_after_second_scan), 1,
            "re-scanning must not duplicate lifecycle debit")

    # ------------------------------------------------------------------
    # Acceptance — PDF report renders (smoke test)
    # ------------------------------------------------------------------
    def test_traveler_pdf_renders(self):
        pkg = self._make_package()
        report = self.env.ref(
            "southbrook_floor_traveler.action_floor_traveler_report")
        rendered, content_type = report._render_qweb_html(
            report.report_name, [pkg.id])
        self.assertEqual(content_type, "html")
        # The QR payload must appear in the rendered output (the
        # template embeds qr_payload as fallback text).
        self.assertIn("sb-package:%s" % pkg.id, rendered.decode("utf-8"),
                      "rendered traveler must include the QR payload text")


@tagged("post_install", "-at_install", "southbrook", "floor_traveler", "p8")
class TestP8ScanEndpointAuth(HttpCase):
    """The scan endpoint advances/finishes production under sudo — it must
    reject callers who aren't internal mrp operators (regression: any
    authenticated user, incl. a portal customer, could finish any job)."""

    def _post_scan(self, payload):
        return self.url_open(
            "/southbrook/api/floor-traveler/scan",
            data=json.dumps({
                "jsonrpc": "2.0", "method": "call",
                "params": {"qr_payload": payload},
            }),
            headers={"Content-Type": "application/json"},
        )

    def test_non_mrp_user_is_forbidden(self):
        self.env["res.users"].create({
            "name": "P8 Plain User",
            "login": "p8_plain_user",
            "password": "p8_plain_user",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        self.authenticate("p8_plain_user", "p8_plain_user")
        resp = self._post_scan("sb-package:1")
        body = json.loads(resp.text)
        # jsonrpc envelope → result is the controller's returned dict.
        result = body.get("result", body)
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("error"), "forbidden")
