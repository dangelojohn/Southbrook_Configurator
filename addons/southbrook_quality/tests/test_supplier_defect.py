# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("southbrook", "post_install", "-at_install")
class TestSupplierDefect(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Defect = self.env["southbrook.quality.supplier_defect"]
        self.vendor = self.env["res.partner"].create(
            {"name": "Acme Hardware Co", "is_company": True}
        )

    def test_defect_rate_computed(self):
        defect = self.Defect.create(
            {
                "partner_id": self.vendor.id,
                "quantity_received": 200.0,
                "quantity_defective": 8.0,
                "defect_type": "hardware",
            }
        )
        self.assertAlmostEqual(defect.defect_rate, 0.04, places=4)

    def test_action_alert_buyer_posts_message(self):
        defect = self.Defect.create(
            {
                "partner_id": self.vendor.id,
                "quantity_received": 100.0,
                "quantity_defective": 5.0,
                "defect_type": "hardware",
            }
        )
        before = len(defect.message_ids)
        defect.action_alert_buyer()
        defect.invalidate_recordset(["message_ids"])
        self.assertGreater(len(defect.message_ids), before)
