# SPDX-License-Identifier: LGPL-3.0-only
"""KD flat-pack export tests."""
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "dealer_portal", "kd_export")
class TestKdExport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ProductionPackage = cls.env["sb.production.package"]
        product = cls.env["product.product"].create({
            "name": "Test cabinet for KD",
            "type": "consu", "is_storable": True,
        })
        cls.env["mrp.bom"].create({
            "product_tmpl_id": product.product_tmpl_id.id, "product_qty": 1.0,
        })
        cls.mo = cls.env["mrp.production"].create({
            "product_id": product.id, "product_qty": 1.0,
        })
        cls.package = cls.ProductionPackage.generate_from_mo(
            cls.mo, 600, 720, 580, "base", 2, 0, soft_close=True,
        )

    def test_export_envelope_schema(self):
        envelope = self.package.export_kd_envelope()
        self.assertEqual(envelope["schema"], "southbrook.kd_flatpack.v1")
        self.assertEqual(envelope["production_package_id"], self.package.id)

    def test_export_includes_all_panels(self):
        envelope = self.package.export_kd_envelope()
        panels = {p["panel_name"] for p in envelope["panels"]}
        self.assertIn("side_L", panels)
        self.assertIn("side_R", panels)
        self.assertIn("top", panels)
        self.assertIn("bottom", panels)
        self.assertIn("back", panels)
        self.assertIn("door", panels)

    def test_predrilled_holes_on_sides_and_top(self):
        envelope = self.package.export_kd_envelope()
        for panel in envelope["panels"]:
            if panel["panel_name"] in ("side_L", "side_R"):
                kinds = {h["kind"] for h in panel["predrilled_holes"]}
                self.assertIn("hinge_cup", kinds,
                              "Sides must have hinge-cup holes for KD")
                self.assertIn("system_line", kinds,
                              "Sides must have 32mm system-line holes")
            elif panel["panel_name"] in ("top", "bottom"):
                kinds = {h["kind"] for h in panel["predrilled_holes"]}
                self.assertIn("cam_lock", kinds,
                              "Top/bottom must have cam-lock corner holes")
            elif panel["panel_name"] == "door":
                kinds = {h["kind"] for h in panel["predrilled_holes"]}
                self.assertIn("hinge_cup", kinds,
                              "Door must have hinge-cup holes")
            elif panel["panel_name"] == "back":
                # Back captures into rabbet — no holes.
                self.assertEqual(panel["predrilled_holes"], [])

    def test_export_includes_hardware(self):
        envelope = self.package.export_kd_envelope()
        self.assertTrue(envelope["hardware"],
                         "KD envelope must include hardware pick list")
        skus = {h["marathon_sku"] for h in envelope["hardware"]}
        self.assertIn("BLM-110-SC", skus, "Soft-close hinges in envelope")

    def test_export_without_cutlist_rejects(self):
        # Package without a cutlist (paranoid edge — generate_from_mo
        # always wires one; build a bare package to test the guard).
        another_mo = self.env["mrp.production"].create({
            "product_id": self.mo.product_id.id, "product_qty": 1.0,
        })
        bare = self.ProductionPackage.create({"mo_id": another_mo.id})
        with self.assertRaises(UserError):
            bare.export_kd_envelope()

    def test_is_kd_variant_flag_writable(self):
        self.package.is_kd_variant = True
        self.assertTrue(self.package.is_kd_variant)
