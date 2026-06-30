# SPDX-License-Identifier: LGPL-3.0-only
"""W051 (R7.6) — equipment alerts tile clickable + cross-link to MOs.

Before W051 the PM dashboard's Equipment tile was a decorative count.
After: tapping the tile fires action_view_equipment_alerts which
opens the alerted equipment list filtered to this workcenter, and
the existing M14 smart button on each equipment record cross-links
to impacted in-flight MOs.

These tests cover the three new tile-action methods on mrp.workcenter:

  * action_view_equipment_alerts — filters maintenance.equipment by
    workcenter_id + condition in (fair/watch/critical/offline)
  * action_view_impacted_productions — opens in-flight MOs whose WOs
    use this workcenter (the cross-link)
  * action_view_inflight_workorders — opens the WO list for the
    workcenter (companion to the In Queue tile)
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_pm", "w051")
class TestW051EquipmentAlertsClickable(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wc = cls.env["mrp.workcenter"]
        cls.Eq = cls.env["maintenance.equipment"]
        cls.wc = cls.Wc.create({
            "name": "W051 Test Workcenter",
            "code": "W051WC",
        })
        # Two alerted equipment + one healthy at this workcenter.
        cls.eq_critical = cls.Eq.create({
            "name": "W051 Critical Eq",
            "workcenter_id": cls.wc.id,
            "southbrook_condition": "critical",
        })
        cls.eq_watch = cls.Eq.create({
            "name": "W051 Watch Eq",
            "workcenter_id": cls.wc.id,
            "southbrook_condition": "watch",
        })
        cls.eq_good = cls.Eq.create({
            "name": "W051 Good Eq",
            "workcenter_id": cls.wc.id,
            "southbrook_condition": "good",
        })

    def test_10_alert_count_excludes_good(self):
        """The dashboard count should pick up only the non-good equipment."""
        # Trigger the recompute by reading the field.
        count = self.wc.southbrook_pm_equipment_alerts
        self.assertEqual(
            count, 2,
            "Two alerted equipment (critical + watch) expected; "
            "good equipment must not count.",
        )

    def test_20_view_equipment_alerts_action_shape(self):
        """The tile-click action returns a properly-shaped act_window
        with a domain that resolves to the alerted equipment only."""
        action = self.wc.action_view_equipment_alerts()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "maintenance.equipment")
        self.assertIn("list", action["view_mode"])
        # Resolve the domain — should match exactly the two alerted Eq.
        found = self.Eq.search(action["domain"])
        self.assertEqual(
            set(found.ids), {self.eq_critical.id, self.eq_watch.id},
            "Action domain should match exactly the two alerted "
            "equipment at this workcenter.",
        )
        self.assertNotIn(
            self.eq_good.id, found.ids,
            "Healthy equipment must not appear in the alert list.",
        )

    def test_30_view_inflight_workorders_action_shape(self):
        """The In-Queue tile action returns a WO act_window."""
        action = self.wc.action_view_inflight_workorders()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "mrp.workorder")
        # Domain must filter to this workcenter.
        domain_pairs = {tuple(t) for t in action["domain"] if isinstance(t, (list, tuple))}
        self.assertIn(
            ("workcenter_id", "=", self.wc.id), domain_pairs,
            "Action domain must filter to this workcenter.",
        )

    def test_40_view_impacted_productions_action_shape(self):
        """The Late tile action returns an MO act_window whose domain
        walks workorder_ids.workcenter_id — the cross-link the W051
        review asked for."""
        action = self.wc.action_view_impacted_productions()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "mrp.production")
        # The domain pair walks the relation — match by tuple shape.
        domain_pairs = {tuple(t) for t in action["domain"]
                        if isinstance(t, (list, tuple))}
        self.assertIn(
            ("workorder_ids.workcenter_id", "=", self.wc.id),
            domain_pairs,
            "MO action must filter on workorder_ids.workcenter_id.",
        )
