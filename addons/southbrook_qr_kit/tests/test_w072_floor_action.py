# SPDX-License-Identifier: LGPL-3.0-only
"""W072 (R8.3, 2026-06-27) — Public floor-action mini-framework tests.

Tests cover:
  * The three built-in kinds (pod, install_check, temp_labor_signin)
    are registered and resolvable.
  * Render-form gates: unknown action -> 404; missing payload -> 400;
    invalid signature -> 403; wrong expected kind -> 400.
  * Submit dispatch: install_check writes chatter on shipping unit;
    temp_labor_signin returns ok with valid name+contact, rejects empty.
  * Rate-limit guard rejects after the configured limit.
  * Scan-log row written for every floor request (ok and fail).
  * Legacy /sb/qr/pod and /sb/qr/pod/submit URLs still exist on the
    QrScanController (backward compat).
"""
from contextlib import contextmanager
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.southbrook_qr_kit.controllers import (
    floor_action as floor_mod,
    qr_scan as qr_scan_mod,
)


class _FakeHttpRequest:
    def __init__(self, ip="10.0.0.1"):
        self.remote_addr = ip
        self.headers = {"User-Agent": "pytest-w072"}
        self.path = "/sb/floor/test"


class _FakeRequest:
    def __init__(self, env, ip="10.0.0.1"):
        self.env = env
        self.session = {}
        self.httprequest = _FakeHttpRequest(ip=ip)
        self.uid = env.uid

    def make_response(self, body, status=200, headers=None):
        # Mimic Odoo's http.Response surface so the controller helpers
        # can keep calling request.make_response.
        return _FakeResponse(body, status=status, headers=headers)


class _FakeResponse:
    def __init__(self, body, status=200, headers=None):
        self.body = body
        self.status_code = status
        self.headers = headers or []

    def get_data(self, as_text=False):
        return self.body if as_text else self.body.encode("utf-8")

    def set_data(self, body):
        self.body = body


@contextmanager
def _patched_floor_request(fake):
    """Patch the `request` symbol the floor_action module imported."""
    with patch.object(floor_mod, "request", fake):
        yield


@tagged("post_install", "-at_install", "southbrook", "qr",
        "w072", "r8_3")
