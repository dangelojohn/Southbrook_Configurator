# SPDX-License-Identifier: LGPL-3.0-only
"""Regression tests for the QR-Kit security hardening pass.

Covers the two behaviours most important to keep from regressing:
  * parse() rejects payloads carrying any query key other than t/s, so a
    validly-signed QR cannot smuggle extra (unsigned) content downstream
    into HTML/JS renderers (the query-param XSS root cause).
  * /sb/qr/identify throttles per-IP PIN brute force.
"""
from contextlib import contextmanager
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.southbrook_qr_kit.controllers import qr_scan as qr_scan_mod


class _FakeHttpRequest:
    def __init__(self, ip="127.0.0.1"):
        self.remote_addr = ip
        self.headers = {"User-Agent": "pytest-sec"}
        self.path = "/sb/qr/identify"


class _FakeRequest:
    def __init__(self, env, ip="127.0.0.1"):
        self.env = env
        self.session = {}
        self.httprequest = _FakeHttpRequest(ip=ip)
        self.uid = env.uid


@contextmanager
def _patched_request(fake):
    with patch.object(qr_scan_mod, "request", fake):
        yield


@tagged("post_install", "-at_install", "southbrook_qr_kit")
class TestQrKitSecurityHardening(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Payload = cls.env["southbrook.qr.payload"]

    def test_valid_payload_round_trips(self):
        payload = self.Payload.build("loc", 42)
        parsed = self.Payload.parse(payload)
        self.assertTrue(parsed["valid_signature"])
        self.assertEqual(parsed["kind"], "loc")
        self.assertEqual(parsed["ident"], 42)

    def test_extra_query_key_is_rejected(self):
        # A validly-signed payload with an appended (unsigned) query key must
        # be rejected outright, not returned as valid_signature=True.
        payload = self.Payload.build("ship", 7)
        smuggled = payload + "&x=%3C/script%3E%3Cscript%3Eevil%3C/script%3E"
        with self.assertRaises(UserError):
            self.Payload.parse(smuggled)

    def test_pin_bruteforce_is_throttled(self):
        qr_scan_mod._PIN_FAIL.clear()
        ip = "203.0.113.77"
        fake = _FakeRequest(self.env, ip=ip)
        ctrl = qr_scan_mod.QrScanController()
        with _patched_request(fake):
            # A PIN unlikely to exist in a demo-less DB; 5 misses allowed...
            for _i in range(5):
                r = ctrl.identify_operator(pin="00000000")
                self.assertFalse(r["ok"])
                self.assertEqual(r["error"], "Unknown PIN")
            # ...the 6th is throttled before the DB is even queried.
            r6 = ctrl.identify_operator(pin="00000000")
            self.assertFalse(r6["ok"])
            self.assertIn("Too many attempts", r6["error"])
        qr_scan_mod._PIN_FAIL.clear()
