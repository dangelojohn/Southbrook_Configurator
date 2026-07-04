# SPDX-License-Identifier: LGPL-3.0-only
"""QA Bug 3 (2026-07-04): the backend sale.order form's inline "3D
Kitchen Preview" tab (get_kitchen_3d_payload) rendered a blank canvas
for orders whose lines were fully configured, priced cabinets.

Root cause: get_kitchen_3d_payload() resolved cabinet geometry purely
from a hardcoded 12-entry SKU lookup table (product_config_line.py
_SKU_DEFAULTS), with no fallback — any line whose product_tmpl_id.
default_code wasn't one of those exact strings was silently skipped
("continue"). Any order made of cabinets from the SEPARATE full-screen
"Open in 3D" configurator's catalog (southbrook_kitchen_3d_configurator,
flagged product.template.southbrook_is_cabinet=True, its own SKU codes)
had every line skipped, leaving an empty scene — even though the lines
were entirely valid and priced. This is a known limitation documented
in southbrook_elearning_internal's own training material.

Fix: fall back to a generic box (mirroring the same "hard defaults when
no SKU match" pattern product_config_line._extract_cabinet_inputs()
already uses for the single-cabinet wizard preview) for any line that's
plausibly a cabinet (southbrook_is_cabinet=True) but isn't one of the
12 hardcoded SB-* SKUs — while still skipping section/note lines and
genuinely non-cabinet products (delivery fees, etc.).
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "kitchen_3d_payload")
class TestKitchen3dPayloadOrder(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "QA Bug3 Test Customer"})
        cls.sb_tmpl = cls.env.ref("southbrook_estimating.base_1dr")

    def _has_is_cabinet_field(self):
        return "southbrook_is_cabinet" in self.env["product.template"]._fields

    def test_recognized_sb_sku_renders_panels(self):
        """Baseline: an order line on one of the 12 hardcoded SB-* SKUs
        must still render panels exactly as before this fix."""
        variant = self.sb_tmpl.product_variant_ids[:1]
        if not variant:
            self.skipTest("base_1dr has no variant available")
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": variant.id,
                "product_uom_qty": 1,
            })],
        })
        payload = order.get_kitchen_3d_payload()
        self.assertTrue(payload.get("panels"),
                         "recognized SB SKU must still render panels")

    def test_other_catalog_cabinet_falls_back_to_generic_box(self):
        """Regression: a product NOT in _SKU_DEFAULTS but flagged
        southbrook_is_cabinet=True (the other configurator's catalog)
        must render a generic box, not be silently skipped."""
        if not self._has_is_cabinet_field():
            self.skipTest(
                "southbrook_kitchen_3d_configurator not installed in "
                "this test run — southbrook_is_cabinet field absent")
        other_tmpl = self.env["product.template"].create({
            "name": "QA Bug3 Other-Catalog Cabinet",
            "default_code": "B24",  # NOT in _SKU_DEFAULTS
            "southbrook_is_cabinet": True,
            "config_ok": False,
            "sale_ok": True,
        })
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": other_tmpl.product_variant_ids[:1].id,
                "product_uom_qty": 1,
            })],
        })
        payload = order.get_kitchen_3d_payload()
        self.assertTrue(
            payload.get("panels"),
            "a southbrook_is_cabinet=True product outside _SKU_DEFAULTS "
            "must still render a generic-box fallback, not be skipped")

    def test_non_cabinet_product_still_skipped(self):
        """Regression companion: an ordinary non-cabinet product (no
        SB-* SKU match, not flagged southbrook_is_cabinet) must NOT
        get a generic box rendered for it — only recognized/cabinet-
        like lines should ever appear in the 3D scene."""
        plain_tmpl = self.env["product.template"].create({
            "name": "QA Bug3 Plain Non-Cabinet Product",
            "default_code": "DELIVERY-FEE",
            "config_ok": False,
            "sale_ok": True,
        })
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": plain_tmpl.product_variant_ids[:1].id,
                "product_uom_qty": 1,
            })],
        })
        payload = order.get_kitchen_3d_payload()
        self.assertFalse(
            payload.get("panels"),
            "a plain non-cabinet product must not render a generic box")

    def test_section_line_still_skipped(self):
        """Section/note lines (display_type set, no product) must never
        be treated as a cabinet-shaped fallback candidate."""
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "display_type": "line_section",
                "name": "QA Bug3 Section Header",
            })],
        })
        payload = order.get_kitchen_3d_payload()
        self.assertFalse(payload.get("panels"))
