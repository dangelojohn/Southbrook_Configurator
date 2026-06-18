# SPDX-License-Identifier: LGPL-3.0-only
"""P8 — Floor Traveler: QR payload, traveler-PDF integration, scan log,
no-duplicate-telemetry.

The audit's load-bearing acceptance is the "exactly once" guarantee on
tool-consumption debit — verified here by asserting that a simulated
scan -> record_scan -> mrp.workorder.button_finish call writes one (and
only one) entry in the scan log per WO advance.
"""
import json

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "floor_traveler", "p8")
class TestP8FloorTraveler(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Package = cls.env["sb.production.package"]
        cls.MO = cls.env["mrp.production"]
        cls.Cutlist = cls.env["sb.cutlist"]
        cls.Hardware = cls.env["sb.hardware.package"]
        cls.Product = cls.env["product.product"]

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
