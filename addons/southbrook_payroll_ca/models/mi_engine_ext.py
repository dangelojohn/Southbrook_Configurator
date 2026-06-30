# SPDX-License-Identifier: LGPL-3.0-only
"""Manufacturing Intelligence — Payroll tiles.

Per the v19 quirk in project memory (odoo19_abstract_model_inherit_trap),
``southbrook.mi.engine`` in southbrook_manufacturing_intelligence is an
AbstractModel and cannot be _inherit'd as a models.Model. We therefore
publish a NEW concrete model that the MI dashboard reads.
"""

from datetime import timedelta

from odoo import api, fields, models

from .cra_calc import eht_ontario_2026


class SouthbrookPayrollMiTiles(models.Model):
    _name = "southbrook.payroll.mi_tiles"
    _description = "Southbrook Payroll MI Tiles (snapshot)"
    _rec_name = "label"

    label = fields.Char(default="Payroll Snapshot", required=True)
    payroll_runs_this_year = fields.Integer(compute="_compute_tiles")
    cert_expiring_30d_count = fields.Integer(compute="_compute_tiles")
    headcount = fields.Integer(compute="_compute_tiles")
    bi_weekly_total_gross_last = fields.Float(compute="_compute_tiles")
    wsib_premium_ytd = fields.Float(compute="_compute_tiles")
    eht_ontario_ytd = fields.Float(compute="_compute_tiles")

    @api.depends("label")
    def _compute_tiles(self):
        today = fields.Date.context_today(self)
        jan_first = today.replace(month=1, day=1)
        soon = today + timedelta(days=30)
        Run = self.env["southbrook.payroll.run"]
        Cert = self.env["southbrook.payroll.certification"]
        Employee = self.env["hr.employee"]
        Payslip = self.env["southbrook.payroll.payslip"]

        runs_this_year = Run.search_count(
            [("pay_date", ">=", jan_first), ("pay_date", "<=", today)]
        )
        expiring = Cert.search_count(
            [
                ("expires_at", ">=", today),
                ("expires_at", "<=", soon),
            ]
        )
        headcount = Employee.search_count([("active", "=", True)])
        last_run = Run.search(
            [("state", "in", ("computed", "posted", "paid"))],
            order="pay_date desc",
            limit=1,
        )
        last_gross = last_run.total_gross if last_run else 0.0

        ytd_slips = Payslip.search(
            [
                ("state", "in", ("posted", "paid")),
                ("payroll_run_id.pay_date", ">=", jan_first),
            ]
        )
        wsib_ytd = sum(ytd_slips.mapped("wsib_employer_premium"))
        gross_ytd = sum(ytd_slips.mapped("gross"))
        eht_ytd = eht_ontario_2026(gross_ytd)

        for rec in self:
            rec.payroll_runs_this_year = runs_this_year
            rec.cert_expiring_30d_count = expiring
            rec.headcount = headcount
            rec.bi_weekly_total_gross_last = last_gross
            rec.wsib_premium_ytd = wsib_ytd
            rec.eht_ontario_ytd = eht_ytd
