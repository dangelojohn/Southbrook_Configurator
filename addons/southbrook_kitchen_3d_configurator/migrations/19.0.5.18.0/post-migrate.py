# -*- coding: utf-8 -*-
"""PR3.0 — y/z field-semantics migration for wall-mounted cabinets.

Lead decision (2026-07-12, see docs/superpowers/plans/
2026-07-12-pr3.0-yz-semantics-migration.md): y_position_in becomes the
canonical mount-height/elevation field; z_position_in returns to its
COORDINATE_CONTRACT.md meaning (depth / plan-Z). Prior to this migration
both persistence writers (controllers/main.py::_layout_item and
kitchen_configurator.js::_addCabinetFromProduct) stored a wall cabinet's
mount-height number into z_position_in with y_position_in hardcoded 0 —
the "z-as-height" convention the coordinate-contract matrix
(docs/2026-07-12-pr3-coordinate-contract-matrix.md) flags as the riskiest
finding blocking PR3.1's renderer-dispatch unification.

Verified live (read-only SELECT against the southbrook prod DB,
2026-07-12) before writing this migration:

  southbrook_kitchen_design_line, grouped by cabinet_type:
    base   118 rows — y=0, z=0 (unaffected; base cabinets are floor-flush)
    filler  91 rows — y=0, z=0 (unaffected)
    tall     2 rows — y=0, z=0 (floor-standing; NOT the legacy mount-
                                 height shape, correctly excluded by the
                                 z>=30 discriminator)
    wall    83 rows — y=0, z in [54, 66]  <- 83/83 match the legacy shape

  ZERO 'panel' or 'corner' rows exist in prod today. The matrix's
  buildOtherCabinet/buildEndCapPanel builders share the same z-as-height
  *read* as wall_cabinet.esm.js, but there is currently no persisted data
  of those cabinet_types to migrate — the builder-read fix (this PR's
  step 3) is forward-looking for when such rows start being saved.

  sale_order_line (sb_layout_* mirror, millimetres, reconcile.py writes
  these from the design line's y/z_position_in * 25.4):
    wall-*   1/1 row matches the mirrored legacy shape
             (sb_layout_y_mm=0, sb_layout_z_mm=1371.6 ~= 54in)
    base-*, filler-*, and one unrelated non-cabinet prefix ('L785')
             all y=0, z=0 — unaffected.
    ZERO 'panel-*'/'corner-*' rows.

Scope is therefore cabinet_type='wall' only for the design-line table,
and sb_layout_key prefix 'wall-' only for the sale-order mirror — the
exact set the verified live data supports. Both statements are
idempotent: after migrating, z_position_in/sb_layout_z_mm is 0, so the
`z >= 30 / z_mm >= 762` discriminator no longer matches those rows on a
re-run.

Fires on 5.17.0 -> 5.18.0 upgrade.
"""
import logging

_logger = logging.getLogger(__name__)

# Inches; matches controllers/main.py's D8 industry-minimum wall-cab
# mount height (34.5" base + 1.5" counter + 18" clearance = 54"). Any
# real mount height is well above this, so 30in is a safe, generous
# floor for "this z value is actually a height", with zero overlap
# against the 0" depth-flush convention floor-standing cabinets use.
_LEGACY_Z_MIN_IN = 30
_LEGACY_Z_MIN_MM = 762  # 30in * 25.4mm/in


def migrate(cr, version):
    _migrate_design_lines(cr)
    _migrate_sale_order_line_mirror(cr)


def _table_exists(cr, table):
    cr.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name=%s",
        (table,),
    )
    return bool(cr.fetchone())


def _column_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name=%s AND column_name=%s",
        (table, column),
    )
    return bool(cr.fetchone())


def _migrate_design_lines(cr):
    if not _table_exists(cr, "southbrook_kitchen_design_line"):
        _logger.warning(
            "5.18.0 post-migrate: southbrook_kitchen_design_line table "
            "not found — skipping design-line y/z migration.")
        return
    cr.execute(
        """
        UPDATE southbrook_kitchen_design_line
           SET y_position_in = z_position_in,
               z_position_in = 0
         WHERE cabinet_type = 'wall'
           AND COALESCE(y_position_in, 0) = 0
           AND z_position_in >= %s
        """,
        (_LEGACY_Z_MIN_IN,),
    )
    _logger.info(
        "5.18.0 post-migrate: migrated %d southbrook_kitchen_design_line "
        "wall row(s) from z-as-height to y-as-height "
        "(y_position_in <- z_position_in, z_position_in -> 0).",
        cr.rowcount,
    )


def _migrate_sale_order_line_mirror(cr):
    if not _table_exists(cr, "sale_order_line") or not _column_exists(
        cr, "sale_order_line", "sb_layout_y_mm"
    ):
        _logger.warning(
            "5.18.0 post-migrate: sale_order_line.sb_layout_y_mm column "
            "not found — skipping sale-order mirror y/z migration.")
        return
    cr.execute(
        """
        UPDATE sale_order_line
           SET sb_layout_y_mm = sb_layout_z_mm,
               sb_layout_z_mm = 0
         WHERE left(sb_layout_key, 5) = 'wall-'
           AND COALESCE(sb_layout_y_mm, 0) = 0
           AND sb_layout_z_mm >= %s
        """,
        (_LEGACY_Z_MIN_MM,),
    )
    _logger.info(
        "5.18.0 post-migrate: migrated %d sale_order_line wall-mirror "
        "row(s) from z-as-height(mm) to y-as-height(mm) "
        "(sb_layout_y_mm <- sb_layout_z_mm, sb_layout_z_mm -> 0).",
        cr.rowcount,
    )
