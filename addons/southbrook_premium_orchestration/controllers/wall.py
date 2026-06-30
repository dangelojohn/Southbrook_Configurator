# SPDX-License-Identifier: LGPL-3.0-only
"""Wall-display JSON feeds for the Southbrook kiosk surface.

Implements the JSON contract from ~/Downloads/southbrook_kiosk_dashboard_spec.md
§4. One controller per station; each returns the versioned envelope:

    {
      "schema_version": 1,
      "station":        "shipping",
      "generated_at":   "2026-06-25T14:32:08Z",
      "valid_for_seconds": 60,
      "payload": { kpis: {...}, rows: [...], alerts: [...] }
    }

The 1-day proof-of-concept (spec §11) ships only /wall/shipping.json
— other stations follow the same template once the architecture is
proven on the dock TV.

AUTH MODEL (spec §2.5):
  Wall feeds are READ-ONLY and currently `auth='public'`. The IP
  allowlist that gates them is intended to live at the Caddy layer
  (spec §7.8), NOT in this controller — keeping access policy out
  of the addon means a network-side scope change doesn't need a
  module upgrade.

  Until the Caddy IP allowlist is in place, these endpoints are
  effectively public — meaning anyone who can reach the hostname
  can read SO numbers + customer names. Per spec §7.9, this is an
  open privacy question that needs a stakeholder decision before
  production.

REFRESH CADENCE:
  `valid_for_seconds=60` for shipping (operator awareness 1min is
  fine). The kiosk JS reads this from the envelope and colors its
  "Updated Xs ago" stamp accordingly (green / amber / red). Tuning
  per station per spec §7.18.
"""
import logging
from datetime import datetime, timedelta

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)

# Stations registered for /wall/<station>.json. Each entry maps the
# URL slug to a build function on this class. Adding a new station =
# add a build_* method + register here.
SCHEMA_VERSION = 1


class WallFeedController(http.Controller):

    @http.route(
        "/southbrook/wall/<string:station>.json",
        type="http", auth="public", methods=["GET"], csrf=False,
    )
    def wall_feed(self, station, **kwargs):
        builders = {
            "shipping": self._build_shipping,
        }
        if station not in builders:
            return request.make_response(
                '{"error":"unknown_station"}',
                status=404,
                headers=[("Content-Type", "application/json")],
            )
        try:
            payload = builders[station]()
            valid_for = 60
            envelope = {
                "schema_version": SCHEMA_VERSION,
                "station": station,
                "generated_at": fields.Datetime.now().isoformat() + "Z",
                "valid_for_seconds": valid_for,
                "payload": payload,
            }
        except Exception as exc:
            _logger.exception("wall_feed error station=%s", station)
            envelope = {
                "schema_version": SCHEMA_VERSION,
                "station": station,
                "generated_at": fields.Datetime.now().isoformat() + "Z",
                "valid_for_seconds": 30,
                "payload": {"error": str(exc)[:200]},
            }
        import json as _json
        return request.make_response(
            _json.dumps(envelope),
            headers=[
                ("Content-Type", "application/json"),
                ("Cache-Control", "no-store"),
            ],
        )

    # ----- per-station builders ---------------------------------------

    def _build_shipping(self):
        """Outbound dock view.

        Returns the rows + KPIs the wall TV at the shipping bay needs.
        Data comes from stock.picking (outgoing type) — we pull today
        + the next 3 days so the dock supervisor sees what's loading
        now AND what's queued for tomorrow morning.

        Status column is sourced from picking.state (Odoo's standard):
            draft         → "Pending"
            waiting       → "Pending"
            confirmed     → "Pending"
            assigned      → "Ready"
            done          → "Departed"
            cancel        → "Cancelled"
        We map to friendly labels here so the JS doesn't have to learn
        Odoo's internal state vocabulary.

        ROW CAP: hard-limited to 50 to keep the wire small. A wall TV
        showing >50 rows is unreadable anyway; if more shipments stack
        up, a separate "/wall/shipping-overflow" page is the answer.
        """
        Picking = request.env["stock.picking"].sudo()
        today = fields.Date.today()
        # Range: yesterday → today+3 days. Yesterday catches "departed
        # last night, still on the activity feed". today+3 covers
        # tomorrow + day-after.
        date_from = today - timedelta(days=1)
        date_to = today + timedelta(days=3)
        pickings = Picking.search([
            ("picking_type_id.code", "=", "outgoing"),
            ("scheduled_date", ">=", date_from),
            ("scheduled_date", "<", date_to + timedelta(days=1)),
            ("state", "!=", "cancel"),
        ], limit=50, order="scheduled_date asc, id asc")

        status_label = {
            "draft": "Pending",
            "waiting": "Pending",
            "confirmed": "Pending",
            "assigned": "Ready",
            "done": "Departed",
        }

        rows = []
        kpi_trucks_at_dock = 0
        kpi_pending = 0
        kpi_late = 0
        now_dt = datetime.now()
        for p in pickings:
            sched = p.scheduled_date
            row_status = status_label.get(p.state, p.state)
            if row_status == "Ready":
                kpi_trucks_at_dock += 1
            if row_status == "Pending":
                kpi_pending += 1
                # Late = scheduled in the past and still not Ready / Departed
                if sched and sched < now_dt:
                    kpi_late += 1
            rows.append({
                "so": p.origin or "",
                "picking": p.name,
                "customer": p.partner_id.name or "",
                "carrier": p.carrier_id.name if hasattr(p, "carrier_id") and p.carrier_id else "",
                "tracking": (getattr(p, "carrier_tracking_ref", "") or ""),
                "scheduled_at": sched.isoformat() + "Z" if sched else None,
                "status": row_status,
                "state_raw": p.state,
            })
        return {
            "kpis": {
                "rows_total": len(rows),
                "trucks_at_dock": kpi_trucks_at_dock,
                "pending": kpi_pending,
                "late": kpi_late,
            },
            "rows": rows,
            "alerts": [],
        }
