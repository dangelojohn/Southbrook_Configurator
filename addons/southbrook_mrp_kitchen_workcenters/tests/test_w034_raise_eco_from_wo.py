# SPDX-License-Identifier: LGPL-3.0-only
"""W034 (R4.W5, 2026-06-27) — Report Engineering Issue from a WO.

JTBD: "When I find a problem at the CNC that needs an engineering
change, I want to photo + describe it from the WO form and have a
draft ECO auto-created with the WO context attached."

Coverage:
  * Button on the WO form opens the wizard pre-bound to the WO.
  * Submitting creates a southbrook.eco in a non-applied stage (draft).
  * The wizard NEVER auto-approves: ECO state remains 'open'.
  * The WO chatter receives a back-link note.
  * The ECO description embeds the WO/MO context block.
  * `mi_check_id` linkage is reflected in the ECO description.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_kitchen", "w034")
class TestW034RaiseEcoFromWo(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env["southbrook.wo.raise.eco.wizard"]
        cls.Eco = cls.env["southbrook.eco"]
        cls.Workorder = cls.env["mrp.workorder"]
        cls.Check = cls.env["southbrook.mi.check"]

    def _make_wo(self):
        wc = self.env["mrp.workcenter"].search([], limit=1)
        if not wc:
            wc = self.env["mrp.workcenter"].create({
                "name": "W034 WC", "code": "W034WC",
            })
        product = self.env["product.product"].search([
            ("type", "=", "consu")], limit=1)
        if not product:
            product = self.env["product.product"].create({
                "name": "W034 product", "type": "consu",
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
        wo = self.Workorder.create({
            "name": "W034 WO",
            "production_id": production.id,
            "workcenter_id": wc.id,
            "product_uom_id": product.uom_id.id,
        })
        return wo

    # ------------------------------------------------------------------
    def test_10_button_returns_wizard_action(self):
        wo = self._make_wo()
        action = wo.action_sbk_raise_eco_wizard()
        self.assertEqual(action["res_model"], "southbrook.wo.raise.eco.wizard")
        self.assertEqual(action["target"], "new")
        self.assertEqual(action["context"]["default_workorder_id"], wo.id)

    def test_20_submit_creates_draft_eco(self):
        wo = self._make_wo()
        wiz = self.Wizard.with_context(
            default_workorder_id=wo.id,
            active_model="mrp.workorder",
            active_id=wo.id,
        ).create({
            "title": "CNC drill hole 4mm off",
            "description": "Hole pattern is shifted left.",
            "severity": "high",
        })
        result = wiz.action_submit()
        # The submit action returns an act_window opening the new ECO.
        self.assertEqual(result["res_model"], "southbrook.eco")
        eco = self.Eco.browse(result["res_id"])
        self.assertTrue(eco.exists(), "ECO must exist after submit.")
        # Always draft / open. Spec: never auto-approved.
        self.assertEqual(
            eco.state, "open",
            "Wizard must NEVER auto-approve; ECO must be in 'open' state.")
        self.assertFalse(
            eco.stage_id.is_applied_stage,
            "ECO must not land in an applied stage.")
        # Priority maps from severity=high -> '2' (Urgent).
        self.assertEqual(eco.priority, "2")
        # Description embeds the WO context block.
        self.assertIn(wo.display_name or str(wo.id), eco.description or "")
        self.assertIn("W034", eco.description or "")

    def test_30_default_target_kind_is_document(self):
        """W034 always pins ECO type to 'document' so apply is record-
        only. Engineering re-types to bom/cut_spec only after triage."""
        wo = self._make_wo()
        wiz = self.Wizard.with_context(
            default_workorder_id=wo.id,
        ).create({
            "title": "test default type",
            "description": "x",
            "severity": "low",
        })
        result = wiz.action_submit()
        eco = self.Eco.browse(result["res_id"])
        self.assertEqual(
            eco.target_kind, "document",
            "W034 must default to a record-only ECO type so apply "
            "doesn't accidentally mutate a BoM or cut-spec.")

    def test_40_wo_chatter_gets_back_link(self):
        wo = self._make_wo()
        existing_msg_count = len(wo.message_ids)
        wiz = self.Wizard.with_context(
            default_workorder_id=wo.id,
        ).create({
            "title": "y",
            "description": "z",
            "severity": "medium",
        })
        wiz.action_submit()
        wo.invalidate_recordset()
        new_msgs = wo.message_ids
        self.assertGreater(
            len(new_msgs), existing_msg_count,
            "WO chatter must receive a back-link note pointing at the "
            "new ECO after submit.")
        body = " ".join(new_msgs.mapped("body") or [])
        self.assertIn("ECO", body)

    def test_50_mi_check_linkage_in_description(self):
        wo = self._make_wo()
        check = self.Check.create({
            "name": "W034 origin defect",
            "message": "origin",
            "severity": "warning",
            "category": "production",
            "production_id": wo.production_id.id,
            "x_sbk_workorder_id": wo.id,
            "x_sbk_inspector_id": self.env.user.id,
        })
        wiz = self.Wizard.with_context(
            default_workorder_id=wo.id,
        ).create({
            "title": "linked to MI check",
            "description": "linked",
            "severity": "medium",
            "mi_check_id": check.id,
        })
        result = wiz.action_submit()
        eco = self.Eco.browse(result["res_id"])
        self.assertIn(
            check.display_name, eco.description or "",
            "The originating MI check display name should be embedded "
            "in the ECO description.")
