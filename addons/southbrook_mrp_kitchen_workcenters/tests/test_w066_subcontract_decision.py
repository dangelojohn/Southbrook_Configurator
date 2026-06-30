# SPDX-License-Identifier: LGPL-3.0-only
"""W066 (R3.9, 2026-06-27) — Subcontract Decision Wizard tests.

JTBD: "When workcenter X is at 120% capacity this week, I want a
one-click flow that diverts THIS MO's affected operation to a
qualified subcontractor — not a 6-form manual setup."

Coverage:
  * Wizard filters to qualified pg.vendor only.
  * Non-qualified vendors are excluded from candidates.
  * Capacity pct is pulled from southbrook.capacity.day (W067).
  * Confirm creates a pg.rfq with source_type='subcontract' (W078).
  * Chatter posted on both the WO and the MO.
  * Canonical BOM routing is NEVER mutated by the divert.
"""
from datetime import date, datetime, timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_kitchen", "w066")
class TestW066SubcontractDecision(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env["southbrook.subcontract.decision.wizard"]
        cls.Workorder = cls.env["mrp.workorder"]
        cls.Vendor = cls.env["pg.vendor"]
        cls.VendorPart = cls.env["pg.vendor.part"]
        cls.Rfq = cls.env["pg.rfq"]
        cls.CapacityDay = cls.env["southbrook.capacity.day"]
        cls.Item = cls.env["pg.item"]
        cls.Category = cls.env["pg.category"]

        # Build a category so vendors can carry one (Path B fallback).
        cls.category = cls.Category.create({
            "name": "W066 Test Category",
        })

        # Qualified vendor (will be in candidates).
        cls.vendor_qual = cls.Vendor.create({
            "name": "W066 Qualified Acme",
            "category_ids": [(6, 0, [cls.category.id])],
        })
        cls.vendor_qual.state = "qualified"

        # Unqualified vendor (must be excluded).
        cls.vendor_unqual = cls.Vendor.create({
            "name": "W066 Unqualified Beta",
            "category_ids": [(6, 0, [cls.category.id])],
        })
        # leave state == 'unqualified' (default)

        # Qualified vendor with NO category set (Path B excludes it
        # so the planner doesn't see a vendor with nothing to
        # evaluate against).
        cls.vendor_qual_nocat = cls.Vendor.create({
            "name": "W066 Qualified NoCategory",
        })
        cls.vendor_qual_nocat.state = "qualified"

        # Workcenter + WO scaffold.
        cls.wc = cls.env["mrp.workcenter"].create({
            "name": "W066 Test CNC",
            "code": "W066CNC",
        })
        product = cls.env["product.product"].search([
            ("type", "=", "consu")], limit=1)
        if not product:
            product = cls.env["product.product"].create({
                "name": "W066 product", "type": "consu",
            })
        cls.product = product
        cls.bom = cls.env["mrp.bom"].create({
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_qty": 1.0,
        })
        cls.mo = cls.env["mrp.production"].create({
            "product_id": product.id,
            "product_qty": 1.0,
            "bom_id": cls.bom.id,
        })
        cls.wo_date = fields.Date.context_today(cls.env["res.users"])
        cls.wo = cls.Workorder.create({
            "name": "W066 WO",
            "production_id": cls.mo.id,
            "workcenter_id": cls.wc.id,
            "product_uom_id": product.uom_id.id,
            "date_start": datetime.combine(
                cls.wo_date, datetime.min.time(),
            ),
            "duration_expected": 60.0,
        })

        # W067 capacity row: WC at 140% on the WO's day.
        cls.cap = cls.CapacityDay.create({
            "workcenter_id": cls.wc.id,
            "date": cls.wo_date,
            "available_minutes": 100.0,
            "loaded_minutes": 140.0,
        })

    # ------------------------------------------------------------------
    def _open_wizard(self, **overrides):
        defaults = {
            "workorder_id": self.wo.id,
            "planned_date": self.wo_date,
            "subcontract_qty": 1.0,
            # selected_vendor_id is required=True on the wizard model
            # (see southbrook_subcontract_decision_wizard.py L148-155).
            # Seed it with the qualified vendor so create() doesn't
            # raise NotNullViolation; individual tests that need a
            # different vendor (e.g. test_70) overwrite it after.
            "selected_vendor_id": self.vendor_qual.id,
        }
        defaults.update(overrides)
        return self.Wizard.with_context(
            default_workorder_id=self.wo.id,
            active_model="mrp.workorder",
            active_id=self.wo.id,
        ).create(defaults)

    # ------------------------------------------------------------------
    def test_10_wizard_filters_to_qualified_vendors(self):
        wiz = self._open_wizard()
        ids = wiz.candidate_vendor_ids.ids
        self.assertIn(
            self.vendor_qual.id, ids,
            "Qualified categorised vendor must be a candidate.",
        )

    def test_20_wizard_excludes_non_qualified(self):
        wiz = self._open_wizard()
        ids = wiz.candidate_vendor_ids.ids
        self.assertNotIn(
            self.vendor_unqual.id, ids,
            "Vendor in 'unqualified' state must NEVER appear in "
            "the candidate list — the AVL is a hard gate.",
        )

    def test_25_wizard_excludes_qualified_with_no_category(self):
        wiz = self._open_wizard()
        ids = wiz.candidate_vendor_ids.ids
        self.assertNotIn(
            self.vendor_qual_nocat.id, ids,
            "Qualified vendor with no pg.category set has nothing "
            "for the planner to evaluate against; Path B excludes.",
        )

    def test_30_capacity_pct_pulls_from_w067_data(self):
        wiz = self._open_wizard()
        # The W067 row has loaded=140, available=100 → 140% on the
        # stored computed field. The wizard pulls that exact value.
        self.assertAlmostEqual(
            wiz.current_utilization_pct, 140.0, places=1,
            msg="Wizard must read utilization from the W067 "
                "southbrook.capacity.day row, not recompute it.",
        )
        self.assertEqual(wiz.capacity_day_id, self.cap)
        self.assertIn("OVERCAPACITY", wiz.capacity_warning or "")

    def test_40_confirm_creates_subcontract_rfq(self):
        wiz = self._open_wizard()
        wiz.selected_vendor_id = self.vendor_qual
        wiz.subcontract_qty = 1.0
        result = wiz.action_confirm()
        self.assertEqual(result["res_model"], "pg.rfq")
        rfq = self.Rfq.browse(result["res_id"])
        self.assertTrue(rfq.exists())
        self.assertEqual(
            rfq.source_type, "subcontract",
            "RFQ must be tagged source_type='subcontract' so the "
            "W078 procurement bridge routes it correctly.",
        )
        self.assertEqual(rfq.state, "draft")
        self.assertIn("W066", rfq.reason or "")
        self.assertIn(self.wo.display_name, rfq.reason or "")

    def test_50_chatter_posted_on_wo_and_mo(self):
        wiz = self._open_wizard()
        wiz.selected_vendor_id = self.vendor_qual
        wo_msg_count_before = len(self.wo.message_ids)
        mo_msg_count_before = len(self.mo.message_ids)
        wiz.action_confirm()
        self.assertGreater(
            len(self.wo.message_ids), wo_msg_count_before,
            "WO must receive a chatter audit message about the "
            "divert decision.",
        )
        self.assertGreater(
            len(self.mo.message_ids), mo_msg_count_before,
            "MO must receive a chatter audit message about the "
            "divert decision (the MO is the planner's primary "
            "lookup surface).",
        )

    def test_60_no_auto_supersede_canonical_bom(self):
        """Divert must NOT mutate the BOM's routing — per-MO only.

        The wizard exists precisely because the BOM-typed
        subcontract pattern was too heavy for a per-MO decision.
        A divert that silently rewrote bom.type would be a Bible
        violation (mrp.bom is written only through governed flows).
        """
        bom_type_before = self.bom.type
        bom_subcontractor_before = (
            self.bom.subcontractor_ids.ids
            if "subcontractor_ids" in self.bom._fields else None
        )
        bom_routing_id_before = (
            self.wo.operation_id.id if self.wo.operation_id else False
        )

        wiz = self._open_wizard()
        wiz.selected_vendor_id = self.vendor_qual
        wiz.action_confirm()

        self.assertEqual(
            self.bom.type, bom_type_before,
            "Canonical BOM type MUST NOT change on a per-MO "
            "subcontract divert.",
        )
        if "subcontractor_ids" in self.bom._fields:
            self.assertEqual(
                self.bom.subcontractor_ids.ids,
                bom_subcontractor_before,
                "Canonical BOM subcontractor_ids MUST NOT change.",
            )
        self.assertEqual(
            self.wo.operation_id.id if self.wo.operation_id else False,
            bom_routing_id_before,
            "WO's operation linkage MUST NOT change.",
        )
        # WO still on its original workcenter.
        self.assertEqual(
            self.wo.workcenter_id, self.wc,
            "WO must remain on its original workcenter — the "
            "divert is sourced via pg.rfq, not by reassigning "
            "the WO in place.",
        )

    def test_70_confirm_requires_qualified_vendor(self):
        """Selecting an out-of-candidates vendor must be rejected."""
        wiz = self._open_wizard()
        # Bypass the domain by writing directly — simulates a stale
        # client form.
        wiz.selected_vendor_id = self.vendor_unqual
        with self.assertRaises(UserError):
            wiz.action_confirm()

    def test_80_button_returns_wizard_action(self):
        action = self.wo.action_sbk_subcontract_decision_wizard()
        self.assertEqual(
            action["res_model"],
            "southbrook.subcontract.decision.wizard",
        )
        self.assertEqual(action["target"], "new")
        self.assertEqual(
            action["context"]["default_workorder_id"], self.wo.id,
        )
