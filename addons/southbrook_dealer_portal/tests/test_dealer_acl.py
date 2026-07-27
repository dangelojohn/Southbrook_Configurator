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

    # ------------------------------------------------------------------
    # C1/C2 — object-level auth on the export routes (IDOR)
    # ------------------------------------------------------------------
    def _make_owned_package(self, partner):
        """A production package traced to `partner`'s own sale order."""
        product = self.env["product.product"].create({
            "name": "IDOR test cab", "type": "consu", "is_storable": True})
        self.env["mrp.bom"].create({
            "product_tmpl_id": product.product_tmpl_id.id, "product_qty": 1.0})
        order = self.env["sale.order"].create({
            "partner_id": partner.id,
            "order_line": [(0, 0, {
                "product_id": product.id, "product_uom_qty": 1.0})]})
        mo = self.env["mrp.production"].create({
            "product_id": product.id, "product_qty": 1.0})
        pkg = self.env["sb.production.package"].generate_from_mo(
            mo, 600, 720, 580, "base", 2, 0, soft_close=True)
        pkg.sale_order_line_id = order.order_line[0].id
        return pkg

    def test_dealer_cannot_export_another_partners_package(self):
        """C1/C2: a dealer must NOT be able to KD-export a package belonging
        to a different customer's order (enumerating pkg ids)."""
        victim = self.env["res.partner"].create({
            "name": "Victim Co", "channel": "dealer"})
        pkg = self._make_owned_package(victim)
        self.authenticate("dealer.joe@example.com", "dealer-strong-pw")
        resp = self.url_open(
            f"/my/dealer/production-package/{pkg.id}/kd",
            allow_redirects=False)
        self.assertIn(resp.status_code, (400, 403, 404))
        self.assertNotIn("southbrook.kd_flatpack", resp.text)

    def test_dealer_can_export_own_package(self):
        """Positive: the owning dealer CAN export their own package."""
        pkg = self._make_owned_package(self.dealer_partner)
        self.authenticate("dealer.joe@example.com", "dealer-strong-pw")
        resp = self.url_open(f"/my/dealer/production-package/{pkg.id}/kd")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("southbrook.kd_flatpack", resp.text)
