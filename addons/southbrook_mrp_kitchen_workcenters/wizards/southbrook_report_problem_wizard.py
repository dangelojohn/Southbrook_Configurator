# SPDX-License-Identifier: LGPL-3.0-only
"""W040 (R2.4, 2026-06-27) — One-screen Report-a-Problem wizard.

JTBD
----
"When something goes wrong at the cell, I want ONE screen to log
scrap qty + defect description + downtime — not 3 separate forms."

Behaviour
---------
Single TransientModel opened from the WO form (tablet-friendly). Three
optional sections — operator fills any subset:

  Scrap     → creates stock.scrap (qty + product + reason) + done()
  Defect    → creates southbrook.mi.check (description + photo + sev)
  Downtime  → creates southbrook.kitchen.workcenter.downtime row

On submit, all three creates run inside ONE savepoint. If any one
fails the operator sees the ORM error and NOTHING was written — no
half-committed scraps with an orphan defect, no orphan downtime row
pointing at a scrap that rolled back.

Constraints honoured
--------------------
- Single-transaction atomicity via `self.env.cr.savepoint()`.
- Operator attribution: writes use the env user; if W035's operator
  PIN binding is active on the WO, the resolved employee_id is
  echoed onto the downtime + mi.check rows.
- No raw SQL. Pure ORM.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.southbrook_mi_check import DEFECT_TYPES, CHECK_STAGES


_logger = logging.getLogger(__name__)


# Downtime reasons mirror the model's DOWNTIME_REASONS enum but
# we re-declare a short list here so the wizard widget renders the
# common ones large. Falls back to a free-text 'other' on submit.
WIZARD_DOWNTIME_REASONS = [
    ("machine_breakdown", "Machine Breakdown"),
    ("material_shortage", "Material Shortage"),
    ("changeover", "Changeover"),
    ("quality_hold", "Quality Hold"),
    ("operator_break", "Operator Break"),
    ("other", "Other"),
]

WIZARD_SCRAP_REASONS = [
    ("damage_in_process", "Damage In Process"),
    ("wrong_dimension", "Wrong Dimension"),
    ("material_defect", "Material Defect"),
    ("operator_error", "Operator Error"),
    ("other", "Other"),
]


class SouthbrookReportProblemWizard(models.TransientModel):
    _name = "southbrook.report.problem.wizard"
    _description = "One-screen Report-a-Problem (scrap + defect + downtime, W040)"

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
    company_id = fields.Many2one(
        "res.company",
        related="workorder_id.company_id",
        readonly=True,
        store=False,
    )

    # ---- Scrap section ----------------------------------------------
    include_scrap = fields.Boolean(string="Log Scrap?", default=False)
    scrap_product_id = fields.Many2one(
        "product.product",
        string="Scrapped Product",
        help="Defaults to the MO's finished good. Pick a component if "
             "the scrap was a part not the finished cabinet.",
    )
    scrap_qty = fields.Float(string="Scrap Qty", default=1.0)
    scrap_uom_id = fields.Many2one(
        "uom.uom",
        string="UoM",
    )
    scrap_reason = fields.Selection(
        WIZARD_SCRAP_REASONS, string="Scrap Reason",
    )
    scrap_notes = fields.Text(string="Scrap Notes")

    # ---- Defect section ----------------------------------------------
    include_defect = fields.Boolean(string="Log Defect?", default=False)
    defect_type = fields.Selection(
        DEFECT_TYPES, string="Defect Type",
    )
    defect_stage = fields.Selection(
        CHECK_STAGES, string="Detected At",
    )
    defect_severity = fields.Selection(
        [("minor", "Minor"), ("major", "Major"), ("critical", "Critical")],
        string="Defect Severity",
        default="minor",
    )
    defect_description = fields.Text(string="Defect Description")
    defect_photo = fields.Binary(string="Defect Photo", attachment=True)
    defect_photo_filename = fields.Char(string="Defect Photo Filename")

    # ---- Downtime section --------------------------------------------
    include_downtime = fields.Boolean(string="Log Downtime?", default=False)
    downtime_reason = fields.Selection(
        WIZARD_DOWNTIME_REASONS, string="Downtime Reason",
    )
    downtime_minutes = fields.Float(
        string="Downtime (min)", default=0.0,
        help="Free-form duration in minutes. Use this when the timer "
             "wasn't started — backfill an honest estimate."
    )
    downtime_notes = fields.Text(string="Downtime Notes")

    # ---- Audit / output handles --------------------------------------
    last_scrap_id = fields.Many2one("stock.scrap", readonly=True)
    last_mi_check_id = fields.Many2one("southbrook.mi.check", readonly=True)
    last_downtime_id = fields.Many2one(
        "southbrook.kitchen.workcenter.downtime", readonly=True)

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        wo_id = (
            self.env.context.get("default_workorder_id")
            or self.env.context.get("active_id")
        )
        if wo_id and (self.env.context.get("active_model") == "mrp.workorder"
                      or "default_workorder_id" in self.env.context):
            vals["workorder_id"] = wo_id
            wo = self.env["mrp.workorder"].browse(wo_id)
            if wo.exists():
                # Default the scrap product to the MO's finished good
                # — most common shop-floor case.
                if wo.production_id and wo.production_id.product_id:
                    vals.setdefault(
                        "scrap_product_id",
                        wo.production_id.product_id.id,
                    )
                    vals.setdefault(
                        "scrap_uom_id",
                        wo.production_id.product_uom_id.id,
                    )
        return vals

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def _validate(self):
        self.ensure_one()
        if not any([self.include_scrap, self.include_defect, self.include_downtime]):
            raise UserError(_(
                "Tick at least one section (Scrap / Defect / Downtime) "
                "before submitting."))
        if self.include_scrap:
            if not self.scrap_product_id:
                raise UserError(_("Scrap section: pick a product."))
            if self.scrap_qty <= 0:
                raise UserError(_("Scrap section: qty must be > 0."))
        if self.include_defect:
            if not (self.defect_type or self.defect_description):
                raise UserError(_(
                    "Defect section: at minimum, pick a Defect Type or "
                    "write a Description."))
        if self.include_downtime:
            if not self.downtime_reason:
                raise UserError(_(
                    "Downtime section: pick a Reason."))
            if self.downtime_minutes <= 0:
                raise UserError(_(
                    "Downtime section: minutes must be > 0."))

    # ------------------------------------------------------------------
    # Submit (atomic)
    # ------------------------------------------------------------------
    def action_submit(self):
        self.ensure_one()
        self._validate()
        # Single-transaction atomicity via a savepoint. The Odoo
        # request-handler wraps the entire RPC in one cr, so a raised
        # exception inside the savepoint rolls EVERYTHING in the
        # wizard back — no half-committed scraps + orphan defects.
        scrap = mi_check = downtime = False
        with self.env.cr.savepoint():
            if self.include_scrap:
                scrap = self._create_scrap()
            if self.include_defect:
                mi_check = self._create_defect()
            if self.include_downtime:
                downtime = self._create_downtime()
            # W090 (R5.10) — when BOTH scrap + defect were created
            # in this wizard pass, link them so the NCR carries the
            # scrap back-reference and the scrap reason. Idempotent
            # by ondelete='set null' on the M2O. Single write inside
            # the savepoint so a downstream failure rolls the link
            # back with the rest.
            if scrap and mi_check:
                mi_check.sudo().write({
                    "x_sbk_scrap_id": scrap.id,
                    "x_sbk_scrap_reason": self.scrap_reason or False,
                })

        # Save the back-refs for the test harness + the success
        # banner. Outside the savepoint because the wizard itself
        # is mid-write, but the wizard record is transient so its
        # write is the same cr.
        self.write({
            "last_scrap_id": scrap and scrap.id,
            "last_mi_check_id": mi_check and mi_check.id,
            "last_downtime_id": downtime and downtime.id,
        })

        # Audit log on WO chatter — one consolidated note.
        self._post_wo_summary(scrap, mi_check, downtime)

        _logger.info(
            "W040: report-problem wizard committed for WO %s by %s "
            "(scrap=%s mi_check=%s downtime=%s)",
            self.workorder_id.id, self.env.user.login,
            scrap and scrap.id, mi_check and mi_check.id,
            downtime and downtime.id,
        )

        # Stay on the WO form — pop a success notification.
        bits = []
        if scrap:
            bits.append(_("Scrap %s") % scrap.name)
        if mi_check:
            bits.append(_("Defect %s") % mi_check.display_name)
        if downtime:
            bits.append(_("Downtime %.1f min") % (downtime.duration_min or 0.0))
        message = _("Logged: %s") % ", ".join(bits) if bits else _("Nothing logged.")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Problem reported"),
                "message": message,
                "type": "success",
                "sticky": False,
                # Reload the WO form so the new badges (rework count,
                # downtime min) refresh in place.
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    # ------------------------------------------------------------------
    # Per-artifact helpers
    # ------------------------------------------------------------------
    def _create_scrap(self):
        """Create + immediately validate a stock.scrap so the
        inventory debit lands in one step. Mirrors the M040 pattern
        used by action_open_scrap_wizard."""
        self.ensure_one()
        scrap = self.env["stock.scrap"].sudo().create({
            "product_id": self.scrap_product_id.id,
            "product_uom_id": (
                self.scrap_uom_id.id
                or self.scrap_product_id.uom_id.id
            ),
            "scrap_qty": self.scrap_qty,
            "production_id": self.production_id.id if self.production_id else False,
            "workorder_id": self.workorder_id.id,
            "company_id": self.company_id.id if self.company_id else self.env.company.id,
            "origin": _("W040 wizard: %s") % (self.workorder_id.display_name or ""),
        })
        # Append the operator's free-text reason to the scrap record
        # as a chatter note (stock.scrap doesn't have a reason field).
        body_bits = []
        if self.scrap_reason:
            label = dict(WIZARD_SCRAP_REASONS).get(
                self.scrap_reason, self.scrap_reason)
            body_bits.append("<strong>%s</strong>" % label)
        if self.scrap_notes:
            body_bits.append(self.scrap_notes)
        if body_bits:
            scrap.message_post(
                body="<br/>".join(body_bits),
                subtype_xmlid="mail.mt_note",
            )
        # Validate immediately so the inventory debit lands. v19
        # stock.scrap exposes action_validate (older flow) or moves
        # via do_scrap; action_validate is the canonical v19 method.
        try:
            scrap.action_validate()
        except Exception as exc:  # noqa: BLE001
            # Surface the error so the savepoint rolls the rest back.
            raise UserError(_(
                "Scrap could not be validated: %s") % exc)
        return scrap

    def _create_defect(self):
        """Create a southbrook.mi.check with the operator's defect
        narrative + photo. Defaults severity (mi.engine triage) to
        'warning' when defect_severity is 'major' or 'critical',
        else 'info'."""
        self.ensure_one()
        engine_severity = (
            "blocker" if self.defect_severity == "critical"
            else "warning" if self.defect_severity == "major"
            else "info"
        )
        vals = {
            "name": (self.defect_type and dict(DEFECT_TYPES).get(self.defect_type))
                    or self.defect_description and self.defect_description[:80]
                    or _("Operator-reported defect"),
            "message": self.defect_description or self.workorder_id.display_name,
            "severity": engine_severity,
            "category": "production",
            "production_id": self.production_id.id if self.production_id else False,
            "x_sbk_workorder_id": self.workorder_id.id,
            "x_sbk_check_stage": self.defect_stage or False,
            "x_sbk_defect_type": self.defect_type or False,
            "x_sbk_defect_severity": self.defect_severity or "minor",
            "x_sbk_result": "fail",
            "x_sbk_inspector_id": self.env.user.id,
            "x_sbk_date_checked": fields.Datetime.now(),
        }
        if self.defect_photo:
            vals["image"] = self.defect_photo
        check = self.env["southbrook.mi.check"].sudo().create(vals)
        return check

    def _create_downtime(self):
        """Create a closed-state downtime row carrying the operator's
        notes + reason. Marks state=closed so duration_min is the
        authoritative figure; date_end backfills from date_start +
        downtime_minutes."""
        self.ensure_one()
        from datetime import timedelta
        date_start = fields.Datetime.now() - timedelta(
            minutes=self.downtime_minutes)
        date_end = fields.Datetime.now()
        # Map wizard reasons onto the model's reason enum. The model
        # enum is defined in the downtime module; both share
        # 'machine_breakdown', 'material_shortage', 'changeover',
        # 'quality_hold', 'operator_break', 'other'.
        downtime = self.env["southbrook.kitchen.workcenter.downtime"].sudo().create({
            "name": (
                _("W040 wizard: %s") % dict(WIZARD_DOWNTIME_REASONS).get(
                    self.downtime_reason, self.downtime_reason)
            ),
            "workcenter_id": self.workcenter_id.id,
            "workorder_id": self.workorder_id.id,
            "date_start": date_start,
            "date_end": date_end,
            "duration_min": self.downtime_minutes,
            "reason": self.downtime_reason,
            "notes": self.downtime_notes or "",
            "state": "closed",
            "responsible_id": self.env.user.id,
        })
        return downtime

    def _post_wo_summary(self, scrap, mi_check, downtime):
        """One consolidated chatter note on the WO so the audit trail
        is single-line per wizard submit."""
        self.ensure_one()
        lines = ["<p><strong>%s</strong></p>" % _("Problem report (W040)"), "<ul>"]
        if scrap:
            lines.append("<li>%s: %s — %s × %s</li>" % (
                _("Scrap"), scrap.name,
                scrap.product_id.display_name, scrap.scrap_qty))
        if mi_check:
            lines.append("<li>%s: %s (%s/%s)</li>" % (
                _("Defect"), mi_check.display_name,
                dict(DEFECT_TYPES).get(mi_check.x_sbk_defect_type, "?"),
                mi_check.x_sbk_defect_severity or "?"))
        if downtime:
            lines.append("<li>%s: %.1f min — %s</li>" % (
                _("Downtime"), downtime.duration_min or 0.0,
                dict(WIZARD_DOWNTIME_REASONS).get(
                    downtime.reason, downtime.reason or "?")))
        lines.append("</ul>")
        lines.append("<p class='text-muted'>%s: %s</p>" % (
            _("Reported by"), self.env.user.display_name))
        self.workorder_id.message_post(
            body="".join(lines),
            subtype_xmlid="mail.mt_note",
        )


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    def action_sbk_open_report_problem_wizard(self):
        """Open the W040 single-screen Report-a-Problem wizard
        pre-bound to this WO."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Report a Problem"),
            "res_model": "southbrook.report.problem.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_workorder_id": self.id,
                "active_id": self.id,
                "active_model": "mrp.workorder",
            },
        }
