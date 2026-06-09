# SPDX-License-Identifier: LGPL-3.0-only
"""Dealer-channel ACL — only res.partner.channel='dealer' portal users
may reach /my/dealer/* routes. Tested as second-customer per ACL discipline."""
from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install", "southbrook", "dealer_portal", "acl")
class TestDealerACL(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env["res.partner"]
        Users = cls.env["res.users"]
        portal_group = cls.env.ref("base.group_portal")

        cls.dealer_partner = Partner.create({
            "name": "Dealer Joe", "email": "dealer.joe@example.com",
            "channel": "dealer",
        })
        cls.dealer_user = Users.create({
            "login": "dealer.joe@example.com",
            "password": "dealer-strong-pw",
            "partner_id": cls.dealer_partner.id,
            "group_ids": [(6, 0, [portal_group.id])],
        })

        cls.retail_partner = Partner.create({
            "name": "Retail Walk-In", "email": "retail.walkin@example.com",
            "channel": "retail",
        })
        cls.retail_user = Users.create({
            "login": "retail.walkin@example.com",
            "password": "retail-strong-pw",
            "partner_id": cls.retail_partner.id,
            "group_ids": [(6, 0, [portal_group.id])],
        })

    def test_dealer_can_open_dealer_orders(self):
        self.authenticate("dealer.joe@example.com", "dealer-strong-pw")
        resp = self.url_open("/my/dealer/orders")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Dealer Orders", resp.text)

    def test_retail_user_blocked_from_dealer_route(self):
        """Retail partner is NOT a dealer — must hit AccessError → 403."""
        self.authenticate("retail.walkin@example.com", "retail-strong-pw")
        resp = self.url_open("/my/dealer/orders")
        # Odoo renders AccessError as 403 in portal/website contexts.
        self.assertEqual(resp.status_code, 403)

    def test_anonymous_blocked(self):
        resp = self.url_open("/my/dealer/orders", allow_redirects=False)
        self.assertIn(resp.status_code, (301, 302, 303, 401, 403))
