# SPDX-License-Identifier: LGPL-3.0-only
"""``southbrook.hermes.recommendation`` — Central Command bus-publish hook.

Phase-2. Publish-only (never writes to southbrook.command.exception). Gated by
``_cc_hooks_enabled()`` — the single guard in ``_sb_cc_publish_each`` covers
both ``create`` and the four state-transition actions. Publishes on
``sb_cc_hermes_<company_id>`` (D5 §1.3). This model has no company_id, so the
acting user's current company is used.
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class SouthbrookHermesRecommendation(models.Model):
    _inherit = "southbrook.hermes.recommendation"

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        self._sb_cc_publish_each(recs)
        return recs

    def action_mark_ready(self):
        result = super().action_mark_ready()
        self._sb_cc_publish_each(self)
        return result

    def action_approve(self):
        result = super().action_approve()
        self._sb_cc_publish_each(self)
        return result

    def action_reject(self):
        result = super().action_reject()
        self._sb_cc_publish_each(self)
        return result

    def action_apply(self):
        result = super().action_apply()
        self._sb_cc_publish_each(self)
        return result

    def _sb_cc_publish_each(self, recs):
        if not self.env["southbrook.command.exception"]._cc_hooks_enabled():
            return
        for rec in recs:
            try:
                rec._sb_cc_publish()
            except Exception:  # noqa: BLE001
                _logger.exception(
                    "Central Command hermes publish failed for "
                    "southbrook.hermes.recommendation %s — non-fatal", rec.id,
                )

    def _sb_cc_publish(self):
        self.ensure_one()
        company_id = self.env.company.id
        self.env["southbrook.command.exception"]._publish(
            "sb_cc_hermes",
            "hermes_upsert",
            {
                "recommendation_id": self.id,
                "state": self.state,
                "recommendation_type": self.recommendation_type,
                "priority": self.priority,
                "source_model": self.source_model,
                "source_res_id": self.source_res_id,
                "company_id": company_id,
            },
        )
