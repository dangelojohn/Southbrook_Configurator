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
    # /health — no auth, fast, safe for monitors
    # ------------------------------------------------------------------
    def test_health_no_auth_returns_ok_with_schema(self):
        resp = self.url_open("/api/v1/health")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["schema"], SCHEMA)
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["service"], "southbrook_api")
        self.assertEqual(body["api_version"], "v1")
        self.assertEqual(body["schema_version"], SCHEMA)
        # The DB name is deliberately NOT exposed to unauthenticated callers
        # (info-disclosure hardening — see REVIEW_REPORT F9).
        self.assertNotIn("db", body)

    # ------------------------------------------------------------------
    # F1 — API-key model may not be forged / hijacked by a regular user
    # ------------------------------------------------------------------
    def test_regular_user_cannot_forge_api_key(self):
        """A base.group_user employee must not be able to create a
        southbrook.api.key row — forging one pointing at an admin user_id
        would let them authenticate as admin over /api/v1/*."""
        from odoo.exceptions import AccessError
        emp = self.env["res.users"].create({
            "name": "API Emp F1", "login": "api_emp_f1",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        with self.assertRaises(AccessError):
            self.env["southbrook.api.key"].with_user(emp).create({
                "user_id": self.env.ref("base.user_admin").id,
                "key_hash": "sha256:forged",
            })

    def test_user_cannot_revoke_another_users_key(self):
        """action_revoke (+ the own-keys record rule) must stop a user from
        revoking someone else's key (fleet-wide DoS otherwise)."""
        from odoo.exceptions import AccessError
        Key = self.env["southbrook.api.key"].sudo()
        victim = self.env["res.users"].create({
            "name": "Victim F1", "login": "api_victim_f1",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        attacker = self.env["res.users"].create({
            "name": "Attacker F1", "login": "api_attacker_f1",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        victim_key = Key.create({
            "user_id": victim.id, "key_hash": "sha256:victimkey_f1",
        })
        with self.assertRaises(AccessError):
            victim_key.with_user(attacker).action_revoke()
        self.assertFalse(victim_key.revoked_at)

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
