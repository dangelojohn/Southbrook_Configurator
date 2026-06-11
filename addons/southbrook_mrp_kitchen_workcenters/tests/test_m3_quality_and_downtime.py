# SPDX-License-Identifier: LGPL-3.0-only
"""M3 — extended QC fields, downtime model, costing math."""
from datetime import datetime, timedelta

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_kitchen", "m3")
class TestQualityCheckExtension(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Check = cls.env["southbrook.mi.check"]

    def test_x_sbk_fields_exist_on_check(self):
        """Every extension field is queryable."""
        expected = (
            "x_sbk_check_stage",
            "x_sbk_defect_type",
            "x_sbk_defect_severity",
            "x_sbk_result",
            "x_sbk_workorder_id",
            "x_sbk_workcenter_id",
            "x_sbk_inspector_id",
            "x_sbk_date_checked",
            "x_sbk_rework_required",
            "x_sbk_rework_workcenter_id",
            "x_sbk_rework_workorder_id",
        )
        for fname in expected:
            self.assertIn(
                fname, self.Check._fields,
                f"southbrook.mi.check missing field {fname!r}",
            )

    def test_existing_severity_field_preserved(self):
        """The upstream severity field (info/warning/blocker) stays
        intact. We never collapse it into x_sbk_defect_severity."""
        sev_field = self.Check._fields.get("severity")
        self.assertIsNotNone(sev_field)
        keys = dict(sev_field.selection).keys()
        self.assertIn("info", keys)
        self.assertIn("warning", keys)
        self.assertIn("blocker", keys)

    def test_rework_required_computed_from_result(self):
        """x_sbk_result='fail' or 'rework' → x_sbk_rework_required."""
        for result, expected in (
            ("pass", False),
            ("fail", True),
            ("rework", True),
            ("hold", False),
            (False, False),
        ):
            check = self.Check.create({
                "name": f"Test check {result}",
                "message": "test",
                "category": "production",
                "x_sbk_result": result,
            })
            self.assertEqual(
                check.x_sbk_rework_required, expected,
                f"x_sbk_result={result!r} should yield rework={expected}",
            )


@tagged("post_install", "-at_install", "southbrook", "sbk_kitchen", "m3")
class TestDowntimeModel(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Downtime = cls.env["southbrook.kitchen.workcenter.downtime"]
        cls.paint_booth = cls.env.ref("southbrook_mrp_pm.wc_paint")

    def test_downtime_duration_computes_from_start_end(self):
        start = datetime(2026, 6, 11, 9, 0, 0)
        end = start + timedelta(minutes=45)
        d = self.Downtime.create({
            "name": "Color changeover",
            "workcenter_id": self.paint_booth.id,
            "reason": "color_finish_changeover",
            "date_start": start,
            "date_end": end,
        })
        self.assertEqual(d.duration_min, 45.0)

    def test_downtime_cost_computes_from_hourly(self):
        """duration / 60 × workcenter.costs_hour. Set costs_hour
        explicitly so the test is deterministic."""
        self.paint_booth.write({"costs_hour": 60.0})
        start = datetime(2026, 6, 11, 9, 0, 0)
        end = start + timedelta(minutes=30)
        d = self.Downtime.create({
            "name": "30 minute idle",
            "workcenter_id": self.paint_booth.id,
            "reason": "waiting_previous_operation",
            "date_start": start,
            "date_end": end,
        })
        self.assertEqual(d.duration_min, 30.0)
        # 30 min @ $60/hr = $30.
        self.assertEqual(d.downtime_cost, 30.0)

    def test_constraint_rejects_end_before_start(self):
        with self.assertRaises(ValidationError):
            self.Downtime.create({
                "name": "Bad dates",
                "workcenter_id": self.paint_booth.id,
                "reason": "other",
                "date_start": datetime(2026, 6, 11, 12, 0),
                "date_end": datetime(2026, 6, 11, 11, 0),
            })

    def test_state_machine_buttons(self):
        d = self.Downtime.create({
            "name": "State test",
            "workcenter_id": self.paint_booth.id,
            "reason": "machine_breakdown",
        })
        self.assertEqual(d.state, "draft")
        d.action_start()
        self.assertEqual(d.state, "active")
        d.action_close()
        self.assertEqual(d.state, "closed")
        self.assertTrue(d.date_end)

    def test_cancel_state(self):
        d = self.Downtime.create({
            "name": "Cancel test",
            "workcenter_id": self.paint_booth.id,
            "reason": "other",
        })
        d.action_cancel()
        self.assertEqual(d.state, "cancelled")


@tagged("post_install", "-at_install", "southbrook", "sbk_kitchen", "m3")
class TestWorkorderCosting(TransactionCase):

    def test_costing_fields_on_workorder(self):
        Workorder = self.env["mrp.workorder"]
        for fname in (
            "x_sbk_kitchen_expected_min",
            "x_sbk_variance_min",
            "x_sbk_estimated_cost",
            "x_sbk_actual_cost",
            "x_sbk_cost_variance",
            "x_sbk_rework_count",
            "x_sbk_rework_cost",
            "x_sbk_downtime_min",
            "x_sbk_downtime_cost",
        ):
            self.assertIn(
                fname, Workorder._fields,
                f"mrp.workorder missing field {fname!r}",
            )

    def test_recalc_button_is_a_noop_without_template_link(self):
        """The button exists on the model so M4's view inheritance has
        a method to bind. Until M4 wires
        mrp.routing.workcenter.x_sbk_operation_template_id, the button
        finds no template and the WO's expected stays untouched."""
        wo = self.env["mrp.workorder"].search([], limit=1)
        if not wo:
            self.skipTest("no mrp.workorder available")
        before = wo.x_sbk_kitchen_expected_min
        wo.action_sbk_recalc_kitchen_duration()
        self.assertEqual(wo.x_sbk_kitchen_expected_min, before)
