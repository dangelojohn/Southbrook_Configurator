# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.asbuilt — finished-cabinet as-built record (SAMI PRD W-08).

The cabinet that ships isn't always the cabinet that was on the BoM
when the MO was confirmed. Mid-MO ECOs version the BoM, operators
record cut-spec deviations, QC catches defects that get reworked,
finishes get substituted. The as-built captures the cabinet AS IT
ACTUALLY LEFT THE FACTORY: BoM version frozen at completion, every
QC inspection linked, every drawing/photo/FreeCAD render attached,
lot + serial for traceability.

Why Phase 4 prerequisite per the production plan:
  - Communities GC / Mattamy volumetric modules require as-built
    records for CSA A277 compliance + warranty traceability.
  - Field service needs the as-built when a homeowner calls about a
    cabinet under warranty 3 years later — what was actually
    delivered, not what the original BoM said.

Lifecycle:
  draft  → created on MO mark_done. Auto-sealed if QC passed all
           checks (no fails / no critical defects), otherwise stays
           draft pending review.
  sealed → immutable audit record. The cabinet that left the
           factory.
  deprecated → preserved for audit but flagged as superseded
           (e.g. cabinet returned + remanufactured under a new MO).

Auto-creation runs in MrpProduction.button_mark_done — see
mrp_production.py in this addon.
"""
from odoo import _, api, fields, models


ASBUILT_STATES = [
    ("draft", "Draft"),
    ("sealed", "Sealed"),
    ("deprecated", "Deprecated"),
]


QC_OVERALL_RESULTS = [
    ("pass", "Pass"),
    ("conditional", "Conditional (rework done)"),
    ("fail", "Fail"),
]


class SouthbrookAsbuilt(models.Model):
    _name = "southbrook.asbuilt"
    _description = "Southbrook As-Built Record"
    _inherit = ["mail.thread", "mail.activity.mixin", "southbrook.qr.mixin"]
    _order = "built_at desc, id desc"
    _qr_kind = "asbuilt"

    name = fields.Char(
        string="As-Built ID",
        default=lambda self: _("New"),
        required=True,
        copy=False,
        readonly=True,
        index=True,
    )
    state = fields.Selection(
        ASBUILT_STATES,
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )

    # --- Source production ---
    production_id = fields.Many2one(
        "mrp.production",
        string="Manufacturing Order",
        required=True,
        index=True,
        ondelete="cascade",
        tracking=True,
    )
    production_package_id = fields.Many2one(
        "sb.production.package",
        string="Production Package",
        index=True,
        ondelete="set null",
    )

    # --- Frozen product + BoM snapshot at build time ---
    product_id = fields.Many2one(
        related="production_id.product_id",
        store=True, readonly=True, index=True,
    )
    bom_id = fields.Many2one(
        related="production_id.bom_id",
        store=True, readonly=True,
    )
    bom_version_snapshot = fields.Integer(
        string="BoM Version (at build)",
        readonly=True,
        copy=False,
        help="Snapshot of the BoM's southbrook_version field at the "
             "moment this as-built was sealed. The BoM may have been "
             "ECO'd since — this is the version that WAS built.",
    )

    # W079 (R4.S8) — cut-spec version snapshot at build time.
    #
    # JTBD: two cabinets built under different cut specs (e.g. before
    # / after an ECO that bumped door_reveal from 3.0 mm to 2.5 mm)
    # must be distinguishable in warranty. The active southbrook.cut.spec
    # carries an auto-incrementing `version` integer; this field
    # snapshots it at asbuilt-create time so the warranty record
    # remains accurate even after subsequent ECOs supersede the spec.
    #
    # Snapshotted in _snapshot_build_context (alongside bom_version_
    # snapshot). Empty when southbrook_plm is not installed or no
    # active cut spec exists at create time — both bucketed as
    # "unknown" in warranty queries (defensive).
    x_sbk_cut_spec_version_at_build = fields.Integer(
        string="Cut Spec Version (at build)",
        readonly=True,
        copy=False,
        index=True,
        help="Snapshot of southbrook.cut.spec.version (the currently-"
             "active cut spec) at the moment this asbuilt was "
             "created. Stable for warranty trace even after subsequent "
             "ECOs supersede the active spec.",
    )

    # --- Identification + traceability ---
    lot_id = fields.Many2one(
        "stock.lot",
        string="Lot / Serial",
        index=True,
        help="The stock.lot of the finished good. Optional but "
             "strongly recommended for warranty + recall traceability.",
    )
    serial_number = fields.Char(
        string="Serial #",
        copy=False,
        help="Customer-visible serial. Maps to the cabinet label.",
    )

    # --- QC linkage ---
    qc_check_ids = fields.Many2many(
        "southbrook.mi.check",
        "southbrook_asbuilt_check_rel",
        "asbuilt_id", "check_id",
        string="QC Checks",
        help="Every QC inspection that touched this MO (pass or fail). "
             "Auto-populated at create from production_id.x_sbk_check_ids "
             "if the underlying field exists; otherwise inspector links "
             "checks manually.",
    )
    qc_overall_result = fields.Selection(
        QC_OVERALL_RESULTS,
        string="QC Result",
        compute="_compute_qc_overall_result",
        store=True,
        help="Aggregated: 'pass' if every linked check is pass, "
             "'conditional' if any failed but the rework WO is done, "
             "'fail' otherwise.",
    )

    # --- Drawings + photos + FreeCAD renders ---
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "southbrook_asbuilt_attach_rel",
        "asbuilt_id", "attachment_id",
        string="Drawings & Photos",
        help="Engineering drawings, FreeCAD renders, floor photos. "
             "Auto-attached at create from MO + production package.",
    )
    attachment_count = fields.Integer(
        compute="_compute_attachment_count")

    # --- Provenance ---
    built_at = fields.Datetime(
        string="Built At",
        default=fields.Datetime.now,
        required=True,
        index=True,
        tracking=True,
    )
    built_by = fields.Many2one(
        "res.users",
        string="Built By",
        default=lambda s: s.env.user,
        tracking=True,
    )
    sealed_at = fields.Datetime(
        string="Sealed At",
        readonly=True,
        copy=False,
    )
    sealed_by = fields.Many2one(
        "res.users",
        string="Sealed By",
        readonly=True,
        copy=False,
    )

    # --- Customer context (related, for filtering + reporting) ---
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Sales Order",
        compute="_compute_sale_order_context",
        store=True, readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        compute="_compute_sale_order_context",
        store=True, readonly=True,
    )
    install_due_date = fields.Date(
        related="production_id.x_sbk_install_due_date",
        store=True, readonly=True,
    )
    cabinet_code = fields.Char(
        related="production_id.x_sbk_cabinet_code",
        store=True, readonly=True,
    )

    # --- Engineering trace (W008, MFG-REVIEW-R4 W4) ---
    # Stored related fields that close the warranty-trace loop:
    # cabinet serial -> MO -> engineering revision in 1 hop instead
    # of the historical 3 hops + 2 archived-record lookups. All four
    # walk production_id.pg_* (added by product_graph_release on
    # mrp.production via PG-112 traceability).
    pg_release_id = fields.Many2one(
        "pg.release",
        string="Engineering Release",
        related="production_id.pg_release_id",
        store=True, readonly=True, index=True,
        help="ProductGraph release that produced this as-built record "
             "(via the MO that consumed the released mrp.bom).",
    )
    pg_revision_code = fields.Char(
        string="Eng Revision",
        related="production_id.pg_revision_code",
        store=True, readonly=True, index=True,
        help="ProductGraph revision code at time of MO release. "
             "One-hop warranty trace from serial -> engineering rev.",
    )
    pg_ebom_id = fields.Many2one(
        "pg.ebom",
        string="Engineering BOM",
        related="production_id.pg_ebom_id",
        store=True, readonly=True, index=True,
        help="ProductGraph EBOM that drove the MRP BOM for this asbuilt.",
    )
    pg_root_item_id = fields.Many2one(
        "pg.item",
        string="Engineering Item",
        related="production_id.pg_root_item_id",
        store=True, readonly=True, index=True,
        help="ProductGraph root item (assembly) for this asbuilt.",
    )

    # --- Free-form ---
    notes = fields.Text(string="Build Notes")

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("attachment_ids")
    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = len(rec.attachment_ids)

    @api.depends("qc_check_ids.x_sbk_result",
                 "qc_check_ids.x_sbk_rework_workorder_id.state")
    def _compute_qc_overall_result(self):
        for rec in self:
            checks = rec.qc_check_ids
            if not checks:
                rec.qc_overall_result = "pass"
                continue
            results = checks.mapped("x_sbk_result") or []
            if any(r == "fail" for r in results):
                # If any fail has a closed rework workorder, treat as
                # conditional. Otherwise — open fail = overall fail.
                fails = checks.filtered(lambda c: c.x_sbk_result == "fail")
                open_fail = any(
                    not c.x_sbk_rework_workorder_id
                    or c.x_sbk_rework_workorder_id.state != "done"
                    for c in fails
                )
                rec.qc_overall_result = "fail" if open_fail else "conditional"
            elif any(r == "rework" for r in results):
                rec.qc_overall_result = "conditional"
            else:
                rec.qc_overall_result = "pass"

    @api.depends("production_id")
    def _compute_sale_order_context(self):
        for rec in self:
            mo = rec.production_id
            order_line = (
                getattr(mo, "sale_line_id", None) if mo else None
            )
            so = order_line.order_id if order_line else False
            rec.sale_order_id = so or False
            rec.partner_id = (so.partner_id if so else False)

    # ------------------------------------------------------------------
    # ORM hooks
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "southbrook.asbuilt") or _("AB/New")
            # W042 (MFG-REVIEW-R5.6) — auto-snapshot lot_id from the
            # MO's lot_producing_id so lot-to-asbuilt warranty trace
            # works without the operator looking it up. Per R5.6
            # baseline, this trace fails ~95% of the time today because
            # nobody stamps the lot manually. If the caller already
            # supplied lot_id, respect it (don't clobber a deliberate
            # override).
            if not vals.get("lot_id") and vals.get("production_id"):
                mo = self.env["mrp.production"].browse(
                    vals["production_id"])
                if mo.exists() and mo.lot_producing_ids:
                    vals["lot_id"] = mo.lot_producing_ids[:1].id
        records = super().create(vals_list)
        # Snapshot BoM version + auto-populate QC checks + attachments
        # at create time so the record carries the build-time truth.
        for rec in records:
            rec._snapshot_build_context()
        return records

    def _snapshot_build_context(self):
        """Capture the build-time context: BoM version, related QC
        checks, MO attachments. Called from create()."""
        self.ensure_one()
        # BoM version snapshot — uses southbrook_version if the plm
        # addon is installed (it adds the field to mrp.bom). Fallback
        # to 1 when the addon isn't there.
        bom = self.production_id.bom_id
        if bom and "southbrook_version" in bom._fields:
            self.bom_version_snapshot = bom.southbrook_version or 1
        # W079 — cut-spec version snapshot. Soft-resolve so the asbuilt
        # creation never breaks when southbrook_plm is uninstalled or
        # no active spec exists.
        if "southbrook.cut.spec" in self.env:
            CutSpec = self.env["southbrook.cut.spec"].sudo()
            active = CutSpec._get_active()
            if active:
                self.x_sbk_cut_spec_version_at_build = active.version or 1
        # Pull QC checks tied to this MO. The southbrook.mi.check
        # model has production_id (canonical link).
        Check = self.env["southbrook.mi.check"]
        checks = Check.search([
            ("production_id", "=", self.production_id.id),
        ])
        if checks:
            self.qc_check_ids = [(6, 0, checks.ids)]
        # Pull attachments tied to this MO (drawings, renders).
        Attach = self.env["ir.attachment"]
        attachments = Attach.search([
            ("res_model", "=", "mrp.production"),
            ("res_id", "=", self.production_id.id),
        ])
        if attachments:
            self.attachment_ids = [(6, 0, attachments.ids)]

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------
    def action_seal(self):
        """Lock the record as immutable. Only authorized users
        (PLM Approver) can seal; once sealed, the form is read-only."""
        for rec in self:
            if rec.state == "sealed":
                continue
            rec.write({
                "state": "sealed",
                "sealed_at": fields.Datetime.now(),
                "sealed_by": self.env.user.id,
            })
            rec.message_post(
                body=_("As-built sealed by %s.") %
                self.env.user.display_name,
            )

    def action_deprecate(self):
        for rec in self:
            rec.state = "deprecated"
            rec.message_post(
                body=_("As-built deprecated by %s.") %
                self.env.user.display_name,
            )

    def action_open_attachments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Drawings & Photos"),
            "res_model": "ir.attachment",
            "view_mode": "kanban,list,form",
            "domain": [("id", "in", self.attachment_ids.ids)],
            "context": {
                "default_res_model": "southbrook.asbuilt",
                "default_res_id": self.id,
            },
        }
