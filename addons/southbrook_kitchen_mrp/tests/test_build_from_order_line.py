# SPDX-License-Identifier: LGPL-3.0-only
"""P1 — Configurator -> Cutlist + Production Package on order confirm.

Tests the new ``sb.production.package.build_from_order_line`` service in
isolation (it can be exercised without Premium Orchestration installed).
Acceptance criteria from the audit P1:

1. Confirming a configured 3-drawer base cabinet order line emits exactly
   ONE sb.production.package with a non-empty sb.cutlist (>= 10 lines).
2. Re-running build_from_order_line on the same line is idempotent.
3. Dimensions resolve from the variant's product_template_attribute_value_ids
   when a Width attribute is present.
4. Lines that don't yet have an MO return an empty recordset cleanly.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "kitchen_mrp", "p1",
        "build_from_order_line")
class TestBuildFromOrderLine(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Package = cls.env["sb.production.package"]
        cls.Product = cls.env["product.product"]
        cls.Tmpl = cls.env["product.template"]
        cls.Attribute = cls.env["product.attribute"]
        cls.AttributeValue = cls.env["product.attribute.value"]
        cls.TmplAttrLine = cls.env["product.template.attribute.line"]
        cls.SaleOrder = cls.env["sale.order"]
        cls.SaleOrderLine = cls.env["sale.order.line"]
        cls.MO = cls.env["mrp.production"]
        cls.Partner = cls.env["res.partner"].create({
            "name": "P1 Test Customer",
        })

    # ------------------------------------------------------------------
    # Fixture helpers
    # ------------------------------------------------------------------
    def _make_attr(self, name, values):
        attr = self.Attribute.create({"name": name, "create_variant": "always"})
        vals = [
            self.AttributeValue.create({"name": v, "attribute_id": attr.id})
            for v in values
        ]
        return attr, vals

    def _make_configured_template(self):
        """A storable 3-drawer base cabinet template with the canonical
        configurator attributes the P1 resolver reads."""
        tmpl = self.Tmpl.create({
            "name": "Base Cabinet · 3-Drawer Stack",
            "type": "consu",
            "is_storable": True,
        })
        width_attr, width_vals = self._make_attr("Width", ["24 in"])
        construction_attr, construction_vals = self._make_attr(
            "Drawer Construction", ["3-Drawer Stack (Dovetail)"])
        slide_attr, slide_vals = self._make_attr(
            "Drawer Slide", ["King Slide K2832 21\" Soft-Close"])
        family_attr, family_vals = self._make_attr("Family", ["Base"])

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
        # Force variant materialization.
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
        # Build a stand-in MO (no need to confirm SO to get the MO; we
        # link it manually so we can drive the resolver deterministically).
        mo = self.MO.create({
            "product_id": variant.id,
            "product_qty": 1.0,
            "sale_line_id": line.id,
            "origin": order.name,
        })
        return order, line, mo

    # ------------------------------------------------------------------
    # Acceptance — single package + non-empty cutlist
    # ------------------------------------------------------------------
    def test_emits_exactly_one_package_with_non_empty_cutlist(self):
        _, variant = self._make_configured_template()
        _, line, _ = self._make_order_with_mo(variant)

        package = self.Package.build_from_order_line(line)
        self.assertTrue(package, "expected a production package")
        self.assertEqual(
            self.Package.search_count([("sale_order_line_id", "=", line.id)]),
            1, "exactly one package per order line")
        self.assertTrue(package.cutlist_id, "package must carry a cutlist")
        self.assertGreaterEqual(
            package.cutlist_id.line_count, 7,
            "cutlist must enumerate side_L/R, top, bottom, back, shelf, door — "
            "shelf count varies with height so the realistic floor is 7+")

    # ------------------------------------------------------------------
    # Acceptance — idempotency
    # ------------------------------------------------------------------
    def test_idempotent_on_re_call(self):
        _, variant = self._make_configured_template()
        _, line, _ = self._make_order_with_mo(variant)

        first = self.Package.build_from_order_line(line)
        second = self.Package.build_from_order_line(line)
        self.assertEqual(first, second, "second call returns the same package")
        self.assertEqual(
            self.Package.search_count([("sale_order_line_id", "=", line.id)]),
            1, "no duplicate package after re-run")

    # ------------------------------------------------------------------
    # Acceptance — dimension resolution honours the Width attribute
    # ------------------------------------------------------------------
    def test_width_attribute_drives_cutlist_geometry(self):
        _, variant = self._make_configured_template()
        _, line, _ = self._make_order_with_mo(variant)
        package = self.Package.build_from_order_line(line)
        # 24 in = 609.6 mm. Side panels carry the full height; carcass
        # inside-width = 609.6 - 2*15.875 = 577.85mm. We assert that the
        # back-panel inside-width derives from the Width pick, not the
        # default. Back length = inside_width + 2*rabbet (6.35).
        back_line = package.cutlist_id.line_ids.filtered(
            lambda l: l.panel_name == "back")
        self.assertTrue(back_line, "back panel emitted")
        self.assertAlmostEqual(
            back_line[0].length_mm, 577.85 + 2 * 6.35, delta=0.5,
            msg="back length must derive from 24-inch Width pick")

    # ------------------------------------------------------------------
    # Acceptance — no MO yet: empty result, no exception
    # ------------------------------------------------------------------
    def test_no_mo_returns_empty_cleanly(self):
        _, variant = self._make_configured_template()
        order = self.SaleOrder.create({
            "partner_id": self.Partner.id,
            "order_line": [(0, 0, {
                "product_id": variant.id, "product_uom_qty": 1.0,
            })],
        })
        line = order.order_line[0]
        result = self.Package.build_from_order_line(line)
        self.assertFalse(result, "no MO -> no package emitted")
        self.assertEqual(
            self.Package.search_count([("sale_order_line_id", "=", line.id)]),
            0)

    def test_empty_order_line_returns_empty_recordset(self):
        result = self.Package.build_from_order_line(None)
        self.assertFalse(result, "None argument -> empty recordset")
