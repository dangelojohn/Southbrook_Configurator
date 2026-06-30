# SPDX-License-Identifier: LGPL-3.0-only
"""T2 — Door-area m² computed field on product.product.

Asserts the computed field returns expected door-face areas for known
configurations:
  - 600mm wide × 720mm tall × 1 door  -> 0.42 m²  (roughly)
  - 600mm wide × 720mm tall × 2 doors -> ~0.42 m² combined
  - Drawer bank (no doors) -> 0.0
  - No picks -> 0.0
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "estimating", "t2",
        "door_area")
class TestT2DoorArea(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Product = cls.env["product.product"]
        cls.Tmpl = cls.env["product.template"]
        cls.Attribute = cls.env["product.attribute"]
        cls.AttributeValue = cls.env["product.attribute.value"]
        cls.TmplAttrLine = cls.env["product.template.attribute.line"]

    def _attr(self, name, values):
        a = self.Attribute.create({"name": name, "create_variant": "always"})
        return a, [
            self.AttributeValue.create({"name": v, "attribute_id": a.id})
            for v in values
        ]

    def _make_variant(self, attrs_map, category="Base"):
        tmpl = self.Tmpl.create({
            "name": f"T2 test cabinet ({category})",
            "type": "consu", "is_storable": True,
            "southbrook_category": category,
        })
        for attr_name, value_names in attrs_map.items():
            attr, vals = self._attr(attr_name, value_names)
            self.TmplAttrLine.create({
                "product_tmpl_id": tmpl.id,
                "attribute_id": attr.id,
                "value_ids": [(6, 0, [v.id for v in vals])],
            })
        tmpl._create_variant_ids()
        return tmpl.product_variant_id

    # ------------------------------------------------------------------
    # Acceptance — 600 × 720, 1 door
    # ------------------------------------------------------------------
    def test_600x720_single_door(self):
        variant = self._make_variant({
            "Width": ["600 mm"],
            "Door Count": ["1"],
        })
        # door_width = 600 - 6 = 594; door_height = 720 - 6 = 714
        # area = 594 * 714 / 1e6 = 0.424116 m²
        self.assertAlmostEqual(variant.x_door_area_m2, 0.4241, delta=0.001)

    # ------------------------------------------------------------------
    # Acceptance — 600 × 720, 2 doors
    # ------------------------------------------------------------------
    def test_600x720_double_door(self):
        variant = self._make_variant({
            "Width": ["600 mm"],
            "Door Count": ["2"],
        })
        # door_width = (600 - 9)/2 = 295.5; door_height = 714; qty 2
        # area = 2 * 295.5 * 714 / 1e6 = 0.4220...
        self.assertAlmostEqual(variant.x_door_area_m2, 0.4220, delta=0.001)

    # ------------------------------------------------------------------
    # Acceptance — Drawer bank has zero door area
    # ------------------------------------------------------------------
    def test_drawer_bank_zero_door_area(self):
        variant = self._make_variant({
            "Width": ["600 mm"],
            "Drawer Construction": ["3-Drawer Stack (Dovetail)"],
        })
        self.assertEqual(variant.x_door_area_m2, 0.0,
                         "drawer banks have no door faces")

    # ------------------------------------------------------------------
    # Acceptance — class-default height (Tall) used when Height unset
    # ------------------------------------------------------------------
    def test_tall_cabinet_uses_class_default_height(self):
        variant = self._make_variant({
            "Width": ["600 mm"],
            "Door Count": ["1"],
        }, category="Tall")
        # door_height = 1970 - 6 = 1964; door_width = 594; area ≈ 1.167
        self.assertAlmostEqual(variant.x_door_area_m2, 1.167, delta=0.005)

    # ------------------------------------------------------------------
    # Acceptance — inches parsed correctly
    # ------------------------------------------------------------------
    def test_inches_parsed(self):
        variant = self._make_variant({
            "Width": ["24 in"],
            "Door Count": ["1"],
        })
        # 24 in = 609.6 mm; door_width = 603.6; door_height = 714
        # area = 603.6 * 714 / 1e6 = 0.4310
        self.assertAlmostEqual(variant.x_door_area_m2, 0.4310, delta=0.002)

    # ------------------------------------------------------------------
    # Acceptance — width -> door count fallback (Q22(a) hides Door Count)
    # ------------------------------------------------------------------
    # The canonical seed (data/attributes.xml) hides the explicit Door
    # Count attribute per locked decision Q22(a). Real wall_2dr / base_2dr
    # variants therefore carry NO Door Count pick — the door count is
    # derived from Width via the §3.4 rule. Without the fallback the
    # door-area metric silently halved on every 2-door cabinet.
    def test_24in_wide_no_door_count_pick_resolves_to_two_doors(self):
        variant = self._make_variant({
            "Width": ["24 in"],  # 609.6 mm — in the 540-920mm 2-door band
        })
        # door_height = 720 - 6 = 714 (Base default)
        # door_width = (609.6 - 9)/2 = 300.3 each
        # area = 2 * 300.3 * 714 / 1e6 ≈ 0.4288
        self.assertAlmostEqual(
            variant.x_door_area_m2, 0.4288, delta=0.005,
            msg="24\" cabinet must derive 2 doors from Width when "
                "Door Count is hidden per Q22(a)")

    def test_18in_wide_no_door_count_pick_stays_one_door(self):
        variant = self._make_variant({
            "Width": ["18 in"],  # 457.2 mm — below the 540mm threshold
        })
        # door_height = 714; door_width = 457.2 - 6 = 451.2
        # area = 451.2 * 714 / 1e6 ≈ 0.3222
        self.assertAlmostEqual(
            variant.x_door_area_m2, 0.3222, delta=0.005)

    # ------------------------------------------------------------------
    # Acceptance — no picks -> 0
    # ------------------------------------------------------------------
    def test_no_picks_zero(self):
        tmpl = self.Tmpl.create({
            "name": "T2 unconfigured cabinet",
            "type": "consu", "is_storable": True,
            "southbrook_category": "Base",
        })
        # No attribute_line_ids means the auto-created variant has no
        # product_template_attribute_value_ids.
        variant = tmpl.product_variant_id
        self.assertEqual(variant.x_door_area_m2, 0.0)
