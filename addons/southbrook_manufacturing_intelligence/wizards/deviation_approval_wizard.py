# SPDX-License-Identifier: LGPL-3.0-only
"""W012 — QC-side wizard for requesting a deviation approval.

Opened by `mi.check.action_approve_deviation`. Creates a
southbrook.deviation.waiver in draft, immediately submits it to
engineering review, and flips the source NCR's state.

Why a wizard not an inline edit:
  * Captures all the customer-acknowledgement fields up front in one
    dialog rather than scattering them across the NCR form (which is
    already busy with the inspector extension's x_sbk_* fields).
  * Gives a clean back-out (Cancel = no record created).
  * Lets us validate "ack captured if applicable" before persisting.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class DeviationApprovalWizard(models.TransientModel):
    _name = "southbrook.deviation.approval.wizard"
    _description = "Wizard — Request Engineering Deviation Approval"

    mi_check_id = fields.Many2one(
        "southbrook.mi.check",
        string="NCR",
        required=True, readonly=True,
    )
    production_id = fields.Many2one(
        "mrp.production",
        string="Manufacturing Order",
        related="mi_check_id.production_id", readonly=True,
    )
    cabinet_serial = fields.Char(
        string="Cabinet Serial",
        compute="_compute_cabinet_serial", readonly=True,
    )
    customer_id = fields.Many2one(
        "res.partner",
        string="Customer",
        compute="_compute_customer_id", readonly=False, store=False,
        help="Auto-resolved from the MO's sale order when present. "
             "Editable so QC can override for stock-build MOs.",
    )

    defect_summary = fields.Text(
        string="Defect Summary",
        required=True,
        help="What is the customer being asked to accept? Plain English. "
             "This text is what the warranty team will read 3 years out.",
    )
    engineering_rationale = fields.Text(
        string="Engineering Rationale (optional)",
        help="If you've already discussed with engineering, summarise "
             "their position. Otherwise leave blank — engineering "
             "fills this in at approval time.",
    )

    # Customer acknowledgement
    customer_acknowledged = fields.Boolean(
        string="Customer Acknowledged",
        help="Engineering will refuse to approve unless this is ticked.",
    )
    customer_acknowledgment_method = fields.Selection(
        [
            ("email", "Customer email"),
            ("phone", "Phone call (logged)"),
            ("in_person", "In-person"),
            ("po_amendment", "Customer PO amendment"),
        ],
        string="Acknowledgement Method",
    )
    customer_acknowledgment_ref = fields.Char(
        string="Acknowledgement Reference",
        help="Email subject, call note ID, PO amendment number — any "
             "external pointer that lets us find the artefact later.",
    )

    # ------------------------------------------------------------------
    # Computed defaults
    # ------------------------------------------------------------------
    @api.depends("production_id", "production_id.lot_producing_id")
    def _compute_cabinet_serial(self):
        for rec in self:
            mo = rec.production_id
            lot = mo.lot_producing_id if mo else False
            rec.cabinet_serial = lot.name if lot else False

    @api.depends("production_id")
    def _compute_customer_id(self):
        for rec in self:
            mo = rec.production_id
            order_line = getattr(mo, "sale_line_id", False) if mo else False
            so = order_line.order_id if order_line else False
            rec.customer_id = (so.partner_id.id
                               if so and so.partner_id else False)

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------
    def action_submit(self):
        """Create the waiver + submit it to engineering review."""
        self.ensure_one()
        if not self.defect_summary:
            raise UserError(_(
                "Please describe the defect — engineering needs context "
                "before approving."))
        if self.customer_acknowledged and \
                not self.customer_acknowledgment_method:
            raise UserError(_(
                "You ticked 'customer acknowledged' — please record the "
                "method (email/phone/in-person/PO amendment)."))
        Waiver = self.env["southbrook.deviation.waiver"]
        waiver = Waiver.create({
            "mi_check_id": self.mi_check_id.id,
            "customer_id": self.customer_id.id if self.customer_id
                           else False,
            "defect_summary": self.defect_summary,
            "engineering_rationale": self.engineering_rationale or False,
            "customer_acknowledged": self.customer_acknowledged,
            "customer_acknowledgment_method":
                self.customer_acknowledgment_method or False,
            "customer_acknowledgment_ref":
                self.customer_acknowledgment_ref or False,
        })
        # Link back BEFORE submitting so the NCR write inside
        # action_submit_for_eng_review sees the waiver_id.
        self.mi_check_id.sudo().write({"deviation_waiver_id": waiver.id})
        waiver.action_submit_for_eng_review()
        return {
            "type": "ir.actions.act_window",
            "name": _("Deviation Waiver"),
            "res_model": "southbrook.deviation.waiver",
            "res_id": waiver.id,
            "view_mode": "form",
            "target": "current",
        }
