# -*- coding: utf-8 -*-
"""C1 fix — repair rows minted under the zone-default keystone bug.

`southbrook.kitchen.design.line.zone` declared BOTH `default="base_run"`
AND `compute="_compute_zone"`, where the compute is guarded by
`if not line.zone: ...` (only backfill on empty — preserves user
overrides). Because the default was truthy at create() time, Odoo never
ran the compute for a brand-new line: every wall/tall/filler/panel
cabinet ever created through the normal `create()` path silently
persisted zone='base_run' regardless of cabinet_type.

Downstream, the pure `kitchen_layout_engine` reads `zone` to pick a
cabinet's elevation (wall zone -> 1400mm mount height) and which
along-wall run-cursor it advances (wall cabinets get their OWN cursor,
independent of the base-run cursor). A mis-zoned upper therefore landed
on the FLOOR of a side wall and queued BEHIND that wall's base run in a
single shared cursor, overflowing the wall and tripping
LayoutCapacityExceeded on action_auto_arrange for any L-shaped kitchen.

This migration repairs existing rows using the SAME
`_ZONE_FROM_CABINET_TYPE` mapping table the (now-fixed) compute uses
(models/kitchen_design.py, module scope, ~line 1713):

    base   -> base_run   (already correct; never touched)
    wall   -> wall
    tall   -> tall
    corner -> base_run   (already correct; dominant case — never touched,
                          per the fix instructions: corner rows are a
                          user-override surface, not a blind mapping)
    filler -> accessory
    panel  -> accessory

Only rows still sitting at the field's old truthy default ('base_run')
are touched — a user who deliberately zoned a wall cabinet 'base_run'
(e.g. an island upper) on purpose would have had to explicitly override
it away from that same value, so this migration cannot distinguish that
case from the bug and, per instructions, does not attempt to; it only
corrects wall/tall/filler/panel rows, and explicitly leaves base/corner
rows untouched.

Fires on 5.19.0 -> 5.20.0 upgrade.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not _table_exists(cr, "southbrook_kitchen_design_line"):
        _logger.warning(
            "5.20.0 post-migration: southbrook_kitchen_design_line table "
            "not found — skipping zone backfill.")
        return

    cr.execute(
        """
        UPDATE southbrook_kitchen_design_line
           SET zone = 'wall'
         WHERE cabinet_type = 'wall'
           AND zone = 'base_run'
        """
    )
    _logger.info(
        "5.20.0 post-migration: repaired %d wall-type "
        "southbrook_kitchen_design_line row(s) mis-zoned 'base_run' "
        "-> 'wall'.", cr.rowcount,
    )

    cr.execute(
        """
        UPDATE southbrook_kitchen_design_line
           SET zone = 'tall'
         WHERE cabinet_type = 'tall'
           AND zone = 'base_run'
        """
    )
    _logger.info(
        "5.20.0 post-migration: repaired %d tall-type "
        "southbrook_kitchen_design_line row(s) mis-zoned 'base_run' "
        "-> 'tall'.", cr.rowcount,
    )

    cr.execute(
        """
        UPDATE southbrook_kitchen_design_line
           SET zone = 'accessory'
         WHERE cabinet_type IN ('filler', 'panel')
           AND zone = 'base_run'
        """
    )
    _logger.info(
        "5.20.0 post-migration: repaired %d filler/panel "
        "southbrook_kitchen_design_line row(s) mis-zoned 'base_run' "
        "-> 'accessory'.", cr.rowcount,
    )

    # corner and base rows are DELIBERATELY left untouched — 'base_run'
    # is the dominant-case-correct mapping for corner, and it always was
    # for base. See module docstring above.


def _table_exists(cr, table):
    cr.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name=%s",
        (table,),
    )
    return bool(cr.fetchone())
