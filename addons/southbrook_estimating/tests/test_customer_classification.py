# SPDX-License-Identifier: LGPL-3.0-only
"""Customer classification (2026-07-06):
- Pipeline stage (computed from the customer's orders): Prospect < Quote <
  Proposal < Active Job — groupable/filterable in Contacts.
- Property type via Contact Tags (res.partner.category) — Residential
  (House/Condo/Apartment) + Commercial (Office/Retail/Restaurant/Multi-unit).
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "customer_classification")
class TestCustomerClassification(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]
        cls.SO = cls.env["sale.order"]

    def _partner(self, name):
        return self.Partner.create({"name": name})

    def test_prospect_when_no_orders(self):
        p = self._partner("No Orders Co")
        self.assertEqual(p.southbrook_pipeline_stage, "prospect")

    def test_quote_then_proposal_then_active_job(self):
        p = self._partner("Progressing Customer")
        o = self.SO.create({"partner_id": p.id})  # draft
        p.invalidate_recordset(["southbrook_pipeline_stage"])
        self.assertEqual(p.southbrook_pipeline_stage, "quote")
        o.state = "sent"
        p.invalidate_recordset(["southbrook_pipeline_stage"])
        self.assertEqual(p.southbrook_pipeline_stage, "proposal")
        o.state = "sale"
        p.invalidate_recordset(["southbrook_pipeline_stage"])
        self.assertEqual(p.southbrook_pipeline_stage, "active_job")

    def test_active_job_wins_over_a_second_draft(self):
        p = self._partner("Repeat Customer")
        self.SO.create({"partner_id": p.id, "state": "sale"})
        self.SO.create({"partner_id": p.id})  # a new draft too
        p.invalidate_recordset(["southbrook_pipeline_stage"])
        self.assertEqual(
            p.southbrook_pipeline_stage, "active_job",
            "a confirmed order outranks a fresh draft")

    def test_property_type_tag_tree_seeded(self):
        for xmlid, parent in [
            ("partner_category_house", "partner_category_residential"),
            ("partner_category_condo", "partner_category_residential"),
            ("partner_category_apartment", "partner_category_residential"),
            ("partner_category_office", "partner_category_commercial"),
            ("partner_category_retail", "partner_category_commercial"),
            ("partner_category_restaurant", "partner_category_commercial"),
            ("partner_category_multi_unit", "partner_category_commercial"),
        ]:
            tag = self.env.ref("southbrook_estimating.%s" % xmlid)
            self.assertEqual(
                tag.parent_id,
                self.env.ref("southbrook_estimating.%s" % parent),
                "%s must sit under %s" % (xmlid, parent))
