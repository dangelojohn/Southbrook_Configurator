# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("southbrook", "post_install", "-at_install")
class TestSpcSample(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Sample = self.env["southbrook.quality.spc_sample"]
        # mrp.workcenter is provided by `mrp`, a hard dep.
        self.workcenter = self.env["mrp.workcenter"].create(
            {"name": "Test Saw 1"}
        )
        self.dim = self.env.ref("southbrook_quality.dim_door_gap_mm")

    def test_in_spec_true(self):
        sample = self.Sample.create(
            {
                "workcenter_id": self.workcenter.id,
                "dimension_id": self.dim.id,
                "measured_value": 3.0,
            }
        )
        self.assertTrue(sample.in_spec)

    def test_in_spec_false_above_usl(self):
        sample = self.Sample.create(
            {
                "workcenter_id": self.workcenter.id,
                "dimension_id": self.dim.id,
                "measured_value": 4.0,
            }
        )
        self.assertFalse(sample.in_spec)

    def test_auto_create_ncr_when_oos(self):
        sample = self.Sample.create(
            {
                "workcenter_id": self.workcenter.id,
                "dimension_id": self.dim.id,
                "measured_value": 5.0,
            }
        )
        ncrs = sample.action_create_ncr_if_oos()
        self.assertEqual(len(ncrs), 1)
        self.assertEqual(ncrs.defect_type, "dimension")
        self.assertEqual(ncrs.spc_sample_id, sample)

    def test_name_sequence(self):
        sample = self.Sample.create(
            {
                "workcenter_id": self.workcenter.id,
                "dimension_id": self.dim.id,
                "measured_value": 3.0,
            }
        )
        self.assertTrue(sample.name.startswith("SPC/"))
