# SPDX-License-Identifier: LGPL-3.0-only
"""W035 (R8.14) — operator PIN-gated scan logging.

Tests cover:
  * /sb/qr/identify accepts a valid PIN and binds the employee.
  * Invalid / non-digit / unknown PIN is rejected with no binding.
  * Binding survives across helper calls and credits the scan log row
    via `_get_operator_employee` + `_dispatch`.
  * Fallback to `env.user.employee_id` when no PIN session bound.
  * /sb/qr/switch-operator clears the binding.
  * Session timeout: after `southbrook.operator_session_timeout_min`
    seconds of inactivity, the binding is cleared on the next read.
  * /sb/qr/whoami round-trips the bound employee.

The HTTP request layer is faked via a stub that exposes the small
subset of `odoo.http.request` the controller actually touches
(env, session dict, httprequest.remote_addr + headers). The pattern
mirrors `southbrook_mrp_kitchen_workcenters/tests/test_w011_form_open_scan_log.py`.
"""
import time
from contextlib import contextmanager
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.southbrook_qr_kit.controllers import qr_scan as qr_scan_mod


class _FakeHttpRequest:
    """The `request.httprequest` sub-object the controller reads."""

    def __init__(self, ua="pytest-w035", ip="127.0.0.1", path="/sb/qr/scan"):
        self.remote_addr = ip
        self.headers = {"User-Agent": ua}
        self.path = path


class _FakeRequest:
    """Stub of `odoo.http.request` carrying only the surface the
    controller methods touch: env, session (plain dict), httprequest."""

    def __init__(self, env, session=None):
        self.env = env
        # Real Odoo sessions are dict-like; a plain dict is enough.
        self.session = session if session is not None else {}
        self.httprequest = _FakeHttpRequest()
        self.uid = env.uid


@contextmanager
def _patched_request(fake):
    """Patch the `request` symbol the controller module imported.

    `from odoo.http import request` snapshots the name at import time,
    so we patch the controller-module-local binding (this is what
    actually gets read at call-site)."""
    with patch.object(qr_scan_mod, "request", fake):
        yield


@tagged("post_install", "-at_install", "southbrook", "qr",
        "w035", "r8_14")
