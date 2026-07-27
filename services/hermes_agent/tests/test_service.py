# SPDX-License-Identifier: LGPL-3.0-only
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hermes_agent.config import HermesConfig
from hermes_agent.service import run_passive_service


class TestHermesAgentService(unittest.TestCase):

    def test_passive_service_waits_without_creating_recommendations(self):
        sleep_calls = []
        cfg = HermesConfig(
            odoo_base_url="http://odoo:8069",
            odoo_api_key="secret-key",
            service_interval_seconds=5,
        )

        iterations = run_passive_service(
            cfg,
            sleep_fn=sleep_calls.append,
            max_iterations=3,
        )

        self.assertEqual(iterations, 3)
        self.assertEqual(sleep_calls, [5, 5, 5])


if __name__ == "__main__":
    unittest.main()
