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
        # Don't read tmpl.image_1920 here — touching an Image field
        # triggers variant-size compute (image_128/256/512/1024) which
        # writes back to the row and conflicts with concurrent updates
        # on the same template. Let /web/image/ handle the
        # missing-image case itself (it returns its own placeholder).

        # Hand the bytes off to Odoo's well-tested binary-streaming
        # path via /web/image/. That route handles variant compute,
        # ETag headers, range requests, and serialization-conflict
        # retries — all of which the manual base64-decode in the
        # original A4 patch did NOT. The UUID is preserved at the
        # cache-key layer (Cloudflare + browser keyed on the
        # /southbrook/catalog/icon/<uuid>/* URL, the redirect target
        # is hot in Odoo's binary cache once warmed).
        #
        # K2-a (Round-2 misc fix): pass `unique=<uuid>` so Odoo's
        # binary route emits the long-cache `Cache-Control:
        # max-age=31536000, immutable` header. The UUID is content-
        # addressed (changes whenever the image changes), so a far-
        # future cache is safe and reverses the perf regression of
        # icons reaching the origin on every page view.
        return request.redirect(
            "/web/image/product.template/%d/image_1920?unique=%s" % (
                tmpl.id, uuid),
            local=True,
        )
