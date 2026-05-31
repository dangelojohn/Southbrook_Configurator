# SPDX-License-Identifier: LGPL-3.0-only
"""
Portal routes for the Southbrook Estimating Order Builder.

Track 2 commit 1 (2026-05-30) — Phase 2 charter amendment 1:
this is the SCAFFOLD route. Renders a portal page with the chrome,
breadcrumbs, sidebar, and an empty `<div id="order_builder_root">`
placeholder where commit 2 will mount the OWL `<OrderBuilder/>`
component tree.

The controller intentionally leaves the OWL bundle off the page in
this commit so we can verify the portal frame, auth, and routing
work cleanly before adding the JavaScript layer. Commit 2 adds the
OWL bundle to the manifest's assets section and switches this
template to inherit the bundle.

Route shape: `/my/southbrook/order-builder/<int:order_id>`
  Matches Odoo portal convention (`/my/...`) so portal-side menu
  hooks + breadcrumbs work without bespoke wiring.

Auth model: portal user; `partner_id.parent_id` chain identifies
the dealer. The controller verifies the order belongs to either
the logged-in partner OR the partner's parent (dealer org).
"""
from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


# ======================================================================
# Phase 2 commit 1 (2026-05-31) — /kitchen-planner scaffold
#
# The CUSTOMER-facing one-page configurator per CLAUDE.md §2.1.
# Three-pane layout per PRODBOARD_MANIFEST §8.1:
#   left  58 px tool rail
#   centre 394 px catalog pane (296×94 tile grid)
#   right flex viewport (Phase 3 mounts Three.js parametric carcass here;
#         Phase 2 ships the 2D-isometric SVG fallback at Tier 3 per the
#         four-tier image cascade per CLAUDE.md §4.5)
#
# This commit scaffolds:
#   - The /kitchen-planner route (portal-authed, website=True so the
#     site frame, theme, and breadcrumbs apply).
#   - The mount-point template with `id="kitchen_planner_root"` (mirrors
#     T2C1's pattern for the Order Builder — commit 2 here would mount
#     <KitchenPlanner/> OWL component into it).
#   - The three-pane SCSS layout grid + Southbrook token import.
#
# This commit does NOT yet ship:
#   - The OWL component tree (Phase 2 commit 2+).
#   - Catalog tile renderer (Phase 2 commit 3+).
#   - The 2D-isometric SVG layer (Phase 2 commit 4+).
#   - Live attribute → price wiring (Phase 2 commit 5+).
#   - "Request a Price" → sale.order.draft + portal email (Phase 2
#     commit 6+).
#   - The Three.js procedural 3D layer (Phase 3).
#
# Auth model: same `auth="user"` as the Order Builder route. The
# customer logs in as an Odoo portal user (light auth — name + email).
# No SSO yet; Phase 4 polish.
# ======================================================================
class SouthbrookKitchenPlanner(http.Controller):
    """Customer-facing /kitchen-planner one-page configurator route."""

    @http.route(
        "/kitchen-planner",
        type="http",
        auth="user",
        website=True,
    )
    def kitchen_planner(self, **kw):
        """Render the customer kitchen planner.

        Phase 2 commit 1 surface: empty three-pane shell with the
        mount-point div in the viewport pane. Commit 2 mounts the OWL
        <KitchenPlanner/> component into that div via planner_boot.esm.js.
        """
        values = {
            "page_name": "southbrook_kitchen_planner",
            "owl_mount_id": "kitchen_planner_root",
            "user_partner": request.env.user.partner_id,
        }
        return request.render(
            "southbrook_estimating_website.kitchen_planner_template",
            values,
        )

    # ==================================================================
    # Phase 2 commit 2 — initial state JSON-RPC endpoint.
    #
    # The OWL <KitchenPlanner/> component calls this on mount to seed
    # its reactive store. Shape mirrors the planned state.session +
    # state.catalog objects the customer SPA needs:
    #
    #   { user: {partner_id, partner_name, channel}
    #     catalog: [{xml_id, sku, name, family, list_price, ...}, ...]
    #     currency: {symbol, position, decimal_places}
    #     session: null  # commit 3+ surfaces an active config session
    #   }
    #
    # Auth=user keeps the planner behind portal-light auth per
    # CLAUDE.md §2.1 ("behind light auth"). Public anonymous browsing
    # is a Phase-3-polish ask separate from this scope.
    # ==================================================================
    @http.route(
        "/southbrook/api/kitchen-planner/state",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def kitchen_planner_state(self, **kw):
        """Return the initial state payload the OWL planner mounts with.

        Phase 2 commit 2 surface: read-only — catalog + user. Subsequent
        commits add session create/update/commit endpoints.
        """
        user = request.env.user
        partner = user.partner_id

        # Catalog: the 12 Q8 cabinet templates. Filtered to config_ok
        # so only configurable cabinets appear (excludes any future
        # demo / utility templates).
        templates = request.env["product.template"].sudo().search([
            ("config_ok", "=", True),
            ("default_code", "like", "SB-"),
        ])
        catalog = [
            {
                "id": t.id,
                "sku": t.default_code or "",
                "name": t.name,
                "list_price": t.list_price,
                "family": self._family_from_sku(t.default_code or ""),
            }
            for t in templates
        ]

        # Website currency (CAD on the southbrook stack per #5).
        # JSON-RPC routes don't get `request.website` injected (that
        # requires `website=True` on the route, which is only valid
        # for `type='http'`). Use get_current_website() instead.
        Website = request.env["website"].sudo()
        website = Website.get_current_website() if hasattr(Website, "get_current_website") else Website
        currency = (website and website.currency_id) or request.env.company.currency_id

        # Partner channel resolution — informs the planner's
        # "your tier / dealer" badge in the viewport corner. Customer
        # users default to channel='retail' if their partner has no
        # channel set.
        channel = getattr(partner, "channel", None) or "retail"

        return {
            "ok": True,
            "user": {
                "partner_id": partner.id,
                "partner_name": partner.name,
                "channel": channel,
            },
            "catalog": catalog,
            "currency": {
                "symbol": currency.symbol or "$",
                "position": currency.position or "before",
                "decimal_places": currency.decimal_places or 2,
                "name": currency.name or "USD",
            },
            "session": None,
        }

    # Helper — derive family code from SKU. Mirrors the Q8 family
    # taxonomy without re-deriving the full _SKU_DEFAULTS table
    # (which lives on product.config.line in southbrook_estimating).
    _FAMILY_BY_PREFIX = {
        "SB-WALL":     "wall",
        "SB-BASE":     "base",
        "SB-DRAWER":   "drawer",
        "SB-SINK":     "sink",
        "SB-TALL":     "tall",
        "SB-CORNER":   "corner",
        "SB-VANITY":   "vanity",
        "SB-ACCESSORY": "accessory",
        "SB-WORKTOP":  "worktop",
    }

    def _family_from_sku(self, sku):
        for prefix, family in self._FAMILY_BY_PREFIX.items():
            if sku.startswith(prefix):
                return family
        return ""


class SouthbrookOrderBuilderPortal(CustomerPortal):
    """Portal route hosting the OWL Order Builder."""

    # T2C1 NF: website=True is required after all. The portal layout
    # template (portal.frontend_layout, called via portal.portal_layout)
    # references the `website` variable in scope, so without
    # website=True the render aborts with KeyError: 'website'.
    # With website=True Odoo injects the current website record (id 1
    # "My Website" on the southbrook stack) into the template context.
    @http.route(
        ["/my/southbrook/order-builder",
         "/my/southbrook/order-builder/<int:order_id>"],
        type="http",
        auth="user",
        website=True,
    )
    def southbrook_order_builder(self, order_id=None, **kw):
        """Render the Order Builder portal page.

        Without order_id: shows the dealer's list of open orders so
        they can pick one (Phase 2 commit 3 polish).

        With order_id: validates access (the partner OR their parent
        partner must own the order), then renders the OWL mount-point
        template with the order context.
        """
        order = None
        if order_id is not None:
            try:
                order = self._southbrook_resolve_order(order_id)
            except (AccessError, MissingError):
                return request.redirect("/my")

        values = self._prepare_southbrook_portal_values(order)
        return request.render(
            "southbrook_estimating_website.portal_order_builder",
            values,
        )

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    def _southbrook_resolve_order(self, order_id):
        """Look up the sale.order and check the user has access.

        Access rule:

          • Internal users (admin, sales reps, anyone whose
            res.users.share is False) see every order — they're
            staff with full backend access anyway, the portal page
            is just an alternate presentation.

          • Portal users (res.users.share=True — customers and
            dealers logged in via the public portal): the logged-in
            partner must equal order.partner_id, OR order.partner_id
            .parent_id must equal the logged-in partner (dealer
            views customer order), OR the logged-in partner's
            parent_id must equal order.partner_id (parent partner
            views child's order).

          • Anything else → AccessError, controller redirects to /my.
        """
        order = request.env["sale.order"].sudo().browse(order_id).exists()
        if not order:
            raise MissingError("Sale order not found.")

        user = request.env.user
        if not user.share:
            # Internal user — full access.
            return order

        my_partner = user.partner_id
        order_partner = order.partner_id
        if my_partner == order_partner:
            return order
        if order_partner.parent_id and order_partner.parent_id == my_partner:
            return order
        if my_partner.parent_id and my_partner.parent_id == order_partner:
            return order
        # Phase 3: dealer-portal page lists every order under the
        # dealer's whole partner tree; for commit 1 we keep access
        # tight to the same partner or first-level parent/child.
        raise AccessError("This order is not accessible to your account.")

    def _prepare_southbrook_portal_values(self, order):
        """Common template context (sidebar, breadcrumb, palette tokens)."""
        values = self._prepare_portal_layout_values()
        values.update({
            "page_name": "southbrook_order_builder",
            "order": order,
            "order_id": order.id if order else None,
            "order_name": order.name if order else "New Order",
            "user_partner": request.env.user.partner_id,
            # Track 2 commits 2+ will add an "owl_mount_id" used by the
            # OWL bootstrap to find its mount point on the page.
            "owl_mount_id": "order_builder_root",
        })
        return values

    # ==================================================================
    # T2C4 — JSON-RPC: /southbrook/api/order/<id>
    #
    # Returns the normalised order payload the OWL `<OrderBuilder/>`
    # store (commit 5) will consume. Shape mirrors the mockup's
    # state.order + state.lines + state.zones objects so the
    # client-side reducer barely needs to transform.
    # ==================================================================

    # Channel → human label + discount %. Mirrors the dispatcher in
    # southbrook_estimating.sale_order. Phase 3 polish reads these
    # from a database table so non-engineers can edit labels.
    _CHANNEL_META = {
        "dealer":       {"label": "DEALER · -50%",            "discount_pct": 50, "css": "dealer"},
        "tradesperson": {"label": "CONTRACTOR · Tiered",      "discount_pct": 0,  "css": "tradesperson"},
        "kd":           {"label": "CENTRAL KD",               "discount_pct": 54, "css": "kd"},
        "bigbox":       {"label": "BIG-BOX WHOLESALE",        "discount_pct": 33, "css": "bigbox"},
        "refacing":     {"label": "REFACING · CTHS",          "discount_pct": 35, "css": "refacing"},
        "retail":       {"label": "RETAIL · list price",      "discount_pct": 0,  "css": "retail"},
    }
    _TRADESPERSON_TIER_DISCOUNT = {"1": 25, "2": 30, "3": 35}

    # T2C10 — ConfigDrawer autosave endpoint.
    #
    # The OWL drawer fires this when the user edits Qty (the only
    # editable field in commit 10 — Phase 3 polish extends to
    # attribute pickers + custom-spec text). Returns {ok: true} on
    # success; the frontend then re-fetches /api/order/<id> to
    # refresh prices, line subtotals, zone subtotals, header totals.
    #
    # Auth: same partner-chain resolver as the read endpoint. Reuses
    # the order's resolver via line.order_id.
    @http.route(
        "/southbrook/api/line/<int:line_id>/update",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def southbrook_api_line_update(self, line_id, qty=None, **kw):
        """Apply a partial edit to a sale.order.line.

        Phase 2 commit 10 surface: qty only. The frontend may send
        other keys (e.g. zone, spec text) — they're ignored without
        error so commit-11+ doesn't need a separate version field.
        """
        line = request.env["sale.order.line"].sudo().browse(line_id).exists()
        if not line:
            return {"error": "not_found"}
        try:
            self._southbrook_resolve_order(line.order_id.id)
        except (AccessError, MissingError):
            return {"error": "forbidden"}

        # Apply qty update if present.
        if qty is not None:
            try:
                qty_f = float(qty)
            except (TypeError, ValueError):
                return {"error": "invalid_qty"}
            if qty_f <= 0:
                return {"error": "invalid_qty"}
            line.with_user(request.env.user).product_uom_qty = qty_f

        return {"ok": True, "line_id": line.id}

    # T2C12 — FooterActions dispatcher.
    #
    # Single endpoint that the OWL FooterActions component calls with
    # action_code in {confirm, duplicate, print}. Returns {ok, ...}
    # or {error, ...}. The dispatch keeps the API surface small and
    # avoids one route per button.
    @http.route(
        "/southbrook/api/order/<int:order_id>/action",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def southbrook_api_order_action(self, order_id, action_code=None, **kw):
        try:
            order = self._southbrook_resolve_order(order_id)
        except MissingError:
            return {"error": "not_found"}
        except AccessError:
            return {"error": "forbidden"}

        order_su = order.with_user(request.env.user)

        if action_code == "confirm":
            if order.state not in ("draft", "sent"):
                return {
                    "error": "wrong_state",
                    "message": (
                        "Order must be in draft/sent state — current "
                        + str(order.state)
                    ),
                }
            order_su.action_confirm()
            return {"ok": True, "new_state": order.state}

        if action_code == "request_price":
            # T2C13 customer-mode "Request a Price" path. Phase-1
            # behaviour: same as confirm. Phase 3 polish:
            #   - DO NOT confirm immediately; flip to "sent" or a
            #     new "awaiting_pricing" state.
            #   - Post a portal message to the assigned salesperson
            #     so they review + price + send back.
            #   - Don't allow MO creation until salesperson confirms.
            # For T2C13 we wire the route + return a distinguishable
            # ok payload so the frontend can render the right success
            # message; behaviour parity with confirm for now.
            if order.state not in ("draft", "sent"):
                return {
                    "error": "wrong_state",
                    "message": "Order already past pricing review.",
                }
            order_su.action_confirm()
            return {
                "ok": True,
                "new_state": order.state,
                "submitted_for_pricing": True,
            }

        if action_code == "duplicate":
            # action_duplicate_as_draft is the NF6 method on
            # southbrook_estimating.sale_order. Returns an
            # ir.actions.act_window dict pointing at the new draft.
            if not hasattr(order_su, "action_duplicate_as_draft"):
                return {"error": "feature_missing"}
            try:
                action = order_su.action_duplicate_as_draft()
            except Exception as exc:                            # noqa: BLE001
                return {"error": "dup_failed", "message": str(exc)}
            new_id = action.get("res_id") if isinstance(action, dict) else None
            if not new_id:
                return {"error": "dup_failed",
                        "message": "No new_id returned"}
            return {
                "ok": True,
                "new_order_id": new_id,
                "redirect_url": f"/my/southbrook/order-builder/{new_id}",
            }

        if action_code == "print":
            # Signature Spec Sheet QWeb PDF — the customer-print
            # report from southbrook_estimating Track 1. We hand the
            # URL back; the OWL component opens it in a new tab so
            # the SPA stays mounted.
            report_xml_id = (
                "southbrook_estimating.action_report_signature_spec_sheet"
            )
            return {
                "ok": True,
                "redirect_url": f"/report/pdf/{report_xml_id}/{order_id}",
            }

        return {"error": "unknown_action", "message": str(action_code)}

    # Phase 2.5 commit 1 — portal kitchen-3d payload.
    #
    # Mirrors the backend `sale.order.get_kitchen_3d_payload` (Track 1
    # T1C6) for portal-auth consumers. Returns the same shape so the
    # portal-side KitchenViewport can reuse Track 1's rendering logic
    # without payload translation.
    @http.route(
        "/southbrook/api/order/<int:order_id>/kitchen-3d",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def southbrook_api_kitchen_3d(self, order_id, **kw):
        try:
            order = self._southbrook_resolve_order(order_id)
        except MissingError:
            return {"error": "not_found"}
        except AccessError:
            return {"error": "forbidden"}
        # The method itself is on the southbrook_estimating sale.order
        # extension (Track 1 T1C6). Same env, same source of truth.
        return order.with_user(request.env.user).get_kitchen_3d_payload()

    @http.route(
        "/southbrook/api/order/<int:order_id>",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def southbrook_api_order(self, order_id, **kw):
        """Return the order shape for the OWL store."""
        try:
            order = self._southbrook_resolve_order(order_id)
        except MissingError:
            return {"error": "not_found"}
        except AccessError:
            return {"error": "forbidden"}
        return self._build_southbrook_order_payload(order)

    def _build_southbrook_order_payload(self, order):
        """Shape the order + lines + zones for client-side consumption.

        Stable contract (the OWL store keys against these names):

            {
              "order": {
                  id, name, state, version,
                  partner_id, partner_name, via,
                  channel, channel_label, channel_css,
                  tradesperson_tier,
                  pricelist_id, pricelist_name,
                  discount_pct,
                  retail_subtotal, channel_total, savings,
                  lead_time_days, line_count
              },
              "lines": [
                  {
                    id, sequence, product_id, product_name, product_sku,
                    family, zone, zone_label, qty,
                    price_unit, price_subtotal, retail_price, channel_price,
                    config_session_id, spec_summary, is_maple, rule_blocked
                  },
                  ...
              ],
              "zones": [
                  { code, label, line_count, subtotal, channel_subtotal },
                  ...
              ]
            }
        """
        partner = order.partner_id
        channel = (partner.channel or "retail") if hasattr(partner, "channel") else "retail"
        tier = (
            partner.tradesperson_tier
            if hasattr(partner, "tradesperson_tier") else None
        )
        # Resolve effective discount %.
        if channel == "tradesperson" and tier:
            discount_pct = self._TRADESPERSON_TIER_DISCOUNT.get(tier, 0)
            channel_label = f"CONTRACTOR · TIER {tier} · -{discount_pct}%"
        else:
            meta = self._CHANNEL_META.get(channel) or self._CHANNEL_META["retail"]
            discount_pct = meta["discount_pct"]
            channel_label = meta["label"]
        channel_css = (self._CHANNEL_META.get(channel) or {}).get("css", "retail")

        # Through-partner ("via Image Floor" reads when a dealer is the
        # customer's partner.parent_id).
        via = partner.parent_id.name if partner.parent_id else None

        retail_subtotal = sum(line.price_subtotal for line in order.order_line)
        channel_total = retail_subtotal * (1 - discount_pct / 100.0)
        savings = retail_subtotal - channel_total

        # Per-line shape.
        lines = []
        zone_buckets = {}
        for idx, line in enumerate(order.order_line, start=1):
            tmpl = (
                line.product_id.product_tmpl_id
                if line.product_id and line.product_id.product_tmpl_id
                else None
            )
            sku = tmpl.default_code if tmpl else ""
            # Family lookup via the SKU defaults table on product.config.session
            # (already used by Track 1 — single source of truth).
            sku_row = request.env["product.config.session"]._SKU_DEFAULTS.get(sku)
            family = sku_row[0] if sku_row else ""

            # Spec summary — the line name carries the attribute mix for
            # dynamic-variant cabinets. Strip the product display prefix
            # when present so the spec text reads cleanly.
            spec_summary = (line.name or "").strip()
            if tmpl and tmpl.display_name and spec_summary.startswith(tmpl.display_name):
                spec_summary = spec_summary[len(tmpl.display_name):].lstrip(" /·-")

            is_maple = "Maple" in spec_summary

            line_retail = line.price_subtotal
            line_channel = line_retail * (1 - discount_pct / 100.0)

            # T2C9 — width fields for the line-row display. Width
            # comes from the SKU defaults table (commit 4 wired the
            # family lookup; same row carries the width). Phase 3
            # polish reads the configured width from the line's
            # variant attributes once dynamic-variant materialisation
            # lands; for now the SKU default is the natural fallback.
            width_mm = sku_row[3] if sku_row else 0
            # Round to 0.25" granularity (cabinet-industry standard).
            width_inches = (
                round((width_mm / 25.4) * 4) / 4 if width_mm else 0
            )

            line_payload = {
                "id": line.id,
                "sequence": idx,
                "product_id": line.product_id.id if line.product_id else None,
                "product_name": tmpl.display_name if tmpl else (line.name or ""),
                "product_sku": sku or "",
                "family": family,
                "zone": line.zone or "other",
                "zone_label": line.zone_label or "",
                "qty": line.product_uom_qty,
                "price_unit": line.price_unit,
                "price_subtotal": line.price_subtotal,
                "retail_price": line_retail,
                "channel_price": line_channel,
                "width_mm": width_mm,
                "width_inches": width_inches,
                "config_session_id": (
                    line.config_session_id.id
                    if hasattr(line, "config_session_id")
                    and line.config_session_id
                    else None
                ),
                "spec_summary": spec_summary,
                "is_maple": is_maple,
                # Phase 3 polish wires the rule engine output per-line; for
                # now nothing is rule-blocked at payload time.
                "rule_blocked": False,
            }
            lines.append(line_payload)

            zb = zone_buckets.setdefault(
                line.zone or "other",
                {
                    "code": line.zone or "other",
                    "label": (
                        dict(line._fields["zone"].selection).get(
                            line.zone, line.zone or "Other",
                        )
                    ),
                    "line_count": 0,
                    "subtotal": 0.0,
                    "channel_subtotal": 0.0,
                },
            )
            zb["line_count"] += 1
            zb["subtotal"] += line_retail
            zb["channel_subtotal"] += line_channel

        # Stable zone ordering for the UI (per Q21 enumeration).
        zone_order = ["base_run", "wall", "tall", "island", "accessory", "other"]
        zones = [
            zone_buckets[z]
            for z in zone_order
            if z in zone_buckets
        ]

        # Lead-time rollup: sum the line lead-time extras (NF11) on top
        # of the base BoM produce_delay. Phase 3 polish: read from
        # mrp.bom.effective_produce_delay once BoMs are auto-materialised
        # per configured variant. For now expose a placeholder of 0 so
        # the OWL store has a stable key to read.
        lead_time_days = 0

        # T2C11 — BoM rollup across the order's SB cabinets. Computes
        # panel + hardware + edge-banding totals by calling Phase-1
        # routine #1 (mrp.bom._compute_panel_dimensions) per line and
        # summing. Same single-source-of-truth pattern as the 3D
        # viewport (Track 1) and the kitchen-run view (T1C6) so any
        # change to BoX_TH / DOOR_TH / etc. propagates everywhere.
        bom_rollup = {
            "cabinet_count": 0,
            "panels": {
                "side": 0,
                "top": 0,
                "bottom": 0,
                "back": 0,
                "shelf": 0,
                "door": 0,
                "drawer_front": 0,
            },
            "hardware": {
                "hinge_pair_count": 0,
                "handle_count": 0,
                "drawer_slide_pair_count": 0,
            },
            "edge_banding_mm": 0,
        }
        Bom = request.env["mrp.bom"]
        # T2C11 fix: walk THIS order's lines, not self.order_line. `self`
        # is the CustomerPortal controller, not the sale.order — the
        # original copy-paste from sale_order.get_kitchen_3d_payload
        # missed the rebind.
        for line in order.order_line:
            tmpl = (
                line.product_id.product_tmpl_id
                if line.product_id and line.product_id.product_tmpl_id
                else None
            )
            sku = tmpl.default_code if tmpl else None
            sku_row = (
                request.env["product.config.session"]._SKU_DEFAULTS.get(sku)
                if sku else None
            )
            if not sku_row:
                continue
            fam, doors, drawers, w, h, d = sku_row
            cut = Bom._compute_panel_dimensions(
                width_mm=w, height_mm=h, depth_mm=d,
                family=fam, door_count=doors, drawer_count=drawers,
                finished_sides="none",
            )
            qty = int(line.product_uom_qty or 0)
            if qty <= 0:
                continue

            bom_rollup["cabinet_count"] += qty
            # Each cabinet: 2 sides + 1 top + 1 bottom + 1 back.
            # Worktop / accessory short-circuit: only 1 panel, no carcass.
            if fam in ("worktop", "accessory"):
                bom_rollup["panels"]["side"] += 1 * qty
            else:
                bom_rollup["panels"]["side"] += 2 * qty
                bom_rollup["panels"]["top"] += 1 * qty
                bom_rollup["panels"]["bottom"] += 1 * qty
                bom_rollup["panels"]["back"] += 1 * qty
            bom_rollup["panels"]["shelf"] += cut.get("shelf_count", 0) * qty
            bom_rollup["panels"]["door"] += cut.get("door_count", 0) * qty
            bom_rollup["panels"]["drawer_front"] += cut.get("drawer_count", 0) * qty
            bom_rollup["hardware"]["hinge_pair_count"] += cut.get("hinge_pair_count", 0) * qty
            bom_rollup["hardware"]["handle_count"] += cut.get("handle_count", 0) * qty
            bom_rollup["hardware"]["drawer_slide_pair_count"] += cut.get("drawer_slide_pair_count", 0) * qty
            bom_rollup["edge_banding_mm"] += cut.get("edge_banding_length_mm", 0) * qty

        # T2C11 — validation issue list. Phase 1 ships an empty list;
        # Phase 3 polish wires the OCA rule engine output here (per-
        # line hard/soft issues). Keeping the key in place now so
        # the OWL ValidationStrip doesn't need to widen the contract.
        validation = []

        return {
            "order": {
                "id":             order.id,
                "name":           order.name,
                "state":          order.state,
                "version":        getattr(order, "version", 1),
                "partner_id":     partner.id,
                "partner_name":   partner.name,
                "via":            via,
                "channel":        channel,
                "channel_label":  channel_label,
                "channel_css":    channel_css,
                "tradesperson_tier": tier,
                "pricelist_id":   order.pricelist_id.id if order.pricelist_id else None,
                "pricelist_name": order.pricelist_id.name if order.pricelist_id else "",
                "discount_pct":   discount_pct,
                "retail_subtotal": retail_subtotal,
                "channel_total":  channel_total,
                "savings":        savings,
                "lead_time_days": lead_time_days,
                "line_count":     len(lines),
            },
            "lines": lines,
            "zones": zones,
            "bom_rollup": bom_rollup,
            "validation": validation,
        }
