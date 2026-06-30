# SPDX-License-Identifier: LGPL-3.0-only
"""Buttons on product.template to launch + browse Hermes research jobs."""
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    hermes_research_job_count = fields.Integer(
        string="Hermes Jobs",
        compute="_compute_hermes_research_job_count",
    )

    def _compute_hermes_research_job_count(self):
        """Smart-button counter — total Hermes jobs ever run on this template.

        Counted in a single grouped query rather than per-record search
        so opening the Configurable Templates list with many rows
        doesn't fire N+1 SELECTs against hermes.research.job.
        """
        if not self.ids:
            for r in self:
                r.hermes_research_job_count = 0
            return
        data = self.env["hermes.research.job"].sudo()._read_group(
            domain=[("product_template_id", "in", self.ids)],
            groupby=["product_template_id"],
            aggregates=["__count"],
        )
        counts = {tpl.id: count for tpl, count in data}
        for r in self:
            r.hermes_research_job_count = counts.get(r.id, 0)

    def action_hermes_research_and_build_bom(self):
        """Open the Hermes wizard against this template.

        Creates a fresh hermes.research.job in 'draft' and hands its id
        to the wizard via context. No external network call yet — the
        wizard's "Run" button is what dispatches.
        """
        self.ensure_one()
        if not self.id:
            raise UserError(_(
                "Save the product before launching Hermes research."
            ))
        job = self.env["hermes.research.job"].create({
            "product_template_id": self.id,
            "state": "draft",
        })
        wizard = self.env["hermes.wizard"].create({
            "job_id": job.id,
        })
        _logger.info(
            "Hermes wizard %s created for template %s (job %s)",
            wizard.id, self.id, job.id,
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Hermes: Research & Build BOM"),
            "res_model": "hermes.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_hermes_view_jobs(self):
        """Open a list of past Hermes jobs for this template."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Hermes Research Jobs"),
            "res_model": "hermes.research.job",
            "view_mode": "list,form",
            "domain": [("product_template_id", "=", self.id)],
            "context": {"default_product_template_id": self.id},
        }
