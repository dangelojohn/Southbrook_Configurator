# Copyright 2026 OdooIQ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Saved-configuration bookmarks.

A `product.config.bookmark` is a buyer-facing reference to a
configured `product.config.session`. The session itself owns the
attribute values, custom values, pricing, and lifecycle state. The
bookmark owns the buyer-facing metadata: name, save date, last-
viewed time, and ownership.

Why a separate model (vs. the prior `bookmark_name` + `is_saved`
fields on `product.config.session`)?

The session model is workflow-state: a session moves from `draft`
to `done` (variant created), gets garbage-collected after some
days of inactivity, may be referenced by a sale-order line. Layering
a buyer-facing bookmark on top of those mechanics confuses two
concerns: "is this session active in some lifecycle" vs. "did a
buyer ask us to remember this configuration for them".

The separate model lets:

- Buyers have multiple bookmarks pointing at the same session
  (rare; e.g., renamed variants of the same build)
- Bookmarks survive session-lifecycle changes (the session may
  graduate from draft to done, the bookmark persists)
- Garbage-collection rules apply to sessions independently of
  bookmarks (an old session no longer referenced by any bookmark
  becomes a GC candidate; a session referenced by a bookmark is
  retained regardless of age)
- Future enhancements — sharing, tags, reminders — attach to the
  bookmark, not the session
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

# Maximum length for the buyer-supplied name. Prevents DB bloat,
# title-bar XSS via runaway-length labels, and pathological UX
# in the portal list view.
_MAX_NAME_LENGTH = 128


class ProductConfigBookmark(models.Model):
    """Buyer-facing saved configuration bookmark."""

    _name = "product.config.bookmark"
    _description = "Saved Configuration Bookmark"
    _order = "last_viewed desc, create_date desc"
    _rec_name = "name"

    name = fields.Char(
        string="Bookmark Name",
        required=True,
        help="Buyer-supplied label for this saved configuration.",
    )
    session_id = fields.Many2one(
        comodel_name="product.config.session",
        string="Configuration Session",
        required=True,
        ondelete="cascade",
        index=True,
        help="The underlying product.config.session that holds the "
        "attribute-value selections, custom values, and pricing.",
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Owner",
        required=True,
        default=lambda self: self.env.user,
        index=True,
        ondelete="cascade",
        help="The user who created this bookmark. Portal users see "
        "only bookmarks where user_id == self via the ir.rule on "
        "this model.",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Customer",
        related="user_id.partner_id",
        store=True,
        readonly=True,
        help="Owner's contact partner — displayed in the portal "
        "list and used for any future buyer-facing communication "
        "(reminder emails, share invitations).",
    )
    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string="Product Template",
        related="session_id.product_tmpl_id",
        store=True,
        readonly=True,
        index=True,
        help="The configurable product template this bookmark "
        "configures. Stored to enable portal filtering and "
        "menu-list grouping.",
    )
    last_viewed = fields.Datetime(
        string="Last Viewed",
        default=fields.Datetime.now,
        help="Timestamp of the most recent buyer interaction with "
        "this bookmark — opening the resume URL bumps this. Used "
        "for portal sort order (most-recently-viewed first) and "
        "for future stale-bookmark cleanup heuristics.",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Soft-delete flag. Inactive bookmarks are hidden from "
        "the portal but the underlying session is preserved for "
        "audit / sale-order-line backreferences.",
    )

    _sql_constraints = [
        (
            "name_not_empty",
            "CHECK (TRIM(name) <> '')",
            "A bookmark must have a non-empty name.",
        ),
    ]

    # ------------------------------------------------------------------
    # CRUD overrides — bound-checking + ownership
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._normalize_name_in_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._normalize_name_in_vals(vals)
        return super().write(vals)

    @api.model
    def _normalize_name_in_vals(self, vals):
        """Trim whitespace and bound length on writes / creates.

        Reject post-trim empty names with a UserError — friendlier
        than the bare IntegrityError the sql_constraint would
        produce. The constraint is still the authoritative gate
        (defense in depth against callers that bypass this
        normalizer, e.g., direct SQL or fields.Command writes).
        """
        if "name" in vals and isinstance(vals["name"], str):
            trimmed = vals["name"].strip()[:_MAX_NAME_LENGTH]
            if not trimmed:
                raise UserError(_("A bookmark must have a non-empty name."))
            vals["name"] = trimmed

    # ------------------------------------------------------------------
    # Buyer-facing actions
    # ------------------------------------------------------------------

    def action_touch_viewed(self):
        """Bump last_viewed to now. Called by the portal resume route
        each time the buyer reopens a bookmark."""
        self.ensure_one()
        # Sudo because portal users have read-only ACL on this model;
        # we want their access to be transparent (no AccessError on a
        # GET to /my/configurations/<id>/resume) but the write here is
        # scoped to the SINGLE record they've already proven ownership
        # of via the route's search.
        self.sudo().write({"last_viewed": fields.Datetime.now()})

    def action_archive(self):
        """Soft-delete: flip active=False. The portal will hide this
        bookmark; the session is preserved."""
        self.write({"active": False})

    def action_unarchive(self):
        """Inverse of action_archive."""
        self.write({"active": True})

    @api.model
    def create_from_session(self, session, name=None):
        """Factory: create a bookmark for an existing session.

        :param session: a product.config.session recordset (one record)
        :param str name: buyer-supplied label, or None to auto-name
            from the product template name
        :return: the created bookmark record
        :raises UserError: if the session is empty or belongs to a
            different user than the caller
        """
        if not session or len(session) != 1:
            raise UserError(_("A bookmark needs exactly one session."))
        if session.user_id != self.env.user and not self.env.user.has_group(
            "base.group_user"
        ):
            # External users can only bookmark their own sessions.
            # Internal users (employees) can bookmark on behalf of a
            # customer as a back-office action.
            raise AccessError(
                _("You cannot bookmark a session that belongs to another user.")
            )
        if not name:
            name = session.product_tmpl_id.name or _("Saved configuration")
        return self.create(
            {
                "name": name,
                "session_id": session.id,
                "user_id": session.user_id.id,
            }
        )


