# SPDX-License-Identifier: LGPL-3.0-only
"""Backfill the four southbrook_* catalog metadata fields on the 12 Q8
cabinets when upgrading an existing database to 19.0.1.1.0.

Why a migration script in addition to the data/cabinet_catalog_metadata.xml
seed:

  - Fresh installs go through `__manifest__.py` -> data files: the seed
    XML populates the four fields at install time. Migrations don't
    run on fresh installs.

  - Existing installs (e.g. the live QNAP southbrook stack which is
    already on 19.0.1.0.0) reach 19.0.1.1.0 via `-u southbrook_estimating`.
    Odoo loads the new data files via the same code path, BUT — because
    every record already exists from the prior install — fields that
    AREN'T mentioned in the new XML stay untouched, and any record
    where the seed XML row exactly matches an existing field value is
    a no-op. So the seed file does work on upgrade too, in theory.

  - This script is the defence-in-depth: if anyone tampers with the
    seed XML (e.g. comments out a record while testing) or the data
    file mis-loads for any reason, the post-migrate hook still
    guarantees the 12 cabinets carry the metadata, keyed by
    default_code (SKU) — which is the stable lookup key.

  - It only writes fields that are currently NULL on the cabinet, so
    it never overwrites a value that an operator has changed via the
    backend form view.

Per Odoo's migration convention (odoo/openupgrade docs):
  - Script name: post-migrate.py runs AFTER the data files load.
  - Signature: migrate(cr, version).
  - cr is a database cursor; version is the prior version string.
"""
import logging

_logger = logging.getLogger(__name__)

# SKU -> (category, description, dimensions, icon_key). Keyed on
# default_code so a partial-data-corruption case (xml_id missing,
# default_code intact) still backfills.
_CATALOG_METADATA = {
    "SB-WALL-1DR": (
        "Wall",
        "Single-door upper cabinet for above-counter storage.",
        '15"W × 30"H × 12"D',
        "wall1",
    ),
    "SB-WALL-2DR": (
        "Wall",
        "Double-door upper cabinet, wide-span storage.",
        '30"W × 30"H × 12"D',
        "wall2",
    ),
    "SB-BASE-1DR": (
        "Base",
        "Single-door floor cabinet with adjustable shelf.",
        '18"W × 34½"H × 24"D',
        "base1",
    ),
    "SB-BASE-2DR": (
        "Base",
        "Double-door floor cabinet, generous lower storage.",
        '36"W × 34½"H × 24"D',
        "base2",
    ),
    "SB-DRAWER": (
        "Drawer",
        "Stacked drawer bank for utensils & cookware.",
        '18"W × 34½"H × 24"D',
        "drawer",
    ),
    "SB-SINK-BASE": (
        "Base",
        "Open base sized to host an undermount sink.",
        '36"W × 34½"H × 24"D',
        "sink",
    ),
    "SB-TALL-PANTRY": (
        "Tall",
        "Full-height pantry with multiple shelves.",
        '24"W × 84"H × 24"D',
        "pantry",
    ),
    "SB-TALL-OVEN": (
        "Tall",
        "Tall housing engineered for a built-in oven.",
        '30"W × 84"H × 24"D',
        "oven",
    ),
    "SB-CORNER": (
        "Base",
        "Corner unit with rotating carousel access.",
        '36" × 36" × 34½"H',
        "corner",
    ),
    "SB-VANITY": (
        "Vanity",
        "Bathroom vanity base with sink cutout.",
        '30"W × 32"H × 21"D',
        "vanity",
    ),
    "SB-ACCESSORY": (
        "Extras",
        "Add-on hardware, trim & filler pieces.",
        "Varies",
        "extra",
    ),
    "SB-WORKTOP": (
        "Extras",
        "Cut-to-size worktop / countertop surface.",
        "Per linear ft",
        "worktop",
    ),
}


def migrate(cr, version):
    """Backfill southbrook_* metadata on the 12 cabinets by SKU.

    Only writes a field if the current value is NULL/empty — operator
    edits via the backend form view are preserved across upgrades.

    Uses the ORM (not direct SQL) because southbrook_description is
    declared with translate=True, which in Odoo 19 means the underlying
    Postgres column is `jsonb` (a lang_code → value map) rather than
    varchar. Direct `UPDATE ... SET southbrook_description = 'text'`
    fails with `invalid input syntax for type json` and the registry
    rolls the entire migration transaction back. The ORM `.write()`
    path wraps the value as `{"<active lang>": "text"}` JSON correctly.
    """
    if not version:
        # Fresh install path — data/cabinet_catalog_metadata.xml will
        # populate via the standard data-load. Nothing for us to do.
        return

    # Lazy import: keep the module load light at import time and
    # only resolve api / SUPERUSER_ID when actually migrating.
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    Template = env["product.template"]

    backfilled = 0
    skipped = 0
    missing = []
    for sku, (category, description, dimensions, icon_key) in (
        _CATALOG_METADATA.items()
    ):
        tmpl = Template.search([("default_code", "=", sku)], limit=1)
        if not tmpl:
            missing.append(sku)
            continue

        updates = {}
        if not tmpl.southbrook_category:
            updates["southbrook_category"] = category
        if not tmpl.southbrook_description:
            updates["southbrook_description"] = description
        if not tmpl.southbrook_dimensions:
            updates["southbrook_dimensions"] = dimensions
        if not tmpl.southbrook_icon_key:
            updates["southbrook_icon_key"] = icon_key

        if not updates:
            skipped += 1
            continue

        tmpl.write(updates)
        backfilled += 1

    _logger.info(
        "southbrook_estimating 19.0.1.1.0 migration: backfilled "
        "%d cabinets, skipped %d (already populated), missing %d "
        "(SKU not present in product_template: %s)",
        backfilled, skipped, len(missing), missing,
    )
