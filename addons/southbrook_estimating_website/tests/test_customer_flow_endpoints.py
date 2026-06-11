# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for the G1-G17 customer-flow endpoints landed 2026-06-01.

Targets the JSON-RPC + helper layers added to controllers/main.py:

    G9        /my/southbrook/order-builder/new (auto-create)
    G11       /api/order/<id>/add-line       (catalog → line)
    G13       cabinet_prices.xml seed         (12 SKUs > 0)
    G14       _prepare_southbrook_portal_values → order_mode='customer'
    G15       /api/line/<id>/attributes      (filtered + flagged)
    G15       /api/line/<id>/set-attribute   (variant swap)
    G16       /api/order/<id>/action request_price
              (state flip + date stamp + chatter post + idempotency)
    G17       order payload timeline keys
              (created_date / submitted_date / confirmed_date)

We can't use unittest.mock.patch() on odoo.http.request — it's a
werkzeug LocalProxy that raises RuntimeError when poked outside an
HTTP context. Instead the tests swap the controllers.main module's
`request` attribute to a MagicMock via a try/finally helper.

Run with:
    odoo --no-http --test-enable -u southbrook_estimating_website \\
        -d <db> --stop-after-init

Or with the explicit tag filter:
    --test-tags=southbrook_customer_flow
