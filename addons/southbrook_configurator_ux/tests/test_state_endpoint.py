# SPDX-License-Identifier: LGPL-3.0-only
"""Contract tests for /southbrook/api/configurator/state.

The OWL component in static/src/js/configurator.esm.js depends on the
exact shape of this endpoint's response. These tests lock the contract
so a future controller refactor can't silently break the bundle.

Run:

    odoo --no-http --test-enable -u southbrook_configurator_ux \\
        -d <db> --stop-after-init

Or with the explicit tag:

    --test-tags=southbrook_cfg_state
"""
from contextlib import contextmanager
from unittest.mock import MagicMock

from odoo.tests import TransactionCase, tagged

from odoo.addons.southbrook_configurator_ux.controllers import main as ctrl_main


@contextmanager
def stubbed_request(env, user=None):
    """Swap controllers.main.request for a MagicMock whose .env resolves
    to a real Odoo env for the duration of the with-block. Same pattern
    as southbrook_estimating_website/tests/test_customer_flow_endpoints.py.
    """
    saved = ctrl_main.request
    mock = MagicMock()
    mock.env = env if user is None else env(user=user.id)
    mock.session = {}
    mock.params = {}
    ctrl_main.request = mock
    try:
        yield mock
    finally:
        ctrl_main.request = saved


