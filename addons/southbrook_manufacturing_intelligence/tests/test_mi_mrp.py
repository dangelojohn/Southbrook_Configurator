# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestManufacturingIntelligenceMrp(TransactionCase):
    def _create_production(self):
        product_values = {"name": "MI Test Cabinet"}
        if "detailed_type" in self.env["product.product"]._fields:
            product_values["detailed_type"] = "consu"
        elif "type" in self.env["product.product"]._fields:
            product_values["type"] = "consu"
        product = self.env["product.product"].create(product_values)
        bom = self.env["mrp.bom"].create(
            {
                "product_tmpl_id": product.product_tmpl_id.id,
                "product_qty": 1.0,
                "product_uom_id": product.uom_id.id,
                "type": "normal",
            }
        )
        production = self.env["mrp.production"].create(
            {
                "product_id": product.id,
                "product_uom_id": product.uom_id.id,
                "product_qty": 1.0,
                "bom_id": bom.id,
            }
        )
        return product, production

    def test_mo_recompute_missing_cutlist_and_cad(self):
        _product, production = self._create_production()
        if "x_cad_status" in production._fields:
            production.x_cad_status = "pending"
        production.action_recompute_manufacturing_intelligence()
        self.assertEqual(production.x_mi_status, "blocked")
        self.assertGreaterEqual(production.x_mi_blocker_count, 1)
        self.assertIn("cutlist", (production.x_mi_next_action or "").lower())
        if "x_cad_status" in production._fields:
            self.assertTrue(
                production.x_mi_check_ids.filtered(
                    lambda check: check.category == "cad"
                    and check.severity == "warning"
                )
            )

    def test_package_recompute_with_cutlist(self):
        _product, production = self._create_production()
        cutlist = self.env["sb.cutlist"].create(
            {
                "name": "MI Test Cutlist",
                "mo_id": production.id,
                "state": "draft",
            }
        )
        self.env["sb.cutlist.line"].create(
            {
                "cutlist_id": cutlist.id,
                "sequence": 10,
                "panel_name": "side_L",
                "qty": 2,
                "length_mm": 700,
                "width_mm": 600,
                "thickness_mm": 19,
                "substrate": "melamine_white_5_8",
                "grain_dir": "with_grain",
                "edge_banding_config": '{"front": true}',
            }
        )
        package = self.env["sb.production.package"].create(
            {
                "name": "MI Test Package",
                "mo_id": production.id,
                "cutlist_id": cutlist.id,
            }
        )
        package.action_recompute_manufacturing_intelligence()
        self.assertGreater(package.x_mi_yield_pct, 0)
        self.assertAlmostEqual(package.x_mi_edge_band_m, 1.4)

    def test_package_recompute_writes_stage_rollups(self):
        product_values = {"name": "MI Rollup Product"}
        if "detailed_type" in self.env["product.product"]._fields:
            product_values["detailed_type"] = "consu"
        elif "type" in self.env["product.product"]._fields:
            product_values["type"] = "consu"
        product = self.env["product.product"].create(product_values)
        mo = self.env["mrp.production"].create(
            {
                "product_id": product.id,
                "product_uom_id": product.uom_id.id,
                "product_qty": 1,
            }
        )
        cutlist = self.env["sb.cutlist"].create({"mo_id": mo.id})
        self.env["sb.cutlist.line"].create(
            {
                "cutlist_id": cutlist.id,
                "panel_name": "side_L",
                "qty": 1,
                "length_mm": 3000,
                "width_mm": 1300,
                "thickness_mm": 19,
                "substrate": "melamine_white_5_8",
                "grain_dir": "with_grain",
            }
        )
        package = self.env["sb.production.package"].create(
            {
                "mo_id": mo.id,
                "cutlist_id": cutlist.id,
            }
        )
        package.action_recompute_manufacturing_intelligence()
        self.assertEqual(package.x_mi_blocked_stage, "saw")
        self.assertIn("Split the part", package.x_mi_next_stage_action)
        self.assertEqual(package.x_mi_saw_blocker_count, 1)
