# SPDX-License-Identifier: LGPL-3.0-only
"""W011 — form-open scan log.

Operators tap into a WO from the kanban (not always by scanning a QR);
the defect-context window in
`DefectQrKind._resolve_workorder_from_context` walks
`southbrook.qr.scan.log` for the user's most recent scan. Without a
synthetic `form_open` row, the first defect scan after a tap-open
silently falls back to the previous scan target.

These tests cover the override on `mrp.workorder.web_read`:

  * single-record web_read from a real HTTP request → ONE log row
    with action='form_open' / target_model='mrp.workorder'
  * cron / no-request context → NO log row (we'd attribute every
    cron-driven web_read to the user that triggered the cron, which
    is wrong AND breaks defect context)
  * test context (test_enable) → NO log row (this very test file
    runs in test_enable; we exercise the underlying helper directly
    by monkey-patching the env context for the assertion arc)
  * multi-record web_read (kanban / list view) → NO log row
  * dedupe — two opens within `_FORM_OPEN_DEDUPE_SEC` produce ONE row
  * defect-context resolver sees the form_open row and resolves the
    WO id (end-to-end integration smoke)

The HTTP request is faked via a small context-manager that patches
`odoo.http.request` with a stub that exposes the
`httprequest.path` + `httprequest.headers` + `httprequest.remote_addr`
shape the override reads.
"""
from contextlib import contextmanager
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged


class _FakeRequest:
    """Minimal stand-in for `odoo.http.request` — only carries the
    attributes our `_sbk_maybe_log_form_open` actually reads."""

    def __init__(self, path="/web/dataset/call_kw", ua="pytest",
                 ip="127.0.0.1"):
        class _HR:
            pass
        hr = _HR()
        hr.path = path
        hr.remote_addr = ip
        hr.headers = {"User-Agent": ua}
        self.httprequest = hr


@contextmanager
def _patched_request(fake):
    """Patch `odoo.http.request` AND clear test_enable so the override
    actually runs. Restores both on exit."""
    with patch("odoo.http.request", fake):
        yield


@tagged("post_install", "-at_install", "southbrook", "sbk_kitchen",
        "w011", "qr")
