# SPDX-License-Identifier: LGPL-3.0-only
"""API auth tests — key issuance, header verification, error envelope."""
import json

from odoo.tests.common import HttpCase, tagged


SCHEMA = "southbrook.flutter.api.v1"


@tagged("post_install", "-at_install", "southbrook", "api", "auth")
class TestApiAuth(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        portal_group = cls.env.ref("base.group_portal")
        cls.partner = cls.env["res.partner"].create({
            "name": "API Test", "email": "api.test@example.com",
        })
        cls.user = cls.env["res.users"].create({
            "login": "api.test@example.com",
            "password": "api-strong-pw-123",
            "partner_id": cls.partner.id,
            "group_ids": [(6, 0, [portal_group.id])],
        })

    # ------------------------------------------------------------------
    # /auth/login
    # ------------------------------------------------------------------
    def test_login_returns_api_key_and_schema(self):
        resp = self.url_open(
            "/api/v1/auth/login",
            data=json.dumps({"email": "api.test@example.com",
                              "password": "api-strong-pw-123"}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["schema"], SCHEMA)
        self.assertIn("api_key", body)
        self.assertEqual(len(body["api_key"]), 64,
                          "256-bit hex string is 64 chars")
        self.assertEqual(body["user"]["email"], "api.test@example.com")

    def test_login_wrong_password_returns_401(self):
        resp = self.url_open(
            "/api/v1/auth/login",
            data=json.dumps({"email": "api.test@example.com",
                              "password": "wrong-password"}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(resp.status_code, 401)
        body = resp.json()
        self.assertEqual(body["schema"], SCHEMA)
        self.assertEqual(body["error"], "invalid_credentials")

    def test_login_unknown_email_returns_401(self):
        resp = self.url_open(
            "/api/v1/auth/login",
            data=json.dumps({"email": "ghost@example.com",
                              "password": "anything"}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["error"], "invalid_credentials")

    def test_login_missing_credentials_400(self):
        resp = self.url_open(
            "/api/v1/auth/login",
            data=json.dumps({"email": "x@y"}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_login_bad_json_400(self):
        resp = self.url_open(
            "/api/v1/auth/login",
            data="not-json-at-all",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"], "bad_json")

    # ------------------------------------------------------------------
    # /me (key verification)
    # ------------------------------------------------------------------
    def _get_api_key(self):
        resp = self.url_open(
            "/api/v1/auth/login",
            data=json.dumps({"email": "api.test@example.com",
                              "password": "api-strong-pw-123"}),
            headers={"Content-Type": "application/json"},
        )
        return resp.json()["api_key"]

    def test_me_with_valid_key(self):
        key = self._get_api_key()
        resp = self.url_open(
            "/api/v1/me",
            headers={"X-Api-Key": key},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["schema"], SCHEMA)
        self.assertEqual(body["user"]["email"], "api.test@example.com")
        self.assertFalse(body["user"]["is_dealer"])

    def test_me_without_key_returns_401(self):
        resp = self.url_open("/api/v1/me")
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["error"], "invalid_api_key")

    def test_me_with_wrong_key_returns_401(self):
        resp = self.url_open(
            "/api/v1/me",
            headers={"X-Api-Key": "deadbeef" * 8},
        )
        self.assertEqual(resp.status_code, 401)
