# SPDX-License-Identifier: LGPL-3.0-only
import datetime
import hashlib

from odoo import api, models


class RagCorpusExport(models.AbstractModel):
    _name = "southbrook.os.rag.export"
    _description = "Build the RAG-grounding bundle for the Hermes sidecar."

    @api.model
    def build_bundle(self, tenant):
        sections = self.env["southbrook.os.section"].search([], order="slug")
        body_concat = "".join(s.body or "" for s in sections)
        build_hash = hashlib.sha256(body_concat.encode()).hexdigest()[:16]
        return {
            "tenant": tenant,
            "build_hash": build_hash,
            "built_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "documents": [
                {
                    "slug": s.slug,
                    "name": s.name,
                    "version": s.version,
                    "source": s.source,
                    "audience": (s.audience_tags or "").split(",") if s.audience_tags else [],
                    "text": s.body or "",
                }
                for s in sections
            ],
        }
