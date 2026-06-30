# SPDX-License-Identifier: LGPL-3.0-only
"""Regression: configured variants get SKU + standard_price.

End-to-end test 2026-06-22 (Bug #3): variants materialised from the
configurator had `default_code = NULL` and `standard_price = 0.0`,
breaking SKU-grouped sales reports and inventory valuation.

Covers:
  - default_code is set from template code + stable hash
  - same value_ids produce the same SKU on a second materialisation
    (idempotency = no SKU drift when a customer re-saves the same config)
  - standard_price inherits from the template
  - the CFG- prefix kicks in when the template has no default_code
"""
from .common import SouthbrookTestCase


class TestVariantSkuCost(SouthbrookTestCase):

    def _seed_template_with_attr(self, code, cost):
        """Minimal template with one attribute + one value."""
        ProductTemplate = self.env["product.template"]
        Attribute = self.env["product.attribute"]
        Value = self.env["product.attribute.value"]
        AttrLine = self.env["product.template.attribute.line"]

        attr = Attribute.create({
            "name": "TestAttr_%s" % code, "create_variant": "no_variant",
        })
        val = Value.create({"name": "X", "attribute_id": attr.id})
        tmpl = ProductTemplate.create({
            "name": "Test Tmpl %s" % code,
            "default_code": code,
            "standard_price": cost,
            "config_ok": True,
        })
        AttrLine.create({
            "product_tmpl_id": tmpl.id,
            "attribute_id": attr.id,
            "value_ids": [(6, 0, val.ids)],
        })
        return tmpl, val

    def _make_session_and_variant(self, tmpl, val):
        Session = self.env["product.config.session"]
        session = Session.create({
            "product_tmpl_id": tmpl.id,
            "value_ids": [(6, 0, val.ids)],
        })
        return session.create_get_variant(value_ids=val.ids)

    def test_default_code_set_from_template_plus_hash(self):
        tmpl, val = self._seed_template_with_attr("TST-SKU-A", 100.0)
        variant = self._make_session_and_variant(tmpl, val)
        self.assertTrue(variant.default_code)
        self.assertTrue(variant.default_code.startswith("TST-SKU-A-"))
        # hash suffix is 6 hex chars
        suffix = variant.default_code.rsplit("-", 1)[-1]
        self.assertEqual(len(suffix), 6)
        self.assertTrue(all(c in "0123456789ABCDEF" for c in suffix))

    def test_standard_price_inherits_from_template(self):
        tmpl, val = self._seed_template_with_attr("TST-SKU-B", 42.50)
        variant = self._make_session_and_variant(tmpl, val)
        self.assertEqual(variant.standard_price, 42.50)

    def test_sku_is_deterministic_for_same_values(self):
        tmpl, val = self._seed_template_with_attr("TST-SKU-C", 10.0)
        first = self._make_session_and_variant(tmpl, val)
        # Second create with same values dedupes to the same variant
        # (search_variant in OCA returns the existing one) — we assert
        # the SKU didn't drift if a fresh create had to happen.
        first_sku = first.default_code
        self.assertTrue(first_sku)
        # Compose SKU manually via the helper to assert determinism
        session2 = self.env["product.config.session"].create({
            "product_tmpl_id": tmpl.id,
            "value_ids": [(6, 0, val.ids)],
        })
        recomputed = session2._southbrook_compose_sku(tmpl, val.ids)
        self.assertEqual(recomputed, first_sku)

    def test_cfg_prefix_when_template_has_no_code(self):
        ProductTemplate = self.env["product.template"]
        tmpl = ProductTemplate.create({
            "name": "NoCode Tmpl",
            "standard_price": 5.0,
            "config_ok": True,
            # No default_code
        })
        Attribute = self.env["product.attribute"]
        Value = self.env["product.attribute.value"]
        AttrLine = self.env["product.template.attribute.line"]
        attr = Attribute.create({
            "name": "TestAttr_NoCode", "create_variant": "no_variant",
        })
        val = Value.create({"name": "Y", "attribute_id": attr.id})
        AttrLine.create({
            "product_tmpl_id": tmpl.id,
            "attribute_id": attr.id,
            "value_ids": [(6, 0, val.ids)],
        })
        variant = self._make_session_and_variant(tmpl, val)
        self.assertTrue(variant.default_code.startswith("CFG-"))
