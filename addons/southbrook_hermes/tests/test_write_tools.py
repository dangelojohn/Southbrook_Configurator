# addons/southbrook_hermes/tests/test_write_tools.py
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "hermes")
class TestWriteTools(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create({
            "name": "Hermes Write Test Partner",
            "email": "hermes_write@example.com",
        })
        product = self.env["product.product"].search([], limit=1)
        if not product:
            self.skipTest("No products")
        self.order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": product.id, "product_uom_qty": 1,
            })],
        })
        from odoo.addons.southbrook_hermes.tools import write_tools  # noqa
        self.tools = write_tools

    def test_post_internal_note(self):
        result = self.tools.post_internal_note(
            self.env, record_model="sale.order", record_id=self.order.id,
            content="Hermes-posted note from test.")
        self.assertTrue(result["ok"])
        self.assertIn(
            "Hermes-posted note", self.order.message_ids[0].body)

    def test_post_internal_note_rejects_disallowed_model(self):
        with self.assertRaises(Exception):
            self.tools.post_internal_note(
                self.env, record_model="res.users", record_id=1,
                content="Should be rejected.")

    def test_schedule_followup_activity(self):
        from datetime import date, timedelta
        due = (date.today() + timedelta(days=3)).isoformat()
        result = self.tools.schedule_followup_activity(
            self.env, order_id=self.order.id,
            summary="Confirm delivery window", due_date=due)
        self.assertTrue(result["ok"])
        self.assertTrue(self.order.activity_ids)

    def test_schedule_followup_activity_rejects_past_date(self):
        from datetime import date, timedelta
        past = (date.today() - timedelta(days=1)).isoformat()
        with self.assertRaises(Exception):
            self.tools.schedule_followup_activity(
                self.env, order_id=self.order.id,
                summary="X", due_date=past)


@tagged("post_install", "-at_install", "southbrook", "hermes")
class TestProposeRecommendation(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create({
            "name": "T2 Test Partner",
        })
        from odoo.addons.southbrook_hermes.tools import write_tools  # noqa
        self.tools = write_tools

    def test_propose_recommendation_creates_draft(self):
        Rec = self.env["southbrook.hermes.recommendation"]
        before = Rec.search_count([])
        result = self.tools.propose_recommendation(
            self.env, partner_id=self.partner.id,
            intent="request_revision",
            payload={"order_id": 1, "change": "swap door style"},
            summary="Test draft recommendation",
        )
        self.assertTrue(result["ok"])
        after = Rec.search_count([])
        self.assertEqual(after, before + 1)
        rec = Rec.browse(result["rec_id"])
        self.assertEqual(rec.state, "draft")
        self.assertEqual(rec.recommendation_type, "task")
        self.assertEqual(rec.source_model, "res.partner")
        self.assertEqual(rec.source_res_id, self.partner.id)

    def test_propose_recommendation_rejects_disallowed_intent_for_trade_partner(self):
        with self.assertRaises(Exception):
            self.tools.propose_recommendation(
                self.env, partner_id=self.partner.id,
                intent="apply_cut_spec_override",
                payload={}, summary="Force a cut-spec change",
                persona="trade_partner",
            )
