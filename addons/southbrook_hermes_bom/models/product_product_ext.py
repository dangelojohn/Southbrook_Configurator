# SPDX-License-Identifier: LGPL-3.0-only
"""Proxy launcher on product.product → opens the wizard for the variant's template."""
from odoo import _, models
from odoo.exceptions import UserError


class ProductProduct(models.Model):
    _inherit = "product.product"

    def action_hermes_research_and_build_bom(self):
        """Variant-form launcher.

        Routes through product_tmpl_id because Hermes operates on the
        template (BOMs are template-bound, enrichment lives on the
        template). The job records the variant id so the audit still
        reflects which variant prompted the run.
        """
        self.ensure_one()
        if not self.product_tmpl_id:
            raise UserError(_(
                "This variant has no template — cannot run Hermes."
            ))
        job = self.env["hermes.research.job"].create({
            "product_template_id": self.product_tmpl_id.id,
            "product_product_id": self.id,
            "state": "draft",
        })
        wizard = self.env["hermes.wizard"].create({"job_id": job.id})
        return {
            "type": "ir.actions.act_window",
            "name": _("Hermes: Research & Build BOM"),
            "res_model": "hermes.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }
