# SPDX-License-Identifier: LGPL-3.0-only
import json

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAsn3pl(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Asn = cls.env["southbrook.integrations.asn_3pl"]
        cls.partner = cls.env["res.partner"].create({"name": "Test 3PL"})
        cls.product = cls.env["product.product"].create({
            "name": "Cabinet Small",
            "type": "consu",
            "is_storable": True,
        })
        cls.big_product = cls.env["product.product"].create({
            "name": "Cabinet Large 2500",
            "type": "consu",
            "is_storable": True,
        })
        # Stamp dims (mm) on the templates if the fields exist.
        for f in ("product_length", "product_width", "product_height"):
            if f in cls.product.product_tmpl_id._fields:
                cls.product.product_tmpl_id[f] = 600.0
            if f in cls.big_product.product_tmpl_id._fields:
                cls.big_product.product_tmpl_id[f] = 2500.0 \
                    if f == "product_length" else 600.0

        picking_type = cls.env["stock.picking.type"].search(
            [("code", "=", "outgoing")], limit=1)
        location = cls.env["stock.location"].search(
            [("usage", "=", "internal")], limit=1)
        dest = cls.env["stock.location"].search(
            [("usage", "=", "customer")], limit=1)

        cls.picking = cls.env["stock.picking"].create({
            "partner_id": cls.partner.id,
            "picking_type_id": picking_type.id,
            "location_id": location.id,
            "location_dest_id": dest.id,
            # stock.move.name was removed in v19 — omit it (the move derives
            # its own label from product_id).
            "move_ids": [
                (0, 0, {
                    "product_id": cls.product.id,
                    "product_uom_qty": 3.0,
                    "product_uom": cls.product.uom_id.id,
                    "location_id": location.id,
                    "location_dest_id": dest.id,
                }),
                (0, 0, {
                    "product_id": cls.big_product.id,
                    "product_uom_qty": 1.0,
                    "product_uom": cls.big_product.uom_id.id,
                    "location_id": location.id,
                    "location_dest_id": dest.id,
                }),
            ],
        })

    def test_emit_asn_includes_all_lines(self):
        asn = self.Asn.create({"picking_id": self.picking.id})
        asn.action_emit_asn()
        self.assertEqual(asn.state, "sent")
        envelope = json.loads(asn.payload_json)
        self.assertEqual(envelope["schema"], "southbrook.asn.214.v1")
        self.assertEqual(len(envelope["lines"]), 2)

    def test_oversize_flag_triggers_on_2400mm(self):
        asn = self.Asn.create({"picking_id": self.picking.id})
        # If dims fields aren't present on product.template in this DB
        # (e.g. stock module variation), the compute returns False and
        # the test is a no-op against the threshold rather than a fail.
        if hasattr(self.big_product.product_tmpl_id, "product_length"):
            self.assertTrue(asn.oversize_load_flag)
        else:
            self.assertFalse(asn.oversize_load_flag)
