# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.installer.tool.loan — tool sign-out / return record.

Links a single ``maintenance.equipment`` (the tool) to an installer
job for the duration of the install visit. On return, a 'damaged' or
'maintenance' condition auto-creates a ``maintenance.request`` against
the equipment so the tool-room manager can intercept the unit before
it ships out on the next job.

Rental kit tracking is supported via four optional fields so a
borrowed tool (vs. company-owned) carries its own audit trail.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


_logger = logging.getLogger(__name__)


TOOL_TYPE = [
    ("power_tool", "Power Tool"),
    ("measuring", "Measuring & Layout"),
    ("cutting", "Cutting Equipment"),
    ("hanging_aid", "Hanging Aids"),
    ("safety", "Safety Equipment"),
    ("site_protection", "Site Protection"),
    ("hardware_tool", "Hardware Installation Tool"),
    ("consumable", "Consumable Kit"),
    ("rental", "Rented Equipment"),
]


SIGN_OUT_CONDITION = [
    ("good", "Good"),
    ("fair", "Fair"),
    ("poor", "Poor — Note Required"),
]


RETURN_CONDITION = [
    ("good", "Good — No Issues"),
    ("maintenance", "Needs Maintenance"),
    ("damaged", "Damaged"),
    ("lost", "Lost — Cannot Return"),
]


# Return conditions that trigger an auto maintenance.request.
_NEEDS_MAINTENANCE_REQUEST = {"maintenance", "damaged"}


