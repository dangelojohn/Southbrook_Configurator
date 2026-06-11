# SPDX-License-Identifier: LGPL-3.0-only
"""Phase 4 Sprint 1 — Accucutt cut-list nesting bridge tests.

Two endpoints:
  GET  /api/v1/cutlist/<id>/envelope         — read cutlist for nesting
  POST /api/v1/cutlist/<id>/nesting-result   — push nesting outcome back

Both gated on X-Api-Key. The envelope is the same dict
sb.cutlist.to_nesting_envelope() returns; the nesting-result endpoint
forwards a JSON payload to sb.cutlist.from_nesting_result(), which
validates schema = southbrook.nesting.v1 and advances state to 'nested'.
"""
import json

from odoo.tests.common import HttpCase, tagged


SCHEMA = "southbrook.flutter.api.v1"
NESTING_SCHEMA = "southbrook.nesting.v1"


@tagged("post_install", "-at_install", "southbrook", "api", "cutlist_nesting")
class TestApiCutlistNesting(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Manufacturing-role user (api key needs full read on sb.cutlist).
        group_mfg = cls.env.ref(
            "mrp.group_mrp_user", raise_if_not_found=False)
        groups = [(6, 0, [group_mfg.id])] if group_mfg else False
        cls.partner = cls.env["res.partner"].create({
            "name": "Accucutt Test", "email": "accucutt.test@example.com",
        })
        user_vals = {
            "login": "accucutt.test@example.com",
            "password": "accucutt-strong-pw-123",
            "partner_id": cls.partner.id,
        }
        if groups:
            user_vals["group_ids"] = groups
        cls.user = cls.env["res.users"].create(user_vals)

        # Build a cutlist with one panel.
        product = cls.env["product.product"].create({
            "name": "Cutlist nesting test cabinet",
            "type": "consu", "is_storable": True,
        })
        cls.env["mrp.bom"].create({
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_qty": 1.0,
        })
        mo = cls.env["mrp.production"].create({
            "product_id": product.id, "product_qty": 1.0,
        })
        cls.cutlist = cls.env["sb.cutlist"].create({
            "mo_id": mo.id,
            "line_ids": [(0, 0, {
                "panel_name": "side_L",
                "qty": 2,
                "length_mm": 720.0,
                "width_mm": 580.0,
                "thickness_mm": 15.875,
                "substrate": "melamine_white_5_8",
                "grain_dir": "no_grain",
            })],
        })

    def _get_api_key(self):
        """Issue an API key for the test user via the login endpoint."""
        resp = self.url_open(
            "/api/v1/auth/login",
            data=json.dumps({
                "email": self.user.login,
                "password": "accucutt-strong-pw-123",
            }),
            headers={"Content-Type": "application/json"},
        )
        return resp.json()["api_key"]

    # ------------------------------------------------------------------
    # Envelope GET
    # ------------------------------------------------------------------
    def test_envelope_returns_nesting_schema_and_panels(self):
        key = self._get_api_key()
        resp = self.url_open(
            f"/api/v1/cutlist/{self.cutlist.id}/envelope",
            headers={"X-Api-Key": key},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        # Top-level body declares the nesting schema (not the flutter one).
        self.assertEqual(body["schema"], NESTING_SCHEMA)
        envelope = body["envelope"]
        self.assertEqual(envelope["schema"], NESTING_SCHEMA)
        self.assertEqual(envelope["cutlist_id"], self.cutlist.id)
        self.assertEqual(len(envelope["panels"]), 1)
        self.assertEqual(envelope["panels"][0]["panel_name"], "side_L")
        self.assertEqual(envelope["panels"][0]["qty"], 2)
        self.assertEqual(envelope["panels"][0]["length_mm"], 720.0)

    def test_envelope_without_api_key_returns_401(self):
        resp = self.url_open(
            f"/api/v1/cutlist/{self.cutlist.id}/envelope",
        )
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["error"], "invalid_api_key")

    def test_envelope_unknown_id_returns_404(self):
        key = self._get_api_key()
        resp = self.url_open(
            "/api/v1/cutlist/999999999/envelope",
            headers={"X-Api-Key": key},
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["error"], "not_found")

    # ------------------------------------------------------------------
    # Nesting-result POST
    # ------------------------------------------------------------------
    def test_nesting_result_advances_state_to_nested(self):
        key = self._get_api_key()
        payload = {
            "schema": NESTING_SCHEMA,
            "sheets_used": 1,
            "yield_pct": 91.4,
            "waste_pct": 8.6,
        }
        resp = self.url_open(
            f"/api/v1/cutlist/{self.cutlist.id}/nesting-result",
            data=json.dumps(payload),
            headers={
                "X-Api-Key": key,
                "Content-Type": "application/json",
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["state"], "nested")
        self.cutlist.invalidate_recordset()
        self.assertEqual(self.cutlist.state, "nested")
        stash = json.loads(self.cutlist.nesting_result_json)
        self.assertEqual(stash["yield_pct"], 91.4)

    def test_nesting_result_bad_schema_returns_422(self):
        key = self._get_api_key()
        payload = {"schema": "something.else", "yield_pct": 0}
        resp = self.url_open(
            f"/api/v1/cutlist/{self.cutlist.id}/nesting-result",
            data=json.dumps(payload),
            headers={
                "X-Api-Key": key,
                "Content-Type": "application/json",
            },
        )
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json()["error"], "nesting_rejected")

    def test_nesting_result_bad_json_returns_400(self):
        key = self._get_api_key()
        resp = self.url_open(
            f"/api/v1/cutlist/{self.cutlist.id}/nesting-result",
            data="not json at all",
            headers={
                "X-Api-Key": key,
                "Content-Type": "application/json",
            },
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"], "bad_json")

    def test_nesting_result_without_api_key_returns_401(self):
        resp = self.url_open(
            f"/api/v1/cutlist/{self.cutlist.id}/nesting-result",
            data=json.dumps({"schema": NESTING_SCHEMA}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(resp.status_code, 401)
