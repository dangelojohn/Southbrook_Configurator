# SPDX-License-Identifier: LGPL-3.0-only
"""Spec-event telemetry — every Marathon hardware resolution emits one row.

The Marathon dashboard reads from this model (or its webhook mirror) to see
which SKUs are being specified, by whom, on what kitchen, in near-real-time.
This is the "demand telemetry" pillar of the channel-partner pitch.
"""
import json
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MarathonSpecEvent(models.Model):
    _name = "kitchenforge.marathon.spec.event"
    _description = "KitchenForge Marathon Spec Event"
    _order = "create_date desc"
    _rec_name = "label"

    label = fields.Char(required=True, default="spec-event")
    sale_order_id = fields.Many2one("sale.order", index=True, ondelete="set null")
    sale_order_line_id = fields.Many2one(
        "sale.order.line", index=True, ondelete="set null")
    project_id = fields.Many2one("project.project", index=True, ondelete="set null")
    product_id = fields.Many2one(
        "product.product", required=True, index=True, ondelete="restrict",
        help="The Marathon SKU specified.")
    qty = fields.Float(default=1.0)
    cabinet_family = fields.Char(index=True)
    pull_finish = fields.Char(index=True)
    pull_size_mm = fields.Integer()
    payload_json = fields.Text(help="Full resolve() args + result snapshot.")
    delivered_to_webhook = fields.Boolean(
        default=False, index=True,
        help="Set true after the telemetry webhook accepts the event.")
    delivered_at = fields.Datetime()

    @api.model
    def emit(self, *, product, qty=1, cabinet_family=None, pull_finish=None,
              pull_size_mm=None, sale_order=None, sale_order_line=None,
              project=None, extra=None):
        """Single emission entry point — called by hardware_catalog inherit.

        Cheap by design: one INSERT, no joins, no constraints. The nightly
        cron rolls up + flushes to Marathon.
        """
        cfg = self.env["kitchenforge.marathon.channel.config"].sudo().get_active()
        if not cfg.enabled:
            return self.browse()
        vals = {
            "label": f"spec/{product.default_code or product.id}",
            "product_id": product.id,
            "qty": qty,
            "cabinet_family": cabinet_family,
            "pull_finish": pull_finish,
            "pull_size_mm": pull_size_mm,
            "sale_order_id": sale_order.id if sale_order else False,
            "sale_order_line_id": sale_order_line.id if sale_order_line else False,
            "project_id": project.id if project else False,
            "payload_json": json.dumps(extra or {}, default=str),
        }
        return self.sudo().create(vals)

    @api.model
    def cron_flush_telemetry(self, batch=200):
        """Nightly cron — drains undelivered events to the Marathon webhook.

        Resilient by design: failures stay queued; successes flip the
        delivered_to_webhook flag. No HTTP retries in the hot path; the
        next cron pass will pick them up.
        """
        cfg = self.env["kitchenforge.marathon.channel.config"].sudo().get_active()
        url = cfg.telemetry_webhook_url
        if not url:
            _logger.info("marathon telemetry: no webhook configured, skip")
            return 0
        try:
            import requests  # available in Odoo's wheel; degrade gracefully
        except ImportError:
            _logger.warning("marathon telemetry: requests unavailable")
            return 0

        events = self.search(
            [("delivered_to_webhook", "=", False)], limit=batch, order="id")
        if not events:
            return 0
        body = {
            "schema": "kitchenforge.marathon.telemetry.v1",
            "tenant": self.env.cr.dbname,
            "events": [{
                "id": e.id,
                "ts": fields.Datetime.to_string(e.create_date),
                "product_default_code": e.product_id.default_code,
                "product_name": e.product_id.display_name,
                "qty": e.qty,
                "cabinet_family": e.cabinet_family,
                "pull_finish": e.pull_finish,
                "pull_size_mm": e.pull_size_mm,
                "sale_order": e.sale_order_id.name if e.sale_order_id else None,
                "project_id": e.project_id.id if e.project_id else None,
            } for e in events],
        }
        try:
            resp = requests.post(url, json=body, timeout=15)
            if resp.status_code >= 400:
                _logger.warning("marathon webhook %s -> %s: %s",
                                url, resp.status_code, resp.text[:200])
                return 0
        except Exception as exc:
            _logger.warning("marathon webhook POST failed: %s", exc)
            return 0
        events.write({
            "delivered_to_webhook": True,
            "delivered_at": fields.Datetime.now(),
        })
        return len(events)
