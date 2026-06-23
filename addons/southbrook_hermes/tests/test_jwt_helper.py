# addons/southbrook_hermes/tests/test_jwt_helper.py
import time

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "hermes")
class TestJwtHelper(TransactionCase):
    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_param(
            "southbrook_hermes.jwt_secret", "test_secret_long_enough_for_hs256")
        from odoo.addons.southbrook_hermes.utils import jwt_helper
        self.helper = jwt_helper

    def test_mint_and_verify_roundtrip(self):
        token = self.helper.mint_jwt(
            self.env, tenant="southbrook", persona="trade_partner",
            partner_id=42, tier="T0+T1", extra={"order_id": 235})
        claims = self.helper.verify_jwt(self.env, token)
        self.assertEqual(claims["tenant"], "southbrook")
        self.assertEqual(claims["persona"], "trade_partner")
        self.assertEqual(claims["partner_id"], 42)
        self.assertEqual(claims["tier"], "T0+T1")
        self.assertEqual(claims["order_id"], 235)
        self.assertIn("exp", claims)
        self.assertIn("iat", claims)

    def test_expired_token_rejected(self):
        token = self.helper.mint_jwt(
            self.env, tenant="southbrook", persona="trade_partner",
            partner_id=42, tier="T0+T1", ttl_seconds=-1)
        with self.assertRaises(Exception):
            self.helper.verify_jwt(self.env, token)

    def test_tampered_token_rejected(self):
        token = self.helper.mint_jwt(
            self.env, tenant="southbrook", persona="trade_partner",
            partner_id=42, tier="T0+T1")
        tampered = token[:-5] + "XXXXX"
        with self.assertRaises(Exception):
            self.helper.verify_jwt(self.env, tampered)

    def test_resolve_persona_portal_user_is_trade_partner(self):
        portal_user = self.env["res.users"].create({
            "login": f"hermes_test_{int(time.time())}@example.com",
            "name": "Hermes Test Portal",
            # Odoo 19 renamed res.users.groups_id → group_ids; old name
            # was silently no-op'd, leaving the user without the portal
            # group and routing them through the internal-user branch of
            # resolve_persona (returning 'employee' instead of
            # 'trade_partner', which would fail this assertion).
            "group_ids": [(6, 0, [self.env.ref("base.group_portal").id])],
        })
        result = self.helper.resolve_persona(portal_user)
        self.assertEqual(result, "trade_partner")
