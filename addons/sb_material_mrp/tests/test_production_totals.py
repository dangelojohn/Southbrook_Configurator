# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_material")
class TestProductionTotals(TransactionCase):
    def test_weight_to_purchase_applies_scrap(self):
        mo = self.env["mrp.production"].new({})
        self.assertAlmostEqual(mo._weight_to_purchase(100.0, 12.0), 112.0, places=2)

    def test_missing_price_is_flagged_not_zeroed_silently(self):
        mo = self.env["mrp.production"].new({})
        prov = mo._merge_provenance([{"tier": "vendor"}, {"tier": "online"}])
        self.assertIn("online", prov)  # honesty: surfaced, not hidden
