# addons/southbrook_os/tests/test_os_section.py
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.southbrook_os.models.os_section import _HAS_MARKDOWN


@tagged("post_install", "-at_install", "southbrook", "southbrook_os")
class TestOsSection(TransactionCase):
    def test_section_created_with_required_fields(self):
        section = self.env["southbrook.os.section"].create({
            "slug": "test_section",
            "name": "Test Section",
            "source": "canonical",
            "body": "# Test\n\nHello.",
        })
        self.assertEqual(section.version, 1)
        self.assertEqual(section.source, "canonical")
        # `markdown` is an OPTIONAL dependency (os_section has a fallback
        # renderer). Only assert real header conversion when it's installed;
        # always assert the body text survives rendering + sanitisation.
        # The `toc` markdown extension emits `<h1 id="...">` (auto-anchor
        # slug), not a bare `<h1>`. Assert against the open-tag prefix so
        # the test tolerates whichever extension set the renderer ships.
        if _HAS_MARKDOWN:
            self.assertIn("<h1", section.body_html)
        self.assertIn("Hello", section.body_html)

    def test_slug_is_unique(self):
        self.env["southbrook.os.section"].create({
            "slug": "dup", "name": "First", "source": "canonical", "body": "a",
        })
        with self.assertRaises(Exception):
            self.env["southbrook.os.section"].create({
                "slug": "dup", "name": "Second", "source": "canonical", "body": "b",
            })

    def test_version_bump_method(self):
        section = self.env["southbrook.os.section"].create({
            "slug": "bumpable", "name": "X", "source": "canonical", "body": "v1",
        })
        section.bump_version(body="v2")
        self.assertEqual(section.version, 2)
        self.assertEqual(section.body, "v2")
        self.assertEqual(section.last_updated_by, self.env.user)
