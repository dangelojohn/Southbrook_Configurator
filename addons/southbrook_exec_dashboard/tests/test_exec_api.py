# SPDX-License-Identifier: LGPL-3.0-only
import json

from odoo.tests.common import HttpCase, tagged


@tagged("southbrook", "exec_dashboard", "post_install", "-at_install")
class TestExecApiReturnsJson(HttpCase):

    def test_exec_api_returns_json(self):
        # The endpoint is now gated to the executive group — grant it to admin.
        exec_group = self.env.ref(
            "southbrook_exec_dashboard.group_southbrook_exec_dashboard_user")
        self.env.ref("base.user_admin").write(
            {"group_ids": [(4, exec_group.id)]})
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

    def test_exec_api_forbids_non_exec_user(self):
        """A logged-in internal user NOT in the executive group must not read
        the company-financials payload (regression C1)."""
        self.env["res.users"].create({
            "name": "Plain Employee",
            "login": "plain_emp_exec_test",
            "password": "plain_emp_exec_test",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        self.authenticate("plain_emp_exec_test", "plain_emp_exec_test")
        response = self.url_open("/exec/morning", data={})
        self.assertEqual(response.status_code, 403,
                         f"expected 403, got {response.status_code}")
