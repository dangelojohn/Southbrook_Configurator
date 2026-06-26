# SPDX-License-Identifier: LGPL-3.0-only
"""Backfill required Hinge Side attribute on 4 door-bearing bases.

Audit 2026-06-26 against southbrook prod: four base templates expose
Door Count (so they can be configured with 1 door) but have no Hinge
Side attribute line — meaning a single-door variant cannot be wired
to a swing direction.

  - Sink Base · Single Bowl
  - Sink Base · Double Bowl
  - Cooktop Base
  - Microwave Drawer Base

Adds the Hinge Side attribute with values LH (Left Hand), RH (Right
Hand), and N/A. Idempotent — skips templates that already have the
attribute line.

The companion JS render at 19.0.1.7.0 will read Hinge Side to flip
the door handle to the proper edge when Door Count=1.
"""
import logging

from odoo import SUPERUSER_ID, api


_logger = logging.getLogger(__name__)


TARGET_TEMPLATE_NAMES = [
    "Sink Base · Single Bowl",
    "Sink Base · Double Bowl",
    "Cooktop Base",
    "Microwave Drawer Base",
]


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    Template = env["product.template"]
    AttrLine = env["product.template.attribute.line"]

    hinge_attr = env.ref(
        "southbrook_estimating.attr_hinge_side",
        raise_if_not_found=False,
    )
    if not hinge_attr:
        _logger.warning(
            "Hinge Side attribute xml_id missing — skipping backfill.")
        return

    val_lh = env.ref(
        "southbrook_estimating.value_hinge_left",
        raise_if_not_found=False,
    )
    val_rh = env.ref(
        "southbrook_estimating.value_hinge_right",
        raise_if_not_found=False,
    )
    val_na = env.ref(
        "southbrook_estimating.value_hinge_na",
        raise_if_not_found=False,
    )
    value_ids = [v.id for v in (val_lh, val_rh, val_na) if v]
    if len(value_ids) < 2:
        _logger.warning(
            "Hinge Side values missing — skipping backfill.")
        return

    backfilled = 0
    already_present = 0
    not_found = []
    for tmpl_name in TARGET_TEMPLATE_NAMES:
        tmpl = Template.search([("name", "=", tmpl_name)], limit=1)
        if not tmpl:
            not_found.append(tmpl_name)
            continue
        existing = AttrLine.search([
            ("product_tmpl_id", "=", tmpl.id),
            ("attribute_id", "=", hinge_attr.id),
        ], limit=1)
        if existing:
            already_present += 1
            continue
        AttrLine.create({
            "product_tmpl_id": tmpl.id,
            "attribute_id": hinge_attr.id,
            "value_ids": [(6, 0, value_ids)],
        })
        backfilled += 1
        _logger.info(
            "Backfilled Hinge Side on template '%s' with values "
            "LH/RH/N/A.", tmpl_name)

    _logger.info(
        "southbrook_configurator_ux 19.0.1.7.0 Hinge Side backfill: "
        "%s updated, %s already present, %s not found.",
        backfilled, already_present, len(not_found),
    )
    if not_found:
        _logger.warning("Templates not found by name: %s",
                        ", ".join(not_found))
