# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for the rule-trigger domains seeded in commit 5.

The per-template product.config.line records that actually fire
restrictions land in commit 7 (when templates exist). Here we verify
that the 6 domain triggers (Series=Contractor/Elegance/Signature,
Width=Narrow/Wide, Family_subtype=Bifold) are present and well-formed.
"""
from odoo.tests.common import tagged

from .common import SouthbrookTestCase


@tagged("post_install", "-at_install", "southbrook")
class TestConfigRuleDomains(SouthbrookTestCase):

    def test_01_six_domains_present(self):
        for xml_id in (
            "domain_series_is_contractor",
            "domain_series_is_elegance",
            "domain_series_is_signature",
            "domain_width_narrow",
            "domain_width_wide",
            "domain_family_subtype_bifold",
        ):
            self._ref(xml_id)  # raises if missing

    def test_02_series_domains_each_have_one_line(self):
        for xml_id in (
            "domain_series_is_contractor",
            "domain_series_is_elegance",
            "domain_series_is_signature",
        ):
            d = self._ref(xml_id)
            self.assertEqual(len(d.domain_line_ids), 1)
            line = d.domain_line_ids[0]
            self.assertEqual(line.condition, "in")
            self.assertEqual(line.operator, "and")
            self.assertEqual(line.attribute_id.name, "Series")

    def test_03_width_narrow_covers_9_to_21(self):
        d = self._ref("domain_width_narrow")
        line = d.domain_line_ids[0]
        names = sorted(v.name for v in line.value_ids)
        self.assertEqual(names, ["12 in", "15 in", "18 in", "21 in", "9 in"])

    def test_04_width_wide_covers_24_to_36(self):
        d = self._ref("domain_width_wide")
        line = d.domain_line_ids[0]
        names = sorted(v.name for v in line.value_ids)
        self.assertEqual(names, ["24 in", "27 in", "30 in", "33 in", "36 in"])

    def test_05_bifold_domain_keyed_on_family_subtype(self):
        d = self._ref("domain_family_subtype_bifold")
        line = d.domain_line_ids[0]
        self.assertEqual(line.attribute_id.name, "Family Subtype")
        self.assertEqual(line.value_ids.mapped("name"), ["Bi-fold"])
