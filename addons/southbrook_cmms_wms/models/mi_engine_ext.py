# SPDX-License-Identifier: LGPL-3.0-only
import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SouthbrookCmmsMiTiles(models.Model):
    _name = "southbrook.cmms.mi_tiles"
    _description = "CMMS Manufacturing-Intelligence Snapshot Tiles"

    label = fields.Char(string="Label", default="Maintenance & Logistics Snapshot")
    as_of = fields.Datetime(string="As Of", default=fields.Datetime.now)
    mtbf_avg_30d = fields.Float(string="MTBF avg (30d)", compute="_compute_tiles", store=False)
    mttr_avg_30d = fields.Float(string="MTTR avg (30d)", compute="_compute_tiles", store=False)
    open_breakdowns_count = fields.Integer(
        string="Open Breakdowns", compute="_compute_tiles", store=False)
    service_contracts_expiring_60d_count = fields.Integer(
        string="Contracts expiring (60d)", compute="_compute_tiles", store=False)
    oversize_pickings_pending_count = fields.Integer(
        string="Oversize pickings pending", compute="_compute_tiles", store=False)
    landed_cost_value_30d = fields.Monetary(
        string="Landed cost (30d)",
        currency_field="currency_id",
        compute="_compute_tiles",
        store=False,
    )
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id)

    @api.depends("as_of")
    def _compute_tiles(self):
        today = fields.Date.context_today(self)
        cutoff = today - timedelta(days=30)
        Report = self.env["southbrook.cmms.mtbf_mttr_report"].sudo()
        Alert = self.env["southbrook.cmms.breakdown_alert"].sudo()
        Contract = self.env["southbrook.cmms.service_contract"].sudo()
        Picking = self.env["stock.picking"].sudo()
        for rec in self:
            recents = Report.search([("as_of_date", ">=", cutoff)])
            rec.mtbf_avg_30d = (
                sum(recents.mapped("mtbf_hours")) / len(recents)
                if recents else 0.0)
            rec.mttr_avg_30d = (
                sum(recents.mapped("mttr_hours")) / len(recents)
                if recents else 0.0)
            rec.open_breakdowns_count = Alert.search_count([("state", "=", "open")])
            rec.service_contracts_expiring_60d_count = Contract.search_count([
                ("days_to_expiry", ">", 0),
                ("days_to_expiry", "<=", 60),
            ])
            rec.oversize_pickings_pending_count = Picking.search_count([
                ("is_oversize_load", "=", True),
                ("oversize_permit_state", "in", ("pending", "not_required")),
                ("state", "in", ("confirmed", "assigned")),
            ])
            value_30d = 0.0
            LandedCost = self.env.get("stock.landed.cost")
            if LandedCost is not None:
                try:
                    LC = self.env["stock.landed.cost"].sudo()
                    costs = LC.search([("create_date", ">=", cutoff)])
                    value_30d = sum(costs.mapped("amount_total")) if costs else 0.0
                except Exception:  # noqa: BLE001
                    _logger.warning(
                        "CMMS MI tiles: stock.landed.cost lookup failed",
                        exc_info=True)
            rec.landed_cost_value_30d = value_30d

    def action_refresh(self):
        self.invalidate_recordset([
            "mtbf_avg_30d", "mttr_avg_30d", "open_breakdowns_count",
            "service_contracts_expiring_60d_count",
            "oversize_pickings_pending_count", "landed_cost_value_30d",
        ])
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }
