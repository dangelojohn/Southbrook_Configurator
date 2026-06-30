# SPDX-License-Identifier: LGPL-3.0-only
"""Record of Employment (Service Canada ROE).

Computes Block 15C (insurable earnings per pay period for the last
27 pay periods) and Block 15A (total insurable hours).  Filing the
actual ROE XML to Service Canada is out of scope; this is the data
layer the filer reads from.
"""

from odoo import _, api, fields, models


class SouthbrookPayrollRoe(models.Model):
    _name = "southbrook.payroll.roe"
    _description = "Southbrook Record of Employment"
    _inherit = ["mail.thread"]
    _order = "create_date desc, id desc"

    name = fields.Char(
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _("New"),
        tracking=True,
    )
    employee_id = fields.Many2one("hr.employee", required=True, tracking=True)
    first_day_worked = fields.Date(tracking=True)
    last_day_worked = fields.Date(tracking=True)
    last_day_for_which_paid = fields.Date(tracking=True)
    reason = fields.Selection(
        [
            ("A", "A — Shortage of work / End of contract or season"),
            ("B", "B — Strike or lockout"),
            ("D", "D — Illness or injury"),
            ("E", "E — Quit"),
            ("F", "F — Maternity"),
            ("G", "G — Mandatory retirement"),
            ("H", "H — Work-sharing"),
            ("K", "K — Other"),
            ("M", "M — Dismissal"),
            ("N", "N — Leave of absence"),
            ("P", "P — Parental"),
        ],
        tracking=True,
    )
    final_pay_period_end = fields.Date(tracking=True)
    total_insurable_hours = fields.Float(tracking=True)
    total_insurable_earnings = fields.Float(tracking=True)
    comments = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                seq = self.env["ir.sequence"].next_by_code("southbrook.payroll.roe")
                vals["name"] = seq or _("New")
        return super().create(vals_list)

    def action_compute_box_15c(self):
        """Sum insurable earnings + hours from the last 27 posted payslips.

        Service Canada requires Block 15C to list per-period earnings for
        the 27 most recent periods (for bi-weekly, this is roughly 1
        year). We aggregate to a single total here; per-period breakdown
        is left to the report layer.
        """
        Payslip = self.env["southbrook.payroll.payslip"]
        for rec in self:
            slips = Payslip.search(
                [
                    ("employee_id", "=", rec.employee_id.id),
                    ("state", "in", ("posted", "paid")),
                ],
                order="create_date desc",
                limit=27,
            )
            rec.total_insurable_earnings = sum(slips.mapped("gross"))
            # Insurable hours: assume 80 hrs per bi-weekly period absent
            # explicit timesheet integration. Real impl reads from
            # hr.attendance / account.analytic.line. We use 80 * count
            # as the audit-traceable default.
            rec.total_insurable_hours = 80.0 * len(slips)
            rec.message_post(
                body=_("Computed Block 15C from %d posted payslips.") % len(slips)
            )
