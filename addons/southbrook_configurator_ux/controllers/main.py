# SPDX-License-Identifier: LGPL-3.0-only
"""Southbrook Configurator UX v2 — JSON-RPC endpoints.

Phase 2a:
    POST /southbrook/api/configurator/state
        Read-only. Returns the product's attribute_lines + values +
        price_extra + base price + a product.config.session id (created
        or reused).

Phase 2c (this commit):
    POST /southbrook/api/configurator/select
        Updates the session value_ids, returns server-resolved price +
        weight + disabled_value_ids from the OCA product.config.line
        rule engine. Replaces the hardcoded isValueDisabled() rules
        that shipped in Phase 2b.

    POST /southbrook/api/configurator/commit
        Materialises the variant via session.create_get_variant() +
        adds it to the user's draft sale.order, then moves the session
        to state='done'. Per the Phase-2 cart-target decision: A —
        Order Builder, not website_sale cart. Returns a redirect URL
        to /my/southbrook/order-builder/<id> so the client can
        navigate.

Auth model: auth='public' + type='json'. The /shop/<slug> page is
publicly accessible (it's a catalog page), so anonymous visitors can
configure too. JSON-RPC routes don't require CSRF tokens. Sessions
for anonymous visitors live under base.public_user with the standard
OCA cleanup TTL.

No schema changes, no writes outside of product.config.session — which
the OCA module is the canonical custodian of. We sudo() the session
ops because public users don't have direct write ACL on that model,
but the scope is tight: search-or-create then attach to the request
user (not to a different user).
"""
import logging

from odoo import http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


# Logical attribute groups for the configurator's right pane. Matches
# the Phase-1 prototype's 4-group layout, keyed by canonical attribute
# name. Attributes on the template that don't appear here fall through
# into the "Other" group at the end of the list so a future new
# attribute doesn't silently disappear from the UI.
#
# Phase 3+ replaces this with a configurable grouping (likely a small
# ir.config_parameter table or a new field on product.attribute). For
# Phase 2 we keep the visual contract with the prototype.
ATTRIBUTE_GROUPS = [
    ("Size & Layout",         ["Width", "Door Count"]),
    ("Series & Materials",    ["Series", "Box Material", "Door Style"]),
    ("Finish & Construction", ["Finish", "Hinge Side", "Finished Sides", "Gables"]),
    ("Hardware & Add-ons",    ["Handle", "Accessories"]),
]


