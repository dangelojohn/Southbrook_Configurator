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

    def test_action_config_start_opens_the_template_picker(self):
        """C1 fix: the header button now opens the plain template-picker
        transient (not the configurator's virtual-record picker), scoped to
        this order. The picker's product_tmpl_id is a plain Many2one, so it
        can never render greyed like the delegated field did."""
        action = self.order.action_config_start()
        self.assertEqual(
            action.get("res_model"), "southbrook.config.template.picker")
        self.assertEqual(action.get("target"), "new")
        self.assertEqual(
            (action.get("context") or {}).get("default_order_id"),
            self.order.id,
        )

    def test_picker_configure_drives_full_flow_to_a_real_step(self):
        """C1 fix — the coverage the prior fix lacked: don't just check the
        action dict, actually DRIVE the flow. Pick a template on the picker,
        Configure, and assert the configurator opens on a REAL (persisted)
        record with the template set and order attached, and that advancing
        one step reaches a genuine config step (not the virtual-record dead
        end)."""
        picker = self.env["southbrook.config.template.picker"].create({
            "order_id": self.order.id,
            "product_tmpl_id": self.tmpl.id,
        })
        action = picker.action_configure()
        self.assertEqual(action.get("res_model"), "product.configurator.sale")
        res_id = action.get("res_id")
        self.assertTrue(res_id, "Configure must open a REAL (persisted) "
                        "wizard record, not a virtual one (res_id was falsy)")
        wizard = self.env["product.configurator.sale"].browse(res_id)
        self.assertTrue(wizard.exists())
        self.assertEqual(wizard.product_tmpl_id, self.tmpl)
        self.assertEqual(wizard.order_id, self.order)
        self.assertTrue(wizard.config_session_id,
                        "the config session must be created on the real record")
        # Advancing must engage the real config pipeline and leave 'select'.
        wizard.action_next_step()
        self.assertNotEqual(
            wizard.state, "select",
            "action_next_step from the picker-launched wizard must advance "
            "into a real configuration step",
        )

    def test_picker_template_is_required(self):
        """The picker can't be submitted without a template — enforced at
        the model level (required=True), so the greyed-picker dead end
        (submit with no template) is structurally impossible here."""
        field = self.env["southbrook.config.template.picker"]._fields[
            "product_tmpl_id"]
        self.assertTrue(field.required)
        # and the domain limits to configurable templates only
        self.assertIn(("config_ok", "=", True), field.domain)

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

    # ------------------------------------------------------------------
    # QA follow-up (2026-07-04): per-line "Reconfigure" for a
    # session-less line must land on Select Template, not jump ahead.
    # ------------------------------------------------------------------
    def _make_variant_and_line(self):
        """A variant + order line matching S01331's actual shape:
        product_id set, but never run through the configurator (no
        config_session_id on the line)."""
        variant = self.env["product.product"].create({
            "product_tmpl_id": self.tmpl.id,
        })
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id,
            "product_id": variant.id,
            "product_uom_qty": 1,
        })
        return variant, line

    def test_reconfigure_session_less_line_lands_on_select_template(self):
        variant, line = self._make_variant_and_line()
        self.assertFalse(line.config_session_id)
        action = line.reconfigure_product()
        self.assertTrue(action.get("res_id"), "must return a wizard action with a res_id")
        wizard = self.env["product.configurator.sale"].browse(action["res_id"])
        self.assertEqual(
            wizard.state, "select",
            "a session-less line's Reconfigure must land on Select "
            "Template, not jump straight past it",
        )
        self.assertEqual(wizard.product_tmpl_id, self.tmpl)
        # Regression (round 2, live-browser-diagnosed): the backend
        # state can correctly be 'select' while the statusbar widget
        # STILL fails to highlight anything, if get_state_selection()'s
        # own option list doesn't include 'select' as a choice --
        # which happens whenever wizard.product_id is set (see
        # get_state_selection, product_configurator.py:108). Assert on
        # the actual selection options the statusbar renders from, not
        # just the field value, so a regression here fails loudly.
        self.assertFalse(
            wizard.product_id,
            "product_id must NOT be set on this wizard -- setting it "
            "makes get_state_selection() drop 'select' from the "
            "statusbar's own option list even though state=='select', "
            "so no step highlights as current (round-1 regression)",
        )
        # get_state_selection() resolves the wizard via context (matching
        # exactly how get_wizard_action(wizard=...) sets it for a real
        # render), not via self.id -- must replicate that here or the
        # method silently no-ops and this assertion would pass for the
        # wrong reason.
        state_options = dict(
            wizard.with_context(
                wizard_id=wizard.id, wizard_id_view_ref=wizard.id,
            ).get_state_selection()
        )
        self.assertIn(
            "select", state_options,
            "'select' must be a valid statusbar option so the current "
            "state can actually be highlighted in the UI",
        )

    def test_reconfigure_existing_session_line_unchanged(self):
        """Regression companion: a line that DOES have a real prior
        config session must keep the existing behavior (jump straight
        to the first attribute step) -- this fix must be scoped to
        session-less lines only."""
        variant, line = self._make_variant_and_line()
        session = self.env["product.config.session"].create({
            "product_tmpl_id": self.tmpl.id, "user_id": self.env.uid,
        })
        line.config_session_id = session.id
        action = line.reconfigure_product()
        wizard = self.env["product.configurator.sale"].browse(action["res_id"])
        self.assertNotEqual(
            wizard.state, "select",
            "a line with a genuine existing config session must still "
            "jump straight past Select Template, unchanged from before",
        )
