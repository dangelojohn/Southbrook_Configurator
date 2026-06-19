# SPDX-License-Identifier: LGPL-3.0-only
"""Regression coverage for Southbrook BoM line Configuration Sets."""
from odoo.tests.common import tagged

from .common import SouthbrookTestCase


@tagged("post_install", "-at_install", "southbrook", "configuration_sets")
class TestConfigurationSetsSeed(SouthbrookTestCase):

    def test_seeded_configuration_sets_exist(self):
        """Manufacturing has starter config sets instead of an empty screen."""
        for xml_id in (
            "config_set_series_contractor",
            "config_set_series_contemporary",
            "config_set_series_elegance",
            "config_set_series_signature",
            "config_set_box_white_melamine",
            "config_set_box_maple",
            "config_set_drawer_dovetail_hardwood",
            "config_set_drawer_metal_blum",
            "config_set_accessory_soft_close",
        ):
            config_set = self._ref(xml_id)
            self.assertEqual(config_set._name, "mrp.bom.line.configuration.set")
            self.assertTrue(config_set.configuration_ids)

    def test_configuration_sets_point_to_expected_values(self):
        cases = {
            "config_set_series_contractor": ["Contractor Series"],
            "config_set_series_signature": ["Signature"],
            "config_set_box_maple": ["Maple"],
            "config_set_door_custom_signature": ["Custom (Signature)"],
            "config_set_drawer_metal_blum": ["Metal (Blum Legrabox)"],
            "config_set_accessory_soft_close": ["Soft-Close"],
        }
        for xml_id, expected_names in cases.items():
            config_set = self._ref(xml_id)
            value_names = sorted(
                config_set.configuration_ids.mapped("value_ids.name"))
            self.assertEqual(value_names, sorted(expected_names))

    def test_seeded_sets_start_unattached_to_bom_lines(self):
        """Seed reusable conditions without changing BoM explosion behavior."""
        config_set = self._ref("config_set_series_signature")
        self.assertFalse(config_set.bom_line_ids)
