# SPDX-License-Identifier: LGPL-3.0-only
"""19.0.1.14.0 — activate the size-aware procurement trigger on the 6 live
sheet components (Fork-1 Option C, T2; see
docs/superpowers/specs/2026-07-27-sizeaware-trigger-design.md and
docs/superpowers/plans/2026-07-27-sizeaware-trigger.md Task 2).

For each of the 6 known `default_code`s below, if the product exists in this
database: apply the native Buy route (`action_sb_set_route_buy`, Phase-2a —
idempotent, (4, id) add) then sync its orderpoint MIN/MAX from open-MO demand
(`action_sb_sync_orderpoints`, T1 — create-or-update by
product/location/company, so re-running this migration or the button is
always idempotent). Products absent from a given database (e.g. this local
test DB, which seeds none of these codes) are skipped and logged — never an
error, never a fabricated activation.

WHY HERE (not data/ or a button-only flow): the sanctioned deploy/migration
path per the cross-module field-order lesson — activation must ship as code,
not a one-off manual click on LIVE, so it replays identically on every
environment this module is installed/upgraded into."""
import logging

_logger = logging.getLogger(__name__)

_SB_SIZEAWARE_TRIGGER_CODES = (
    "RM-MELAMINE_WHITE_5_8",
    "SBK-SHEET-MB34-WW",
    "RM-PLY_3_4",
    "SBK-SHEET-BPY12",
    "SBK-SHEET-BPY14",
    "RM-HARDBOARD_1_4",
)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    Product = env["product.product"]
    activated, skipped = 0, 0
    for code in _SB_SIZEAWARE_TRIGGER_CODES:
        product = Product.search([("default_code", "=", code)], limit=1)
        if not product:
            _logger.info(
                "sb_material_mrp 19.0.1.14.0: default_code %s not found in "
                "this database -- skipping (honesty: no fabricated "
                "activation).", code,
            )
            skipped += 1
            continue
        tmpl = product.product_tmpl_id
        tmpl.action_sb_set_route_buy()
        tmpl.action_sb_sync_orderpoints()
        _logger.info(
            "sb_material_mrp 19.0.1.14.0: activated size-aware trigger on "
            "%s (default_code %s) -- Buy route + orderpoint sync.",
            tmpl.display_name, code,
        )
        activated += 1
    _logger.info(
        "sb_material_mrp 19.0.1.14.0: size-aware trigger activation done -- "
        "%s activated, %s skipped (absent) of %s known codes (from %s).",
        activated, skipped, len(_SB_SIZEAWARE_TRIGGER_CODES), version,
    )