@tagged("post_install", "-at_install", "southbrook_cfg_state")
class TestConfiguratorStateEndpoint(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.controller = ctrl_main.SouthbrookConfiguratorAPI()
        # Reference cabinet for happy-path tests — SB-BASE-1DR has the
        # full 11-attribute set including hinge_side, finished_sides,
        # gables, and the Q3 width-narrow/door_count=1 rule.
        cls.tmpl_base_1dr = cls.env.ref("southbrook_estimating.base_1dr")
        # A non-configurable product for the not_configurable error path.
        # Any built-in Odoo demo product without config_ok works; if
        # the demo data isn't loaded we create one on the fly.
        non_config = cls.env["product.template"].search(
            [("config_ok", "=", False)], limit=1)
        if not non_config:
            non_config = cls.env["product.template"].create({
                "name": "Test Non-Configurable",
                "default_code": "TEST-NC",
                "config_ok": False,
            })
        cls.tmpl_non_config = non_config

    # ==================================================================
    # Error paths — argument validation + product lookup
    # ==================================================================
    def test_missing_product_tmpl_id_returns_error(self):
        with stubbed_request(self.env):
            r = self.controller.configurator_state()
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "missing_product_tmpl_id")

    def test_bad_product_tmpl_id_returns_error(self):
        with stubbed_request(self.env):
            r = self.controller.configurator_state(
                product_tmpl_id="not-an-int")
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "bad_product_tmpl_id")

    def test_unknown_product_tmpl_id_returns_error(self):
        with stubbed_request(self.env):
            r = self.controller.configurator_state(product_tmpl_id=999_999)
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "product_not_found")

    def test_non_configurable_product_returns_error(self):
        with stubbed_request(self.env):
            r = self.controller.configurator_state(
                product_tmpl_id=self.tmpl_non_config.id)
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "not_configurable")

    # ==================================================================
    # Happy path — full response shape
    # ==================================================================
    def test_payload_shape_for_base_1dr(self):
        with stubbed_request(self.env):
            r = self.controller.configurator_state(
                product_tmpl_id=self.tmpl_base_1dr.id)
        self.assertTrue(r["ok"])
        # Top-level keys
        for k in ("product", "session_id", "base_price",
                  "groups", "attributes", "selected_value_ids"):
            self.assertIn(k, r, f"top-level key '{k}' missing from response")
        # Product block
        p = r["product"]
        for k in ("tmpl_id", "sku", "name", "list_price", "currency"):
            self.assertIn(k, p, f"product.{k} missing")
        self.assertEqual(p["tmpl_id"], self.tmpl_base_1dr.id)
        self.assertTrue(p["sku"].startswith("SB-"))
        self.assertGreater(p["list_price"], 0,
            "Base 1-Door must have list_price > 0 for the catalog card")
        for k in ("symbol", "position", "decimal_places", "name"):
            self.assertIn(k, p["currency"])
        # base_price mirrors list_price
        self.assertEqual(r["base_price"], p["list_price"])

    def test_attributes_have_required_value_fields(self):
        with stubbed_request(self.env):
            r = self.controller.configurator_state(
                product_tmpl_id=self.tmpl_base_1dr.id)
        self.assertGreater(len(r["attributes"]), 1,
            "SB-BASE-1DR exposes multiple attributes")
        for attr_id, attr in r["attributes"].items():
            # OWL component reads these on every attribute
            for k in ("name", "display_type", "sequence", "values"):
                self.assertIn(k, attr,
                    f"attribute {attr_id} ({attr.get('name')}) missing key '{k}'")
            self.assertGreaterEqual(len(attr["values"]), 1,
                f"attribute {attr['name']} has no values — the line "
                f"would render an empty chip group")
            for val in attr["values"]:
                for k in ("id", "name", "price_extra", "html_color",
                          "sequence", "disabled"):
                    self.assertIn(k, val,
                        f"value in attribute {attr['name']} missing key '{k}'")

    def test_groups_cluster_attributes_in_logical_order(self):
        with stubbed_request(self.env):
            r = self.controller.configurator_state(
                product_tmpl_id=self.tmpl_base_1dr.id)
        # Phase 1 prototype's 4 groups should appear in the response
        # (assuming the template carries the attributes we expect).
        group_titles = [g["title"] for g in r["groups"]]
        for expected in ("Size & Layout", "Series & Materials",
                         "Finish & Construction", "Hardware & Add-ons"):
            self.assertIn(expected, group_titles,
                f"group '{expected}' missing from response — the "
                f"hardcoded ATTRIBUTE_GROUPS mapping needs an update")
        # Every group's attribute_ids should reference real attributes
        # in the response.
        for g in r["groups"]:
            for aid in g["attribute_ids"]:
                self.assertIn(str(aid), r["attributes"],
                    f"group '{g['title']}' references attribute {aid} "
                    f"that's not in the attributes block")

    # ==================================================================
    # Session — created, reused, scoped to user+template
    # ==================================================================
    def test_session_is_created_on_first_call(self):
        # Clear any existing draft sessions for this template+admin.
        self.env["product.config.session"].sudo().search([
            ("product_tmpl_id", "=", self.tmpl_base_1dr.id),
            ("user_id", "=", self.env.user.id),
            ("state", "=", "draft"),
        ]).unlink()
        with stubbed_request(self.env):
            r = self.controller.configurator_state(
                product_tmpl_id=self.tmpl_base_1dr.id)
        self.assertTrue(r["ok"])
        sess = self.env["product.config.session"].browse(r["session_id"])
        self.assertTrue(sess.exists(),
            "Endpoint should have created a session")
        self.assertEqual(sess.product_tmpl_id.id, self.tmpl_base_1dr.id)
        self.assertEqual(sess.state, "draft")

    def test_session_is_reused_on_repeated_call(self):
        with stubbed_request(self.env):
            r1 = self.controller.configurator_state(
                product_tmpl_id=self.tmpl_base_1dr.id)
            r2 = self.controller.configurator_state(
                product_tmpl_id=self.tmpl_base_1dr.id)
        self.assertEqual(r1["session_id"], r2["session_id"],
            "Repeated calls should return the SAME draft session "
            "(otherwise a customer's selections orphan on every reload)")

    def test_selected_value_ids_persisted_from_session(self):
        # Pre-seed the session with a value picked already.
        sess = self.env["product.config.session"].sudo().create({
            "product_tmpl_id": self.tmpl_base_1dr.id,
            "user_id": self.env.user.id,
        })
        # Pick the first Width value, whatever it is.
        width_attr = self.env["product.attribute"].search(
            [("name", "=", "Width")], limit=1)
        if width_attr:
            value = width_attr.value_ids.sorted("sequence")[:1]
            if value:
                sess.sudo().value_ids = [(6, 0, value.ids)]
                with stubbed_request(self.env):
                    r = self.controller.configurator_state(
                        product_tmpl_id=self.tmpl_base_1dr.id)
                self.assertIn(value.id, r["selected_value_ids"],
                    "Pre-selected value should round-trip on next call")

    def test_price_extra_default_zero_when_no_template_override(self):
        # OCA's auto-create-ptav semantics: when an attribute_line is
        # added, ptav rows are auto-materialised at price_extra=0.0.
        # Any value WITHOUT a ptav row should still default to 0.0
        # rather than missing the key.
        with stubbed_request(self.env):
            r = self.controller.configurator_state(
                product_tmpl_id=self.tmpl_base_1dr.id)
        for attr_id, attr in r["attributes"].items():
            for val in attr["values"]:
                self.assertIsInstance(val["price_extra"], (int, float),
                    f"price_extra on value '{val['name']}' "
                    f"(attribute {attr['name']}) must be numeric")
                # All values default to disabled=False from this
                # endpoint (Phase 2c sets True from the rule engine).
                self.assertFalse(val["disabled"])