class SouthbrookConfiguratorAPI(http.Controller):
    """JSON-RPC endpoints for the v2 configurator UX."""

    # ------------------------------------------------------------------
    # /state — read-only product + attributes + session payload.
    # ------------------------------------------------------------------
    @http.route(
        "/southbrook/api/configurator/state",
        type="json",
        auth="public",
        methods=["POST"],
        website=True,
    )
    def configurator_state(self, product_tmpl_id=None, **kw):
        """Return everything the OWL configurator needs to render.

        Args:
            product_tmpl_id: int — the product.template id resolved by
                the OWL bootstrap from the page's mount-point div.

        Response (success):
            {
              ok: True,
              product: {tmpl_id, name, sku, list_price, currency:
                        {symbol, position, decimal_places, name}},
              session_id: int,
              base_price: float,
              groups: [{title: str, attribute_ids: [int, ...]}, ...],
              attributes: {
                "<attribute_id>": {
                  name: str, display_type: str, sequence: int,
                  required: bool,
                  values: [
                    {id, name, price_extra, html_color, sequence},
                    ...
                  ]
                },
                ...
              },
              selected_value_ids: [int, ...]   // existing picks if any
            }

        Response (error):
            {ok: False, error: "<code>", message: "<human-readable>"}
        """
        if not product_tmpl_id:
            return {"ok": False, "error": "missing_product_tmpl_id",
                    "message": "product_tmpl_id is required"}

        try:
            tmpl_id_int = int(product_tmpl_id)
        except (TypeError, ValueError):
            return {"ok": False, "error": "bad_product_tmpl_id",
                    "message": f"product_tmpl_id must be int, got {product_tmpl_id!r}"}

        # Sudo because the OCA configurator option-products attached to
        # attribute values aren't website_published; without sudo the
        # public ir.rule "Public product template" 403s on the
        # template's attribute_line_ids traversal. Same defect /
        # workaround as the OCA WebsiteSale.product override at
        # addons/website_product_configurator/controllers/main.py:135-156.
        # Scope discipline: only the read path is sudo'd; we never
        # write through this sudo recordset.
        Tmpl = request.env["product.template"].sudo()
        tmpl = Tmpl.browse(tmpl_id_int).exists()
        if not tmpl:
            return {"ok": False, "error": "product_not_found",
                    "message": f"No product.template with id={tmpl_id_int}"}
        if not tmpl.config_ok:
            return {"ok": False, "error": "not_configurable",
                    "message": f"{tmpl.display_name} is not configurable "
                               f"(config_ok=False)"}

        # Resolve or create a config session for this user + template.
        # Public visitors get a session attached to base.public_user; the
        # OCA module's standard cleanup cron sweeps stale public sessions.
        session = self._get_or_create_session(tmpl)

        # Build the attribute payload. Iterate attribute_line_ids in
        # sequence order so the UI renders attributes consistently.
        attributes = {}
        for line in tmpl.attribute_line_ids.sorted(key=lambda l: l.attribute_id.sequence):
            attr = line.attribute_id
            # Per-template attribute values carry the price_extra +
            # html_color overrides. The OCA model auto-creates one row
            # per (template, value) when an attribute_line is added.
            ptav_by_value_id = {
                ptav.product_attribute_value_id.id: ptav
                for ptav in line.product_template_value_ids
            }
            values = []
            for val in line.value_ids.sorted(key=lambda v: v.sequence):
                ptav = ptav_by_value_id.get(val.id)
                values.append({
                    "id": val.id,
                    "name": val.name,
                    "sequence": val.sequence,
                    "price_extra": float(ptav.price_extra) if ptav else 0.0,
                    "html_color": ptav.html_color if ptav and ptav.html_color
                                  else (val.html_color or None),
                    # Phase 2c will set this from product.config.line
                    # rule evaluation; for now every value starts enabled.
                    "disabled": False,
                })
            attributes[str(attr.id)] = {
                "name": attr.name,
                "display_type": attr.display_type,
                "sequence": attr.sequence,
                # OCA's required is on the attribute_line, not the
                # attribute, so we expose the line-level flag.
                "required": bool(line.required) if hasattr(line, "required") else False,
                "values": values,
            }

        # Map ATTRIBUTE_GROUPS canonical names to live attribute ids.
        # Attributes present on the template but not in any group fall
        # through into an "Other" group at the end so they're always
        # visible.
        group_payload = []
        all_attr_ids = {a.attribute_id.id: a.attribute_id.name
                        for a in tmpl.attribute_line_ids}
        used_ids = set()
        for title, names in ATTRIBUTE_GROUPS:
            ids = [aid for aid, nm in all_attr_ids.items() if nm in names]
            if ids:
                group_payload.append({"title": title, "attribute_ids": ids})
                used_ids.update(ids)
        leftover = [aid for aid in all_attr_ids if aid not in used_ids]
        if leftover:
            group_payload.append({"title": "Other", "attribute_ids": leftover})

        # Selected values: anything the session already carries — lets
        # a customer reload the page and pick up where they left off.
        selected = session.value_ids.ids if session else []

        # Resolve the SKU from the lowest-id variant (the v19
        # template.default_code-blanks-on-multi-variant gotcha).
        sku = ""
        for variant in tmpl.product_variant_ids.sorted("id"):
            if variant.default_code:
                sku = variant.default_code
                break
        if not sku and tmpl.default_code:
            sku = tmpl.default_code

        # Website currency for the UI's $ formatter.
        Website = request.env["website"].sudo()
        website = (Website.get_current_website()
                   if hasattr(Website, "get_current_website") else Website)
        currency = ((website and website.currency_id)
                    or request.env.company.currency_id)

        return {
            "ok": True,
            "product": {
                "tmpl_id": tmpl.id,
                "sku": sku,
                "name": tmpl.name,
                "list_price": float(tmpl.list_price),
                "currency": {
                    "symbol": currency.symbol or "$",
                    "position": currency.position or "before",
                    "decimal_places": currency.decimal_places or 2,
                    "name": currency.name or "CAD",
                },
            },
            "session_id": session.id if session else None,
            "base_price": float(tmpl.list_price),
            "groups": group_payload,
            "attributes": attributes,
            "selected_value_ids": selected,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_or_create_session(self, tmpl):
        """Search for an existing session for (user, template); create if absent.

        Sessions are tied to res.users. Public visitors land on
        base.public_user; portal / internal users get their own
        session. The OCA configurator's cleanup cron handles
        abandoned public sessions on a TTL.
        """
        Session = request.env["product.config.session"]
        # Search as the actual user first — if they have draft sessions
        # we want to honour their ACL. If the search returns empty AND
        # we have to create, that's where we sudo (so public users can
        # create their own session row).
        existing = Session.search([
            ("product_tmpl_id", "=", tmpl.id),
            ("user_id", "=", request.env.user.id),
            ("state", "=", "draft"),
        ], limit=1, order="create_date desc")
        if existing:
            return existing
        return Session.sudo().create({
            "product_tmpl_id": tmpl.id,
            "user_id": request.env.user.id,
        })

    # ------------------------------------------------------------------
    # /select — apply picks, return server-resolved price + disabled set.
    # ------------------------------------------------------------------
    @http.route(
        "/southbrook/api/configurator/select",
        type="json",
        auth="public",
        methods=["POST"],
        website=True,
    )
    def configurator_select(self, session_id=None, value_ids=None, **kw):
        """Update the session's value_ids and return server-resolved
        price + weight + disabled_value_ids (from the OCA rule engine).

        Client contract: send the COMPLETE current pick set as
        `value_ids` — the server resolves diffs internally. Sending a
        smaller set than last time means the missing attributes get
        cleared. Sending an unrelated value_id (not on the template)
        gets silently skipped.

        Args:
            session_id: int — the session created by /state
            value_ids: [int] — current picks, one value per attribute
                       at most

        Response (success):
            {
              ok: True,
              selected_value_ids: [int],     // what the server settled on
              price: float,                  // base + sum(price_extras)
              weight: float,                 // computed by OCA
              disabled_value_ids: [int],     // values forbidden by rules
              warnings: [str]                // reserved for soft messages
            }

        Response (error):
            {ok: False, error: "<code>", message: "<text>"}
        """
        if not session_id:
            return {"ok": False, "error": "missing_session_id"}
        if not isinstance(value_ids, list):
            return {"ok": False, "error": "value_ids_must_be_list",
                    "message": "value_ids must be a JSON array of ints"}

        try:
            session = self._authorize_session(int(session_id))
        except ValueError:
            return {"ok": False, "error": "bad_session_id"}
        if isinstance(session, dict):
            return session  # error dict bubbled up from the helper

        if session.state != "draft":
            return {"ok": False, "error": "session_locked",
                    "message": "This configuration was already committed."}

        tmpl = session.product_tmpl_id

        # Build {attribute_id: value_id} dict from the flat value_ids
        # list. Resolve each value's attribute via the global
        # product.attribute.value record. Unknown values are skipped;
        # if two values land for the same attribute (client bug), the
        # later one wins via dict semantics.
        Value = request.env["product.attribute.value"].sudo()
        attr_val_dict = {}
        for vid in value_ids:
            try:
                vid_int = int(vid)
            except (TypeError, ValueError):
                continue
            val = Value.browse(vid_int).exists()
            if val:
                attr_val_dict[val.attribute_id.id] = vid_int

        # Attributes on the template that aren't in the new picks get
        # explicitly cleared so OCA's update_config removes their old
        # value rather than carrying it over.
        for line in tmpl.attribute_line_ids:
            aid = line.attribute_id.id
            if aid not in attr_val_dict:
                attr_val_dict[aid] = []

        try:
            session.sudo().update_config(attr_val_dict)
        except (UserError, ValidationError) as exc:
            return {"ok": False, "error": "rule_blocked",
                    "message": getattr(exc, "args", [str(exc)])[0]}

        # Compute the disabled set: every value the template exposes
        # minus the available subset given current picks.
        all_val_ids = list({
            vid
            for line in tmpl.attribute_line_ids
            for vid in line.value_ids.ids
        })
        try:
            available_ids = session.sudo().values_available(
                check_val_ids=list(all_val_ids),
            )
            available_ids = [int(v) for v in available_ids]
        except Exception:                                  # noqa: BLE001
            # Belt-and-braces: if values_available barfs (rare; usually
            # only if a malformed rule landed in the DB), fall back to
            # "nothing disabled" rather than failing the whole pick.
            _logger.warning(
                "values_available raised on session %s; treating all "
                "values as enabled this round.",
                session.id, exc_info=True,
            )
            available_ids = list(all_val_ids)
        disabled_ids = sorted(set(all_val_ids) - set(available_ids))

        return {
            "ok": True,
            "selected_value_ids": session.value_ids.ids,
            "price": float(session.price or 0.0),
            "weight": float(getattr(session, "weight", 0.0) or 0.0),
            "disabled_value_ids": disabled_ids,
            "warnings": [],
        }

    # ------------------------------------------------------------------
    # /commit — materialise variant + add to user's draft sale.order.
    # ------------------------------------------------------------------
    @http.route(
        "/southbrook/api/configurator/commit",
        type="json",
        auth="public",
        methods=["POST"],
        website=True,
    )
    def configurator_commit(self, session_id=None, order_id=None, **kw):
        """Materialise a product.product variant from the session +
        add it as a sale.order.line on the visitor's draft order.

        Public visitors get login_required (anonymous quotes aren't
        supported in the Southbrook flow per the existing customer-
        flow controller). They're sent to /web/signup with a return
        URL back to the current configurator page so they can finish
        what they started after signup.

        Per the Phase-2 cart-target decision: A — Order Builder.
        On success the client navigates to
        /my/southbrook/order-builder/<order_id> (the redirect field
        in the response).

        Args:
            session_id: int — the configured session
            order_id: int — optional. If supplied, the variant is
                      appended to that order (which must belong to
                      the same user). If absent, the importer reuses
                      the user's most-recent draft sale.order, or
                      creates a new draft if none exists.

        Response (success):
            {
              ok: True,
              variant_id: int,
              order_id: int,
              order_line_id: int,
              redirect: "/my/southbrook/order-builder/<id>",
            }

        Response (error):
            {ok: False, error: "<code>", message: "<text>",
             login_url: "..."?, state: "<order.state>"?}
        """
        # Anonymous visitors: surface login_required so the OWL
        # component can render a "Sign in to add to quote" CTA
        # instead of a generic AccessError.
        if request.env.user._is_public():
            return {
                "ok": False,
                "error": "login_required",
                "login_url": "/web/signup",
                "message": "Sign in or create a free account to add this "
                           "configuration to your quote.",
            }

        if not session_id:
            return {"ok": False, "error": "missing_session_id"}

        try:
            session = self._authorize_session(int(session_id))
        except ValueError:
            return {"ok": False, "error": "bad_session_id"}
        if isinstance(session, dict):
            return session

        if session.state != "draft":
            return {"ok": False, "error": "session_locked",
                    "message": "This configuration has already been added "
                               "to a quote. Start a new one to add another."}

        # Materialise (or fetch existing) variant for the picks.
        # OCA's create_get_variant calls validate_configuration first;
        # it raises ValidationError on rule violation or missing
        # required values.
        try:
            variant = session.sudo().create_get_variant()
        except (UserError, ValidationError) as exc:
            return {"ok": False, "error": "validation_failed",
                    "message": getattr(exc, "args", [str(exc)])[0]}

        # Resolve or create the user's draft sale.order. Same pattern
        # as southbrook_estimating_website's G9 self-service order
        # creation (one draft per partner; reused across multiple
        # add-to-quote actions until the partner submits it).
        partner = request.env.user.partner_id
        SaleOrder = request.env["sale.order"].sudo()
        if order_id:
            try:
                order = SaleOrder.browse(int(order_id)).exists()
            except ValueError:
                return {"ok": False, "error": "bad_order_id"}
            if not order:
                return {"ok": False, "error": "order_not_found"}
            # Authorize: order must belong to this user's partner.
            if order.partner_id.id != partner.id:
                return {"ok": False, "error": "order_forbidden"}
            if order.state not in ("draft", "sent"):
                return {"ok": False, "error": "order_locked",
                        "state": order.state,
                        "message": f"Cannot add to a {order.state} order; "
                                   f"start a new quote."}
        else:
            order = SaleOrder.search([
                ("partner_id", "=", partner.id),
                ("state", "=", "draft"),
            ], limit=1, order="create_date desc")
            if not order:
                order = SaleOrder.create({"partner_id": partner.id})

        # Add the variant as a new order line. qty=1 by default; the
        # customer can change qty in the Order Builder. Trigger
        # product_id_change so price_unit / name / uom populate from
        # the variant.
        line = request.env["sale.order.line"].sudo().create({
            "order_id": order.id,
            "product_id": variant.id,
            "product_uom_qty": 1,
        })
        if hasattr(line, "product_id_change"):
            line.product_id_change()

        # Lock the session: state='done' + product_id link. A new
        # configuration starts a new session via /state.
        try:
            session.sudo().action_confirm(product_id=variant)
        except Exception:                                   # noqa: BLE001
            # action_confirm failure is non-fatal — the variant was
            # created + the line was added; the session just stays
            # in draft (and the cleanup cron handles it eventually).
            _logger.warning(
                "session.action_confirm failed on session %s; "
                "variant %s + line %s already created.",
                session.id, variant.id, line.id, exc_info=True,
            )

        return {
            "ok": True,
            "variant_id": variant.id,
            "order_id": order.id,
            "order_line_id": line.id,
            "redirect": f"/my/southbrook/order-builder/{order.id}",
        }

    # ------------------------------------------------------------------
    # Shared helper: resolve + authorize a session by id.
    # ------------------------------------------------------------------
    def _authorize_session(self, session_id):
        """Browse + permission-check a session.

        Returns the recordset on success, or an error dict (caller
        bubbles it up as-is to the client) on failure. Sessions can
        only be touched by the user who created them — same shape as
        the customer-flow controller's _southbrook_resolve_order
        authorisation guard.
        """
        Session = request.env["product.config.session"].sudo()
        session = Session.browse(session_id).exists()
        if not session:
            return {"ok": False, "error": "session_not_found"}
        if session.user_id.id != request.env.user.id:
            return {"ok": False, "error": "forbidden",
                    "message": "This configuration session belongs to a "
                               "different user."}
        return session
