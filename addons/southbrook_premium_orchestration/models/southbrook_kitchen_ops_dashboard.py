# SPDX-License-Identifier: LGPL-3.0-only
"""Kitchen Ops manager dashboard — proposals §3.1 proof of concept.

A single TransientModel that backs the splash dashboard the plant
manager lands on when opening the Kitchen Ops menu. Tiles are
compute fields, refreshed on each form load (manager hits the menu
in the morning -> sees a fresh snapshot).

POC SCOPE — 3 tiles + activity feed:
  - Tile A: Cabinets in Progress (mrp.production state in progress
    or to_close)
  - Tile B: FreeCAD Bridge — health + pending render count
  - Tile C: Recent Activity (last 10 southbrook.ops.event rows)

Each tile's primary numeric is clickable: opens the corresponding
list view, pre-filtered. This is the drill-down navigation pattern
from proposals §3.5.

DELIBERATELY DEFERRED (future commits per the proposals):
  - Cron observability strip (§3.2) — needs the southbrook.cron.health
    model + per-cron trace decorator first.
  - Integration Hub unification (§3.3) — needs the southbrook.integration
    model + migration from per-activator forms to cards.
  - SSE / 30s auto-refresh (§3.4 live feed) — needs an OWL widget
    rather than the form's static render.
  - Permission tiers (§3.6), shift awareness (§3.7), responsive
    polish (§3.8) — week 4 in the build sequence.

REFRESH STRATEGY: today's POC has NO client-side auto-refresh.
Manager reloads the page or re-clicks the menu to get a fresh
snapshot. Adding `setInterval`-style refresh requires an OWL widget
(out of scope for the proof-of-concept). The compute fields all
read fresh from the DB on each render, so a manual refresh is
genuinely current.
"""
from odoo import api, fields, models


class KitchenOpsDashboard(models.TransientModel):
    _name = "southbrook.kitchen.ops.dashboard"
    _description = "Kitchen Ops manager dashboard (proposals §3.1 POC)"

    # ----- Tile A: Manufacturing WIP -----
    wip_count = fields.Integer(
        compute="_compute_wip_count",
        string="Cabinets in Progress",
        help="mrp.production where state is 'progress' or 'to_close'.",
    )

    # ----- Tile B: FreeCAD Bridge health -----
    freecad_status_label = fields.Char(
        compute="_compute_freecad",
        string="FreeCAD Bridge Status",
    )
    freecad_pending_count = fields.Integer(
        compute="_compute_freecad",
        string="Pending CAD Renders",
    )

    # ----- Tile C: Recent activity -----
    recent_event_ids = fields.Many2many(
        "southbrook.ops.event",
        compute="_compute_recent_events",
        string="Recent Activity (last 10)",
    )
    recent_event_summary = fields.Char(
        compute="_compute_recent_events",
        string="Activity Summary",
        help="Compact one-line summary so the empty state is meaningful.",
    )

    # ----- Computes -----
    @api.depends_context("uid")
    def _compute_wip_count(self):
        MO = self.env["mrp.production"].sudo()
        n = MO.search_count([("state", "in", ["progress", "to_close"])])
        for rec in self:
            rec.wip_count = n

    @api.depends_context("uid")
    def _compute_freecad(self):
        Act = self.env["southbrook.freecad.activator"].sudo()
        console = Act.search([], limit=1)
        if not console:
            label, pending = "Not configured", 0
        elif not console.enabled:
            label, pending = "Disabled (G2a)", console.mo_pending_cad_count
        else:
            # "Enabled" doesn't prove the daemon is reachable. The
            # activator's last_health_check_status carries the signal
            # but only updates when someone runs action_health_check.
            # For POC, "Enabled" = the gate is open; the activator
            # console is one click away for detailed status.
            label = "Enabled"
            pending = console.mo_pending_cad_count
        for rec in self:
            rec.freecad_status_label = label
            rec.freecad_pending_count = pending

    @api.depends_context("uid")
    def _compute_recent_events(self):
        Event = self.env["southbrook.ops.event"].sudo()
        events = Event.search([], limit=10, order="create_date desc")
        if events:
            summary = f"{len(events)} event(s), most recent: {events[0].summary[:60]}"
        else:
            summary = "No events recorded yet. Confirm an MO to populate this feed."
        for rec in self:
            rec.recent_event_ids = [(6, 0, events.ids)]
            rec.recent_event_summary = summary

    # ----- Drill-down actions (proposals §3.5) -----
    def action_open_wip(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Cabinets in Progress",
            "res_model": "mrp.production",
            "view_mode": "list,form",
            "domain": [("state", "in", ["progress", "to_close"])],
        }

    def action_open_freecad_activator(self):
        Act = self.env["southbrook.freecad.activator"].sudo()
        console = Act.search([], limit=1)
        if not console:
            console = Act.create({})
        return {
            "type": "ir.actions.act_window",
            "name": "FreeCAD Bridge Activator",
            "res_model": "southbrook.freecad.activator",
            "view_mode": "form",
            "res_id": console.id,
            "target": "current",
        }

    def action_open_pending_renders(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Pending CAD Renders",
            "res_model": "mrp.production",
            "view_mode": "list,form",
            "domain": [("x_cad_status", "=", "pending")],
        }

    def action_refresh(self):
        """Form button: invalidate computes + redisplay. No-op
        functionally (computes are non-stored, always fresh on read)
        but the explicit button gives the manager a visible 'reload'
        affordance without browser-level refresh."""
        self.invalidate_recordset()
        return {
            "type": "ir.actions.client",
            "tag": "soft_reload",
        }
