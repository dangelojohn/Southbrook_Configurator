# SPDX-License-Identifier: LGPL-3.0-only
"""Seed integrity — every brand, every SKU, every supplier-info link
present and well-formed after a clean install."""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "hardware_catalog", "seed")
class TestSeedIntegrity(TransactionCase):

    def test_all_21_brands_present(self):
        """Module ships 21 brand records — the original 19 from the
        Marathon workbook plus DTC and King Slide added 2026-06-10
        after auditing marathonhardware.com."""
        Brand = self.env["southbrook.hardware.brand"]
        self.assertEqual(
            Brand.search_count([]), 21,
            "Expected 21 brand records, got a different count",
        )

    def test_marathon_aligned_additions_present(self):
        """2026-06-10 — verify the two Marathon-aligned brand
        additions (DTC + King Slide) are present by xml_id so a
        future drop / rename surfaces as a test failure."""
        for xml_id in ("brand_dtc", "brand_king_slide"):
            brand = self.env.ref(
                f"southbrook_hardware_catalog.{xml_id}")
            self.assertTrue(
                brand.active,
                f"{xml_id} should be active by default")

    def test_seed_sku_count_at_least_29(self):
        """Path A SKU additions 2026-06-10 brought the seed catalog
        to 29 hardware SKUs. Locks the floor — adding more is fine,
        silent drops are not."""
        Product = self.env["product.product"]
        n = Product.search_count([("x_hardware_category", "!=", False)])
        self.assertGreaterEqual(
            n, 29,
            f"Expected at least 29 hardware SKUs, got {n}")

    def test_marathon_aligned_sku_additions_present(self):
        """2026-06-10 Path A — spot-check that each new category
        addition (DTC hinge, King Slide undermount, multi-finish pull,
        appliance pull, hinge accessory) has a representative SKU
        with the right brand attached."""
        cases = [
            ("hw_dtc_c80_110_sc", "brand_dtc"),
            ("hw_king_slide_k2832_21", "brand_king_slide"),
            ("hw_handle_pull_128_mb", "brand_top_knobs"),
            ("hw_handle_app_pull_18_bn", "brand_top_knobs"),
            ("hw_blum_clip_mounting_plate", "brand_blum"),
        ]
        for sku_ref, brand_ref in cases:
            product = self.env.ref(
                f"southbrook_hardware_catalog.{sku_ref}")
            expected_brand = self.env.ref(
                f"southbrook_hardware_catalog.{brand_ref}")
            self.assertEqual(
                product.x_hardware_brand_id, expected_brand,
                f"{sku_ref} brand drifted from {brand_ref}")
            self.assertTrue(
                product.x_marathon_sku,
                f"{sku_ref} missing x_marathon_sku")

    def test_brand_codes_unique_and_lowercased(self):
        Brand = self.env["southbrook.hardware.brand"]
        codes = Brand.search([]).mapped("code")
        self.assertEqual(len(codes), len(set(codes)), "brand codes not unique")
        for code in codes:
            self.assertEqual(code, code.lower(), f"brand code not lowercase: {code}")

    def test_marathon_vendor_present(self):
        partner = self.env.ref(
            "southbrook_hardware_catalog.partner_marathon_hardware"
        )
        self.assertTrue(partner.is_company)
        self.assertEqual(partner.supplier_rank, 1)
        self.assertEqual(partner.name, "Marathon Hardware")

    def test_every_seed_sku_has_a_brand_and_marathon_sku(self):
        Product = self.env["product.product"]
        hardware = Product.search([("x_hardware_category", "!=", False)])
        self.assertGreater(
            len(hardware), 0,
            "No hardware-category products were seeded",
        )
        for p in hardware:
            self.assertTrue(
                p.x_marathon_sku,
                f"Hardware SKU {p.display_name} missing x_marathon_sku",
            )
            self.assertTrue(
                p.x_hardware_brand_id,
                f"Hardware SKU {p.display_name} missing brand",
            )

    def test_all_categories_covered_by_seed(self):
        """Every selection value in HARDWARE_CATEGORIES must have at
        least one seeded SKU — guards against a future selection-list
        expansion silently leaving a category empty."""
        Product = self.env["product.product"]
        from odoo.addons.southbrook_hardware_catalog.models.product_product import (
            HARDWARE_CATEGORIES,
        )
        for category_key, label in HARDWARE_CATEGORIES:
            with self.subTest(category=category_key):
                count = Product.search_count([
                    ("x_hardware_category", "=", category_key),
                ])
                self.assertGreater(
                    count, 0,
                    f"Category '{label}' has no seeded SKUs",
                )

    def test_marathon_supplierinfo_links(self):
        """A representative subset of seeded SKUs ship with vendor links."""
        for ref_name in (
            "hw_blum_clip_top_blumotion_110",
            "hw_blum_movento_450",
            "hw_shelf_pin_5mm",
            "hw_leveler_50mm",
        ):
            product = self.env.ref(f"southbrook_hardware_catalog.{ref_name}")
            self.assertTrue(
                product.seller_ids,
                f"{ref_name} has no product.supplierinfo records",
            )
            seller = product.seller_ids[0]
            self.assertEqual(
                seller.partner_id.name, "Marathon Hardware",
                f"{ref_name} not linked to Marathon",
            )
