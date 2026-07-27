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


@tagged("post_install", "-at_install", "southbrook", "southbrook_os")
class TestAttributeGenerator(TransactionCase):
    def test_attribute_generator_lists_attributes(self):
        result = self.env["southbrook.os.generators"].generate_attributes()
        section = self.env["southbrook.os.section"].search(
            [("slug", "=", "03_attributes.generated")], limit=1)
        self.assertTrue(section)
        self.assertIn("attribute", section.body.lower())
        self.assertEqual(result["status"], "ok")


@tagged("post_install", "-at_install", "southbrook", "southbrook_os")
class TestCutSpecGenerator(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The generator graceful-skips when southbrook.cut.spec isn't
        # installed (southbrook_os doesn't depend on southbrook_plm).
        # When PLM IS present, we need an active spec for the generator
        # to emit the rows the assertion looks for — the PLM seed
        # (cut_spec_nf14_seed) provides one on a normal install, but
        # tests run in isolated transactions and noupdate seeds aren't
        # guaranteed. Idempotently ensure an active spec exists.
        CutSpec = cls.env.get("southbrook.cut.spec")
        cls._cut_spec_available = CutSpec is not None
        if cls._cut_spec_available and not CutSpec.search(
                [("active", "=", True)], limit=1):
            # Field defaults populate every geometric constant (box_th,
            # door_reveal, etc.) so the generator can read non-None
            # values straight out of create.
            CutSpec.create({"name": "Test Cut Spec (fixture)"})

    def test_cut_spec_generator_emits_active_values(self):
        if not self._cut_spec_available:
            self.skipTest("southbrook.cut.spec model not installed")
        result = self.env["southbrook.os.generators"].generate_cut_spec()
        section = self.env["southbrook.os.section"].search(
            [("slug", "=", "06_cut_spec.generated")], limit=1)
        self.assertTrue(section)
        self.assertEqual(result["status"], "ok")
        text = section.body.lower()
        if self.env.get("southbrook.cut.spec") is not None:
            # Full stack (southbrook_plm present): real spec fields are rendered.
            self.assertTrue("thickness" in text or "reveal" in text)
        else:
            # southbrook_plm absent → generator emits a documented stub; the
            # status-ok + section-exists checks are the meaningful assertions.
            self.assertIn("cut specification", text)


@tagged("post_install", "-at_install", "southbrook", "southbrook_os")
class TestWorkCenterGenerator(TransactionCase):
    def test_work_center_generator(self):
        result = self.env["southbrook.os.generators"].generate_work_centers()
        section = self.env["southbrook.os.section"].search(
            [("slug", "=", "08_work_centers.generated")], limit=1)
        self.assertTrue(section)
        self.assertIn("Work Center", section.body)
        self.assertEqual(result["status"], "ok")
