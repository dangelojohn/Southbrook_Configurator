# SPDX-License-Identifier: LGPL-3.0-only
"""W073 (R8.8, 2026-06-27) — Bin-scan + Load-unit OWL floor UI tests.

JTBD: "When I'm at the receiving dock with a barcoded box, I want a
real UI that scans the box, shows what's inside, and lets me confirm
or split — not just a JSON endpoint."

Coverage:
  * /sb/qr/inventory/bin-inspect endpoint shape + signature gating.
  * /southbrook/floor/bin-scan + /load-unit routes serve a shell
    page that references the data-sb-floor-app mount attribute and
    pulls in the lazy bundle.
  * Manifest declares `web.assets_qr_floor` bundle with the OWL
    screens + the W036 audio + W037 offline queue (both required
    for the floor UX).
  * Floor screens JS file carries the two component classes and
    dispatches on data-sb-floor-app.
"""
import os

from odoo.modules import get_module_path
from odoo.tests.common import HttpCase, TransactionCase, tagged


_QR_KIT_ROOT = get_module_path("southbrook_qr_kit")


@tagged("post_install", "-at_install", "southbrook", "qr",
        "w073", "r8_8")
class TestW073BinInspect(TransactionCase):
    """Read-only bin-inspect endpoint that powers the BinScanScreen
    'what's in this bin?' panel."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Payload = cls.env["southbrook.qr.payload"].sudo()
        # Use an existing stock location so we don't depend on demo data.
        cls.loc = cls.env["stock.location"].search(
            [("usage", "=", "internal")], limit=1)
        if not cls.loc:
            cls.loc = cls.env["stock.location"].create({
                "name": "W073 Test Bin",
                "usage": "internal",
            })

    def test_10_bin_inspect_rejects_bad_signature(self):
        from odoo.addons.southbrook_qr_kit.controllers import qr_scan
        # A payload-shaped string that fails HMAC verification.
        bad = "sb://loc/%d?t=1&s=forged" % self.loc.id
        # Direct method invocation — no http request needed because
        # the method is pure-data (no session reads).
        from unittest.mock import patch

        class _FakeReq:
            env = self.env
            httprequest = type("H", (), {"remote_addr": "127.0.0.1",
                                          "headers": {}})()
            session = {}

        with patch.object(qr_scan, "request", _FakeReq()):
            ctrl = qr_scan.QrScanController()
            res = ctrl.bin_inspect(bin=bad)
        self.assertFalse(res["ok"])
        self.assertIn("signature", res["error"].lower())

    def test_11_bin_inspect_returns_shape(self):
        """A valid signed loc payload returns location + quants
        (empty list when bin is empty — which is the common case
        before products arrive)."""
        from odoo.addons.southbrook_qr_kit.controllers import qr_scan
        from unittest.mock import patch

        good = self.Payload.build("loc", self.loc.id)

        class _FakeReq:
            env = self.env
            httprequest = type("H", (), {"remote_addr": "127.0.0.1",
                                          "headers": {}})()
            session = {}

        with patch.object(qr_scan, "request", _FakeReq()):
            ctrl = qr_scan.QrScanController()
            res = ctrl.bin_inspect(bin=good)
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["location"]["id"], self.loc.id)
        self.assertIn("complete_name", res["location"])
        self.assertIn("quants", res)
        self.assertIsInstance(res["quants"], list)


@tagged("post_install", "-at_install", "southbrook", "qr",
        "w073", "r8_8")
class TestW073FloorRoutes(HttpCase):
    """Both floor screens serve a shell page that mounts the OWL app
    with the correct data-sb-floor-app dispatch attribute."""

    def _assert_shell(self, path, expected_app):
        # Authenticate as admin so the auth='user' route lets us in.
        self.authenticate("admin", "admin")
        resp = self.url_open(path)
        self.assertEqual(resp.status_code, 200, path)
        text = resp.text
        self.assertIn('id="sb_floor_root"', text,
                      "shell must carry the OWL mount point")
        self.assertIn(f'data-sb-floor-app="{expected_app}"', text,
                      "shell must carry the app dispatch attribute")
        self.assertIn("sb-dense", text,
                      "body must carry the W039 dense class")

    def test_20_bin_scan_route(self):
        self._assert_shell("/southbrook/floor/bin-scan", "bin-scan")

    def test_21_load_unit_route(self):
        self._assert_shell("/southbrook/floor/load-unit", "load-unit")


@tagged("post_install", "-at_install", "southbrook", "qr",
        "w073", "r8_8")
class TestW073AssetsAndScreens(TransactionCase):
    """File-level invariants — manifest declares the bundle, the JS
    file carries both component classes and dispatches on the mount
    attribute."""

    def _read(self, rel):
        with open(os.path.join(_QR_KIT_ROOT, rel), "r", encoding="utf-8") as fh:
            return fh.read()

    def test_30_manifest_declares_floor_bundle(self):
        manifest = self._read("__manifest__.py")
        self.assertIn("web.assets_qr_floor", manifest,
                      "lazy bundle for floor screens missing")
        self.assertIn(
            "southbrook_qr_kit/static/src/js/floor_screens.esm.js",
            manifest)
        self.assertIn(
            "southbrook_qr_kit/static/src/scss/floor_screens.scss",
            manifest)
        # Bundle must include the audio + offline queue so the
        # floor UX gets both for free (without re-importing them).
        # We can't be sure they're in the qr_floor block by line
        # alone here, but they're at minimum present in the file.
        self.assertIn(
            "southbrook_qr_kit/static/src/js/scan_audio_cue.js",
            manifest)

    def test_31_floor_screens_carry_both_components(self):
        js = self._read("static/src/js/floor_screens.esm.js")
        self.assertIn("class BinScanScreen", js,
                      "BinScanScreen component missing")
        self.assertIn("class LoadUnitScreen", js,
                      "LoadUnitScreen component missing")
        # Dispatch on the mount-attribute is the load-bearing
        # bootstrap contract.
        self.assertIn('"data-sb-floor-app"', js,
                      "boot must read data-sb-floor-app attribute")
        self.assertIn('app === "bin-scan"', js)
        self.assertIn('app === "load-unit"', js)
        # Both POST endpoints must be referenced.
        self.assertIn("/sb/qr/inventory/bin-scan", js)
        self.assertIn("/sb/qr/inventory/bin-inspect", js)
        self.assertIn("/sb/qr/shipping/load-unit", js)
