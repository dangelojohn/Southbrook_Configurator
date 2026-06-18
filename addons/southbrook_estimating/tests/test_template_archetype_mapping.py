# SPDX-License-Identifier: LGPL-3.0-only
"""Template-to-Prodboard-archetype mapping tests."""

from odoo.tests.common import TransactionCase, tagged


_LOCKED_TEMPLATE_IDS = [
    "wall_1dr",
    "wall_2dr",
    "base_1dr",
    "base_2dr",
    "drawer_bank",
    "sink_base",
    "tall_pantry",
    "tall_oven",
    "corner",
    "vanity",
    "accessory",
    "worktop",
]

_EXPECTED_MAPPINGS = {
    "wall_1dr": "CC-WD{H}1DR",
    "wall_2dr": "CC-WD{H}2DR",
    "base_1dr": "CC-BHL1DR",
    "base_2dr": "CC-BHL2DR",
    "drawer_bank": "CC-BMD3DW",
    "sink_base": "CC-BHS1DR",
    "tall_pantry": "CC-TL{H}{h}T",
    "tall_oven": "CC-TA{H}SODRS",
    "corner": "CC-CHL{S}",
}

_INTENTIONALLY_UNMAPPED = [
    "vanity",
    "accessory",
    "worktop",
]


@tagged("post_install", "-at_install", "southbrook", "prodboard_mapping")
class TestTemplateArchetypeMapping(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Template = cls.env["product.template"]
        cls.Mapper = cls.env["southbrook.estimating.template_archetype"]

    def _ref(self, xml_id):
        return self.env.ref(f"southbrook_estimating.{xml_id}")

    def test_mapping_field_exists(self):
        self.assertIn("x_prodboard_archetype_id", self.Template._fields)
        field = self.Template._fields["x_prodboard_archetype_id"]
        self.assertEqual(field.type, "many2one")
        self.assertEqual(field.comodel_name, "southbrook.cabinet.archetype")

    def test_all_locked_templates_still_resolve(self):
        for xml_id in _LOCKED_TEMPLATE_IDS:
            self.assertTrue(self._ref(xml_id), f"{xml_id} no longer resolves")

    def test_canonical_templates_map_to_expected_archetype_codes(self):
        self.Mapper.assign_archetypes()

        for xml_id, expected_code in _EXPECTED_MAPPINGS.items():
            tmpl = self._ref(xml_id)
            self.assertTrue(
                tmpl.x_prodboard_archetype_id,
                f"{xml_id} should map to {expected_code}",
            )
            self.assertEqual(tmpl.x_prodboard_archetype_id.code, expected_code)

    def test_southbrook_only_templates_remain_unmapped(self):
        self.Mapper.assign_archetypes()

        for xml_id in _INTENTIONALLY_UNMAPPED:
            tmpl = self._ref(xml_id)
            self.assertFalse(
                tmpl.x_prodboard_archetype_id,
                f"{xml_id} is Southbrook-specific and should not be forced "
                "onto an unrelated UK Prodboard archetype",
            )

    def test_assignment_is_idempotent(self):
        self.Mapper.assign_archetypes()
        before = {
            xml_id: self._ref(xml_id).x_prodboard_archetype_id.id
            for xml_id in _LOCKED_TEMPLATE_IDS
        }

        self.Mapper.assign_archetypes()
        after = {
            xml_id: self._ref(xml_id).x_prodboard_archetype_id.id
            for xml_id in _LOCKED_TEMPLATE_IDS
        }

        self.assertEqual(before, after)

