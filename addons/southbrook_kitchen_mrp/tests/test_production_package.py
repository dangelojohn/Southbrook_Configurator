# SPDX-License-Identifier: LGPL-3.0-only
"""sb.production.package — DoD test: an MO produces a complete cutlist +
hardware package via generate_from_mo()."""
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "kitchen_mrp",
        "production_package", "dod")
class TestProductionPackage(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ProductionPackage = cls.env["sb.production.package"]
        cls.Product = cls.env["product.product"]

    def _new_mo(self):
        product = self.Product.create({
            "name": "Module 4 DoD cabinet", "type": "consu", "is_storable": True,
        })
        self.env["mrp.bom"].create({
            "product_tmpl_id": product.product_tmpl_id.id, "product_qty": 1.0,
        })
        return self.env["mrp.production"].create({
            "product_id": product.id, "product_qty": 1.0,
        })

    # ------------------------------------------------------------------
    # DoD — an MO produces a complete cutlist + hardware package
    # ------------------------------------------------------------------
    def test_dod_base_cabinet_produces_complete_package(self):
        mo = self._new_mo()
        package = self.ProductionPackage.generate_from_mo(
            mo, width_mm=600, height_mm=720, depth_mm=580,
            cabinet_family="base", door_count=2, drawer_count=0,
            soft_close=True,
        )
        self.assertTrue(package.exists())
        self.assertEqual(package.mo_id, mo)
        self.assertEqual(package.state, "ready")

        # Cutlist is complete: 7 panel-line types for a 2-door 2-shelf base.
        self.assertTrue(package.cutlist_id)
        cutlist_panels = set(package.cutlist_id.line_ids.mapped("panel_name"))
        self.assertEqual(cutlist_panels, {
            "side_L", "side_R", "top", "bottom", "back",
            "adjustable_shelf", "door",
        })

        # Hardware package is complete: at least the soft-close hinge.
        self.assertTrue(package.hardware_package_id)
        hardware_skus = set(
            package.hardware_package_id.line_ids.mapped("product_id.x_marathon_sku")
        )
        self.assertIn("BLM-110-SC", hardware_skus,
                      "Soft-close hinge must be in the resolved hardware pack")

    def test_idempotent_regenerate(self):
        """Calling generate_from_mo twice replaces the prior package
        rather than creating duplicates — required so an ECO that
        retriggers the orchestration doesn't accumulate ghost packages."""
        mo = self._new_mo()
        first = self.ProductionPackage.generate_from_mo(
            mo, 600, 720, 580, "base", 2, 0,
        )
        second = self.ProductionPackage.generate_from_mo(
            mo, 600, 720, 580, "base", 2, 0,
        )
        # The first is gone — its id should not resolve.
        self.assertFalse(first.exists())
        self.assertTrue(second.exists())
        # The MO has exactly one production package.
        self.assertEqual(
            self.ProductionPackage.search_count([("mo_id", "=", mo.id)]),
            1,
        )

    def test_no_duplicate_packages_per_mo_constraint(self):
        """SQL constraint: one production package per MO."""
        mo = self._new_mo()
        self.ProductionPackage.generate_from_mo(
            mo, 600, 720, 580, "base", 1, 0,
        )
        # Trying to create a second one outside of generate_from_mo's
        # idempotent path must hit the unique constraint.
        with self.assertRaises(Exception):
            self.ProductionPackage.create({"mo_id": mo.id})

    def test_missing_mo_argument_raises(self):
        with self.assertRaises(UserError):
            self.ProductionPackage.generate_from_mo(
                None, 600, 720, 580, "base", 1, 0,
            )

    def test_drawer_bank_no_door_hardware_resolves_slides(self):
        """A drawer bank with 3 drawers must NOT have a door cutlist line
        (door_count=0 → shared.southbrook_dims.door() returns None) but
        MUST resolve to drawer slides in the hardware package.

        Note: shared.southbrook_dims.shelf_count() is height-only and does
        not know about cabinet families, so a drawer bank's cutlist still
        carries the adjustable_shelf line. Family-aware shelf suppression
        is a future layer (Module 5/7 workspace rules), not a shared/
        formula change — G2 keeps the signed-off geometry stable."""
        mo = self._new_mo()
        package = self.ProductionPackage.generate_from_mo(
            mo, width_mm=600, height_mm=720, depth_mm=580,
            cabinet_family="drawer", door_count=0, drawer_count=3,
            soft_close=True,
        )
        cutlist_panels = set(package.cutlist_id.line_ids.mapped("panel_name"))
        self.assertNotIn("door", cutlist_panels,
                         "Drawer bank: no door in cutlist (door_count=0)")

        hardware_skus = set(
            package.hardware_package_id.line_ids.mapped("product_id.x_marathon_sku")
        )
        self.assertIn("BLM-MOV-450", hardware_skus, "Drawer slides resolved")
        # 3 drawer slides + 3 handles, but NO door hinges.
        self.assertNotIn("BLM-110-SC", hardware_skus,
                         "Drawer bank must NOT have door hinges")

    def test_pricing_pending_propagates_through_to_production_package(self):
        mo = self._new_mo()
        package = self.ProductionPackage.generate_from_mo(
            mo, 600, 720, 580, "base", 1, 0,
        )
        self.assertTrue(package.has_pricing_pending,
                        "Until the trade-account workbook lands, every "
                        "production package must surface pending pricing")
