# SPDX-License-Identifier: LGPL-3.0-only
"""W066 (R3.9, 2026-06-27) — Subcontract Decision Wizard.

JTBD
----
"When I see workcenter X is at 120% capacity this week, I want a
one-click flow that diverts THIS MO's affected operation to a
qualified subcontractor — not a 6-form manual setup."

Today
-----
- Native Odoo 19 has `mrp_subcontracting` (BOM type = subcontract)
  but that's a static, per-template route — not a per-MO planner
  decision.
- `pg.vendor` (W031 / Phase 2) carries qualified vendors with
  categories.
- `southbrook.capacity.day` (W067) carries calendar-aware capacity
  per (WC × day).
- `pg.rfq.source_type = 'subcontract'` (W078) is the AVL-fed route
  for subcontract sourcing decisions.

What was missing: the PLANNER-FACING wizard that fuses these three
into a 3-click "this WO is over-capacity, here's a qualified vendor,
file the subcontract RFQ" flow.

This wizard owns nothing — it READS capacity, READS qualified
vendors, and WRITES a `pg.rfq` with `source_type='subcontract'`.
The canonical BOM routing is NEVER mutated; the divert is per-MO
only and is fully reversible (the planner can cancel the RFQ and
leave the WO on its original workcenter).

Constraints honoured
--------------------
- No raw SQL — pure ORM.
- Uses W067 + W078 data — does NOT duplicate either.
- Does NOT modify the canonical BOM routing — per-MO transient.
- Restricted to mrp planners (`mrp.group_mrp_user`).
- W035 employee context propagated via env.user / message_post.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


# Capacity threshold above which a wizard launch is "auto-justified"
# (the planner can still divert below the threshold — they just have
# to do it deliberately via the menu rather than from a contextual
# capacity-overflow warning).
OVERCAPACITY_PCT = 100.0


class SouthbrookSubcontractDecisionWizard(models.TransientModel):
    _name = "southbrook.subcontract.decision.wizard"
    _description = (
        "Subcontract Decision Wizard — divert MO operation to a "
        "qualified vendor (W066)"
    )

    # ------------------------------------------------------------------
    # Source WO + auto-derived context
    # ------------------------------------------------------------------
    workorder_id = fields.Many2one(
        "mrp.workorder",
        string="Work Order",
        required=True,
        ondelete="cascade",
    )
    production_id = fields.Many2one(
        "mrp.production",
        related="workorder_id.production_id",
        readonly=True,
        store=False,
    )
    workcenter_id = fields.Many2one(
        "mrp.workcenter",
        related="workorder_id.workcenter_id",
        readonly=True,
        store=False,
    )
    operation_id = fields.Many2one(
        "mrp.routing.workcenter",
        related="workorder_id.operation_id",
        readonly=True,
        store=False,
    )
    product_id = fields.Many2one(
        "product.product",
        related="workorder_id.product_id",
        readonly=True,
        store=False,
    )
    # Planned date used to pull the right capacity row. Defaults to
    # the WO date_start day; planner can override (e.g. when the WO
    # has not been scheduled yet).
    planned_date = fields.Date(
        string="Planned Date",
        required=True,
        help="The day whose capacity we evaluate. Defaults to the "
             "WO's planned start date; override to look at a "
             "different day's load.",
    )

    # ------------------------------------------------------------------
    # Capacity context (read-only — from W067)
    # ------------------------------------------------------------------
    capacity_day_id = fields.Many2one(
        "southbrook.capacity.day",
        compute="_compute_capacity",
        string="Capacity Row",
        help="Underlying W067 row for the (workcenter × planned_date) "
             "pair. Read-only — refresh via the W067 cron / server "
             "action if stale.",
    )
    current_utilization_pct = fields.Float(
        compute="_compute_capacity",
        string="Utilization %",
        help="From southbrook.capacity.day for the WO's workcenter + "
             "planned date. >100% = the case the planner is here to "
             "solve.",
    )
    capacity_warning = fields.Char(
        compute="_compute_capacity",
        string="Capacity Status",
    )

    # ------------------------------------------------------------------
    # Candidate vendors (read-only — from pg.vendor AVL)
    # ------------------------------------------------------------------
    candidate_vendor_ids = fields.Many2many(
        "pg.vendor",
        "sbk_subcontract_wiz_vendor_rel",
        "wizard_id", "vendor_id",
        compute="_compute_candidate_vendors",
        string="Qualified Vendors",
        help="Qualified pg.vendor records ranked for this divert. "
             "Filter: state='qualified' AND (has a pg.vendor.part "
             "for the MO's product item) OR (vendor has at least "
             "one category — looser fallback when the AVL is sparse).",
    )
    candidate_count = fields.Integer(
        compute="_compute_candidate_vendors",
        string="# Candidates",
    )

    selected_vendor_id = fields.Many2one(
        "pg.vendor",
        string="Subcontractor",
        # NOT required= at the field level: the wizard is opened empty (the
        # user picks the vendor after seeing the candidate list), so a NOT NULL
        # column makes create() fail before the form even renders. The
        # requirement is enforced where it belongs — action_confirm raises
        # "Pick a qualified subcontractor first." if it's unset.
        ondelete="restrict",
        help="The vendor to whom the operation is diverted. Must be "
             "in the qualified-candidates list (W031 AVL).",
    )

    # ------------------------------------------------------------------
    # Decision details
    # ------------------------------------------------------------------
    subcontract_qty = fields.Float(
        string="Quantity to Subcontract",
        default=1.0,
        required=True,
        help="How much of this MO to divert. Defaults to the WO's "
             "qty_production; planner can split (e.g. 6 of 10 to "
             "vendor, 4 in-house).",
    )
    requested_completion_date = fields.Date(
        string="Requested Completion",
        help="Date the planner needs the subcontracted work back. "
             "Becomes the RFQ due_date.",
    )
    notes = fields.Text(
        string="Planner Notes",
        help="Free-text rationale (e.g. 'CNC2 at 140% week of 6-30, "
             "Vendor Acme has bandwidth, MO ships Wed').",
    )

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        wo_id = (defaults.get("workorder_id")
                 or self.env.context.get("default_workorder_id")
                 or self.env.context.get("active_id"))
        if wo_id and self.env.context.get("active_model") in (
            "mrp.workorder", None, False,
        ):
            wo = self.env["mrp.workorder"].browse(wo_id).exists()
            if wo:
                defaults.setdefault("workorder_id", wo.id)
                # Planned date: WO.date_start → day; falls back to
                # production.date_start; finally today.
                day = None
                if wo.date_start:
                    day = wo.date_start.date()
                elif wo.production_id and wo.production_id.date_start:
                    day = wo.production_id.date_start.date()
                else:
                    day = fields.Date.context_today(self)
                defaults.setdefault("planned_date", day)
                # Default qty to the WO's qty_production so the
                # 100% case is the natural starting point.
                qty = getattr(wo, "qty_production", None) or 1.0
                defaults.setdefault("subcontract_qty", qty)
        return defaults

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("workorder_id", "workcenter_id", "planned_date")
    def _compute_capacity(self):
        CapacityDay = self.env["southbrook.capacity.day"]
        for wiz in self:
            row = CapacityDay.browse()
            pct = 0.0
            warning = _("No capacity data — refresh W067 cron.")
            if wiz.workcenter_id and wiz.planned_date:
                row = CapacityDay.search([
                    ("workcenter_id", "=", wiz.workcenter_id.id),
                    ("date", "=", wiz.planned_date),
                ], limit=1)
                if row:
                    pct = row.utilization_pct
                    if pct > OVERCAPACITY_PCT:
                        warning = _(
                            "OVERCAPACITY: %(wc)s at %(pct).0f%% on "
                            "%(d)s — divert recommended."
                        ) % {
                            "wc": wiz.workcenter_id.display_name,
                            "pct": pct,
                            "d": wiz.planned_date,
                        }
                    elif pct >= 80.0:
                        warning = _(
                            "Tight: %(wc)s at %(pct).0f%% — divert "
                            "optional."
                        ) % {
                            "wc": wiz.workcenter_id.display_name,
                            "pct": pct,
                        }
                    else:
                        warning = _(
                            "Headroom: %(wc)s at %(pct).0f%% — divert "
                            "is a deliberate sourcing decision, not a "
                            "capacity escape valve."
                        ) % {
                            "wc": wiz.workcenter_id.display_name,
                            "pct": pct,
                        }
            wiz.capacity_day_id = row.id if row else False
            wiz.current_utilization_pct = pct
            wiz.capacity_warning = warning

    @api.depends("workorder_id", "product_id")
    def _compute_candidate_vendors(self):
        """Rank candidate vendors for this WO's divert.

        Filter:
        - state == 'qualified' (hard gate per Phase 2 AVL).
        - Match path A: vendor has a pg.vendor.part whose item is the
          pg.item the MO's product/template resolves to (via the
          release back-reference shipped by product_graph_release).
        - Match path B (fallback): vendor has at least one
          pg.category set — used when the WO's product has no AVL
          entry yet but the vendor is otherwise qualified and
          categorised (we surface them with lower implied rank — the
          planner gets a non-empty list to act on rather than a dead
          end).
        """
        Vendor = self.env["pg.vendor"]
        for wiz in self:
            if not wiz.workorder_id:
                wiz.candidate_vendor_ids = Vendor.browse()
                wiz.candidate_count = 0
                continue

            # Resolve the pg.item the MO's product maps to (release
            # bridge). The mrp.production carries pg_root_item_id via
            # product_graph_release; safe-getattr keeps the wizard
            # functional even if the release link is missing.
            pg_item = self._resolve_pg_item(wiz.production_id)

            # Path A — strict AVL match.
            path_a_ids = set()
            if pg_item:
                parts = self.env["pg.vendor.part"].search([
                    ("item_id", "=", pg_item.id),
                    ("active", "=", True),
                ])
                # Vendor must also be qualified (relying on the
                # related is_qualified flag).
                path_a_ids = set(parts.filtered(
                    lambda p: p.vendor_id.state == "qualified"
                ).mapped("vendor_id.id"))

            # Path B — qualified vendors with at least one category.
            # Excludes vendors with no category at all so we don't
            # surface a "qualified but not categorised" vendor where
            # the planner has nothing to evaluate against.
            domain_b = [("state", "=", "qualified")]
            if "category_ids" in Vendor._fields:
                domain_b.append(("category_ids", "!=", False))
            path_b = Vendor.search(domain_b)
            path_b_ids = set(path_b.ids)

            # Path A wins when non-empty; otherwise Path B fallback.
            # We always union so a strict-AVL match still surfaces
            # other categorised qualified vendors as additional
            # options (planner may prefer a vendor with capacity
            # over a vendor who happens to be on the AVL).
            candidate_ids = sorted(path_a_ids | path_b_ids)
            wiz.candidate_vendor_ids = Vendor.browse(candidate_ids)
            wiz.candidate_count = len(candidate_ids)

    def _resolve_pg_item(self, production):
        """Return the pg.item for the MO's root product, or False.

        Safe across deployments where product_graph_release is not
        installed (the production_id won't have pg_root_item_id —
        we just return False and Path B handles it).
        """
        if not production:
            return False
        if "pg_root_item_id" not in production._fields:
            return False
        return production.pg_root_item_id or False

    # ------------------------------------------------------------------
    # Action
    # ------------------------------------------------------------------
    def action_confirm(self):
        """Create a subcontract pg.rfq for the diverted operation.

        Does NOT touch the canonical BOM routing. The WO stays on its
        original workcenter; the planner picks up the awarded
        purchase.requisition through the W078 → procurement bridge
        once the buyer awards the RFQ. If the divert is later
        abandoned (vendor declines, RFQ cancelled), the original WO
        plan is unaffected.
        """
        self.ensure_one()
        if not self.selected_vendor_id:
            raise UserError(_("Pick a qualified subcontractor first."))
        if self.selected_vendor_id not in self.candidate_vendor_ids:
            raise UserError(_(
                "%(v)s is not in the qualified-candidate list for "
                "this WO. Refresh the wizard or qualify the vendor "
                "first."
            ) % {"v": self.selected_vendor_id.display_name})
        if self.subcontract_qty <= 0.0:
            raise UserError(_("Subcontract quantity must be > 0."))

        pg_item = self._resolve_pg_item(self.production_id)

        rfq_vals = {
            "title": _("Subcontract — %(wo)s") % {
                "wo": self.workorder_id.display_name,
            },
            "source_type": "subcontract",
            "buyer_id": self.env.uid,
            "requestor_id": self.env.uid,
            "due_date": self.requested_completion_date,
            "reason": self._compose_reason(),
        }
        if pg_item:
            rfq_vals["item_id"] = pg_item.id

        Rfq = self.env["pg.rfq"]
        rfq = Rfq.create(rfq_vals)

        # Add a line if we have a pg.item — otherwise the RFQ header
        # carries the subcontract intent and the buyer fills line
        # detail at the procurement step. We never silently fabricate
        # a line against a wrong item.
        if pg_item:
            self.env["pg.rfq.line"].create({
                "rfq_id": rfq.id,
                "item_id": pg_item.id,
                "qty": self.subcontract_qty,
            })

        # Audit trail on both records (W035-style attribution flows
        # naturally via env.user — message_post stamps the author).
        body_wo = _(
            "Operation diverted to subcontractor "
            "<strong>%(v)s</strong> via W066 wizard.<br/>"
            "RFQ: <strong>%(rfq)s</strong><br/>"
            "Qty: %(qty)s<br/>"
            "Capacity at decision time: %(pct).1f%%<br/>"
            "Canonical BOM routing UNCHANGED — this is a per-MO "
            "divert via subcontract RFQ."
        ) % {
            "v": self.selected_vendor_id.display_name,
            "rfq": rfq.display_name,
            "qty": self.subcontract_qty,
            "pct": self.current_utilization_pct,
        }
        self.workorder_id.message_post(body=body_wo)
        if self.production_id:
            self.production_id.message_post(body=body_wo)

        body_vendor = _(
            "Subcontract RFQ %(rfq)s raised from over-capacity "
            "divert on WO %(wo)s (workcenter %(wc)s at %(pct).1f%%)."
        ) % {
            "rfq": rfq.display_name,
            "wo": self.workorder_id.display_name,
            "wc": (self.workcenter_id.display_name
                   if self.workcenter_id else _("(unset)")),
            "pct": self.current_utilization_pct,
        }
        # Vendor side audit — only post if the vendor model carries
        # mail.thread (Phase 2 vendors do).
        if "message_post" in dir(self.selected_vendor_id):
            try:
                self.selected_vendor_id.message_post(body=body_vendor)
            except Exception:
                # Don't break the divert if vendor chatter is
                # mis-configured; the WO+MO audit trail is the
                # primary record.
                _logger.warning(
                    "W066: failed to post chatter on vendor %s",
                    self.selected_vendor_id.id, exc_info=True,
                )

        return {
            "type": "ir.actions.act_window",
            "name": _("Subcontract RFQ"),
            "res_model": "pg.rfq",
            "res_id": rfq.id,
            "view_mode": "form",
            "target": "current",
        }

    def _compose_reason(self):
        """Build the reason text written onto the pg.rfq."""
        self.ensure_one()
        bits = [
            _("W066 — subcontract divert from over-capacity WO."),
            _("Source WO: %s") % self.workorder_id.display_name,
            _("Source MO: %s") % (
                self.production_id.display_name
                if self.production_id else _("(unset)")
            ),
            _("Workcenter: %s") % (
                self.workcenter_id.display_name
                if self.workcenter_id else _("(unset)")
            ),
            _("Utilization at decision: %.1f%%") % (
                self.current_utilization_pct
            ),
            _("Qty: %s") % self.subcontract_qty,
        ]
        if self.notes:
            bits.append(_("Notes: %s") % self.notes)
        return "\n".join(bits)


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    def action_sbk_subcontract_decision_wizard(self):
        """Button on the WO form opens the W066 wizard pre-bound to
        this WO."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Divert to Subcontractor"),
            "res_model": "southbrook.subcontract.decision.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_workorder_id": self.id,
                "active_id": self.id,
                "active_model": "mrp.workorder",
            },
        }
