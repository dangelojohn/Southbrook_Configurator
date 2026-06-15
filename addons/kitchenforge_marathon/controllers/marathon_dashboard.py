# SPDX-License-Identifier: LGPL-3.0-only
"""Marathon-facing read-only dashboard endpoints.

Marathon's BI tool pulls these on a schedule. Auth uses the shared
X-Api-Key, but the route checks that the calling user belongs to the
'KitchenForge / Dealer' group OR has explicit Marathon read access.
"""
import json

from odoo import http
from odoo.http import request

from odoo.addons.southbrook_api.controllers.main import (
    requires_api_key, _json, _error,
)


class MarathonDashboard(http.Controller):

    @http.route("/agent/v1/marathon/telemetry", type="http", auth="public",
                methods=["GET"], csrf=False)
    @requires_api_key
    def telemetry(self, **kw):
        limit = int(kw.get("limit", 200))
        Event = request.env["kitchenforge.marathon.spec.event"].sudo()
        events = Event.search([], limit=limit, order="create_date desc")
        return _json({
            "schema": "kitchenforge.marathon.telemetry.v1",
            "tenant": request.env.cr.dbname,
            "count": len(events),
            "events": [{
                "id": e.id,
                "ts": str(e.create_date),
                "product_default_code": e.product_id.default_code,
                "product_name": e.product_id.display_name,
                "qty": e.qty,
                "cabinet_family": e.cabinet_family,
                "pull_finish": e.pull_finish,
                "pull_size_mm": e.pull_size_mm,
                "sale_order": e.sale_order_id.name if e.sale_order_id else None,
            } for e in events],
        })

    @http.route("/agent/v1/marathon/rebates", type="http", auth="public",
                methods=["GET"], csrf=False)
    @requires_api_key
    def rebates(self, **kw):
        Rebate = request.env["kitchenforge.marathon.rebate"].sudo()
        period = kw.get("period")
        summary = Rebate.monthly_summary(period=period)
        return _json({
            "schema": "kitchenforge.marathon.rebates.v1",
            "tenant": request.env.cr.dbname,
            "summary": summary,
        })
