# SPDX-License-Identifier: LGPL-3.0-only
import logging

from . import models
from . import controllers

_logger = logging.getLogger(__name__)


_SOUTHBROOK_COMPANY_DETAILS = (
    "<span>Southbrook Cabinetry</span><br/>"
    "<span>info@southbrookcabinetry.space</span><br/>"
    "<span>southbrookcabinetry.space</span>"
)


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


def _configure_southbrook_report_branding(env):
    """Configure res.company so PDF reports show the real Southbrook
    branding instead of Odoo's "Your logo" placeholder.

    Set per company, idempotently (only writes fields that drifted):
      - external_report_layout_id  → web.external_layout_standard
      - logo                       → copy of website.logo (the real
                                      "southbrook CABINETRY" wordmark)
      - company_details            → name + info@ + website (HTML)

    Deliberately does NOT fabricate street/phone/zip: no real address
    exists. The standard layout guards those fields with t-if so they
    silently omit when unset.

    Safe to re-run: each field is only written when it differs from the
    target, so this is a no-op on a correctly-configured DB.
    """
    Company = env["res.company"].sudo()
    Website = env["website"].sudo()

    standard_layout = env.ref(
        "web.external_layout_standard", raise_if_not_found=False,
    )
    website = Website.search([], limit=1)
    web_logo = website.logo if website else False

    for company in Company.search([]):
        updates = {}
        if standard_layout and company.external_report_layout_id != standard_layout:
            updates["external_report_layout_id"] = standard_layout.id
        if web_logo and company.logo != web_logo:
            updates["logo"] = web_logo
        if company.company_details != _SOUTHBROOK_COMPANY_DETAILS:
            updates["company_details"] = _SOUTHBROOK_COMPANY_DETAILS
        if updates:
            _logger.info(
                "Southbrook branding: updating %s on company %s (id=%s)",
                sorted(updates.keys()), company.display_name, company.id,
            )
            company.write(updates)


def _southbrook_estimating_post_init(env):
    """Combined post-init hook for southbrook_estimating.

    Chained so adding new idempotent post-install steps is one
    function call here, not a manifest edit. Each step is independent;
    each handles its own idempotency.
    """
    _ensure_sales_journal(env)
    _configure_southbrook_report_branding(env)