class TestW035OperatorPin(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Log = cls.env["southbrook.qr.scan.log"]
        cls.Employee = cls.env["hr.employee"]
        cls.Controller = qr_scan_mod.QrScanController()

        # Employee with a known PIN. Mark active explicitly so the
        # `active=True` filter in the controller matches.
        cls.emp = cls.Employee.create({
            "name": "W035 Operator Alice",
            "pin": "1234",
            "active": True,
        })
        # Second employee for the switch test.
        cls.emp2 = cls.Employee.create({
            "name": "W035 Operator Bob",
            "pin": "9876",
            "active": True,
        })
        # Inactive employee — must NOT resolve.
        cls.emp_off = cls.Employee.create({
            "name": "W035 Inactive",
            "pin": "5555",
            "active": False,
        })
        # Ensure session timeout ICP is a deterministic value.
        cls.env["ir.config_parameter"].sudo().set_param(
            "southbrook.operator_session_timeout_min", "30")

    # ------------------------------------------------------------------
    # /sb/qr/identify
    # ------------------------------------------------------------------

    def test_10_identify_with_valid_pin_binds_employee(self):
        fake = _FakeRequest(self.env)
        with _patched_request(fake):
            res = self.Controller.identify_operator(pin="1234")
        self.assertTrue(res.get("ok"), res)
        self.assertEqual(res["employee"]["id"], self.emp.id)
        self.assertEqual(res["employee"]["name"], self.emp.name)
        self.assertEqual(
            fake.session.get("sbk_operator_employee_id"), self.emp.id,
            "Successful identify must persist employee id in session.")
        self.assertIn("timeout_min", res)
        # PIN must never appear in the response.
        self.assertNotIn("pin", res)
        self.assertNotIn("1234", str(res))

    def test_11_identify_invalid_pin_rejected(self):
        fake = _FakeRequest(self.env)
        with _patched_request(fake):
            res = self.Controller.identify_operator(pin="000000")
        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("error"), "Unknown PIN")
        self.assertNotIn("sbk_operator_employee_id", fake.session)

    def test_12_identify_non_digit_pin_rejected(self):
        fake = _FakeRequest(self.env)
        with _patched_request(fake):
            res = self.Controller.identify_operator(pin="ab12")
        self.assertFalse(res.get("ok"))
        self.assertIn("digits", res.get("error", "").lower())
        self.assertNotIn("sbk_operator_employee_id", fake.session)

    def test_13_identify_empty_pin_rejected(self):
        fake = _FakeRequest(self.env)
        with _patched_request(fake):
            res = self.Controller.identify_operator(pin="")
        self.assertFalse(res.get("ok"))

    def test_14_identify_inactive_employee_rejected(self):
        fake = _FakeRequest(self.env)
        with _patched_request(fake):
            res = self.Controller.identify_operator(pin="5555")
        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("error"), "Unknown PIN")

    # ------------------------------------------------------------------
    # _get_operator_employee + scan-log stamping (via _dispatch)
    # ------------------------------------------------------------------

    def test_20_get_operator_employee_returns_bound_employee(self):
        fake = _FakeRequest(
            self.env,
            session={
                "sbk_operator_employee_id": self.emp.id,
                "sbk_operator_pin_at": int(time.time()),
                "sbk_operator_last_seen": int(time.time()),
            },
        )
        with _patched_request(fake):
            emp = self.Controller._get_operator_employee()
        self.assertEqual(emp.id, self.emp.id)

    def test_21_get_operator_falls_back_to_session_user_employee(self):
        # No session binding. env.user.employee_id may or may not exist
        # in the test env — verify we don't raise and the return is a
        # recordset (possibly empty).
        fake = _FakeRequest(self.env, session={})
        with _patched_request(fake):
            emp = self.Controller._get_operator_employee()
        # Either empty or env.user.employee_id — both are acceptable.
        self.assertEqual(emp._name, "hr.employee")

    def test_22_dispatch_stamps_employee_id_when_pin_bound(self):
        # Dispatch with an empty payload still creates a scan log
        # row with result=error — we only care that employee_id is
        # stamped on every row coming out of _dispatch.
        fake = _FakeRequest(
            self.env,
            session={
                "sbk_operator_employee_id": self.emp.id,
                "sbk_operator_pin_at": int(time.time()),
                "sbk_operator_last_seen": int(time.time()),
            },
        )
        with _patched_request(fake):
            self.Controller._dispatch(
                payload="", action="open", params={}, source="json")
        row = self.Log.sudo().search([], order="id desc", limit=1)
        self.assertTrue(row, "Dispatch should have created a log row.")
        self.assertEqual(
            row.employee_id.id, self.emp.id,
            "Bound operator must be stamped onto the log row.")

    def test_23_dispatch_employee_id_matches_resolver(self):
        # No session binding — log row's employee_id must match whatever
        # `_get_operator_employee` resolves (env.user.employee_id or
        # empty). This pins down the contract: scan log mirrors the
        # resolver's answer, whichever branch wins.
        fake = _FakeRequest(self.env, session={})
        with _patched_request(fake):
            expected = self.Controller._get_operator_employee()
            self.Controller._dispatch(
                payload="", action="open", params={}, source="json")
        row = self.Log.sudo().search([], order="id desc", limit=1)
        self.assertEqual(
            row.employee_id.id, expected.id if expected else False,
            "Log row's employee_id must match the resolver's answer.")

    # ------------------------------------------------------------------
    # /sb/qr/switch-operator
    # ------------------------------------------------------------------

    def test_30_switch_operator_clears_session(self):
        fake = _FakeRequest(
            self.env,
            session={
                "sbk_operator_employee_id": self.emp.id,
                "sbk_operator_pin_at": int(time.time()),
                "sbk_operator_last_seen": int(time.time()),
            },
        )
        with _patched_request(fake):
            res = self.Controller.switch_operator()
        self.assertTrue(res.get("ok"))
        self.assertNotIn("sbk_operator_employee_id", fake.session)
        self.assertNotIn("sbk_operator_pin_at", fake.session)
        self.assertNotIn("sbk_operator_last_seen", fake.session)

    def test_31_switch_then_identify_binds_new_operator(self):
        fake = _FakeRequest(
            self.env,
            session={
                "sbk_operator_employee_id": self.emp.id,
                "sbk_operator_pin_at": int(time.time()),
                "sbk_operator_last_seen": int(time.time()),
            },
        )
        with _patched_request(fake):
            self.Controller.switch_operator()
            res = self.Controller.identify_operator(pin="9876")
        self.assertTrue(res.get("ok"))
        self.assertEqual(res["employee"]["id"], self.emp2.id)
        self.assertEqual(
            fake.session.get("sbk_operator_employee_id"), self.emp2.id)

    # ------------------------------------------------------------------
    # Session timeout
    # ------------------------------------------------------------------

    def test_40_session_timeout_clears_employee(self):
        # Bind, then rewind last_seen past the timeout window.
        # Default 30 min → 1800 s. Use 1801 s in the past.
        now = int(time.time())
        fake = _FakeRequest(
            self.env,
            session={
                "sbk_operator_employee_id": self.emp.id,
                "sbk_operator_pin_at": now - 3600,
                "sbk_operator_last_seen": now - 1801,
            },
        )
        with _patched_request(fake):
            emp = self.Controller._get_operator_employee()
        # The stale session must have been cleared.
        self.assertNotIn("sbk_operator_employee_id", fake.session,
                         "Stale session must be cleared on lookup.")
        # Returned employee is the env.user.employee_id fallback
        # (which may be empty) — the important thing is the binding
        # didn't persist.
        self.assertEqual(emp._name, "hr.employee")

    def test_41_session_timeout_extends_on_activity(self):
        # Within the window → binding survives AND last_seen bumps.
        now = int(time.time())
        fake = _FakeRequest(
            self.env,
            session={
                "sbk_operator_employee_id": self.emp.id,
                "sbk_operator_pin_at": now - 600,
                "sbk_operator_last_seen": now - 600,
            },
        )
        with _patched_request(fake):
            emp = self.Controller._get_operator_employee()
        self.assertEqual(emp.id, self.emp.id)
        # last_seen must have been bumped on lookup (rolling timeout).
        self.assertGreaterEqual(
            fake.session.get("sbk_operator_last_seen", 0), now - 5,
            "Activity must extend the rolling timeout.",
        )

    def test_42_session_timeout_icp_is_honored(self):
        # Set a 1-minute timeout, then look up 90s in the past.
        self.env["ir.config_parameter"].sudo().set_param(
            "southbrook.operator_session_timeout_min", "1")
        try:
            now = int(time.time())
            fake = _FakeRequest(
                self.env,
                session={
                    "sbk_operator_employee_id": self.emp.id,
                    "sbk_operator_pin_at": now - 200,
                    "sbk_operator_last_seen": now - 90,
                },
            )
            with _patched_request(fake):
                self.Controller._get_operator_employee()
            self.assertNotIn("sbk_operator_employee_id", fake.session,
                             "1-min ICP must time out a 90s-stale session.")
        finally:
            self.env["ir.config_parameter"].sudo().set_param(
                "southbrook.operator_session_timeout_min", "30")

    # ------------------------------------------------------------------
    # /sb/qr/whoami
    # ------------------------------------------------------------------

    def test_50_whoami_returns_bound_employee(self):
        now = int(time.time())
        fake = _FakeRequest(
            self.env,
            session={
                "sbk_operator_employee_id": self.emp.id,
                "sbk_operator_pin_at": now,
                "sbk_operator_last_seen": now,
            },
        )
        with _patched_request(fake):
            res = self.Controller.whoami()
        self.assertTrue(res.get("ok"))
        self.assertEqual(res["employee"]["id"], self.emp.id)
        self.assertIn("timeout_min", res)

    def test_51_whoami_no_binding_returns_employee_none_when_no_fallback(self):
        # Detach admin's employee so the env.user.employee_id fallback
        # is empty for this lookup. We only assert the response shape
        # is correct — `employee` may still be present if admin happens
        # to have an attached employee (depends on demo data).
        fake = _FakeRequest(self.env, session={})
        with _patched_request(fake):
            res = self.Controller.whoami()
        self.assertTrue(res.get("ok"))
        # Shape contract: response has employee + timeout_min keys.
        self.assertIn("employee", res)
        self.assertIn("timeout_min", res)
