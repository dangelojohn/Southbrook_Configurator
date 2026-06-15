# SPDX-License-Identifier: LGPL-3.0-only
"""Regression coverage for the public /commercial page.

The live site is served by Odoo behind Caddy/Cloudflare. A standalone
static page can exist on disk and still 404 in production unless the Odoo
website addon owns the route.
"""

from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install", "southbrook", "commercial_page")
class TestCommercialPage(HttpCase):

    def test_commercial_page_is_served_by_odoo_website(self):
        resp = self.url_open("/commercial")
        self.assertEqual(resp.status_code, 200)

        html = resp.text
        self.assertIn(
            "Make Odoo Projects the operating system for cabinet manufacturing.",
            html,
        )
        self.assertIn("Practical intelligence layer", html)
        self.assertIn("Request commercial review", html)
