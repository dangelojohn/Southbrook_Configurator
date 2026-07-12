# SPDX-License-Identifier: LGPL-3.0-only
import random

from odoo.tests.common import TransactionCase, tagged


@tagged("southbrook", "post_install", "-at_install")
class TestCpkView(TransactionCase):
    def test_cpk_computed_for_capable_process(self):
        Sample = self.env["southbrook.quality.spc_sample"]
        Cpk = self.env["southbrook.quality.cpk_report"]
        workcenter = self.env["mrp.workcenter"].create({"name": "Test WC Cpk"})
        dim = self.env.ref("southbrook_quality.dim_door_gap_mm")
        rng = random.Random(1234)
        # 30 samples tightly clustered around nominal -> Cpk should be > 0.
        for _i in range(30):
            Sample.create(
                {
                    "workcenter_id": workcenter.id,
                    "dimension_id": dim.id,
                    "measured_value": dim.nominal + rng.uniform(-0.1, 0.1),
                }
            )
        # The Cpk report is a SQL view reading the spc_sample TABLE directly;
        # flush the ORM-pending sample INSERTs first or the view sees nothing.
        self.env.flush_all()
        # Refresh view definition (idempotent) and re-query.
        Cpk.init()
        rows = Cpk.search(
            [
                ("workcenter_id", "=", workcenter.id),
                ("dimension_key", "=", dim.key),
            ]
        )
        self.assertTrue(rows, "Cpk view should expose the workcenter+dimension row")
        self.assertGreater(rows.cpk, 0.0)
        self.assertEqual(rows.sample_count, 30)
