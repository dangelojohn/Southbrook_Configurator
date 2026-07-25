# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_material")
class TestRollup(TransactionCase):
    def _material_product(self, name, weight_per_unit):
        """Create a product whose variant resolves to a per_unit material via the
        REAL attribute->material link (Task 4). per_unit avoids any cutlist
        dependency so this test isolates the multi-level rollup.

        DEVIATION from the task-7 brief's literal fixture: the brief used
        `create_variant: "no_variant"` on the attribute. Verified against a
        real Odoo 19 registry that this makes the attribute value a
        sale-order-line-time custom value (`no_variant_attribute_value_ids`),
        never linked onto the variant's own
        `product_template_attribute_value_ids` — so `_resolve_material()`
        (which reads exactly that field, per Task 4) always returns empty
        for a no_variant attribute, regardless of the material link being
        correct. Dropping `create_variant` (defaulting to Odoo's "always")
        makes the single attribute value participate in normal variant
        generation, which is what actually populates
        `product_template_attribute_value_ids` on the variant. This is the
        minimal fixture change needed to prove multi-level explode() rollup
        with a real attribute->material chain; it does not touch any
        production code path.
        """
        mat = self.env["southbrook.kitchen.material"].create(
            {"name": name, "code": name, "weight_source": "per_unit",
             "weight_per_unit": weight_per_unit})
        attr = self.env["product.attribute"].create(
            {"name": "Material-%s" % name})
        val = self.env["product.attribute.value"].create(
            {"name": name, "attribute_id": attr.id, "material_id": mat.id})
        tmpl = self.env["product.template"].create({
            "name": name, "type": "consu",
            "attribute_line_ids": [(0, 0, {
                "attribute_id": attr.id, "value_ids": [(6, 0, [val.id])]})],
        })
        variant = tmpl.product_variant_ids[:1]
        self.assertEqual(variant._resolve_material(), mat)  # link works
        return variant

    def test_multilevel_sums_leaves(self):
        Bom = self.env["mrp.bom"]
        leaf = self._material_product("LEAF", 0.5)          # 0.5 kg per unit
        sub = self.env["product.product"].create({"name": "Sub", "type": "consu"})
        top = self.env["product.product"].create({"name": "Top", "type": "consu"})
        # sub-assembly BoM: 1 x leaf.
        #
        # SECOND DEVIATION from the brief's literal fixture: verified against
        # Odoo 19's real `mrp.bom.explode()` source
        # (odoo/addons/mrp/models/mrp_bom.py) that it only recurses into a
        # sub-component's own BoM when that BoM's `type` is 'phantom' (kit) —
        # `update_product_boms()` hardcodes `bom_type='phantom'` on its
        # `_bom_find()` call. A default `type='normal'` ("Manufacture this
        # product") sub-BoM is intentionally NOT unfolded by native
        # explode() — the sub is treated as its own purchasable/manufacturable
        # component, which is correct Odoo behavior, not a bug. So the
        # sub-assembly BoM here is explicitly `type: "phantom"` — this is
        # what actually exercises multi-level flattening through the real
        # native explode(), matching the brief's stated intent ("explode()
        # must reach the leaf").
        Bom.create({"product_tmpl_id": sub.product_tmpl_id.id, "product_qty": 1.0,
                    "type": "phantom",
                    "bom_line_ids": [(0, 0, {"product_id": leaf.id, "product_qty": 1.0})]})
        # top BoM: 1 x sub  (sub has its own phantom BoM -> explode() must reach the leaf)
        top_bom = Bom.create({"product_tmpl_id": top.product_tmpl_id.id, "product_qty": 1.0,
                    "bom_line_ids": [(0, 0, {"product_id": sub.id, "product_qty": 1.0})]})
        self.assertAlmostEqual(top_bom.material_weight_total, 0.5, places=2)
