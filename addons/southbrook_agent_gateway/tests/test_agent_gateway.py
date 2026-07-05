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

    # ------------------------------------------------------------------
    # v2 — phone tightening, address capture, draft-quote line items
    # ------------------------------------------------------------------
    def test_validate_rejects_freetext_phone(self):
        # Regression: phone_format echoes unparseable input back rather
        # than raising; the tightened _format_phone must still reject it.
        cleaned, err = self.Inquiry.validate_payload(
            _payload(customer={"phone": "call me maybe"}))
        self.assertIsNone(cleaned)
        self.assertIn("phone", err)

    def test_validate_captures_address(self):
        cleaned, err = self.Inquiry.validate_payload(_payload(address={
            "street": "123 Bank St",
            "city": "Ottawa",
            "state": "Ontario",
            "zip": "K1P 1A1",
            "country": "Canada",
        }))
        self.assertIsNone(err)
        self.assertEqual(cleaned["street"], "123 Bank St")
        self.assertEqual(cleaned["city"], "Ottawa")
        self.assertEqual(cleaned["zip_code"], "K1P 1A1")

    def test_new_partner_gets_address(self):
        cleaned, _err = self.Inquiry.validate_payload(_payload(
            customer={"email": "addr.test@example.com"},
            address={"street": "500 King St", "city": "Toronto",
                     "country": "Canada"}))
        inquiry = self.Inquiry.submit(cleaned)
        self.assertEqual(inquiry.partner_id.street, "500 King St")
        self.assertEqual(inquiry.partner_id.city, "Toronto")
        self.assertTrue(inquiry.partner_id.country_id)
        self.assertEqual(inquiry.partner_id.country_id.code, "CA")

    def test_existing_partner_address_not_overwritten(self):
        existing = self.env["res.partner"].create({
            "name": "Established Customer",
            "email": "established@example.com",
            "phone": False,
        })
        cleaned, _err = self.Inquiry.validate_payload(_payload(
            customer={"email": "established@example.com",
                      "phone": "+1 613 555 0142"},
            address={"street": "999 Attacker Rd"}))
        inquiry = self.Inquiry.submit(cleaned)
        self.assertEqual(inquiry.partner_id, existing)
        # SECURITY: unverified third-party submission must NOT write onto
        # a pre-existing contact — not phone, not address.
        self.assertFalse(existing.phone)
        self.assertFalse(existing.street)

    def test_validate_line_items_resolves_real_skus(self):
        tmpl = self.env.ref("southbrook_estimating.base_1dr")
        items, err = self.Inquiry.validate_line_items(
            [{"sku": tmpl.default_code, "qty": 3}])
        self.assertIsNone(err)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["template"], tmpl)
        self.assertEqual(items[0]["qty"], 3)

    def test_validate_line_items_rejects_unknown_sku(self):
        items, err = self.Inquiry.validate_line_items(
            [{"sku": "NOT-A-REAL-SKU", "qty": 1}])
        self.assertIsNone(items)
        self.assertIn("unknown SKU", err)

    def test_validate_line_items_empty_is_lead_only(self):
        items, err = self.Inquiry.validate_line_items(None)
        self.assertIsNone(err)
        self.assertEqual(items, [])

    def test_validate_line_items_caps_qty(self):
        tmpl = self.env.ref("southbrook_estimating.base_1dr")
        items, err = self.Inquiry.validate_line_items(
            [{"sku": tmpl.default_code, "qty": 9999}])
        self.assertIsNone(items)
        self.assertIn("between 1 and", err)

    def test_submit_with_line_items_creates_draft_quote(self):
        tmpl = self.env.ref("southbrook_estimating.base_1dr")
        cleaned, _err = self.Inquiry.validate_payload(
            _payload(customer={"email": "quote.buyer@example.com"}))
        items, _e = self.Inquiry.validate_line_items(
            [{"sku": tmpl.default_code, "qty": 2}])
        inquiry = self.Inquiry.submit(cleaned, line_items=items)
        order = inquiry.sale_order_id
        self.assertTrue(order)
        # Submitted for review, never confirmed (no MOs spawned).
        self.assertEqual(order.state, "sent")
        self.assertEqual(len(order.order_line), 1)
        self.assertEqual(order.order_line.product_uom_qty, 2)
        self.assertEqual(
            order.order_line.product_id.product_tmpl_id, tmpl)
        # Quote summary is customer-safe and priced.
        summary = inquiry.quote_summary()
        self.assertEqual(summary["quote_reference"], order.name)
        self.assertEqual(len(summary["lines"]), 1)
        self.assertGreater(summary["total"], 0)
        self.assertNotIn("cost", summary)
        self.assertNotIn("margin", summary)

    def test_submit_without_line_items_creates_no_order(self):
        cleaned, _err = self.Inquiry.validate_payload(_payload())
        inquiry = self.Inquiry.submit(cleaned, line_items=[])
        self.assertFalse(inquiry.sale_order_id)
        self.assertIsNone(inquiry.quote_summary())


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

    def test_quote_endpoint_requires_line_items(self):
        # /quote without line_items is a 400 pointing at /quote-request.
        resp = self.url_open(
            "/agent/api/v1/quote",
            data=json.dumps(_payload()),
            headers={"Content-Type": "application/json"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("line_items is required", resp.json()["detail"])

    def test_quote_endpoint_returns_priced_quote(self):
        tmpl = self.env.ref("southbrook_estimating.base_1dr")
        body = _payload(
            customer={"email": "http.quote@example.com"},
            address={"city": "Ottawa", "country": "Canada"})
        body["line_items"] = [{"sku": tmpl.default_code, "qty": 4}]
        resp = self.url_open(
            "/agent/api/v1/quote",
            data=json.dumps(body),
            headers={"Content-Type": "application/json"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertIn("quote", data)
        quote = data["quote"]
        self.assertTrue(quote["quote_reference"].startswith("S"))
        self.assertEqual(len(quote["lines"]), 1)
        self.assertEqual(quote["lines"][0]["qty"], 4)
        self.assertGreater(quote["total"], 0)

    def test_offerings_advertises_instant_quote(self):
        resp = self.url_open("/agent/api/v1/offerings")
        data = resp.json()
        self.assertEqual(
            data["instant_quote_endpoint"], "/agent/api/v1/quote")
