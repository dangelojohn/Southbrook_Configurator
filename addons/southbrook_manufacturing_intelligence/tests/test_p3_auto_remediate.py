# SPDX-License-Identifier: LGPL-3.0-only
"""P3 — MI auto-creates the cutlist it currently only requests.

Two flag positions:
  - OFF (default): _recompute_production behaviour is byte-identical
    to the pre-P3 baseline. A MO with no cutlist still fires the
    Missing-cutlist blocker.
  - ON: a MO whose source order line carries a complete configuration
    gets the cutlist auto-generated; the blocker doesn't fire, and an
    "Cutlist auto-generated" info check carries the audit note.

Ambiguous configurations — Door Style = "Custom (Signature)" or any
value name containing "Custom" — still produce the blocker even with
the flag ON.

"CAD not complete" warnings are independent and never auto-cleared.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "mi", "p3",
        "auto_remediate_cutlist")
class TestP3AutoRemediate(TransactionCase):

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
        cls.Partner = cls.env["res.partner"].create({"name": "P3 customer"})

    def _set_flag(self, value):
        self.env["ir.config_parameter"].sudo().set_param(
            "southbrook_manufacturing_intelligence.auto_remediate_cutlist",
            value,
        )

    def _attr(self, name, values):
        a = self.Attribute.create({"name": name, "create_variant": "always"})
        vals = [
            self.AttributeValue.create({"name": v, "attribute_id": a.id})
            for v in values
        ]
        return a, vals

    def _make_configured_3drawer(self, width="24 in", door_style=None):
        tmpl = self.Tmpl.create({
            "name": "P3 — 3-Drawer Test",
            "type": "consu", "is_storable": True,
        })
        width_attr, width_vals = self._attr("Width", [width])
        cons_attr, cons_vals = self._attr(
            "Drawer Construction", ["3-Drawer Stack (Dovetail)"])
        fam_attr, fam_vals = self._attr("Family", ["Drawer Base"])
        lines = [
            (width_attr, width_vals),
            (cons_attr, cons_vals),
            (fam_attr, fam_vals),
        ]
        if door_style is not None:
            ds_attr, ds_vals = self._attr("Door Style", [door_style])
            lines.append((ds_attr, ds_vals))
        for attr, vals in lines:
            self.TmplAttrLine.create({
                "product_tmpl_id": tmpl.id,
                "attribute_id": attr.id,
                "value_ids": [(6, 0, [v.id for v in vals])],
            })
        tmpl._create_variant_ids()
        return tmpl, tmpl.product_variant_id

    def _make_so_with_mo(self, variant):
        so = self.SaleOrder.create({
            "partner_id": self.Partner.id,
            "order_line": [(0, 0, {
                "product_id": variant.id,
                "product_uom_qty": 1.0,
            })],
        })
        line = so.order_line[0]
        mo = self.MO.create({
            "product_id": variant.id,
            "product_qty": 1.0,
            "sale_line_id": line.id,
            "origin": so.name,
        })
        return so, line, mo

    # ------------------------------------------------------------------
    # Acceptance — flag OFF: legacy blocker behavior preserved
    # ------------------------------------------------------------------
    def test_flag_off_fires_missing_cutlist_blocker(self):
        self._set_flag("False")
        _, variant = self._make_configured_3drawer()
        _, _, mo = self._make_so_with_mo(variant)
        self.Engine._recompute_production(mo)
        blockers = self.Check.search([
            ("production_id", "=", mo.id),
            ("name", "=", "Missing cutlist"),
            ("severity", "=", "blocker"),
        ])
        self.assertTrue(blockers, "flag OFF must preserve legacy blocker")

    # ------------------------------------------------------------------
    # Acceptance — flag ON + complete config: blocker absent, info present
    # ------------------------------------------------------------------
    def test_flag_on_complete_config_self_heals(self):
        self._set_flag("True")
        _, variant = self._make_configured_3drawer(door_style="Shaker")
        _, _, mo = self._make_so_with_mo(variant)
        self.Engine._recompute_production(mo)
        blockers = self.Check.search([
            ("production_id", "=", mo.id),
            ("name", "=", "Missing cutlist"),
            ("severity", "=", "blocker"),
        ])
        self.assertFalse(
            blockers,
            "P3 must self-heal Missing cutlist when source config is complete")
        info_checks = self.Check.search([
            ("production_id", "=", mo.id),
            ("severity", "=", "info"),
            ("category", "=", "cut"),
        ])
        self.assertTrue(
            info_checks,
            "auto-generated cutlist must leave an audit-note info check")
        self.assertIn("audit P3", (info_checks[0].message or "").lower(),
                      "audit note must reference P3 for traceability")

    # ------------------------------------------------------------------
    # Acceptance — ambiguous config (Custom Signature) still blocks
    # ------------------------------------------------------------------
    def test_ambiguous_custom_config_still_blocks(self):
        self._set_flag("True")
        # "Custom (Signature)" door style is the audit's canonical
        # ambiguity case — the resolver can't safely fill in joinery
        # for a custom signature door.
        _, variant = self._make_configured_3drawer(
            door_style="Custom (Signature)")
        _, _, mo = self._make_so_with_mo(variant)
        self.Engine._recompute_production(mo)
        blockers = self.Check.search([
            ("production_id", "=", mo.id),
            ("name", "=", "Missing cutlist"),
            ("severity", "=", "blocker"),
        ])
        self.assertTrue(
            blockers,
            "ambiguous Custom Signature config must still block, even ON")