class TestW072FloorAction(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Kind = cls.env["southbrook.floor.action.kind"]
        cls.Payload = cls.env["southbrook.qr.payload"].sudo()
        cls.Log = cls.env["southbrook.qr.scan.log"].sudo()
        cls.Unit = cls.env["southbrook.shipping.unit"]
        cls.Loc = cls.env["stock.location"]
        cls.Ctrl = floor_mod.FloorActionController()

        # Knock out rate limit for most tests (one test re-enables it).
        cls.env["ir.config_parameter"].sudo().set_param(
            "southbrook.floor_action.rate_limit", "10000")
        cls.env["ir.config_parameter"].sudo().set_param(
            "southbrook.floor_action.rate_window_sec", "60")
        # Clear the in-process rate bucket between test runs (otherwise
        # tests in the same worker bleed counters).
        floor_mod._RATE_BUCKETS.clear()

        # A shipping unit (POD + install_check target).
        cls.unit = cls.Unit.create({
            "name": "W072 Unit", "kind": "carton",
        })
        # An internal stock location (temp_labor_signin target).
        cls.loc = cls.Loc.search([("usage", "=", "internal")], limit=1)
        if not cls.loc:
            cls.loc = cls.Loc.create({
                "name": "W072 Bay", "usage": "internal"})

    # ------------------------------------------------------------------
    # Kind registry
    # ------------------------------------------------------------------
    def test_10_three_kinds_registered(self):
        for slug, model in (
            ("pod", "southbrook.floor.action.kind.pod"),
            ("install_check",
             "southbrook.floor.action.kind.install_check"),
            ("temp_labor_signin",
             "southbrook.floor.action.kind.temp_labor_signin"),
        ):
            handler = self.Kind.resolve_kind(slug)
            self.assertTrue(handler,
                            "Kind '%s' must be registered" % slug)
            self.assertEqual(handler._name, model)

    def test_11_unknown_kind_returns_none(self):
        self.assertFalse(self.Kind.resolve_kind("nope"))
        self.assertFalse(self.Kind.resolve_kind(""))
        self.assertFalse(self.Kind.resolve_kind(None))

    # ------------------------------------------------------------------
    # Dispatcher: GET /sb/floor/<action>
    # ------------------------------------------------------------------
    def test_20_render_unknown_action_404(self):
        fake = _FakeRequest(self.env)
        with _patched_floor_request(fake):
            resp = self.Ctrl.floor_render(action="nope", p="anything")
        self.assertEqual(resp.status_code, 404)

    def test_21_render_invalid_signature_403(self):
        fake = _FakeRequest(self.env, ip="10.0.0.2")
        bad = "sb://ship/%d?t=1&s=forged" % self.unit.id
        with _patched_floor_request(fake):
            resp = self.Ctrl.floor_render(action="install_check", p=bad)
        self.assertEqual(resp.status_code, 403)

    def test_22_render_wrong_kind_400(self):
        # install_check wants 'ship' QR; pass a 'loc' payload.
        fake = _FakeRequest(self.env, ip="10.0.0.3")
        loc_payload = self.Payload.build("loc", self.loc.id)
        with _patched_floor_request(fake):
            resp = self.Ctrl.floor_render(
                action="install_check", p=loc_payload)
        self.assertEqual(resp.status_code, 400)

    def test_23_render_install_check_ok(self):
        fake = _FakeRequest(self.env, ip="10.0.0.4")
        payload = self.Payload.build("ship", self.unit.id)
        with _patched_floor_request(fake):
            resp = self.Ctrl.floor_render(
                action="install_check", p=payload)
        # render_form returns HTML body string -> controller wraps it.
        self.assertEqual(resp.status_code, 200)
        # And a scan-log row was written for forensics.
        log = self.Log.search(
            [("action", "=", "floor:install_check"),
             ("target_id", "=", self.unit.id)],
            order="id desc", limit=1)
        self.assertTrue(log)
        self.assertEqual(log.result, "ok")

    # ------------------------------------------------------------------
    # Dispatcher: POST /sb/floor/<action>/submit
    # ------------------------------------------------------------------
    def test_30_submit_install_check_writes_chatter(self):
        fake = _FakeRequest(self.env, ip="10.0.0.5")
        payload = self.Payload.build("ship", self.unit.id)
        before = len(self.unit.message_ids)
        with _patched_floor_request(fake):
            res = self.Ctrl.floor_submit(
                action="install_check",
                payload=payload,
                installer="John Tradesperson",
                condition="minor",
                notes="Hinge needs adjustment",
            )
        self.assertTrue(res.get("ok"), res)
        self.unit.invalidate_recordset(["message_ids"])
        self.assertGreater(len(self.unit.message_ids), before)
        # Sanity: message body mentions installer + condition.
        latest = self.unit.message_ids[:1]
        self.assertIn("John Tradesperson", latest.body or "")
        self.assertIn("Minor", latest.body or "")

    def test_31_submit_install_check_rejects_empty_installer(self):
        fake = _FakeRequest(self.env, ip="10.0.0.6")
        payload = self.Payload.build("ship", self.unit.id)
        with _patched_floor_request(fake):
            res = self.Ctrl.floor_submit(
                action="install_check",
                payload=payload, installer="", condition="ok",
            )
        self.assertFalse(res.get("ok"))
        self.assertIn("installer", res.get("error", "").lower())

    def test_32_submit_temp_labor_signin_ok(self):
        fake = _FakeRequest(self.env, ip="10.0.0.7")
        payload = self.Payload.build("loc", self.loc.id)
        with _patched_floor_request(fake):
            res = self.Ctrl.floor_submit(
                action="temp_labor_signin",
                payload=payload,
                full_name="Jane Helper",
                contact="555-1212",
                crew="ABC Crew",
            )
        self.assertTrue(res.get("ok"), res)
        self.assertIn("Jane", res.get("message", ""))

    def test_33_submit_temp_labor_signin_rejects_missing_contact(self):
        fake = _FakeRequest(self.env, ip="10.0.0.8")
        payload = self.Payload.build("loc", self.loc.id)
        with _patched_floor_request(fake):
            res = self.Ctrl.floor_submit(
                action="temp_labor_signin",
                payload=payload,
                full_name="Sam Solo", contact="",
            )
        self.assertFalse(res.get("ok"))
        self.assertIn("contact", res.get("error", "").lower())

    def test_34_submit_unknown_action(self):
        fake = _FakeRequest(self.env, ip="10.0.0.9")
        payload = self.Payload.build("ship", self.unit.id)
        with _patched_floor_request(fake):
            res = self.Ctrl.floor_submit(
                action="bogus_action", payload=payload)
        self.assertFalse(res.get("ok"))
        self.assertIn("Unknown floor action", res.get("error", ""))

    # ------------------------------------------------------------------
    # Rate limit
    # ------------------------------------------------------------------
    def test_40_rate_limit_enforced(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "southbrook.floor_action.rate_limit", "3")
        self.env["ir.config_parameter"].sudo().set_param(
            "southbrook.floor_action.rate_window_sec", "60")
        floor_mod._RATE_BUCKETS.clear()
        fake = _FakeRequest(self.env, ip="10.99.99.99")
        payload = self.Payload.build("ship", self.unit.id)
        results = []
        with _patched_floor_request(fake):
            for _ in range(5):
                results.append(self.Ctrl.floor_submit(
                    action="install_check", payload=payload,
                    installer="X", condition="ok"))
        # At least one of the last responses must be the rate-limit
        # refusal — the first 3 should succeed (or fail on content, but
        # NOT on rate); calls 4+ trip the limit.
        rate_refusals = [r for r in results
                         if "Rate limit" in (r.get("error") or "")]
        self.assertTrue(rate_refusals,
                        "Expected at least one rate-limit refusal "
                        "after the limit of 3")
        # Restore for any further tests in the same worker.
        self.env["ir.config_parameter"].sudo().set_param(
            "southbrook.floor_action.rate_limit", "10000")
        floor_mod._RATE_BUCKETS.clear()

    # ------------------------------------------------------------------
    # Backward compat — legacy /sb/qr/pod must still exist
    # ------------------------------------------------------------------
    def test_50_legacy_pod_routes_still_exist(self):
        ctrl = qr_scan_mod.QrScanController()
        # `pod_capture` is the GET; `pod_submit` is the POST.
        self.assertTrue(callable(getattr(ctrl, "pod_capture", None)),
                        "Legacy /sb/qr/pod route must still exist for "
                        "backward compat with QR labels in the field.")
        self.assertTrue(callable(getattr(ctrl, "pod_submit", None)),
                        "Legacy /sb/qr/pod/submit route must still "
                        "exist.")
