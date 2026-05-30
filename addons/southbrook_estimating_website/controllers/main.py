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
        }
