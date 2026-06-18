# SPDX-License-Identifier: LGPL-3.0-only
"""P2 — Brand-aware Drawer Slide: resolved BoM binds the picked slide.

Acceptance criterion (audit P2): selecting "King Slide K2832 21\"
Soft-Close" causes the resolved hardware package to contain product 458
(KS-K2832-21) at qty = drawer_count. Product 458 is a runtime-assigned
id — we assert via the stable x_marathon_sku field instead.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "kitchen_mrp", "p2",
        "drawer_slide", "brand_aware")
class TestP2DrawerSlide(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Package = cls.env["sb.production.package"]
        cls.Product = cls.env["product.product"]
        cls.Tmpl = cls.env["product.template"]
        cls.Attribute = cls.env["product.attribute"]
        cls.AttributeValue = cls.env["product.attribute.value"]
        cls.TmplAttrLine = cls.env["product.template.attribute.line"]
        cls.MO = cls.env["mrp.production"]
        cls.SaleOrder = cls.env["sale.order"]
        cls.Partner = cls.env["res.partner"].create({
            "name": "P2 Test Customer",
        })

    def _attr(self, name, values):
        attr = self.Attribute.create({"name": name, "create_variant": "always"})
        return attr, [
            self.AttributeValue.create({"name": v, "attribute_id": attr.id})
            for v in values
        ]

    def _make_3drawer_with_k2832(self):
        tmpl = self.Tmpl.create({
            "name": "P2 — 3-Drawer Base Cabinet",
            "type": "consu",
            "is_storable": True,
        })
        width_attr, width_vals = self._attr("Width", ["24 in"])
        construction_attr, construction_vals = self._attr(
            "Drawer Construction", ["3-Drawer Stack (Dovetail)"])
        slide_attr, slide_vals = self._attr(
            "Drawer Slide",
            ["King Slide K2832 21\" Soft-Close"],
        )
        family_attr, family_vals = self._attr("Family", ["Drawer Base"])
        for attr, vals in (
            (width_attr, width_vals),
            (construction_attr, construction_vals),
            (slide_attr, slide_vals),
            (family_attr, family_vals),
        ):
            self.TmplAttrLine.create({
                "product_tmpl_id": tmpl.id,
                "attribute_id": attr.id,
                "value_ids": [(6, 0, [v.id for v in vals])],
            })
        tmpl._create_variant_ids()
        return tmpl, tmpl.product_variant_id

    def _make_order_with_mo(self, variant):
        order = self.SaleOrder.create({
            "partner_id": self.Partner.id,
            "order_line": [(0, 0, {
                "product_id": variant.id,
                "product_uom_qty": 1.0,
            })],
        })
        line = order.order_line[0]
        mo = self.MO.create({
            "product_id": variant.id,
            "product_qty": 1.0,
            "sale_line_id": line.id,
            "origin": order.name,
        })
        return order, line, mo

    # ------------------------------------------------------------------
    # Acceptance — KS-K2832-21 × 3 binds into the resolved hardware pack
    # ------------------------------------------------------------------
    def test_k2832_slide_binds_into_hardware_package_at_drawer_count(self):
        _, variant = self._make_3drawer_with_k2832()
        _, line, _ = self._make_order_with_mo(variant)

        package = self.Package.build_from_order_line(line)
        self.assertTrue(package, "P1 emitted the package")

        # The resolver substituted the configured slide SKU into per_drawer.
        skus = package.hardware_package_id.line_ids.mapped(
            "product_id.x_marathon_sku")
        self.assertIn(
            "KS-K2832-21", skus,
            "the brand-aware slide must appear in the hardware package — "
            "this is the load-bearing P2 acceptance criterion")
        self.assertNotIn(
            "BLM-MOV-450", skus,
            "the legacy per_drawer default Blum MOVENTO must be displaced "
            "when a King Slide is configured (no double-binding)")

        # Quantity must equal drawer_count (3 for this fixture).
        ks_line = package.hardware_package_id.line_ids.filtered(
            lambda l: l.product_id.x_marathon_sku == "KS-K2832-21")
        self.assertEqual(
            ks_line.qty, 3,
            "King Slide K2832 binds at qty = drawer_count (3)")

    # ------------------------------------------------------------------
    # Regression — no slide pick leaves the legacy default untouched
    # ------------------------------------------------------------------
    def test_no_slide_pick_keeps_legacy_blm_movento(self):
        # A 3-drawer template without a Drawer Slide attribute falls
        # back to the per_drawer default in the hardware_map JSON.
        tmpl = self.Tmpl.create({
            "name": "P2 — 3-Drawer Cabinet (no slide attr)",
            "type": "consu", "is_storable": True,
        })
        width_attr, width_vals = self._attr("Width", ["24 in"])
        construction_attr, construction_vals = self._attr(
            "Drawer Construction", ["3-Drawer Stack (Dovetail)"])
        family_attr, family_vals = self._attr("Family", ["Drawer Base"])
        for attr, vals in (
            (width_attr, width_vals),
            (construction_attr, construction_vals),
            (family_attr, family_vals),
        ):
            self.TmplAttrLine.create({
                "product_tmpl_id": tmpl.id,
                "attribute_id": attr.id,
                "value_ids": [(6, 0, [v.id for v in vals])],
            })
        tmpl._create_variant_ids()
        variant = tmpl.product_variant_id
        _, line, _ = self._make_order_with_mo(variant)

        package = self.Package.build_from_order_line(line)
        skus = package.hardware_package_id.line_ids.mapped(
            "product_id.x_marathon_sku")
        # Legacy default still wins when no slide is configured.
        self.assertIn("BLM-MOV-450", skus,
                      "no Drawer Slide picked -> legacy default stands")
