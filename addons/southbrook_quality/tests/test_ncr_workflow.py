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

    def test_raw_write_state_is_guarded(self):
        """A raw write() cannot launder state past the transition graph
        (regression N1: draft -> released skips quarantine + disposition)."""
        ncr = self._new_ncr()
        with self.assertRaises(UserError):
            ncr.write({"state": "released"})
        self.assertEqual(ncr.state, "draft")

    def test_critical_release_requires_manager(self):
        """Use-as-is release of a CRITICAL NCR needs a Quality Manager
        (regression N2)."""
        ncr = self._new_ncr()
        ncr.severity = "critical"
        ncr.action_quarantine()
        ncr.disposition_reason = "Use as-is: cosmetic only."
        # Current test user lacks the quality-manager group.
        mgr = "southbrook_quality.group_southbrook_quality_manager"
        if not self.env.user.has_group(mgr):
            with self.assertRaises(UserError):
                ncr.action_release()

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
        # Back-date opened_at so the delta is deterministic. (create_date is not
        # writable in v19 — the ORM silently ignores it — which is exactly why
        # the model tracks its own opened_at as the SLA start.)
        ncr.write({"opened_at": datetime.now() - timedelta(hours=4)})
        ncr.action_scrap()
        ncr.invalidate_recordset(["time_to_close_hours"])
        self.assertGreater(ncr.time_to_close_hours, 3.0)
