# SPDX-License-Identifier: LGPL-3.0-only
import logging

from . import models

_logger = logging.getLogger(__name__)


def _ensure_sales_journal(env):
    """Create a default Sales journal for any company that lacks one.

    REG-C1 (2026-06-18): Claude Chrome end-to-end Run 2 reported that
    `Create Invoice` on a confirmed sale.order throws

        Invalid Operation — No journal could be found in company
        Southbrook Cabinetry for any of those types: sale.

    Out-of-the-box Odoo creates a Sales journal during the Accounting
    onboarding wizard. The Southbrook live database skipped that
    wizard (the rep stack was installed straight into a fresh DB
    without an accountant ever logging in), so no journal exists and
    `account_move._search_default_journal` returns nothing.

    This hook is idempotent: it only acts on companies that have zero
    `account.journal` records of type=sale. Companies whose accountant
    has set up their own Sales journal (manual record, l10n module
    chart-of-accounts import, etc.) are skipped untouched.

    Runs on -i AND -u of southbrook_estimating, which means an
    upgrade against the broken live DB will also heal it. The
    accountant can still rename / re-code / re-link the auto-created
    journal afterwards.
    """
    Journal = env["account.journal"].sudo()
    Company = env["res.company"].sudo()
    for company in Company.search([]):
        existing = Journal.search(
            [("company_id", "=", company.id), ("type", "=", "sale")],
            limit=1,
        )
        if existing:
            continue
        _logger.info(
            "REG-C1: seeding Sales journal for company %s (id=%s)",
            company.display_name, company.id,
        )
        Journal.create({
            "name": "Customer Invoices",
            "code": "INV",
            "type": "sale",
            "company_id": company.id,
            "show_on_dashboard": True,
        })
