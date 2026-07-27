# SPDX-License-Identifier: LGPL-3.0-only
"""Employee certifications (WHMIS, Forklift, First-Aid, etc.).

Soft-coupled to ``southbrook_elearning_internal``'s ``slide.channel`` via
a Reference field so the addon installs cleanly without it.  When the
elearning addon is present, a course completion can populate the
``source_course_id`` to thread certification back to its learning record.
"""

from datetime import timedelta

from odoo import _, api, fields, models


class SouthbrookPayrollCertification(models.Model):
    _name = "southbrook.payroll.certification"
    _description = "Southbrook Employee Certification"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "expires_at, name"

    name = fields.Char(required=True, tracking=True)
    employee_id = fields.Many2one(
        "hr.employee", required=True, tracking=True, ondelete="cascade"
    )
    issued_at = fields.Date(required=True, tracking=True)
    expires_at = fields.Date(tracking=True)
    expiry_status = fields.Selection(
        [
            ("valid", "Valid"),
            ("expiring_soon", "Expiring Soon (<=30d)"),
            ("expired", "Expired"),
        ],
        compute="_compute_expiry_status",
        store=True,
    )
    proof_attachment_ids = fields.Many2many(
        "ir.attachment",
        "southbrook_payroll_cert_attach_rel",
        "cert_id",
        "attachment_id",
        string="Proof",
    )
    # Soft reference to the elearning course. We use Reference, not
    # Many2one, so this addon does not need to depend on
    # southbrook_elearning_internal. The model exists on disk in this
    # repo but is not in our manifest deps.
    source_course_ref = fields.Reference(
        selection=[("slide.channel", "Course")],
        string="Source Course",
        help="Optional link to the slide.channel that issued this cert. "
             "Available only when southbrook_elearning_internal is installed.",
    )

    @api.depends("expires_at")
    def _compute_expiry_status(self):
        today = fields.Date.context_today(self)
        soon = today + timedelta(days=30)
        for rec in self:
            if not rec.expires_at:
                rec.expiry_status = "valid"
            elif rec.expires_at < today:
                rec.expiry_status = "expired"
            elif rec.expires_at <= soon:
                rec.expiry_status = "expiring_soon"
            else:
                rec.expiry_status = "valid"

    @api.model
    def cron_alert_expiring(self):
        """Daily cron: refresh expiry status, then post ONE renewal activity
        per cert expiring in <=30d (deduped, per-row isolated)."""
        import logging
        _logger = logging.getLogger(__name__)
        today = fields.Date.context_today(self)
        soon = today + timedelta(days=30)
        # M8: expiry_status is a stored compute keyed only on expires_at, so a
        # cert that crossed its expiry since the last write keeps a stale
        # status (and the employee's expiring/expired counts drift). Recompute
        # every dated cert nightly so the kanban grouping + counts stay true.
        dated = self.search([("expires_at", "!=", False)])
        if dated:
            dated._compute_expiry_status()
        summary = _("Certification expiring soon")
        todo_type = self.env.ref("mail.mail_activity_data_todo")
        certs = self.search(
            [
                ("expires_at", ">=", today),
                ("expires_at", "<=", soon),
            ]
        )
        posted = 0
        for cert in certs:
            try:
                # M5: dedup — the cron runs daily; without this it schedules a
                # fresh to-do every day (~30 duplicates per cert). Skip if an
                # open renewal activity of this kind already exists.
                already = self.env["mail.activity"].search_count(
                    [
                        ("res_model", "=", self._name),
                        ("res_id", "=", cert.id),
                        ("activity_type_id", "=", todo_type.id),
                        ("summary", "=", summary),
                    ]
                )
                if already:
                    continue
                mgr = cert.employee_id.parent_id.user_id or self.env.user
                cert.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=summary,
                    note=_(
                        "Certification %(cert)s for %(emp)s expires on "
                        "%(date)s — renew before then."
                    ) % {
                        "cert": cert.name,
                        "emp": cert.employee_id.name,
                        "date": cert.expires_at,
                    },
                    user_id=mgr.id,
                )
                posted += 1
            except Exception as e:  # noqa: BLE001 — one bad row must not abort the sweep
                _logger.warning(
                    "cert cron: activity for %s failed: %s", cert.name, e)
        return posted
