# SPDX-License-Identifier: LGPL-3.0-only
"""``southbrook.cmms.breakdown_alert`` — Central Command materialize hook.

Phase-2 event-driven materialization. Gated by ``_cc_hooks_enabled()``.
Verified against ``addons/southbrook_cmms_wms/models/breakdown_alert.py``:
severity (low/medium/high/critical passthrough), equipment_id (required,
provides company via maintenance.equipment.company_id), workcenter_id
(optional), name/description/state. No base ``create`` override — ``_inherit``
safe. Publishes on BOTH the exceptions and alerts channels (D5 §2).
"""
import logging

from odoo import api, models

from .southbrook_command_exception import SEVERITY_HARMONIZATION

_logger = logging.getLogger(__name__)


class SouthbrookCmmsBreakdownAlert(models.Model):
    _inherit = "southbrook.cmms.breakdown_alert"

    @api.model_create_multi
    def create(self, vals_list):
        alerts = super().create(vals_list)
        if not self.env["southbrook.command.exception"]._cc_hooks_enabled():
            return alerts
        for alert in alerts:
            try:
                alert._sb_cc_materialize()
            except Exception:  # noqa: BLE001
                _logger.exception(
                    "Central Command materialize failed for "
                    "southbrook.cmms.breakdown_alert %s — non-fatal", alert.id,
                )
        return alerts

    def _sb_cc_materialize(self):
        self.ensure_one()
        severity, severity_rank = SEVERITY_HARMONIZATION["breakdown_alert"].get(
            self.severity, ("medium", 2)
        )
        company_id = (
            self.equipment_id.company_id.id
            if self.equipment_id and self.equipment_id.company_id
            else self.env.company.id
        )
        Exception = self.env["southbrook.command.exception"]
        # No natural accountable user on a breakdown alert (reported_by is who
        # filed it, not who owns triage). Use the configurable OQ-8 fallback.
        owner_id = Exception._default_owner_id(self)
        impact_summary = (
            "Breakdown %s on %s (%s): %s"
            % (self.name, self.equipment_id.display_name, self.severity,
               (self.description or self.name or "")[:100])
        )[:280]
        why_text = (
            "southbrook.cmms.breakdown_alert %s: severity=%s state=%s equipment=%s"
            % (self.name, self.severity, self.state, self.equipment_id.display_name)
        )
        vals = {
            "severity": severity,
            "severity_rank": severity_rank,
            "owner_id": owner_id,
            "workcenter_id": self.workcenter_id.id if self.workcenter_id else False,
            "company_id": company_id,
            "impact_summary": impact_summary,
            "recommended_action": (
                "Dispatch maintenance (Action: Dispatch) and confirm which "
                "MOs are affected before releasing work at this equipment."
            ),
            "why_text": why_text,
        }
        exc = Exception._upsert_exception(
            "breakdown_alert", "southbrook.cmms.breakdown_alert", self.id, vals
        )
        base_payload = {
            "exception_id": exc.id,
            "exception_type": "breakdown_alert",
            "severity": severity,
            "severity_rank": severity_rank,
            "state": exc.state,
            "owner_id": owner_id,
            "workcenter_id": vals["workcenter_id"],
            "company_id": company_id,
            "write_date": exc.write_date.isoformat() if exc.write_date else None,
        }
        exc._publish("sb_cc_exceptions", "exception_upsert", base_payload)
        exc._publish(
            "sb_cc_alerts",
            "ops_event",
            {
                "source": "breakdown_alert",
                "event_id": self.id,
                "event_type": "breakdown_alert_created",
                "severity": severity,
                "res_model": "southbrook.cmms.breakdown_alert",
                "res_id": self.id,
                # NO impact_summary on the bus — the alerts channel is a
                # guessable string channel (sb_cc_alerts_<cid>) that Odoo does
                # NOT per-user authorize, so a cross-company subscriber would
                # get the breakdown detail in cleartext. The client re-fetches
                # the summary by res_id through the ACL-checked ORM.
                "company_id": company_id,
            },
        )
