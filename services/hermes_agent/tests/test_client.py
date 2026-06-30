# SPDX-License-Identifier: LGPL-3.0-only
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hermes_agent.client import HermesOdooClient, build_recommendation_payload
from hermes_agent.config import HermesConfig, load_config


class FakeTransport:

    def __init__(self):
        self.calls = []

    def post_json(self, url, payload, headers):
        self.calls.append((url, payload, headers))
        return {"ok": True, "recommendation_id": 12, "state": "draft"}


class TestHermesAgentClient(unittest.TestCase):

    def test_load_config_requires_odoo_settings(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                load_config()

    def test_load_config_defaults_to_free_gemini_testing_model(self):
        env = {
            "HERMES_ODOO_BASE_URL": "https://southbrookcabinetry.space",
            "HERMES_ODOO_API_KEY": "secret-key",
        }

        cfg = load_config(env)

        self.assertEqual(cfg.model_provider, "google")
        self.assertEqual(cfg.model_name, "gemini-3.5-flash")

    def test_load_config_defaults_passive_service_interval(self):
        env = {
            "HERMES_ODOO_BASE_URL": "https://southbrookcabinetry.space",
            "HERMES_ODOO_API_KEY": "secret-key",
        }

        cfg = load_config(env)

        self.assertEqual(cfg.service_interval_seconds, 300)

    def test_build_recommendation_payload_defaults_to_draft_safe_shape(self):
        payload = build_recommendation_payload(
            name="Review commercial estimate",
            summary="Confirm the estimate before changing Odoo records.",
            recommendation_type="task",
            proposed_action="Ask an estimator to review the discrepancy.",
            payload={"project_id": 7, "task_name": "Review estimate"},
            agent_run_id="run-123",
            model_provider="google",
            model_name="gemini-3.5-flash",
        )

        self.assertEqual(payload["name"], "Review commercial estimate")
        self.assertEqual(payload["recommendation_type"], "task")
        self.assertEqual(payload["payload"]["project_id"], 7)
        self.assertEqual(payload["agent_run_id"], "run-123")

    def test_client_posts_json_with_api_key(self):
        transport = FakeTransport()
        cfg = HermesConfig(
            odoo_base_url="https://southbrookcabinetry.space",
            odoo_api_key="secret-key",
            model_provider="google",
            model_name="gemini-3.5-flash",
        )
        client = HermesOdooClient(cfg, transport=transport)
        payload = build_recommendation_payload(
            name="Draft recommendation",
            summary="Human approval required.",
        )

        result = client.create_recommendation(payload)

        self.assertEqual(result["state"], "draft")
        self.assertEqual(
            transport.calls[0][0],
            "https://southbrookcabinetry.space/hermes/api/v1/recommendations",
        )
        self.assertEqual(transport.calls[0][2]["X-Api-Key"], "secret-key")
        self.assertEqual(transport.calls[0][2]["Content-Type"], "application/json")


if __name__ == "__main__":
    unittest.main()
