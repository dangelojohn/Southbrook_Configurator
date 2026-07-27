# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for CE-native manufacturing costing.

Two of these encode defects in the module being replaced: a zero-output
order must not be costed as one unit, and industrial_cost must carry a real
figure without waiting on a financial close.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook_costing")
class TestSouthbrookCosting(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.wc = cls.env["mrp.workcenter"].create({
            "name": "TEST Panel Saw",
            "costs_hour": 60.0,          # £1/minute, keeps the maths obvious
            "time_start": 6.0,
            "time_stop": 6.0,
        })
        cls.panel = cls.env["product.product"].create({
            "name": "TEST Panel", "type": "consu", "is_storable": True,
            "standard_price": 10.0,
        })
        cls.cabinet = cls.env["product.product"].create({
            "name": "TEST Cabinet", "type": "consu", "is_storable": False,
        })
        cls.bom = cls.env["mrp.bom"].create({
            "product_tmpl_id": cls.cabinet.product_tmpl_id.id,
            "product_qty": 1.0, "type": "normal",
            "bom_line_ids": [(0, 0, {"product_id": cls.panel.id,
                                     "product_qty": 2.0})],
            "operation_ids": [(0, 0, {"name": "Cut",
                                      "workcenter_id": cls.wc.id,
                                      "time_cycle_manual": 30.0})],
        })

    def _mo(self, qty=1.0):
        return self.env["mrp.production"].create({
            "product_id": self.cabinet.id,
            "product_qty": qty,
            "product_uom_id": self.cabinet.uom_id.id,
            "bom_id": self.bom.id,
        })

    def test_standard_material_from_bom(self):
        mo = self._mo(3.0)
        self.assertEqual(
            mo.std_mat_cost, 60.0,
            "3 cabinets x 2 panels x 10.0 standard price = 60.0")

    def test_standard_routing_split(self):
        mo = self._mo(1.0)
        self.assertEqual(
            mo.std_var_cost, 30.0,
            "30 cycle minutes at 60/hour = 30.0 variable")
        self.assertEqual(
            mo.std_fixed_cost, 0.0,
            "costs_hour_fixed is unset on this workcenter, so fixed is zero "
            "rather than falling back to costs_hour")

    def test_planned_cost_frozen_at_confirm(self):
        mo = self._mo(2.0)
        self.assertEqual(mo.planned_direct_cost, 0.0,
                         "Nothing is frozen before confirmation.")
        mo.action_confirm()
        self.assertGreater(
            mo.planned_direct_cost, 0.0,
            "Confirmation must snapshot a planned cost — this is the field "
            "Command Center reads for job margin.")
        frozen = mo.planned_direct_cost
        self.panel.standard_price = 999.0
        mo.invalidate_recordset()
        self.assertEqual(
            mo.planned_direct_cost, frozen,
            "The planned snapshot must not drift when a component price "
            "changes after confirmation.")

    def test_standard_cost_does_follow_price_changes(self):
        """Standard is live where planned is frozen — the contrast matters.

        This test failed on the first implementation, which stored the
        standard-cost fields. A stored compute cannot depend on component
        standard_price reached through a recursive BoM explosion, so the
        figure went stale on reprice — silently, and exactly as the module
        being replaced behaved. The fields are now unstored.
        """
        mo = self._mo(1.0)
        self.assertEqual(mo.std_mat_cost, 20.0, "2 panels x 10.0")
        self.panel.standard_price = 20.0
        mo.invalidate_recordset()
        self.assertEqual(
            mo.std_mat_cost, 40.0,
            "Standard cost is a live BoM valuation: repricing the panel to "
            "20.0 must move 2 x 10.0 = 20.0 to 2 x 20.0 = 40.0.")

    def test_industrial_cost_falls_back_to_plan_while_open(self):
        """The defect this replaces: industrial_cost read 0.0 forever.

        The vendor module only wrote it during button_closure, which is gated
        on company accounts that are unset, so Command Center scored every
        job as costless.
        """
        mo = self._mo(2.0)
        mo.action_confirm()
        self.assertGreater(
            mo.industrial_cost, 0.0,
            "industrial_cost must carry a usable figure without a financial "
            "close having been run.")
        self.assertEqual(mo.industrial_cost, mo.planned_direct_cost)

    def test_zero_output_is_not_costed_as_one_unit(self):
        """The vendor code did `return qty_produced or 1.0`.

        A done order that produced nothing then got per-unit costs divided by
        a fabricated quantity of 1, inventing a plausible figure.
        """
        mo = self._mo(5.0)
        mo.action_confirm()
        # Force the shape of a finished order that yielded nothing.
        mo.write({"state": "done"})
        mo.invalidate_recordset()
        self.assertEqual(
            mo.qty_costed, 0.0,
            "A done order that produced nothing has a costed quantity of "
            "zero, not one.")
        self.assertEqual(
            mo.industrial_cost_unit, 0.0,
            "No denominator means no unit cost — not a fabricated one.")
        self.assertTrue(
            mo.costing_note,
            "The zero-output condition must be surfaced, not silent.")

    def test_variance_is_actual_less_planned(self):
        mo = self._mo(1.0)
        mo.action_confirm()
        self.assertEqual(
            mo.delta_direct_cost, 0.0,
            "With no recorded consumption, industrial falls back to planned, "
            "so variance is zero rather than minus the whole plan.")

    def test_contract_fields_exist_on_mrp_production(self):
        """Guards the soft coupling to Command Center and Project.

        Both read these via getattr(..., 0.0), so a rename would not raise —
        it would silently report at-risk jobs as free.
        """
        fields_ = self.env["mrp.production"]._fields
        for name in ("planned_direct_cost", "industrial_cost"):
            self.assertIn(
                name, fields_,
                f"{name} is read by southbrook_project_mrp and "
                f"southbrook_command_center; removing it silently zeroes "
                f"job margin instead of failing.")
