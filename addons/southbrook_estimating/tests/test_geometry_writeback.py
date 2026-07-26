# SPDX-License-Identifier: LGPL-3.0-only
"""Task A1 — Variant geometry fields + reader on product.product

Asserts that geometry writeback fields exist on product.product and that
_sb_geometry_inputs() returns the correct dict for configured variants.

Fields: sb_width_mm, sb_height_mm, sb_depth_mm, sb_panel_family, sb_door_count,
        sb_drawer_count, sb_finished_sides
Method: _sb_geometry_inputs() -> dict or {}
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "sb_geo")
class TestGeometryWriteback(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Product = cls.env["product.product"]
        cls.Tmpl = cls.env["product.template"]

    def test_variant_geometry_fields_and_reader(self):
        """Assert geometry fields exist and reader returns dict for dims > 0."""
        p = self.Product.create({"name": "Cab A"})

        # Assert all geometry fields exist
        for f in ("sb_width_mm", "sb_height_mm", "sb_depth_mm", "sb_panel_family",
                  "sb_door_count", "sb_drawer_count", "sb_finished_sides"):
            self.assertIn(f, p._fields,
                         f"Field {f} not found on product.product")

        # Empty dims -> empty dict
        self.assertEqual(p._sb_geometry_inputs(), {},
                        "All-zero dims should return empty dict")

        # Set dims
        p.write({
            "sb_width_mm": 600,
            "sb_height_mm": 762,
            "sb_depth_mm": 600,
        })

        # Now should return the dict
        result = p._sb_geometry_inputs()
        self.assertEqual(result["width_mm"], 600,
                        "width_mm should match sb_width_mm")
        self.assertEqual(result["height_mm"], 762,
                        "height_mm should match sb_height_mm")
        self.assertEqual(result["depth_mm"], 600,
                        "depth_mm should match sb_depth_mm")
        self.assertEqual(result["family"], "base",
                        "family should default to 'base'")
        self.assertEqual(result["door_count"], 1,
                        "door_count should default to 1")
        self.assertEqual(result["drawer_count"], 0,
                        "drawer_count should default to 0")
        self.assertEqual(result["finished_sides"], "none",
                        "finished_sides should default to 'none'")

    def test_geometry_inputs_with_all_fields_set(self):
        """Assert _sb_geometry_inputs() uses all set fields."""
        p = self.Product.create({
            "name": "Cab B",
            "sb_width_mm": 800,
            "sb_height_mm": 900,
            "sb_depth_mm": 650,
            "sb_panel_family": "contemporary",
            "sb_door_count": 2,
            "sb_drawer_count": 2,
            "sb_finished_sides": "both",
        })

        result = p._sb_geometry_inputs()
        self.assertEqual(result["width_mm"], 800)
        self.assertEqual(result["height_mm"], 900)
        self.assertEqual(result["depth_mm"], 650)
        self.assertEqual(result["family"], "contemporary")
        self.assertEqual(result["door_count"], 2)
        self.assertEqual(result["drawer_count"], 2)
        self.assertEqual(result["finished_sides"], "both")

    def test_geometry_inputs_zero_width_returns_empty(self):
        """Zero width should return empty dict even if height/depth set."""
        p = self.Product.create({
            "name": "Cab C",
            "sb_width_mm": 0,
            "sb_height_mm": 762,
            "sb_depth_mm": 600,
        })
        self.assertEqual(p._sb_geometry_inputs(), {})

    def test_geometry_inputs_zero_height_returns_empty(self):
        """Zero height should return empty dict even if width/depth set."""
        p = self.Product.create({
            "name": "Cab D",
            "sb_width_mm": 600,
            "sb_height_mm": 0,
            "sb_depth_mm": 600,
        })
        self.assertEqual(p._sb_geometry_inputs(), {})

    def test_geometry_inputs_zero_depth_returns_empty(self):
        """Zero depth should return empty dict even if width/height set."""
        p = self.Product.create({
            "name": "Cab E",
            "sb_width_mm": 600,
            "sb_height_mm": 762,
            "sb_depth_mm": 0,
        })
        self.assertEqual(p._sb_geometry_inputs(), {})

    def test_field_defaults(self):
        """Assert field defaults are applied correctly."""
        p = self.Product.create({
            "name": "Cab F",
            "sb_width_mm": 600,
            "sb_height_mm": 762,
            "sb_depth_mm": 600,
        })

        self.assertEqual(p.sb_panel_family, "base")
        self.assertEqual(p.sb_door_count, 1)
        self.assertEqual(p.sb_drawer_count, 0)
        self.assertEqual(p.sb_finished_sides, "none")
