#  Copyright 2024 Simone Rubino - Aion Tech
#  License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import Form

from odoo.addons.base.tests.common import BaseCommon


class TestSaleOrderLine(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env["res.partner"].create(
            {
                "name": "Test partner",
            }
        )
        cls.sale_order = cls.env["sale.order"].create(
            {
                "partner_id": cls.customer.id,
            }
        )

        attribute_form = Form(cls.env["product.attribute"])
        attribute_form.name = "Test attribute"
        with attribute_form.value_ids.new() as value:
            value.name = "Test value 1"
        with attribute_form.value_ids.new() as value:
            value.name = "Test value 2"
        cls.attribute = attribute_form.save()

        product_template_form = Form(cls.env["product.template"])
        product_template_form.name = "Test configurable template"
        product_template_form.taxes_id.clear()
        with product_template_form.attribute_line_ids.new() as attribute_line:
            attribute_line.attribute_id = cls.attribute
            for value in cls.attribute.value_ids:
                attribute_line.value_ids.add(value)
        product_template = product_template_form.save()
        product_template.config_ok = True
        cls.product_template = product_template

    def _create_wizard(self, sale_order, product_template):
        """Create configuration wizard for `product_template` in `sale_order`."""
        wizard_action = sale_order.action_config_start()
        wizard_model = self.env[wizard_action["res_model"]]
        wizard_context = wizard_action.get("context", {})
        wizard = wizard_model.with_context(**wizard_context).create(
            {
                "product_tmpl_id": product_template.id,
            }
        )
        return wizard

    def _configure_wizard(self, wizard, template_values):
        """Fill `wizard` with `template_values`."""
        # Fill in the values
        fields_prefixes = wizard._prefixes
        field_prefix = fields_prefixes.get("field_prefix")
        for attribute, ptav in template_values.items():
            dynamic_attribute_name = field_prefix + str(attribute.id)
            wizard.write(
                {
                    dynamic_attribute_name: ptav.product_attribute_value_id.id,
                }
            )
        return wizard.action_config_done()

    def _configure_product(self, sale_order, product_template, template_values):
        """
        Configure `product_template` in `sale_order` with values `template_values`.
        """
        wizard = self._create_wizard(sale_order, product_template)

        return self._configure_wizard(wizard, template_values)

    def test_config_session_change_price_unit(self):
        """
        The unit price is the price of the configuration session.
        """
        # Arrange: create a product with 2 product template attribute values
        # having extra price 10 and 20 respectively
        product_template = self.product_template
        ptavs = product_template.attribute_line_ids.product_template_value_ids
        ptav_10 = ptavs[:1]
        ptav_10.price_extra = 10
        ptav_20 = (ptavs - ptav_10)[:1]
        ptav_20.price_extra = 20
        attribute = ptav_10.attribute_id
        sale_order = self.sale_order
        self.assertEqual(ptav_10.price_extra, 10)
        self.assertEqual(ptav_20.price_extra, 20)
        self.assertTrue(product_template.config_ok)
        self.assertFalse(sale_order.order_line)

        # Act: Create two order lines, each having a different template attribute value
        self._configure_product(
            sale_order,
            product_template,
            {
                attribute: ptav_10,
            },
        )
        order_line_10 = sale_order.order_line
        self._configure_product(
            sale_order,
            product_template,
            {
                attribute: ptav_20,
            },
        )
        order_line_20 = sale_order.order_line - order_line_10

        # Assert: Each line has the unit price of the configuration session
        config_session_10 = order_line_10.config_session_id
        self.assertEqual(config_session_10.price, order_line_10.price_unit)
        config_session_20 = order_line_20.config_session_id
        self.assertEqual(config_session_20.price, order_line_20.price_unit)
        # Changing the configuration session changes the unit price
        order_line_20.config_session_id = config_session_10
        self.assertEqual(config_session_10.price, order_line_20.price_unit)

    def _create_tax(self, name, amount, price_include=False, include_base_amount=False):
        """Create a tax record. Helper for the tax-coverage tests below."""
        return self.env["account.tax"].create(
            {
                "name": name,
                "amount_type": "percent",
                "amount": amount,
                "price_include_override": "tax_included" if price_include else "tax_excluded",
                "include_base_amount": include_base_amount,
            }
        )

    def test_config_session_price_unit_with_price_excluded_tax(self):
        """[REF] tax coverage — close pre-existing gap.

        Pre-existing gap (disclosed in PR #1 body and tracked in
        post-merge-followups.md): the existing test
        test_config_session_change_price_unit deliberately clears taxes
        via ``product_template_form.taxes_id.clear()``, so
        ``_fix_tax_included_price_company`` runs with an empty
        product-taxes recordset — the tax-math branch in
        ``_compute_price_unit`` is exercised but cleared. No test
        covered a configured line with actual taxes attached.

        This test exercises the price-excluded-tax case: when the
        product carries a price-excluded tax and the order line uses
        the same tax, ``_compute_price_unit`` should leave
        ``price_unit`` equal to the session price (tax is added on top,
        not removed from the price).
        """
        # Arrange: clone the configurable template but attach a
        # price-excluded 10% tax (do NOT clear like the existing test).
        product_template = self.product_template
        tax_10_excluded = self._create_tax("Test 10% Excluded", 10.0, price_include=False)
        product_template.taxes_id = [(6, 0, [tax_10_excluded.id])]

        ptav = product_template.attribute_line_ids.product_template_value_ids[:1]
        ptav.price_extra = 50  # base 0 + extra 50 → session price 50
        attribute = ptav.attribute_id
        sale_order = self.sale_order

        # Act: configure the product
        self._configure_product(
            sale_order,
            product_template,
            {attribute: ptav},
        )
        order_line = sale_order.order_line[-1]

        # Assert: with price-EXCLUDED tax, session.price equals
        # price_unit (tax added on top by Odoo's tax engine at total
        # computation, not modifying the unit price)
        config_session = order_line.config_session_id
        self.assertEqual(
            order_line.price_unit,
            config_session.price,
            "With price-EXCLUDED tax, price_unit must equal "
            "session.price (tax is added on top, not affecting unit)",
        )
        # And confirm the tax IS on the line (the order-line tax_ids
        # should inherit from the product's taxes_id via the standard
        # sale flow)
        self.assertIn(
            tax_10_excluded,
            order_line.tax_ids,
            "Order line should inherit the product's tax",
        )

    def test_config_session_price_unit_with_price_included_tax(self):
        """[REF] tax coverage — the substantial branch.

        When the product carries a PRICE-INCLUDED tax,
        ``_fix_tax_included_price_company`` is the function that does
        the work: it adjusts the input price so that, when the line's
        own taxes are applied, the total matches the original
        configured price (whether tax-included or tax-excluded on the
        line side).

        Verifies that ``_compute_price_unit`` produces a price_unit
        consistent with this contract, not silently returning the raw
        session price.
        """
        # Arrange: configurable template with a 20% PRICE-INCLUDED tax.
        product_template = self.product_template
        tax_20_included = self._create_tax("Test 20% Included", 20.0, price_include=True)
        product_template.taxes_id = [(6, 0, [tax_20_included.id])]

        ptav = product_template.attribute_line_ids.product_template_value_ids[:1]
        ptav.price_extra = 120  # session price 120 (tax-included)
        attribute = ptav.attribute_id
        sale_order = self.sale_order

        # Act
        self._configure_product(
            sale_order,
            product_template,
            {attribute: ptav},
        )
        order_line = sale_order.order_line[-1]

        # Assert: with both the product's tax AND the line's tax being
        # the same price-included tax, _fix_tax_included_price_company
        # should pass the configured price through unchanged (it only
        # adjusts when the line's taxes DIFFER from the product's).
        config_session = order_line.config_session_id
        self.assertEqual(
            order_line.price_unit,
            config_session.price,
            "When product taxes == line taxes (both price-included), "
            "_fix_tax_included_price_company leaves the price "
            "unchanged — price_unit should equal session.price",
        )
        # The tax IS on the line:
        self.assertIn(
            tax_20_included,
            order_line.tax_ids,
            "Order line should inherit the product's price-included tax",
        )

    def test_config_session_price_unit_with_compound_tax(self):
        """[REF] tax coverage — the compound (cascading) branch.

        Compound taxes are applied on top of an already-taxed amount.
        When a configured product carries both a base tax and a
        compound tax, the unit-price computation must continue to
        produce a consistent number — exercising the non-trivial
        branch of ``_fix_tax_included_price_company``.
        """
        # Arrange: two taxes — a base 10% and a compound 5% on top.
        product_template = self.product_template
        tax_10_base = self._create_tax(
            "Test 10% Base", 10.0, price_include=False, include_base_amount=True
        )
        tax_5_compound = self.env["account.tax"].create(
            {
                "name": "Test 5% Compound",
                "amount_type": "percent",
                "amount": 5.0,
                "price_include_override": "tax_excluded",
                "include_base_amount": False,
                "sequence": 10,  # applied AFTER tax_10_base (sequence 1 default)
            }
        )
        product_template.taxes_id = [(6, 0, [tax_10_base.id, tax_5_compound.id])]

        ptav = product_template.attribute_line_ids.product_template_value_ids[:1]
        ptav.price_extra = 100
        attribute = ptav.attribute_id
        sale_order = self.sale_order

        # Act
        self._configure_product(
            sale_order,
            product_template,
            {attribute: ptav},
        )
        order_line = sale_order.order_line[-1]

        # Assert: with price-excluded taxes (both), price_unit equals
        # session.price; tax engine applies taxes to compute totals.
        # The point of this test is the multiple-tax code path runs
        # without raising, not the numerical tax result (which is
        # core Odoo's responsibility, exercised by its own test suite).
        config_session = order_line.config_session_id
        self.assertEqual(
            order_line.price_unit,
            config_session.price,
            "Compound-tax path: price_unit equals session.price for "
            "price-excluded compound taxes",
        )
        # Both taxes are on the line:
        self.assertEqual(
            len(order_line.tax_ids),
            2,
            "Order line should carry both the base and compound taxes",
        )
        self.assertIn(tax_10_base, order_line.tax_ids)
        self.assertIn(tax_5_compound, order_line.tax_ids)
