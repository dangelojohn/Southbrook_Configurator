# SPDX-License-Identifier: LGPL-3.0-only
from odoo.addons.southbrook_estimating import _ensure_sales_journal
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sales_journal")
class TestSalesJournalHook(TransactionCase):

    def test_hook_creates_missing_sales_journal_once(self):
        company = self.env["res.company"].create({
            "name": "Southbrook Journal Hook Test Co",
        })
        Journal = self.env["account.journal"].sudo()
        domain = [("company_id", "=", company.id), ("type", "=", "sale")]
        Journal.search(domain).unlink()

        self.assertFalse(Journal.search(domain))

        _ensure_sales_journal(self.env)
        journals = Journal.search(domain)
        self.assertEqual(len(journals), 1)
        self.assertEqual(journals.name, "Customer Invoices")
        self.assertEqual(journals.code, "INV")

        _ensure_sales_journal(self.env)
        self.assertEqual(len(Journal.search(domain)), 1)
