# SPDX-License-Identifier: LGPL-3.0-only
import random
import json
from odoo import api, fields, models


class SbPanel(models.Model):
    _name = "sb.panel"
    _description = "Panel Manufacturing Passport"
    _order = "name desc"

    name = fields.Char(
        string="Panel ID", required=True, copy=False, readonly=True,
        index=True, default=lambda self: "New",
    )
    barcode = fields.Char(string="Barcode", required=True, index=True, copy=False)
    production_id = fields.Many2one("mrp.production", string="Manufacturing Order",
                                    ondelete="set null", index=True)
    product_id = fields.Many2one("product.product", string="Panel Product")
    material = fields.Char(string="Material")
    cabinet_ref = fields.Char(string="Cabinet")
    kitchen_ref = fields.Char(string="Kitchen")
    customer_id = fields.Many2one("res.partner", string="Customer")
    state = fields.Selection(
        [("draft", "Draft"), ("in_progress", "In Progress"),
         ("complete", "Complete"), ("installed", "Installed")],
        string="Status", default="draft", required=True,
    )
    install_date = fields.Date(string="Installation Date")
    cycle_ids = fields.One2many("sb.panel.cycle", "panel_id", string="Operations")
    qc_result = fields.Selection(
        [("pass", "Pass"), ("fail", "Fail"), ("na", "N/A")],
        string="Overall QC", compute="_compute_qc_result", store=True,
    )
    event_ids = fields.One2many("sb.machine.event", "panel_id", string="Events")

    _barcode_unique = models.Constraint(
        "unique(barcode)",
        "A panel with this barcode already exists.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("sb.panel") or "New"
                )
        return super().create(vals_list)

    @api.depends("cycle_ids.qc_result")
    def _compute_qc_result(self):
        for panel in self:
            results = panel.cycle_ids.mapped("qc_result")
            if "fail" in results:
                panel.qc_result = "fail"
            elif results and all(r == "pass" for r in results):
                panel.qc_result = "pass"
            else:
                panel.qc_result = "na"

    def _derive_customer(self):
        """Best-effort: set customer_id from the MO's sale/partner link.

        CE mrp.production has no guaranteed partner. Probe known link
        paths with getattr guards so this never raises regardless of
        which optional modules are installed. Silent no-op when nothing
        resolves.
        """
        for panel in self:
            mo = panel.production_id
            if not mo:
                continue
            partner = False
            # Path A: a direct partner_id (present if some module added it).
            partner = getattr(mo, "partner_id", False)
            # Path B: sale_id.partner_id (sale_mrp-style link).
            if not partner:
                sale = getattr(mo, "sale_id", False)
                partner = getattr(sale, "partner_id", False) if sale else False
            if partner:
                panel.customer_id = partner.id

    @api.model
    def _lookup_by_barcode(self, barcode):
        """Return the panel matching this barcode (empty recordset if none)."""
        if not barcode:
            return self.browse()
        return self.search([("barcode", "=", barcode)], limit=1)

    def _simulate_from_production(self, production, panel_count=1, seed=0):
        """Fabricate deterministic genealogy for an MO (no machine needed).

        Uses a locally-seeded Random so the same seed reproduces
        byte-identical cycle times + QC. Mirrors the homag_session
        'deterministic with seed' convention. Each panel gets a CUT
        and a DRILL cycle plus a scan event.
        """
        rng = random.Random(seed)
        bore_wc = self.env["mrp.workcenter"].search(
            [("code", "=", "SB-CNC-BORE")], limit=1)
        programs = ["HINGE_32MM_RIGHT", "HINGE_32MM_LEFT", "SHELF_PIN_5MM"]
        panels = self.browse()
        for _i in range(panel_count):
            panel = self.create({
                "barcode": "SIM-%s-%s" % (production.id, rng.randint(10**6, 10**7)),
                "production_id": production.id,
                "product_id": production.product_id.id,
                "material": "18mm MDF White",
                "state": "in_progress",
            })
            for op, wc in [("CUT", False), ("DRILL", bore_wc)]:
                dur = round(rng.uniform(38.0, 52.0), 1)
                qc = "pass" if rng.random() > 0.05 else "fail"
                self.env["sb.panel.cycle"].create({
                    "panel_id": panel.id,
                    "workcenter_id": wc.id if wc else False,
                    "operation": op,
                    "program": rng.choice(programs) if op == "DRILL" else False,
                    "tool_ref": "5mm Drill" if op == "DRILL" else "8mm Comp Bit",
                    "duration_s": dur,
                    "qc_result": qc,
                })
            self.env["sb.machine.event"].create({
                "panel_id": panel.id,
                "workcenter_id": bore_wc.id if bore_wc else False,
                "machine_code": "SIMULATOR",
                "event_type": "scan",
                "payload": json.dumps({"barcode": panel.barcode}),
            })
            panels |= panel
        return panels
