# SPDX-License-Identifier: LGPL-3.0-only
import datetime
import json

from odoo import http
from odoo.http import request


class OsPublicController(http.Controller):

    @http.route("/southbrook/os.json", type="http", auth="public",
                website=False, methods=["GET"], csrf=False)
    def os_json(self, **kw):
        # PUBLIC endpoint — expose ONLY sections whose canonical `audience:`
        # frontmatter includes "public" (today that is just 00_charter). Every
        # other section is audience-scoped INTERNAL content: partner tiers
        # (01_company), production control (05_production), PLM (06_plm), and —
        # most sensitively — systems topology (20_systems_topology: container
        # names, deploy paths, co-tenant list = infra recon). A bare search([])
        # here leaked the entire internal knowledge base to anonymous callers.
        # Do NOT widen this filter without re-auditing canonical/*.md tags.
        sections = request.env["southbrook.os.section"].sudo().search(
            [("audience_tags", "ilike", "public")], order="slug")
        # Read-only: serve the latest EXISTING publication for provenance
        # metadata only. Building publications is the cron/OSRO job
        # (os_generators.generate_all) — an anonymous GET must never create
        # rows (that was write-amplification + a TOCTOU IntegrityError→500 on
        # the UNIQUE(calendar_key, build_hash) constraint).
        publication = request.env["southbrook.os.publication"].sudo().search(
            [], order="calendar_key desc, built_at desc, id desc", limit=1)
        payload = {
            "tenant": "southbrook",
            "publication": {
                "calendar_key": publication.calendar_key,
                "build_hash": publication.build_hash,
                "built_at": publication.built_at.isoformat()
                    if publication.built_at else None,
            } if publication else None,
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
