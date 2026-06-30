# SPDX-License-Identifier: LGPL-3.0-only
"""W037 (R8.4, 2026-06-27) — Offline scan queue tests.

JTBD: "When wifi drops for 30 seconds while I scan 5 cabinets, I want
those scans queued locally and synced when wifi returns — no manual
re-scan."

Server-side coverage (the Service Worker itself runs in the browser
and is exercised by manual smoke; here we cover the server contract
the SW relies on):
  * /sb/qr/sw.js route exists, serves the SW file, sets the
    Service-Worker-Allowed header so the browser grants /sb/qr/
    scope.
  * client_uuid replay dedup: a first call processes normally; a
    second call with the SAME client_uuid returns the CACHED result
    with replayed=True, and does NOT create a second scan-log row.
  * client_uuid rejects malformed values silently (no dedup, no
    error to caller).
  * ICP defaults are seeded by the data file.
  * Asset registration: offline_scan_queue.js is in both bundles;
    offline_scan_sw.js is NOT bundled (it's served by the SW route).
  * JS files carry the load-bearing identifiers (SW path,
    IndexedDB store name, ui badge states).
"""
import os
from contextlib import contextmanager
from unittest.mock import patch

from odoo.modules import get_module_path
from odoo.tests.common import HttpCase, TransactionCase, tagged

from odoo.addons.southbrook_qr_kit.controllers import qr_scan as qr_scan_mod


_QR_KIT_ROOT = get_module_path("southbrook_qr_kit")


class _FakeHttpRequest:
    def __init__(self):
        self.remote_addr = "127.0.0.1"
        self.headers = {"User-Agent": "pytest-w037"}


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
        "w037", "r8_4")
