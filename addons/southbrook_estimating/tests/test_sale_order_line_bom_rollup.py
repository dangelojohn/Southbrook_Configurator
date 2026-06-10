# SPDX-License-Identifier: LGPL-3.0-only
"""Phase 3 Sprint B2 — per-line live BoM rollup tests.

Guards the computed sb_panel_count / sb_door_count / sb_width_mm
fields on sale.order.line, plus the _sb_derive_dimensions helper
that powers them.

Why this matters: PHASE_2_TRACK_2_GATE.md line 53 calls out four
demo-data limitations (zero panel rollup, empty spec text, zero
width, missing MAPLE badge). The first three share a root cause —
demo variants are created bare without a product.config.session,
so attribute values like width and family can't be read off the
variant. This test suite is what guarantees option (b)'s parser
fallback works end-to-end without depending on a configurator
session.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "phase_3", "bom_rollup")
class TestSaleOrderLineBomRollup(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        partner = cls.env["res.partner"].create({"name": "BoM Rollup Test"})
        product = cls.env["product.product"].create({
            "name": "Test bare cabinet",
            "type": "consu", "is_storable": True,
        })
        cls.order = cls.env["sale.order"].create({
            "partner_id": partner.id,
            "order_line": [(0, 0, {
                "product_id": product.id,
                "name": "Base 2-Door · Contemporary · Maple · 30\" · "
                        "Soft-close",
                "product_uom_qty": 1,
            })],
        })
        cls.line = cls.order.order_line[0]

    # ------------------------------------------------------------------
    # _sb_derive_dimensions helper
    # ------------------------------------------------------------------
    def test_derive_parses_width_inches_from_line_name(self):
        dims = self.line._sb_derive_dimensions()
        # 30 inch = 762 mm exactly.
        self.assertAlmostEqual(dims["width_mm"], 762.0, places=1)

    def test_derive_parses_family_base_from_line_name(self):
        dims = self.line._sb_derive_dimensions()
        self.assertEqual(dims["family"], "base")

    def test_derive_parses_door_count_two_from_line_name(self):
        dims = self.line._sb_derive_dimensions()
        self.assertEqual(dims["door_count"], 2)

    def test_derive_wall_family_picks_wall_defaults(self):
        self.line.name = "Wall 1-Door · 18\""
        dims = self.line._sb_derive_dimensions()
        self.assertEqual(dims["family"], "wall")
        self.assertEqual(dims["depth_mm"], 310.0)
        self.assertEqual(dims["height_mm"], 760.0)

    def test_derive_tall_family_picks_tall_defaults(self):
        self.line.name = "Tall Pantry · Elegance · Walnut · 24\""
        dims = self.line._sb_derive_dimensions()
        self.assertEqual(dims["family"], "tall")
        self.assertEqual(dims["height_mm"], 2100.0)
        self.assertEqual(dims["depth_mm"], 600.0)

    def test_derive_unknown_name_falls_back_to_base_default(self):
        self.line.name = "Some opaque description"
        dims = self.line._sb_derive_dimensions()
        self.assertEqual(dims["family"], "base")
        self.assertEqual(dims["width_mm"], 600.0)
        self.assertEqual(dims["door_count"], 1)

    # ------------------------------------------------------------------
    # sb_panel_count + sb_door_count + sb_width_mm computed fields
    # ------------------------------------------------------------------
    def test_panel_count_positive_for_base_2dr_30in(self):
        self.assertGreater(
            self.line.sb_panel_count, 0,
            "Live-computed BoM rollup must produce nonzero panel "
            "count for demo-seed variant. Sprint B2 contract.",
        )

    def test_door_count_two_for_2dr_line(self):
        self.assertEqual(self.line.sb_door_count, 2)

    def test_width_mm_30in_resolves_to_762(self):
        self.assertAlmostEqual(self.line.sb_width_mm, 762.0, places=1)

    def test_panel_count_scales_with_qty(self):
        self.line.product_uom_qty = 2
        # Recompute is automatic via @api.depends.
        single_qty_value = self.line.sb_panel_count
        self.line.product_uom_qty = 3
        triple_qty_value = self.line.sb_panel_count
        # qty 3 should be 1.5x of qty 2 (same underlying cabinet,
        # multiplied by the new qty).
        self.assertEqual(triple_qty_value, int(single_qty_value * 1.5))
