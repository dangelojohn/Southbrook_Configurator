# addons/southbrook_hermes/tests/test_read_tools.py
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "hermes")
class TestReadToolsBatch1(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create({
            "name": "Hermes Test Partner",
        })
        product = self.env["product.product"].search([], limit=1)
        if not product:
            self.skipTest("No products in DB to build a sale order from")
        self.order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": product.id,
                "product_uom_qty": 1,
            })],
        })
        from odoo.addons.southbrook_hermes.tools import read_tools  # noqa
        self.tools = read_tools

    def test_list_my_orders(self):
        result = self.tools.list_my_orders(self.env, partner_id=self.partner.id)
        self.assertIsInstance(result, list)
        refs = [o["ref"] for o in result]
        self.assertIn(self.order.name, refs)
        for item in result:
            for k in ("ref", "stage", "partner_name"):
                self.assertIn(k, item)

    def test_get_order_status(self):
        status = self.tools.get_order_status(self.env, order_id=self.order.id)
        for k in ("stage", "mos", "bottleneck", "blocker",
                  "next_action", "install_due", "readiness_score", "version"):
            self.assertIn(k, status)

    def test_get_order_line(self):
        line = self.order.order_line[0]
        result = self.tools.get_order_line(
            self.env, order_id=self.order.id, line_id=line.id)
        for k in ("sku", "variant_name", "qty", "attributes", "retail", "channel", "flags"):
            self.assertIn(k, result)
        self.assertEqual(result["qty"], 1)

    def test_get_order_line_rejects_cross_partner_line(self):
        other = self.env["res.partner"].create({"name": "Other Partner"})
        product = self.env["product.product"].search([], limit=1)
        their_order = self.env["sale.order"].create({
            "partner_id": other.id,
            "order_line": [(0, 0, {
                "product_id": product.id, "product_uom_qty": 1})],
        })
        their_line = their_order.order_line[0]
        with self.assertRaises(Exception):
            self.tools.get_order_line(
                self.env, order_id=self.order.id, line_id=their_line.id)


@tagged("post_install", "-at_install", "southbrook", "hermes")
class TestReadToolsBatch2(TransactionCase):
    def setUp(self):
        super().setUp()
        from odoo.addons.southbrook_hermes.tools import read_tools  # noqa
        self.tools = read_tools

    def test_get_os_section_returns_charter(self):
        result = self.tools.get_os_section(self.env, slug="00_charter")
        for k in ("slug", "body", "version"):
            self.assertIn(k, result)
        self.assertEqual(result["slug"], "00_charter")

    def test_get_os_section_missing(self):
        with self.assertRaises(Exception):
            self.tools.get_os_section(self.env, slug="no_such_slug_anywhere")

    def test_list_my_kitchen_projects_returns_list(self):
        partner = self.env["res.partner"].create({"name": "Empty Partner"})
        result = self.tools.list_my_kitchen_projects(
            self.env, partner_id=partner.id)
        self.assertEqual(result, [])

    def test_list_my_recommendations(self):
        partner = self.env["res.partner"].create({"name": "Rec Partner"})
        result = self.tools.list_my_recommendations(
            self.env, partner_id=partner.id)
        self.assertIsInstance(result, list)
