# FEATURE 2 — Portal integration for saved configurations (bookmark model).
#
# This controller adds the "My Configurations" surface to the standard
# Odoo customer portal so logged-in buyers can return to saved
# product.config.bookmark records they made via the storefront. The
# bookmark model (product.config.bookmark) replaces the prior
# bookmark_name+is_saved field pair on product.config.session —
# the controller now reads/writes the dedicated model.
#
# The session itself still holds the configuration state (attribute
# values, custom values, pricing); the bookmark is a buyer-owned
# pointer to a session with metadata (name, last_viewed, active).
# See product_configurator/models/product_config_bookmark.py for
# the model and its rationale.
#
# Surface in this controller:
#   GET  /my                                — homepage card with count
#   GET  /my/configurations                 — list view
#   GET  /my/configurations/<id>/resume     — prime session cookie + redirect to wizard
#   POST /my/configurations/<id>/rename     — buyer-supplied label change
#   POST /my/configurations/<id>/delete     — archive (soft-delete)
#
# All four routes are auth='user' (logged-in only) — public anonymous
# buyers don't have bookmarks. The storefront cookie-based resume
# mechanism in main.py covers their flow separately.

import logging

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager

_logger = logging.getLogger(__name__)

# Tuneable: how many bookmarks to show per page. Kept low because
# this is a buyer-facing list; pagination is a real signal that the
# buyer's configurator usage has grown past casual browsing.
_PAGE_SIZE = 20


