# SPDX-License-Identifier: LGPL-3.0-only
from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook_os_kernel")
class TestOsAgentBudget(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Agent = cls.env["southbrook.os.agent"]

    def _make(self, **kw):
        vals = {
            "name": "Test Agent",
            "code": "test_agent_%s" % kw.get("code", "default"),
            "feature_key": "test_feature",
        }
        vals.update(kw)
        return self.Agent.create(vals)

    def test_unlimited_budget_always_passes(self):
        agent = self._make(code="unlimited", daily_call_budget=0, daily_token_budget=0)
        for _i in range(5):
            self.assertTrue(agent.check_and_consume())

    def test_call_budget_enforced(self):
        agent = self._make(code="call_budget", daily_call_budget=1)
        self.assertTrue(agent.check_and_consume())
        self.assertFalse(agent.check_and_consume())

    def test_token_budget_enforced(self):
        agent = self._make(code="token_budget", daily_token_budget=100)
        # First call under budget succeeds; record actual usage near the cap.
        self.assertTrue(agent.check_and_consume(est_tokens=50))
        agent.record_usage(90)
        # Next estimate would push tokens_today over the cap.
        self.assertFalse(agent.check_and_consume(est_tokens=50))

    def test_disabled_agent_always_false(self):
        agent = self._make(code="disabled", enabled=False)
        self.assertFalse(agent.check_and_consume())

    def test_reset_daily_zeroes_counters(self):
        agent = self._make(code="reset_me", daily_call_budget=1)
        self.assertTrue(agent.check_and_consume())
        self.assertEqual(agent.calls_today, 1)
        self.Agent.reset_daily()
        self.assertEqual(agent.calls_today, 0)
        self.assertEqual(agent.tokens_today, 0)
        self.assertEqual(agent.budget_date, fields.Date.context_today(agent))

    def test_budget_date_rollover_resets_counters(self):
        agent = self._make(code="rollover", daily_call_budget=1)
        self.assertTrue(agent.check_and_consume())
        self.assertFalse(agent.check_and_consume())
        # Simulate a new day by back-dating budget_date directly (no sleep).
        stale = fields.Date.context_today(agent) - timedelta(days=1)
        agent.write({"budget_date": stale})
        self.assertTrue(agent.check_and_consume(), "new day must reset the call budget")
