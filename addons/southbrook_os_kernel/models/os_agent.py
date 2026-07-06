# SPDX-License-Identifier: LGPL-3.0-only
"""``southbrook.os.agent`` — the OS Kernel's agent registry + daily budgets.

Spec: docs/OS_KERNEL_SPEC.md §5. Design invariants:

* Uniqueness on ``code`` is enforced with ``models.Constraint`` (NOT the
  legacy ``_sql_constraints``, which Odoo 19 silently ignores).
* ``check_and_consume`` rolls the daily counters over when ``budget_date``
  is not today (compared via ``fields.Date.context_today``), a 0 budget
  means unlimited, a disabled agent always refuses, and a successful check
  increments ``calls_today`` before returning True.
* ``cron_id`` points at ``ir.cron`` but the cron record itself is out of
  scope for this file (no data XML lives here).
"""
from odoo import api, fields, models


class SouthbrookOsAgent(models.Model):
    _name = "southbrook.os.agent"
    _description = "Southbrook OS Kernel — Agent Registry"
    _inherit = ["mail.thread"]

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True)
    purpose = fields.Text()
    feature_key = fields.Char(index=True, help="Links kernel calls to this agent.")
    cron_id = fields.Many2one("ir.cron", ondelete="set null")
    enabled = fields.Boolean(default=True, tracking=True)

    daily_call_budget = fields.Integer(
        default=0, help="0 = unlimited calls per day."
    )
    daily_token_budget = fields.Integer(
        default=0, help="0 = unlimited tokens per day."
    )
    calls_today = fields.Integer(readonly=True)
    tokens_today = fields.Integer(readonly=True)
    budget_date = fields.Date(readonly=True)
    last_run_at = fields.Datetime()
    last_status = fields.Char()

    _unique_code = models.Constraint(
        "unique(code)",
        "Agent code must be unique.",
    )

    def _reset_if_new_day(self):
        """Roll calls_today/tokens_today/budget_date over when the stored
        budget_date is not today. Internal helper shared by
        check_and_consume; never raises."""
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.budget_date != today:
                rec.write(
                    {
                        "budget_date": today,
                        "calls_today": 0,
                        "tokens_today": 0,
                    }
                )

    def _lock_row(self):
        """Take a row-level lock (SELECT ... FOR UPDATE) on this agent so a
        concurrent check_and_consume/record_usage on another worker blocks
        until this transaction commits, then re-read fresh counter values.
        Never raises (a lock failure degrades to the unlocked soft-limit
        behavior rather than blocking the kernel call)."""
        self.ensure_one()
        try:
            self.env.cr.execute(
                "SELECT id FROM southbrook_os_agent WHERE id = %s FOR UPDATE",
                (self.id,),
            )
            self.invalidate_recordset(
                ["calls_today", "tokens_today", "budget_date"]
            )
        except Exception:
            pass

    def check_and_consume(self, est_tokens=0):
        """Return True if this agent may run now, consuming one call unit.

        Resets the daily counters when budget_date != today. A disabled
        agent always returns False. 0 on either budget means unlimited for
        that dimension. On success, increments calls_today.

        Concurrency: the read-check-increment runs under a row lock
        (_lock_row) so two simultaneous kernel calls on the same feature
        cannot both pass a nearly-exhausted budget.
        """
        self.ensure_one()
        self._lock_row()
        self._reset_if_new_day()
        if not self.enabled:
            return False
        if self.daily_call_budget and self.calls_today >= self.daily_call_budget:
            return False
        if (
            self.daily_token_budget
            and (self.tokens_today + (est_tokens or 0)) > self.daily_token_budget
        ):
            return False
        self.write({"calls_today": self.calls_today + 1})
        return True

    def record_usage(self, tokens):
        """Add actual consumed tokens to today's running total."""
        self.ensure_one()
        self._lock_row()
        self._reset_if_new_day()
        self.write({"tokens_today": self.tokens_today + (tokens or 0)})
        return True

    @api.model
    def reset_daily(self):
        """Zero every agent's daily counters. Called by the (out-of-scope
        here) cron."""
        today = fields.Date.context_today(self)
        agents = self.search([])
        agents.write(
            {
                "budget_date": today,
                "calls_today": 0,
                "tokens_today": 0,
            }
        )
        return True
