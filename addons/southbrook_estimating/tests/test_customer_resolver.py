# SPDX-License-Identifier: LGPL-3.0-only
"""Customer identity resolver (2026-07-06).

The Order Builder is a staff/dealer tool: the logged-in user builds an
order ON BEHALF OF a customer, so the order must be tied to a distinct,
captured customer — never the employee. res.partner._southbrook_resolve_
customer is the one routine that resolves-or-creates that customer.
"""
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "customer_resolver")
class TestCustomerResolver(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]

    def test_creates_new_customer_with_full_fields(self):
        p = self.Partner._southbrook_resolve_customer({
            "name": "Jane Homeowner", "email": "jane@example.com",
            "phone": "555-0100", "street": "5 Elm St", "city": "Barrie",
            "zip": "L4N 1A1",
        }, trusted=True)
        self.assertTrue(p.id)
        self.assertEqual(p.name, "Jane Homeowner")
        self.assertEqual(p.email, "jane@example.com")
        self.assertEqual(p.phone, "555-0100")
        self.assertEqual(p.city, "Barrie")
        self.assertGreaterEqual(p.customer_rank, 1,
                                "resolved customer must list as a customer")

    def test_dedup_by_email_returns_same_partner(self):
        a = self.Partner._southbrook_resolve_customer(
            {"name": "First Label", "email": "dup@example.com"}, trusted=True)
        b = self.Partner._southbrook_resolve_customer(
            {"name": "Second Label", "email": "dup@example.com"}, trusted=True)
        self.assertEqual(a.id, b.id, "same email must resolve to one partner")
        self.assertEqual(b.name, "First Label",
                         "an existing contact's name must not be overwritten")

    def test_untrusted_never_mutates_existing_contact(self):
        existing = self.Partner.create({
            "name": "Real Customer", "email": "real@example.com"})
        # unverified public submission claiming the same email + a phone
        got = self.Partner._southbrook_resolve_customer(
            {"name": "Impostor", "email": "real@example.com",
             "phone": "555-9999"}, trusted=False)
        self.assertEqual(got.id, existing.id)
        self.assertFalse(existing.phone,
                         "untrusted submission must not plant data on a "
                         "pre-existing contact")

    def test_trusted_backfills_only_blanks(self):
        existing = self.Partner.create({
            "name": "Has Name", "email": "blank@example.com"})  # no phone
        self.Partner._southbrook_resolve_customer(
            {"name": "Ignored", "email": "blank@example.com",
             "phone": "555-2222"}, trusted=True)
        self.assertEqual(existing.phone, "555-2222",
                         "trusted rep may backfill a blank field")
        self.assertEqual(existing.name, "Has Name",
                         "backfill must not overwrite a non-blank field")

    def test_name_only_walkin_creates_customer(self):
        p = self.Partner._southbrook_resolve_customer(
            {"name": "Walk-in Customer"}, trusted=True)
        self.assertTrue(p.id)
        self.assertEqual(p.name, "Walk-in Customer")

    def test_empty_raises(self):
        with self.assertRaises(ValidationError):
            self.Partner._southbrook_resolve_customer({}, trusted=True)
