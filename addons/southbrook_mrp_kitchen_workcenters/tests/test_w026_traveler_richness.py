# SPDX-License-Identifier: LGPL-3.0-only
"""W026 — Rich WO traveler PDF (MFG-REVIEW R2.5 + R8.2).

Coverage:
  * the 3 action QR payloads (start / pause / done) are DISTINCT —
    they encode different scan URLs so the wo handler routes each to
    the right state transition
  * the action URLs carry the right ?action= query param (start,
    pause, finish — UI-label `done` maps to handler `finish`)
  * the CAD thumbnail compute falls back to product.image_1920 when
    no FreeCAD bridge render is attached to the MO
  * the QWeb report renders for a WO without raising — proves the
    template parses, the new fields resolve in the WO render env, and
    the 3 action QR <img> tags render (or fall back to the "QR
    unavailable" placeholder if qrcode lib is missing)

We don't try to assert PDF byte output (wkhtmltopdf isn't always
present in the test container); instead we render through the
`_render_qweb_html` path which is what the binding uses up to
PDF-bake time.
"""
import base64

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_kitchen", "w026")
class TestW026TravelerRichness(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Workcenter = cls.env["mrp.workcenter"]
        cls.Workorder = cls.env["mrp.workorder"]
        cls.Production = cls.env["mrp.production"]
        cls.Bom = cls.env["mrp.bom"]
        cls.RoutingWC = cls.env["mrp.routing.workcenter"]
        cls.Product = cls.env["product.product"]

        # Pin a base URL so the action URL compute returns non-empty
        # strings — without this the URL builder returns "" and the
        # QR-distinctness assertions become noise.
        cls.env["ir.config_parameter"].sudo().set_param(
            "web.base.url", "https://w026-test.example",
        )

        wc = cls.Workcenter.search([("active", "=", True)], limit=1)
        if not wc:
            wc = cls.Workcenter.create({"name": "W026 test WC"})
        cls.workcenter = wc

    def _build_minimal_wo(self, with_product_image=False):
        """Build the smallest MO that produces a single WO. Returns
        (wo, product). If with_product_image=True, plants a 1x1 PNG
        on product.image_1920 so the CAD-thumbnail-fallback test has
        something to fall back TO."""
        # 1x1 transparent PNG — smallest valid PNG that exercises the
        # binary path without dragging in pillow gymnastics.
        png_1x1 = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
            "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        product_vals = {
            "name": "W026 cabinet",
            "type": "consu",
            "is_storable": True,
        }
        if with_product_image:
            product_vals["image_1920"] = base64.b64encode(png_1x1)
        product = self.Product.create(product_vals)
        bom = self.Bom.create({
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_qty": 1.0,
        })
        self.RoutingWC.create({
            "bom_id": bom.id,
            "workcenter_id": self.workcenter.id,
            "name": "W026 op",
        })
        mo = self.Production.create({
            "product_id": product.id,
            "product_qty": 1.0,
            "bom_id": bom.id,
        })
        # v19: onchange dispatches implicitly on field write; the legacy
        # `_onchange_move_raw()` internal method was removed in v19, and
        # `action_confirm()` below explodes the BOM into raw moves anyway.
        mo.action_confirm()
        wo = mo.workorder_ids[:1]
        self.assertTrue(wo, "Expected MO confirm to spawn a workorder")
        return wo, product

    # ------------------------------------------------------------------
    # 1. The 3 action QR payloads are distinct
    # ------------------------------------------------------------------
    def test_qr_action_urls_are_distinct(self):
        wo, _ = self._build_minimal_wo()
        url_start = wo.qr_action_start_url
        url_pause = wo.qr_action_pause_url
        url_done = wo.qr_action_done_url
        # All three non-empty (we pinned web.base.url in setUpClass)
        self.assertTrue(url_start, "start URL should be non-empty")
        self.assertTrue(url_pause, "pause URL should be non-empty")
        self.assertTrue(url_done, "done URL should be non-empty")
        # Distinct from each other
        self.assertNotEqual(url_start, url_pause)
        self.assertNotEqual(url_pause, url_done)
        self.assertNotEqual(url_start, url_done)

    def test_qr_action_urls_carry_handler_actions(self):
        """URL ?action= query MUST match what the wo handler accepts:
        action=start, action=pause, action=finish. The UI label
        'done' is mapped to handler action 'finish' inside the
        builder — this is the contract test for that mapping."""
        wo, _ = self._build_minimal_wo()
        self.assertIn("action=start", wo.qr_action_start_url)
        self.assertIn("action=pause", wo.qr_action_pause_url)
        self.assertIn(
            "action=finish", wo.qr_action_done_url,
            "UI 'done' must map to handler 'finish' so button_finish fires",
        )

    # ------------------------------------------------------------------
    # 2. The 3 action QR images (when qrcode is installed) are distinct
    # ------------------------------------------------------------------
    def test_qr_action_images_distinct_when_qrcode_present(self):
        try:
            import qrcode  # noqa: F401
        except ImportError:
            self.skipTest("qrcode lib not installed in test env")
        wo, _ = self._build_minimal_wo()
        b64_start = wo.qr_action_start_b64
        b64_pause = wo.qr_action_pause_b64
        b64_done = wo.qr_action_done_b64
        # All three non-empty (URLs were non-empty, qrcode is installed)
        self.assertTrue(b64_start)
        self.assertTrue(b64_pause)
        self.assertTrue(b64_done)
        # Different inputs => different PNGs (no shared library cache)
        self.assertNotEqual(b64_start, b64_pause)
        self.assertNotEqual(b64_pause, b64_done)
        self.assertNotEqual(b64_start, b64_done)

    # ------------------------------------------------------------------
    # 3. CAD thumbnail falls back to product image when no render
    # ------------------------------------------------------------------
    def test_cad_thumbnail_falls_back_to_product_image(self):
        """When the MO has no FreeCAD bridge attachments (vanilla
        case — bridge installed but never invoked, or bridge not
        installed at all), cad_thumbnail must surface the product
        image so the traveler still carries SOMETHING visual."""
        wo, product = self._build_minimal_wo(with_product_image=True)
        self.assertTrue(product.image_1920, "Product image plant failed")
        thumb = wo.cad_thumbnail
        self.assertTrue(thumb, "Expected fallback to product.image_1920")
        # Sanity — same bytes (Odoo may re-encode but image_1920 is
        # returned as base64 bytes from compute, no resize at this layer)
        self.assertEqual(thumb, product.image_1920)

    def test_cad_thumbnail_empty_when_no_source(self):
        """No FreeCAD render AND no product image => no thumbnail.
        The QWeb template wraps the <img> in t-if so this is a
        graceful blank, not a broken image."""
        wo, _ = self._build_minimal_wo(with_product_image=False)
        self.assertFalse(
            wo.cad_thumbnail,
            "Expected blank thumbnail when neither bridge nor product image",
        )

    # ------------------------------------------------------------------
    # 4. Template renders end-to-end without raising
    # ------------------------------------------------------------------
    def test_traveler_renders_html_for_wo(self):
        """End-to-end render of the QWeb template — proves all the
        new fields resolve from the render env, the t-if guards
        work, and the 3 action QR sections actually emit markup."""
        wo, _ = self._build_minimal_wo(with_product_image=True)
        Report = self.env["ir.actions.report"]
        report = Report._get_report(
            "southbrook_mrp_kitchen_workcenters.wo_traveler_document"
        )
        self.assertTrue(report, "Traveler report record not found")
        html, _content_type = self.env[
            "ir.actions.report"
        ]._render_qweb_html(
            "southbrook_mrp_kitchen_workcenters.wo_traveler_document",
            wo.ids,
        )
        body = html.decode("utf-8") if isinstance(html, bytes) else html
        # The 3 action labels appear
        self.assertIn("START", body)
        self.assertIn("PAUSE", body)
        self.assertIn("DONE", body)
        # The CAD-thumbnail web/image route is referenced
        self.assertIn(
            f"/web/image/mrp.workorder/{wo.id}/cad_thumbnail",
            body,
            "Expected the CAD thumbnail web/image route to render",
        )

    def test_traveler_contains_three_qr_blocks(self):
        """Either qrcode is present (3 data:image/png QRs) OR it's
        absent (3 'QR unavailable' placeholders). Both modes ship 3
        blocks, never zero, never one — that's the whole point of
        the W026 surface (3 actions, 3 entry points)."""
        wo, _ = self._build_minimal_wo()
        html, _ct = self.env["ir.actions.report"]._render_qweb_html(
            "southbrook_mrp_kitchen_workcenters.wo_traveler_document",
            wo.ids,
        )
        body = html.decode("utf-8") if isinstance(html, bytes) else html
        try:
            import qrcode  # noqa: F401
            qr_count = body.count("data:image/png;base64,")
            # Should be at least 3 (single SCAN-TO-OPEN + 3 action QRs
            # = 4 total when qrcode is installed; we allow either since
            # the single open-QR is from the mixin and may not always
            # render in this test env).
            self.assertGreaterEqual(
                qr_count, 3,
                "Expected at least 3 base64 PNG QRs (start/pause/done)",
            )
        except ImportError:
            self.assertEqual(
                body.count("QR unavailable"), 3,
                "Without qrcode, expect 3 'QR unavailable' placeholders",
            )
