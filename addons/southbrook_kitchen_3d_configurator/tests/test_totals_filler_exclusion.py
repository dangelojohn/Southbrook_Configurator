# SPDX-License-Identifier: LGPL-3.0-only
"""Task 6 (kitchen templates) — total_cabinets excludes fillers.

A filler strip is not a cabinet: quoting '7 cabinets' when two of them
are 3" filler panels misstates the kitchen to customer AND shop. New
contract: total_cabinets counts cabinet_type != 'filler'; filler_count
carries the strips separately; estimated_price still includes fillers
(they are real BOM-reaching lines).
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook",
        "southbrook_kitchen_3d_configurator", "kitchen_templates")
class TestTotalsFillerExclusion(TransactionCase):

    def _design_with_lines(self):
        design = self.env["southbrook.kitchen.design"].create(
            {"name": "T6 totals", "room_width_in": 120.0})
        base = self.env.ref(
            "southbrook_kitchen_3d_configurator.product_tmpl_b24"
        ).product_variant_id
        filler = self.env.ref(
            "southbrook_kitchen_3d_configurator.product_tmpl_fp3"
        ).product_variant_id
        Line = self.env["southbrook.kitchen.design.line"]
        for seq, (p, ct) in enumerate(
                [(base, "base"), (base, "base"), (filler, "filler")]):
            Line.create({
                "design_id": design.id, "sequence": seq * 10,
                "product_id": p.id, "quantity": 1,
                "price_unit": p.lst_price,
                "cabinet_type": ct, "width_in": 24.0, "height_in": 34.5,
                "depth_in": 24.0, "origin": "configurator"})
        return design

    def test_fillers_excluded_from_total_but_counted(self):
        design = self._design_with_lines()
        self.assertEqual(design.total_cabinets, 2,
                         "fillers must not count as cabinets")
        self.assertEqual(design.filler_count, 1)

    def test_price_still_includes_fillers(self):
        design = self._design_with_lines()
        filler_price = self.env.ref(
            "southbrook_kitchen_3d_configurator.product_tmpl_fp3"
        ).product_variant_id.lst_price
        self.assertGreater(filler_price, 0.0)
        total = sum(design.cabinet_line_ids.mapped(
            lambda l: l.quantity * l.price_unit))
        self.assertEqual(design.estimated_price, total,
                         "price keeps filler lines — they reach the BOM")
