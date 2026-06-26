# SPDX-License-Identifier: LGPL-3.0-only
import json

from odoo.tests.common import HttpCase, tagged


@tagged("southbrook", "exec_dashboard", "post_install", "-at_install")
class TestExecApiReturnsJson(HttpCase):

    def test_exec_api_returns_json(self):
        # Authenticate as admin so the portal-session branch fires
        self.authenticate("admin", "admin")
        response = self.url_open("/exec/morning", data={})
        self.assertEqual(
            response.status_code, 200,
            f"expected 200, got {response.status_code} body={response.text[:200]}",
        )
        self.assertEqual(
            response.headers.get("Content-Type", "").split(";")[0],
            "application/json",
        )
        body = json.loads(response.text)
        # Required keys per spec
        for key in (
            "as_of", "units_yesterday", "fpy_7d", "otd_30d", "wip",
            "bottleneck", "revenue_30d", "cash",
        ):
            self.assertIn(key, body, f"missing key '{key}' in {body!r}")
        # bottleneck is a nested dict
        self.assertIn("workcenter", body["bottleneck"])
        self.assertIn("load_pct", body["bottleneck"])
