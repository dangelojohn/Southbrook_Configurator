# SPDX-License-Identifier: LGPL-3.0-only
"""Thin behavioral hook: capture a completion observation when a work order
finishes. Does NOT write any MRP planning field — it only reads the finished WO
and creates an oiq.completion.observation, preserving the read-only-vs-MRP posture
for scheduling data.
"""
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    def button_finish(self):
        res = super().button_finish()
        service = self.env["oiq.scheduling.intelligence"]
        for wo in self:
            if wo.state == "done":
                # Never let calibration capture break a shop's ability to finish
                # a work order — the harvest cron will pick it up on the next pass.
                try:
                    service._capture_observation(wo)
                except Exception:  # noqa: BLE001
                    _logger.exception(
                        "OdooIQ: failed to capture observation for workorder %s", wo.id)
        return res
