import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "addons" / "southbrook_project" / "__manifest__.py"
PATCH = (
    REPO_ROOT
    / "addons"
    / "southbrook_project"
    / "static"
    / "src"
    / "js"
    / "kanban_template_field_ids.esm.js"
)
ASSET_PATH = "southbrook_project/static/src/js/kanban_template_field_ids.esm.js"


class KanbanTemplateFieldPatchTest(unittest.TestCase):
    def test_backend_asset_includes_kanban_template_field_patch(self):
        manifest = ast.literal_eval(MANIFEST.read_text())
        backend_assets = manifest["assets"]["web.assets_backend"]
        self.assertIn(ASSET_PATH, backend_assets)

    def test_patch_assigns_missing_field_ids_before_kanban_compilation(self):
        source = PATCH.read_text()
        self.assertIn("KanbanArchParser.prototype", source)
        self.assertIn("Field.parseFieldNode", source)
        self.assertIn("node.setAttribute(\"field_id\"", source)
        self.assertIn("templateDocs", source)


if __name__ == "__main__":
    unittest.main()
