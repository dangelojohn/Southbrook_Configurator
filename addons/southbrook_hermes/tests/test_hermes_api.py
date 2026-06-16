# SPDX-License-Identifier: LGPL-3.0-only
import json

from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install", "southbrook", "hermes", "api")
class TestHermesApi(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.api_user = cls.env.ref("base.user_admin")
        issued = cls.env["southbrook.api.key"].sudo().issue_for_user(
            cls.api_user, label="hermes-test",
        )
        cls.api_key = issued["cleartext"]

    def _post(self, payload, api_key=None):
        headers = {"Content-Type": "application/json"}
        if api_key is not None:
            headers["X-Api-Key"] = api_key
        return self.url_open(
            "/hermes/api/v1/recommendations",
            data=payload if isinstance(payload, str) else json.dumps(payload),
            headers=headers,
        )

    def test_create_recommendation_requires_api_key(self):
        resp = self._post({
            "name": "Unauthenticated recommendation",
            "summary": "This should not be accepted.",
        })

        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["error"], "invalid_api_key")

    def test_create_recommendation_rejects_bad_json(self):
        resp = self._post("not-json", api_key=self.api_key)

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"], "bad_json")

    def test_create_recommendation_creates_draft(self):
        resp = self._post({
            "name": "Draft from HERMES",
            "recommendation_type": "note",
            "summary": "A human should review this recommendation.",
            "rationale": "The agent found a mismatch in source data.",
            "proposed_action": "Open a review task if the mismatch is real.",
            "payload": {"source": "unit-test"},
            "agent_run_id": "api-run-001",
            "model_provider": "openai",
            "model_name": "gpt-5",
        }, api_key=self.api_key)

        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["state"], "draft")

        rec = self.env["southbrook.hermes.recommendation"].browse(
            body["recommendation_id"],
        )
        self.assertTrue(rec.exists())
        self.assertEqual(rec.name, "Draft from HERMES")
        self.assertEqual(rec.state, "draft")
        self.assertEqual(rec.agent_run_id, "api-run-001")
