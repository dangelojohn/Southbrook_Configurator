# SPDX-License-Identifier: LGPL-3.0-only
"""product.template / product.product extension fields — onchange
applies category defaults, search filter works, and the form's
'is tool' toggle drives the conditional tab visibility (verified
via the underlying field state)."""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "kitchen_tools",
        "product_ext")
class TestProductExtensions(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Product = cls.env["product.template"]
        cls.cat_saw_blades = cls.env.ref(
            "southbrook_mrp_kitchen_tools.cat_saw_blades")
        cls.cat_adhesives = cls.env.ref(
            "southbrook_mrp_kitchen_tools.cat_adhesives")
        cls.cat_screws = cls.env.ref(
            "southbrook_mrp_kitchen_tools.cat_screws")

    # ──────────────────────────────────────────────────────────────────
    # The big field surface exists on product.template
    # ──────────────────────────────────────────────────────────────────
    def test_all_classification_fields_exist(self):
        for f in (
            "x_southbrook_is_tool",
            "x_southbrook_is_consumable_tool",
            "x_southbrook_is_reusable_tool",
            "x_southbrook_is_indirect_tool",
            "x_southbrook_is_maintenance_supply",
            "x_southbrook_tool_category_id",
            "x_southbrook_tool_family",
            "x_southbrook_directness",
            "x_southbrook_tool_lifecycle_state",
        ):
            self.assertIn(f, self.Product._fields,
                          f"Missing classification field {f}")

    def test_all_geometry_fields_exist(self):
        for f in (
            "x_southbrook_cutting_diameter_mm",
            "x_southbrook_shank_diameter_mm",
            "x_southbrook_tooth_count",
            "x_southbrook_blade_diameter_mm",
            "x_southbrook_kerf_width_mm",
            "x_southbrook_rotation_speed_max",
            "x_southbrook_feed_rate_max",
        ):
            self.assertIn(f, self.Product._fields)

    def test_all_chemical_fields_exist(self):
        for f in (
            "x_southbrook_glue_type",
            "x_southbrook_open_time_min",
            "x_southbrook_cure_time_min",
            "x_southbrook_shelf_life_days",
            "x_southbrook_expiry_required",
            "x_southbrook_hazardous",
            "x_southbrook_msds_required",
            "x_southbrook_flammable",
        ):
            self.assertIn(f, self.Product._fields)

    def test_all_replenishment_fields_exist(self):
        for f in (
            "x_southbrook_preferred_vendor_id",
            "x_southbrook_vendor_sku",
            "x_southbrook_min_stock_qty",
            "x_southbrook_max_stock_qty",
            "x_southbrook_reorder_multiple",
            "x_southbrook_issue_uom_id",
            "x_southbrook_estimated_life_qty",
            "x_southbrook_estimated_life_unit",
            "x_southbrook_sharpening_interval_qty",
            "x_southbrook_calibration_interval_days",
        ):
            self.assertIn(f, self.Product._fields)

    # ──────────────────────────────────────────────────────────────────
    # Picking the saw blade category seeds reusable + sharpening defaults
    # ──────────────────────────────────────────────────────────────────
    def test_onchange_category_seeds_reusable_tool(self):
        product = self.Product.new({"name": "Test blade"})
        product.x_southbrook_tool_category_id = self.cat_saw_blades
        product._onchange_tool_category()
        self.assertTrue(product.x_southbrook_is_tool)
        self.assertTrue(product.x_southbrook_is_reusable_tool)
        self.assertFalse(product.x_southbrook_is_consumable_tool)
        self.assertEqual(product.x_southbrook_tool_family, "saw_blade")
        self.assertEqual(
            product.x_southbrook_directness, "direct_production_tool",
        )

    def test_onchange_category_seeds_consumable_screw(self):
        product = self.Product.new({"name": "Test screw"})
        product.x_southbrook_tool_category_id = self.cat_screws
        product._onchange_tool_category()
        self.assertTrue(product.x_southbrook_is_tool)
        self.assertTrue(product.x_southbrook_is_consumable_tool)
        self.assertFalse(product.x_southbrook_is_reusable_tool)
        self.assertEqual(product.x_southbrook_directness, "direct_consumable")

    def test_onchange_category_seeds_expiry_for_adhesive(self):
        product = self.Product.new({"name": "Test glue"})
        product.x_southbrook_tool_category_id = self.cat_adhesives
        product._onchange_tool_category()
        self.assertTrue(product.x_southbrook_expiry_required)
        self.assertTrue(product.x_southbrook_hazardous)
        self.assertTrue(product.x_southbrook_msds_required)

    # ──────────────────────────────────────────────────────────────────
    # Persist + read back round-trip
    # ──────────────────────────────────────────────────────────────────
    def test_save_and_search_finds_tool(self):
        product = self.Product.create({
            "name": "Persisted tool",
            "x_southbrook_is_tool": True,
            "x_southbrook_tool_category_id": self.cat_saw_blades.id,
            "x_southbrook_tool_family": "saw_blade",
            "x_southbrook_directness": "direct_production_tool",
            "x_southbrook_is_reusable_tool": True,
            "x_southbrook_blade_diameter_mm": 305.0,
            "x_southbrook_tooth_count": 96,
        })
        found = self.Product.search([
            ("x_southbrook_is_tool", "=", True),
            ("x_southbrook_tool_family", "=", "saw_blade"),
            ("x_southbrook_tooth_count", "=", 96),
        ])
        self.assertIn(product, found)

    def test_product_count_on_category(self):
        self.Product.create({
            "name": "Count test blade",
            "x_southbrook_is_tool": True,
            "x_southbrook_tool_category_id": self.cat_saw_blades.id,
        })
        # _compute_product_count is not stored; force a read.
        self.cat_saw_blades.invalidate_recordset(
            ["product_count"])
        self.assertGreaterEqual(self.cat_saw_blades.product_count, 1)
