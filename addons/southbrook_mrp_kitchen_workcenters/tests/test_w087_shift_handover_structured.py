# SPDX-License-Identifier: LGPL-3.0-only
"""W087 (R2.7) — structured shift-handover prompts.

JTBD: zero handovers exist today because the free-text summary
is too high-friction. Three yes/no triage questions + optional
notes lower the cognitive cost to "tap three Yes/No".
"""
from datetime import date

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_kitchen", "w087")
class TestW087StructuredHandover(TransactionCase):

    def test_structured_fields_present(self):
        """All four structured fields exist on the model with
        the expected types."""
        H = self.env["southbrook.shift.handover"]
        for fname, ftype in (
            ("q_anything_broken", "boolean"),
            ("q_material_low", "boolean"),
            ("q_safety_concern", "boolean"),
            ("q_extra_notes", "text"),
        ):
            self.assertIn(fname, H._fields,
                          "W087 field %s missing" % fname)
            self.assertEqual(H._fields[fname].type, ftype,
                             "W087 field %s type drift" % fname)

    def test_legacy_summary_field_preserved(self):
        """The pre-W087 `summary` field must still exist for
        backward compatibility with historical handovers and
        search filters."""
        H = self.env["southbrook.shift.handover"]
        self.assertIn("summary", H._fields)
        self.assertEqual(H._fields["summary"].type, "text")

    def test_handover_created_with_structured_only(self):
        """A handover answered ONLY with the three booleans + no
        free-text summary is fully valid (the structured prompts
        are the new minimum viable handover)."""
        H = self.env["southbrook.shift.handover"]
        rec = H.create({
            "shift": "day",
            "shift_date": date.today(),
            "q_anything_broken": False,
            "q_material_low": True,
            "q_safety_concern": False,
        })
        self.assertEqual(rec.state, "draft")
        self.assertFalse(rec.summary,
                         "summary should be empty / not required")
        self.assertTrue(rec.q_material_low)
        # Submit transitions cleanly even without legacy summary.
        rec.action_submit()
        self.assertEqual(rec.state, "submitted")

    def test_tracking_on_triage_fields(self):
        """Triage fields must be tracked so the chatter shows
        the answer history (audit-trail requirement)."""
        H = self.env["southbrook.shift.handover"]
        for fname in (
            "q_anything_broken",
            "q_material_low",
            "q_safety_concern",
        ):
            self.assertTrue(
                H._fields[fname].tracking,
                "W087 triage field %s must be tracked" % fname,
            )
