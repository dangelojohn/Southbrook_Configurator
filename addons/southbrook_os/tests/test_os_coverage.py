# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


_REQUIRED_SLUGS = [
    "00_charter",
    "01_company",
    "02_catalog",
    "03_attributes",
    "04_lifecycle",
    "05_production",
    "06_plm",
    "07_partner_faq",
    "20_systems_topology",
    "99_glossary",
]


@tagged("post_install", "-at_install", "southbrook", "southbrook_os")
class TestOsCoverage(TransactionCase):
    def test_all_required_canonical_sections_exist(self):
        Section = self.env["southbrook.os.section"]
        existing = {s.slug for s in Section.search([("source", "=", "canonical")])}
        missing = [slug for slug in _REQUIRED_SLUGS if slug not in existing]
        self.assertFalse(missing, f"Missing required canonical sections: {missing}")

    def test_partner_faq_contains_anchor_questions(self):
        """The 'where is my kitchen?' question must always be answerable from
        the FAQ — it is the headline Hermes use case."""
        section = self.env["southbrook.os.section"].search(
            [("slug", "=", "07_partner_faq")], limit=1)
        self.assertTrue(section)
        anchor_questions = [
            "Where is my kitchen?",
            "What's blocking my install?",
            "When will my install be ready?",
        ]
        for q in anchor_questions:
            self.assertIn(q, section.body,
                f"FAQ section missing anchor question: {q!r}")
