# SPDX-License-Identifier: LGPL-3.0-only
"""Template-to-Prodboard-archetype mapping and placeholder-image tests."""
import base64

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

_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc\xcf"
    b"\xc0\x00\x00\x00\x03\x00\x01\xe3]\xc5\x06\x00\x00\x00\x00IEND\xaeB`\x82"
)


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

    def test_generated_placeholder_images_cover_all_locked_templates(self):
        self.Mapper.assign_placeholder_images(force=True)

        for xml_id in _LOCKED_TEMPLATE_IDS:
            tmpl = self._ref(xml_id)
            self.assertTrue(tmpl.image_1920, f"{xml_id} has no image_1920")
            image_bytes = base64.b64decode(tmpl.image_1920)
            self.assertTrue(
                image_bytes.startswith(b"\x89PNG\r\n\x1a\n"),
                f"{xml_id}.image_1920 is not a PNG placeholder",
            )
            self.assertTrue(tmpl.x_image_uuid, f"{xml_id} has no image UUID")
            self.assertEqual(
                tmpl.x_image_filename,
                f"southbrook-{xml_id}.png",
            )

    def test_placeholder_seed_does_not_overwrite_existing_image_by_default(self):
        tmpl = self._ref("base_1dr")
        tmpl.write({
            "image_1920": base64.b64encode(_TINY_PNG).decode("ascii"),
            "x_image_uuid": False,
            "x_image_filename": False,
        })

        self.Mapper.assign_placeholder_images()

        self.assertEqual(base64.b64decode(tmpl.image_1920), _TINY_PNG)
        self.assertTrue(tmpl.x_image_uuid)
        self.assertEqual(tmpl.x_image_filename, "southbrook-base_1dr.png")
