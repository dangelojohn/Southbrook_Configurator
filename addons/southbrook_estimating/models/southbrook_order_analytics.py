# SPDX-License-Identifier: LGPL-3.0-only
"""
southbrook.order.analytics — the AI data spine companion model per
Build Spec section 8.

NF1 carve-out: this file does NOT count against the 7-routine custom
register in Build Spec section 4. The register lists business-logic
files (custom math, custom dispatch, custom external integration).
southbrook.order.analytics is a thin record schema + a rollup-from-
existing-fields capture hook. There is no decision-making, no business
rule, no math beyond Counter.most_common(). If this model ever grows
methods that compute anything beyond rollup-from-existing-fields,
that's the signal to revisit the boundary.

Capture hook lives in sale_order.py (modified in this commit, not here).
"""
from collections import Counter

from odoo import api, fields, models


class SouthbrookOrderAnalytics(models.Model):
    _name = "southbrook.order.analytics"
    _description = "Southbrook Order Analytics (AI data spine companion)"
    _rec_name = "sale_order_id"

    # 1:1 relation to sale.order
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Sale Order",
        required=True,
        ondelete="cascade",
        index=True,
    )

    # Channel tags (Build Spec section 8 rows 1-4)
    channel = fields.Selection(
        related="sale_order_id.partner_id.channel",
        string="Channel",
        store=True,
        readonly=True,
    )
    series = fields.Char(
        string="Predominant Series",
        readonly=True,
    )
    tradesperson_tier = fields.Selection(
        related="sale_order_id.partner_id.tradesperson_tier",
        string="Tradesperson Tier",
        store=True,
        readonly=True,
    )
    dealer_id = fields.Many2one(
        "res.partner",
        string="Dealer",
        readonly=True,
    )

    # Lifecycle timestamps
    quoted_at = fields.Datetime(
        related="sale_order_id.create_date",
        string="Quoted At",
        store=True,
        readonly=True,
    )
    confirmed_at = fields.Datetime(string="Confirmed At", readonly=True)
    production_start_at = fields.Datetime(string="Production Start", readonly=True)
    production_end_at = fields.Datetime(string="Production End", readonly=True)

    # BoM rollup counts
    cabinet_count = fields.Integer(string="Cabinet Count", readonly=True)
    panel_count = fields.Integer(string="Panel Count", readonly=True)
    door_count = fields.Integer(string="Door Count", readonly=True)

    # Phase 4 nest yield
    nest_yield_pct = fields.Float(
        string="Nest Yield (%)",
        digits=(5, 2),
        readonly=True,
        help=(
            "Set by the Accucutt bridge in Phase 4. Null until Phase 4 lands."
        ),
    )

    # ------------------------------------------------------------------
    # Capture (idempotent)
    # ------------------------------------------------------------------
    @api.model
    def capture(self, sale_order):
        """Create or refresh the analytics row for a confirmed sale order.

        Idempotent — re-running on the same sale_order updates the existing
        row rather than creating a duplicate.

        Args:
            sale_order: a sale.order record (singleton).

        Returns:
            The southbrook.order.analytics record (existing or new).
        """
        existing = self.search(
            [("sale_order_id", "=", sale_order.id)], limit=1
        )
        vals = self._rollup_vals(sale_order)
        if existing:
            existing.write(vals)
            return existing
        return self.create({"sale_order_id": sale_order.id, **vals})

    def _rollup_vals(self, sale_order):
        """Compute the analytic field values from a sale order.

        Pure data movement — reads existing fields, writes them to the
        analytics row. No new business rules.
        """
        series_counts = Counter()
        cabinet_count = 0
        panel_count = 0
        door_count = 0
        for line in sale_order.order_line:
            if not line.product_id:
                continue
            # Series rollup: read from the variant's Series attribute value.
            series_val = line.product_id.product_template_attribute_value_ids.filtered(
                lambda v: v.attribute_id.name == "Series"
            )
            if series_val:
                # [:1] slice is defensive against a future case where a
                # variant might carry multiple Series attribute values.
                # Q2 locks Series as single-value per cabinet, so today
                # this slice picks the only element. Belt-and-suspenders.
                series_counts[series_val[:1].name] += 1
            cabinet_count += int(line.product_uom_qty)
            # Panel + door counts pull from the BoM rollup. Stub for commit
            # 6 — real numbers land when commit 8 ships _compute_panel_dimensions.
            # TODO(phase-3-sprint-b): wire to mrp.bom._compute_panel_dimensions
            # so the gate-walk D4 column shows real panel counts. Today this
            # returns 0 for every line because demo variants are created bare
            # (no product.config.session), so the W×H×D + family + door_count
            # the rollup needs aren't on the variant. Two paths considered:
            #   (a) re-seed demos through a real configurator session
            #   (b) live-compute from line.name + default dims when no session
            # See docs/PHASE_3_PLAN.md Sprint B for the decision matrix.
        return {
            "series": (series_counts.most_common(1)[0][0]
                       if series_counts else False),
            "dealer_id": (sale_order.partner_id.id
                          if sale_order.partner_id.channel == "dealer"
                          else False),
            "confirmed_at": sale_order.date_order,
            "cabinet_count": cabinet_count,
            "panel_count": panel_count,
            "door_count": door_count,
        }
