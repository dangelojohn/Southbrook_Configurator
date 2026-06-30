# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("southbrook", "exec_dashboard", "post_install", "-at_install")
class TestSnapshotComputesAllFields(TransactionCase):
    """Snapshot creation must populate all 12 KPI fields with concrete
    numeric values — never False / None."""

    def test_snapshot_computes_all_fields(self):
        snapshot = self.env["southbrook.exec_dashboard.snapshot"].create({})

        # Integer fields
        for fname in (
            "yesterday_units_produced",
            "yesterday_units_target",
            "units_planned_today",
            "quality_open_critical_ncr_count",
        ):
            value = snapshot[fname]
            self.assertIsInstance(
                value, int,
                f"{fname} should be int, got {type(value).__name__}={value!r}",
            )

        # Float / Monetary fields
        for fname in (
            "yesterday_takt_adherence_pct",
            "fpy_pct_7d",
            "otd_pct_30d",
            "wip_value_current",
            "revenue_last_30d",
            "cash_position",
            "top_bottleneck_load_pct",
        ):
            value = snapshot[fname]
            self.assertIsInstance(
                value, float,
                f"{fname} should be float, got {type(value).__name__}={value!r}",
            )

        # Char field
        self.assertTrue(
            isinstance(snapshot.top_bottleneck_workcenter, str),
            "top_bottleneck_workcenter should be a string",
        )
        self.assertTrue(
            len(snapshot.top_bottleneck_workcenter) > 0,
            "top_bottleneck_workcenter should never be empty",
        )

        # Sanity: as_of is set
        self.assertTrue(snapshot.as_of, "as_of should be populated")
        self.assertTrue(snapshot.currency_id, "currency_id should resolve")
