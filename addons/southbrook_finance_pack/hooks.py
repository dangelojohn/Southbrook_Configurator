# SPDX-License-Identifier: LGPL-3.0-only
"""Post-install hook: activate the Canadian Chart of Accounts.

``post_init_hook`` runs ONLY on first install (``-i``), never on ``-u`` (see
project memory note ``southbrook_spec_sheet_invoice_v19_4_4_0``); migrations
should be used for re-runs. Best-effort: if l10n_ca is already loaded or the
template-load API has moved, swallow and log so the install never breaks.
"""

import logging

_logger = logging.getLogger(__name__)


def post_init_activate_l10n_ca(env):
    """Best-effort installer for the Canadian CoA on the main company.

    Odoo 19 invokes ``post_init_hook`` with a single positional argument
    (``env``); the legacy ``cr, registry`` signature was dropped. See
    https://github.com/odoo/odoo/blob/19.0/odoo/modules/loading.py.
    """
    try:
        company = env.ref("base.main_company", raise_if_not_found=False)
        if not company:
            company = env["res.company"].search([], limit=1)
        if not company:
            _logger.warning(
                "southbrook_finance_pack: no res.company found, "
                "skipping l10n_ca activation"
            )
            return

        # Skip when a chart of accounts is already loaded for this company:
        # account.account is empty until a template is materialised.
        existing = env["account.account"].search_count(
            [("company_id", "=", company.id)]
        )
        if existing:
            _logger.info(
                "southbrook_finance_pack: company %s already has %d accounts, "
                "skipping l10n_ca chart template load",
                company.name,
                existing,
            )
            return

        # The ChartTemplate API surface has been renamed across recent v18/v19
        # rolling releases; probe and call whichever exists.
        Tpl = env["account.chart.template"]
        # Odoo 19 (and late v18): try_loading(template_code, company)
        if hasattr(Tpl, "try_loading"):
            Tpl.try_loading("ca", company=company, install_demo=False)
            _logger.info(
                "southbrook_finance_pack: loaded l10n_ca chart on %s via try_loading",
                company.name,
            )
            return
        if hasattr(Tpl, "_load"):
            Tpl._load("ca", company)
            _logger.info(
                "southbrook_finance_pack: loaded l10n_ca chart on %s via _load",
                company.name,
            )
            return
        _logger.warning(
            "southbrook_finance_pack: no recognised loader on account.chart.template; "
            "user must load the CoA manually from Accounting Settings"
        )
    except Exception as exc:  # pylint: disable=broad-except
        # Never block install — the addon is useful even without the CoA.
        _logger.warning(
            "southbrook_finance_pack: l10n_ca activation skipped: %s", exc
        )
