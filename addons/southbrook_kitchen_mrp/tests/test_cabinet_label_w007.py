# SPDX-License-Identifier: LGPL-3.0-only
"""W007 — engineering revision code on cabinet label + QR payload.

MFG-REVIEW-R9 W007 / R4 W2: the cabinet label and its QR payload must
carry ``mrp.production.pg_revision_code`` (when stamped) so installers
at site can verify match-to-spec without phoning the office.

These tests cover the two states that matter:

1. ``pg_revision_code`` IS set on the MO — the label HTML renders the
   ``Rev: <code>`` row AND the QR URL carries ``?rev=<code>``.
2. ``pg_revision_code`` is NULL/empty (pre-PG-112 MOs, or databases
   without the ``product_graph_release`` addon installed) — the label
   still renders without crashing; the rev row is omitted; the QR URL
   has no rev query param. Backward-compat guarantee.

Note: ``pg_revision_code`` is a field added by the sibling addon
``product_graph_release`` (see CLAUDE.md Decision 1 / R1). In a test
DB where that addon is not installed the field literally does not
exist on the model. We skip the "rev present" assertion in that case
and exercise only the NULL-path test — which is the more important
one for protecting against regressions in the unstamped path.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "kitchen_mrp",
        "cabinet_label", "w007")
class TestCabinetLabelW007(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Product = cls.env["product.product"]
        cls.Production = cls.env["mrp.production"]

    def _new_mo(self):
        product = self.Product.create({
            "name": "W007 test cabinet",
            "type": "consu",
            "is_storable": True,
        })
        self.env["mrp.bom"].create({
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_qty": 1.0,
        })
        return self.Production.create({
            "product_id": product.id,
            "product_qty": 1.0,
        })

    # ------------------------------------------------------------------
    # NULL-path — MO without pg_revision_code stamp (or DB without
    # product_graph_release installed). Must render cleanly with no rev.
    # ------------------------------------------------------------------
    def test_label_renders_without_rev_when_unstamped(self):
        mo = self._new_mo()

        # Force-clear the rev if the field exists (handles both:
        # product_graph_release installed but no release linked to
        # this MO's bom, AND addon not installed at all).
        if "pg_revision_code" in mo._fields:
            # Field is computed/related — value is already empty for a
            # bom with no pg.release. Just assert it's falsy.
            self.assertFalse(
                mo.pg_revision_code,
                "Fresh MO with no pg.release link should have empty "
                "pg_revision_code",
            )

        # QR URL must NOT contain ?rev= when no rev stamped.
        self.assertNotIn(
            "?rev=", mo.sbk_label_qr_url or "",
            "QR URL must omit ?rev= when pg_revision_code is empty",
        )

        # Report must render without crashing. We render the QWeb
        # template directly (avoiding wkhtmltopdf in the test
        # environment) and assert the rev row is absent.
        IrActionsReport = self.env["ir.actions.report"]
        report = self.env.ref(
            "southbrook_kitchen_mrp.action_report_cabinet_label",
        )
        html_bytes, _content_type = IrActionsReport._render_qweb_html(
            report.id, mo.ids,
        )
        html = html_bytes.decode("utf-8") if isinstance(html_bytes, bytes) else html_bytes
        # The Rev ROW element must NOT be present. Assert on the opening tag
        # (`<tr class="sbk-rev-row"`), NOT the bare class name — the CSS
        # `.sbk-rev-row { ... }` selector in the <style> block always contains
        # "sbk-rev-row", so the old assertNotIn("sbk-rev-row") matched the
        # stylesheet, not the row. (Before the report's hasattr→`in o._fields`
        # fix this test ERRORed on the QWeb render and never got here.)
        self.assertNotIn(
            '<tr class="sbk-rev-row"', html,
            "Rev row must be omitted when pg_revision_code is empty",
        )
        # Sanity — the label still rendered the cabinet code section.
        self.assertIn("sbk-label", html, "Label container must render")

    # ------------------------------------------------------------------
    # Stamped path — when pg_revision_code is set, rev must appear in
    # both the label HTML and the QR URL.
    # ------------------------------------------------------------------
    def test_label_renders_rev_when_stamped(self):
        mo = self._new_mo()
        if "pg_revision_code" not in mo._fields:
            self.skipTest(
                "product_graph_release not installed on this test DB — "
                "stamped-path assertions cannot be exercised. The "
                "unstamped-path test above covers the backward-compat "
                "contract that matters for this DB shape.",
            )

        # pg_revision_code is a related (store=True, readonly=True)
        # field on a m2o chain — we can't write it directly. The simplest
        # way to drive the stamped path is to monkey-patch the related
        # value at the cache layer via a write to the underlying record,
        # OR use the lower-level invalidate + a temporary override of
        # the field's getter for this test. Avoid both — instead, we
        # call the compute helper directly with a forced value via a
        # context flag the compute doesn't honour, so we patch the
        # cache. The most surgical path: set the cache directly.
        rev_code = "A.3"
        mo.invalidate_recordset(["pg_revision_code"])
        # Set the value in the env cache. This is a test-only escape
        # hatch — production code never does this.
        self.env.cache.set(mo, mo._fields["pg_revision_code"], rev_code)

        # Force QR recompute (it's store=False so reading triggers it).
        mo.invalidate_recordset(["sbk_label_qr_url", "sbk_label_qr_image"])
        url = mo.sbk_label_qr_url
        self.assertIn(
            "?rev=A.3", url,
            f"QR URL must carry the rev as a query param. Got: {url}",
        )

        # Render the QWeb HTML and assert the rev row is present.
        IrActionsReport = self.env["ir.actions.report"]
        report = self.env.ref(
            "southbrook_kitchen_mrp.action_report_cabinet_label",
        )
        html_bytes, _content_type = IrActionsReport._render_qweb_html(
            report.id, mo.ids,
        )
        html = html_bytes.decode("utf-8") if isinstance(html_bytes, bytes) else html_bytes
        self.assertIn(
            "sbk-rev-row", html,
            "Rev row must render when pg_revision_code is set",
        )
        self.assertIn(
            "Rev:", html,
            "Rev label text must render when pg_revision_code is set",
        )
        self.assertIn(
            rev_code, html,
            f"Rev code {rev_code!r} must appear in the rendered label",
        )

    # ------------------------------------------------------------------
    # QR URL — special chars in rev code are URL-encoded.
    # ------------------------------------------------------------------
    def test_qr_url_quotes_rev_with_special_chars(self):
        mo = self._new_mo()
        if "pg_revision_code" not in mo._fields:
            self.skipTest("product_graph_release not installed")
        # A rev like "A/3" (PG style is dotted but defensive coverage
        # against future schemes that may include /, &, ?, =) must be
        # percent-encoded so the URL parses cleanly.
        rev_code = "A/3&x=1"
        mo.invalidate_recordset(["pg_revision_code"])
        self.env.cache.set(mo, mo._fields["pg_revision_code"], rev_code)
        mo.invalidate_recordset(["sbk_label_qr_url", "sbk_label_qr_image"])
        url = mo.sbk_label_qr_url
        # The rev param value must be percent-encoded — no raw / or &
        # leaking after the ?rev= sentinel.
        self.assertIn("?rev=A%2F3%26x%3D1", url, f"Got: {url}")
