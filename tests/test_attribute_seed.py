# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for the configurator attribute seed (Q2/Q3/Q4/Q6/Q22(a)/Q23(b))."""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook")
class TestAttributeSeed(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Attr = cls.env["product.attribute"]
        cls.Val = cls.env["product.attribute.value"]

    def _ref(self, xml_id):
        return self.env.ref(f"southbrook_estimating.{xml_id}")

    def test_01_eleven_user_facing_attributes_present(self):
        """Q2 — the 11 canonical attributes from Mapping §3.3."""
        for name in [
            "attr_family", "attr_width", "attr_series", "attr_box_material",
            "attr_door_style", "attr_finish", "attr_hinge_side",
            "attr_finished_sides", "attr_gables", "attr_handle",
            "attr_accessories",
        ]:
            self._ref(name)  # raises if missing

    def test_02_derived_attributes_present(self):
        """Q22(a) door_count + Q23(b) family_subtype + Q8 accessory_type."""
        self._ref("attr_door_count")
        self._ref("attr_family_subtype")
        self._ref("attr_accessory_type")

    def test_03_all_attributes_use_dynamic_variant_creation(self):
        """Q6 — every attribute is create_variant='dynamic'."""
        # Walk every attribute we seeded (find by external id prefix)
        # and assert create_variant.
        seeded = self.env["ir.model.data"].search([
            ("module", "=", "southbrook_estimating"),
            ("model", "=", "product.attribute"),
        ])
        self.assertGreater(len(seeded), 0)
        for data in seeded:
            attr = self.env["product.attribute"].browse(data.res_id)
            self.assertEqual(
                attr.create_variant, "dynamic",
                f"attribute {attr.name} must be dynamic per Q6",
            )

    def test_04_width_values_carry_dual_storage(self):
        """Q4 — width values have value_inches AND value_mm set."""
        cases = [
            ("value_width_9",  9, 228),
            ("value_width_12", 12, 304),
            ("value_width_18", 18, 457),
            ("value_width_24", 24, 609),
            ("value_width_30", 30, 762),
            ("value_width_36", 36, 914),
        ]
        for xml_id, expected_in, expected_mm in cases:
            v = self._ref(xml_id)
            self.assertEqual(v.value_inches, expected_in,
                             f"{xml_id}: value_inches mismatch")
            self.assertEqual(v.value_mm, expected_mm,
                             f"{xml_id}: value_mm mismatch (canonical from #5)")

    def test_05_non_dimensional_values_have_null_dual_storage(self):
        """Q4 — series / door_style / etc. leave both dual-storage fields null."""
        for xml_id in ("value_series_contractor", "value_door_thermofoil_slab_white",
                       "value_box_white_melamine", "value_hinge_left"):
            v = self._ref(xml_id)
            self.assertEqual(v.value_inches, 0.0)
            self.assertEqual(v.value_mm, 0)

    def test_06_maple_box_carries_lead_time_extra(self):
        """Q3 — maple box value has lead_time_extra = 14 days (+2 weeks)."""
        maple = self._ref("value_box_maple")
        self.assertEqual(maple.lead_time_extra, 14.0)
        # White melamine baseline is 0.
        white = self._ref("value_box_white_melamine")
        self.assertEqual(white.lead_time_extra, 0.0)

    def test_07_door_count_is_hidden(self):
        """Q22(a) — door_count is display_type='hidden'."""
        attr = self._ref("attr_door_count")
        self.assertEqual(attr.display_type, "hidden")

    def test_08_family_has_nine_values_not_corner_bifold(self):
        """Q23(b) — corner is single family value; bifold is family_subtype."""
        family_values = self.env["product.attribute.value"].search([
            ("attribute_id", "=", self._ref("attr_family").id)
        ])
        names = sorted(v.name for v in family_values)
        self.assertEqual(len(family_values), 9,
                         "family must have exactly 9 values per Q2")
        self.assertNotIn("Corner Bi-fold", names,
                         "Q23(b): bifold lives in family_subtype, not family")
        subtype_values = self.env["product.attribute.value"].search([
            ("attribute_id", "=", self._ref("attr_family_subtype").id)
        ])
        subtype_names = sorted(v.name for v in subtype_values)
        self.assertEqual(subtype_names, ["Bi-fold", "Standard"])

    def test_09_accessory_type_five_values(self):
        """Q8 — accessory_type has 5 values."""
        vals = self.env["product.attribute.value"].search([
            ("attribute_id", "=", self._ref("attr_accessory_type").id)
        ])
        names = sorted(v.name for v in vals)
        self.assertEqual(names, ["Cornice", "End Panel", "Filler", "Pelmet", "Plinth"])
