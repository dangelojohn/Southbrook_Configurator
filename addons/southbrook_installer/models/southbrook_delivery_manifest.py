# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.delivery.manifest — digital delivery receipt for a job.

Layered with ``southbrook.delivery.manifest.line`` (one row per move
line on the source kit picking). Operator confirms each line in one of
four states: pending → ok / damaged / missing.

Critical: ``action_scan_barcode`` matches against three identifiers
(product barcode, lot name, default_code) in priority order and must
return under 200ms on a 250-line manifest (per v1 spec). Achieved by
keying off pre-indexed lookups (the M2o reverse-relation cache + lot
index) instead of looping.

On sign-off, any line in 'damaged' or 'missing' state auto-spawns a
``southbrook.damage.flag`` so the dispatcher dashboard updates live.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


_logger = logging.getLogger(__name__)


MANIFEST_STATES = [
    ("draft", "Draft"),
    ("open", "Open — Confirming Items"),
    ("partial", "Partially Confirmed"),
    ("confirmed", "Fully Confirmed"),
    ("discrepancy", "Confirmed with Discrepancies"),
]


LINE_STATUS = [
    ("pending", "Pending Confirmation"),
    ("ok", "✓ Received — OK"),
    ("damaged", "⚠ Received — Damaged"),
    ("missing", "✗ Not Received"),
]


DAMAGE_TYPE = [
    ("transit", "Damaged in Transit"),
    ("wrong_sku", "Wrong SKU"),
    ("wrong_size", "Wrong Size"),
    ("wrong_finish", "Wrong Finish"),
    ("missing_hardware", "Missing Hardware"),
    ("qty_short", "Quantity Short"),
]


# When a line is signed off as damaged/missing, which damage.flag
# issue_type do we spawn? Maps the manifest-level DAMAGE_TYPE +
# missing-line case onto the damage.flag.ISSUE_TYPE enum.
_LINE_TO_FLAG_ISSUE = {
    "transit": "damaged_transit",
    "wrong_sku": "wrong_sku",
    "wrong_size": "wrong_size",
    "wrong_finish": "wrong_finish",
    "missing_hardware": "missing_hardware",
    "qty_short": "qty_short",
}


