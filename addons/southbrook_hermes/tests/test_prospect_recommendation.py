# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for the prospect recommendation type — the apply path that
synthesizes a crm.lead from a lead_prospector agent payload.

The lead_prospector is the Hermes Console agent loop that uses
Gemini-grounded Google search to discover potential Southbrook customers.
It submits draft recommendations through the southbrook_api boundary; a
Southbrook sales reviewer hits Approve → Apply, and this code path turns
the structured payload into a real crm.lead with full provenance.
"""
import json

from odoo.tests.common import TransactionCase, tagged


_FULL_PAYLOAD = {
    "company": "ACME Construction Ltd",
    "lead_type": "construction_renovation_project",
    "city": "Toronto, ON",
    "source_url": "https://example.com/news/acme-tower-project",
    "contact_hint": "info@acme.example",
    "why_fit": (
        "Multi-floor luxury condo build with custom kitchens spec'd in "
        "their tender; flat-pack signature-series fit is natural."
    ),
}


@tagged("post_install", "-at_install", "southbrook", "hermes", "prospect")
class TestProspectRecommendation(TransactionCase):

    def _draft_prospect(self, **payload_overrides):
        """Create + approve a prospect recommendation ready to apply."""
        payload = {**_FULL_PAYLOAD, **payload_overrides}
        rec = self.env["southbrook.hermes.recommendation"].create({
            "name": "Hermes prospect — ACME Construction",
            "recommendation_type": "prospect",
            "priority": "high",
            "summary": "Prospect surfaced by lead_prospector loop.",
            "proposed_action": "Outreach via salesperson rotation.",
            "payload_json": json.dumps(payload),
            "agent_run_id": "test-prospect-001",
            "model_provider": "google",
            "model_name": "gemini-2.5-flash",
        })
        rec.action_approve()
        return rec

    # ------------------------------------------------------------------
    # Happy-path mapping
    # ------------------------------------------------------------------
    def test_apply_creates_crm_lead(self):
        rec = self._draft_prospect()
        before = self.env["crm.lead"].search_count([])
        rec.action_apply()
        after = self.env["crm.lead"].search_count([])
        self.assertEqual(after, before + 1)
        self.assertEqual(rec.state, "applied")
        self.assertTrue(rec.created_crm_lead_id)

    def test_lead_field_mapping(self):
        rec = self._draft_prospect()
        rec.action_apply()
        lead = rec.created_crm_lead_id
        self.assertEqual(lead.partner_name, "ACME Construction Ltd")
        self.assertEqual(lead.city, "Toronto")  # province stripped
        self.assertEqual(lead.type, "lead")
        self.assertEqual(lead.priority, "2")  # high → "2"
        self.assertIn("Multi-floor luxury condo", lead.description)
        self.assertIn("info@acme.example", lead.description)
        self.assertIn("construction_renovation_project", lead.description)

    # ------------------------------------------------------------------
    # Priority mapping — exhaustive across the four recommendation tiers
    # ------------------------------------------------------------------
    def test_priority_mapping_low(self):
        rec = self._draft_prospect()
        rec.priority = "low"
        # priority can be set on an approved recommendation before apply.
        rec.action_apply()
        self.assertEqual(rec.created_crm_lead_id.priority, "0")

    def test_priority_mapping_blocker(self):
        rec = self._draft_prospect()
        rec.priority = "blocker"
        rec.action_apply()
        self.assertEqual(rec.created_crm_lead_id.priority, "3")

    # ------------------------------------------------------------------
    # Source URL filtering — Google's grounding redirector is unsalespable
    # ------------------------------------------------------------------
    def test_source_url_real_domain_becomes_website(self):
        rec = self._draft_prospect(
            source_url="https://realbusiness.example/about",
        )
        rec.action_apply()
        self.assertEqual(
            rec.created_crm_lead_id.website,
            "https://realbusiness.example/about",
        )

    def test_source_url_google_redirector_dropped(self):
        rec = self._draft_prospect(
            source_url=(
                "https://vertexaisearch.cloud.google.com/grounding-api-redirect/"
                "abc123"
            ),
        )
        rec.action_apply()
        # The redirector should NOT become the lead's website (no
        # salespable value), but should still appear in the description
        # as the citation source.
        self.assertFalse(rec.created_crm_lead_id.website)
        self.assertIn(
            "vertexaisearch.cloud.google.com",
            rec.created_crm_lead_id.description,
        )

    # ------------------------------------------------------------------
    # Tag synthesis — the sales pipeline filter
    # ------------------------------------------------------------------
    def test_tag_synthesized_when_new(self):
        rec = self._draft_prospect(lead_type="kitchen_manufacturer")
        before = self.env["crm.tag"].search_count(
            [("name", "=", "Hermes: kitchen_manufacturer")])
        self.assertEqual(before, 0)
        rec.action_apply()
        after = self.env["crm.tag"].search_count(
            [("name", "=", "Hermes: kitchen_manufacturer")])
        self.assertEqual(after, 1)
        tags = rec.created_crm_lead_id.tag_ids.mapped("name")
        self.assertIn("Hermes: kitchen_manufacturer", tags)

    def test_tag_reused_not_duplicated(self):
        # Pre-create the tag
        self.env["crm.tag"].create({
            "name": "Hermes: construction_renovation_project"})
        rec = self._draft_prospect()  # full payload includes this lead_type
        rec.action_apply()
        # Should NOT have created a duplicate
        count = self.env["crm.tag"].search_count(
            [("name", "=", "Hermes: construction_renovation_project")])
        self.assertEqual(count, 1)

    # ------------------------------------------------------------------
    # Resilience to incomplete payloads
    # ------------------------------------------------------------------
    def test_missing_company_uses_placeholder(self):
        rec = self._draft_prospect(company=None)
        rec.action_apply()
        # The lead is still created — no "company" becomes a generic
        # placeholder rather than blocking the apply.
        self.assertTrue(rec.created_crm_lead_id)
        self.assertEqual(rec.created_crm_lead_id.partner_name, "Unknown company")

    def test_city_without_province(self):
        rec = self._draft_prospect(city="Vancouver")
        rec.action_apply()
        self.assertEqual(rec.created_crm_lead_id.city, "Vancouver")

    def test_chatter_post_explains_source(self):
        rec = self._draft_prospect()
        rec.action_apply()
        body = rec.created_crm_lead_id.message_ids[0].body
        self.assertIn("Fabio prospect recommendation", body)
        self.assertIn("Hermes Lead Prospector", body)
