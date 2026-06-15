# SPDX-License-Identifier: LGPL-3.0-only
import json

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.kitchenforge_core.controllers import _fs


@tagged("post_install", "-at_install", "kitchenforge")
class TestAgentFS(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cabinet = cls.env["product.template"].create({
            "name": "Test Wall 300", "type": "consu", "config_ok": True,
        })
        cls.tmpl = cls.env["project.project"].create({
            "name": "FS Test Template",
            "is_template": True,
            "kitchenforge_kind": "full_kitchen",
        })
        cls.line = cls.env["kitchenforge.template.line"].create({
            "template_project_id": cls.tmpl.id,
            "sequence": 10,
            "name": "W-01 Wall 300",
            "product_tmpl_id": cls.cabinet.id,
            "quantity": 1,
            "width_mm": 300,
            "height_mm": 900,
            "depth_mm": 320,
        })
        cls.partner = cls.env["res.partner"].create({"name": "FS Test Partner"})

    def test_split_path(self):
        self.assertEqual(_fs.split_path(""), [])
        self.assertEqual(_fs.split_path("/"), [])
        self.assertEqual(_fs.split_path("/a/b"), ["a", "b"])
        self.assertEqual(_fs.split_path("a/b/"), ["a", "b"])

    def test_slugify(self):
        self.assertEqual(_fs.slugify("Full Kitchen Build"), "full-kitchen-build")
        self.assertEqual(_fs.slugify(""), "unnamed")

    def test_resolve_root_lists_namespaces(self):
        r = _fs.resolve(self.env, "/")
        self.assertEqual(r["kind"], "dir")
        names = [e["name"] for e in r["entries"]]
        self.assertIn("templates", names)
        self.assertIn("projects", names)
        self.assertIn("catalog", names)
        self.assertIn("shop", names)

    def test_resolve_templates_lists_seed(self):
        r = _fs.resolve(self.env, "/templates")
        self.assertEqual(r["kind"], "dir")
        slugs = [e["name"] for e in r["entries"]]
        self.assertIn("fs-test-template.yaml", slugs)

    def test_resolve_template_file(self):
        r = _fs.resolve(self.env, "/templates/fs-test-template.yaml")
        self.assertEqual(r["kind"], "file")
        self.assertEqual(r["content"]["name"], "FS Test Template")
        self.assertGreaterEqual(r["content"]["default_cabinet_zone_count"], 1)
        self.assertTrue(any(t["id"] == "instantiate" for t in r["content"]["tools"]))

    def test_resolve_template_zone_file(self):
        r = _fs.resolve(self.env, "/templates/fs-test-template/zones")
        self.assertEqual(r["kind"], "dir")
        self.assertEqual(len(r["entries"]), 1)
        zone_path = r["entries"][0]["path"]
        zone = _fs.resolve(self.env, zone_path)
        self.assertEqual(zone["kind"], "file")
        self.assertEqual(zone["content"]["dimensions_mm"]["width"], 300)
        self.assertEqual(zone["content"]["product_tmpl_id"], self.cabinet.id)

    def test_resolve_project_after_instantiate(self):
        proj = self.tmpl.kitchenforge_instantiate(partner=self.partner)
        r = _fs.resolve(self.env, f"/projects/{proj.id}.yaml")
        self.assertEqual(r["content"]["partner"]["name"], "FS Test Partner")
        self.assertEqual(r["content"]["instantiated_from"]["id"], self.tmpl.id)
        q = _fs.resolve(self.env, f"/projects/{proj.id}/quote.yaml")
        self.assertEqual(q["kind"], "file")
        self.assertEqual(q["content"]["state"], "draft")
        self.assertEqual(len(q["content"]["lines"]), 1)

    def test_write_template_zone_round_trip(self):
        r = _fs.write(
            self.env,
            "/templates/fs-test-template/zones/010-w-01-wall-300.yaml",
            {
                "name": "W-01 Wall 300",
                "sequence": 10,
                "product_tmpl_id": self.cabinet.id,
                "quantity": 2,
                "dimensions_mm": {"width": 450, "height": 900, "depth": 320},
                "preselected_attribute_values": {},
            },
            if_match=None,
        )
        self.assertEqual(r["kind"], "file")
        self.assertEqual(r["content"]["quantity"], 2)
        self.assertEqual(r["content"]["dimensions_mm"]["width"], 450)

    def test_not_found_raises(self):
        with self.assertRaises(_fs.NotFound):
            _fs.resolve(self.env, "/no/such/namespace")
        with self.assertRaises(_fs.NotFound):
            _fs.resolve(self.env, "/templates/does-not-exist.yaml")

    def test_write_to_read_only_namespace_raises(self):
        with self.assertRaises(_fs.ReadOnly):
            _fs.write(self.env, "/catalog/attributes.yaml", {}, None)