class CustomerPortalConfigurator(CustomerPortal):
    """Extend the customer portal with a saved-configurations list.

    Ownership is enforced by the ir.rule on product.config.bookmark
    (portal_rule, defined in product_configurator/security/
    configurator_security.xml). The controller never sudo()s on
    write/unlink — those go through the user's env and the rule
    blocks cross-user access cleanly. Sudo IS used on a few read
    traversals (e.g., bookmark.product_tmpl_id.name in the template)
    where core's "Public product template" ir.rule would otherwise
    403 on non-website_published configurable templates.
    """

    # ------------------------------------------------------------------
    # Homepage counter card
    # ------------------------------------------------------------------

    def _prepare_home_portal_values(self, counters):
        """Add a 'configuration_count' card to /my (portal home)."""
        values = super()._prepare_home_portal_values(counters)
        if "configuration_count" in counters:
            values["configuration_count"] = request.env[
                "product.config.bookmark"
            ].search_count([("user_id", "=", request.env.user.id)])
        return values

    # ------------------------------------------------------------------
    # List view
    # ------------------------------------------------------------------

    @http.route(
        ["/my/configurations", "/my/configurations/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_configurations(self, page=1, sortby=None, **kwargs):
        """Render the buyer's saved-configurations list.

        Default sort: last_viewed desc, falling back to create_date
        (per the model's ``_order``). Buyers return to recent
        bookmarks; this surfaces them first.
        """
        Bookmark = request.env["product.config.bookmark"]
        domain = [("user_id", "=", request.env.user.id)]
        total = Bookmark.search_count(domain)
        pager_vals = portal_pager(
            url="/my/configurations",
            total=total,
            page=page,
            step=_PAGE_SIZE,
        )
        bookmarks = Bookmark.search(
            domain,
            limit=_PAGE_SIZE,
            offset=pager_vals["offset"],
        )

        # Sudo the recordset so the QWeb template can traverse
        # bookmark.product_tmpl_id.name without 403'ing on the
        # core "Public product template" ir.rule. Ownership is
        # already proven by the search domain above; this sudo
        # is scoped to known-owned records for read-only traversal.
        values = self._prepare_portal_layout_values()
        values.update(
            {
                "configurations": bookmarks.sudo(),
                "page_name": "configurations",
                "pager": pager_vals,
                "default_url": "/my/configurations",
            }
        )
        return request.render(
            "website_product_configurator.portal_my_configurations",
            values,
        )

    # ------------------------------------------------------------------
    # Resume — prime session cookie, redirect to wizard
    # ------------------------------------------------------------------

    @http.route(
        "/my/configurations/<int:bookmark_id>/resume",
        type="http",
        auth="user",
        website=True,
    )
    def portal_resume_configuration(self, bookmark_id, **kwargs):
        """Resume editing the configuration this bookmark points at.

        The URL ID is the BOOKMARK's id, not the session's. We
        lookup the bookmark, follow its session_id, prime the
        storefront session cookie, then redirect to the wizard.

        Why the bookmark id and not the session id: bookmarks are
        the buyer-facing entity. The session is an implementation
        detail; the buyer's mental model is "this is my saved
        Track-Car-Spec configuration", not "this is session #4729".
        """
        bookmark = request.env["product.config.bookmark"].search(
            [("id", "=", bookmark_id), ("user_id", "=", request.env.user.id)],
            limit=1,
        )
        if not bookmark:
            # 404-equivalent: don't leak existence of other users'
            # bookmarks, and don't expose archived ones as resumable.
            return request.redirect("/my/configurations")

        # Bump last_viewed for "recent bookmarks" UX. Sudo because
        # portal write on this exact record is already permitted by
        # the rule, but the touch path is intentionally noop-safe.
        bookmark.action_touch_viewed()

        # Sudo for the read traversal into product.template (core's
        # ir.rule blocks portal-user reads on non-website_published
        # templates).
        bookmark_sudo = bookmark.sudo()
        session = bookmark_sudo.session_id
        product_tmpl_id = bookmark_sudo.product_tmpl_id

        # Prime the storefront session cookie so the wizard reopens
        # this exact session. Stringify the key — JSON-serialized
        # request.session coerces int keys to strings (see the
        # comment on get_config_session in main.py).
        product_config_sessions = request.session.get(
            "product_config_session", {}
        )
        product_config_sessions[str(product_tmpl_id.id)] = session.id
        request.session["product_config_session"] = product_config_sessions

        # Redirect to the wizard entry. /shop/product/<slug> renders
        # the configurator form for config_ok templates; the primed
        # cookie ensures we get THIS session, not a fresh one.
        slug = request.env["ir.http"]._slug(product_tmpl_id)
        return request.redirect("/shop/product/%s" % slug)

    # ------------------------------------------------------------------
    # Rename (inline edit from the portal list)
    # ------------------------------------------------------------------

    @http.route(
        "/my/configurations/<int:bookmark_id>/rename",
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def portal_rename_configuration(self, bookmark_id, name=None, **kwargs):
        """POST handler for the rename form on the portal list.

        Form fields:
          name — new buyer-supplied label (trimmed, bounded to 128 chars
                 by the model's write override).

        Empty name is rejected to avoid the buyer accidentally clearing
        the label via empty submission.
        """
        bookmark = request.env["product.config.bookmark"].search(
            [("id", "=", bookmark_id), ("user_id", "=", request.env.user.id)],
            limit=1,
        )
        if not bookmark:
            return request.redirect("/my/configurations")

        if not name or not name.strip():
            # Silent ignore; user just gets bounced back to the list.
            # Could surface a flash message in a future iteration.
            return request.redirect("/my/configurations")

        try:
            bookmark.write({"name": name})
        except (UserError, AccessError):
            _logger.exception(
                "portal_rename_configuration write failed for bookmark %s",
                bookmark_id,
            )
            # Fall through to the redirect — best-effort UX.
        return request.redirect("/my/configurations")

    # ------------------------------------------------------------------
    # Delete (archive)
    # ------------------------------------------------------------------

    @http.route(
        "/my/configurations/<int:bookmark_id>/delete",
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def portal_delete_configuration(self, bookmark_id, **kwargs):
        """POST handler for the buyer-initiated delete.

        Soft-delete via active=False (NOT hard unlink). Rationale:
        the underlying product.config.session may be referenced by
        a sale-order line (the buyer might have already added a
        cart entry pointing at this session before changing their
        mind about the bookmark). Hard-deleting the bookmark would
        be safe (cascade is to bookmark only), but the buyer might
        want the bookmark back from an "Archived" tab in a future
        iteration. Soft-delete preserves that option.
        """
        bookmark = request.env["product.config.bookmark"].search(
            [("id", "=", bookmark_id), ("user_id", "=", request.env.user.id)],
            limit=1,
        )
        if not bookmark:
            return request.redirect("/my/configurations")

        try:
            bookmark.action_archive()
        except (UserError, AccessError):
            _logger.exception(
                "portal_delete_configuration write failed for bookmark %s",
                bookmark_id,
            )
        return request.redirect("/my/configurations")
