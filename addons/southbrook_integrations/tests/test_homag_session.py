# SPDX-License-Identifier: LGPL-3.0-only
import json

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestHomagSession(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Mo = cls.env["mrp.production"]
        cls.Session = cls.env["southbrook.integrations.homag_session"]
        cls.product = cls.env["product.product"].create({
            "name": "Test Cabinet Panel",
            "type": "consu",
            "is_storable": True,
        })
        cls.component = cls.env["product.product"].create({
            "name": "Test Component",
            "type": "consu",
            "is_storable": True,
        })
        bom = cls.env["mrp.bom"].create({
            "product_tmpl_id": cls.product.product_tmpl_id.id,
            "product_qty": 1.0,
            "bom_line_ids": [(0, 0, {
                "product_id": cls.component.id,
                "product_qty": 2.0,
            })],
        })
        cls.mo = cls.Mo.create({
            "product_id": cls.product.id,
            "product_qty": 10.0,
            "product_uom_id": cls.product.uom_id.id,
            "bom_id": bom.id,
        })
        cls.mo.action_confirm()

    def test_export_payload_emitted_from_bom(self):
        session = self.Session.create({"production_id": self.mo.id})
        session.action_export_to_homag()
        self.assertEqual(session.state, "sent_to_homag")
        envelope = json.loads(session.btl_export_payload)
        self.assertEqual(envelope["schema"], "southbrook.homag.btl.v1")
        self.assertEqual(envelope["qty"], 10.0)
        self.assertIsInstance(envelope["lines"], list)
        self.assertGreater(len(envelope["lines"]), 0)

    def test_simulate_count_deterministic_with_seed(self):
        s1 = self.Session.create({
            "production_id": self.mo.id, "simulator_seed": "pin-1"})
        s2 = self.Session.create({
            "production_id": self.mo.id, "simulator_seed": "pin-1"})
        s1.action_export_to_homag()
        s2.action_export_to_homag()
        s1.action_simulate_homag_count()
        s2.action_simulate_homag_count()
        self.assertAlmostEqual(s1.count_received, s2.count_received, places=4)
        self.assertAlmostEqual(s1.scrap_qty, s2.scrap_qty, places=4)

    def test_post_to_mo_increments_qty_producing(self):
        session = self.Session.create({
            "production_id": self.mo.id, "simulator_seed": "smoke"})
        session.action_export_to_homag()
        session.action_simulate_homag_count()
        before = session.count_received
        session.action_post_to_mo()
        self.assertEqual(session.state, "completed")
        self.assertAlmostEqual(self.mo.qty_producing, before, places=4)
