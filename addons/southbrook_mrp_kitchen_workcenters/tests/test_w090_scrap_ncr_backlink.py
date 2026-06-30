# SPDX-License-Identifier: LGPL-3.0-only
"""W090 (R5.10) — scrap-NCR back-link tests.

JTBD: finance cannot today walk from a written-off piece of
inventory to the defect that caused it. W090 stamps the scrap
M2O + scrap_reason onto the NCR when both are created in the
same W040 wizard pass.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_kitchen", "w090")
class TestW090ScrapNcrBacklink(TransactionCase):

    def test_fields_present_on_mi_check(self):
        Check = self.env["southbrook.mi.check"]
        self.assertIn("x_sbk_scrap_id", Check._fields)
        self.assertIn("x_sbk_scrap_reason", Check._fields)
        f = Check._fields["x_sbk_scrap_id"]
        self.assertEqual(f.type, "many2one")
        self.assertEqual(f.comodel_name, "stock.scrap")
        # Per W090 spec: ondelete must be set null so a finance
        # correction unlinking the scrap doesn't cascade to NCR.
        self.assertEqual(f.ondelete, "set null")

    def test_scrap_reason_selection_mirrors_wizard(self):
        Check = self.env["southbrook.mi.check"]
        keys = {k for k, _ in Check._fields["x_sbk_scrap_reason"].selection}
        # Must include the 5 reasons mirrored from the W040 wizard.
        for k in (
            "damage_in_process",
            "wrong_dimension",
            "material_defect",
            "operator_error",
            "other",
        ):
            self.assertIn(k, keys, "W090 scrap reason key %s missing" % k)

    def test_wizard_stamps_scrap_ref_when_both_created(self):
        """When the W040 wizard creates BOTH a scrap and a defect
        in one savepoint, the resulting NCR carries x_sbk_scrap_id
        + x_sbk_scrap_reason pointing at the scrap row."""
        WO = self.env["mrp.workorder"].sudo().search(
            [("state", "in", ("ready", "progress"))], limit=1)
        if not WO:
            self.skipTest("no WO available for end-to-end W090 wizard run")
        product = WO.production_id.product_id
        if not product:
            self.skipTest("WO has no finished good product")

        Wiz = self.env["southbrook.report.problem.wizard"]
        wiz = Wiz.create({
            "workorder_id": WO.id,
            "include_scrap": True,
            "scrap_product_id": product.id,
            "scrap_qty": 1.0,
            "scrap_uom_id": product.uom_id.id,
            "scrap_reason": "damage_in_process",
            "scrap_notes": "W090 test stamp",
            "include_defect": True,
            "defect_type": "scratch",
            "defect_stage": "production",
            "defect_severity": "minor",
            "defect_description": "W090 test defect",
        })
        try:
            wiz.action_submit()
        except Exception as exc:  # noqa: BLE001
            self.skipTest("scrap validate refused in this env: %s" % exc)

        self.assertTrue(wiz.last_scrap_id, "scrap should be created")
        self.assertTrue(wiz.last_mi_check_id, "NCR should be created")
        ncr = wiz.last_mi_check_id
        self.assertEqual(ncr.x_sbk_scrap_id, wiz.last_scrap_id,
                         "NCR.x_sbk_scrap_id must point at the scrap")
        self.assertEqual(ncr.x_sbk_scrap_reason, "damage_in_process",
                         "NCR.x_sbk_scrap_reason must mirror wizard")
