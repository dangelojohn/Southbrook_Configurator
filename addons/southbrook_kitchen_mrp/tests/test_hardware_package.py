# SPDX-License-Identifier: LGPL-3.0-only
"""sb.hardware.package assembly — wraps the Module 3
southbrook.hardware.catalog.resolve() output into stored lines."""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "kitchen_mrp",
        "hardware_package")
class TestHardwarePackage(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.HardwarePackage = cls.env["sb.hardware.package"]
        cls.Catalog = cls.env["southbrook.hardware.catalog"]
        cls.Product = cls.env["product.product"]

    def _new_mo(self):
        product = self.Product.create({
            "name": "MO test cabinet", "type": "consu", "is_storable": True,
        })
        self.env["mrp.bom"].create({
            "product_tmpl_id": product.product_tmpl_id.id, "product_qty": 1.0,
        })
        return self.env["mrp.production"].create({
            "product_id": product.id, "product_qty": 1.0,
        })

    def test_base_2door_2shelf_assembles_lines(self):
        mo = self._new_mo()
        picks = self.Catalog.resolve(
            cabinet_family="base", door_count=2,
            drawer_count=0, shelf_count=2, soft_close=True,
        )
        package = self.HardwarePackage.create({"mo_id": mo.id})
        self.HardwarePackage.generate_lines_from_resolution(package, picks)

        self.assertEqual(len(package.line_ids), len(picks),
                         "One line per resolved (product, qty) tuple")
        skus = {ln.product_id.x_marathon_sku: ln.qty for ln in package.line_ids}
        self.assertEqual(skus.get("BLM-110-SC"), 4, "4 hinges (2 per door × 2 doors)")
        self.assertEqual(skus.get("MRH-LVL-50"), 4)
        self.assertEqual(skus.get("MRH-SHLFPIN-5MM"), 8, "4 pins × 2 shelves")

    def test_has_pricing_pending_propagates(self):
        """Module 3 seed has every SKU flagged pending — so a freshly-built
        hardware package must report has_pricing_pending=True."""
        mo = self._new_mo()
        picks = self.Catalog.resolve(
            cabinet_family="base", door_count=1, drawer_count=0,
            shelf_count=1, soft_close=True,
        )
        package = self.HardwarePackage.create({"mo_id": mo.id})
        self.HardwarePackage.generate_lines_from_resolution(package, picks)
        self.assertTrue(package.has_pricing_pending)

    def test_zero_qty_lines_skipped(self):
        """Defensive — if a future resolver returns a (product, 0) tuple,
        the package builder must skip it rather than create an empty line."""
        mo = self._new_mo()
        a_product = self.env.ref(
            "southbrook_hardware_catalog.hw_blum_clip_top_blumotion_110"
        )
        picks = [(a_product, 0)]
        package = self.HardwarePackage.create({"mo_id": mo.id})
        self.HardwarePackage.generate_lines_from_resolution(package, picks)
        self.assertEqual(len(package.line_ids), 0)
