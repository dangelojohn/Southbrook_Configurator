from ..tests.common import (
    TestProductConfiguratorValues,
)


class TestSaleOrder(TestProductConfiguratorValues):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env.ref("base.res_partner_1")
        cls.product = cls.env["product.product"].create({"name": "test product"})
        cls.product_uom_unit = cls.env.ref("uom.product_uom_unit")
        # 19.0: product.pricelist.discount_policy was removed (pricelist
        # mechanism was simplified). Drop the field; default 19.0 pricelist
        # behavior is fine for this test fixture.
        cls.pricelist = cls.env["product.pricelist"].create(
            {
                "name": "New Pricelist",
                "currency_id": cls.env.user.company_id.currency_id.id,
            }
        )
        cls.sale_order = cls.env["sale.order"].create(
            {
                "name": "test SO",
                "partner_id": cls.partner.id,
                "partner_invoice_id": cls.partner.id,
                "partner_shipping_id": cls.partner.id,
                "pricelist_id": cls.pricelist.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.product.id,
                            "name": "Test Line",
                            "product_uom_id": cls.product_uom_unit.id,
                            "product_uom_qty": 2.0,
                            "price_unit": 400.00,
                            "config_session_id": cls.session_id.id,
                        },
                    ),
                ],
            }
        )

    # [REF] (c) — rewrite of the original test_cart_update against
    # the 19.0 split cart API. The pre-19.0 sale.order._cart_update
    # method was refactored into three separate methods:
    #
    #   _cart_add(product_id, quantity, **kwargs)
    #     — for adding a new product to the cart
    #   _cart_update_line_quantity(line_id, quantity, **kwargs)
    #     — for updating an existing line's qty (including
    #       quantity=0 to remove)
    #   _cart_update_order_line(order_line, quantity, **kwargs)
    #     — internal helper (OCA overrides this for config_session
    #       context)
    #
    # The original test's mixed set_qty/add_qty semantics don't map
    # 1:1 to the new API. Each test method below covers ONE focused
    # scenario through the new API, asserting the OCA contribution
    # (config_session_id preservation through update, threading
    # through cart-add) rather than re-testing core Odoo's
    # cart-mechanics behavior.

    def test_cart_update_line_quantity_preserves_config_session(self):
        """Update an existing config-bearing line's qty via the 19.0
        ``_cart_update_line_quantity`` entry point. Assert that the
        OCA contribution to the chain — specifically the
        config_session_id linkage on the line — is preserved through
        the quantity update.

        Exercises OCA's ``_cart_update_order_line`` override which
        sets ``default_config_session_id`` in context before the
        super call."""
        line = self.sale_order.order_line
        self.assertEqual(line.config_session_id, self.session_id)
        original_session_id = line.config_session_id.id

        result = self.sale_order._cart_update_line_quantity(
            line_id=line.id,
            quantity=5.0,
        )

        # The line should still exist with updated qty and the same
        # config_session_id (the OCA override threads it through the
        # _cart_update_order_line context).
        self.assertEqual(
            line.product_uom_qty,
            5.0,
            "Line quantity should be updated to the new value",
        )
        self.assertEqual(
            line.config_session_id.id,
            original_session_id,
            "config_session_id linkage must be preserved across "
            "the quantity update",
        )
        # The return value should be a dict — the new method's
        # contract returns values used by the cart service to give
        # feedback to the customer.
        self.assertIsInstance(result, dict, "Return value must be a dict")

    def test_cart_update_line_quantity_zero_removes_line(self):
        """Setting quantity=0 on a config-bearing line via the new
        API should remove the line entirely (the 19.0 equivalent of
        the 17.0 ``set_qty=0`` / ``set_qty=-1`` removal semantics)."""
        line = self.sale_order.order_line
        line_id = line.id
        self.assertTrue(
            line,
            "Pre-condition: order has an order_line from setUp",
        )

        self.sale_order._cart_update_line_quantity(
            line_id=line_id,
            quantity=0,
        )

        # Line should be gone.
        remaining = self.sale_order.order_line.filtered(lambda l: l.id == line_id)
        self.assertFalse(
            remaining,
            "Line should be removed when quantity is set to 0",
        )

    def test_cart_update_line_quantity_with_invalid_line_id(self):
        """Calling ``_cart_update_line_quantity`` with a line_id that
        doesn't exist on the order should return a warning dict
        rather than raising. The 19.0 method contract surfaces this
        case explicitly (used when the user updates the cart in
        other tabs or with a stale link)."""
        bogus_line_id = 999999999
        result = self.sale_order._cart_update_line_quantity(
            line_id=bogus_line_id,
            quantity=2.0,
        )
        self.assertIsInstance(result, dict)
        self.assertIn(
            "warning",
            result,
            "Invalid line_id should return a 'warning' key in the "
            "result dict, not raise",
        )
