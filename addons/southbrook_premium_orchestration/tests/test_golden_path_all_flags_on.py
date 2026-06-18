# SPDX-License-Identifier: LGPL-3.0-only
"""Golden-path TransactionCase — P1 + P2 + P3 + P5 acceptance end-to-end.

Configure a 3-drawer base cabinet with King Slide K2832 21" Soft-Close,
confirm the order with both feature flags ON, then assert:

  (a) a production package + cutlist exist for the configured line.
  (b) the resolved hardware package contains KS-K2832-21 x 3
      (the audit's product 458 binding criterion — asserted via the
      stable x_marathon_sku field, not a runtime id).
  (c) the MI engine recompute leaves zero cutlist blockers on the MO.
  (d) the SKU is lossless — a sibling order with Blum MOVENTO 450
      produces a different SKU.

Acceptance is intentionally aggregated rather than split across the
per-task tests because the audit's definition-of-done requires this
exact integration to be green simultaneously.
"""
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.southbrook_configurator_ux.controllers.main import (
    SouthbrookConfiguratorAPI,
)


@tagged("post_install", "-at_install", "southbrook", "premium_orchestration",
        "golden_path", "audit_definition_of_done")
class TestGoldenPathAllFlagsOn(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.api = SouthbrookConfiguratorAPI()
        cls.Engine = cls.env["southbrook.mi.engine"]
        cls.Check = cls.env["southbrook.mi.check"]
        cls.Package = cls.env["sb.production.package"]
        cls.Attribute = cls.env["product.attribute"]
        cls.AttributeValue = cls.env["product.attribute.value"]
        cls.Tmpl = cls.env["product.template"]
        cls.TmplAttrLine = cls.env["product.template.attribute.line"]
        cls.Session = cls.env["product.config.session"]
        cls.SaleOrder = cls.env["sale.order"]
        cls.MO = cls.env["mrp.production"]
        cls.Project = cls.env["project.project"]
        cls.Partner = cls.env["res.partner"].create({
            "name": "Golden Path Customer",
        })
        cls.project = cls.Project.create({"name": "Golden Path Project"})

        # Flags ON for the duration of the test class.
        ICP = cls.env["ir.config_parameter"].sudo()
        ICP.set_param(
            "southbrook_premium.default_kitchen_project_id",
            str(cls.project.id))
        ICP.set_param(
            "southbrook_premium_orchestration.auto_emit_cutlist", "True")
        ICP.set_param(
            "southbrook_manufacturing_intelligence.auto_remediate_cutlist",
            "True")

    def _attr(self, name, values):
        a = self.Attribute.create({"name": name, "create_variant": "always"})
        return a, [
            self.AttributeValue.create({"name": v, "attribute_id": a.id})
            for v in values
        ]

    def _make_template(self, slide_value="King Slide K2832 21\" Soft-Close"):
        tmpl = self.Tmpl.create({
            "name": "Golden — 3-Drawer Base", "type": "consu",
            "is_storable": True,
        })
        width_attr, width_vals = self._attr("Width", ["24 in"])
        series_attr, series_vals = self._attr("Series", ["Contemporary"])
        finish_attr, finish_vals = self._attr("Finish", ["White"])
        cons_attr, cons_vals = self._attr(
            "Drawer Construction", ["3-Drawer Stack (Dovetail)"])
        slide_attr, slide_vals = self._attr("Drawer Slide", [slide_value])
        family_attr, family_vals = self._attr("Family", ["Drawer Base"])
        for attr, vals in (
            (width_attr, width_vals),
            (series_attr, series_vals),
            (finish_attr, finish_vals),
            (cons_attr, cons_vals),
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

    def _confirm_order(self, variant):
        so = self.SaleOrder.create({
            "partner_id": self.Partner.id,
            "order_line": [(0, 0, {
                "product_id": variant.id, "product_uom_qty": 1.0,
            })],
        })
        line = so.order_line[0]
        # Manual MO link so P1 / P3 resolve cleanly without needing a
        # full BoM to drive Odoo's stock-quants pipeline.
        self.MO.create({
            "product_id": variant.id, "product_qty": 1.0,
            "sale_line_id": line.id, "origin": so.name,
        })
        so.action_confirm()
        return so, line

    # ------------------------------------------------------------------
    # Golden path
    # ------------------------------------------------------------------
    def test_definition_of_done(self):
        tmpl_k2832, variant_k2832 = self._make_template(
            slide_value="King Slide K2832 21\" Soft-Close")
        so, line = self._confirm_order(variant_k2832)

        # (a) production package + cutlist exist for the line.
        packages = self.Package.search(
            [("sale_order_line_id", "=", line.id)])
        self.assertEqual(
            len(packages), 1,
            "(a) exactly one production package per configured line")
        self.assertTrue(packages.cutlist_id,
                        "(a) the package carries a cutlist")
        self.assertGreaterEqual(
            packages.cutlist_id.line_count, 5,
            "(a) cutlist enumerates the standard panel set")

        # (b) BoM (hardware package) contains the K2832 slide x 3.
        ks_lines = packages.hardware_package_id.line_ids.filtered(
            lambda ln: ln.product_id.x_marathon_sku == "KS-K2832-21")
        self.assertEqual(
            len(ks_lines), 1,
            "(b) resolved hardware package contains the KS-K2832-21 slide "
            "(audit's product 458 binding criterion)")
        self.assertEqual(
            ks_lines.qty, 3,
            "(b) slide qty = drawer_count = 3")

        # (c) MI run yields zero cutlist blockers on the MO.
        mo = self.MO.search(
            [("sale_line_id", "=", line.id)], limit=1)
        self.Engine._recompute_production(mo)
        cutlist_blockers = self.Check.search([
            ("production_id", "=", mo.id),
            ("category", "=", "cut"),
            ("severity", "=", "blocker"),
        ])
        self.assertFalse(
            cutlist_blockers,
            "(c) MI engine sees zero cutlist blockers — the auto-emitted "
            "cutlist satisfies the rule")

        # (d) SKU is lossless — sibling order with MOVENTO produces a
        # different SKU. (Asserts the P5 grammar extension is active.)
        _, variant_movento = self._make_template(
            slide_value="Blum MOVENTO 450")
        # Sessions for both, picking matching attrs.
        def _session_for(variant):
            session = self.Session.create({
                "product_tmpl_id": variant.product_tmpl_id.id,
                "user_id": self.env.user.id,
            })
            session.value_ids = [(6, 0,
                variant.product_template_attribute_value_ids.mapped(
                    "product_attribute_value_id").ids)]
            return session
        sku_k = self.api._compute_sku_from_session(
            _session_for(variant_k2832))
        sku_b = self.api._compute_sku_from_session(
            _session_for(variant_movento))
        self.assertNotEqual(
            sku_k, sku_b,
            "(d) SKU grammar is lossless — slide brand divergence "
            "produces distinct SKUs")
