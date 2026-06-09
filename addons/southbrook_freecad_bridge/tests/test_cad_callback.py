# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for /plm/cad_callback HTTP controller.

Covers the auth contract (secret unset → 503, missing → 401, mismatch →
401), validation (malformed body → 400, unknown MO → 404), and the
happy-path side effects (x_cad_status flips, x_cad_attachment_ids gets
populated).

Run directly with --test-tags=cad_callback. Counts toward `southbrook`
tag aggregate.
"""
import json

from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install", "southbrook", "cad_callback")
class TestCadCallback(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.url = "/plm/cad_callback"
        cls.secret = "test-secret-do-not-use-in-prod"
        cls.env["ir.config_parameter"].sudo().set_param(
            "freecad_bridge.secret", cls.secret
        )

        # Minimal MO. We need a product + BoM so mrp.production.create works.
        product = cls.env["product.product"].create({
            "name": "G1 test cabinet",
            "type": "consu",
            "is_storable": True,
        })
        cls.env["mrp.bom"].create({
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_qty": 1.0,
        })
        cls.mo = cls.env["mrp.production"].create({
            "product_id": product.id,
            "product_qty": 1.0,
        })

    def _post(self, body, secret=None):
        headers = {"Content-Type": "application/json"}
        if secret is not None:
            headers["X-Bridge-Secret"] = secret
        return self.url_open(
            self.url,
            data=json.dumps(body),
            headers=headers,
        )

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------
    def test_missing_secret_header_returns_403(self):
        """No X-Bridge-Secret → AccessError → controller returns 403."""
        r = self._post(
            {"production_id": self.mo.id, "status": "done", "attachment_ids": []},
            secret="",
        )
        self.assertIn(r.status_code, (401, 403))  # Odoo renders AccessError as 403

    def test_wrong_secret_returns_403(self):
        r = self._post(
            {"production_id": self.mo.id, "status": "done", "attachment_ids": []},
            secret="wrong",
        )
        self.assertIn(r.status_code, (401, 403))

    def test_secret_unset_returns_503(self):
        """Unset the config param then post — controller short-circuits 503."""
        self.env["ir.config_parameter"].sudo().set_param("freecad_bridge.secret", "")
        try:
            r = self._post(
                {"production_id": self.mo.id, "status": "done", "attachment_ids": []},
                secret=self.secret,
            )
            self.assertEqual(r.status_code, 503)
            self.assertEqual(r.json().get("error"), "bridge_secret_unset")
        finally:
            self.env["ir.config_parameter"].sudo().set_param(
                "freecad_bridge.secret", self.secret
            )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def test_unknown_production_returns_404(self):
        r = self._post(
            {"production_id": 9999999, "status": "done", "attachment_ids": []},
            secret=self.secret,
        )
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json().get("error"), "unknown_production")

    def test_invalid_status_returns_400(self):
        r = self._post(
            {"production_id": self.mo.id, "status": "weird", "attachment_ids": []},
            secret=self.secret,
        )
        self.assertEqual(r.status_code, 400)

    def test_missing_production_id_returns_400(self):
        r = self._post(
            {"status": "done", "attachment_ids": []},
            secret=self.secret,
        )
        self.assertEqual(r.status_code, 400)

    # ------------------------------------------------------------------
    # Happy path — state flips, attachments link
    # ------------------------------------------------------------------
    def test_callback_done_links_attachments_and_flips_status(self):
        att1 = self.env["ir.attachment"].create({
            "name": "test_dxf_panel_side_L.dxf",
            "res_model": "mrp.production",
            "res_id": self.mo.id,
        })
        att2 = self.env["ir.attachment"].create({
            "name": "test_shopdrw.svg",
            "res_model": "mrp.production",
            "res_id": self.mo.id,
        })
        # Initial state.
        self.assertEqual(self.mo.x_cad_status, "pending")
        self.assertFalse(self.mo.x_cad_attachment_ids)

        r = self._post(
            {
                "production_id": self.mo.id,
                "status": "done",
                "attachment_ids": [att1.id, att2.id],
            },
            secret=self.secret,
        )
        self.assertEqual(r.status_code, 200, r.text)
        payload = r.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "done")

        self.mo.invalidate_recordset(["x_cad_status", "x_cad_attachment_ids"])
        self.assertEqual(self.mo.x_cad_status, "done")
        self.assertEqual(
            set(self.mo.x_cad_attachment_ids.ids),
            {att1.id, att2.id},
        )

    def test_callback_error_status_flips_and_no_attachments(self):
        r = self._post(
            {"production_id": self.mo.id, "status": "error", "attachment_ids": []},
            secret=self.secret,
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.mo.invalidate_recordset(["x_cad_status"])
        self.assertEqual(self.mo.x_cad_status, "error")
