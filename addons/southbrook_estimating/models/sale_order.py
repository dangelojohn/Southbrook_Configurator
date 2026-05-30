# SPDX-License-Identifier: LGPL-3.0-only
"""
sale.order extension — channel-to-pricelist resolution dispatcher.

This file IS custom routine #3 per Build Spec section 4. Adding any
business logic beyond _resolve_channel_pricelist requires PUNCHLIST
justification.

The dispatcher reads partner.channel (and partner.tradesperson_tier
when applicable) and returns the matching pricelist record. Called
from a default-getter on pricelist_id so the user can still manually
override the resolved pricelist post-creation.

NF5 behaviour: when channel=tradesperson and tier is null, returns
the base pricelist_tradesperson (cost+5% floor, no tier discount).
A soft warning is logged (not raised) so order creation isn't
blocked but the operations team is alerted.
"""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # Channel → pricelist xml_id mapping (Q1). Centralised alongside the
    # _TRADESPERSON_TIER_PRICELISTS table below for symmetry. Tradesperson
    # is the one channel that needs a sub-dispatcher (NF5 tier resolution);
    # the others are flat direct lookups.
    _CHANNEL_PRICELISTS = {
        "retail":   "southbrook_estimating.pricelist_retail",
        "dealer":   "southbrook_estimating.pricelist_dealer",
        "kd":       "southbrook_estimating.pricelist_kd",
        "bigbox":   "southbrook_estimating.pricelist_bigbox",
        "refacing": "southbrook_estimating.pricelist_refacing",
    }
    _FALLBACK_PRICELIST_XML_ID = "southbrook_estimating.pricelist_retail"

    @api.model
    def _resolve_channel_pricelist(self, partner):
        """Return the product.pricelist matching the partner's channel.

        Custom routine #3 per Build Spec section 4. Dispatch-only — no
        business logic beyond mapping channel -> pricelist xml_id.

        Args:
            partner: a res.partner record.

        Returns:
            A product.pricelist record. Falls back to retail when no
            partner is supplied or the channel is unrecognised.
        """
        if not partner:
            return self.env.ref(self._FALLBACK_PRICELIST_XML_ID)

        channel = partner.channel or "retail"

        if channel == "tradesperson":
            return self._resolve_tradesperson_pricelist(partner)

        return self.env.ref(
            self._CHANNEL_PRICELISTS.get(channel, self._FALLBACK_PRICELIST_XML_ID)
        )

    # Tier → pricelist xml_id mapping (NF5). Adding a tier 4 means one
    # row here, one row in res.partner.tradesperson_tier selection, one
    # new pricelist record. Centralising the table makes the contract obvious.
    _TRADESPERSON_TIER_PRICELISTS = {
        "1": "southbrook_estimating.pricelist_tradesperson_tier_1",
        "2": "southbrook_estimating.pricelist_tradesperson_tier_2",
        "3": "southbrook_estimating.pricelist_tradesperson_tier_3",
    }

    def _resolve_tradesperson_pricelist(self, partner):
        """Pick the right tradesperson tier sub-pricelist (NF5).

        Returns the tier-specific pricelist when the partner has a
        tradesperson_tier set; falls back to the base (cost+5% floor,
        no tier discount) with a soft warning otherwise.
        """
        tier_xml_id = self._TRADESPERSON_TIER_PRICELISTS.get(
            partner.tradesperson_tier
        )
        if tier_xml_id:
            return self.env.ref(tier_xml_id)

        _logger.warning(
            "southbrook: partner %s has channel=tradesperson but no "
            "tradesperson_tier set; falling back to base pricelist "
            "(cost+5%% floor, no tier discount).",
            partner.display_name,
        )
        return self.env.ref("southbrook_estimating.pricelist_tradesperson")

    # Default-getter — on new sale.order, auto-resolve from partner
    # without preventing the user from overriding pricelist_id manually.
    @api.onchange("partner_id")
    def _onchange_partner_id_southbrook_pricelist(self):
        for order in self:
            if not order.partner_id:
                continue
            resolved = order._resolve_channel_pricelist(order.partner_id)
            if resolved:
                order.pricelist_id = resolved.id

    # ------------------------------------------------------------------
    # Analytics capture (NF1 — Build Spec section 8 "AI data spine")
    # ------------------------------------------------------------------
    # Fire the southbrook.order.analytics.capture() hook at confirm-time.
    # Idempotent; safe to re-confirm. NF1 carve-out: this is data capture,
    # not business logic — does not bump the 7-routine custom register.
    def action_confirm(self):
        result = super().action_confirm()
        Analytics = self.env["southbrook.order.analytics"]
        for order in self:
            Analytics.capture(order)
        return result

    # ------------------------------------------------------------------
    # NF6 — Image Floor iterative-design pattern (Case Study section 3.A)
    # ------------------------------------------------------------------
    # parent_order_id + version + action_duplicate_as_draft give reps
    # the "Duplicate as Draft" affordance that Image Floor's 3-visit flow
    # needs: same kitchen revised 3 times, each saved as a new draft with
    # the prior version linked. Free side-effect: full revision history
    # walkable via parent_order_id chain.
    #
    # Schema only. The view button + action wiring lands in
    # views/sale_order_views.xml.
    parent_order_id = fields.Many2one(
        "sale.order",
        string="Parent Order (Duplicated From)",
        ondelete="set null",
        copy=False,
        help=(
            "When this order was created via 'Duplicate as Draft', this "
            "Many2one points at the prior version. NF6 — Image Floor "
            "iterative-design pattern."
        ),
    )
    version = fields.Integer(
        string="Version",
        default=1,
        copy=False,
        help=(
            "Auto-incremented by action_duplicate_as_draft. The Image "
            "Floor flow typically reaches v3 before final confirmation."
        ),
    )

    # ------------------------------------------------------------------
    # 3D kitchen-run viewport — Track 1 commit 6 (2026-05-30).
    #
    # Returns a multi-cabinet 3D payload spanning every order_line whose
    # product matches one of the 12 Q8-locked SB cabinet SKUs. Cabinets
    # are laid out left-to-right along the X axis in line order; the
    # zone field (Q21) determines each line's Y floor — wall cabinets
    # float at 1400 mm above the floor, everything else sits at y=0.
    #
    # The same _SKU_DEFAULTS / _cut_list_to_3d_payload pipeline that
    # drives the single-cabinet wizard viewport also drives this one,
    # so a change to the named geometric constants (BOX_TH, BACK_TH,
    # DOOR_TH, TOEKICK_H) propagates to BOTH views — no fork.
    # ------------------------------------------------------------------
    _ZONE_FLOOR_Y = {
        "base_run": 0,
        "wall":     1400,    # wall mount height above counter
        "tall":     0,       # full-height cabinets on floor
        "island":   0,
        "accessory": 0,
        "other":    0,
    }

    def get_kitchen_3d_payload(self):
        """Multi-cabinet 3D payload for the OWL kitchen viewport.

        Loop over self.order_line in display order. For each line whose
        product matches an SB-* SKU, compute its single-cabinet panels at
        the origin (via the existing config_session pipeline), then
        translate every panel by (x_offset, y_floor, 0):
          • x_offset accumulates as cabinets are placed — cumulative
            X grows by the cabinet's width per placement.
          • y_floor comes from _ZONE_FLOOR_Y[line.zone].

        Concatenates all per-cabinet panels into one list with prefixed
        names so the OWL component can address each line's panels
        independently in future highlight-on-hover work.

        Returns the same payload shape as
        product.config.session.get_3d_payload — the OWL component
        consumes it without per-payload code paths.
        """
        self.ensure_one()
        Session = self.env["product.config.session"]
        Bom = self.env["mrp.bom"]
        sku_defaults = Session._SKU_DEFAULTS

        cumulative_x = 0      # mm — X position of next cabinet's left edge
        max_h = 0             # tallest cabinet's top, for camera framing
        max_d = 0             # deepest cabinet, for camera framing
        all_panels = []

        for line in self.order_line:
            tmpl = line.product_id.product_tmpl_id if line.product_id else None
            sku = tmpl.default_code if tmpl else None
            row = sku_defaults.get(sku) if sku else None
            if not row:
                continue   # non-southbrook product → skip; only SB SKUs render

            fam, doors, drawers, w, h, d = row
            y_floor = self._ZONE_FLOOR_Y.get(line.zone or "base_run", 0)

            cab_inputs = {
                "width_mm":   w,
                "height_mm":  h,
                "depth_mm":   d,
                "family":     fam,
                "door_count": doors,
                "drawer_count": drawers,
                "finished_sides": "none",
            }
            cut = Bom._compute_panel_dimensions(
                width_mm=w, height_mm=h, depth_mm=d,
                family=fam, door_count=doors, drawer_count=drawers,
                finished_sides="none",
            )
            single = Session._cut_list_to_3d_payload(cab_inputs, cut)

            x_offset = cumulative_x + w / 2
            line_tag = f"L{line.id}_"
            for panel in single["panels"]:
                p = dict(panel)
                p["pos"] = {
                    "x": panel["pos"]["x"] + x_offset,
                    "y": panel["pos"]["y"] + y_floor,
                    "z": panel["pos"]["z"],
                }
                p["name"] = line_tag + panel["name"]
                all_panels.append(p)

            cumulative_x += w
            cabinet_top = (h if fam != "worktop" else 25) + y_floor
            max_h = max(max_h, cabinet_top)
            max_d = max(max_d, d)

        # Frame the camera around the full kitchen run.
        if cumulative_x == 0:
            # No SB cabinets on this order — return an empty scene with
            # a sane default camera so the viewport still renders the
            # floor and shadow without errors.
            return {
                "panels": [],
                "metadata": {
                    "line_count": 0,
                    "kitchen_width_mm": 0,
                    "kitchen_height_mm": 0,
                    "kitchen_depth_mm": 0,
                },
                "camera": {
                    "target":   [0, 400, 0],
                    "position": [2500, 1800, 3500],
                },
                "bounds": {"min": [-500, 0, -500], "max": [500, 800, 0]},
            }

        kitchen_w = cumulative_x
        cam_target = [kitchen_w / 2, max_h / 2, -max_d / 2]
        # Camera distance scales with kitchen footprint so wide runs
        # still frame cleanly without manual zoom.
        cam_dist = max(kitchen_w, max_h, max_d) * 1.8
        cam_position = [kitchen_w / 2, max_h * 1.4, cam_dist]

        return {
            "panels": all_panels,
            "metadata": {
                "line_count": len([
                    l for l in self.order_line
                    if l.product_id
                    and l.product_id.product_tmpl_id.default_code
                    in sku_defaults
                ]),
                "kitchen_width_mm":  kitchen_w,
                "kitchen_height_mm": max_h,
                "kitchen_depth_mm":  max_d,
            },
            "camera": {"target": cam_target, "position": cam_position},
            "bounds": {
                "min": [0, 0, -max_d],
                "max": [kitchen_w, max_h, 0],
            },
        }

    def action_duplicate_as_draft(self):
        """Create a new draft sale.order copied from this one (NF6).

        Copies all order lines (preserving product.config.session refs
        where applicable), links parent_order_id, increments version,
        stays in draft state ('draft' / 'sent'). Safe to chain — v3
        duplicates v2 which duplicates v1.

        Returns the action descriptor that opens the new order's form.
        """
        self.ensure_one()
        new_order = self.copy({
            "parent_order_id": self.id,
            "version": self.version + 1,
            "state": "draft",
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "res_id": new_order.id,
            "view_mode": "form",
            "target": "current",
            "name": f"{new_order.name} (v{new_order.version})",
        }
