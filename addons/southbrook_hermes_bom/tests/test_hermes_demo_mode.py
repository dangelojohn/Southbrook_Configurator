# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for the Hermes demo/mock mode and two hardening items:

1. southbrook_hermes_bom.demo_mode short-circuits HermesService.research()
   to a deterministic offline response, with no api_key and no network
   call, and the full wizard flow works end-to-end on top of it.
2. Production (demo_mode off) is fail-closed exactly as before: no key
   raises, and a key present goes through the real requests.post() path
   (demo mode never hijacks it).
3. hermes_available / hermes_config_hint early-validation fields.
4. HermesWizard._clip() truncates + strips control characters.
"""
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..services.hermes_service import HermesService

# Mirrors the CANNED_RESPONSE style used in test_hermes_bom_creation.py —
# used only for the "demo off + key set" case, to prove the real
# requests.post() path is still reachable and demo mode didn't hijack it.
CANNED_RESPONSE_JSON = {
    "product_enrichment": {
        "name": "Soft-Close Hinge — 110°",
        "short_description": "Concealed cup hinge with integrated soft-close.",
        "long_description": "<p>Industry-standard cup hinge.</p>",
        "technical_description": "Steel body, nickel-plated.",
        "manufacturer": "Blum",
        "manufacturer_pn": "B71B3550",
        "dimensions": [],
        "specs": [],
        "install_notes": [],
    },
    "bom": {"bom_type": "normal", "lines": []},
    "audit": {"source_urls": [], "overall_confidence": 0.9},
}


@tagged("post_install", "-at_install", "southbrook", "southbrook_hermes_bom")
class HermesDemoModeCase(TransactionCase):

    def setUp(self):
        super().setUp()
        self.ICP = self.env["ir.config_parameter"].sudo()
        # Start from a clean slate — no key, demo mode off — regardless
        # of whatever data/hermes_config_data.xml seeded.
        self.ICP.set_param("southbrook_hermes_bom.api_key", "")
        self.ICP.set_param("southbrook_hermes_bom.demo_mode", "False")
        self.template = self.env["product.template"].create({
            "name": "Demo Mode Test Cabinet",
            "default_code": "DEMO-TEST-1",
            "type": "consu",
        })

    def _payload(self, **overrides):
        payload = {
            "product_template_id": self.template.id,
            "product_name": self.template.name,
            "internal_reference": self.template.default_code,
            "user_notes": "",
        }
        payload.update(overrides)
        return payload

    # ================================================================
    # (a) demo_mode on + NO api_key → deterministic offline response,
    #     never touches the network.
    # ================================================================
    def test_demo_mode_no_api_key_returns_mock_without_network(self):
        self.ICP.set_param("southbrook_hermes_bom.demo_mode", "True")
        self.assertFalse(self.ICP.get_param("southbrook_hermes_bom.api_key"))

        with patch("requests.post") as mock_post:
            response = HermesService(self.env).research(
                self._payload(user_notes="Focus on the hinge cup size.")
            )
            mock_post.assert_not_called()

        for key in ("product_enrichment", "bom", "audit"):
            self.assertIn(key, response)
        enrichment = response["product_enrichment"]
        self.assertIn("DEMO", enrichment["short_description"].upper())
        self.assertIn(self.template.name, enrichment["name"])
        # Reviewer notes must visibly flow through the demo path.
        joined_notes = " ".join(
            n.get("text", "") for n in enrichment["install_notes"]
        )
        self.assertIn("hinge cup size", joined_notes)

    # ================================================================
    # (b) Full wizard flow in demo mode.
    # ================================================================
    def test_demo_mode_full_wizard_flow_reaches_review(self):
        # Seed a couple of real components so the demo BOM lines have
        # something to match against.
        self.env["product.product"].create({
            "name": "Demo Component A",
            "default_code": "DEMO-COMP-A",
            "type": "consu",
        })
        self.env["product.product"].create({
            "name": "Demo Component B",
            "default_code": "DEMO-COMP-B",
            "type": "consu",
        })
        self.ICP.set_param("southbrook_hermes_bom.demo_mode", "True")

        action = self.template.action_hermes_research_and_build_bom()
        wizard = self.env["hermes.wizard"].browse(action["res_id"])
        wizard.write({"user_notes": "Please double-check the finish."})
        wizard.action_collect_and_research()

        self.assertEqual(wizard.state, "review")
        self.assertTrue(wizard.proposed_name)
        self.assertTrue(wizard.proposed_short_description)
        self.assertTrue(wizard.proposed_bom_json)

        import json
        bom_payload = json.loads(wizard.proposed_bom_json)
        # Components exist in this test DB (seeded above), so the demo
        # response should have found at least one to reference.
        self.assertTrue(
            bom_payload.get("lines"),
            "demo BOM should reference at least one real component "
            "found via product.product search",
        )

        # Applying should not raise and should actually build a BOM.
        wizard.action_apply()
        self.assertEqual(wizard.state, "done")
        bom = self.env["mrp.bom"].search([
            ("product_tmpl_id", "=", self.template.id),
        ])
        self.assertTrue(bom)

    # ================================================================
    # (b2) L3 fix: demo mode must NEVER write customer-visible fields
    #      (name, description_sale) onto the product master — mock text
    #      like "[DEMO] Mock enrichment..." must not reach a quote.
    # ================================================================
    def test_demo_mode_does_not_touch_customer_visible_fields(self):
        self.template.write({
            "name": "Real Cabinet Name",
            "description_sale": "Real sales description a customer sees.",
            "description": False,  # empty internal note
        })
        self.ICP.set_param("southbrook_hermes_bom.demo_mode", "True")

        action = self.template.action_hermes_research_and_build_bom()
        wizard = self.env["hermes.wizard"].browse(action["res_id"])
        wizard.action_collect_and_research()
        self.assertEqual(wizard.state, "review")
        # the proposed customer-visible fields DO carry the demo text...
        self.assertIn("Demo", wizard.proposed_name)
        self.assertIn("[DEMO]", wizard.proposed_short_description)

        wizard.action_apply()

        # ...but applying them must NOT overwrite the customer-facing fields.
        self.assertEqual(
            self.template.name, "Real Cabinet Name",
            "demo mode must not overwrite the product name")
        self.assertEqual(
            self.template.description_sale,
            "Real sales description a customer sees.",
            "demo mode must not overwrite description_sale (the quote leak)")
        # and the demo string must appear nowhere customer-facing
        self.assertNotIn("[DEMO]", self.template.name or "")
        self.assertNotIn("[DEMO]", self.template.description_sale or "")

    def test_demo_confidence_is_below_high_threshold(self):
        """Defense in depth: mock output must read as low-confidence so the
        overwrite guard protects even non-empty fields."""
        from odoo.addons.southbrook_hermes_bom.models.hermes_wizard import (
            HIGH_CONFIDENCE_THRESHOLD,
        )
        from odoo.addons.southbrook_hermes_bom.services.hermes_service import (
            _DEMO_CONFIDENCE,
        )
        self.assertLess(_DEMO_CONFIDENCE, HIGH_CONFIDENCE_THRESHOLD)

    # ================================================================
    # (c) Production fail-closed unchanged: demo off + no key → raises.
    # ================================================================
    def test_demo_off_no_key_still_raises_userror(self):
        self.ICP.set_param("southbrook_hermes_bom.demo_mode", "False")
        self.ICP.set_param("southbrook_hermes_bom.api_key", "")
        with self.assertRaises(UserError):
            HermesService(self.env).research(self._payload())

    # ================================================================
    # (d) Production path unaffected: demo off + key set → attempts the
    #     real requests.post() call (proves demo mode doesn't hijack it).
    # ================================================================
    def test_demo_off_with_key_attempts_real_request(self):
        self.ICP.set_param("southbrook_hermes_bom.demo_mode", "False")
        self.ICP.set_param("southbrook_hermes_bom.api_key", "TEST-KEY-REAL")

        fake_resp = MagicMock()
        fake_resp.raise_for_status.return_value = None
        fake_resp.json.return_value = CANNED_RESPONSE_JSON

        with patch("requests.post", return_value=fake_resp) as mock_post:
            response = HermesService(self.env).research(self._payload())
            mock_post.assert_called_once()

        self.assertEqual(
            response["product_enrichment"]["manufacturer"], "Blum",
        )

    # ================================================================
    # (e) hermes_available / hermes_config_hint
    # ================================================================
    def test_hermes_available_reflects_demo_and_key_state(self):
        self.ICP.set_param("southbrook_hermes_bom.demo_mode", "False")
        self.ICP.set_param("southbrook_hermes_bom.api_key", "")
        action = self.template.action_hermes_research_and_build_bom()
        wizard = self.env["hermes.wizard"].browse(action["res_id"])
        self.assertFalse(wizard.hermes_available)
        self.assertTrue(wizard.hermes_config_hint)

        self.ICP.set_param("southbrook_hermes_bom.demo_mode", "True")
        wizard.invalidate_recordset(
            ["hermes_available", "hermes_config_hint"]
        )
        self.assertTrue(wizard.hermes_available)
        self.assertFalse(wizard.hermes_config_hint)

        # Also true when a real key is set instead of demo mode.
        self.ICP.set_param("southbrook_hermes_bom.demo_mode", "False")
        self.ICP.set_param("southbrook_hermes_bom.api_key", "SOME-KEY")
        wizard.invalidate_recordset(
            ["hermes_available", "hermes_config_hint"]
        )
        self.assertTrue(wizard.hermes_available)

    # ================================================================
    # (f) _clip() truncation + control-char stripping
    # ================================================================
    def test_clip_truncates_and_strips_control_chars(self):
        action = self.template.action_hermes_research_and_build_bom()
        wizard = self.env["hermes.wizard"].browse(action["res_id"])

        long_name = "A" * 300
        clipped = wizard._clip(long_name, 256)
        self.assertEqual(len(clipped), 256)

        dirty = "Hello\x00World\x07!\nkeep this\ttab"
        cleaned = wizard._clip(dirty, 100)
        self.assertNotIn("\x00", cleaned)
        self.assertNotIn("\x07", cleaned)
        self.assertIn("\n", cleaned)
        self.assertIn("\t", cleaned)
        self.assertIn("HelloWorld!", cleaned)
