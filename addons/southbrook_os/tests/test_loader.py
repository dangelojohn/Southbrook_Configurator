# addons/southbrook_os/tests/test_loader.py
import os

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "southbrook_os")
class TestOsLoader(TransactionCase):
    def test_canonical_files_loaded_as_sections(self):
        # After install (this is post_install), every canonical/*.md should
        # exist as a southbrook.os.section record with source=canonical.
        Section = self.env["southbrook.os.section"]
        for fname in os.listdir("/mnt/extra-addons/southbrook_os/canonical"):
            if not fname.endswith(".md"):
                continue
            slug = fname[:-3]  # strip .md
            section = Section.search([("slug", "=", slug)], limit=1)
            self.assertTrue(
                section, f"Expected southbrook.os.section with slug='{slug}'")
            self.assertEqual(section.source, "canonical")
            self.assertTrue(section.body, f"Section {slug} has empty body")

    def test_partner_faq_loaded_with_content(self):
        section = self.env["southbrook.os.section"].search(
            [("slug", "=", "07_partner_faq")], limit=1)
        self.assertTrue(section)
        self.assertIn("Where is my kitchen?", section.body)
