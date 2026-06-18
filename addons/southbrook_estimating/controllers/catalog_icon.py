# SPDX-License-Identifier: LGPL-3.0-only
"""A4 — Stable, cache-bustable catalog-icon URLs.

GET /southbrook/catalog/icon/<uuid>            -> 200 image bytes
GET /southbrook/catalog/icon/<uuid>/<filename> -> 200 image bytes (filename ignored)

The UUID is looked up on product.template.x_image_uuid. When matched,
the template's image_1920 attachment is served with a far-future Cache-
Control header (the UUID changes whenever the content changes; pattern
borrowed from the source catalogue's content-addressed image strategy).
When no template matches, returns HTTP 404. Public route — catalog icons
are publicly visible product imagery.
"""
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class SouthbrookCatalogIcon(http.Controller):

    @http.route(
        ["/southbrook/catalog/icon/<string:uuid>",
         "/southbrook/catalog/icon/<string:uuid>/<string:filename>"],
        type="http",
        auth="public",
        methods=["GET"],
        website=True,
    )
    def catalog_icon(self, uuid, filename=None, **kw):
        if not uuid:
            return request.not_found()
        Template = request.env["product.template"].sudo()
        tmpl = Template.search(
            [("x_image_uuid", "=", uuid)], limit=1)
        if not tmpl:
            return request.not_found()
        if not tmpl.image_1920:
            return request.not_found()

        # Stream image_1920 with a long Cache-Control max-age. Since the
        # UUID changes when content changes, the URL itself is the cache
        # key — safe to cache for a year.
        from odoo.tools import image_process
        image_b64 = tmpl.image_1920
        # We don't transform — full-quality image as stored. Odoo's
        # generic image-handling utility returns base64-decoded bytes.
        import base64
        try:
            content = base64.b64decode(image_b64)
        except Exception:
            _logger.warning(
                "Failed to b64-decode image_1920 for template %s (uuid=%s)",
                tmpl.id, uuid)
            return request.not_found()

        headers = [
            ("Content-Type", "image/png"),
            ("Cache-Control", "public, max-age=31536000, immutable"),
            ("X-Southbrook-Template-Id", str(tmpl.id)),
        ]
        return request.make_response(content, headers=headers)
