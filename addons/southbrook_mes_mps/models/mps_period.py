# SPDX-License-Identifier: LGPL-3.0-only
"""MPS Period — rolling 13-week master production schedule per product.

SAMI PRD §4.4 pillar: hand-rolled because native ``mrp_mps`` is
Enterprise-only and not installable on this CE build.
"""
import logging
from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def _iso_week_start(d):
    """Return the Monday of the ISO week containing ``d``."""
    return d - timedelta(days=d.weekday())


class SouthbrookMesMpsMpsPeriod(models.Model):
    _name = "southbrook.mes_mps.mps_period"
    _description = "MPS Period (Rolling 13-Week)"
    _inherit = ["mail.thread"]
    _order = "week_start asc, product_id asc"

    # v19: UNIQUE must be uppercase. Lowercase silently no-ops.
    # We use the models.Constraint API because the legacy
    # constraint list on the model body is dropped silently in v19.
    _unique_product_week = models.Constraint(
        "UNIQUE(product_id, week_start)",
        "An MPS period for this product and week already exists.",
    )

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        ondelete="cascade",
        tracking=True,
    )
    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Product Template",
        required=True,
        ondelete="cascade",
    )
    week_start = fields.Date(
        string="Week Start (Mon)",
        required=True,
        tracking=True,
    )
    week_number = fields.Integer(
        string="ISO Week",
        compute="_compute_week_year",
        store=True,
    )
    year = fields.Integer(
        string="Year",
        compute="_compute_week_year",
        store=True,
    )
    forecast_qty = fields.Float(
        string="Forecast Qty",
        required=True,
        default=0.0,
        tracking=True,
    )
    actual_demand_qty = fields.Float(
        string="Actual Demand (SOL)",
        compute="_compute_actual_demand",
    )
    planned_supply_qty = fields.Float(
        string="Planned Supply (MO)",
        compute="_compute_planned_supply",
    )
    safety_stock = fields.Float(string="Safety Stock", default=0.0)
    to_supply_qty = fields.Float(
        string="To Supply",
        compute="_compute_to_supply",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("approved", "Approved"),
            ("executed", "Executed"),
        ],
        default="draft",
        tracking=True,
        required=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                seq = self.env["ir.sequence"].next_by_code(
                    "southbrook.mes_mps.mps_period"
                )
                if seq:
                    vals["name"] = seq
                else:
                    # Fall back to a deterministic stamp so create
                    # never blocks on a missing sequence (sequence
                    # data file loads in the same install pass).
                    ws = vals.get("week_start")
                    if ws:
                        if isinstance(ws, str):
                            ws = fields.Date.from_string(ws)
                        iso = ws.isocalendar()
                        vals["name"] = "MPS/%s-%02d" % (iso[0], iso[1])
                    else:
                        vals["name"] = "MPS/NEW"
            if vals.get("product_id") and not vals.get("product_tmpl_id"):
                prod = self.env["product.product"].browse(vals["product_id"])
                vals["product_tmpl_id"] = prod.product_tmpl_id.id
        return super().create(vals_list)

    @api.depends("week_start")
    def _compute_week_year(self):
        for rec in self:
            if rec.week_start:
                iso = rec.week_start.isocalendar()
                rec.year = iso[0]
                rec.week_number = iso[1]
            else:
                rec.year = 0
                rec.week_number = 0

    @api.depends("product_id", "week_start")
    def _compute_actual_demand(self):
        SOL = self.env["sale.order.line"]
        for rec in self:
            if not (rec.product_id and rec.week_start):
                rec.actual_demand_qty = 0.0
                continue
            week_end = rec.week_start + timedelta(days=7)
            domain = [
                ("product_id", "=", rec.product_id.id),
                ("state", "in", ("sale", "done")),
                ("order_id.date_order", ">=", rec.week_start),
                ("order_id.date_order", "<", week_end),
            ]
            lines = SOL.search(domain)
            rec.actual_demand_qty = sum(lines.mapped("product_uom_qty"))

    @api.depends("product_id", "week_start")
    def _compute_planned_supply(self):
        MO = self.env["mrp.production"]
        for rec in self:
            if not (rec.product_id and rec.week_start):
                rec.planned_supply_qty = 0.0
                continue
            week_end = rec.week_start + timedelta(days=7)
            domain = [
                ("product_id", "=", rec.product_id.id),
                ("state", "in", ("confirmed", "progress", "to_close")),
                ("date_start", ">=", rec.week_start),
                ("date_start", "<", week_end),
            ]
            mos = MO.search(domain)
            rec.planned_supply_qty = sum(mos.mapped("product_qty"))

    @api.depends(
        "forecast_qty",
        "safety_stock",
        "planned_supply_qty",
        "product_id",
    )
    def _compute_to_supply(self):
        for rec in self:
            on_hand = 0.0
            if rec.product_id:
                # qty_available is on product.product in CE.
                on_hand = rec.product_id.qty_available or 0.0
            rec.to_supply_qty = (
                rec.forecast_qty
                + rec.safety_stock
                - rec.planned_supply_qty
                - on_hand
            )

    @api.model
    def action_generate_rolling_13_weeks(self, product_id):
        """Create the next 13 weekly MPS rows for ``product_id``.

        Existing rows are left untouched (the unique key on
        ``(product_id, week_start)`` would otherwise raise). Returns
        the recordset (newly created + pre-existing) for the window.
        """
        if not product_id:
            raise UserError(_("A product is required to seed MPS rows."))
        if isinstance(product_id, models.BaseModel):
            product = product_id
        else:
            product = self.env["product.product"].browse(int(product_id))
        if not product.exists():
            raise UserError(_("Unknown product %s") % product_id)
        today = fields.Date.context_today(self)
        start = _iso_week_start(today)
        rows = self.env["southbrook.mes_mps.mps_period"]
        existing = self.search(
            [
                ("product_id", "=", product.id),
                ("week_start", ">=", start),
                ("week_start", "<", start + timedelta(weeks=13)),
            ]
        )
        existing_starts = set(existing.mapped("week_start"))
        to_create = []
        for week in range(13):
            ws = start + timedelta(weeks=week)
            if ws in existing_starts:
                continue
            to_create.append({
                "product_id": product.id,
                "product_tmpl_id": product.product_tmpl_id.id,
                "week_start": ws,
                "forecast_qty": 0.0,
                "state": "draft",
            })
        if to_create:
            rows |= self.create(to_create)
        return rows | existing

    def action_approve(self):
        self.write({"state": "approved"})

    def action_mark_executed(self):
        self.write({"state": "executed"})
