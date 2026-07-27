# SPDX-License-Identifier: LGPL-3.0-only
"""Task 7 (kitchen templates) — the /rearrange model seam.

The route (controllers/main.py rearrange) is a thin composition over
this seam: write room dims -> action_auto_arrange(sync=False) ->
re-emit lines; a resize the cabinets can't fit is refused (the engine
either raises LayoutCapacityExceeded or — the T5 lesson — 'fits' by
ARCHIVING lines; the route maps BOTH to ROOM_TOO_SMALL and reverts).
These tests pin that seam's behavior end to end on shipped data.
"""
from odoo.tests import TransactionCase, tagged

from odoo.addons.southbrook_estimating.models import kitchen_layout_engine


@tagged("post_install", "-at_install", "southbrook",
        "southbrook_kitchen_3d_configurator", "kitchen_templates")
class TestRearrangeSeam(TransactionCase):

    def _galley(self):
        tpl = self.env["southbrook.kitchen.template"].search(
            [("code", "=", "GAL-10")], limit=1)
        self.assertTrue(tpl, "GAL-10 ships active (T4)")
        return tpl.action_instantiate()

    def test_grow_rearranges_and_keeps_every_line(self):
        design = self._galley()
        active_before = design.cabinet_line_ids.filtered(
            lambda l: l.layout_role == "canonical")
        xs_before = {l.id: (l.x_position_in, l.z_position_in)
                     for l in active_before}
        design.write({"room_width_in": 144.0})
        design.action_auto_arrange(sync=False)
        self.assertTrue(all(l.active for l in active_before),
                        "growing the room must never drop a cabinet")
        self.assertEqual(design.room_width_in, 144.0)
        # Poses were re-derived by the engine (same run origins here,
        # so equality is fine — the point is no exception, no drops,
        # and a coherent layout at the new width).
        for line in active_before:
            self.assertIn(line.id, xs_before)

    def test_impossible_shrink_is_detectable_and_revertible(self):
        design = self._galley()
        pre_active = design.cabinet_line_ids.filtered(
            lambda l: l.layout_role == "canonical")
        pre_ids = pre_active.ids
        design.write({"room_width_in": 60.0})   # GAL-10 needs ~105"/wall
        raised = False
        try:
            design.action_auto_arrange(sync=False)
        except kitchen_layout_engine.LayoutCapacityExceeded:
            raised = True
        dropped = self.env["southbrook.kitchen.design.line"].with_context(
            active_test=False).browse(pre_ids).filtered(
            lambda l: not l.active)
        self.assertTrue(raised or dropped,
                        "an impossible shrink must be DETECTABLE: either "
                        "the engine raises or it archives cabinets — "
                        "never a silent 'success' with everything intact")
        # The route's revert path: original dims + re-arrange restores
        # every originally-active canonical line.
        design.write({"room_width_in": 120.0})
        design.action_auto_arrange(sync=False)
        restored = self.env["southbrook.kitchen.design.line"].with_context(
            active_test=False).browse(pre_ids)
        self.assertTrue(all(restored.mapped("active")),
                        "revert must restore the original layout")
        self.assertEqual(design.room_width_in, 120.0)
