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


@tagged("post_install", "-at_install", "southbrook", "hermes")
class TestDraftCustomerEmail(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create({
            "name": "Draft Email Test Partner",
            "email": "draft_email_test@example.com",
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

    def _note_subtype_id(self):
        return self.env.ref("mail.mt_note").id

    def test_draft_customer_email_posts_internal_note(self):
        before = len(self.order.message_ids)
        result = self.tools.draft_customer_email(
            self.env, order_id=self.order.id,
            subject="Follow-up on your kitchen order",
            body="Hi there — just checking whether the door style you "
                 "picked is still what you want.",
        )
        self.assertTrue(result["ok"])
        self.assertTrue(result["human_review_required"])
        self.assertEqual(result["order_id"], self.order.id)
        self.assertEqual(result["order_name"], self.order.name)
        self.assertIn("message_id", result)
        # A new message was posted.
        self.assertGreater(len(self.order.message_ids), before)
        msg = self.env["mail.message"].browse(result["message_id"])
        self.assertTrue(msg.exists())
        # Body contains the marker (mail.message sanitizes but keeps text).
        self.assertIn("Fabio-drafted customer email", msg.body)
        self.assertIn("NOT SENT", msg.body)
        # Subtype is note, NOT email — the whole point of this tool.
        self.assertEqual(msg.subtype_id.id, self._note_subtype_id())
        # And message_type must be comment (never 'email').
        self.assertEqual(msg.message_type, "comment")

    def test_draft_customer_email_rejects_empty_body(self):
        before = len(self.order.message_ids)
        result = self.tools.draft_customer_email(
            self.env, order_id=self.order.id,
            subject="Empty-body test", body="   ",
        )
        self.assertEqual(result, {"error": "empty_body"})
        # No message posted.
        self.assertEqual(len(self.order.message_ids), before)

    def test_draft_customer_email_missing_order(self):
        result = self.tools.draft_customer_email(
            self.env, order_id=999999,
            subject="Ghost order", body="Should not post.",
        )
        self.assertEqual(result, {"error": "order_not_found"})

    def test_draft_customer_email_truncates_long_subject(self):
        long_subject = "A" * 500
        result = self.tools.draft_customer_email(
            self.env, order_id=self.order.id,
            subject=long_subject,
            body="Body is fine.",
        )
        self.assertTrue(result["ok"])
        msg = self.env["mail.message"].browse(result["message_id"])
        # The stored mail.message.subject should be capped at 256 chars.
        self.assertLessEqual(len(msg.subject or ""), 256)
        self.assertEqual(msg.subject, "A" * 256)

    def test_draft_customer_email_warns_if_partner_has_no_email(self):
        partner_no_email = self.env["res.partner"].create({
            "name": "No Email Partner",
        })
        product = self.env["product.product"].search([], limit=1)
        order = self.env["sale.order"].create({
            "partner_id": partner_no_email.id,
            "order_line": [(0, 0, {
                "product_id": product.id, "product_uom_qty": 1,
            })],
        })
        before = len(order.message_ids)
        result = self.tools.draft_customer_email(
            self.env, order_id=order.id,
            subject="Status update",
            body="Wanted to touch base on your order.",
        )
        self.assertTrue(result["ok"])
        self.assertIn("warning", result)
        self.assertEqual(result["warning"], "customer has no email on file")
        # Message still posted despite missing partner email.
        self.assertGreater(len(order.message_ids), before)

    def test_draft_customer_email_registered_with_correct_persona(self):
        from odoo.addons.southbrook_hermes.tools.decorator import TOOL_REGISTRY
        entry = next(
            (t for t in TOOL_REGISTRY if t["slug"] == "draft_customer_email"),
            None,
        )
        self.assertIsNotNone(entry, "draft_customer_email not in TOOL_REGISTRY")
        self.assertEqual(set(entry["personas"]), {"sales_rep", "mfg_manager"})
        self.assertEqual(entry["tier"], "T2")
        self.assertEqual(entry["scope"], "own_order")
        self.assertNotIn("trade_partner", entry["personas"])
