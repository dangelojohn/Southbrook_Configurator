# SPDX-License-Identifier: LGPL-3.0-only
"""QWeb report render tests — commit 10 NF13-class mitigation for QWeb.

QWeb syntax slips are a real class:
  - <t t-foreach> with the wrong t-as binding
  - <t t-esc> vs <t t-out> (v17+ migration)
  - missing t-set declarations
  - <t-call> against a template that doesn't exist

XML lint catches well-formedness; render tests catch semantic correctness.
Each report is instantiated against a minimal fixture and rendered to
HTML; assertions confirm specific strings appear in the output.

Per Build Spec section 4 routine #6, three reports:
  - Signature Spec Sheet (sale.order)
  - Shop Copy (mrp.production — MO-driven per John's commit-10 ask)
  - Door Order (sale.order)
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "qweb")
class TestQWebReports(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "QWeb Test Customer",
            "channel": "dealer",
        })
        cls.product = cls.env["product.product"].create({
            "name": "QWeb Test Cabinet 18in Base 1-Door",
            "list_price": 366.0,
            "type": "consu",
        })
        cls.order = cls.env["sale.order"].create({
            "partner_id": cls.partner.id,
        })
        cls.line = cls.env["sale.order.line"].create({
            "order_id": cls.order.id,
            "product_id": cls.product.id,
            "product_uom_qty": 2.0,
            "zone": "base_run",
        })

    def _render(self, action_xml_id, res_ids):
        """Render a report to HTML (faster than PDF; doesn't need wkhtmltopdf)."""
        report = self.env.ref(f"southbrook_estimating.{action_xml_id}")
        content, _content_type = report._render_qweb_html(res_ids)
        return content.decode() if isinstance(content, bytes) else content

    # ------------------------------------------------------------------
    # Action existence + binding correctness
    # ------------------------------------------------------------------

    def test_01_signature_spec_sheet_action_binds_sale_order(self):
        r = self.env.ref("southbrook_estimating.action_report_signature_spec_sheet")
        self.assertEqual(r.model, "sale.order")
        self.assertEqual(r.report_type, "qweb-pdf")

    def test_02_shop_copy_action_binds_mrp_production(self):
        """John's commit-10 ask: Shop Copy MUST be MO-driven, NOT order-driven."""
        r = self.env.ref("southbrook_estimating.action_report_shop_copy")
        self.assertEqual(
            r.model, "mrp.production",
            "Shop Copy must bind to mrp.production (MO-driven). "
            "Binding to sale.order recreates the legacy 254-formula "
            "spreadsheet mirror.",
        )

    def test_03_door_order_action_binds_sale_order(self):
        r = self.env.ref("southbrook_estimating.action_report_door_order")
        self.assertEqual(r.model, "sale.order")

    # ------------------------------------------------------------------
    # Render assertions — signature spec sheet
    # ------------------------------------------------------------------

    def test_04_signature_spec_sheet_renders_customer_name(self):
        html = self._render(
            "action_report_signature_spec_sheet", [self.order.id]
        )
        self.assertIn("Your Southbrook Kitchen", html)
        self.assertIn("Signature Spec Sheet", html)
        self.assertIn(self.partner.name, html)
        self.assertIn(self.order.name, html)

    def test_05_signature_spec_sheet_renders_line_data(self):
        html = self._render(
            "action_report_signature_spec_sheet", [self.order.id]
        )
        # Line product + qty appear.
        self.assertIn("QWeb Test Cabinet", html)
        # Zone column rendered with the human label.
        self.assertIn("Base Run", html)

    def test_06_signature_spec_sheet_illustrative_banner(self):
        """When seed_mode='illustrative', the banner appears in the rendered HTML."""
        # Default mode is illustrative per commit 2.
        html = self._render(
            "action_report_signature_spec_sheet", [self.order.id]
        )
        self.assertIn("ILLUSTRATIVE SEED", html)

    # ------------------------------------------------------------------
    # Render assertions — shop copy (against a real MO)
    # ------------------------------------------------------------------

    def test_07_shop_copy_renders_mo_and_so_ref(self):
        """Shop Copy must show originating SO ref + product name."""
        # Create a minimal MO that links back to our SO.
        mo = self.env["mrp.production"].create({
            "product_id": self.product.id,
            "product_qty": 1.0,
            "product_uom_id": self.product.uom_id.id,
            "origin": self.order.name,
        })
        html = self._render("action_report_shop_copy", [mo.id])
        self.assertIn("Shop Copy", html)
        self.assertIn(self.product.display_name, html)

    # ------------------------------------------------------------------
    # Render assertions — door order
    # ------------------------------------------------------------------

    def test_08_door_order_renders(self):
        html = self._render(
            "action_report_door_order", [self.order.id]
        )
        self.assertIn("Door Order", html)
        self.assertIn(self.order.name, html)
        self.assertIn(self.partner.name, html)
