# SPDX-License-Identifier: LGPL-3.0-only
"""19.0.1.14.1 — make the Buy route product-selectable.

Live finding (2026-07-27): `purchase_stock.route_warehouse0_buy` had
`product_selectable=False` on prod. Odoo 19 applies the `route_ids` field
domain to READS, so the 1.14.0 migration's route link — present in the
`stock_route_product` rel table — was invisible to the ORM and therefore to
native procurement: the size-aware trigger stayed dead despite the link.
Standard Odoo default is True. Setting it True makes the existing links
visible (proven live: route_ids [] -> [6] on flip). Idempotent.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    buy = env.ref("purchase_stock.route_warehouse0_buy", raise_if_not_found=False)
    if not buy:
        _logger.warning("1.14.1: Buy route missing; skipping.")
        return
    if not buy.product_selectable:
        buy.product_selectable = True
        _logger.info("1.14.1: Buy route product_selectable set True.")
    else:
        _logger.info("1.14.1: Buy route already product_selectable; no-op.")