class TestW037OfflineScanQueueDedup(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Log = cls.env["southbrook.qr.scan.log"]
        cls.Controller = qr_scan_mod.QrScanController()
        # Clear the in-process dedup cache between test classes so
        # other test runs don't leak across.
        qr_scan_mod._CLIENT_UUID_CACHE.clear()

    def setUp(self):
        super().setUp()
        # Clear before EACH test so dedup state is deterministic.
        qr_scan_mod._CLIENT_UUID_CACHE.clear()

    # ------------------------------------------------------------------
    # ICP defaults seeded by data/qr_kit_config_parameters.xml
    # ------------------------------------------------------------------

    def test_10_icp_offline_queue_cap_default(self):
        ICP = self.env["ir.config_parameter"].sudo()
        self.assertEqual(
            ICP.get_param("southbrook.qr_kit.offline_queue_cap"),
            "500",
            "Default queue cap must be 500 entries.",
        )

    def test_11_icp_client_uuid_ttl_default(self):
        ICP = self.env["ir.config_parameter"].sudo()
        self.assertEqual(
            ICP.get_param("southbrook.qr_kit.client_uuid_ttl_sec"),
            "600",
            "Default replay TTL must be 600 seconds.",
        )

    # ------------------------------------------------------------------
    # client_uuid dedup
    # ------------------------------------------------------------------

    _GOOD_UUID = "11111111-2222-4333-8444-555555555555"
    _BAD_UUID = "not-a-uuid"

    def test_20_first_call_processes_normally(self):
        cached = qr_scan_mod._seen_client_uuid(self._GOOD_UUID)
        self.assertIsNone(cached, "First-seen uuid must not be cached.")

    def test_21_remember_then_seen_returns_cached(self):
        qr_scan_mod._remember_client_uuid(
            self._GOOD_UUID, {"ok": True, "thing": 42})
        cached = qr_scan_mod._seen_client_uuid(self._GOOD_UUID)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["thing"], 42)

    def test_22_malformed_uuid_is_ignored(self):
        qr_scan_mod._remember_client_uuid(
            self._BAD_UUID, {"ok": True, "thing": 99})
        self.assertIsNone(
            qr_scan_mod._seen_client_uuid(self._BAD_UUID),
            "Malformed uuids must never enter the cache.",
        )
        self.assertIsNone(
            qr_scan_mod._seen_client_uuid(""),
            "Empty client_uuid must short-circuit.")
        self.assertIsNone(
            qr_scan_mod._seen_client_uuid(None),
            "None client_uuid must short-circuit.")

    def test_23_dispatch_dedups_replay(self):
        """_dispatch with same client_uuid returns cached result,
        does NOT create a second scan_log row."""
        fake = _FakeRequest(self.env)
        # Prime: a known-bad payload returns an error result. The
        # error path also gets cached so replays don't re-spam the
        # log; that's the WHOLE point of dedup. We instead inject
        # a synthetic OK result via the public _remember helper and
        # verify the controller short-circuits.
        baseline_count = self.Log.search_count([])
        with _patched_request(fake):
            res = self.Controller._dispatch(
                payload="sb://garbage",  # parse will fail
                action="open", params={}, source="json",
                client_uuid=self._GOOD_UUID,
            )
        self.assertFalse(res.get("ok"))
        # First call: one log row created (the error row).
        after_first = self.Log.search_count([])
        self.assertEqual(after_first, baseline_count + 1)
        # SUCCEED path doesn't cache failure here (only the success
        # branch caches), so this test is mainly verifying the cache
        # is not poisoned with failure. Now we seed the cache with
        # a fake success and re-call: it should short-circuit.
        qr_scan_mod._remember_client_uuid(
            self._GOOD_UUID, {"ok": True, "result": "ok",
                              "record_name": "synthetic"})
        with _patched_request(fake):
            res2 = self.Controller._dispatch(
                payload="sb://garbage",
                action="open", params={}, source="json",
                client_uuid=self._GOOD_UUID,
            )
        self.assertTrue(res2.get("ok"))
        self.assertTrue(res2.get("replayed"),
                        "Cached replay must be tagged replayed=True")
        # And no extra log row from the replay path.
        after_replay = self.Log.search_count([])
        self.assertEqual(after_replay, after_first,
                         "Replay must not create another scan log row.")

    def test_24_ttl_expiry(self):
        """Once TTL elapses the cache entry is dropped."""
        import time as _t
        qr_scan_mod._remember_client_uuid(
            self._GOOD_UUID, {"ok": True})
        # Rewind the cached timestamp past the TTL.
        old_ts = qr_scan_mod._CLIENT_UUID_CACHE[self._GOOD_UUID]
        far_past = _t.time() - 99999
        qr_scan_mod._CLIENT_UUID_CACHE[self._GOOD_UUID] = (
            int(far_past), old_ts[1])
        # Need a fake request for the ICP read inside the TTL function.
        with _patched_request(_FakeRequest(self.env)):
            cached = qr_scan_mod._seen_client_uuid(self._GOOD_UUID)
        self.assertIsNone(cached, "Expired entry must not be returned.")
        self.assertNotIn(self._GOOD_UUID, qr_scan_mod._CLIENT_UUID_CACHE,
                         "Expired entry must be evicted on read.")

    # ------------------------------------------------------------------
    # Service Worker source file invariants
    # ------------------------------------------------------------------

    def _read(self, rel):
        with open(os.path.join(_QR_KIT_ROOT, rel), "r", encoding="utf-8") as fh:
            return fh.read()

    def test_30_sw_file_present_and_scoped(self):
        sw = self._read("static/src/js/offline_scan_sw.js")
        self.assertIn('SCOPE_PREFIX = "/sb/qr/"', sw,
                      "SW scope must be limited to /sb/qr/* per W037 spec.")
        self.assertIn('STORE_DB = "sb-offline-scan-queue"', sw,
                      "SW must use the documented IndexedDB store.")
        # Synthetic ack contract used by the UI badge.
        self.assertIn("queued: true", sw)
        self.assertIn("queued_at:", sw)

    def test_31_client_glue_carries_load_bearing_ids(self):
        glue = self._read("static/src/js/offline_scan_queue.js")
        self.assertIn("/southbrook_qr_kit/static/src/js/offline_scan_sw.js",
                      glue, "Glue must reference the SW path.")
        self.assertIn('SW_SCOPE = "/sb/qr/"', glue)
        self.assertIn("uuidv4", glue,
                      "Glue must mint client_uuid v4.")
        self.assertIn("client_uuid", glue,
                      "Glue must attach client_uuid to outgoing scans.")
        # Three badge states required by spec.
        for state_class in (
            "sb-state-online", "sb-state-queued", "sb-state-draining",
        ):
            self.assertIn(state_class, glue,
                          f"Badge missing state class {state_class}")

    def test_32_manifest_bundles_glue_not_sw(self):
        """The glue must be in both asset bundles; the SW itself must
        NOT be bundled (it's served by /sb/qr/sw.js so it can take
        scope over /sb/qr/* instead of /addon/static/...)."""
        manifest = self._read("__manifest__.py")
        self.assertIn(
            "southbrook_qr_kit/static/src/js/offline_scan_queue.js",
            manifest, "Glue must be in assets.")
        self.assertNotIn(
            "southbrook_qr_kit/static/src/js/offline_scan_sw.js",
            manifest,
            "SW must NOT be bundled — served via /sb/qr/sw.js route.")


@tagged("post_install", "-at_install", "southbrook", "qr",
        "w037", "r8_4")
class TestW037ServiceWorkerRoute(HttpCase):
    """End-to-end: the /sb/qr/sw.js route serves the SW file with the
    Service-Worker-Allowed header so browsers grant it /sb/qr/ scope."""

    def test_40_sw_route_serves_with_scope_header(self):
        resp = self.url_open("/sb/qr/sw.js")
        self.assertEqual(resp.status_code, 200)
        # Header is the load-bearing security contract — without it
        # the browser silently scopes the SW to /sb/qr/ only (which
        # is what we want), but with our SW path being /sb/qr/sw.js
        # the default scope IS /sb/qr/, so even without the explicit
        # header things work. We still set the header for forward-
        # compat (we may move the file later).
        self.assertEqual(
            resp.headers.get("Service-Worker-Allowed"), "/sb/qr/",
            "Service-Worker-Allowed must widen scope to /sb/qr/.")
        self.assertIn("javascript", resp.headers.get("Content-Type", ""))
        # The file should be the actual SW source, not an error page.
        self.assertIn('SCOPE_PREFIX = "/sb/qr/"', resp.text)
