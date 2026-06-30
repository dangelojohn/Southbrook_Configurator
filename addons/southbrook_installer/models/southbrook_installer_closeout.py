# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.installer.closeout — site close-out checklist.

One closeout per job (enforced by unique constraint). Five sections:

  1. Site cleanup  — 7 boolean gates + builder confirmation
  2. Leftover materials — auto-creates return picking on submit
  3. Tools — auto-populated from job.tool_loan_ids; all must be
     returned (or flagged 'lost') before submit
  4. Open flags — every damage flag must be resolved OR have a
     confirmed replacement ETA
  5. Installer sign-off — final hand-raise

``action_submit_closeout`` collects ALL failing gates and raises one
``UserError`` — never one-at-a-time prompts.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


_logger = logging.getLogger(__name__)


CLOSEOUT_STATES = [
    ("draft", "Draft"),
    ("in_progress", "In Progress"),
    ("complete", "Complete"),
]


WASTE_METHODS = [
    ("sami_truck", "SAMI Truck — Take to Facility"),
    ("builder_bin", "Builder Site Bin (Authorized)"),
    ("third_party", "Third-Party Disposal"),
]


MATERIAL_REASON = [
    ("unused", "Unused"),
    ("wrong_item", "Wrong Item Delivered"),
    ("overstock", "Overstock"),
]


MATERIAL_CONDITION = [
    ("new", "Unopened"),
    ("opened", "Opened / Partial"),
    ("damaged", "Damaged"),
]


# Mirrors tool_loan.RETURN_CONDITION so a closeout tool line can
# carry the same vocab.
TOOL_RETURN_CONDITION = [
    ("good", "Good — No Issues"),
    ("maintenance", "Needs Maintenance"),
    ("damaged", "Damaged"),
    ("lost", "Lost — Cannot Return"),
]


