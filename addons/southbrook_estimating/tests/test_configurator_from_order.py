# SPDX-License-Identifier: LGPL-3.0-only
"""QA Bug 1 (2026-07-04): launching the Product Configurator from an
existing sales order (the "Configure Product" header button,
action_config_start in product_configurator_sale) must present a
working template picker and never surface a raw ORM ValidationError.

Root cause: action_config_start forced allow_preset_selection=True onto
the very first ("select") screen — a field whose domain is always empty
until a template is chosen, on the SAME screen as the (correctly
working) template picker. If a wizard record is ever created without a
product_id or product_tmpl_id (the DB-level failure mode this masked),
ProductConfigurator.create() used to let `int(vals.get("product_tmpl_id"))`
== int(False) == 0 flow straight into product.config.session.create(),
hitting its NOT NULL constraint and surfacing a raw, uncaught
ValidationError with text like "Missing required value for the field
'Configurable Template' ... Model: 'Product Config Session'".

Two fixes, tested independently:
  * sale_order.py: action_config_start no longer passes
    allow_preset_selection=True.
  * product_configurator.py: ProductConfigurator.create() raises a
    friendly UserError up front when neither product_id nor
    product_tmpl_id is supplied, instead of ever reaching the DB write
    that would violate the NOT NULL constraint.
"""
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "config_from_order")
class TestConfiguratorFromOrder(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmpl = cls.env.ref("southbrook_estimating.base_1dr")
        cls.partner = cls.env["res.partner"].create({
            "name": "QA Bug1 Test Customer"})
        cls.order = cls.env["sale.order"].create({
            "partner_id": cls.partner.id})

    def test_action_config_start_does_not_force_preset_selection(self):
        """Regression: the order-launched wizard action must not carry
        allow_preset_selection=True in its context — that's what put an
        always-empty 'Preset' field on the same screen as the (working)
        template picker."""
        action = self.order.action_config_start()
        ctx = action.get("context") or {}
        self.assertFalse(
            ctx.get("allow_preset_selection"),
            "action_config_start must not force allow_preset_selection; "
            "got context: %r" % ctx,
        )

    def test_action_config_start_returns_a_wizard_action(self):
        action = self.order.action_config_start()
        self.assertEqual(action.get("res_model"), "product.configurator.sale")
        self.assertEqual(
            (action.get("context") or {}).get("default_order_id"),
            self.order.id,
        )

    def test_wizard_create_without_template_raises_friendly_error(self):
        """Regression: this is the exact failure mode the QA report
        hit — a wizard record created with no product_id/product_tmpl_id
        (i.e. the state Odoo's implicit pre-button-call save would
        produce if a user clicked Next without picking a template) must
        raise a friendly UserError, never the raw ORM
        'Missing required value ... Model: Product Config Session'
        ValidationError."""
        with self.assertRaises(UserError) as ctx:
            self.env["product.configurator.sale"].create({
                "order_id": self.order.id,
            })
        msg = str(ctx.exception)
        self.assertIn("Configurable Template", msg)
        # The raw ORM message this replaces names the technical model —
        # a friendly message must not leak that framing.
        self.assertNotIn("Product Config Session", msg)

    def test_wizard_create_with_template_succeeds(self):
        """Companion positive case: supplying product_tmpl_id must still
        work exactly as before — this fix must not block the legitimate
        path."""
        wizard = self.env["product.configurator.sale"].create({
            "order_id": self.order.id,
            "product_tmpl_id": self.tmpl.id,
        })
        self.assertTrue(wizard.config_session_id)
        self.assertEqual(wizard.config_session_id.product_tmpl_id, self.tmpl)

    def test_wizard_create_with_product_id_still_succeeds(self):
        """The reconfigure-existing-line path passes product_id (not
        product_tmpl_id directly) — must not be caught by the new
        guard."""
        variant = self.tmpl.product_variant_ids[:1]
        if not variant:
            self.skipTest("base_1dr has no variant to reconfigure yet")
        wizard = self.env["product.configurator.sale"].create({
            "order_id": self.order.id,
            "product_id": variant.id,
        })
        self.assertTrue(wizard.config_session_id)