class SouthbrookInstallerToolLoan(models.Model):
    _name = "southbrook.installer.tool.loan"
    _description = "Southbrook Installer Tool Loan"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "signed_out_time desc, id desc"

    name = fields.Char(
        compute="_compute_name",
        store=True,
        index=True,
    )
    job_id = fields.Many2one(
        "southbrook.installer.job",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    equipment_id = fields.Many2one(
        "maintenance.equipment",
        string="Tool / Equipment",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    equipment_category = fields.Char(
        related="equipment_id.category_id.name",
        store=False,
        readonly=True,
    )
    tool_type = fields.Selection(
        TOOL_TYPE,
        default="power_tool",
        index=True,
        tracking=True,
    )

    # ── Sign-out ─────────────────────────────────────────────────────
    signed_out_by_id = fields.Many2one("hr.employee", string="Signed Out By")
    signed_out_time = fields.Datetime(default=fields.Datetime.now)
    signed_out_condition = fields.Selection(
        SIGN_OUT_CONDITION, default="good")
    signed_out_notes = fields.Text()

    # ── Rental (optional) ────────────────────────────────────────────
    rental_company = fields.Char()
    rental_ref = fields.Char(string="Rental Agreement #")
    rental_return_due = fields.Date()
    rental_daily_cost = fields.Float(digits=(8, 2))

    # ── Return ───────────────────────────────────────────────────────
    returned = fields.Boolean(
        default=False,
        tracking=True,
        index=True,
    )
    returned_by_id = fields.Many2one(
        "hr.employee",
        string="Returned By",
        readonly=True,
        copy=False,
    )
    returned_time = fields.Datetime(readonly=True, copy=False)
    return_condition = fields.Selection(
        RETURN_CONDITION,
        tracking=True,
    )
    return_notes = fields.Text()
    maintenance_request_id = fields.Many2one(
        "maintenance.request",
        readonly=True,
        copy=False,
        help="Auto-created when return_condition is 'maintenance' "
             "or 'damaged'.",
    )

    # ── Derived ──────────────────────────────────────────────────────
    days_on_loan = fields.Integer(
        compute="_compute_days_on_loan",
        store=True,
        help="Whole-day count between sign-out and return (or now if "
             "not yet returned).",
    )

    display_name = fields.Char(
        compute="_compute_display_name",
        store=False,
        recursive=False,
    )

    # ── Computes ─────────────────────────────────────────────────────
    @api.depends("equipment_id.name", "job_id.name")
    def _compute_name(self):
        for rec in self:
            rec.name = "%s / %s" % (
                rec.equipment_id.name or "?",
                rec.job_id.name or "?",
            )

    @api.depends("name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _("New Loan")

    @api.depends("signed_out_time", "returned_time")
    def _compute_days_on_loan(self):
        now = fields.Datetime.now()
        for rec in self:
            if not rec.signed_out_time:
                rec.days_on_loan = 0
                continue
            end = rec.returned_time or now
            rec.days_on_loan = max((end - rec.signed_out_time).days, 0)

    # ── Constraints ──────────────────────────────────────────────────
    @api.constrains("signed_out_condition", "signed_out_notes")
    def _check_poor_needs_note(self):
        for rec in self:
            if (rec.signed_out_condition == "poor"
                    and not (rec.signed_out_notes or "").strip()):
                raise ValidationError(_(
                    "Tool %(t)s signed out in 'poor' condition needs "
                    "a note describing the issue.",
                ) % {"t": rec.equipment_id.display_name})

    @api.constrains("return_condition", "returned", "return_notes")
    def _check_return_notes_required(self):
        for rec in self:
            if (rec.returned
                    and rec.return_condition in ("damaged", "lost")
                    and not (rec.return_notes or "").strip()):
                raise ValidationError(_(
                    "Tool %(t)s returned as %(c)s — describe what "
                    "happened in the Return Notes.",
                ) % {
                    "t": rec.equipment_id.display_name,
                    "c": rec.return_condition,
                })

    # ==================================================================
    # Actions
    # ==================================================================
    def action_return_tool(self, return_condition=None, notes=None):
        """Mark the loan returned. If condition is 'maintenance' or
        'damaged', auto-spawn a maintenance.request on the equipment.

        Programmatic callers (e.g. mobile API) can pass condition +
        notes directly; UI callers set the fields first and call the
        button with no args."""
        for rec in self:
            if rec.returned:
                raise UserError(_(
                    "Tool %s already returned at %s.",
                ) % (rec.name,
                     fields.Datetime.to_string(rec.returned_time)))
            condition = return_condition or rec.return_condition
            if not condition:
                raise UserError(_(
                    "Pick a return condition before returning tool %s.",
                ) % rec.name)
            employee = self.env.user.employee_id
            vals = {
                "returned": True,
                "returned_time": fields.Datetime.now(),
                "returned_by_id": employee.id if employee else False,
                "return_condition": condition,
            }
            if notes is not None:
                vals["return_notes"] = notes
            rec.write(vals)
            if condition in _NEEDS_MAINTENANCE_REQUEST:
                rec._spawn_maintenance_request()
            rec.job_id.message_post(body=_(
                "🛠 Tool <b>%(t)s</b> returned in <b>%(c)s</b> "
                "condition by %(u)s.",
            ) % {
                "t": rec.equipment_id.display_name,
                "c": dict(RETURN_CONDITION).get(condition, condition),
                "u": self.env.user.display_name,
            })

    def action_report_lost(self, notes=None):
        """Specialised return — sets condition='lost'. Always requires
        a note (constraint). Posts an alert to the parent job."""
        for rec in self:
            rec.action_return_tool(
                return_condition="lost",
                notes=notes or rec.return_notes,
            )
            rec.job_id.message_post(body=_(
                "🚨 <b>LOST TOOL</b> — %s flagged as lost by %s.",
            ) % (
                rec.equipment_id.display_name,
                self.env.user.display_name,
            ))

    def _spawn_maintenance_request(self):
        """Auto-create maintenance.request linked to equipment. Stored
        on maintenance_request_id so the operator can drill in from
        the tool loan record."""
        self.ensure_one()
        Maintenance = self.env["maintenance.request"]
        # maintenance_request_id may already exist if action_return was
        # re-run from a stuck state — idempotent.
        if self.maintenance_request_id:
            return self.maintenance_request_id
        req = Maintenance.create({
            "name": _("Auto: %(c)s — %(eq)s after job %(j)s") % {
                "c": dict(RETURN_CONDITION).get(
                    self.return_condition, self.return_condition),
                "eq": self.equipment_id.name,
                "j": self.job_id.name,
            },
            "equipment_id": self.equipment_id.id,
            "maintenance_type": "corrective",
            "description": _(
                "Auto-raised from southbrook.installer.tool.loan %(n)s.\n"
                "Job: %(j)s — Site: %(s)s\n"
                "Returned by: %(by)s\n"
                "Condition: %(c)s\n"
                "Notes: %(notes)s"
            ) % {
                "n": self.name,
                "j": self.job_id.name,
                "s": self.job_id.site_address or "?",
                "by": (self.returned_by_id.name
                       or self.env.user.display_name),
                "c": dict(RETURN_CONDITION).get(
                    self.return_condition, self.return_condition),
                "notes": self.return_notes or "—",
            },
        })
        self.write({"maintenance_request_id": req.id})
        self.job_id.message_post(body=_(
            "🔧 Maintenance request <b>%(r)s</b> opened on %(eq)s "
            "(condition: %(c)s).",
        ) % {
            "r": req.name,
            "eq": self.equipment_id.display_name,
            "c": dict(RETURN_CONDITION).get(
                self.return_condition, self.return_condition),
        })
        return req

    def action_view_maintenance_request(self):
        self.ensure_one()
        if not self.maintenance_request_id:
            raise UserError(_("No maintenance request on this loan."))
        return {
            "type": "ir.actions.act_window",
            "res_model": "maintenance.request",
            "res_id": self.maintenance_request_id.id,
            "view_mode": "form",
            "target": "current",
        }
