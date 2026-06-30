# SPDX-License-Identifier: LGPL-3.0-only
"""Work-In-Process snapshot at a date.

Walks open ``mrp.production`` records and sums consumed components at
standard cost. Each open MO contributes one or more lines to the report,
one per consumed component (qty_done from stock.move).
"""

from odoo import _, api, fields, models


OPEN_MO_STATES = ("confirmed", "progress", "to_close")


class SouthbrookFinanceWipReport(models.Model):
    _name = "southbrook.finance.wip_report"
    _description = "Southbrook Finance - WIP Report"
    _order = "as_of_date desc, id desc"

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
    )
    as_of_date = fields.Date(
        string="As Of Date",
        required=True,
        default=fields.Date.context_today,
    )
    line_ids = fields.One2many(
        "southbrook.finance.wip_line",
        "wip_report_id",
        string="WIP Lines",
    )
    total_wip_value = fields.Monetary(
        string="Total WIP",
        compute="_compute_total_wip",
        store=True,
        currency_field="currency_id",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        string="Currency",
        store=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                seq = self.env["ir.sequence"].next_by_code(
                    "southbrook.finance.wip_report"
                )
                vals["name"] = seq or "WIP/%s" % fields.Date.today().isoformat()
        return super().create(vals_list)

    @api.depends("line_ids.wip_value")
    def _compute_total_wip(self):
        for rec in self:
            rec.total_wip_value = sum(line.wip_value for line in rec.line_ids)

    def action_compute(self):
        """Wipe and re-populate the lines from currently open MOs."""
        Line = self.env["southbrook.finance.wip_line"]
        Production = self.env["mrp.production"]
        for rec in self:
            rec.line_ids.unlink()
            mos = Production.search(
                [
                    ("state", "in", OPEN_MO_STATES),
                    ("company_id", "=", rec.company_id.id),
                ]
            )
            for mo in mos:
                for move in mo.move_raw_ids:
                    # qty_done is the consumed quantity in v19; on older
                    # builds it sits on the underlying move.line records.
                    qty = move.quantity if hasattr(move, "quantity") else 0.0
                    if not qty:
                        # Fallback when ``quantity`` not yet computed.
                        qty = sum(move.move_line_ids.mapped("quantity"))
                    if qty <= 0:
                        continue
                    Line.create(
                        {
                            "wip_report_id": rec.id,
                            "production_id": mo.id,
                            "product_id": move.product_id.id,
                            "qty_consumed": qty,
                            "standard_cost": move.product_id.standard_price or 0.0,
                        }
                    )
        return True
