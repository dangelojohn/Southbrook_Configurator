# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "kitchenforge")
class TestInstantiate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]
        cls.Project = cls.env["project.project"]
        cls.Tmpl = cls.env["product.template"]
        cls.partner = cls.Partner.create({"name": "Acme Kitchens"})
        cls.cabinet_tmpl = cls.Tmpl.create({
            "name": "Test Base 600",
            "type": "consu",
            "config_ok": True,
        })
        cls.template = cls.Project.create({
            "name": "Test Full Kitchen",
            "is_template": True,
            "kitchenforge_kind": "full_kitchen",
        })
        cls.env["kitchenforge.template.line"].create({
            "template_project_id": cls.template.id,
            "sequence": 10,
            "name": "B-01 Sink Base 36",
            "product_tmpl_id": cls.cabinet_tmpl.id,
            "quantity": 1,
            "width_mm": 900,
            "height_mm": 720,
            "depth_mm": 580,
        })
        cls.env["kitchenforge.template.line"].create({
            "template_project_id": cls.template.id,
            "sequence": 20,
            "name": "B-02 Drawer Base 600",
            "product_tmpl_id": cls.cabinet_tmpl.id,
            "quantity": 1,
            "width_mm": 600,
            "height_mm": 720,
            "depth_mm": 580,
        })

    def test_template_flag_set(self):
        self.assertTrue(self.template.is_template)
        self.assertEqual(len(self.template.default_cabinet_zone_ids), 2)

    def test_instantiate_creates_project_and_so(self):
        new_proj = self.template.kitchenforge_instantiate(
            partner=self.partner,
            dims={"room_width_mm": 3600, "room_depth_mm": 3000},
        )
        self.assertFalse(new_proj.is_template)
        self.assertEqual(new_proj.partner_id, self.partner)
        self.assertEqual(new_proj.instantiated_from_template_id, self.template)
        self.assertTrue(new_proj.sale_order_id)
        so = new_proj.sale_order_id
        self.assertEqual(so.partner_id, self.partner)
        self.assertEqual(len(so.order_line), 2)
        self.assertEqual(so.kitchenforge_template_id, self.template)
        self.assertEqual(so.kitchenforge_project_id, new_proj)

    def test_zone_dimensions_carried_to_so_line(self):
        new_proj = self.template.kitchenforge_instantiate(partner=self.partner)
        line_900 = new_proj.sale_order_id.order_line.filtered(
            lambda l: l.kitchenforge_zone_width_mm == 900)
        self.assertTrue(line_900)
        self.assertEqual(line_900.kitchenforge_zone_height_mm, 720)
        self.assertEqual(line_900.kitchenforge_zone_depth_mm, 580)

    def test_instantiate_refuses_non_template(self):
        from odoo.exceptions import UserError
        non_tmpl = self.Project.create({
            "name": "Not a template", "is_template": False})
        with self.assertRaises(UserError):
            non_tmpl.kitchenforge_instantiate(partner=self.partner)

    def test_product_template_auto_routes_manufacture(self):
        route = self.env.ref(
            "mrp.route_warehouse0_manufacture", raise_if_not_found=False)
        if not route:
            self.skipTest("mrp.route_warehouse0_manufacture not found")
        new_tmpl = self.Tmpl.create({
            "name": "Auto-routed cabinet",
            "type": "consu",
            "config_ok": True,
        })
        self.assertIn(route, new_tmpl.route_ids)

    def test_no_template_no_auto_route(self):
        route = self.env.ref(
            "mrp.route_warehouse0_manufacture", raise_if_not_found=False)
        if not route:
            self.skipTest("mrp.route_warehouse0_manufacture not found")
        plain = self.Tmpl.create({
            "name": "Plain product",
            "type": "consu",
            "config_ok": False,
        })
        self.assertNotIn(route, plain.route_ids)
