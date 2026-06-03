# SPDX-License-Identifier: LGPL-3.0-only
"""Southbrook Configurator UX v2 — JSON-RPC endpoints.

Phase 2a (this commit):
    POST /southbrook/api/configurator/state
        Read-only. Returns the product's attribute_lines + values +
        price_extra + base price + a product.config.session id (created
        or reused). The OWL component fetches this on mount instead of
        the hardcoded OPTIONS object that ships with Phase 1.

Phase 2c (deferred):
    POST /southbrook/api/configurator/select
        Updates the session value_ids, returns server-resolved price +
        weight + disabled_value_ids from product.config.line rules.

    POST /southbrook/api/configurator/commit
        Materialises the variant + adds it to the user's draft
        sale.order (per the Phase-2 cart-target decision: A — Order
        Builder, not website_sale cart).

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
