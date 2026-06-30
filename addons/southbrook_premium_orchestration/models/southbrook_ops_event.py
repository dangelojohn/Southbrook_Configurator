# SPDX-License-Identifier: LGPL-3.0-only
"""Operational event log for the Kitchen Ops activity feed.

Proposed in docs ~/Downloads/southbrook_kitchen_ops_proposals.md
section 3.4. A lightweight append-only log of "something happened"
events that surface in the manager dashboard's right column and
(later) drive push notifications.

DESIGN CHOICES:

- Append-only via the `emit()` model method; callers shouldn't write
  direct ORM creates that bypass severity defaults.
- `res_model` + `res_id` are optional click-through pointers — when
  set, the dashboard renders a link to the underlying record.
- Severity has only three levels (info / warn / alert). More tiers
  invite mis-classification; three covers the dashboard's color band
  needs (green / amber / red).
- No retention cron in this commit. Will add when row count gets
  meaningful. For now table grows unbounded — that's fine for the
  proof-of-concept.

USAGE FROM ANY MODEL:

    self.env["southbrook.ops.event"].emit(
        "mo_done",
        f"MO {self.name} marked done",
        res_model="mrp.production",
        res_id=self.id,
        severity="info",
    )

Wrap caller code in try/except — the activity feed must never crash
the workflow it's observing. If an event fails to emit, it's lost,
that's acceptable. The MO going to `done` is far more important than
the dashboard line.
"""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SouthbrookOpsEvent(models.Model):
    _name = "southbrook.ops.event"
    _description = "Operational event for the Kitchen Ops activity feed"
    _order = "create_date desc"

    event_type = fields.Selection(
        [
            ("mo_confirm", "MO Confirmed"),
            ("mo_done", "MO Done"),
            ("eco_proposed", "ECO Proposed"),
            ("cron_run", "Cron Run"),
            ("cad_render_done", "CAD Render Done"),
            ("cad_render_error", "CAD Render Error"),
            ("tool_due", "Tool Maintenance Due"),
            ("install_risk", "Install Risk Flagged"),
            ("override_flagged", "Cut Spec Override Flagged"),
        ],
        required=True,
        string="Event Type",
    )
    summary = fields.Char(required=True)
    res_model = fields.Char(help="Click-through model. None = no click target.")
    res_id = fields.Integer(help="Click-through record id.")
    severity = fields.Selection(
        [("info", "Info"), ("warn", "Warning"), ("alert", "Alert")],
        default="info",
        required=True,
    )

    @api.model
    def emit(self, event_type, summary, res_model=None, res_id=None,
             severity="info"):
        """Create an event row. Returns the new record (or empty
        recordset on failure). Never raises — calling code MAY wrap
        in try/except but doesn't have to.
        """
        try:
            return self.sudo().create({
                "event_type": event_type,
                "summary": summary,
                "res_model": res_model,
                "res_id": res_id,
                "severity": severity,
            })
        except Exception:
            # Activity feed must never break the workflow it observes.
            _logger.exception("ops.event emit failed: %s", summary)
            return self.browse()