class SouthbrookDeliveryManifest(models.Model):
    _name = "southbrook.delivery.manifest"
    _description = "Southbrook Installer Delivery Manifest"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"
    _rec_name = "name"

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
    picking_id = fields.Many2one(
        "stock.picking",
        string="Source Kit Delivery Order",
        ondelete="set null",
        help="Auto-populates the manifest lines from this picking's "
             "move lines when the manifest is opened.",
    )
    state = fields.Selection(
        MANIFEST_STATES,
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    line_ids = fields.One2many(
        "southbrook.delivery.manifest.line",
        "manifest_id",
        string="Manifest Lines",
    )

    # ── Sign-off telemetry ──────────────────────────────────────────
    confirm_date = fields.Datetime(readonly=True, copy=False)
    confirmed_by_id = fields.Many2one(
        "hr.employee",
        readonly=True,
        copy=False,
    )
    driver_name = fields.Char()
    truck_plate = fields.Char()
    delivery_photo_ids = fields.Many2many(
        "ir.attachment",
        "southbrook_delivery_manifest_photo_rel",
        "manifest_id",
        "attachment_id",
        string="Delivery / Truck Photos",
    )
    signature_data = fields.Binary(string="Driver Signature")
    notes = fields.Text()

    # ── Aggregates ──────────────────────────────────────────────────
    total_lines = fields.Integer(
        compute="_compute_line_counts",
        store=True,
    )
    lines_ok = fields.Integer(
        compute="_compute_line_counts",
        store=True,
    )
    lines_damaged = fields.Integer(
        compute="_compute_line_counts",
        store=True,
    )
    lines_missing = fields.Integer(
        compute="_compute_line_counts",
        store=True,
    )
    lines_pending = fields.Integer(
        compute="_compute_line_counts",
        store=True,
    )
    confirmation_pct = fields.Float(
        compute="_compute_line_counts",
        store=True,
        digits=(5, 2),
    )

    display_name = fields.Char(
        compute="_compute_display_name",
        store=False,
        recursive=False,
    )

    # ── Computes ────────────────────────────────────────────────────
    @api.depends("job_id.name")
    def _compute_name(self):
        for rec in self:
            rec.name = (rec.job_id.name or _("New")) + "/MANIFEST"

    @api.depends("name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _("New Manifest")

    @api.depends("line_ids", "line_ids.status")
    def _compute_line_counts(self):
        for rec in self:
            lines = rec.line_ids
            total = len(lines)
            ok = sum(1 for l in lines if l.status == "ok")
            damaged = sum(1 for l in lines if l.status == "damaged")
            missing = sum(1 for l in lines if l.status == "missing")
            pending = sum(1 for l in lines if l.status == "pending")
            rec.total_lines = total
            rec.lines_ok = ok
            rec.lines_damaged = damaged
            rec.lines_missing = missing
            rec.lines_pending = pending
            rec.confirmation_pct = (
                100.0 * (ok + damaged + missing) / total
            ) if total else 0.0

    # ==================================================================
    # Actions
    # ==================================================================
    def action_load_from_picking(self):
        """Populate lines from picking_id.move_line_ids. Idempotent —
        re-running creates only lines for products not yet present."""
        Line = self.env["southbrook.delivery.manifest.line"]
        for manifest in self:
            picking = manifest.picking_id or manifest.job_id.kit_picking_id
            if not picking:
                raise UserError(_(
                    "Manifest %s has no source picking. Link one on "
                    "the job's Delivery tab first.",
                ) % manifest.name)
            existing_products = manifest.line_ids.mapped("product_id")
            seq = max(manifest.line_ids.mapped("sequence") or [0]) + 10
            new_vals = []
            for ml in picking.move_line_ids.sorted("id"):
                if ml.product_id in existing_products:
                    continue
                new_vals.append({
                    "manifest_id": manifest.id,
                    "sequence": seq,
                    "product_id": ml.product_id.id,
                    "lot_id": ml.lot_id.id if ml.lot_id else False,
                    "qty_expected": ml.quantity or ml.product_uom_qty,
                    "uom_id": ml.product_uom_id.id,
                    "move_line_id": ml.id,
                })
                existing_products |= ml.product_id
                seq += 10
            if new_vals:
                Line.create(new_vals)
            # First load → open state
            if manifest.state == "draft":
                manifest.write({"state": "open"})
        return True

    def action_confirm_all_ok(self):
        """Operator convenience: mark every still-pending line ok in
        one tap. Requires at least one delivery photo as evidence."""
        for manifest in self:
            if not manifest.delivery_photo_ids:
                raise UserError(_(
                    "Attach at least one delivery photo on manifest "
                    "%s before bulk-confirming all lines.",
                ) % manifest.name)
            pending = manifest.line_ids.filtered(
                lambda l: l.status == "pending"
            )
            for line in pending:
                line.action_set_ok()
            manifest.message_post(body=_(
                "✅ %(n)s lines bulk-confirmed OK by %(u)s.",
            ) % {"n": len(pending), "u": self.env.user.display_name})

    def action_sign_off(self):
        """Close out the manifest. Determines final state based on
        line status mix; spawns damage.flag for every damaged/missing
        line; flips job.delivery_confirmed via the computed depends."""
        for manifest in self:
            if manifest.state in ("confirmed", "discrepancy"):
                raise UserError(_(
                    "Manifest %s is already signed off.") % manifest.name)
            pending = manifest.line_ids.filtered(
                lambda l: l.status == "pending"
            )
            if pending:
                raise UserError(_(
                    "Cannot sign off %(n)s — %(p)s lines still "
                    "pending. Mark each line OK / Damaged / Missing.",
                ) % {"n": manifest.name, "p": len(pending)})
            emp = self.env.user.employee_id
            has_issues = bool(
                manifest.line_ids.filtered(
                    lambda l: l.status in ("damaged", "missing")
                )
            )
            manifest.write({
                "state": "discrepancy" if has_issues else "confirmed",
                "confirm_date": fields.Datetime.now(),
                "confirmed_by_id": emp.id if emp else False,
            })
            manifest._auto_create_damage_flags()
            manifest.job_id.message_post(body=_(
                "📋 Delivery manifest %(n)s signed off by %(u)s: "
                "%(ok)s OK / %(d)s damaged / %(m)s missing.",
            ) % {
                "n": manifest.name,
                "u": self.env.user.display_name,
                "ok": manifest.lines_ok,
                "d": manifest.lines_damaged,
                "m": manifest.lines_missing,
            })
        return True

    def _auto_create_damage_flags(self):
        """For each damaged/missing line that doesn't already have a
        linked damage flag, create one. Lines with status='ok' or
        status='pending' are ignored."""
        Flag = self.env["southbrook.damage.flag"]
        for manifest in self:
            for line in manifest.line_ids.filtered(
                lambda l: l.status in ("damaged", "missing")
                and not l.damage_flag_id
            ):
                issue_type = (
                    "missing_item" if line.status == "missing"
                    else _LINE_TO_FLAG_ISSUE.get(
                        line.damage_type or "transit", "damaged_transit"
                    )
                )
                # Default urgency: missing/qty_short = blocking,
                # others non_blocking. Operator can escalate later.
                urgency = "blocking" if (
                    line.status == "missing"
                    or line.damage_type == "qty_short"
                ) else "non_blocking"
                qty = (
                    (line.qty_expected - (line.qty_received_ok or 0))
                    if line.status == "missing"
                    else (line.qty_damaged or line.qty_expected)
                )
                flag = Flag.create({
                    "job_id": manifest.job_id.id,
                    "manifest_line_id": line.id,
                    "product_id": line.product_id.id,
                    "lot_id": line.lot_id.id if line.lot_id else False,
                    "issue_type": issue_type,
                    "urgency": urgency,
                    "qty_affected": max(qty, 1.0),
                    "description": (
                        line.damage_description
                        or "Auto-raised from manifest %(n)s line %(s)s."
                        % {"n": manifest.name, "s": line.sequence}
                    ),
                    "photo_ids": [(6, 0, line.photo_ids.ids)],
                })
                line.write({"damage_flag_id": flag.id})

    def action_view_damage_flags(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Damage Flags — %s") % self.name,
            "res_model": "southbrook.damage.flag",
            "view_mode": "list,form",
            "domain": [("manifest_line_id.manifest_id", "=", self.id)],
        }


class SouthbrookDeliveryManifestLine(models.Model):
    _name = "southbrook.delivery.manifest.line"
    _description = "Delivery Manifest Line"
    _order = "manifest_id, sequence, id"

    manifest_id = fields.Many2one(
        "southbrook.delivery.manifest",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one(
        "product.product",
        required=True,
        ondelete="restrict",
        index=True,
    )
    product_name = fields.Char(
        related="product_id.name",
        store=False,
        readonly=True,
    )
    lot_id = fields.Many2one(
        "stock.lot",
        ondelete="set null",
        index=True,
    )
    lot_name = fields.Char(
        related="lot_id.name",
        store=False,
        readonly=True,
    )
    barcode = fields.Char(
        related="product_id.barcode",
        store=False,
        readonly=True,
    )
    qty_expected = fields.Float(
        required=True,
        digits=(12, 3),
    )
    uom_id = fields.Many2one("uom.uom")
    status = fields.Selection(
        LINE_STATUS,
        default="pending",
        required=True,
        index=True,
    )
    qty_received_ok = fields.Float(default=0.0, digits=(12, 3))
    qty_damaged = fields.Float(default=0.0, digits=(12, 3))
    qty_missing = fields.Float(
        compute="_compute_qty_missing",
        store=True,
        digits=(12, 3),
    )
    scanned_by_barcode = fields.Boolean(
        string="Confirmed via Barcode Scan",
        readonly=True,
        copy=False,
    )
    damage_description = fields.Text()
    damage_type = fields.Selection(DAMAGE_TYPE)
    photo_ids = fields.Many2many(
        "ir.attachment",
        "southbrook_manifest_line_photo_rel",
        "line_id",
        "attachment_id",
        string="Line Photos",
    )
    photo_count = fields.Integer(
        compute="_compute_photo_count",
        store=True,
    )
    confirmed_by_id = fields.Many2one("hr.employee", readonly=True, copy=False)
    confirmed_time = fields.Datetime(readonly=True, copy=False)
    damage_flag_id = fields.Many2one(
        "southbrook.damage.flag",
        ondelete="set null",
        readonly=True,
        copy=False,
        help="Linked damage flag if this line was reported damaged or "
             "missing on manifest sign-off.",
    )
    move_line_id = fields.Many2one(
        "stock.move.line",
        ondelete="set null",
        readonly=True,
        help="Source move line from the kit picking.",
    )

    # ── Computes ────────────────────────────────────────────────────
    @api.depends("qty_expected", "qty_received_ok", "qty_damaged")
    def _compute_qty_missing(self):
        for rec in self:
            rec.qty_missing = max(
                (rec.qty_expected or 0)
                - (rec.qty_received_ok or 0)
                - (rec.qty_damaged or 0),
                0.0,
            )

    @api.depends("photo_ids")
    def _compute_photo_count(self):
        for rec in self:
            rec.photo_count = len(rec.photo_ids)

    # ── Constraints ─────────────────────────────────────────────────
    @api.constrains("status", "damage_type", "photo_ids")
    def _check_damage_metadata(self):
        for rec in self:
            if rec.status == "damaged":
                if not rec.damage_type:
                    raise ValidationError(_(
                        "Line for %s: pick a damage type before "
                        "marking damaged.",
                    ) % rec.product_id.display_name)
                if not rec.photo_ids:
                    raise ValidationError(_(
                        "Line for %s: at least one photo is required "
                        "for a damaged line.",
                    ) % rec.product_id.display_name)

    # ==================================================================
    # State-change actions (called by inline buttons on the form)
    # ==================================================================
    def action_set_ok(self):
        """Mark line OK. Records who + when."""
        for rec in self:
            emp = self.env.user.employee_id
            rec.write({
                "status": "ok",
                "qty_received_ok": rec.qty_expected,
                "qty_damaged": 0.0,
                "confirmed_by_id": emp.id if emp else False,
                "confirmed_time": fields.Datetime.now(),
            })

    def action_set_damaged(self):
        """Set status=damaged. Operator should then pick damage_type
        and attach a photo — UI gates the damage_type/photo via the
        constraint above."""
        for rec in self:
            emp = self.env.user.employee_id
            rec.write({
                "status": "damaged",
                "confirmed_by_id": emp.id if emp else False,
                "confirmed_time": fields.Datetime.now(),
            })

    def action_set_missing(self):
        """Set status=missing. No qty received, qty_missing computes
        to the full expected."""
        for rec in self:
            emp = self.env.user.employee_id
            rec.write({
                "status": "missing",
                "qty_received_ok": 0.0,
                "qty_damaged": 0.0,
                "confirmed_by_id": emp.id if emp else False,
                "confirmed_time": fields.Datetime.now(),
            })

    def action_set_pending(self):
        """Operator undo: revert to pending."""
        for rec in self:
            rec.write({
                "status": "pending",
                "confirmed_by_id": False,
                "confirmed_time": False,
            })

    # ==================================================================
    # Barcode scan — critical path
    # ==================================================================
    @api.model
    def scan_barcode_on_manifest(self, manifest_id, barcode_value):
        """Called by the mobile scanner (REST API in Phase 3 + OWL
        widget in Phase 2.2). Resolves the barcode against the lines
        of the given manifest in priority order:

          1. ``product_id.barcode``  (the actual product barcode)
          2. ``lot_id.name``         (serial label scan)
          3. ``product_id.default_code`` (internal reference fallback)

        Returns a JSON-friendly dict.

        Designed to stay under 200ms on a 250-line manifest by doing
        ONE search per priority tier (not N).
        """
        if not barcode_value:
            return {"status": "not_found", "message": _(
                "Empty barcode.")}
        manifest = self.env["southbrook.delivery.manifest"].browse(
            manifest_id
        ).exists()
        if not manifest:
            return {"status": "not_found", "message": _(
                "Unknown manifest.")}
        line = self.search([
            ("manifest_id", "=", manifest.id),
            ("product_id.barcode", "=", barcode_value),
        ], limit=1) or self.search([
            ("manifest_id", "=", manifest.id),
            ("lot_id.name", "=", barcode_value),
        ], limit=1) or self.search([
            ("manifest_id", "=", manifest.id),
            ("product_id.default_code", "=", barcode_value),
        ], limit=1)
        if not line:
            return {
                "status": "not_found",
                "barcode": barcode_value,
                "message": _("No matching line on manifest %s.") % manifest.name,
            }
        if line.status == "ok":
            return {
                "status": "already_confirmed",
                "line_id": line.id,
                "product_name": line.product_id.display_name,
                "message": _("Already confirmed OK."),
            }
        line.action_set_ok()
        line.write({"scanned_by_barcode": True})
        return {
            "status": "ok",
            "line_id": line.id,
            "product_name": line.product_id.display_name,
            "qty_received_ok": line.qty_received_ok,
        }
