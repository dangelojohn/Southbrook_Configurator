# addons/southbrook_os/tests/test_generators.py
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "southbrook_os")
class TestCatalogGenerator(TransactionCase):
    def test_catalog_generator_produces_section(self):
        result = self.env["southbrook.os.generators"].generate_catalog()
        section = self.env["southbrook.os.section"].search(
            [("slug", "=", "02_catalog.generated")], limit=1)
        self.assertTrue(section)
        self.assertEqual(section.source, "generated")
        self.assertIn("#", section.body)  # has at least one header
        # Should mention at least one real product family
        self.assertTrue(any(
            family in section.body
            for family in ["Base", "Wall", "Tall", "Vanity"]
        ))
        self.assertEqual(result["status"], "ok")

    def test_catalog_generator_is_idempotent(self):
        first = self.env["southbrook.os.generators"].generate_catalog()
        second = self.env["southbrook.os.generators"].generate_catalog()
        section = self.env["southbrook.os.section"].search(
            [("slug", "=", "02_catalog.generated")], limit=1)
        # Unchanged content should not bump version twice
        self.assertEqual(section.version, first["new_version"])
        self.assertEqual(section.version, second["new_version"])
