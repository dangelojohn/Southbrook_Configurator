# SPDX-License-Identifier: LGPL-3.0-only
"""Audit/log row for each Hermes research dispatch.

One job per wizard invocation. Lives outside the wizard's transient
lifetime so the audit trail survives long after the wizard form closes.
"""
import json
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Datetime as fields_Datetime

_logger = logging.getLogger(__name__)


# Default GC retention if no ir.config_parameter override.
DEFAULT_RETENTION_DAYS = 180


class HermesResearchJob(models.Model):
    _name = "hermes.research.job"
    _description = "Hermes Research Job"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(
        string="Reference",
        required=True,
        readonly=True,
        default=lambda self: _("New"),
    )
    product_template_id = fields.Many2one(
        comodel_name="product.template",
        string="Template",
        required=True,
        ondelete="cascade",
        tracking=True,
    )
    product_product_id = fields.Many2one(
        comodel_name="product.product",
        string="Variant",
        ondelete="set null",
        help="Optional — set when the job was dispatched from a specific "
             "variant rather than its template.",
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("running", "Running"),
            ("review", "Awaiting Review"),
            ("applied", "Applied"),
            ("failed", "Failed"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    hermes_request_payload = fields.Text(
        string="Request Payload (JSON)",
        groups="base.group_system",
        help="Outbound payload sent to the Hermes endpoint, including "
             "cost / internal-notes / southbrook_* context fields. "
             "Admin-only because a reviewer whose product.template "
             "access is later narrowed could otherwise still read the "
             "snapshot here.",
    )
    hermes_raw_response = fields.Text(string="Raw Response (JSON)")
    hermes_parsed_enrichment = fields.Text(string="Parsed Enrichment (JSON)")
    hermes_parsed_bom = fields.Text(string="Parsed BOM (JSON)")
    error_message = fields.Text(string="Error Detail")
    applied_fields = fields.Text(
        string="Applied Fields",
        help="JSON list of {model, field, old, new} entries that were "
             "actually written when the wizard's Apply ran. Empty until "
             "state = applied.",
    )
    bom_id = fields.Many2one(
        comodel_name="mrp.bom",
        string="BOM",
        ondelete="set null",
    )
    source_urls = fields.Text(
        string="Source URLs (JSON)",
        help="JSON list of source URLs the Hermes response cited.",
    )
    confidence_summary = fields.Char(string="Confidence")
    created_by = fields.Many2one(
        comodel_name="res.users",
        string="Triggered By",
        default=lambda self: self.env.user,
        readonly=True,
    )

    def _ensure_name(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                template_id = vals.get("product_template_id")
                template_label = ""
                if template_id:
                    template = self.env["product.template"].browse(template_id)
                    template_label = template.display_name or ""
                seq = self.env["ir.sequence"].next_by_code(
                    "hermes.research.job"
                )
                if seq:
                    vals["name"] = (
                        "{seq} — {label}".format(seq=seq, label=template_label)
                        if template_label
                        else seq
                    )
                else:
                    vals["name"] = _(
                        "Hermes Job — %s"
                    ) % (template_label or _("Unspecified"))
        return vals_list

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = self._ensure_name(list(vals_list))
        records = super().create(vals_list)
        _logger.info(
            "Created %d hermes.research.job record(s): %s",
            len(records), records.ids,
        )
        return records

    def unlink(self):
        """Refuse to drop applied audit rows unless the caller is admin.

        The whole point of the audit row is to survive the wizard. A
        regular `group_hermes_user` should not be able to erase a
        successfully-applied job to cover up a bad apply. Admins can
        still unlink (e.g. for the GC cron — see _gc_old_jobs which
        sudo's its own unlink call).
        """
        if not self.env.is_admin():
            protected = self.filtered(lambda j: j.state == "applied")
            if protected:
                raise UserError(_(
                    "Cannot delete applied Hermes research jobs (%s) — "
                    "they are part of the audit trail. Ask an "
                    "administrator if removal is required."
                ) % ", ".join(protected.mapped("name")))
        return super().unlink()

    @api.model
    def _gc_old_jobs(self):
        """Cron entry: drop old non-applied jobs.

        Applied jobs are kept forever — they're the audit trail.
        Draft/running/review/failed rows older than the retention
        window are removed to keep the table small.

        Retention window is tunable via ir.config_parameter key
        ``southbrook_hermes_bom.retention_days`` (default 180).
        """
        ICP = self.env["ir.config_parameter"].sudo()
        try:
            days = int(ICP.get_param(
                "southbrook_hermes_bom.retention_days",
                DEFAULT_RETENTION_DAYS,
            ))
        except (TypeError, ValueError):
            days = DEFAULT_RETENTION_DAYS
        if days <= 0:
            _logger.info(
                "Hermes GC disabled (retention_days=%s); skipping.", days,
            )
            return 0
        cutoff = fields_Datetime.now() - timedelta(days=days)
        old = self.sudo().search([
            ("state", "in", ("draft", "running", "review", "failed")),
            ("create_date", "<", cutoff),
        ])
        count = len(old)
        if count:
            _logger.info(
                "Hermes GC removing %d old non-applied jobs "
                "(older than %s days).", count, days,
            )
            old.unlink()
        return count

    def get_source_urls_list(self):
        """Helper for the view: parse source_urls JSON into a list."""
        self.ensure_one()
        if not self.source_urls:
            return []
        try:
            return [str(u) for u in (json.loads(self.source_urls) or [])
                    if isinstance(u, (str, dict))]
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
