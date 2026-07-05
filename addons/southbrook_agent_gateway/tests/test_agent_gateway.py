# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook_agent_gateway tests.

Two layers, mirroring the addon's own split:
  * TransactionCase against southbrook.agent.inquiry — validation,
    partner dedupe, lead creation, verification state machine (the
    whole business flow, no HTTP).
  * HttpCase against the public routes — content types, status codes,
    honeypot, token-gated status polling (the transport contract an
    external AI agent actually sees).
"""
import json

from odoo.tests.common import HttpCase, TransactionCase, tagged


def _payload(**overrides):
    base = {
        "agent": {"name": "TestShopper", "platform": "unit-test"},
        "customer": {
            "name": "Pat Prospect",
            "email": "pat.prospect@example.com",
            "phone": "+1 613 555 0142",
        },
        "project": {
            "description": "Full 10x12 L-shaped kitchen, shaker doors, "
                           "island if budget allows.",
            "room_type": "kitchen",
            "budget_range": "$10,000-$15,000",
            "timeline": "next 3 months",
        },
        "consent": True,
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key].update(value)
        else:
            base[key] = value
    return base


@tagged("post_install", "-at_install", "southbrook", "agent_gateway")
class TestAgentInquiryModel(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Inquiry = cls.env["southbrook.agent.inquiry"]

    def test_validate_happy_path(self):
        cleaned, err = self.Inquiry.validate_payload(_payload())
        self.assertIsNone(err)
        self.assertEqual(cleaned["customer_name"], "Pat Prospect")
        self.assertEqual(cleaned["email"], "pat.prospect@example.com")
        # phone_validation must have E.164-formatted the number.
        self.assertTrue(cleaned["phone"].startswith("+1613"))

    def test_validate_rejects_missing_consent(self):
        cleaned, err = self.Inquiry.validate_payload(_payload(consent=False))
        self.assertIsNone(cleaned)
        self.assertIn("consent", err)

    def test_validate_rejects_bad_email(self):
        cleaned, err = self.Inquiry.validate_payload(
            _payload(customer={"email": "not-an-email"}))
        self.assertIsNone(cleaned)
        self.assertIn("email", err)

    def test_validate_rejects_bad_phone(self):
        cleaned, err = self.Inquiry.validate_payload(
            _payload(customer={"phone": "call me maybe"}))
        self.assertIsNone(cleaned)
        self.assertIn("phone", err)

    def test_validate_rejects_short_description(self):
        cleaned, err = self.Inquiry.validate_payload(
            _payload(project={"description": "hi"}))
        self.assertIsNone(cleaned)
        self.assertIn("description", err)

    def test_validate_rejects_non_dict_body(self):
        cleaned, err = self.Inquiry.validate_payload(["not", "a", "dict"])
        self.assertIsNone(cleaned)
        self.assertTrue(err)

    def test_submit_creates_partner_lead_and_tokens(self):
        cleaned, err = self.Inquiry.validate_payload(_payload())
        self.assertIsNone(err)
        inquiry = self.Inquiry.submit(cleaned, user_agent="pytest")
        self.assertTrue(inquiry.reference.startswith("AIQ-"))
        self.assertEqual(inquiry.state, "new")
        self.assertTrue(inquiry.verify_token)
        self.assertTrue(inquiry.status_token)
        self.assertNotEqual(inquiry.verify_token, inquiry.status_token)
        self.assertTrue(inquiry.partner_id)
        self.assertEqual(inquiry.partner_id.email, "pat.prospect@example.com")
        self.assertTrue(inquiry.lead_id)
        self.assertEqual(inquiry.lead_id.type, "lead")
        self.assertIn("UNVERIFIED", inquiry.lead_id.description)
        source = self.env.ref("southbrook_agent_gateway.utm_source_ai_agent")
        self.assertEqual(inquiry.lead_id.source_id, source)

    def test_submit_dedupes_partner_by_email(self):
        existing = self.env["res.partner"].create({
            "name": "Pat Already-Here",
            "email": "pat.prospect@example.com",
        })
        cleaned, _err = self.Inquiry.validate_payload(_payload())
        inquiry = self.Inquiry.submit(cleaned)
        self.assertEqual(inquiry.partner_id, existing)
        # Never overwrite an existing contact's name from an unverified
        # third-party submission.
        self.assertEqual(existing.name, "Pat Already-Here")

    def test_submit_spam_creates_nothing_but_the_audit_record(self):
        cleaned, _err = self.Inquiry.validate_payload(_payload())
        leads_before = self.env["crm.lead"].search_count([])
        inquiry = self.Inquiry.submit(cleaned, is_spam=True)
        self.assertEqual(inquiry.state, "spam")
        self.assertFalse(inquiry.partner_id)
        self.assertFalse(inquiry.lead_id)
        self.assertEqual(self.env["crm.lead"].search_count([]), leads_before)

    def test_verify_by_token_flips_state_and_logs_on_lead(self):
        cleaned, _err = self.Inquiry.validate_payload(_payload())
        inquiry = self.Inquiry.submit(cleaned)
        msgs_before = len(inquiry.lead_id.message_ids)
        verified = self.Inquiry.verify_by_token(inquiry.verify_token)
        self.assertEqual(verified, inquiry)
        self.assertEqual(inquiry.state, "verified")
        self.assertTrue(inquiry.verified_at)
        self.assertGreater(len(inquiry.lead_id.message_ids), msgs_before)
        # Idempotent re-click.
        again = self.Inquiry.verify_by_token(inquiry.verify_token)
        self.assertEqual(again, inquiry)

    def test_verify_by_token_rejects_garbage(self):
        self.assertFalse(self.Inquiry.verify_by_token("nope"))
        self.assertFalse(self.Inquiry.verify_by_token(""))
        self.assertFalse(self.Inquiry.verify_by_token(None))
        self.assertFalse(self.Inquiry.verify_by_token("x" * 500))

    def test_status_payload_shape(self):
        cleaned, _err = self.Inquiry.validate_payload(_payload())
        inquiry = self.Inquiry.submit(cleaned)
        status = inquiry.status_payload()
        self.assertEqual(status["reference"], inquiry.reference)
        self.assertEqual(status["state"], "new")
        self.assertFalse(status["email_verified"])
        self.assertIn("sales_stage", status)


@tagged("post_install", "-at_install", "southbrook", "agent_gateway")
class TestAgentGatewayHttp(HttpCase):

    def _post_quote(self, payload):
        return self.url_open(
            "/agent/api/v1/quote-request",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

    def test_llms_txt_served(self):
        resp = self.url_open("/llms.txt")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/plain", resp.headers.get("Content-Type", ""))
        body = resp.text
        self.assertIn("Southbrook Cabinetry", body)
        self.assertIn("/agent/api/v1/quote-request", body)
        self.assertIn("/agent/api/v1/openapi.json", body)

    def test_openapi_served(self):
        resp = self.url_open("/agent/api/v1/openapi.json")
        self.assertEqual(resp.status_code, 200)
        spec = resp.json()
        self.assertEqual(spec["openapi"], "3.1.0")
        self.assertIn("/agent/api/v1/quote-request", spec["paths"])

    def test_offerings_served(self):
        resp = self.url_open("/agent/api/v1/offerings")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["company"], "Southbrook Cabinetry")
        self.assertIsInstance(data["cabinets"], list)
        self.assertTrue(data["cabinets"], "the 12 seeded cabinets must "
                                          "appear in the public catalog")
        first = data["cabinets"][0]
        for key in ("name", "sku", "category", "list_price"):
            self.assertIn(key, first)

    def test_quote_request_happy_path_over_http(self):
        resp = self._post_quote(_payload())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["reference"].startswith("AIQ-"))
        self.assertEqual(data["status"], "pending_email_verification")
        self.assertIn("status_token", data)

        # Status poll with the returned token.
        status_resp = self.url_open(
            "/agent/api/v1/quote-request/%s/status?token=%s"
            % (data["reference"], data["status_token"]))
        self.assertEqual(status_resp.status_code, 200)
        self.assertEqual(status_resp.json()["state"], "new")

        # Wrong token → 404, same as unknown reference (no oracle).
        bad = self.url_open(
            "/agent/api/v1/quote-request/%s/status?token=wrong"
            % data["reference"])
        self.assertEqual(bad.status_code, 404)

    def test_quote_request_validation_error_is_400(self):
        resp = self._post_quote(_payload(consent=False))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"], "invalid")

    def test_quote_request_malformed_json_is_400(self):
        resp = self.url_open(
            "/agent/api/v1/quote-request",
            data="{not json",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_quote_request_honeypot_returns_ok_but_creates_no_lead(self):
        leads_before = self.env["crm.lead"].search_count([])
        resp = self._post_quote(_payload(website_url="http://spam.example"))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        self.assertEqual(
            self.env["crm.lead"].search_count([]), leads_before,
            "honeypot submissions must not reach the CRM")
        ref = resp.json()["reference"]
        inquiry = self.env["southbrook.agent.inquiry"].sudo().search(
            [("reference", "=", ref)])
        self.assertEqual(inquiry.state, "spam")

    def test_verify_link_flips_state(self):
        resp = self._post_quote(_payload())
        ref = resp.json()["reference"]
        inquiry = self.env["southbrook.agent.inquiry"].sudo().search(
            [("reference", "=", ref)])
        page = self.url_open("/agent/verify/%s" % inquiry.verify_token)
        self.assertEqual(page.status_code, 200)
        self.assertIn("confirmed", page.text)
        inquiry.invalidate_recordset()
        self.assertEqual(inquiry.state, "verified")

    def test_verify_bad_token_renders_invalid_page(self):
        page = self.url_open("/agent/verify/definitely-not-a-token")
        self.assertEqual(page.status_code, 200)
        self.assertIn("isn't valid", page.text)
