# SPDX-License-Identifier: LGPL-3.0-only
"""Task A1 — Variant geometry fields + reader on product.product
   Task A2 — populate those fields at OCA variant-creation time

Asserts that geometry writeback fields exist on product.product and that
_sb_geometry_inputs() returns the correct dict for configured variants.

Fields: sb_width_mm, sb_height_mm, sb_depth_mm, sb_panel_family, sb_door_count,
        sb_drawer_count, sb_finished_sides
Method: _sb_geometry_inputs() -> dict or {}

Task A2 adds `product.config.session.get_variant_vals()` override coverage
— a variant created through the OCA configurator wizard flow
(`create_get_variant`) must carry the resolver's geometry (from the
existing `_extract_cabinet_inputs()` on product.config.session, itself
defined in `product_config_line.py`) onto the new `product.product`.
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


@tagged("post_install", "-at_install", "sb_geo")
class TestGeometryWritebackVariantCreation(TransactionCase):
    """Task A2 — geometry lands on the variant at config-session time."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Session = cls.env["product.config.session"]

    def test_variant_created_via_config_gets_geometry(self):
        # base_1dr is a real, locked-Q8 configurable cabinet template
        # (default_code SB-BASE-1DR -> the _SKU_DEFAULTS row in
        # product_config_line.py: family=base, 1 door, 0 drawers,
        # 609x762x609mm). No attribute picks are required for the SKU
        # lookup tier of _extract_cabinet_inputs() to populate dims.
        tmpl = self.env.ref(
            "southbrook_estimating.base_1dr", raise_if_not_found=False)
        if not tmpl:
            self.skipTest("base_1dr template not present")

        # OCA product.config.session has user_id NOT NULL; the
        # default=lambda doesn't always fire under a sudo'd test env
        # (see test_variant_sku_cost.py / test_phase1_smoke.py for the
        # same guard).
        session = self.Session.create({
            "product_tmpl_id": tmpl.id,
            "user_id": self.env.uid,
        })
        variant = session.create_get_variant(session.value_ids.ids)

        self.assertTrue(
            variant.sb_width_mm and variant.sb_height_mm
            and variant.sb_depth_mm,
            "Variant created via create_get_variant must carry non-zero "
            "geometry from _extract_cabinet_inputs()",
        )
        self.assertEqual(variant.sb_width_mm, 609)
        self.assertEqual(variant.sb_height_mm, 762)
        self.assertEqual(variant.sb_depth_mm, 609)
        self.assertEqual(variant.sb_panel_family, "base")
        self.assertEqual(variant.sb_door_count, 1)
        self.assertEqual(variant.sb_drawer_count, 0)

    def test_variant_created_for_non_cabinet_template_does_not_break(self):
        """Non-configurator / plain products must never break variant
        creation even though they have no _extract_cabinet_inputs geometry
        signal — the try/except guard falls back to leaving dims at 0."""
        ProductTemplate = self.env["product.template"]
        Attribute = self.env["product.attribute"]
        Value = self.env["product.attribute.value"]
        AttrLine = self.env["product.template.attribute.line"]

        attr = Attribute.create({
            "name": "TestAttr_A2Plain", "create_variant": "no_variant",
        })
        val = Value.create({"name": "X", "attribute_id": attr.id})
        tmpl = ProductTemplate.create({
            "name": "Plain Non-Cabinet Tmpl",
            "default_code": "TST-A2-PLAIN",
            "config_ok": True,
        })
        AttrLine.create({
            "product_tmpl_id": tmpl.id,
            "attribute_id": attr.id,
            "value_ids": [(6, 0, val.ids)],
        })
        session = self.Session.create({
            "product_tmpl_id": tmpl.id,
            "value_ids": [(6, 0, val.ids)],
            "user_id": self.env.uid,
        })
        # Should not raise even though this template isn't one of the
        # locked Q8 cabinet SKUs.
        variant = session.create_get_variant(value_ids=val.ids)
        self.assertTrue(variant)
