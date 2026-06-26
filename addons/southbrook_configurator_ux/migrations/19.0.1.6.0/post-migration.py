# SPDX-License-Identifier: LGPL-3.0-only
"""Backfill the Door Count attribute on the 3 Corner Base templates.

Audited 2026-06-26 against southbrook prod (v19.0-20260504): three
base-cabinet templates that have doors were missing the Door Count
attribute line, so the configurator could not capture the
single-vs-double choice:

  - Corner Base · Blind
  - Corner Base · Diagonal
  - Corner Base · Lazy-Susan

The companion JS-side fix in configurator.esm.js 19.0.1.5.0 papered
over the gap by inferring door count from width — but that doesn't
drive BOM / SKU composition. This migration is the durable backfill.

Why a migration script (not data XML)?
The 3 templates were created without external IDs, so a
``<record id="...">`` reference is impossible. Migration scripts
search by name and call ORM directly. Idempotent — re-running is a
no-op (existing attribute lines are detected and left alone).

Why no per-template default?
Width and series drive the actual door count downstream; the
Door Count attribute is captured but doesn't pre-pick a value. The
customer (or the website UX width-default rule) picks 1 vs 2.
"""
import logging

from odoo import SUPERUSER_ID, api


_logger = logging.getLogger(__name__)


# Templates audited as having doors but missing the Door Count attribute.
TARGET_TEMPLATE_NAMES = [
    "Corner Base · Blind",
    "Corner Base · Diagonal",
    "Corner Base · Lazy-Susan",
]


def migrate(cr, version):
    # Odoo migration scripts get a bare cursor — build an Environment
    # for ORM access. SUPERUSER bypasses security so the backfill
    # can write to product.template.attribute.line regardless of who
    # triggers the -u.
    env = api.Environment(cr, SUPERUSER_ID, {})

    Template = env["product.template"]
    AttrLine = env["product.template.attribute.line"]

    # Resolve Door Count attribute + values via the stable xml_ids in
    # southbrook_estimating. Raise loudly if the seed is missing —
    # we should fail fast rather than create a half-wired line.
    door_count_attr = env.ref(
        "southbrook_estimating.attr_door_count",
        raise_if_not_found=False,
    )
    if not door_count_attr:
        _logger.warning(
            "southbrook_configurator_ux 19.0.1.6.0: Door Count "
            "attribute xml_id not found — skipping backfill. "
            "Ensure southbrook_estimating is installed at version "
            "that ships attr_door_count."
        )
        return

    value_one = env.ref(
        "southbrook_estimating.value_door_count_1",
        raise_if_not_found=False,
    )
    value_two = env.ref(
        "southbrook_estimating.value_door_count_2",
        raise_if_not_found=False,
    )
    if not value_one or not value_two:
        _logger.warning(
            "Door Count value(s) missing — skipping backfill.")
        return

    backfilled = 0
    already_present = 0
    not_found = []
    for tmpl_name in TARGET_TEMPLATE_NAMES:
        tmpl = Template.search(
            [("name", "=", tmpl_name)], limit=1)
        if not tmpl:
            not_found.append(tmpl_name)
            continue
        existing = AttrLine.search([
            ("product_tmpl_id", "=", tmpl.id),
            ("attribute_id", "=", door_count_attr.id),
        ], limit=1)
        if existing:
            already_present += 1
            continue
        AttrLine.create({
            "product_tmpl_id": tmpl.id,
            "attribute_id": door_count_attr.id,
            "value_ids": [(6, 0, [value_one.id, value_two.id])],
        })
        backfilled += 1
        _logger.info(
            "Backfilled Door Count attribute on template '%s' "
            "with values 1 and 2.", tmpl_name)

    _logger.info(
        "southbrook_configurator_ux 19.0.1.6.0 backfill done: "
        "%s template(s) updated, %s already had the attribute, "
        "%s not found.",
        backfilled, already_present, len(not_found),
    )
    if not_found:
        _logger.warning(
            "Could not find these templates by name: %s",
            ", ".join(not_found),
        )
