# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for the CE-native requirements planner.

The first test is the one that matters: it encodes the exact defect that
made the vendor engine useless here — a non-storable, made-to-order
finished good must still generate a requirement. Against
``openvalue_mrp_planning_demand`` this scenario yields zero lines, because
its demand query filters on ``product_id.is_storable``.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook_planning")
class TestSouthbrookPlanning(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.env.company.id)], limit=1)
        cls.partner = cls.env["res.partner"].create({"name": "Planning Test Co"})

        # A cabinet modelled the way Southbrook actually models them:
        # consumable, NOT stock-tracked.
        cls.cabinet = cls.env["product.product"].create({
            "name": "TEST Base Cabinet (non-storable)",
            "type": "consu",
            "is_storable": False,
        })
        # A stock-tracked component.
        cls.panel = cls.env["product.product"].create({
            "name": "TEST Side Panel",
            "type": "consu",
            "is_storable": True,
        })
        cls.env["mrp.bom"].create({
            "product_tmpl_id": cls.cabinet.product_tmpl_id.id,
            "product_qty": 1.0,
            "type": "normal",
            "bom_line_ids": [(0, 0, {
                "product_id": cls.panel.id,
                "product_qty": 2.0,
            })],
        })

    def _confirmed_order(self, product, qty):
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": product.id,
                "product_uom_qty": qty,
            })],
        })
        order.action_confirm()
        return order

    def _run(self, **kw):
        vals = {"warehouse_id": self.warehouse.id}
        vals.update(kw)
        run = self.env["southbrook.planning.run"].create(vals)
        run.action_compute()
        return run

    def test_non_storable_finished_good_generates_requirement(self):
        """The defect this module exists to fix.

        A non-storable cabinet on a confirmed order must produce a
        requirement. The vendor engine returns nothing here.
        """
        self._confirmed_order(self.cabinet, 3.0)
        run = self._run()
        cabinet_lines = run.line_ids.filtered(
            lambda l: l.product_id == self.cabinet)
        self.assertTrue(
            cabinet_lines,
            "A non-storable made-to-order finished good must still generate a "
            "planning requirement; this is precisely what the vendor engine "
            "filtered out via is_storable.")
        self.assertEqual(cabinet_lines.gross_qty, 3.0)
        self.assertEqual(
            cabinet_lines.supply_qty, 0.0,
            "A non-storable product has no stock balance to net against.")
        self.assertEqual(cabinet_lines.net_qty, 3.0)
        self.assertEqual(cabinet_lines.supply_type, "manufacture")
        self.assertTrue(cabinet_lines.is_independent)

    def test_bom_explosion_creates_dependent_demand(self):
        """Components are pulled through the BoM at the right multiple."""
        self._confirmed_order(self.cabinet, 3.0)
        run = self._run()
        panel_lines = run.line_ids.filtered(
            lambda l: l.product_id == self.panel)
        self.assertTrue(panel_lines, "BoM component must appear as demand.")
        self.assertEqual(
            panel_lines.gross_qty, 6.0,
            "3 cabinets x 2 panels each = 6 panels required.")
        self.assertFalse(
            panel_lines.is_independent,
            "Component demand is dependent, not independent.")

    def test_available_stock_nets_off_component_demand(self):
        """On-hand stock reduces a storable component's net requirement."""
        self.env["stock.quant"]._update_available_quantity(
            self.panel, self.warehouse.lot_stock_id, 4.0)
        self._confirmed_order(self.cabinet, 3.0)
        run = self._run()
        panel_lines = run.line_ids.filtered(
            lambda l: l.product_id == self.panel)
        self.assertEqual(panel_lines.gross_qty, 6.0)
        self.assertEqual(panel_lines.supply_qty, 4.0)
        self.assertEqual(
            panel_lines.net_qty, 2.0,
            "6 required less 4 on hand should leave 2 to supply.")

    def test_fully_covered_component_is_omitted(self):
        """Nothing to do means no line — the plan lists actions, not facts."""
        self.env["stock.quant"]._update_available_quantity(
            self.panel, self.warehouse.lot_stock_id, 50.0)
        self._confirmed_order(self.cabinet, 1.0)
        run = self._run()
        self.assertFalse(
            run.line_ids.filtered(lambda l: l.product_id == self.panel),
            "A component already covered by stock should not be listed.")

    def test_draft_orders_are_not_demand(self):
        """Only confirmed orders drive the plan."""
        self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": self.cabinet.id,
                "product_uom_qty": 5.0,
            })],
        })  # deliberately left in draft
        run = self._run()
        self.assertFalse(
            run.line_ids,
            "A quotation is not demand until it is confirmed.")

    def test_run_writes_nothing_to_mrp(self):
        """Computing a plan must not create manufacturing orders."""
        self._confirmed_order(self.cabinet, 2.0)
        before = self.env["mrp.production"].search_count([])
        self._run()
        self.assertEqual(
            self.env["mrp.production"].search_count([]), before,
            "Computing requirements must be side-effect free; MOs appear only "
            "on explicit release.")

    def test_recompute_preserves_released_lines(self):
        """Recomputing must not delete a released line.

        A released line is the audit record of work actually put into the
        system, and it is pointed at by a live MO. Wiping it on recompute
        loses that trail.
        """
        self._confirmed_order(self.cabinet, 3.0)
        run = self._run()
        line = run.line_ids.filtered(lambda l: l.product_id == self.cabinet)
        line.action_release()
        released_id = line.id
        mo = line.generated_ref
        run.action_compute()
        surviving = run.line_ids.filtered(lambda l: l.id == released_id)
        self.assertTrue(
            surviving,
            "A released line must survive recompute — it is the record that "
            "this requirement was actioned.")
        self.assertEqual(surviving.generated_ref, mo)

    def test_released_production_is_not_planned_twice(self):
        """The over-production guard.

        Release 3 cabinets, then let a further order for 2 arrive. Gross
        demand becomes 5, but 3 are already being built, so only 2 more
        should be proposed. Without netting against open MOs this proposed 5
        again and released 8 units of work for 5 units of demand.
        """
        self._confirmed_order(self.cabinet, 3.0)
        run = self._run()
        run.line_ids.filtered(
            lambda l: l.product_id == self.cabinet).action_release()

        self._confirmed_order(self.cabinet, 2.0)
        run2 = self._run()
        proposal = run2.line_ids.filtered(
            lambda l: l.product_id == self.cabinet and not l.released)
        self.assertTrue(proposal, "The 2 extra units should be proposed.")
        self.assertEqual(
            proposal.net_qty, 2.0,
            "3 of the 5 required cabinets are already on an open MO, so only "
            "2 more may be proposed.")
        self.assertEqual(
            proposal.supply_qty, 3.0,
            "Open manufacturing orders are the supply signal for a "
            "non-storable product.")

    def test_release_creates_manufacturing_order(self):
        """Releasing a manufacture line creates exactly one MO, once."""
        self._confirmed_order(self.cabinet, 2.0)
        run = self._run()
        line = run.line_ids.filtered(lambda l: l.product_id == self.cabinet)
        line.action_release()
        self.assertTrue(line.released)
        self.assertTrue(line.generated_ref)
        self.assertEqual(line.generated_ref._name, "mrp.production")
        self.assertEqual(line.generated_ref.product_qty, 2.0)
        # Idempotent: releasing again must not create a second document.
        first = line.generated_ref
        line.action_release()
        self.assertEqual(
            line.generated_ref, first,
            "Re-releasing a line must be a no-op, not a duplicate order.")
