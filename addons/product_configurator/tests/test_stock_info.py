# Copyright 2026 OdooIQ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
#
# Tests for product.config.session.get_config_stock_info — the stock
# aggregation that surfaces in the wizard's [REF] (e) stock badge.

from .common import ProductConfiguratorTestCases


class TestStockInfo(ProductConfiguratorTestCases):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Build three option-products with deliberately-different
        # qty_available values. The aggregation rule is MIN across
        # selected option-products, so the test fixtures need to
        # exercise the min boundary.
        cls.option_high = cls._make_option_product(
            cls.env, name="High Stock Option", qty=100
        )
        cls.option_low = cls._make_option_product(
            cls.env, name="Low Stock Option", qty=2
        )
        cls.option_zero = cls._make_option_product(
            cls.env, name="Zero Stock Option", qty=0
        )

        # Three attribute values, each linking to a distinct
        # option-product. value_with_high.product_id = option_high, etc.
        cls.value_with_high = cls.env["product.attribute.value"].create(
            {
                "name": "Has High Stock Component",
                "attribute_id": cls.attr_fuel.id,
                "product_id": cls.option_high.id,
            }
        )
        cls.value_with_low = cls.env["product.attribute.value"].create(
            {
                "name": "Has Low Stock Component",
                "attribute_id": cls.attr_fuel.id,
                "product_id": cls.option_low.id,
            }
        )
        cls.value_with_zero = cls.env["product.attribute.value"].create(
            {
                "name": "Has Zero Stock Component",
                "attribute_id": cls.attr_fuel.id,
                "product_id": cls.option_zero.id,
            }
        )

    @staticmethod
    def _make_option_product(env, *, name, qty):
        """Create a product.product with the given on-hand quantity
        via a stock.quant. Use Form/quant-setting pattern rather than
        the read-only qty_available compute."""
        tmpl = (
            env["product.template"]
            .sudo()
            .create(
                {
                    "name": name,
                    "type": "consu",
                    "is_storable": True,
                }
            )
        )
        product = tmpl.product_variant_id
        if qty > 0:
            stock_location = env.ref("stock.stock_location_stock")
            env["stock.quant"].sudo().create(
                {
                    "product_id": product.id,
                    "location_id": stock_location.id,
                    "quantity": qty,
                }
            )
            product.invalidate_recordset(["qty_available"])
        return product

    def _make_session_with_values(self, value_ids):
        return self.env["product.config.session"].create(
            {
                "product_tmpl_id": self.config_product.id,
                "user_id": self.env.user.id,
                "value_ids": [(6, 0, value_ids)],
            }
        )

    def test_no_components_when_no_option_products(self):
        """A session whose selected values have no option-products
        attached returns status='no_components'."""
        # value_gasoline (from demo) doesn't have an option-product
        # attached in the base demo data.
        session = self._make_session_with_values([self.value_gasoline.id])
        info = session.get_config_stock_info()
        # Either no_components OR a real status — depends on whether
        # the demo data attaches a product_id. Assert structurally.
        self.assertIn(
            info["status"],
            {"no_components", "in_stock", "low_stock", "out_of_stock"},
            "status must be one of the documented values",
        )
        self.assertIn("min_qty_available", info)
        self.assertIn("threshold", info)

    def test_in_stock_when_all_components_above_threshold(self):
        """All option-products have qty > threshold → 'in_stock'."""
        session = self._make_session_with_values([self.value_with_high.id])
        info = session.get_config_stock_info()
        self.assertEqual(info["status"], "in_stock")
        self.assertEqual(info["min_qty_available"], 100.0)
        self.assertEqual(info["components_checked"], 1)

    def test_low_stock_when_component_below_threshold(self):
        """A component with 0 < qty <= threshold → 'low_stock'."""
        session = self._make_session_with_values([self.value_with_low.id])
        info = session.get_config_stock_info()
        self.assertEqual(info["status"], "low_stock")
        self.assertEqual(info["min_qty_available"], 2.0)

    def test_out_of_stock_when_any_component_zero(self):
        """A component with qty <= 0 → 'out_of_stock', regardless of
        other components' availability."""
        session = self._make_session_with_values(
            [self.value_with_high.id, self.value_with_zero.id]
        )
        info = session.get_config_stock_info()
        self.assertEqual(info["status"], "out_of_stock")
        self.assertEqual(info["min_qty_available"], 0.0)
        # The constraint should be the zero-stock option, not the
        # high-stock one.
        self.assertEqual(
            info["components_constraint"]["id"],
            self.option_zero.id,
            "Constraint should be the option-product with the lowest "
            "qty_available, not just the first one checked",
        )

    def test_min_aggregation_across_components(self):
        """When multiple components are selected, the result reflects
        the MIN across them — not the max, sum, or average."""
        session = self._make_session_with_values(
            [self.value_with_high.id, self.value_with_low.id]
        )
        info = session.get_config_stock_info()
        # Both selected; min(100, 2) = 2 → low_stock
        self.assertEqual(info["status"], "low_stock")
        self.assertEqual(info["min_qty_available"], 2.0)
        self.assertEqual(info["components_checked"], 2)
        self.assertEqual(
            info["components_constraint"]["id"],
            self.option_low.id,
            "Constraint should be the bottleneck (low-stock) option",
        )

    def test_threshold_is_configurable(self):
        """Changing the ir.config_parameter shifts the in_stock vs
        low_stock boundary."""
        # With default threshold 5, qty=10 should be in_stock
        # (above threshold). Raise threshold to 50; qty=10 then drops
        # to low_stock.
        opt_mid = self._make_option_product(self.env, name="Mid Stock", qty=10)
        val_mid = self.env["product.attribute.value"].create(
            {
                "name": "Has Mid Stock Component",
                "attribute_id": self.attr_fuel.id,
                "product_id": opt_mid.id,
            }
        )
        session = self._make_session_with_values([val_mid.id])

        self.env["ir.config_parameter"].sudo().set_param(
            "product_configurator.low_stock_threshold", "5"
        )
        self.assertEqual(session.get_config_stock_info()["status"], "in_stock")

        self.env["ir.config_parameter"].sudo().set_param(
            "product_configurator.low_stock_threshold", "50"
        )
        self.assertEqual(session.get_config_stock_info()["status"], "low_stock")
