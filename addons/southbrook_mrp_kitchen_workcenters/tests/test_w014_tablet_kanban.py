# SPDX-License-Identifier: LGPL-3.0-only
"""W014 — tablet kanban for the operator (MFG-REVIEW R2.1 / R8.13).

These tests cover the static surface and the wiring, not the OWL render
itself (that's a JS test target — view rendering is exercised by the
v19 `get_view` machinery here as a smoke check).

Coverage:
  * kanban view arch loads cleanly through `get_view` — view-validation
    passes (catches `column_invisible` / x_* / non-stored compute traps
    that the v19 validator now blocks at install time)
  * action `action_sbk_tablet_wo_queue` exists, references the kanban
    view, and filters by `workcenter_id == active_id`
  * direct state-machine button calls (`button_start`, `button_pending`,
    `button_finish`) work in sequence against a minimal MO — proves the
    methods we reference from the kanban actually exist on `mrp.workorder`
    in the live registry
  * the kanban defaults `group_by` to `state` — operator opens to a
    state-banded view, not a flat list
  * related fields `x_sbk_cabinet_code` / `x_sbk_kitchen_room` resolve
    on `mrp.workorder` (proves the related field path didn't break)
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_kitchen", "w014")
class TestW014TabletKanban(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Workorder = cls.env["mrp.workorder"]
        cls.Workcenter = cls.env["mrp.workcenter"]
        cls.Production = cls.env["mrp.production"]
        cls.Bom = cls.env["mrp.bom"]
        cls.RoutingWC = cls.env["mrp.routing.workcenter"]

        # Pick or build a workcenter we can attach a routing to.
        wc = cls.Workcenter.search([("active", "=", True)], limit=1)
        if not wc:
            wc = cls.Workcenter.create({"name": "W014 test WC"})
        cls.workcenter = wc

    def _build_minimal_mo(self):
        """Build the smallest MO that produces a single WO bound to
        self.workcenter. Used by the button-state-transition test."""
        Product = self.env["product.product"]
        product = Product.search([("type", "=", "consu")], limit=1)
        if not product:
            product = Product.create({
                "name": "W014 test product",
                "type": "consu",
            })
        bom = self.Bom.create({
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_qty": 1.0,
        })
        self.RoutingWC.create({
            "bom_id": bom.id,
            "workcenter_id": self.workcenter.id,
            "name": "W014 test op",
            "time_cycle": 10.0,
        })
        mo = self.Production.create({
            "product_id": product.id,
            "product_qty": 1.0,
            "bom_id": bom.id,
        })
        mo.action_confirm()
        return mo

    # ------------------------------------------------------------------
    # Static surface — view + action wiring
    # ------------------------------------------------------------------

    def test_10_kanban_view_loads_without_error(self):
        """get_view on the tablet kanban returns valid arch.

        v19 view validation rejects unresolved fields, bad invisibles,
        and stale x_* references at install time. If this test passes,
        the view installed cleanly — the symptom we're guarding against
        is the silent "view in DB but won't render" partial-commit trap
        called out in [[odoo19_view_dep_chain_manual_fields]].
        """
        view = self.env.ref(
            "southbrook_mrp_kitchen_workcenters."
            "view_mrp_workorder_kanban_sbk_tablet",
        )
        self.assertEqual(view.model, "mrp.workorder")
        self.assertEqual(view.type, "kanban")
        # get_view exercises the full validation path.
        res = self.Workorder.get_view(view.id, "kanban")
        self.assertIn("arch", res)
        # Sanity: our class hook is in the rendered arch so the SCSS
        # bundle has a target to bind to.
        self.assertIn("o_kanban_sb_tablet", res["arch"])

    def test_20_action_filters_by_active_workcenter(self):
        """The action narrows to the calling workcenter via active_id
        and only surfaces WOs the operator can act on."""
        action = self.env.ref(
            "southbrook_mrp_kitchen_workcenters."
            "action_sbk_tablet_wo_queue",
        )
        self.assertEqual(action.res_model, "mrp.workorder")
        self.assertIn("kanban", action.view_mode)
        # Domain references the three operator-actionable states and
        # binds workcenter to active_id (the workcenter the button was
        # pressed on).
        dom = action.domain or ""
        self.assertIn("workcenter_id", dom)
        self.assertIn("active_id", dom)
        for st in ("ready", "progress", "blocked"):
            self.assertIn(st, dom)

    def test_30_default_groupby_state(self):
        """The tablet kanban must open grouped by state — operator
        sees Ready / In Progress / Blocked columns, not a flat list."""
        view = self.env.ref(
            "southbrook_mrp_kitchen_workcenters."
            "view_mrp_workorder_kanban_sbk_tablet",
        )
        self.assertIn("default_group_by=\"state\"", view.arch)

    def test_40_related_fields_resolve_on_workorder(self):
        """The kitchen cabinet code + room must be readable on the WO
        via the related field path (production_id.x_sbk_*) — the kanban
        relies on these for the top-line label.

        Pulls an existing WO if there is one, otherwise builds the
        minimal MO and reads its first WO.
        """
        wo = self.Workorder.search([], limit=1)
        if not wo:
            mo = self._build_minimal_mo()
            wo = mo.workorder_ids[:1]
        self.assertTrue(wo)
        # Just reading the field exercises the related path; if the
        # field doesn't exist on the model, this raises AttributeError.
        _ = wo.x_sbk_cabinet_code
        _ = wo.x_sbk_kitchen_room
        # Field definition sanity — proves they're declared on the WO
        # model and stored (per the model's docstring rationale).
        cab = self.Workorder._fields["x_sbk_cabinet_code"]
        self.assertEqual(cab.related, "production_id.x_sbk_cabinet_code")
        self.assertTrue(cab.store)

    # ------------------------------------------------------------------
    # Button state transitions — proves the methods we wired exist
    # ------------------------------------------------------------------

    def test_50_start_pause_finish_transitions(self):
        """The kanban buttons call native button_start / button_pending /
        button_finish. Drive a minimal WO through that sequence and
        assert the state flips at each step.

        Catches the failure mode where a future Odoo update renames a
        button — the kanban template would render but the buttons
        would 404 in production.
        """
        mo = self._build_minimal_mo()
        wo = mo.workorder_ids[:1]
        self.assertTrue(wo, "Minimal MO must produce a WO")

        # MO action_confirm should land the first WO in 'ready'.
        self.assertEqual(wo.state, "ready",
                         f"Expected ready, got {wo.state}")

        # button_start → progress
        wo.button_start()
        self.assertEqual(wo.state, "progress",
                         f"After button_start, got {wo.state}")

        # button_pending → progress remains (it's a "pause" signal that
        # stops the user-timer; native button doesn't transition state
        # back to ready in v19, so we just assert it doesn't raise and
        # state is still progress).
        wo.button_pending()
        self.assertEqual(wo.state, "progress",
                         f"After button_pending, got {wo.state}")

        # button_finish → done
        # qty_producing must be set or button_finish raises.
        wo.qty_producing = wo.qty_production or 1.0
        wo.button_finish()
        self.assertEqual(wo.state, "done",
                         f"After button_finish, got {wo.state}")