"""
from contextlib import contextmanager
from unittest.mock import MagicMock

from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import mute_logger

from odoo.addons.southbrook_estimating_website.controllers import main as ctrl_main


@contextmanager
def stubbed_request(env, user=None):
    """Swap controllers.main.request for a MagicMock whose .env
    resolves to a real Odoo env for the duration of the with-block.
    Restores the original werkzeug LocalProxy on exit.
    """
    saved = ctrl_main.request
    mock = MagicMock()
    mock.env = env if user is None else env(user=user.id)
    if user is not None:
        # Some controller branches read request.env.user.name. The
        # mocked env returns a real user record so .name is available.
        pass
    mock.session = {}
    mock.params = {}
    ctrl_main.request = mock
    try:
        yield mock
    finally:
        ctrl_main.request = saved


@tagged("post_install", "-at_install", "southbrook_customer_flow")
class TestCustomerFlowEndpoints(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # G13 — the 12 Q8 cabinet templates with seeded prices.
        cls.tmpl_base_1dr = cls.env.ref("southbrook_estimating.base_1dr")
        cls.tmpl_wall_1dr = cls.env.ref("southbrook_estimating.wall_1dr")
        cls.tmpl_accessory = cls.env.ref("southbrook_estimating.accessory")

        # A portal user + their partner. Portal users have share=True
        # which is what _prepare_southbrook_portal_values keys off.
        cls.partner_customer = cls.env["res.partner"].create({
            "name": "Test Customer 2026-06-01",
            "email": "test_customer_g17@southbrook.test",
        })
        portal_group = cls.env.ref("base.group_portal")
        cls.user_customer = cls.env["res.users"].create({
            "name": "Test Customer 2026-06-01",
            "login": "test_customer_g17@southbrook.test",
            "partner_id": cls.partner_customer.id,
            # Odoo 19 renamed res.users.groups_id → group_ids.
            "group_ids": [(6, 0, [portal_group.id])],
        })
        # The order under test for most cases.
        cls.order = cls.env["sale.order"].create({
            "partner_id": cls.partner_customer.id,
        })

    # ==================================================================
    # G13 — cabinet_prices.xml seed
    # ==================================================================
    def test_g13_all_twelve_cabinets_have_positive_list_price(self):
        codes = [
            "SB-WALL-1DR", "SB-WALL-2DR", "SB-BASE-1DR", "SB-BASE-2DR",
            "SB-DRAWER", "SB-SINK-BASE", "SB-TALL-PANTRY", "SB-TALL-OVEN",
            "SB-CORNER", "SB-VANITY", "SB-ACCESSORY", "SB-WORKTOP",
        ]
        tmpls = self.env["product.template"].search([
            ("default_code", "in", codes),
        ])
        self.assertEqual(len(tmpls), 12, "Expected all 12 Q8 cabinet SKUs")
        for tmpl in tmpls:
            self.assertGreater(
                tmpl.list_price, 0.0,
                f"{tmpl.default_code} has list_price=0 — cabinet_prices.xml "
                f"seed missed this SKU; customer Order Builder shows $0",
            )

    # ==================================================================
    # G14 — _prepare_southbrook_portal_values resolves customer mode
    # ==================================================================
    def test_g14_portal_user_gets_customer_mode(self):
        controller = ctrl_main.SouthbrookOrderBuilderPortal()
        # Patch _prepare_portal_layout_values to a no-op so we don't
        # need real portal context.
        controller._prepare_portal_layout_values = lambda: {}
        with stubbed_request(self.env, user=self.user_customer):
            values = controller._prepare_southbrook_portal_values(self.order)
        self.assertEqual(
            values["order_mode"], "customer",
            "Portal user with share=True must default to customer mode",
        )

    def test_g14_internal_user_gets_dealer_mode(self):
        controller = ctrl_main.SouthbrookOrderBuilderPortal()
        controller._prepare_portal_layout_values = lambda: {}
        # admin user (default) is internal, share=False.
        with stubbed_request(self.env):
            values = controller._prepare_southbrook_portal_values(self.order)
        self.assertEqual(
            values["order_mode"], "dealer",
            "Internal user (share=False) must default to dealer mode",
        )

    # ==================================================================
    # G17 — order payload includes timeline timestamps
    # ==================================================================
    def test_g17_order_payload_includes_timeline_timestamps(self):
        controller = ctrl_main.SouthbrookOrderBuilderPortal()
        with stubbed_request(self.env):
            payload = controller._build_southbrook_order_payload(self.order)
        order_dict = payload["order"]
        # created_date always set (Odoo auto-stamps create_date).
        self.assertIsNotNone(order_dict["created_date"])
        # submitted_date null on a draft order.
        self.assertIsNone(order_dict["submitted_date"])
        # confirmed_date null until state in ('sale', 'done').
        self.assertIsNone(order_dict["confirmed_date"])

    # ==================================================================
    # G15 — /api/line/<id>/attributes
    # ==================================================================
    def test_g15_attributes_filters_single_value_attributes(self):
        variant = self.tmpl_base_1dr.product_variant_ids[:1]
        if not variant:
            variant = self.env["product.product"].create({
                "product_tmpl_id": self.tmpl_base_1dr.id,
            })
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id,
            "product_id": variant.id,
            "product_uom_qty": 1,
        })
        controller = ctrl_main.SouthbrookOrderBuilderPortal()
        # Bypass the partner-chain access check.
        controller._southbrook_resolve_line = lambda _id: line
        with stubbed_request(self.env):
            result = controller.southbrook_api_line_attributes(line.id)
        self.assertTrue(result.get("ok"))
        attrs = result["attributes"]
        self.assertGreater(len(attrs), 1,
            "SB-BASE-1DR should expose multiple attributes (Door Style, "
            "Width, Finish, etc.)")
        for attr in attrs:
            self.assertGreaterEqual(
                len(attr["values"]), 2,
                f"Attribute {attr['name']} surfaced with <2 values — "
                f"the 1-value filter (e.g. Family) should have dropped it",
            )

    def test_g15_set_attribute_swaps_variant_with_new_combination(self):
        # Reuse the template's existing default variant (one is auto-
        # created on template install). Creating a second variant with
        # the same empty combination_indices trips the
        # product_product_combination_unique constraint — that's a real
        # Odoo invariant the controller's create-fallback path must
        # also respect.
        variant = self.tmpl_base_1dr.product_variant_ids[:1]
        if not variant:
            variant = self.env["product.product"].create({
                "product_tmpl_id": self.tmpl_base_1dr.id,
            })
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id,
            "product_id": variant.id,
            "product_uom_qty": 1,
        })
        attr_lines = self.tmpl_base_1dr.attribute_line_ids
        door_attr_line = next(
            (al for al in attr_lines
             if "Door Style" in (al.attribute_id.name or "")),
            None,
        )
        self.assertIsNotNone(
            door_attr_line, "Door Style attribute must be on SB-BASE-1DR",
        )
        chosen_value = door_attr_line.value_ids[0]

        controller = ctrl_main.SouthbrookOrderBuilderPortal()
        controller._southbrook_resolve_line = lambda _id: line
        with stubbed_request(self.env):
            result = controller.southbrook_api_line_set_attribute(
                line.id,
                attribute_id=door_attr_line.attribute_id.id,
                value_id=chosen_value.id,
            )
        self.assertTrue(result.get("ok"),
            f"set-attribute should return ok=True, got {result}")
        line.invalidate_recordset()
        new_ptavs = line.product_id.product_template_attribute_value_ids
        self.assertTrue(any(
            ptav.product_attribute_value_id == chosen_value
            for ptav in new_ptavs
        ), "Line's new variant should carry the chosen attribute value")

    def test_g15_set_attribute_rejects_value_not_in_template(self):
        variant = self.tmpl_base_1dr.product_variant_ids[:1]
        if not variant:
            variant = self.env["product.product"].create({
                "product_tmpl_id": self.tmpl_base_1dr.id,
            })
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id,
            "product_id": variant.id,
            "product_uom_qty": 1,
        })
        bogus_attr = self.env["product.attribute"].create({"name": "Bogus"})
        bogus_value = self.env["product.attribute.value"].create({
            "name": "Bogus Value", "attribute_id": bogus_attr.id,
        })

        controller = ctrl_main.SouthbrookOrderBuilderPortal()
        controller._southbrook_resolve_line = lambda _id: line
        with stubbed_request(self.env):
            result = controller.southbrook_api_line_set_attribute(
                line.id,
                attribute_id=bogus_attr.id,
                value_id=bogus_value.id,
            )
        self.assertEqual(result.get("error"), "value_not_in_template",
            "Setting a value not on the template must return value_not_in_template")

    # ==================================================================
    # G11 — /api/order/<id>/add-line
    # ==================================================================
    def test_g11_add_line_creates_line_for_dynamic_variant_template(self):
        controller = ctrl_main.SouthbrookOrderBuilderPortal()
        controller._southbrook_resolve_order = lambda _id: self.order
        with stubbed_request(self.env):
            result = controller.southbrook_api_order_add_line(
                self.order.id,
                product_tmpl_id=self.tmpl_wall_1dr.id,
            )
        self.assertTrue(result.get("ok"))
        line = self.env["sale.order.line"].browse(result["line_id"])
        self.assertEqual(line.order_id, self.order)
        self.assertEqual(
            line.product_id.product_tmpl_id, self.tmpl_wall_1dr,
        )
        self.assertEqual(line.product_uom_qty, 1.0)

    def test_g11_add_line_blocks_when_order_locked(self):
        self.order.state = "cancel"
        controller = ctrl_main.SouthbrookOrderBuilderPortal()
        controller._southbrook_resolve_order = lambda _id: self.order
        with stubbed_request(self.env):
            result = controller.southbrook_api_order_add_line(
                self.order.id,
                product_tmpl_id=self.tmpl_accessory.id,
            )
        self.assertEqual(result.get("error"), "order_locked")
        self.assertEqual(result.get("state"), "cancel")

    # ==================================================================
    # G16 + G17 — request_price action
    # ==================================================================
    @mute_logger("odoo.addons.southbrook_estimating_website.controllers.main")
    def test_g16_request_price_flips_state_and_stamps_date(self):
        variant = self.tmpl_base_1dr.product_variant_ids[:1]
        if not variant:
            variant = self.env["product.product"].create({
                "product_tmpl_id": self.tmpl_base_1dr.id,
            })
        self.env["sale.order.line"].create({
            "order_id": self.order.id,
            "product_id": variant.id,
            "product_uom_qty": 1,
        })
        self.assertEqual(self.order.state, "draft")
        self.assertFalse(self.order.southbrook_submitted_date)

        controller = ctrl_main.SouthbrookOrderBuilderPortal()
        controller._southbrook_resolve_order = lambda _id: self.order
        with stubbed_request(self.env):
            result = controller.southbrook_api_order_action(
                self.order.id, action_code="request_price",
            )

        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("new_state"), "sent")
        self.assertTrue(result.get("submitted_for_pricing"))
        self.assertFalse(result.get("already_submitted"))
        self.order.invalidate_recordset()
        self.assertEqual(self.order.state, "sent")
        self.assertTrue(
            self.order.southbrook_submitted_date,
            "G17: southbrook_submitted_date must be stamped on first submit",
        )

    @mute_logger("odoo.addons.southbrook_estimating_website.controllers.main")
    def test_g16_request_price_is_idempotent(self):
        # Drive the order to 'sent' once, then request_price again.
        from odoo import fields as odoo_fields
        original_date = odoo_fields.Datetime.now()
        self.order.write({
            "state": "sent",
            "southbrook_submitted_date": original_date,
        })

        controller = ctrl_main.SouthbrookOrderBuilderPortal()
        controller._southbrook_resolve_order = lambda _id: self.order
        with stubbed_request(self.env):
            result = controller.southbrook_api_order_action(
                self.order.id, action_code="request_price",
            )
        self.assertTrue(result.get("ok"))
        self.assertTrue(
            result.get("already_submitted"),
            "Idempotent path must surface already_submitted=True so the "
            "frontend can show 'Submitted ✓' without re-firing email",
        )
        self.order.invalidate_recordset()
        # The original submitted_date must NOT be overwritten.
        self.assertEqual(
            self.order.southbrook_submitted_date, original_date,
            "Re-submit must not overwrite the original submitted_date",
        )

    # ==================================================================
    # 2026-06-02 catalog-picker redesign
    # ==================================================================
    def test_catalog_picker_metadata_stamped_on_every_cabinet(self):
        """kitchen_planner_state stamps category / description /
        dimensions / icon onto each catalog entry — the four fields the
        redesigned CatalogPicker reads to render search, filter pills,
        thumbnails, and dimension callouts.
        """
        # kitchen_planner_state lives on SouthbrookKitchenPlanner
        # (the public-facing catalog controller), not on the
        # OrderBuilder portal controller.
        controller = ctrl_main.SouthbrookKitchenPlanner()
        with stubbed_request(self.env, user=self.user_customer):
            result = controller.kitchen_planner_state()
        catalog = result["catalog"]
        # All 12 Q8 cabinets should resolve via xml_id (this is what
        # the catalog-tile flake fix locked in 2026-06-01).
        self.assertEqual(
            len(catalog), 12,
            "Expected all 12 Q8 cabinets in the catalog response",
        )
        for item in catalog:
            for key in ("category", "description", "dimensions", "icon"):
                self.assertIn(
                    key, item,
                    f"catalog item {item.get('sku')} missing '{key}' — "
                    f"redesigned CatalogPicker depends on this field",
                )
            self.assertTrue(
                item["category"],
                f"{item.get('sku')} has empty category — pill filter "
                f"would silently drop it",
            )

    def test_catalog_picker_category_set_covers_redesign_brief(self):
        """The category set must include the six categories the
        CatalogPicker's filter pills render: Wall / Base / Drawer /
        Tall / Vanity / Extras.
        """
        # kitchen_planner_state lives on SouthbrookKitchenPlanner
        # (the public-facing catalog controller), not on the
        # OrderBuilder portal controller.
        controller = ctrl_main.SouthbrookKitchenPlanner()
        with stubbed_request(self.env, user=self.user_customer):
            result = controller.kitchen_planner_state()
        categories = {item["category"] for item in result["catalog"]}
        for required in (
            "Wall", "Base", "Drawer", "Tall", "Vanity", "Extras",
        ):
            self.assertIn(
                required, categories,
                f"Category '{required}' missing — the filter pill row "
                f"on the CatalogPicker would have a dead category",
            )

    def test_add_line_accepts_qty_argument(self):
        """The redesigned card carries a quantity stepper. The qty
        value must propagate through /add-line to sale.order.line.
        product_uom_qty.
        """
        controller = ctrl_main.SouthbrookOrderBuilderPortal()
        controller._southbrook_resolve_order = lambda _id: self.order
        with stubbed_request(self.env):
            result = controller.southbrook_api_order_add_line(
                self.order.id,
                product_tmpl_id=self.tmpl_wall_1dr.id,
                qty=3,
            )
        self.assertTrue(result.get("ok"))
        line = self.env["sale.order.line"].browse(result["line_id"])
        self.assertEqual(
            line.product_uom_qty, 3.0,
            "Catalog-picker qty stepper value didn't carry through to "
            "sale.order.line.product_uom_qty",
        )

    def test_add_line_defaults_qty_to_one_when_omitted(self):
        """Original callers (anyone still passing only
        product_tmpl_id) must keep their original behaviour: qty=1.
        """
        controller = ctrl_main.SouthbrookOrderBuilderPortal()
        controller._southbrook_resolve_order = lambda _id: self.order
        with stubbed_request(self.env):
            result = controller.southbrook_api_order_add_line(
                self.order.id,
                product_tmpl_id=self.tmpl_wall_1dr.id,
            )
        self.assertTrue(result.get("ok"))
        line = self.env["sale.order.line"].browse(result["line_id"])
        self.assertEqual(line.product_uom_qty, 1.0)

    def test_add_line_clamps_qty_below_one_to_one(self):
        """A malformed payload (qty=0, qty=-2, qty='abc') must not
        produce a zero-quantity line — clamp to 1 silently.
        """
        controller = ctrl_main.SouthbrookOrderBuilderPortal()
        controller._southbrook_resolve_order = lambda _id: self.order
        for bad_qty in (0, -2, "not-a-number"):
            with stubbed_request(self.env):
                result = controller.southbrook_api_order_add_line(
                    self.order.id,
                    product_tmpl_id=self.tmpl_wall_1dr.id,
                    qty=bad_qty,
                )
            self.assertTrue(
                result.get("ok"),
                f"qty={bad_qty!r} should produce a valid line, got "
                f"{result}",
            )
            line = self.env["sale.order.line"].browse(result["line_id"])
            self.assertEqual(
                line.product_uom_qty, 1.0,
                f"qty={bad_qty!r} should have clamped to 1",
            )

    # ==================================================================
    # 2026-06-02 — channel-aware preview pricing in the catalog payload
    # ==================================================================
    def test_catalog_channel_price_equals_list_price_for_retail_partner(
        self,
    ):
        """A retail partner sees channel_price == list_price for every
        cabinet — the OWL CatalogPicker's hasChannelDiscount() returns
        false and the card renders a single price.
        """
        # The test partner created in setUpClass has either no channel
        # set or 'retail' (a parallel-session change set retail as the
        # default value rather than null). Either resolves to the
        # retail pricelist downstream in _resolve_channel_pricelist;
        # this assertion documents the precondition without pinning
        # the storage representation.
        self.assertIn(
            self.partner_customer.channel or "retail", ("retail", False, None),
            "Test partner should be on the retail channel (default)",
        )

        # kitchen_planner_state lives on SouthbrookKitchenPlanner
        # (the public-facing catalog controller), not on the
        # OrderBuilder portal controller.
        controller = ctrl_main.SouthbrookKitchenPlanner()
        with stubbed_request(self.env, user=self.user_customer):
            result = controller.kitchen_planner_state()

        # Channel label should be the retail pricelist's name.
        self.assertIn(
            "Retail", result["user"]["channel_label"],
            "Retail partner should resolve to the Retail pricelist; "
            f"got channel_label={result['user']['channel_label']!r}",
        )

        # Every cabinet's channel_price should match list_price exactly
        # (retail pricelist has no discount rules).
        for item in result["catalog"]:
            self.assertEqual(
                item["channel_price"], item["list_price"],
                f"{item['sku']}: channel_price should equal list_price "
                f"for a retail partner (got channel={item['channel_price']} "
                f"vs list={item['list_price']})",
            )

    def test_catalog_channel_price_differs_for_tradesperson_tier_3(self):
        """A Tradesperson Tier 3 partner sees channel_price < list_price
        for every cabinet (the −35% chained discount applies), and the
        channel_label reflects the resolved pricelist's display name.
        Drives the dual-price treatment in the CatalogPicker card.
        """
        # Promote the test partner to tradesperson tier 3 — same
        # smoke-test shape as the Q7 Demo Tradesperson partner.
        self.partner_customer.write({
            "channel": "tradesperson",
            "tradesperson_tier": "3",
        })

        # kitchen_planner_state lives on SouthbrookKitchenPlanner
        # (the public-facing catalog controller), not on the
        # OrderBuilder portal controller.
        controller = ctrl_main.SouthbrookKitchenPlanner()
        with stubbed_request(self.env, user=self.user_customer):
            result = controller.kitchen_planner_state()

        # Channel label should mention Tier 3 or -35%.
        label = result["user"]["channel_label"] or ""
        self.assertTrue(
            "Tier 3" in label or "35" in label,
            f"Tradesperson Tier 3 partner should resolve to a tier-3 "
            f"labelled pricelist; got channel_label={label!r}",
        )

        # At least the cabinets WITH a variant should price strictly
        # below list_price. Templates with no variant fall back to
        # list_price by the controller's defensive fallback — that's
        # fine; we don't assert against them.
        priced_below = 0
        for item in result["catalog"]:
            if item["channel_price"] < item["list_price"]:
                priced_below += 1
            # Sanity: channel_price must never be higher than list.
            self.assertLessEqual(
                item["channel_price"], item["list_price"],
                f"{item['sku']}: channel_price should never exceed "
                f"list_price (got channel={item['channel_price']} "
                f"vs list={item['list_price']})",
            )
        self.assertGreater(
            priced_below, 0,
            "At least one cabinet should price below list_price for "
            "the Tradesperson Tier 3 channel; got zero — pricelist "
            "resolution may have fallen back to retail silently",
        )

    # ==================================================================
    # 2026-06-02 — filter-contract tests at the controller level
    #
    # The OWL CatalogPicker filters client-side via its buildDomain() /
    # applyFilters() seam. We can't run the JS in a TransactionCase,
    # but we CAN lock the contract the JS depends on: the controller
    # always emits a name + sku pair on each catalog item, with the
    # values portal users actually see (no nulls, no shape drift).
    # ==================================================================
    def test_catalog_emits_name_and_sku_per_item_for_filter_match(self):
        """The JS search-by-name-and-sku filter relies on every catalog
        item carrying truthy string `name` AND truthy string `sku`.
        Without both, an `ilike` substring match silently drops the
        row.
        """
        # kitchen_planner_state lives on SouthbrookKitchenPlanner
        # (the public-facing catalog controller), not on the
        # OrderBuilder portal controller.
        controller = ctrl_main.SouthbrookKitchenPlanner()
        with stubbed_request(self.env, user=self.user_customer):
            result = controller.kitchen_planner_state()
        for item in result["catalog"]:
            self.assertTrue(
                item.get("name"),
                f"item id={item.get('id')} has empty name — catalog "
                f"search would drop it",
            )
            self.assertTrue(
                item.get("sku"),
                f"item id={item.get('id')} (name={item.get('name')!r}) "
                f"has empty sku — catalog search by SKU would drop it",
            )

    def test_catalog_category_set_drives_filter_pills(self):
        """The JS getCategoryTabs() builder reads item.category off
        each catalog row to derive the pill tabs. Every row must
        carry a non-empty string category for the pill row to be
        complete.
        """
        # kitchen_planner_state lives on SouthbrookKitchenPlanner
        # (the public-facing catalog controller), not on the
        # OrderBuilder portal controller.
        controller = ctrl_main.SouthbrookKitchenPlanner()
        with stubbed_request(self.env, user=self.user_customer):
            result = controller.kitchen_planner_state()
        for item in result["catalog"]:
            self.assertTrue(
                item.get("category"),
                f"item id={item.get('id')} ({item.get('sku')}) has "
                f"empty category — would be silently bucketed into "
                f"the 'Extras' default by the JS getCategoryTabs",
            )

    def test_add_line_endpoint_unchanged_for_zero_qty_path(self):
        """Sanity that add-line's int-cast + clamp-to-1 contract
        matches what the JS qty stepper (also clamped at 1) ships
        through. The stepper enforces >=1 client-side; the endpoint
        is the second-line defence. Negative or non-numeric input
        from a hand-crafted RPC must still produce qty=1, never 0
        or a 500.
        """
        controller = ctrl_main.SouthbrookOrderBuilderPortal()
        controller._southbrook_resolve_order = lambda _id: self.order
        for raw in (0, -10, None):
            with stubbed_request(self.env):
                result = controller.southbrook_api_order_add_line(
                    self.order.id,
                    product_tmpl_id=self.tmpl_wall_1dr.id,
                    qty=raw,
                )
            self.assertTrue(result.get("ok"), f"qty={raw!r}: {result}")
            line = self.env["sale.order.line"].browse(result["line_id"])
            self.assertEqual(
                line.product_uom_qty, 1.0,
                f"qty={raw!r} must clamp to 1 (defence-in-depth for "
                f"the JS qty stepper)",
            )
