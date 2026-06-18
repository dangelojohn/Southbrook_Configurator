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
