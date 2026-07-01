# addons/southbrook_hermes/tests/test_read_tools.py
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "hermes")
class TestReadToolsBatch1(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create({
            "name": "Hermes Test Partner",
        })
        product = self.env["product.product"].search([], limit=1)
        if not product:
            self.skipTest("No products in DB to build a sale order from")
        self.order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": product.id,
                "product_uom_qty": 1,
            })],
        })
        from odoo.addons.southbrook_hermes.tools import read_tools  # noqa
        self.tools = read_tools

    def test_list_my_orders(self):
        result = self.tools.list_my_orders(self.env, partner_id=self.partner.id)
        self.assertIsInstance(result, list)
        refs = [o["ref"] for o in result]
        self.assertIn(self.order.name, refs)
        for item in result:
            for k in ("ref", "stage", "partner_name"):
                self.assertIn(k, item)

    def test_get_order_status(self):
        status = self.tools.get_order_status(self.env, order_id=self.order.id)
        for k in ("stage", "mos", "bottleneck", "blocker",
                  "next_action", "install_due", "readiness_score", "version"):
            self.assertIn(k, status)

    def test_get_order_line(self):
        line = self.order.order_line[0]
        result = self.tools.get_order_line(
            self.env, order_id=self.order.id, line_id=line.id)
        for k in ("sku", "variant_name", "qty", "attributes", "retail", "channel", "flags"):
            self.assertIn(k, result)
        self.assertEqual(result["qty"], 1)

    def test_get_order_line_rejects_cross_partner_line(self):
        other = self.env["res.partner"].create({"name": "Other Partner"})
        product = self.env["product.product"].search([], limit=1)
        their_order = self.env["sale.order"].create({
            "partner_id": other.id,
            "order_line": [(0, 0, {
                "product_id": product.id, "product_uom_qty": 1})],
        })
        their_line = their_order.order_line[0]
        with self.assertRaises(Exception):
            self.tools.get_order_line(
                self.env, order_id=self.order.id, line_id=their_line.id)


@tagged("post_install", "-at_install", "southbrook", "hermes")
class TestReadToolsBatch2(TransactionCase):
    def setUp(self):
        super().setUp()
        from odoo.addons.southbrook_hermes.tools import read_tools  # noqa
        self.tools = read_tools

    def test_get_os_section_returns_charter(self):
        result = self.tools.get_os_section(self.env, slug="00_charter")
        for k in ("slug", "body", "version"):
            self.assertIn(k, result)
        self.assertEqual(result["slug"], "00_charter")

    def test_get_os_section_missing(self):
        with self.assertRaises(Exception):
            self.tools.get_os_section(self.env, slug="no_such_slug_anywhere")

    def test_list_my_kitchen_projects_returns_list(self):
        partner = self.env["res.partner"].create({"name": "Empty Partner"})
        result = self.tools.list_my_kitchen_projects(
            self.env, partner_id=partner.id)
        self.assertEqual(result, [])

    def test_list_my_recommendations(self):
        partner = self.env["res.partner"].create({"name": "Rec Partner"})
        result = self.tools.list_my_recommendations(
            self.env, partner_id=partner.id)
        self.assertIsInstance(result, list)


