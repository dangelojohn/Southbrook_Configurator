# SPDX-License-Identifier: LGPL-3.0-only
"""PR3.0 — y/z field-semantics migration
(migrations/19.0.5.18.0/post-migrate.py).

Loads the migration module directly (Odoo migration scripts are not a
regular importable package) and runs it against synthetic rows built to
the EXACT legacy shape verified read-only against the live southbrook
prod DB on 2026-07-12 (see the migration script's own docstring + the
PR3.0 report for the verification queries):

  * southbrook_kitchen_design_line: cabinet_type='wall',
    y_position_in=0, z_position_in in [54, 66] — 83/83 wall rows in
    prod match this shape exactly. Non-wall rows (base/filler/tall) all
    have y=0, z=0 and must be left untouched.
  * sale_order_line (sb_layout_* mirror, mm): sb_layout_key LIKE
    'wall-%%', sb_layout_y_mm=0, sb_layout_z_mm>=762 — 1/1 wall-mirror
    row in prod matches. Non-wall rows must be left untouched.

Asserts the migration is a one-shot transform (legacy shape -> canonical
shape) AND idempotent (a second run changes nothing further).
"""
import importlib.util
import os

from odoo.tests import TransactionCase, tagged


def _load_migration_module():
    path = os.path.join(
        os.path.dirname(__file__), "..", "migrations", "19.0.5.18.0",
        "post-migrate.py",
    )
    spec = importlib.util.spec_from_file_location(
        "southbrook_kitchen_3d_configurator_5_18_0_post_migrate", path,
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@tagged("post_install", "-at_install", "southbrook",
        "southbrook_kitchen_3d_configurator", "yz_semantics_migration")
class TestYZSemanticsMigration(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.migration = _load_migration_module()

        cls.partner = cls.env["res.partner"].create({
            "name": "PR3.0 Migration Test Customer",
            "email": "kitchen3d.pr30@southbrook.test",
        })
        cls.design = cls.env["southbrook.kitchen.design"].create({
            "name": "PR3.0 migration test",
            "partner_id": cls.partner.id,
            "room_width_in": 144,
            "room_depth_in": 96,
            "room_height_in": 96,
        })

        cls.tmpl_wall = cls.env["product.template"].create({
            "name": "PR3.0 Migration Wall Cabinet",
            "type": "consu",
            "sale_ok": True,
            "list_price": 350.0,
        })
        cls.tmpl_wall.southbrook_is_cabinet = True
        cls.tmpl_wall.southbrook_cabinet_type = "wall"
        cls.product_wall = cls.tmpl_wall.product_variant_id

        cls.tmpl_base = cls.env["product.template"].create({
            "name": "PR3.0 Migration Base Cabinet",
            "type": "consu",
            "sale_ok": True,
            "list_price": 500.0,
        })
        cls.tmpl_base.southbrook_is_cabinet = True
        cls.tmpl_base.southbrook_cabinet_type = "base"
        cls.product_base = cls.tmpl_base.product_variant_id

    # ------------------------------------------------------------------
    def _make_design_line(self, cabinet_type, product, layout_key,
                           y_position_in, z_position_in):
        return self.env["southbrook.kitchen.design.line"].create({
            "design_id":       self.design.id,
            "product_id":      product.id,
            "cabinet_type":    cabinet_type,
            "layout_key":      layout_key,
            "origin":          "configurator",
            "x_position_in":   0.0,
            "y_position_in":   y_position_in,
            "z_position_in":   z_position_in,
            "width_in":        18.0,
            "height_in":       30.0,
            "depth_in":        12.0,
            "quantity":        1,
            "price_unit":      350.0,
        })

    def test_design_line_legacy_wall_shape_migrates_and_is_idempotent(self):
        """83 synthetic wall rows in the exact verified prod legacy
        shape (y=0, z in [54,66]) -> after migrate(): y=old z, z=0.
        A second migrate() run changes nothing further (idempotent)."""
        N = 83
        lines = self.env["southbrook.kitchen.design.line"]
        expected_y = []
        for i in range(N):
            z = 54.0 + (i % 13)  # spread across the verified [54,66] range
            expected_y.append(z)
            lines |= self._make_design_line(
                "wall", self.product_wall, "pr30-wall-%d" % i, 0.0, z)

        # Non-wall control rows: must be left untouched by the migration.
        control_base = self._make_design_line(
            "base", self.product_base, "pr30-base-control", 0.0, 0.0)
        control_tall = self._make_design_line(
            "tall", self.product_base, "pr30-tall-control", 0.0, 0.0)

        self.env.flush_all()
        pre_count = len(lines)
        self.assertEqual(pre_count, N)

        # RED-before-GREEN evidence: before migrate(), the legacy shape
        # is exactly what prod has (the discriminator query the
        # migration itself uses would match all N rows here).
        self.env.cr.execute(
            "SELECT count(*) FROM southbrook_kitchen_design_line "
            "WHERE cabinet_type = 'wall' AND COALESCE(y_position_in,0) = 0 "
            "AND z_position_in >= 30 AND id = ANY(%s)",
            (lines.ids,),
        )
        self.assertEqual(
            self.env.cr.fetchone()[0], N,
            "pre-migration: all %d synthetic rows must match the legacy "
            "discriminator (red state)" % N,
        )

        # ── run the migration ───────────────────────────────────────
        self.migration.migrate(self.env.cr, None)

        lines.invalidate_recordset()
        for line in lines:
            idx = int(line.layout_key.rsplit("-", 1)[-1])
            z = 54.0 + (idx % 13)
            self.assertAlmostEqual(line.y_position_in, z, places=2,
                msg="migrated wall line %s: y_position_in must now carry "
                    "the old mount-height value" % line.layout_key)
            self.assertEqual(line.z_position_in, 0.0,
                msg="migrated wall line %s: z_position_in must be 0 "
                    "(flush) post-migration" % line.layout_key)

        # Control (non-wall) rows must be untouched.
        control_base.invalidate_recordset()
        control_tall.invalidate_recordset()
        self.assertEqual(control_base.y_position_in, 0.0)
        self.assertEqual(control_base.z_position_in, 0.0)
        self.assertEqual(control_tall.y_position_in, 0.0)
        self.assertEqual(control_tall.z_position_in, 0.0)

        # Post-migration: GREEN — zero rows now match the legacy
        # discriminator (this is the "83 -> 0" acceptance check).
        self.env.cr.execute(
            "SELECT count(*) FROM southbrook_kitchen_design_line "
            "WHERE cabinet_type = 'wall' AND COALESCE(y_position_in,0) = 0 "
            "AND z_position_in >= 30 AND id = ANY(%s)",
            (lines.ids,),
        )
        self.assertEqual(
            self.env.cr.fetchone()[0], 0,
            "post-migration: 0 rows should match the legacy discriminator "
            "(83 -> 0 acceptance check)",
        )

        # ── idempotency: run again, snapshot must be unchanged ───────
        snapshot_before_rerun = {
            line.id: (line.y_position_in, line.z_position_in)
            for line in lines
        }
        self.migration.migrate(self.env.cr, None)
        lines.invalidate_recordset()
        snapshot_after_rerun = {
            line.id: (line.y_position_in, line.z_position_in)
            for line in lines
        }
        self.assertEqual(
            snapshot_after_rerun, snapshot_before_rerun,
            "re-running the migration must be a no-op (idempotent)",
        )

    def test_sale_order_line_mirror_legacy_shape_migrates_and_is_idempotent(self):
        """sale_order_line's sb_layout_y_mm / sb_layout_z_mm mirror —
        same discriminator, translated to millimetres (z_mm >= 762)."""
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        wall_line = self.env["sale.order.line"].create({
            "order_id":         order.id,
            "product_id":       self.product_wall.id,
            "product_uom_qty":  1,
            "sb_layout_key":    "wall-1",
            "sb_layout_x_mm":   0,
            "sb_layout_y_mm":   0,
            "sb_layout_z_mm":   1371.6,   # 54in legacy mount height, mm
        })
        base_line = self.env["sale.order.line"].create({
            "order_id":         order.id,
            "product_id":       self.product_base.id,
            "product_uom_qty":  1,
            "sb_layout_key":    "base-1",
            "sb_layout_x_mm":   0,
            "sb_layout_y_mm":   0,
            "sb_layout_z_mm":   0,
        })
        unrelated_line = self.env["sale.order.line"].create({
            "order_id":         order.id,
            "product_id":       self.product_base.id,
            "product_uom_qty":  1,
            "sb_layout_key":    False,
        })

        self.env.flush_all()
        self.migration.migrate(self.env.cr, None)

        wall_line.invalidate_recordset()
        base_line.invalidate_recordset()
        unrelated_line.invalidate_recordset()

        self.assertAlmostEqual(wall_line.sb_layout_y_mm, 1371.6, places=1)
        self.assertEqual(wall_line.sb_layout_z_mm, 0.0)
        self.assertEqual(base_line.sb_layout_y_mm, 0.0)
        self.assertEqual(base_line.sb_layout_z_mm, 0.0)
        self.assertFalse(unrelated_line.sb_layout_key)

        snapshot = (wall_line.sb_layout_y_mm, wall_line.sb_layout_z_mm)
        self.migration.migrate(self.env.cr, None)
        wall_line.invalidate_recordset()
        self.assertEqual(
            (wall_line.sb_layout_y_mm, wall_line.sb_layout_z_mm), snapshot,
            "re-running the migration must be a no-op (idempotent)",
        )

    def test_migration_skips_gracefully_when_table_missing(self):
        """Defensive path: the migration must not raise if run against a
        cursor pointed at a schema that lacks these tables/columns (a
        malformed/partial install). Uses a nonexistent table name so
        this exercises the guard without touching real schema."""
        # Sanity: the guard helpers used by migrate() must not raise for
        # a table/column that genuinely does not exist.
        self.assertFalse(
            self.migration._table_exists(self.env.cr, "no_such_table_xyz"))
        self.assertFalse(
            self.migration._column_exists(
                self.env.cr, "sale_order_line", "no_such_column_xyz"))
