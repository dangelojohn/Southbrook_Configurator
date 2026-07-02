# -*- coding: utf-8 -*-
"""Ensure Manufacture route on all southbrook_is_cabinet templates.

Background: 5.6.5 introduced canonical_catalog_routes.xml with
noupdate="1" so runtime edits survive -u. Consequence: existing
installs that upgrade from 5.6.4 or earlier NEVER receive the seed
because Odoo's XML loader skips noupdate records on -u.

The 5.6.5 defense-in-depth in kitchen_design._ensure_kitchen_bom
patches this at quote time, but a template that never sees a quote
click stays without the route. This one-shot post-migrate closes
the gap idempotently.

Runs once on 5.6.8 -> 5.6.9 upgrade. Idempotent — write only if the
route isn't already linked. Skips cleanly if mrp isn't installed
(shouldn't happen, but defensive).
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    mfg = env.ref("mrp.route_warehouse0_manufacture", raise_if_not_found=False)
    if not mfg:
        _logger.warning(
            "5.6.9 post-migrate: mrp.route_warehouse0_manufacture "
            "xmlid not found — skipping. Ensure mrp is installed.")
        return
    Tmpl = env["product.template"]
    if "southbrook_is_cabinet" not in Tmpl._fields:
        _logger.warning(
            "5.6.9 post-migrate: southbrook_is_cabinet field not on "
            "product.template — skipping.")
        return
    cabinets = Tmpl.search([("southbrook_is_cabinet", "=", True)])
    patched = 0
    for t in cabinets:
        if mfg.id not in t.route_ids.ids:
            t.write({"route_ids": [(4, mfg.id)]})
            patched += 1
    _logger.info(
        "5.6.9 post-migrate: examined %d southbrook_is_cabinet templates, "
        "wrote Manufacture route to %d that lacked it.",
        len(cabinets), patched)
