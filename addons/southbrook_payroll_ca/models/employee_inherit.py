# SPDX-License-Identifier: LGPL-3.0-only
"""Extend hr.employee with certifications + WSIB classification."""

from datetime import timedelta

from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    certification_ids = fields.One2many(
        "southbrook.payroll.certification",
        "employee_id",
        string="Certifications",
    )
    cert_count = fields.Integer(compute="_compute_cert_stats", store=False)
    cert_expiring_soon_count = fields.Integer(
        compute="_compute_cert_stats", store=False
    )
    next_cert_expiry_date = fields.Date(
        compute="_compute_cert_stats", store=False
    )
    wsib_classification_unit = fields.Char(
        default="Manufacturing — Wood Cabinets",
    )
    payroll_contract_ids = fields.One2many(
        "southbrook.payroll.contract",
        "employee_id",
        string="Payroll Contracts",
    )
    payroll_contract_count = fields.Integer(
        compute="_compute_payroll_contract_count",
        store=False,
    )

    @api.depends("payroll_contract_ids")
    def _compute_payroll_contract_count(self):
        for emp in self:
            emp.payroll_contract_count = len(emp.payroll_contract_ids)

    def action_view_payroll_contracts(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "southbrook_payroll_ca.action_southbrook_payroll_contract"
        )
        action["domain"] = [("employee_id", "=", self.id)]
        action["context"] = {"default_employee_id": self.id}
        return action

    def action_view_certifications(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "southbrook_payroll_ca.action_southbrook_payroll_certification"
        )
        action["domain"] = [("employee_id", "=", self.id)]
        action["context"] = {"default_employee_id": self.id}
        return action

    @api.depends(
        "certification_ids",
        "certification_ids.expires_at",
        "certification_ids.expiry_status",
    )
    def _compute_cert_stats(self):
        for emp in self:
            certs = emp.certification_ids
            emp.cert_count = len(certs)
            emp.cert_expiring_soon_count = len(
                certs.filtered(lambda c: c.expiry_status == "expiring_soon")
            )
            future = certs.filtered(lambda c: c.expires_at).sorted("expires_at")
            emp.next_cert_expiry_date = future[:1].expires_at if future else False
