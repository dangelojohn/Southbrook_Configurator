# SPDX-License-Identifier: LGPL-3.0-only
"""``southbrook.command.exception`` — Central Command's one new model.

Implements Deliverable 2 (DELIVERABLE_2_DATA_MODEL.md) field-for-field.

Design invariants this file must never violate (see Deliverable 2 §"Why no
``@api.depends``..." and the repo-wide Odoo 19 CE traps this deployment has
hit before):

* ``severity`` / ``severity_rank`` / ``impact_summary`` / ``recommended_action``
  / ``why_text`` are written IMPERATIVELY by a sync/materializer method
  (out of scope for this file — see the class docstring below), never by
  ``@api.depends`` against a foreign model. A wrong field name in
  ``@api.depends`` silently breaks the whole registry on this deployment.
* ``source_record`` is ``store=False`` and MUST NEVER be referenced in a view
  domain (Odoo 19 rejects non-stored computed fields used in domains — this
  is enforced by convention/review here, not by the ORM).
* The uniqueness rule uses ``models.Constraint`` (NOT the legacy
  ``_sql_constraints``, which Odoo 19 silently ignores).
* ``res.users`` access elsewhere in this addon uses ``group_ids``, never the
  removed ``groups_id`` name (N/A directly to this model, called out here
  per the frozen-contract instructions).

Scope note: this file implements the schema + the exception's own workflow
(``action_acknowledge`` / ``action_resolve`` / ``action_dismiss``) only. The
``_sync_from_source()`` materializer described in Deliverable 2 §2 (which
reads the seven heterogeneous source models and writes the imperative
fields) is deliberately NOT implemented here — it is a separate, larger
surface explicitly out of this file's scope. ``SEVERITY_HARMONIZATION`` below
is provided as a documented starting point for whoever implements that
method next, so the mapping table doesn't have to be re-derived.
"""
from odoo import _, api, fields, models


# Per-source severity vocabularies harmonized onto this model's own
# low/medium/high/critical scale (Deliverable 2 §2, `severity` row).
# Not consumed anywhere in this file — provided for the future
# `_sync_from_source()` implementation so the three source vocabularies
# (verified: southbrook.mi.check.severity, southbrook.cmms.breakdown_alert
# .severity, southbrook.ncr.severity are three distinct Selection value
# sets) are harmonized identically wherever that method is written.
SEVERITY_HARMONIZATION = {
    # southbrook.mi.check.severity -> (severity, severity_rank)
    "mi_check": {
        "info": ("low", 3),
        "warning": ("medium", 2),
        "blocker": ("critical", 0),
    },
    # southbrook.cmms.breakdown_alert.severity -> passthrough (same vocabulary)
    "breakdown_alert": {
        "low": ("low", 3),
        "medium": ("medium", 2),
        "high": ("high", 1),
        "critical": ("critical", 0),
    },
    # southbrook.ncr.severity -> minor/major/critical
    "ncr": {
        "minor": ("low", 3),
        "major": ("medium", 2),
        "critical": ("critical", 0),
    },
}


