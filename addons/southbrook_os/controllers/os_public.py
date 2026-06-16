# SPDX-License-Identifier: LGPL-3.0-only
import datetime
import json

from odoo import http
from odoo.http import request


class OsPublicController(http.Controller):

    @http.route("/southbrook/os.json", type="http", auth="public",
                website=False, methods=["GET"], csrf=False)
    def os_json(self, **kw):
        sections = request.env["southbrook.os.section"].sudo().search(
            [], order="slug")
        Pub = request.env["southbrook.os.publication"].sudo()
        calendar_key = datetime.date.today().strftime("%Y-%m")
        publication = Pub.publish(calendar_key)
        payload = {
            "tenant": "southbrook",
            "publication": {
                "calendar_key": publication.calendar_key,
                "build_hash": publication.build_hash,
                "built_at": publication.built_at.isoformat(),
            },
            "sections": [
                {
                    "slug": s.slug,
                    "name": s.name,
                    "version": s.version,
                    "source": s.source,
                    "audience_tags": s.audience_tags or "",
                    "body": s.body,
                    "last_updated_at": s.last_updated_at.isoformat()
                        if s.last_updated_at else None,
                }
                for s in sections
            ],
        }
        return request.make_response(
            json.dumps(payload),
            headers=[
                ("Content-Type", "application/json"),
                ("Cache-Control", "public, max-age=300"),
            ],
        )