@tagged("post_install", "-at_install", "southbrook", "hermes")
class TestCatalogAndPricingTools(TransactionCase):
    """Tests for list_catalog / get_cabinet_price / get_pricelist.

    Depend on southbrook_estimating being installed (which is a manifest
    dependency of southbrook_hermes) so the 12 Q8 cabinet templates
    exist in the DB.
    """

    def setUp(self):
        super().setUp()
        from odoo.addons.southbrook_hermes.tools import read_tools  # noqa
        self.tools = read_tools
        self._sb_estimating_available = bool(self.env.ref(
            "southbrook_estimating.wall_1dr", raise_if_not_found=False))
        if not self._sb_estimating_available:
            self.skipTest(
                "southbrook_estimating cabinet templates not seeded — "
                "cannot exercise catalog / pricing tools.")

    # ---- list_catalog ------------------------------------------------

    def test_list_catalog_no_filter_returns_seeded_cabinets(self):
        result = self.tools.list_catalog(self.env)
        self.assertIn("cabinets", result)
        cabinets = result["cabinets"]
        # 12 Q8 locked templates should all come back (limit is 40).
        self.assertGreaterEqual(len(cabinets), 12)
        for c in cabinets:
            for k in ("id", "name", "family", "series", "list_price"):
                self.assertIn(k, c)

    def test_list_catalog_family_filter(self):
        result = self.tools.list_catalog(self.env, family="base")
        cabinets = result["cabinets"]
        self.assertGreaterEqual(len(cabinets), 1)
        for c in cabinets:
            self.assertEqual(c["family"], "base")
        names = [c["name"] for c in cabinets]
        # base_1dr / base_2dr are among the 12 Q8 templates.
        self.assertTrue(any("Base" in n for n in names))

    def test_list_catalog_returns_empty_for_unknown_family(self):
        # Unknown family slug should return empty without raising —
        # matches the "no-match" contract in the tool docstring.
        # (Enum validation is enforced at the sidecar layer; the tool
        # itself is defensive.)
        result = self.tools.list_catalog(self.env, family="nonsense")
        self.assertEqual(result, {"cabinets": []})

    # ---- get_cabinet_price -------------------------------------------

    def test_get_cabinet_price_retail_default(self):
        wall_1dr = self.env.ref("southbrook_estimating.wall_1dr")
        result = self.tools.get_cabinet_price(
            self.env, product_tmpl_id=wall_1dr.id)
        self.assertEqual(result["product_tmpl_id"], wall_1dr.id)
        self.assertEqual(result["list_price"], wall_1dr.list_price)
        self.assertEqual(result["attribute_extras"], [])
        self.assertEqual(result["retail_total"], wall_1dr.list_price)
        self.assertEqual(result["channel"], "retail")
        self.assertEqual(result["channel_pct"], 0.0)
        self.assertEqual(result["channel_total"], wall_1dr.list_price)
        self.assertIn("currency", result)
        for k in ("symbol", "name", "position", "decimal_places"):
            self.assertIn(k, result["currency"])

    def test_get_cabinet_price_with_attribute_extras(self):
        """Maple box carries +10% list per CLAUDE.md §5 Rule 2 when its
        PTAV.price_extra is seeded. This test tolerates the seed being
        absent (price_extra=0) — it asserts the plumbing (attribute name,
        value name, extras list contains maple) rather than a specific
        currency amount that depends on downstream seeding.
        """
        wall_1dr = self.env.ref("southbrook_estimating.wall_1dr")
        maple_val = self.env.ref(
            "southbrook_estimating.value_box_maple",
            raise_if_not_found=False,
        )
        if not maple_val:
            self.skipTest("Maple box attribute value not seeded")

        # Seed a non-zero price_extra on the maple PTAV bound to wall_1dr
        # so we can assert retail_total > list_price without depending on
        # the tactical_price_seed helper being available.
        PTAV = self.env["product.template.attribute.value"].sudo()
        ptav = PTAV.search([
            ("product_tmpl_id", "=", wall_1dr.id),
            ("product_attribute_value_id", "=", maple_val.id),
        ], limit=1)
        if not ptav:
            self.skipTest(
                "Maple PTAV not bound to wall_1dr — attribute line missing")
        ptav.price_extra = round(wall_1dr.list_price * 0.10, 2)

        result = self.tools.get_cabinet_price(
            self.env,
            product_tmpl_id=wall_1dr.id,
            attribute_value_ids=[maple_val.id],
        )
        self.assertEqual(len(result["attribute_extras"]), 1)
        extra = result["attribute_extras"][0]
        self.assertEqual(extra["value"].lower().find("maple") >= 0, True)
        self.assertGreater(extra["price_extra"], 0.0)
        self.assertGreater(result["retail_total"], result["list_price"])

    def test_get_cabinet_price_dealer_channel(self):
        wall_1dr = self.env.ref("southbrook_estimating.wall_1dr")
        result = self.tools.get_cabinet_price(
            self.env, product_tmpl_id=wall_1dr.id, channel="dealer")
        self.assertEqual(result["channel"], "dealer")
        self.assertEqual(result["channel_pct"], 50.0)
        self.assertAlmostEqual(
            result["channel_total"], result["retail_total"] * 0.5, places=2)

    def test_get_cabinet_price_tradesperson_tier_3(self):
        wall_1dr = self.env.ref("southbrook_estimating.wall_1dr")
        result = self.tools.get_cabinet_price(
            self.env,
            product_tmpl_id=wall_1dr.id,
            channel="tradesperson",
            tradesperson_tier="3",
        )
        self.assertEqual(result["channel_pct"], 35.0)
        self.assertAlmostEqual(
            result["channel_total"],
            result["retail_total"] * 0.65,
            places=2,
        )

    def test_get_cabinet_price_returns_empty_for_missing_template(self):
        result = self.tools.get_cabinet_price(
            self.env, product_tmpl_id=999999)
        self.assertEqual(result, {})

    # ---- get_pricelist -----------------------------------------------

    def test_get_pricelist_dealer(self):
        result = self.tools.get_pricelist(self.env, channel="dealer")
        self.assertEqual(result["channel"], "dealer")
        self.assertEqual(result["discount_pct"], 50.0)
        self.assertIn("Dealer", result["label"])
        self.assertIn("notes", result)

    def test_get_pricelist_tradesperson_tier_2(self):
        result = self.tools.get_pricelist(
            self.env, channel="tradesperson", tradesperson_tier="2")
        self.assertEqual(result["channel"], "tradesperson")
        self.assertEqual(result["discount_pct"], 30.0)
        # Notes should mention the tier system so the LLM can explain
        # the mechanic to a caller.
        lowered = (result["notes"] or "").lower()
        self.assertTrue(
            "contractor" in lowered or "tier" in lowered,
            f"Expected notes to mention contractor/tier system: {result['notes']!r}",
        )

    # ---- registry ----------------------------------------------------

    def test_tools_registered_with_correct_personas(self):
        from odoo.addons.southbrook_hermes.tools.decorator import TOOL_REGISTRY
        by_slug = {t["slug"]: t for t in TOOL_REGISTRY}
        for slug in ("list_catalog", "get_cabinet_price", "get_pricelist"):
            self.assertIn(slug, by_slug, f"{slug} not registered")
            entry = by_slug[slug]
            self.assertEqual(entry["tier"], "T0")
            self.assertEqual(entry["scope"], "global")
            for persona in ("trade_partner", "sales_rep", "mfg_manager"):
                self.assertIn(persona, entry["personas"])
