# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields, models


class SbProductionPackage(models.Model):
    _inherit = "sb.production.package"

    x_mi_status = fields.Selection(
        [
            ("ok", "OK"),
            ("review", "Review"),
            ("blocked", "Blocked"),
        ],
        string="MI Status",
        default="ok",
        copy=False,
    )
    x_mi_check_ids = fields.One2many(
        "southbrook.mi.check",
        "production_package_id",
        string="Manufacturing Intelligence Checks",
    )
    x_mi_blocker_count = fields.Integer(string="MI Blockers", copy=False)
    x_mi_warning_count = fields.Integer(string="MI Warnings", copy=False)
    x_mi_install_warning_count = fields.Integer(
        string="MI Install Warnings", copy=False
    )
    x_mi_next_action = fields.Text(string="MI Next Action", copy=False)
    x_mi_yield_pct = fields.Float(string="MI Sheet Yield %", copy=False)
    x_mi_waste_area_m2 = fields.Float(string="MI Waste Area m2", copy=False)
    x_mi_edge_band_m = fields.Float(string="MI Edge Band m", copy=False)
    x_mi_blocked_stage = fields.Selection(
        [
            ("saw", "Saw"),
            ("cnc", "CNC"),
            ("edgeband", "Edgeband"),
            ("assembly", "Assembly"),
            ("finish_qc", "Finish / QC"),
            ("delivery", "Delivery"),
            ("install", "Install"),
        ],
        string="MI Blocked Stage",
        copy=False,
    )
    x_mi_next_stage_action = fields.Text(string="MI Next Stage Action", copy=False)
    x_mi_saw_blocker_count = fields.Integer(string="Saw Blockers", copy=False)
    x_mi_cnc_blocker_count = fields.Integer(string="CNC Blockers", copy=False)
    x_mi_edgeband_blocker_count = fields.Integer(
        string="Edgeband Blockers", copy=False
    )
    x_mi_assembly_blocker_count = fields.Integer(
        string="Assembly Blockers", copy=False
    )
    x_mi_finish_qc_blocker_count = fields.Integer(
        string="Finish/QC Blockers", copy=False
    )
    x_mi_delivery_blocker_count = fields.Integer(
        string="Delivery Blockers", copy=False
    )
    x_mi_install_blocker_count = fields.Integer(
        string="Install Blockers", copy=False
    )

    def action_recompute_manufacturing_intelligence(self):
        engine = self.env["southbrook.mi.engine"]
        for package in self:
            engine._recompute_package(package)
        return True

    def _mi_install_check_lines_for_pdf(self):
        self.ensure_one()
        checks = self.env["southbrook.mi.check"].sudo().search(
            [
                ("production_package_id", "=", self.id),
                ("category", "=", "install"),
            ]
        )
        return self.env["southbrook.mi.engine"]._install_check_lines_for_pdf(checks)
