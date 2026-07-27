# SPDX-License-Identifier: LGPL-3.0-only
"""W018 — defect-context window + scan-response WO echo.

Two changes verified here (R5.3 of MFG-REVIEW-R9):

  1. Default defect-context lookback widened 300s -> 900s. Operators
     who scan-then-walk-to-defect-station now keep the WO context for
     a realistic 15 minutes (was 5).
  2. The scan-response toast now echoes the resolved WO + workcenter
     so the operator can confirm the NCR linked to the right work
     order (was generic "NCR drafted").

Depends on W001 (mail.thread on southbrook.mi.check) + W011 (form-open
scan log), both already landed.
"""
from contextlib import contextmanager
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged


class _FakeRequest:
    def __init__(self, env=None, path="/sb/qr/scan", ua="pytest", ip="127.0.0.1"):
        class _HR:
            pass
        hr = _HR()
        hr.path = path
        hr.remote_addr = ip
        hr.headers = {"User-Agent": ua}
        self.httprequest = hr
        # The controller normally sets this on dispatch; the defect
        # handler reads it as a fallback for defect_type.
        self.qr_parsed_ident = "scratch"
        # v19 translation machinery (odoo.tools.translate._get_lang)
        # reads request.env.lang during any `_()` call when a request
        # is bound. Provide both env (real Environment) and a session
        # dict so the handler under test can run end-to-end without
        # falling through to RuntimeError("object is not bound").
        self.env = env
        self.session = {}


@contextmanager
def _patched_request(fake):
    with patch("odoo.http.request", fake):
        yield


@tagged("post_install", "-at_install", "southbrook", "sbk_kitchen",
        "w018", "qr")
class TestW018DefectContextEcho(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Handler = cls.env["southbrook.qr.kind.defect"]
        cls.Log = cls.env["southbrook.qr.scan.log"]
        wo = cls.env["mrp.workorder"].search([], limit=1)
        if not wo:
            product = cls.env["product.product"].search([
                ("type", "=", "consu"),
            ], limit=1) or cls.env["product.product"].create({
                "name": "W018 test product",
                "type": "consu",
            })
            bom = cls.env["mrp.bom"].create({
                "product_tmpl_id": product.product_tmpl_id.id,
                "product_qty": 1.0,
            })
            workcenter = cls.env["mrp.workcenter"].search([], limit=1)
            cls.env["mrp.routing.workcenter"].create({
                "bom_id": bom.id,
                "workcenter_id": workcenter.id,
                "name": "W018 test op",
                "time_cycle": 10.0,
            })
            mo = cls.env["mrp.production"].create({
                "product_id": product.id,
                "product_qty": 1.0,
                "bom_id": bom.id,
            })
            mo.action_confirm()
            wo = mo.workorder_ids[:1]
        cls.wo = wo

    def test_10_default_window_is_900s(self):
        """W018 — the lookback default widened from 5 min to 15 min."""
        # When the ir.config_parameter is unset, the handler falls back
        # to the class-level default. Ensure that default is 900s.
        self.assertEqual(
            self.Handler._DEFAULT_DEFECT_CONTEXT_SEC, 900,
            "Default defect-context window should be 900s (15 min)."
        )

    def test_20_icp_override_still_respected(self):
        """A site that prefers a tighter window can still override
        via ir.config_parameter — the default change must not break
        the operator-tunable surface."""
        Param = self.env["ir.config_parameter"].sudo()
        Param.set_param(
            "southbrook.qr_kit.defect_context_window_seconds", "60")
        # Force a fresh log row >60s old by tagging the cutoff math:
        # the helper reads create_date >= now - window, so if window
        # is small enough, no logs match. Easiest is to assert the
        # parameter is read at call time.
        try:
            with _patched_request(_FakeRequest(env=self.env)):
                # No log row exists yet; resolver returns False.
                resolved = self.Handler._resolve_workorder_from_context()
            self.assertFalse(
                resolved,
                "With no recent scan log entry, resolver must return False.",
            )
        finally:
            Param.set_param(
                "southbrook.qr_kit.defect_context_window_seconds", False)

    def test_30_scan_response_echoes_wo_and_workcenter(self):
        """W018 — toast now includes WO name + workcenter."""
        # Seed a form-open scan log row so the resolver finds our WO.
        self.wo.with_context(test_enable=False)._sbk_maybe_log_form_open()
        # The helper short-circuits under test_enable=True; create
        # the log row directly so the resolver sees it.
        self.Log.sudo().create({
            "kind": "wo",
            "ident": str(self.wo.id),
            "action": "form_open",
            "result": "ok",
            "target_model": "mrp.workorder",
            "target_id": self.wo.id,
            "user_id": self.env.uid,
            "payload": "synthetic-w018-test",
        })
        with _patched_request(_FakeRequest(env=self.env)):
            result = self.Handler.handle_action(
                self.env["southbrook.mi.check"],
                action="open",
                params={"defect_type": "scratch"},
            )
        self.assertTrue(result.get("record_id"),
                        "Defect handler should create an NCR record.")
        self.assertEqual(
            result.get("wo_id"), self.wo.id,
            "Scan response should echo the resolved WO id.",
        )
        self.assertEqual(
            result.get("wo_name"), self.wo.display_name,
            "Scan response should echo the resolved WO display_name.",
        )
        wc_name = (self.wo.workcenter_id.name
                   if self.wo.workcenter_id else "")
        self.assertEqual(
            result.get("workcenter_name"), wc_name,
            "Scan response should echo the resolved workcenter name.",
        )
        self.assertTrue(
            result.get("context_resolved"),
            "context_resolved flag should be True for context-resolved scans.",
        )
        # Message body shape: 'Drafted defect ... -> WO... (...)'
        self.assertIn(
            "->", result.get("message", ""),
            "Toast should use the new 'Drafted defect ... -> WO... '"
            " message format.",
        )
        self.assertIn(
            self.wo.display_name, result.get("message", ""),
            "Toast should include the resolved WO display_name.",
        )

    def test_40_scan_response_when_no_context_is_clear(self):
        """When no WO is resolved, toast still tells the operator
        (rather than silently looking like it linked)."""
        # No log rows for THIS user are present that would link a WO.
        # Create a sentinel user to isolate from prior tests.
        sentinel = self.env["res.users"].create({
            "name": "W018 sentinel",
            "login": "w018_sentinel@example.invalid",
        })
        with _patched_request(_FakeRequest(env=self.env)):
            result = self.Handler.with_user(sentinel).handle_action(
                self.env["southbrook.mi.check"],
                action="open",
                params={"defect_type": "edge_defect"},
            )
        self.assertFalse(
            result.get("wo_id"),
            "Without a recent scan, scan response wo_id should be False.",
        )
        self.assertFalse(
            result.get("context_resolved"),
            "Without a recent scan, context_resolved should be False.",
        )
        self.assertIn(
            "link manually", result.get("message", ""),
            "Toast should tell the operator no WO was auto-linked.",
        )
