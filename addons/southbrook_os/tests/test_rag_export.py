# addons/southbrook_os/tests/test_rag_export.py
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "southbrook_os")
class TestRagExport(TransactionCase):
    def test_export_emits_one_entry_per_section(self):
        bundle = self.env["southbrook.os.rag.export"].build_bundle(
            tenant="southbrook")
        self.assertEqual(bundle["tenant"], "southbrook")
        self.assertIn("documents", bundle)
        slugs = {d["slug"] for d in bundle["documents"]}
        self.assertIn("00_charter", slugs)

    def test_export_includes_metadata_per_document(self):
        bundle = self.env["southbrook.os.rag.export"].build_bundle(
            tenant="southbrook")
        doc = bundle["documents"][0]
        for key in ("slug", "name", "version", "source", "text", "audience"):
            self.assertIn(key, doc)