class ProductConfigSession(models.Model):
    """Inherited to add a reverse relation to bookmarks and a
    has-bookmark convenience flag.

    The legacy ``bookmark_name`` and ``is_saved`` fields on this
    model are preserved for two reasons:

    1. Backwards compatibility — earlier callers (the
       ``save_configuration_bookmark`` JSON-RPC endpoint, the OCA
       17.0 wizard "save" button if anyone has it customized) wrote
       to these fields directly. Removing them would silently
       break.

    2. The session GC cron (`_gc_draft_sessions`) needs a way to
       skip sessions that have an associated bookmark — checking
       ``is_saved`` is the original mechanism. We could rewrite the
       GC to check ``bookmark_ids`` instead (preferred long-term);
       this commit keeps the legacy field as a synchronized
       compute for one release cycle so both paths agree.
    """

    _inherit = "product.config.session"

    bookmark_ids = fields.One2many(
        comodel_name="product.config.bookmark",
        inverse_name="session_id",
        string="Bookmarks",
        help="Bookmarks pointing at this configuration session. "
        "Multiple bookmarks may reference the same session (the "
        "buyer renamed it, the same configuration was saved twice "
        "under different labels, etc.).",
    )
    has_active_bookmark = fields.Boolean(
        compute="_compute_has_active_bookmark",
        store=True,
        help="True when at least one active bookmark references "
        "this session. Used by the session GC to skip bookmarked "
        "sessions regardless of age.",
    )

    @api.depends("bookmark_ids.active")
    def _compute_has_active_bookmark(self):
        for session in self:
            session.has_active_bookmark = any(
                b.active for b in session.bookmark_ids
            )

    def action_save_config(self, name=None):
        """Override of the legacy save action.

        The original (in product_config.py) sets ``is_saved=True``
        and stores ``bookmark_name`` on the session row. That logic
        is preserved by calling ``super()`` — any caller that reads
        those legacy fields continues to work.

        On top of that, we create or refresh a
        ``product.config.bookmark`` record so the new portal surface
        and any future buyer-facing UX picks it up.

        Idempotent: if an active bookmark already exists for this
        session, just refresh its ``last_viewed`` and (optionally)
        rename. Avoids duplicate-bookmark proliferation if the
        buyer hits Save twice.
        """
        self.ensure_one()
        # Legacy field writes via super.
        super().action_save_config(name=name)

        # Create or refresh the bookmark record.
        Bookmark = self.env["product.config.bookmark"]
        existing = Bookmark.sudo().search(
            [("session_id", "=", self.id), ("active", "=", True)],
            limit=1,
        )
        if existing:
            update_vals = {"last_viewed": fields.Datetime.now()}
            if name:
                update_vals["name"] = name
            existing.write(update_vals)
            return existing
        return Bookmark.sudo().create_from_session(
            self, name=name or self.bookmark_name
        )
