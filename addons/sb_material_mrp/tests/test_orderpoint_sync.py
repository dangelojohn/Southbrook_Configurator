# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestOrderpointSync(TransactionCase):
    # NOTE: `mrp.bom.line.material_demand_qty` is a stored *computed* field
    # (see mrp_bom.py `_compute_material_demand_qty`) -- this test fixture
    # writes a known synthetic value directly onto it (no material/geometry
    # is set up here, so the real compute would otherwise fall back to the
    # honest "per_unit" default of `line.product_qty`). That direct write is
    # stable... until a LATER, unrelated `product.template.create()` call
    # elsewhere in the same test re-marks the field "to compute" for
    # already-created lines too (an existing recompute-scoping quirk in the
    # dependency graph, orthogonal to this task's production code -- it
    # reproduces even with a second BoM line on a completely different
    # product). `_cabinet_with_open_mo` therefore returns the line so tests
    # that create more than one cabinet can re-assert the synthetic value
    # right before reading the rollup, once no further templates will be
    # created.
    def _cabinet_with_open_mo(self, comp, qty_per_cab=2.5, mo_qty=3.0):
        cab_tmpl = self.env["product.template"].create(
            {"name": "Cab OP", "is_storable": True})
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": cab_tmpl.id,
            "product_id": cab_tmpl.product_variant_id.id,
            "product_qty": 1.0,
        })
        line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": comp.id, "product_qty": 1.0,
        })
        line.material_demand_qty = qty_per_cab
        mo = self.env["mrp.production"].create({
            "product_id": cab_tmpl.product_variant_id.id,
            "bom_id": bom.id, "product_qty": mo_qty,
        })
        mo.action_confirm()
        return mo, line

    def test_no_open_mo_rollup_is_zero(self):
        comp = self.env["product.product"].create({"name": "Comp OP0", "is_storable": True})
        self.assertEqual(comp.product_tmpl_id._sb_open_mo_material_demand_qty(), 0.0)

    def test_rollup_scales_by_mo_qty(self):
        comp = self.env["product.product"].create({"name": "Comp OP1", "is_storable": True})
        self._cabinet_with_open_mo(comp, qty_per_cab=2.5, mo_qty=3.0)
        # (single cabinet in this test -- no later product.template.create()
        # to re-invalidate the fixture's synthetic override, see the class
        # note above.)
        # 2.5 m2/cabinet * 3 cabinets = 7.5 m2 of open demand
        self.assertAlmostEqual(
            comp.product_tmpl_id._sb_open_mo_material_demand_qty(), 7.5, places=2)

    def test_sync_creates_orderpoint_with_max_from_rollup(self):
        comp = self.env["product.product"].create(
            {"name": "Comp OP2", "is_storable": True, "purchase_ok": True})
        self._cabinet_with_open_mo(comp, qty_per_cab=4.0, mo_qty=2.0)  # 8.0 m2
        wh = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1)
        comp.product_tmpl_id.action_sb_sync_orderpoint_max(warehouse_ids=wh)
        op = self.env["stock.warehouse.orderpoint"].search([
            ("product_id", "=", comp.id), ("warehouse_id", "=", wh.id)])
        self.assertEqual(len(op), 1)
        self.assertEqual(op.product_max_qty, 8.0)
        self.assertEqual(op.product_min_qty, 0.0)  # untouched -- not this task's job

    def test_sync_is_idempotent_and_refreshes_existing_max(self):
        comp = self.env["product.product"].create(
            {"name": "Comp OP3", "is_storable": True, "purchase_ok": True})
        _mo1, line1 = self._cabinet_with_open_mo(comp, qty_per_cab=1.0, mo_qty=1.0)  # 1.0 m2
        wh = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1)
        comp.product_tmpl_id.action_sb_sync_orderpoint_max(warehouse_ids=wh)
        op1 = self.env["stock.warehouse.orderpoint"].search([
            ("product_id", "=", comp.id), ("warehouse_id", "=", wh.id)])
        _mo2, line2 = self._cabinet_with_open_mo(comp, qty_per_cab=5.0, mo_qty=2.0)  # +10.0 m2
        # Re-assert both synthetic overrides -- line1's was just re-marked
        # "to compute" by the product.template.create() inside the second
        # _cabinet_with_open_mo call above (see the class note). No further
        # template will be created after this point in the test.
        line1.material_demand_qty = 1.0
        line2.material_demand_qty = 5.0
        comp.product_tmpl_id.action_sb_sync_orderpoint_max(warehouse_ids=wh)
        op2 = self.env["stock.warehouse.orderpoint"].search([
            ("product_id", "=", comp.id), ("warehouse_id", "=", wh.id)])
        self.assertEqual(op1.id, op2.id)  # same record, not duplicated
        self.assertAlmostEqual(op2.product_max_qty, 11.0, places=2)

    def test_zero_demand_skips_creating_orderpoint(self):
        comp = self.env["product.product"].create({"name": "Comp OP4", "is_storable": True})
        wh = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1)
        comp.product_tmpl_id.action_sb_sync_orderpoint_max(warehouse_ids=wh)
        op = self.env["stock.warehouse.orderpoint"].search([
            ("product_id", "=", comp.id), ("warehouse_id", "=", wh.id)])
        self.assertFalse(op)  # honest: no phantom orderpoint for zero demand
