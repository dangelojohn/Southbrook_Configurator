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
        """Daily cron: post an activity on each cert expiring in <=30d."""
        today = fields.Date.context_today(self)
        soon = today + timedelta(days=30)
        certs = self.search(
            [
                ("expires_at", ">=", today),
                ("expires_at", "<=", soon),
            ]
        )
        for cert in certs:
            mgr = cert.employee_id.parent_id.user_id or self.env.user
            cert.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=_("Certification expiring soon"),
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
        return len(certs)