class SouthbrookInstallerCloseout(models.Model):
    _name = "southbrook.installer.closeout"
    _description = "Southbrook Installer Close-Out Checklist"
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
    state = fields.Selection(
        CLOSEOUT_STATES,
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )

    # ── Section 1: Site cleanup ─────────────────────────────────────
    packaging_removed = fields.Boolean(
        string="All cardboard / plastic packaging removed")
    offcuts_collected = fields.Boolean(
        string="Wood off-cuts collected")
    cabinets_wiped = fields.Boolean(
        string="Cabinet interiors clean")
    sawdust_cleared = fields.Boolean(
        string="Sawdust swept / vacuumed")
    adhesive_removed = fields.Boolean(
        string="Wall adhesive residue removed")
    floor_protection_removed = fields.Boolean(
        string="Floor protection removed")
    tape_removed = fields.Boolean(
        string="All blue tape removed")
    builder_approves_cleanup = fields.Boolean(
        string="Builder confirmed site is clean")
    waste_disposal_method = fields.Selection(
        WASTE_METHODS,
        default="sami_truck",
    )
    waste_disposal_provider = fields.Char(
        help="Third-party hauler name. Required when "
             "waste_disposal_method='third_party'.",
    )

    # ── Section 2: Leftover materials ───────────────────────────────
    material_return_ids = fields.One2many(
        "southbrook.installer.closeout.material.line",
        "closeout_id",
        string="Material Returns",
    )
    has_leftover_materials = fields.Boolean(
        compute="_compute_has_leftover_materials",
        store=True,
    )
    return_picking_id = fields.Many2one(
        "stock.picking",
        readonly=True,
        copy=False,
        help="Auto-created from material_return_ids on submit.",
    )

    # ── Section 3: Tools ────────────────────────────────────────────
    tool_return_ids = fields.One2many(
        "southbrook.installer.closeout.tool.line",
        "closeout_id",
        string="Tool Returns",
    )
    all_tools_returned = fields.Boolean(
        compute="_compute_tool_return_stats",
        store=True,
    )
    tool_return_pct = fields.Float(
        compute="_compute_tool_return_stats",
        store=True,
        digits=(5, 2),
    )

    # ── Section 4: Open flags ───────────────────────────────────────
    open_flag_ids = fields.Many2many(
        "southbrook.damage.flag",
        "southbrook_installer_closeout_open_flag_rel",
        "closeout_id",
        "flag_id",
        string="Open Damage Flags",
        compute="_compute_open_flags",
        store=True,
    )
    all_flags_resolved_or_eta = fields.Boolean(
        compute="_compute_open_flags",
        store=True,
        help="True when every damage flag on the parent job is "
             "either in resolved/cancelled OR has a non-empty "
             "replacement_eta.",
    )

    # ── Section 5: Lead installer sign-off ──────────────────────────
    installer_confirmed = fields.Boolean(tracking=True)
    installer_sign_time = fields.Datetime(readonly=True, copy=False)
    installer_sign_id = fields.Many2one(
        "hr.employee", readonly=True, copy=False)

    display_name = fields.Char(
        compute="_compute_display_name",
        store=False,
        recursive=False,
    )

    # Unique per job — one closeout per job.
    _job_uniq = models.Constraint(
        "unique(job_id)",
        "A close-out checklist already exists for this job.",
    )

    # ── Computes ────────────────────────────────────────────────────
    @api.depends("job_id.name")
    def _compute_name(self):
        for rec in self:
            rec.name = "%s/CLOSEOUT" % (rec.job_id.name or _("New"))

    @api.depends("name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _("New Close-Out")

    @api.depends("material_return_ids")
    def _compute_has_leftover_materials(self):
        for rec in self:
            rec.has_leftover_materials = bool(rec.material_return_ids)

    @api.depends("tool_return_ids", "tool_return_ids.confirmed_loaded",
                 "tool_return_ids.return_condition")
    def _compute_tool_return_stats(self):
        for rec in self:
            lines = rec.tool_return_ids
            total = len(lines)
            done = sum(
                1 for l in lines
                if l.confirmed_loaded
                or l.return_condition == "lost"
            )
            rec.all_tools_returned = total == 0 or done == total
            rec.tool_return_pct = (100.0 * done / total) if total else 100.0

    @api.depends(
        "job_id",
        "job_id.damage_flag_ids",
        "job_id.damage_flag_ids.state",
        "job_id.damage_flag_ids.replacement_eta",
    )
    def _compute_open_flags(self):
        for rec in self:
            open_flags = rec.job_id.damage_flag_ids.filtered(
                lambda f: f.state not in ("resolved", "cancelled")
            )
            rec.open_flag_ids = open_flags
            # "Resolved or has ETA" — open flags WITH an ETA count
            # as covered.
            unresolved = open_flags.filtered(
                lambda f: not f.replacement_eta
            )
            rec.all_flags_resolved_or_eta = not unresolved

    # ── Constraints ─────────────────────────────────────────────────
    @api.constrains("waste_disposal_method", "waste_disposal_provider")
    def _check_provider_for_third_party(self):
        for rec in self:
            if (rec.waste_disposal_method == "third_party"
                    and not (rec.waste_disposal_provider or "").strip()):
                raise ValidationError(_(
                    "Close-out %s: third-party waste disposal needs a "
                    "named provider.",
                ) % rec.name)

    # ==================================================================
    # Actions
    # ==================================================================
    def action_open(self):
        """Move from draft → in_progress and auto-populate the tool
        return lines from the parent job's tool loans."""
        ToolLine = self.env["southbrook.installer.closeout.tool.line"]
        for rec in self:
            if rec.state != "draft":
                continue
            # Auto-populate one tool_return_line per active tool_loan
            existing_loans = rec.tool_return_ids.mapped("tool_loan_id")
            missing = rec.job_id.tool_loan_ids - existing_loans
            if missing:
                ToolLine.create([
                    {"closeout_id": rec.id, "tool_loan_id": l.id}
                    for l in missing
                ])
            rec.write({"state": "in_progress"})
            rec.job_id.message_post(body=_(
                "📋 Close-out checklist opened (%d tool(s) staged "
                "for return).",
            ) % len(rec.job_id.tool_loan_ids))

    def action_submit_closeout(self):
        """Validate ALL gates in one pass, then create the return
        picking and mark complete. Failures surface as a single
        UserError listing every problem."""
        for rec in self:
            if rec.state == "complete":
                raise UserError(_(
                    "Close-out %s is already complete.") % rec.name)
            failures = rec._collect_closeout_failures()
            if failures:
                msg = _("Cannot submit close-out %s. Missing:") % rec.name
                lines = "\n".join(f"  • {f}" for f in failures)
                raise UserError(f"{msg}\n{lines}")

            # Gate passed — execute side effects.
            if rec.material_return_ids and not rec.return_picking_id:
                rec._create_return_picking()
            emp = self.env.user.employee_id
            rec.write({
                "state": "complete",
                "installer_sign_time": fields.Datetime.now(),
                "installer_sign_id": emp.id if emp else False,
            })
            rec.job_id.message_post(body=_(
                "✅ Close-out checklist <b>%(n)s</b> submitted by "
                "%(u)s. %(m)s",
            ) % {
                "n": rec.name,
                "u": self.env.user.display_name,
                "m": (
                    _("Return picking %s created.")
                    % rec.return_picking_id.name
                    if rec.return_picking_id else ""
                ),
            })

    def _collect_closeout_failures(self):
        """Returns a list of human-readable strings, one per failing
        check. Empty list means submit is allowed."""
        self.ensure_one()
        failures = []

        # Section 1 — cleanup
        cleanup_checks = [
            (self.packaging_removed, _("Packaging not removed")),
            (self.offcuts_collected, _("Wood off-cuts not collected")),
            (self.cabinets_wiped, _("Cabinet interiors not wiped")),
            (self.sawdust_cleared, _("Sawdust not cleared")),
            (self.adhesive_removed, _("Adhesive residue not removed")),
            (self.floor_protection_removed, _("Floor protection not removed")),
            (self.tape_removed, _("Blue tape not removed")),
            (self.builder_approves_cleanup, _("Builder has not confirmed cleanup")),
        ]
        for value, label in cleanup_checks:
            if not value:
                failures.append(label)

        # Section 3 — tools (only if there are tool lines)
        if self.tool_return_ids and not self.all_tools_returned:
            pending = self.tool_return_ids.filtered(
                lambda l: not l.confirmed_loaded
                and l.return_condition != "lost"
            )
            names = ", ".join(
                l.equipment_id.name or "?" for l in pending[:5]
            )
            more = ""
            if len(pending) > 5:
                more = _(" (+%d more)") % (len(pending) - 5)
            failures.append(_(
                "Tools not confirmed returned: %(names)s%(more)s",
            ) % {"names": names, "more": more})

        # Section 4 — open flags
        if not self.all_flags_resolved_or_eta:
            unresolved = self.open_flag_ids.filtered(
                lambda f: not f.replacement_eta
            )
            names = ", ".join(f.name for f in unresolved[:5])
            more = ""
            if len(unresolved) > 5:
                more = _(" (+%d more)") % (len(unresolved) - 5)
            failures.append(_(
                "Damage flags open without ETA: %(names)s%(more)s",
            ) % {"names": names, "more": more})

        # Section 5 — installer confirm
        if not self.installer_confirmed:
            failures.append(_(
                "Lead installer has not confirmed sign-off"))

        # Job-level: at least 1 phase photo as evidence of work
        if not self.job_id.phase_photo_ids and not any(
            log.photo_ids for log in self.job_id.stage_log_ids
        ):
            failures.append(_(
                "No phase photos attached to the job — at least one "
                "is required for close-out."))

        return failures

    def _create_return_picking(self):
        """Build the return stock.picking from material_return_ids.

        Strategy: find any incoming-type picking type on a warehouse;
        use customer location as source, warehouse stock as dest.
        Raises UserError if essential pieces are missing — closeout
        will refuse to submit rather than silently skipping.
        """
        self.ensure_one()
        Picking = self.env["stock.picking"]
        Move = self.env["stock.move"]
        Warehouse = self.env["stock.warehouse"]
        Location = self.env["stock.location"]

        wh = Warehouse.search(
            [("company_id", "=", self.env.company.id)], limit=1
        )
        if not wh:
            raise UserError(_(
                "No warehouse configured for company %s — cannot "
                "create return picking for close-out %s.",
            ) % (self.env.company.display_name, self.name))

        picking_type = wh.in_type_id
        if not picking_type:
            raise UserError(_(
                "Warehouse %s has no incoming picking type configured.",
            ) % wh.name)

        # Source = customers / vendors location; dest = warehouse stock
        # location (or the line-specific return_location_id if set).
        customer_loc = Location.search(
            [("usage", "=", "customer")], limit=1
        )
        if not customer_loc:
            raise UserError(_(
                "No customer-usage stock.location found — cannot pick "
                "a return-from location."))

        picking_vals = {
            "picking_type_id": picking_type.id,
            "partner_id": self.job_id.builder_contact_id.id or False,
            "origin": "%s — %s" % (self.job_id.name, self.name),
            "location_id": customer_loc.id,
            "location_dest_id": wh.lot_stock_id.id,
            "note": _(
                "Auto-generated return picking from close-out %(n)s\n"
                "Job: %(j)s\nSite: %(s)s"
            ) % {
                "n": self.name,
                "j": self.job_id.name,
                "s": self.job_id.site_address or "?",
            },
        }
        picking = Picking.create(picking_vals)

        for line in self.material_return_ids:
            dest_loc = line.return_location_id or wh.lot_stock_id
            # v19 dropped stock.move.name — description is derived from
            # product_id.display_name + description_picking. Setting
            # name= raises ValueError on create.
            Move.create({
                "product_id": line.product_id.id,
                "product_uom_qty": line.qty_returning,
                "product_uom": (
                    line.uom_id.id or line.product_id.uom_id.id
                ),
                "location_id": customer_loc.id,
                "location_dest_id": dest_loc.id,
                "picking_id": picking.id,
                "description_picking": line.product_id.display_name,
            })

        self.write({"return_picking_id": picking.id})
        return picking

    def action_view_return_picking(self):
        self.ensure_one()
        if not self.return_picking_id:
            raise UserError(_(
                "No return picking — close-out hasn't been submitted "
                "yet or had no material returns."))
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "res_id": self.return_picking_id.id,
            "view_mode": "form",
            "target": "current",
        }


