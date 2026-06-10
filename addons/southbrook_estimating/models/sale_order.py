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

    # G14 + G17 (customer-flow JTBD gap 2026-06-01) — customer-visible
    # progress timeline. Stamped by the portal 'Request a Price' action
    # so the StagePipeline can show 'Submitted on <date>' instead of
    # an undated chip. Phase 3 polish adds southbrook_in_production_date
    # populated by the MO-creation hook.
    southbrook_submitted_date = fields.Datetime(
        string="Submitted for Pricing",
        readonly=True,
        copy=False,
        tracking=True,
        help=(
            "Set automatically the first time the customer (or sales "
            "rep on the customer's behalf) submits a draft order for "
            "pricing review via the portal 'Request a Price' action."
        ),
    )

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
    # 3D kitchen-run viewport — Track 1 commits 6 + 7 (2026-05-30).
    #
    # Returns a multi-cabinet 3D payload spanning every order_line whose
    # product matches one of the 12 Q8-locked SB cabinet SKUs.
    #
    # Track 1 commit 7 layout — zone-aware X positioning:
    #
    #   Real kitchen elevation looks like:
    #
    #       [W1][W2][W3]                    ← wall cabs at Y=1400mm
    #       [B1][B2][B3] [T1]               ← base + tall at Y=0mm
    #                          [WT1]        ← worktop at Y=762mm
    #                                       ← island at Z=-2500mm
    #
    #   Each zone gets its OWN cumulative X cursor so wall cabinets
    #   share the X range with the base cabinets they sit above
    #   (visually aligned in elevation), while tall extends the ground
    #   cursor (continues the run to the right), and island/other use
    #   distinct Z offsets so they don't collide visually with the
    #   main run.
    #
    # The same _SKU_DEFAULTS / _cut_list_to_3d_payload pipeline that
    # drives the single-cabinet wizard viewport also drives this one,
    # so a change to the named geometric constants (BOX_TH, BACK_TH,
    # DOOR_TH, TOEKICK_H) propagates to BOTH views — no fork.
    # ------------------------------------------------------------------
    # Zone → (cursor_name, y_floor_mm, z_offset_mm). Zones sharing a
    # cursor_name accumulate along the same X axis.
    _ZONE_LAYOUT = {
        # GROUND cursor: base + tall + accessory continue the floor run
        # left to right. Wall cabinets get their own cursor so they
        # share the X range with their base partners, not extending
        # past them.
        "base_run":  ("ground", 0,    0),
        "wall":      ("wall",   1400, 0),       # wall mount height
        "tall":      ("ground", 0,    0),       # extends ground run
        "island":    ("island", 0,    -2500),   # separate Z plane
        "accessory": ("ground", 0,    0),
        "other":     ("other",  0,    -3000),   # tucked away
    }
    # Worktop family override — countertop sits at Y=762mm regardless
    # of zone. T1C7 dispatches by FAMILY for worktops; the zone field
    # is still respected for everything else.
    _WORKTOP_Y_FLOOR = 762
    _WORKTOP_CURSOR = "ground"

    # Legacy alias for T1C6 callers (just zone → y_floor). Kept for
    # backwards-compat with any test that grew up against commit 6.
    _ZONE_FLOOR_Y = {z: l[1] for z, l in _ZONE_LAYOUT.items()}

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

        # Per-zone X cursors — T1C7. Each cursor accumulates the
        # cabinet widths placed under it. Zones in _ZONE_LAYOUT
        # share a cursor name when they belong on the same horizontal
        # axis (e.g. base_run, tall, accessory all advance "ground").
        cursors = {"ground": 0, "wall": 0, "island": 0, "other": 0}
        max_h = 0             # tallest cabinet's top, for camera framing
        max_d = 0             # deepest cabinet, for camera framing
        max_z_back = 0        # most negative Z reached (for camera + bounds)
        all_panels = []
        # T1C8 — per-line index for hover tooltip in the OWL component.
        # The frontend reads this map by line.id (extracted from panel
        # name prefix "L{id}_") to display "Line N · Family · SKU"
        # in the toolbar while the mouse is over a cabinet.
        lines_index = {}
        sequence = 0

        for line in self.order_line:
            tmpl = line.product_id.product_tmpl_id if line.product_id else None
            sku = tmpl.default_code if tmpl else None
            row = sku_defaults.get(sku) if sku else None
            if not row:
                continue   # non-southbrook product → skip; only SB SKUs render

            fam, doors, drawers, w, h, d = row

            # T1C7 dispatch: worktops sit on the counter (Y=762) and
            # share the ground X cursor regardless of zone. Everything
            # else dispatches by zone via _ZONE_LAYOUT.
            if fam == "worktop":
                cursor_name = self._WORKTOP_CURSOR
                y_floor = self._WORKTOP_Y_FLOOR
                z_offset = 0
            else:
                zone = line.zone or "base_run"
                cursor_name, y_floor, z_offset = self._ZONE_LAYOUT.get(
                    zone, ("ground", 0, 0),
                )

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

            x_offset = cursors[cursor_name] + w / 2
            line_tag = f"L{line.id}_"
            for panel in single["panels"]:
                p = dict(panel)
                p["pos"] = {
                    "x": panel["pos"]["x"] + x_offset,
                    "y": panel["pos"]["y"] + y_floor,
                    "z": panel["pos"]["z"] + z_offset,
                }
                p["name"] = line_tag + panel["name"]
                all_panels.append(p)

            cursors[cursor_name] += w
            cabinet_top = (h if fam != "worktop" else 25) + y_floor
            max_h = max(max_h, cabinet_top)
            max_d = max(max_d, d)
            # Z bounds — most-negative z (back of farthest cabinet) used
            # for camera framing + scene bounds.
            cabinet_back_z = z_offset - d
            if cabinet_back_z < max_z_back:
                max_z_back = cabinet_back_z

            # T1C8 — line index entry.
            sequence += 1
            lines_index[str(line.id)] = {
                "id": line.id,
                "sequence": sequence,
                "sku": sku or "",
                "family": fam,
                "zone": line.zone or "base_run",
                "width_mm": w,
                "height_mm": h,
                "depth_mm": d,
                "product_name": (
                    tmpl.display_name if tmpl else ""
                ),
            }

        # Widest cursor determines the camera framing width.
        widest = max(cursors.values())
        cumulative_x = widest

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
        # Z extent — from the farthest-back cabinet (negative Z) to
        # the front of the deepest cabinet at the main row (~0).
        scene_z_back = max_z_back - max_d
        scene_z_front = 0
        scene_z_centre = (scene_z_back + scene_z_front) / 2

        cam_target = [kitchen_w / 2, max_h / 2, scene_z_centre]
        # Camera distance scales with kitchen footprint so wide runs
        # still frame cleanly without manual zoom.
        cam_dist = max(kitchen_w, max_h, abs(scene_z_back)) * 1.8
        cam_position = [
            kitchen_w / 2,
            max_h * 1.4,
            scene_z_front + cam_dist,
        ]

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
                "cursors": dict(cursors),  # diagnostic: per-zone X totals
                "lines": lines_index,      # T1C8 — per-line lookup for hover
            },
            "camera": {"target": cam_target, "position": cam_position},
            "bounds": {
                "min": [0, 0, scene_z_back],
                "max": [kitchen_w, max_h, scene_z_front],
            },
        }

    # ------------------------------------------------------------------
    # Phase 3 Sprint C3 — version-history chain walker.
    # ------------------------------------------------------------------
    def _southbrook_history_chain(self, max_depth=20):
        """Walk parent_order_id backwards and return the ancestry.

        Returns a list of dicts (newest first) covering EVERY order in
        the chain — including self. Caller renders it as a timeline.

        max_depth guards against pathological cycles; 20 is enough for
        any plausible iterative-design workflow (Image Floor's typical
        v3 is the high-water mark in observed practice).
        """
        self.ensure_one()
        chain = []
        seen = set()
        cur = self
        while cur and cur.id not in seen and len(chain) < max_depth:
            seen.add(cur.id)
            chain.append({
                "id": cur.id,
                "name": cur.name,
                "version": int(cur.version or 1),
                "state": cur.state,
                "amount_total": float(cur.amount_total or 0.0),
                "date_order": (
                    cur.date_order.isoformat() if cur.date_order else None
                ),
                "is_current": cur.id == self.id,
            })
            cur = cur.parent_order_id
        return chain

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
