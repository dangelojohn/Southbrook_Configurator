# SPDX-License-Identifier: LGPL-3.0-only
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SouthbrookCmmsServiceContract(models.Model):
    _name = "southbrook.cmms.service_contract"
    _description = "CMMS Service Contract"
    _inherit = ["mail.thread"]
    _order = "date_end asc, id desc"

    name = fields.Char(string="Reference", required=True, tracking=True)
    vendor_id = fields.Many2one(
        "res.partner",
        string="Vendor",
        required=True,
        domain=[("supplier_rank", ">", 0)],
        tracking=True,
    )
    equipment_ids = fields.Many2many(
        "maintenance.equipment",
        relation="southbrook_cmms_contract_equip_rel",
        column1="contract_id",
        column2="equipment_id",
        string="Equipment",
    )
    date_start = fields.Date(string="Start", tracking=True)
    date_end = fields.Date(string="End", required=True, tracking=True)
    annual_value = fields.Monetary(
        string="Annual Value", currency_field="currency_id", tracking=True)
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
    )
    days_to_expiry = fields.Integer(
        string="Days to Expiry", compute="_compute_days_to_expiry", store=True,
        help="Stored, but depends only on date_end (not 'today'), so it does "
             "NOT re-fire as the calendar advances. The daily expiry cron "
             "force-recomputes it so state/alerts stay accurate.",
    )
    last_alert_date = fields.Date(
        string="Last Expiry Alert",
        help="Set by the daily cron when it posts an expiry alert; used to "
             "throttle re-alerts to a weekly cadence.",
    )
    expiry_alert_at = fields.Selection(
        [("30", "30 days"), ("60", "60 days"), ("90", "90 days"), ("180", "180 days")],
        default="60",
        required=True,
    )
    state = fields.Selection(
        [
            ("active", "Active"),
            ("expiring_soon", "Expiring Soon"),
            ("expired", "Expired"),
            ("renewed", "Renewed"),
            ("cancelled", "Cancelled"),
        ],
        compute="_compute_state",
        inverse="_inverse_state",
        store=True,
        tracking=True,
    )
    state_override = fields.Selection(
        [("renewed", "Renewed"), ("cancelled", "Cancelled")],
        string="Manual State Override",
        help="When set, freezes state to the chosen value (renewed/cancelled). "
             "Clear to resume automatic active/expiring/expired computation.",
    )

    @api.depends("date_end")
    def _compute_days_to_expiry(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.days_to_expiry = (rec.date_end - today).days if rec.date_end else 0

    @api.depends("days_to_expiry", "expiry_alert_at", "state_override")
    def _compute_state(self):
        for rec in self:
            if rec.state_override:
                rec.state = rec.state_override
                continue
            days = rec.days_to_expiry
            alert_at = int(rec.expiry_alert_at or "60")
            if days < 0:
                rec.state = "expired"
            elif days <= alert_at:
                rec.state = "expiring_soon"
            else:
                rec.state = "active"

    def _inverse_state(self):
        # Manager override path: writing renewed/cancelled stores it; other
        # values fall back to automatic computation.
        for rec in self:
            if rec.state in ("renewed", "cancelled"):
                rec.state_override = rec.state
            else:
                rec.state_override = False

    @api.model
    def _cron_check_expiry(self):
        today = fields.Date.context_today(self)
        manager_group = self.env.ref(
            "southbrook_cmms_wms.group_southbrook_cmms_manager",
            raise_if_not_found=False,
        )
        # v19 renamed res.groups.users -> user_ids (the old name AttributeError'd
        # here, so the expiry cron failed 100% of runs). all_user_ids also picks
        # up managers who hold the group via implied_ids.
        partners = (
            manager_group.all_user_ids.partner_id
            if manager_group else self.env["res.partner"]
        )
        contracts = self.search([
            ("date_end", ">=", today),
            ("state_override", "=", False),
        ])
        # days_to_expiry / state are stored computes keyed on date_end (not
        # 'today'), so they DON'T re-fire as the calendar advances — a contract
        # created 90 days out keeps reporting 90 forever. Force-recompute here so
        # the window filter below (and the UI/search) reflect today.
        contracts.invalidate_recordset(["days_to_expiry", "state"])
        contracts._compute_days_to_expiry()
        contracts._compute_state()
        sent = 0
        for c in contracts:
            try:
                alert_at = int(c.expiry_alert_at or "60")
                if not (0 <= c.days_to_expiry <= alert_at):
                    continue
                # Throttle re-alerts to a weekly cadence — without this the cron
                # re-posted a manager alert every day for the whole alert window.
                if c.last_alert_date and (today - c.last_alert_date).days < 7:
                    continue
                body = ("Service contract <b>%s</b> with vendor <b>%s</b> "
                        "expires in %d day(s) (end: %s).") % (
                            c.name, c.vendor_id.display_name,
                            c.days_to_expiry, c.date_end)
                c.message_post(
                    body=body,
                    partner_ids=partners.ids if partners else [],
                    subject="CMMS service contract expiring soon",
                )
                c.last_alert_date = today
                sent += 1
            except Exception:  # noqa: BLE001 — one bad row must not abort the sweep
                _logger.exception(
                    "CMMS expiry sweep: contract %s failed", c.display_name)
        _logger.info("CMMS service contract expiry sweep: %d alerts posted", sent)
        return sent