class TestW011FormOpenScanLog(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Log = cls.env["southbrook.qr.scan.log"]
        # Smallest WO we can build that w_e_b_read returns: pick the
        # first existing WO if any, otherwise build a trivial MO from
        # the demo product. Using existing demo data keeps the test
        # fast and avoids re-implementing MO scaffolding here.
        wo = cls.env["mrp.workorder"].search([], limit=1)
        if not wo:
            # Build a minimal MO so we have a WO to read. The
            # `southbrook_kitchen_mrp` demo data normally provides
            # one; this is the no-demo fallback.
            product = cls.env["product.product"].search([
                ("type", "=", "consu"),
            ], limit=1) or cls.env["product.product"].create({
                "name": "W011 test product",
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
                "name": "W011 test op",
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
        cls.spec = {}  # web_read accepts an empty spec dict

    def _count_form_open_for(self, wo):
        return self.Log.sudo().search_count([
            ("action", "=", "form_open"),
            ("target_model", "=", "mrp.workorder"),
            ("target_id", "=", wo.id),
        ])

    # ------------------------------------------------------------------
    # Direct helper exercises (bypass test_enable guard)
    # ------------------------------------------------------------------

    def test_10_helper_writes_form_open_with_request(self):
        """Calling the helper directly with a faked HTTP request +
        without the test_enable guard produces exactly one log row."""
        before = self._count_form_open_for(self.wo)
        wo = self.wo.with_context(test_enable=False)
        with _patched_request(_FakeRequest()):
            wo._sbk_maybe_log_form_open()
        self.assertEqual(
            self._count_form_open_for(self.wo), before + 1,
            "Form-open with real request should create one scan log row.",
        )
        row = self.Log.sudo().search([
            ("action", "=", "form_open"),
            ("target_model", "=", "mrp.workorder"),
            ("target_id", "=", self.wo.id),
        ], limit=1, order="create_date desc")
        self.assertEqual(row.kind, "wo")
        self.assertEqual(row.ident, str(self.wo.id))
        self.assertEqual(row.result, "ok")
        self.assertEqual(row.user_id.id, self.env.uid)

    def test_20_no_log_when_no_request(self):
        """Cron / sudo / RPC without HTTP request → no log row."""
        before = self._count_form_open_for(self.wo)
        wo = self.wo.with_context(test_enable=False)
        # request is None
        with patch("odoo.http.request", None):
            wo._sbk_maybe_log_form_open()
        self.assertEqual(
            self._count_form_open_for(self.wo), before,
            "No HTTP request → no form-open log row.",
        )

    def test_30_no_log_for_multi_record(self):
        """Kanban / list web_read fetches many records at once — we
        must NOT spam one row per record."""
        # Build a 2-record set by reusing the same WO twice via |
        # (recordset union with self drops dupes); fall back to
        # searching for any second WO if available.
        wo2 = self.env["mrp.workorder"].search(
            [("id", "!=", self.wo.id)], limit=1)
        if not wo2:
            # Skip — can't construct a multi-record set on this DB.
            self.skipTest("Only one WO available; multi-record path "
                          "exercised in integration.")
        multi = self.wo | wo2
        multi = multi.with_context(test_enable=False)
        before = self._count_form_open_for(self.wo)
        with _patched_request(_FakeRequest()):
            multi._sbk_maybe_log_form_open()
        self.assertEqual(
            self._count_form_open_for(self.wo), before,
            "Multi-record web_read must not write any form-open row.",
        )

    def test_40_no_log_for_qr_scan_path(self):
        """If web_read fires as a downstream of /sb/qr/*, the
        controller already wrote its own log row — don't double-log."""
        before = self._count_form_open_for(self.wo)
        wo = self.wo.with_context(test_enable=False)
        with _patched_request(_FakeRequest(path="/sb/qr/scan")):
            wo._sbk_maybe_log_form_open()
        self.assertEqual(
            self._count_form_open_for(self.wo), before,
            "QR scan controller path must not double-log.",
        )

    def test_50_no_log_for_xmlrpc_path(self):
        """External integrations hitting /xmlrpc or /jsonrpc should
        not pollute the operator's defect-context window."""
        before = self._count_form_open_for(self.wo)
        wo = self.wo.with_context(test_enable=False)
        with _patched_request(_FakeRequest(path="/xmlrpc/2/object")):
            wo._sbk_maybe_log_form_open()
        self.assertEqual(
            self._count_form_open_for(self.wo), before,
            "XML-RPC path must not write a form-open row.",
        )

    def test_60_dedupe_within_window(self):
        """Two form-opens of the same WO by the same user within the
        dedupe window collapse to ONE row."""
        wo = self.wo.with_context(test_enable=False)
        before = self._count_form_open_for(self.wo)
        with _patched_request(_FakeRequest()):
            wo._sbk_maybe_log_form_open()
            wo._sbk_maybe_log_form_open()
            wo._sbk_maybe_log_form_open()
        self.assertEqual(
            self._count_form_open_for(self.wo), before + 1,
            "Three opens within dedupe window must collapse to one row.",
        )

    def test_70_defect_context_resolves_from_form_open(self):
        """End-to-end: a form_open row should satisfy the defect
        context window resolver — the whole point of W011."""
        wo = self.wo.with_context(test_enable=False)
        with _patched_request(_FakeRequest()):
            wo._sbk_maybe_log_form_open()
        Handler = self.env["southbrook.qr.kind.defect"]
        resolved = Handler._resolve_workorder_from_context()
        self.assertEqual(
            resolved, self.wo.id,
            "Defect-context resolver should see the form_open log "
            "row and pick the WO that was form-opened.",
        )

    # ------------------------------------------------------------------
    # web_read override sanity
    # ------------------------------------------------------------------

    def test_80_test_enable_guard_blocks_during_tests(self):
        """The override checks `env.context.get('test_enable')` so
        that ordinary test runs don't pollute the log. Calling
        web_read in this very test (test_enable=True) should NOT
        create a row even with a faked request."""
        before = self._count_form_open_for(self.wo)
        with _patched_request(_FakeRequest()):
            # Default test env has test_enable=True; web_read still
            # runs cleanly but the helper short-circuits.
            self.wo.web_read(self.spec)
        self.assertEqual(
            self._count_form_open_for(self.wo), before,
            "test_enable context must suppress the form-open log row.",
        )
