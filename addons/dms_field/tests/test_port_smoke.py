# Copyright 2026 Southbrook
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
"""Task B2 — runtime smoke tests for the two dms_field files that couple to
PRIVATE Odoo core internals (the real 18.0->19.0 port risk surface):

- ``models/ir_ui_view.py``: imports the private ``NameManager`` class and
  replicates ``_postprocess_tag_field`` plumbing to postprocess the
  ``dms_list`` view type. Exercised here by rendering the
  ``dms_field.view_dms_field_template_form`` view, which embeds
  ``dms_directory_ids`` with ``mode="dms_list"`` — the same mechanism the
  Product/MO/picking bridge will rely on.
- ``models/dms_directory.py`` ``_search_parents`` (~lines 116-165): hand-rolled
  raw SQL against ``query.from_clause`` / ``query.where_clause`` /
  ``_order_to_sql`` / ``_apply_ir_rules`` — all ``Query``-object internals
  that changed shape release-to-release.

These do not fail at import; they only fail (or misbehave) when actually
called, which is what these tests force.
"""
from odoo.tests import tagged

from odoo.addons.base.tests.common import BaseCommon


@tagged("post_install", "-at_install", "dms_field_port")
class TestDmsFieldPortSmoke(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.storage = cls.env["dms.storage"].create(
            {"name": "B2 smoke storage", "save_type": "database"}
        )
        cls.root = cls.env["dms.directory"].create(
            {
                "name": "B2 root",
                "is_root_directory": True,
                "storage_id": cls.storage.id,
            }
        )
        cls.child = cls.env["dms.directory"].create(
            {"name": "B2 child", "parent_id": cls.root.id, "storage_id": cls.storage.id}
        )
        cls.grandchild = cls.env["dms.directory"].create(
            {
                "name": "B2 grandchild",
                "parent_id": cls.child.id,
                "storage_id": cls.storage.id,
            }
        )
        cls.all_dirs = cls.root | cls.child | cls.grandchild

    def test_search_parents_runs(self):
        """Exercises dms.directory._search_parents' raw-SQL builder
        (query.from_clause / query.where_clause / _order_to_sql /
        _apply_ir_rules) against the live v19 core Query/Domain internals.

        Of the three directories only ``root`` has no readable parent in the
        result set, so it must be the sole "top level" element returned.
        """
        parents = self.env["dms.directory"].search_parents(
            [("id", "in", self.all_dirs.ids)]
        )
        self.assertEqual(parents, self.root)

        count = self.env["dms.directory"].search_parents(
            [("id", "in", self.all_dirs.ids)], count=True
        )
        self.assertEqual(count, 1)

        res = self.env["dms.directory"].search_read_parents(
            [("id", "in", self.all_dirs.ids)], fields=["id"]
        )
        self.assertEqual(res, [{"id": self.root.id}])

        res_named = self.env["dms.directory"].search_read_parents(
            [("id", "in", self.all_dirs.ids)], fields=["id", "name"]
        )
        self.assertEqual(res_named, [{"id": self.root.id, "name": self.root.name}])

    def test_dms_list_view_type_registered(self):
        vt = self.env["ir.ui.view"].fields_get(["type"])["type"]["selection"]
        self.assertIn("dms_list", dict(vt))

    def test_dms_list_embed_postprocess(self):
        """Exercises ir_ui_view._postprocess_tag_dms_list end-to-end: getting
        the dms.field.template form view (which embeds dms_directory_ids
        with mode="dms_list") forces the ORM to fetch the missing dms_list
        sub-arch for dms.directory, which is postprocessed through the
        private NameManager-based plumbing dms_field replicates.
        """
        view = self.env.ref("dms_field.view_dms_field_template_form")
        result = self.env["dms.field.template"].get_view(view.id, "form")
        self.assertIn('mode="dms_list"', result["arch"])
        # the dms_list sub-view was actually embedded (not left as a bare
        # childless <field>), proving _postprocess_tag_dms_list ran and
        # produced the <dms_list> node's children in the combined arch.
        self.assertIn("<dms_list", result["arch"])
