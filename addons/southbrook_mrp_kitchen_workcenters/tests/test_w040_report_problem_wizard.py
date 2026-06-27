# SPDX-License-Identifier: LGPL-3.0-only
"""W040 (R2.4, 2026-06-27) — One-screen Report-a-Problem wizard.

JTBD: "When something goes wrong at the cell, I want ONE screen to
log scrap qty + defect description + downtime — not 3 separate forms."

Coverage:
  * Button on the WO form opens the wizard pre-bound to the WO.
  * Submitting all three sections creates scrap + mi.check + downtime
    in a single transaction.
  * Submitting only a subset works (any combination of the 3).
  * Empty submit (no sections ticked) raises UserError — no silent NOP.
  * Atomicity: a bad scrap qty in the scrap section causes UserError
    AND prevents the defect + downtime from being written
    (savepoint rollback).
"""
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_kitchen", "w040")
class TestW040ReportProblemWizard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env["southbrook.report.problem.wizard"]
        cls.Scrap = cls.env["stock.scrap"]
        cls.Check = cls.env["southbrook.mi.check"]
        cls.Downtime = cls.env["southbrook.kitchen.workcenter.downtime"]
        cls.Workorder = cls.env["mrp.workorder"]

    def _make_wo(self):
        wc = self.env["mrp.workcenter"].search([], limit=1)
        if not wc:
            wc = self.env["mrp.workcenter"].create({
                "name": "W040 WC", "code": "W040WC",
            })
        product = self.env["product.product"].search([
            ("type", "=", "consu")], limit=1)
        if not product:
            product = self.env["product.product"].create({
                "name": "W040 product", "type": "consu",
            })
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_qty": 1.0,
        })
        production = self.env["mrp.production"].create({
            "product_id": product.id,
            "product_qty": 1.0,
            "bom_id": bom.id,
        })
        production.action_confirm()
        wo = self.Workorder.create({
            "name": "W040 WO",
            "production_id": production.id,
            "workcenter_id": wc.id,
            "product_uom_id": product.uom_id.id,
        })
        return wo, product

    # ------------------------------------------------------------------
    def test_10_button_returns_wizard_action(self):
        wo, _p = self._make_wo()
        action = wo.action_sbk_open_report_problem_wizard()
        self.assertEqual(action["res_model"], "southbrook.report.problem.wizard")
        self.assertEqual(action["target"], "new")
        self.assertEqual(action["context"]["default_workorder_id"], wo.id)

    def test_20_all_three_sections_in_one_transaction(self):
        wo, product = self._make_wo()
        wiz = self.Wizard.with_context(
            default_workorder_id=wo.id,
            active_model="mrp.workorder",
            active_id=wo.id,
        ).create({
            "include_scrap": True,
            "scrap_product_id": product.id,
            "scrap_qty": 1.0,
            "scrap_uom_id": product.uom_id.id,
            "scrap_reason": "operator_error",
            "include_defect": True,
            "defect_type": "wrong_dimension",
            "defect_severity": "major",
            "defect_description": "Hole drilled 3mm low.",
            "include_downtime": True,
            "downtime_reason": "machine_breakdown",
            "downtime_minutes": 12.5,
            "downtime_notes": "Spindle vibration.",
        })
        wiz.action_submit()
        self.assertTrue(wiz.last_scrap_id, "Scrap row must be created.")
        self.assertTrue(wiz.last_mi_check_id, "mi.check row must be created.")
        self.assertTrue(wiz.last_downtime_id, "Downtime row must be created.")
        # Defect linkage on the mi.check
        self.assertEqual(
            wiz.last_mi_check_id.x_sbk_workorder_id.id, wo.id,
            "mi.check must be linked back to the WO.")
        self.assertEqual(
            wiz.last_mi_check_id.x_sbk_defect_severity, "major")
        # Downtime values land verbatim
        self.assertEqual(wiz.last_downtime_id.workorder_id.id, wo.id)
        self.assertAlmostEqual(
            wiz.last_downtime_id.duration_min, 12.5, places=2)
        self.assertEqual(wiz.last_downtime_id.reason, "machine_breakdown")

    def test_30_partial_submit_defect_only(self):
        wo, _p = self._make_wo()
        wiz = self.Wizard.with_context(default_workorder_id=wo.id).create({
            "include_defect": True,
            "defect_type": "grain_direction",
            "defect_description": "Wrong-way grain on stile.",
            "defect_severity": "minor",
        })
        wiz.action_submit()
        self.assertFalse(wiz.last_scrap_id)
        self.assertTrue(wiz.last_mi_check_id)
        self.assertFalse(wiz.last_downtime_id)

    def test_40_empty_submit_raises(self):
        wo, _p = self._make_wo()
        wiz = self.Wizard.with_context(default_workorder_id=wo.id).create({})
        with self.assertRaises(UserError):
            wiz.action_submit()

    def test_50_atomicity_bad_scrap_rolls_back_defect_and_downtime(self):
        """If the scrap section is invalid, the wizard must raise BEFORE
        writing the defect or downtime. The savepoint guarantees no
        half-committed state."""
        wo, product = self._make_wo()
        # Snapshot pre-existing counts so the assertion is robust to
        # demo/seed rows.
        scraps_before = self.Scrap.search_count([
            ("workorder_id", "=", wo.id)])
        checks_before = self.Check.search_count([
            ("x_sbk_workorder_id", "=", wo.id)])
        downtimes_before = self.Downtime.search_count([
            ("workorder_id", "=", wo.id)])
        wiz = self.Wizard.with_context(default_workorder_id=wo.id).create({
            "include_scrap": True,
            "scrap_product_id": product.id,
            "scrap_qty": -5.0,  # invalid — _validate rejects before any create
            "scrap_uom_id": product.uom_id.id,
            "include_defect": True,
            "defect_type": "wrong_dimension",
            "defect_description": "should never land",
            "defect_severity": "minor",
            "include_downtime": True,
            "downtime_reason": "machine_breakdown",
            "downtime_minutes": 5.0,
        })
        with self.assertRaises(UserError):
            wiz.action_submit()
        # NOTHING was written — savepoint rolled all three back.
        self.assertEqual(
            self.Scrap.search_count([("workorder_id", "=", wo.id)]),
            scraps_before)
        self.assertEqual(
            self.Check.search_count([("x_sbk_workorder_id", "=", wo.id)]),
            checks_before)
        self.assertEqual(
            self.Downtime.search_count([("workorder_id", "=", wo.id)]),
            downtimes_before)
