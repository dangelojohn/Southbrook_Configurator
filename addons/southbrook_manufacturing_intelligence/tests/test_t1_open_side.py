# SPDX-License-Identifier: LGPL-3.0-only
"""T1 — Open-side MI rule.

When the flag is ON and the source order line carries no Finished Sides
pick (or "None"), MI fires a warning-severity check. Left/Right/Both
suppress it. Flag OFF -> behaviour byte-identical to pre-T1.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "mi", "t1",
        "open_side_detection")
class TestT1OpenSide(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Engine = cls.env["southbrook.mi.engine"]
        cls.Check = cls.env["southbrook.mi.check"]
        cls.Tmpl = cls.env["product.template"]
        cls.Attribute = cls.env["product.attribute"]
        cls.AttributeValue = cls.env["product.attribute.value"]
        cls.TmplAttrLine = cls.env["product.template.attribute.line"]
        cls.MO = cls.env["mrp.production"]
        cls.SaleOrder = cls.env["sale.order"]
        cls.Partner = cls.env["res.partner"].create({"name": "T1 customer"})

    def _set_flag(self, val):
        self.env["ir.config_parameter"].sudo().set_param(
            "southbrook_manufacturing_intelligence.detect_open_sides", val,
        )

    def _make_so_with_finished_sides(self, value_name):
        """Create a sale order + MO with the named Finished Sides value."""
        tmpl = self.Tmpl.create({
            "name": f"T1 cabinet ({value_name})",
            "type": "consu", "is_storable": True,
        })
        fs_attr = self.Attribute.create({
            "name": "Finished Sides", "create_variant": "always"})
        fs_val = self.AttributeValue.create({
            "name": value_name, "attribute_id": fs_attr.id})
        self.TmplAttrLine.create({
            "product_tmpl_id": tmpl.id,
            "attribute_id": fs_attr.id,
            "value_ids": [(6, 0, [fs_val.id])],
        })
        tmpl._create_variant_ids()
        variant = tmpl.product_variant_id

        so = self.SaleOrder.create({
            "partner_id": self.Partner.id,
            "order_line": [(0, 0, {
                "product_id": variant.id,
                "product_uom_qty": 1.0,
            })],
        })
        line = so.order_line[0]
        mo = self.MO.create({
            "product_id": variant.id, "product_qty": 1.0,
            "sale_line_id": line.id, "origin": so.name,
        })
        return mo

    # ------------------------------------------------------------------
    # Acceptance — flag OFF: no warning regardless
    # ------------------------------------------------------------------
    def test_flag_off_no_warning(self):
        self._set_flag("False")
        mo = self._make_so_with_finished_sides("None")
        self.Engine._recompute_production(mo)
        warnings = self.Check.search([
            ("production_id", "=", mo.id),
            ("name", "=", "Possible open cabinet side"),
        ])
        self.assertFalse(warnings, "flag OFF must not fire the warning")

    # ------------------------------------------------------------------
    # Acceptance — flag ON + None: warning fires
    # ------------------------------------------------------------------
    def test_flag_on_none_fires_warning(self):
        self._set_flag("True")
        mo = self._make_so_with_finished_sides("None")
        self.Engine._recompute_production(mo)
        warnings = self.Check.search([
            ("production_id", "=", mo.id),
            ("name", "=", "Possible open cabinet side"),
            ("severity", "=", "warning"),
            ("category", "=", "assembly"),
        ])
        self.assertEqual(
            len(warnings), 1,
            "flag ON + Finished Sides=None must fire one warning")

    # ------------------------------------------------------------------
    # Acceptance — flag ON + Both: warning suppressed
    # ------------------------------------------------------------------
    def test_flag_on_both_no_warning(self):
        self._set_flag("True")
        mo = self._make_so_with_finished_sides("Both")
        self.Engine._recompute_production(mo)
        warnings = self.Check.search([
            ("production_id", "=", mo.id),
            ("name", "=", "Possible open cabinet side"),
        ])
        self.assertFalse(
            warnings,
            "Finished Sides=Both covers the visible faces — no warning")

    def test_flag_on_left_no_warning(self):
        self._set_flag("True")
        mo = self._make_so_with_finished_sides("Left")
        self.Engine._recompute_production(mo)
        warnings = self.Check.search([
            ("production_id", "=", mo.id),
            ("name", "=", "Possible open cabinet side"),
        ])
        self.assertFalse(warnings)
