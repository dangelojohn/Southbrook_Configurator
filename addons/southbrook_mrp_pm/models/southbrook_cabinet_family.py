# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.cabinet.family — M11 PM KPI by cabinet family.

M11 (Manufacturing PM JTBD 2026-06-01): the M10 dashboard answers
'how busy is each station'. M11 adds the orthogonal cut: 'how many
of each cabinet type are flowing through right now'. PM walks the
shop floor and asks 'how are we doing on bases today?' — this
model + its kanban view answers that.

Family list pulled from the canonical 12-cabinet taxonomy
(southbrook_estimating + the Q8 charter):

    base       SB-BASE-1DR + SB-BASE-2DR + SB-SINK-BASE
    wall       SB-WALL-1DR + SB-WALL-2DR
    tall       SB-TALL-PANTRY + SB-TALL-OVEN
    drawer     SB-DRAWER
    sink       (overlap with base — kept distinct because the
                sink-cutout adds floor-level routing variance)
    corner     SB-CORNER
    vanity     SB-VANITY
    accessory  SB-ACCESSORY
    worktop    SB-WORKTOP

Compute fields read from mrp.production grouped by product family
via product.template.default_code prefix matching — same lookup
the customer-flow controller uses for catalog display.
"""
from datetime import datetime, time

from odoo import _, api, fields, models


_IN_FLIGHT_MO_STATES = ("draft", "confirmed", "progress", "to_close")

# SKU prefix → family code. Mirrors
# SouthbrookKitchenPlanner._FAMILY_BY_PREFIX in
# southbrook_estimating_website/controllers/main.py. The two
# should drift together if a new cabinet family ships.
_FAMILY_BY_PREFIX = {
    "SB-WALL":      "wall",
    "SB-BASE":      "base",
    "SB-DRAWER":    "drawer",
    "SB-SINK":      "sink",
    "SB-TALL":      "tall",
    "SB-CORNER":    "corner",
    "SB-VANITY":    "vanity",
    "SB-ACCESSORY": "accessory",
    "SB-WORKTOP":   "worktop",
}


class SouthbrookCabinetFamily(models.Model):
    _name = "southbrook.cabinet.family"
    _description = "Southbrook cabinet family — PM throughput KPI"
    _order = "sequence, code"

    name = fields.Char(string="Name", required=True)
    code = fields.Char(string="Code", required=True, index=True)
    sequence = fields.Integer(string="Sequence", default=10)

    inflight_count = fields.Integer(
        string="In Flight",
        compute="_compute_family_kpis",
        help=(
            "Manufacturing orders currently in flight whose product "
            "default_code matches this family's SKU prefix."
        ),
    )

    throughput_today = fields.Integer(
        string="Done Today",
        compute="_compute_family_kpis",
        help=(
            "Manufacturing orders of this family finished since "
            "midnight today."
        ),
    )

    late_count = fields.Integer(
        string="Late",
        compute="_compute_family_kpis",
    )

    @api.depends_context("uid")
    def _compute_family_kpis(self):
        Mo = self.env["mrp.production"].sudo()
        today_start = fields.Datetime.to_string(
            datetime.combine(fields.Date.context_today(self), time.min)
        )
        now = fields.Datetime.now()

        # Reverse lookup: family code → SKU prefix.
        prefixes_by_family = {}
        for prefix, family in _FAMILY_BY_PREFIX.items():
            prefixes_by_family.setdefault(family, []).append(prefix)

        for fam in self:
            prefixes = prefixes_by_family.get(fam.code, [])
            if not prefixes:
                fam.inflight_count = 0
                fam.throughput_today = 0
                fam.late_count = 0
                continue
            # MO's product.product.default_code is the canonical
            # SKU. Several prefixes might map to the same family
            # (e.g. 'SB-SINK' is also a base cabinet) — match any.
            # The domain becomes ('product_id.default_code',
            # 'like', 'SB-WALL%') OR ('...', 'like', 'SB-BASE%')...
            inflight_domain = [("state", "in", list(_IN_FLIGHT_MO_STATES))]
            done_domain = [
                ("state", "=", "done"),
                ("date_finished", ">=", today_start),
            ]
            late_domain = [
                ("state", "not in", ["done", "cancel"]),
                ("date_deadline", "<", now),
            ]
            prefix_clause = []
            for prefix in prefixes:
                prefix_clause.append(
                    ("product_id.default_code", "=like", prefix + "%")
                )
            # Build OR-domain from prefix_clause list.
            or_domain = []
            if len(prefix_clause) > 1:
                or_domain = ["|"] * (len(prefix_clause) - 1) + prefix_clause
            elif prefix_clause:
                or_domain = prefix_clause

            fam.inflight_count = Mo.search_count(inflight_domain + or_domain)
            fam.throughput_today = Mo.search_count(done_domain + or_domain)
            fam.late_count = Mo.search_count(late_domain + or_domain)