class SouthbrookCommandException(models.Model):
    _name = "southbrook.command.exception"
    _description = "Central Command — accountable exception aggregation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "severity_rank desc, create_date desc"

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    name = fields.Char(
        default=lambda self: _("New"),
        copy=False,
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Taxonomy / source pointer
    # ------------------------------------------------------------------
    exception_type = fields.Selection(
        [
            ("mi_blocker", "MI Blocker"),
            ("breakdown_alert", "Breakdown Alert"),
            ("quality_ncr", "Quality NCR"),
            ("job_blocked", "Job Blocked"),
            ("approval_gate_stall", "Approval Gate Stall"),
            ("bom_skip", "BoM Skip"),
            ("cutlist_divergence", "Cutlist Divergence"),
            ("po_delivery_risk", "PO Delivery Risk"),
        ],
        required=True,
        index=True,
        tracking=True,
    )
    source_model = fields.Char(required=True, index=True)
    source_res_id = fields.Integer(required=True, index=True)

    # NEW: convenience accessor only. depends() is intra-model (source_model,
    # source_res_id both live on THIS record) — never a cross-model depends,
    # so this cannot hit the "wrong field name silently breaks registry" trap
    # described in Deliverable 2. store=False by design; NEVER reference this
    # field inside a <field name="domain">.
    source_record = fields.Reference(
        selection=[
            ("mrp.production", "Manufacturing Order"),
            ("project.task", "Job / Task"),
            ("sale.order", "Sales Order"),
            ("purchase.order", "Purchase Order"),
            ("southbrook.mi.check", "MI Check"),
            ("southbrook.cmms.breakdown_alert", "Breakdown Alert"),
            ("southbrook.ncr", "NCR"),
        ],
        compute="_compute_source_record",
        store=False,
    )

    @api.depends("source_model", "source_res_id")
    def _compute_source_record(self):
        for rec in self:
            if rec.source_model and rec.source_res_id:
                rec.source_record = f"{rec.source_model},{rec.source_res_id}"
            else:
                rec.source_record = False

    # ------------------------------------------------------------------
    # Reference-only FKs — pure pointers, no source field values copied
    # ------------------------------------------------------------------
    mo_id = fields.Many2one("mrp.production", string="Manufacturing Order")
    task_id = fields.Many2one("project.task", string="Job")
    sale_order_id = fields.Many2one("sale.order", string="Sales Order")
    purchase_order_id = fields.Many2one("purchase.order", string="Purchase Order")
    workcenter_id = fields.Many2one("mrp.workcenter", string="Workcenter")

    # ------------------------------------------------------------------
    # Harmonized severity — written imperatively by the (not-yet-implemented
    # here) sync method, never by @api.depends against a foreign model.
    # ------------------------------------------------------------------
    severity = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        required=True,
        default="low",
        tracking=True,
    )
    severity_rank = fields.Integer(
        default=3,
        index=True,
        help="Lower = more severe (0=critical .. 3=low), matching the "
             "existing southbrook.mi.check.severity_rank convention. "
             "Written imperatively alongside `severity`.",
    )

    # ------------------------------------------------------------------
    # Ownership / workflow
    # ------------------------------------------------------------------
    # NOTE (OQ-8, DELIVERABLE_8_OPEN_QUESTIONS.md): Deliverable 2 declares
    # this field `required`, but OQ-8 is an OPEN, owner-level policy
    # question about whether a source with no natural responsible user
    # (e.g. southbrook.cmms.breakdown_alert) should route to a role-queue
    # placeholder user or be left null pending manual triage — which is in
    # tension with `required=True`. This file implements the field EXACTLY
    # as specified in Deliverable 2 (required=True); whoever implements the
    # materializer MUST always resolve a concrete owner_id (e.g. a
    # role-queue placeholder res.users record) at create time until OQ-8 is
    # formally ratified. Do not relax `required` without re-reading OQ-8.
    owner_id = fields.Many2one("res.users", required=True, tracking=True)

    state = fields.Selection(
        [
            ("new", "New"),
            ("acknowledged", "Acknowledged"),
            ("in_progress", "In Progress"),
            ("resolved", "Resolved"),
            ("dismissed", "Dismissed"),
        ],
        default="new",
        required=True,
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Rule-based narrative fields — imperative, never @api.depends
    # ------------------------------------------------------------------
    impact_summary = fields.Char(size=280)
    recommended_action = fields.Text()
    why_text = fields.Text()

    # ------------------------------------------------------------------
    # Hermes link — pure FK, never mirrors Hermes's own fields
    # ------------------------------------------------------------------
    hermes_recommendation_id = fields.Many2one(
        "southbrook.hermes.recommendation",
        string="Filed Recommendation",
    )

    # ------------------------------------------------------------------
    # Timestamps (own workflow only — feeds Success Definition #2)
    # ------------------------------------------------------------------
    acknowledged_date = fields.Datetime(readonly=True)
    resolved_date = fields.Datetime(readonly=True)

    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )

    _source_uniq = models.Constraint(
        "unique(source_model, source_res_id, exception_type)",
        "An exception of this type already exists for this source record.",
    )

    # ------------------------------------------------------------------
    # Create: sequence-backed name (falls back gracefully if no
    # ir.sequence with this code has been registered by a later data file)
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                seq = self.env["ir.sequence"].next_by_code(
                    "southbrook.command.exception"
                )
                vals["name"] = seq or _("New")
        records = super().create(vals_list)
        for rec in records:
            if rec.name in (_("New"), False):
                rec.name = f"CC-{rec.id:06d}"
        return records

    # ------------------------------------------------------------------
    # Own-workflow action methods — the only fields this model may ever
    # write to itself outside the (out-of-scope-here) sync method.
    # ------------------------------------------------------------------
    def action_acknowledge(self):
        self.write(
            {
                "state": "acknowledged",
                "acknowledged_date": fields.Datetime.now(),
            }
        )
        return True

    def action_start_progress(self):
        """Not in Deliverable 2's three named actions, but required to
        reach 'in_progress' from the UI without skipping the state
        machine; does not stamp a new timestamp field (none defined for
        this transition in Deliverable 2)."""
        self.write({"state": "in_progress"})
        return True

    def action_resolve(self):
        self.write(
            {
                "state": "resolved",
                "resolved_date": fields.Datetime.now(),
                "active": False,
            }
        )
        return True

    def action_dismiss(self):
        self.write(
            {
                "state": "dismissed",
                "resolved_date": fields.Datetime.now(),
                "active": False,
            }
        )
        return True

    def action_reopen(self):
        """Undo a resolve/dismiss — return the exception to the open queue.
        Powers the dashboard's undo-toast (misclick recovery)."""
        self.write(
            {
                "state": "new",
                "active": True,
                "resolved_date": False,
                "acknowledged_date": False,
            }
        )
        return True
