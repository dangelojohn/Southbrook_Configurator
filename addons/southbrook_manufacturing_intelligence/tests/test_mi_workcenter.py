# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestManufacturingIntelligenceWorkcenter(TransactionCase):
    def _create_production(self, name):
        Product = self.env["product.product"]
        product_values = {"name": name}
        if "detailed_type" in Product._fields:
            product_values["detailed_type"] = "consu"
        elif "type" in Product._fields:
            product_values["type"] = "consu"
        product = Product.create(product_values)
        bom = self.env["mrp.bom"].create(
            {
                "product_tmpl_id": product.product_tmpl_id.id,
                "product_qty": 1.0,
                "product_uom_id": product.uom_id.id,
                "type": "normal",
            }
        )
        return self.env["mrp.production"].create(
            {
                "product_id": product.id,
                "product_uom_id": product.uom_id.id,
                "product_qty": 1.0,
                "bom_id": bom.id,
            }
        )

    def test_workcenter_counts_mi_blockers_and_warnings(self):
        workcenter = self.env["mrp.workcenter"].create(
            {"name": "MI Review Station"}
        )
        blocked = self._create_production("Blocked MI Cabinet")
        review = self._create_production("Review MI Cabinet")
        self.env["mrp.workorder"].create(
            {
                "name": "Blocked Work",
                "workcenter_id": workcenter.id,
                "production_id": blocked.id,
            }
        )
        self.env["mrp.workorder"].create(
            {
                "name": "Review Work",
                "workcenter_id": workcenter.id,
                "production_id": review.id,
            }
        )
        blocked.write(
            {
                "x_mi_status": "blocked",
                "x_mi_blocker_count": 1,
                "x_mi_warning_count": 1,
            }
        )
        review.write(
            {
                "x_mi_status": "review",
                "x_mi_blocker_count": 0,
                "x_mi_warning_count": 2,
            }
        )

        workcenter._compute_southbrook_mi_kpis()

        self.assertEqual(workcenter.x_mi_workcenter_blocker_count, 1)
        self.assertEqual(workcenter.x_mi_workcenter_warning_count, 3)
