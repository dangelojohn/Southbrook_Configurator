# SPDX-License-Identifier: LGPL-3.0-only
"""W080 (R1.W2) — MO form tab consolidation tests.

JTBD: "Planner shouldn't horizontal-scroll the MO notebook tab
strip on a 1366x768 shop-floor laptop."

Coverage:
  * The 5 lifecycle group pages (sbk_grp_*) are present in the
    composed MO form arch.
  * The consolidation view is registered with priority 22 so it
    layers AFTER the priority-21 hide-upstream-mi view but does
    not collide with priority-20 mi_tab.
  * The 5 group pages do NOT remove any existing page that has
    an active xml_id (canonical pages stay registered for
    binding-action resolution).
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_kitchen", "w080")
class TestW080TabConsolidation(TransactionCase):

    def test_consolidation_view_is_priority_22(self):
        view = self.env.ref(
            "southbrook_mrp_kitchen_workcenters."
            "view_mrp_production_form_sbk_tab_consolidation"
        )
        self.assertEqual(view.priority, 22)
        self.assertEqual(view.model, "mrp.production")

    def test_five_lifecycle_pages_present_in_composed_arch(self):
        """The composed MO form arch must contain all 5 sbk_grp_*
        page names. Uses get_view so the result is the merged arch
        the operator actually sees."""
        composed = self.env["mrp.production"].get_view(
            view_id=self.env.ref("mrp.mrp_production_form_view").id,
            view_type="form",
        )
        arch = composed.get("arch", "")
        for name in (
            "sbk_grp_production",
            "sbk_grp_intelligence",
            "sbk_grp_engineering",
            "sbk_grp_qc",
            "sbk_grp_misc",
        ):
            self.assertIn(name, arch,
                          "lifecycle group page %s missing" % name)

    def test_canonical_pages_still_registered(self):
        """The Cabinet Label + MI tab + Kitchen tab pages must
        still be registered in the composed arch even if some are
        hidden via invisible=1. Their xml_ids are referenced by
        actions in sibling addons."""
        composed = self.env["mrp.production"].get_view(
            view_id=self.env.ref("mrp.mrp_production_form_view").id,
            view_type="form",
        )
        arch = composed.get("arch", "")
        for name in ("sbk_label", "sbk_mi", "sbk_kitchen"):
            self.assertIn(name, arch,
                          "canonical page %s must remain in arch" % name)
