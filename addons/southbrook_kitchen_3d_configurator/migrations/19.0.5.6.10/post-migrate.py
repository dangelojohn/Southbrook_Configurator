# -*- coding: utf-8 -*-
"""Ensure Manufacture route on all southbrook_is_cabinet product.product
variants.

Supersedes 19.0.5.6.9/post-migrate.py which wrote to product.template.route_ids —
in Odoo v19 stock module, route_ids is defined on product.product (variant),
not product.template. The template-level write silently no-ops.

Fires on 5.6.9 -> 5.6.10 upgrade. Idempotent — checks each variant.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    mfg = env.ref("mrp.route_warehouse0_manufacture", raise_if_not_found=False)
    if not mfg:
        _logger.warning(
            "5.6.10 post-migrate: mrp.route_warehouse0_manufacture xmlid "
            "not found — skipping. Ensure mrp is installed.")
        return
    Tmpl = env["product.template"]
    if "southbrook_is_cabinet" not in Tmpl._fields:
        _logger.warning(
            "5.6.10 post-migrate: southbrook_is_cabinet field not on "
            "product.template — skipping.")
        return
    templates = Tmpl.search([("southbrook_is_cabinet", "=", True)])
    variant_count = 0
    patched = 0
    for t in templates:
        for variant in t.product_variant_ids:
            variant_count += 1
            if mfg.id not in variant.route_ids.ids:
                variant.write({"route_ids": [(4, mfg.id)]})
                patched += 1
    _logger.info(
        "5.6.10 post-migrate: examined %d templates / %d variants, "
        "wrote Manufacture route to %d variants that lacked it.",
        len(templates), variant_count, patched)
