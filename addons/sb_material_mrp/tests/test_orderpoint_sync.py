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

    # ------------------------------------------------------------------
    # I-2 fix (final review, 2026-07-26) -- MAX must never be written in
    # the wrong dimension when the component's purchase UoM has no common
    # reference with its material's canonical (m2/m) demand unit.
    # ------------------------------------------------------------------

    def test_max_native_conversion_when_material_uom_compatible(self):
        # Case 2: material resolves AND the component's own UoM genuinely
        # shares a reference with the canonical m2 unit -- real native
        # conversion, resolved, MAX in that UoM (existing-style behavior,
        # now exercised with a material actually set).
        fam = self.env["material.family"].create({"name": "OPY2", "code": "opy2_test"})
        mat = self.env["southbrook.kitchen.material"].create({
            "name": "OPY2 Mat", "code": "opy2_mat", "family_id": fam.id,
            "density": 0.68, "weight_source": "density_volume", "thickness_mm": 19.05,
        })
        sqft = self.env.ref("uom.product_uom_square_foot")
        comp_tmpl = self.env["product.template"].create({
            "name": "Comp OPY2", "is_storable": True, "purchase_ok": True,
            "uom_id": sqft.id,
        })
        comp_tmpl.material_id = mat.id
        comp = comp_tmpl.product_variant_id
        self._cabinet_with_open_mo(comp, qty_per_cab=2.0, mo_qty=1.0)  # 2.0 m2 demand
        wh = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1)
        comp_tmpl.action_sb_sync_orderpoint_max(warehouse_ids=wh)
        op = self.env["stock.warehouse.orderpoint"].search([
            ("product_id", "=", comp.id), ("warehouse_id", "=", wh.id)])
        self.assertEqual(len(op), 1)
        # 2.0 m2 -> ft2 native conversion (~21.5278) -> ceil 22.
        self.assertEqual(op.product_max_qty, 22.0)

    def test_max_yield_aware_when_uom_incompatible(self):
        # Case 3 (the bug scenario): material resolves, component's own
        # UoM (default Units) shares NO reference with canonical m2, but a
        # vendor uom_yield_qty is recorded -- MAX = CEIL(demand/yield) in
        # purchase units, NOT the raw un-converted m2 number.
        fam = self.env["material.family"].create({"name": "OPY1", "code": "opy1_test"})
        mat = self.env["southbrook.kitchen.material"].create({
            "name": "OPY1 Mat", "code": "opy1_mat", "family_id": fam.id,
            "density": 0.68, "weight_source": "density_volume", "thickness_mm": 19.05,
        })
        vendor = self.env["res.partner"].create({"name": "OPY1 Vendor"})
        comp = self.env["product.product"].create(
            {"name": "Comp OPY1", "is_storable": True, "purchase_ok": True})
        comp.product_tmpl_id.material_id = mat.id
        self.env["product.supplierinfo"].create({
            "partner_id": vendor.id, "product_tmpl_id": comp.product_tmpl_id.id,
            "price": 40.0, "uom_yield_qty": 2.973})
        self._cabinet_with_open_mo(comp, qty_per_cab=7.5, mo_qty=1.0)  # 7.5 m2 demand
        wh = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1)
        comp.product_tmpl_id.action_sb_sync_orderpoint_max(warehouse_ids=wh)
        op = self.env["stock.warehouse.orderpoint"].search([
            ("product_id", "=", comp.id), ("warehouse_id", "=", wh.id)])
        self.assertEqual(len(op), 1)
        # CEIL(7.5 / 2.973) = CEIL(2.5227...) = 3.0 -- NOT 8.0 (the naive
        # ceil of the raw un-converted m2 number the pre-fix code wrote).
        self.assertEqual(op.product_max_qty, 3.0)

    def test_max_skipped_when_uom_incompatible_and_no_yield(self):
        # No common UoM reference AND no vendor yield recorded -- honesty
        # contract: never fabricate a MAX. A pre-existing orderpoint's MAX
        # must be left untouched, and no new orderpoint is created when
        # none existed.
        fam = self.env["material.family"].create({"name": "OPY0", "code": "opy0_test"})
        mat = self.env["southbrook.kitchen.material"].create({
            "name": "OPY0 Mat", "code": "opy0_mat", "family_id": fam.id,
            "density": 0.68, "weight_source": "density_volume", "thickness_mm": 19.05,
        })
        comp = self.env["product.product"].create(
            {"name": "Comp OPY0", "is_storable": True, "purchase_ok": True})
        comp.product_tmpl_id.material_id = mat.id
        self._cabinet_with_open_mo(comp, qty_per_cab=7.5, mo_qty=1.0)  # 7.5 m2, no yield
        wh = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1)
        op = self.env["stock.warehouse.orderpoint"].create({
            "product_id": comp.id, "location_id": wh.lot_stock_id.id,
            "warehouse_id": wh.id, "company_id": wh.company_id.id,
            "product_min_qty": 0.0, "product_max_qty": 1.0,
        })
        comp.product_tmpl_id.action_sb_sync_orderpoint_max(warehouse_ids=wh)
        op2 = self.env["stock.warehouse.orderpoint"].search([
            ("product_id", "=", comp.id), ("warehouse_id", "=", wh.id)])
        self.assertEqual(len(op2), 1)
        self.assertEqual(op2.id, op.id)
        self.assertEqual(
            op2.product_max_qty, 1.0,
            "MAX must stay untouched, never a fabricated dimensionally-"
            "wrong number, when neither a compatible UoM nor a vendor "
            "yield is available",
        )

    def test_max_skipped_creates_no_orderpoint_when_none_existed(self):
        # Same unresolved scenario as above, but with NO pre-existing
        # orderpoint -- must create nothing (no phantom orderpoint with a
        # fabricated MAX).
        fam = self.env["material.family"].create({"name": "OPY0B", "code": "opy0b_test"})
        mat = self.env["southbrook.kitchen.material"].create({
            "name": "OPY0B Mat", "code": "opy0b_mat", "family_id": fam.id,
            "density": 0.68, "weight_source": "density_volume", "thickness_mm": 19.05,
        })
        comp = self.env["product.product"].create(
            {"name": "Comp OPY0B", "is_storable": True, "purchase_ok": True})
        comp.product_tmpl_id.material_id = mat.id
        self._cabinet_with_open_mo(comp, qty_per_cab=7.5, mo_qty=1.0)
        wh = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1)
        comp.product_tmpl_id.action_sb_sync_orderpoint_max(warehouse_ids=wh)
        op = self.env["stock.warehouse.orderpoint"].search([
            ("product_id", "=", comp.id), ("warehouse_id", "=", wh.id)])
        self.assertFalse(op)