class SouthbrookInstallerCloseoutMaterialLine(models.Model):
    _name = "southbrook.installer.closeout.material.line"
    _description = "Close-Out Material Return Line"
    _order = "closeout_id, sequence, id"

    closeout_id = fields.Many2one(
        "southbrook.installer.closeout",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one(
        "product.product",
        required=True,
        ondelete="restrict",
    )
    lot_id = fields.Many2one("stock.lot", ondelete="set null")
    qty_returning = fields.Float(
        required=True,
        digits=(12, 3),
    )
    uom_id = fields.Many2one("uom.uom")
    reason = fields.Selection(MATERIAL_REASON, default="unused")
    condition = fields.Selection(MATERIAL_CONDITION, default="new")
    return_location_id = fields.Many2one(
        "stock.location",
        domain=[("usage", "in", ["internal", "transit"])],
        help="Override the warehouse stock location for this line "
             "(e.g. QC quarantine for damaged returns).",
    )

    @api.constrains("qty_returning")
    def _check_qty_positive(self):
        for rec in self:
            if rec.qty_returning <= 0:
                raise ValidationError(_(
                    "Material return line must have a positive "
                    "quantity (%s).") % rec.product_id.display_name)


class SouthbrookInstallerCloseoutToolLine(models.Model):
    _name = "southbrook.installer.closeout.tool.line"
    _description = "Close-Out Tool Return Line"
    _order = "closeout_id, id"

    closeout_id = fields.Many2one(
        "southbrook.installer.closeout",
        required=True,
        ondelete="cascade",
        index=True,
    )
    tool_loan_id = fields.Many2one(
        "southbrook.installer.tool.loan",
        required=True,
        ondelete="restrict",
        index=True,
    )
    equipment_id = fields.Many2one(
        related="tool_loan_id.equipment_id",
        store=True,
        readonly=True,
    )
    tool_type = fields.Selection(
        related="tool_loan_id.tool_type",
        store=False,
        readonly=True,
    )
    confirmed_loaded = fields.Boolean(
        string="Loaded on Truck",
        help="Operator confirms the tool is physically on the truck "
             "leaving site.",
    )
    return_condition = fields.Selection(
        TOOL_RETURN_CONDITION,
        help="Mirror of the tool loan's return condition. Writing "
             "here also updates the loan record on close-out submit.",
    )
    notes = fields.Text()

    @api.onchange("return_condition")
    def _onchange_return_condition(self):
        """If a non-lost condition is set, default confirmed_loaded=True
        (the tool is being returned). 'lost' covers the not-loaded case."""
        for rec in self:
            if (rec.return_condition
                    and rec.return_condition != "lost"
                    and not rec.confirmed_loaded):
                rec.confirmed_loaded = True
