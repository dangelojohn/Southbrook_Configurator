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
    # Guard: `website` is not a manifest dep of this addon, so on cold
    # installs that don't transitively pull it in (e.g. installing
    # southbrook_estimating standalone, or via a sibling that doesn't
    # bring website) env["website"] raises KeyError. Fall through to
    # the no-logo path; company_details + standard layout still apply.
    Website = (
        env["website"].sudo() if "website" in env.registry.models else None
    )

    standard_layout = env.ref(
        "web.external_layout_standard", raise_if_not_found=False,
    )
    website = Website.search([], limit=1) if Website else False
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


def _backfill_single_value_attribute_defaults(env):
    """Auto-set default_val on every configurable attribute_line that
    has exactly one value option.

    Phase 3 follow-up (2026-06-24): the wizard renders a field per
    attribute_line even when the line has just one option, forcing the
    user to click through a no-choice picker (e.g. "Cabinet Style:
    Base — Base"). OCA's `product.config.session.create()` already
    auto-applies `default_val` to value_ids at session creation, so the
    safest way to skip those clicks is to backfill default_val on every
    single-value line.

    Once default_val is set, a companion view inherit (see
    views/product_configurator_wizard_view.xml) hides the field — but
    ONLY when default_val is set, so a line that never got backfilled
    still renders (never strand the user with no way to submit).

    Idempotent: only writes lines where default_val is currently unset.
    Safe to re-run on every -u. Skips:
      - lines with len(value_ids) != 1
      - lines that already have default_val
      - non-config templates (config_ok = False)
    """
    AttrLine = env["product.template.attribute.line"].sudo()
    lines = AttrLine.search([
        ("default_val", "=", False),
        ("product_tmpl_id.config_ok", "=", True),
    ])
    updated = 0
    for line in lines:
        if len(line.value_ids) != 1:
            continue
        line.default_val = line.value_ids[0].id
        updated += 1
    if updated:
        _logger.info(
            "Backfilled default_val on %s single-value attribute "
            "line(s) — wizard click-through eliminated.", updated,
        )


def post_init_backfill_geometry(env):
    """Task A3 (Materials geometry-writeback plan, 2026-07-24).

    A2 (commit 9458739) only stamps `sb_width_mm`/`sb_height_mm`/
    `sb_depth_mm` etc. onto variants materialised THROUGH the OCA
    configurator wizard (`product.config.session.get_variant_vals`)
    from that commit forward. Every variant that already existed on a
    live database before A2 landed — plus any variant created via a
    path that bypasses `get_variant_vals` (direct `create()`, imports,
    demo data) — is missing real geometry, which starves the Materials
    weight calc.

    Delegates to `product.product._sb_backfill_geometry()`, which is
    idempotent on its own (only ever writes rows where all three dims
    are currently 0), so this hook is safe to run on every `-u` of
    southbrook_estimating, not just the initial `-i`.

    Registered standalone (not folded silently into the resolver logic)
    so it stays independently callable/testable per the A3 brief, but
    chained into `_southbrook_estimating_post_init` below rather than
    claiming a second `post_init_hook` manifest key — Odoo only invokes
    one hook name per module (`odoo/modules/loading.py`:
    `getattr(py_module, post_init)(env)`).
    """
    env["product.product"]._sb_backfill_geometry()


def _southbrook_estimating_post_init(env):
    """Combined post-init hook for southbrook_estimating.

    Chained so adding new idempotent post-install steps is one
    function call here, not a manifest edit. Each step is independent;
    each handles its own idempotency.
    """
    _ensure_sales_journal(env)
    _configure_southbrook_report_branding(env)
    _backfill_single_value_attribute_defaults(env)
    post_init_backfill_geometry(env)
