# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestMaterialDemandQty(TransactionCase):
    def _make_cabinet_bom(self, weight_source, thickness_mm):
        # NOTE: code suffixed with thickness_mm — the brief's original test
        # calls this helper twice in test_density_volume_demand_is_area_m2
        # (19.05 then 12.70) within the SAME TransactionCase test method, so
        # a fixed "ew_dq"/"sheet_dq" code collided with sb_material_core's
        # unique(code) constraint on material.family/southbrook.kitchen.
        # material. Suffixing keeps both calls unique without changing the
        # test's intent (compare demand across two distinct thicknesses).
        suffix = str(thickness_mm).replace(".", "_")
        fam = self.env["material.family"].create({"name": "EW", "code": f"ew_dq_{suffix}"})
        mat = self.env["southbrook.kitchen.material"].create({
            "name": f"Sheet {suffix}", "code": f"sheet_dq_{suffix}", "family_id": fam.id,
            "density": 0.68, "weight_source": weight_source,
            "thickness_mm": thickness_mm,
        })
        # a cabinet variant carrying real geometry
        tmpl = self.env["product.template"].create({"name": "Cab DQ"})
        variant = tmpl.product_variant_id
        variant.write({
            "sb_width_mm": 600, "sb_height_mm": 720, "sb_depth_mm": 580,
            "sb_panel_family": "base", "sb_door_count": 1, "sb_drawer_count": 0,
            "sb_finished_sides": "none",
        })
        comp = self.env["product.product"].create({"name": "Comp DQ"})
        comp.product_tmpl_id.material_id = mat.id
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": tmpl.id, "product_id": variant.id, "product_qty": 1.0,
        })
        line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": comp.id, "product_qty": 1.0,
        })
        return mat, line

    def test_density_volume_demand_is_area_m2(self):
        mat, line = self._make_cabinet_bom("density_volume", 19.05)
        # area = carcass volume / thickness / 1e6, and must be > 0
        self.assertGreater(line.material_demand_qty, 0.0)
        # thinner sheet, same geometry -> larger area for the same volume share
        mat2, line2 = self._make_cabinet_bom("density_volume", 12.70)
        self.assertGreater(line2.material_demand_qty, line.material_demand_qty)

    def test_per_unit_demand_equals_product_qty(self):
        fam = self.env["material.family"].create({"name": "HW", "code": "hw_dq"})
        mat = self.env["southbrook.kitchen.material"].create({
            "name": "Hinge", "code": "hinge_dq", "family_id": fam.id,
            "weight_source": "per_unit", "weight_per_unit": 0.05,
        })
        tmpl = self.env["product.template"].create({"name": "Cab HW"})
        comp = self.env["product.product"].create({"name": "Comp HW"})
        comp.product_tmpl_id.material_id = mat.id
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": tmpl.id, "product_id": tmpl.product_variant_id.id,
        })
        line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": comp.id, "product_qty": 4.0,
        })
        self.assertEqual(line.material_demand_qty, 4.0)

    def test_no_geometry_is_zero(self):
        mat, line = self._make_cabinet_bom("density_volume", 19.05)
        line.bom_id.product_id.write({"sb_width_mm": 0, "sb_height_mm": 0, "sb_depth_mm": 0})
        line.invalidate_recordset(["material_demand_qty"])
        # recompute
        line._compute_material_demand_qty()
        self.assertEqual(line.material_demand_qty, 0.0)
