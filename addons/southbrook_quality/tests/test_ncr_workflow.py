# SPDX-License-Identifier: LGPL-3.0-only
from datetime import datetime, timedelta

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("southbrook", "post_install", "-at_install")
class TestNcrWorkflow(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Ncr = self.env["southbrook.ncr"]

    def _new_ncr(self):
        return self.Ncr.create(
            {
                "defect_type": "dimension",
                "severity": "minor",
                "quantity": 1.0,
                "description": "Test NCR",
            }
        )

    def test_draft_to_quarantine(self):
        ncr = self._new_ncr()
        self.assertEqual(ncr.state, "draft")
        ncr.action_quarantine()
        self.assertEqual(ncr.state, "quarantine")

    def test_quarantine_to_rework_requires_disposition(self):
        ncr = self._new_ncr()
        ncr.action_quarantine()
        with self.assertRaises(UserError):
            ncr.action_rework()
        ncr.disposition_reason = "Rework: re-sand and refinish front edge."
        ncr.action_rework()
        self.assertEqual(ncr.state, "rework")

    def test_quarantine_to_scrap(self):
        ncr = self._new_ncr()
        ncr.action_quarantine()
        ncr.disposition_reason = "Material unrecoverable."
        ncr.action_scrap()
        self.assertEqual(ncr.state, "scrap")
        self.assertTrue(ncr.closed_at)

    def test_quarantine_to_released(self):
        ncr = self._new_ncr()
        ncr.action_quarantine()
        ncr.disposition_reason = "Use as-is per engineering review."
        ncr.action_release()
        self.assertEqual(ncr.state, "released")
        self.assertTrue(ncr.closed_at)

    def test_invalid_transition_raises(self):
        ncr = self._new_ncr()
        # draft -> rework is not in VALID_TRANSITIONS.
        with self.assertRaises(UserError):
            ncr.action_rework()

    def test_terminal_state_sets_closed_at(self):
        ncr = self._new_ncr()
        ncr.action_quarantine()
        ncr.disposition_reason = "Scrap."
        ncr.action_scrap()
        self.assertTrue(ncr.closed_at)

    def test_time_to_close_hours_computed(self):
        ncr = self._new_ncr()
        ncr.action_quarantine()
        ncr.disposition_reason = "Scrap."
        # Force a known create_date so the delta is non-zero deterministically.
        ncr.write({"create_date": datetime.now() - timedelta(hours=4)})
        ncr.action_scrap()
        ncr.invalidate_recordset(["time_to_close_hours"])
        self.assertGreater(ncr.time_to_close_hours, 3.0)
