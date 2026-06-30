# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestIotLabelPrinter(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Printer = cls.env["southbrook.integrations.iot_label_printer"]
        cls.partner = cls.env["res.partner"].create({"name": "Ship-To Co"})

    def test_render_zpl_substitutes_vars(self):
        picking_type = self.env["stock.picking.type"].search(
            [("code", "=", "outgoing")], limit=1)
        loc = self.env["stock.location"].search(
            [("usage", "=", "internal")], limit=1)
        dest = self.env["stock.location"].search(
            [("usage", "=", "customer")], limit=1)
        picking = self.env["stock.picking"].create({
            "partner_id": self.partner.id,
            "picking_type_id": picking_type.id,
            "location_id": loc.id,
            "location_dest_id": dest.id,
        })
        printer = self.Printer.create({
            "name": "Test ZPL",
            "model_target": "stock.picking",
            "zpl_template": "^XA^FDPicking ${name} for ${partner_id}^FS^XZ",
        })
        out = printer.render_zpl(picking)
        self.assertIn(picking.name, out)
        self.assertIn("Ship-To Co", out)
        # Unknown placeholders render empty (intentional).
        printer2 = self.Printer.create({
            "name": "Unknown var test",
            "model_target": "stock.picking",
            "zpl_template": "^XA^FD${this_field_does_not_exist}^FS^XZ",
        })
        out2 = printer2.render_zpl(picking)
        self.assertIn("^FD^FS", out2)

    def test_print_via_iot_logs_row(self):
        printer = self.Printer.create({
            "name": "Log test",
            "model_target": "stock.picking",
            "zpl_template": "^XA^FDhello^FS^XZ",
        })
        log = printer.print_via_iot("^XA^FDhello^FS^XZ")
        self.assertEqual(log.status, "queued")
        self.assertEqual(log.printer_id, printer)
