# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.installer.punchlist — installer + builder walk-through.

Three models in this file because they form one logical workflow:

  southbrook.installer.punchlist.template  — admin-configurable
      master list of inspection items grouped by 6 sections (per
      PRD §7.8). New jobs that open a punchlist clone the template
      items in.

  southbrook.installer.punchlist           — per-job inspection
      record. State machine: draft → in_progress → complete.
      Holds the signature blob, signed_by_name, signed_at; on
      submit_signoff auto-creates a damage flag for every FAIL item
      and a draft account.move for finance.

  southbrook.installer.punchlist.item      — per check.
      Result: pass / minor / fail. Minor needs notes, fail needs
      both notes AND a photo (constraint).

`sign` is an Enterprise-only module and is uninstallable on this CE
deployment — sign-off is captured as a canvas-style Binary signature
(same pattern as southbrook.shipping.unit.delivery_signature from
the QR Kit POD page).
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


_logger = logging.getLogger(__name__)


SECTION = [
    ("A", "A — Upper Cabinets"),
    ("B", "B — Base Cabinets"),
    ("C", "C — Tall / Pantry"),
    ("D", "D — Hardware"),
    ("E", "E — Trim & Finish"),
    ("F", "F — Cleanup"),
]


RESULT = [
    ("pass", "✅ Pass"),
    ("minor", "⚠️ Minor — Note Required"),
    ("fail", "❌ Fail — Photo + Note Required"),
]


PUNCHLIST_STATE = [
    ("draft", "Draft"),
    ("in_progress", "In Progress"),
    ("complete", "Complete"),
    ("cancelled", "Cancelled"),
]


OVERALL_RESULT = [
    ("pass", "✅ Pass — Builder Accepts"),
    ("pass_with_minor", "⚠️ Pass with Minor — Note Filed"),
    ("fail", "❌ Fail — Re-work Required"),
]


class SouthbrookInstallerPunchlistTemplate(models.Model):
    _name = "southbrook.installer.punchlist.template"
    _description = "Installer Punchlist Template"
    _order = "section, sequence, id"
    _rec_name = "description"

    section = fields.Selection(SECTION, required=True, index=True)
    description = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    require_photo_on_fail = fields.Boolean(
        default=True,
        help="When True, a FAIL result on this item requires at "
             "least one attached photo. Defaults True for visual "
             "items (alignment, finish) — disable for non-visual "
             "checks (e.g. drawer slide pressure).",
    )


class SouthbrookInstallerPunchlist(models.Model):
    _name = "southbrook.installer.punchlist"
    _description = "Installer Job Punchlist"
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
        PUNCHLIST_STATE,
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    item_ids = fields.One2many(
        "southbrook.installer.punchlist.item",
        "punchlist_id",
        string="Inspection Items",
    )

    # ── Aggregates ──────────────────────────────────────────────────
    pass_count = fields.Integer(
        compute="_compute_counts",
        store=True,
    )
    minor_count = fields.Integer(
        compute="_compute_counts",
        store=True,
    )
    fail_count = fields.Integer(
        compute="_compute_counts",
        store=True,
    )
    pending_count = fields.Integer(
        compute="_compute_counts",
        store=True,
    )
    overall_result = fields.Selection(
        OVERALL_RESULT,
        compute="_compute_counts",
        store=True,
    )

    # ── Signature (CE-safe alternative to sign.request) ─────────────
    signature_data = fields.Binary(
        string="Builder Signature",
        help="Canvas-captured signature blob (PNG). Replaces "
             "sign.request which is EE-only and uninstallable here.",
    )
    signed_by_name = fields.Char(
        string="Printed Name",
        tracking=True,
    )
    signed_by_role = fields.Char(
        string="Signer Role",
        default="Builder Site Supervisor",
    )
    signed_at = fields.Datetime(
        readonly=True,
        copy=False,
        tracking=True,
    )
    completed_date = fields.Datetime(readonly=True, copy=False)

    # ── Invoice trigger output ──────────────────────────────────────
    invoice_id = fields.Many2one(
        "account.move",
        string="Draft Invoice",
        readonly=True,
        copy=False,
        help="Auto-created draft invoice when sign-off passes "
             "(state in pass / pass_with_minor). Finance finalises "
             "the lines + posts.",
    )

    display_name = fields.Char(
        compute="_compute_display_name",
        store=False,
        recursive=False,
    )

    # Unique per job — one punchlist per job.
    _job_uniq = models.Constraint(
        "unique(job_id)",
        "A punchlist already exists for this job.",
    )

    # ── Computes ────────────────────────────────────────────────────
    @api.depends("job_id.name")
    def _compute_name(self):
        for rec in self:
            rec.name = "%s/PUNCH" % (rec.job_id.name or _("New"))

    @api.depends("name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _("New Punchlist")

    @api.depends("item_ids", "item_ids.result")
    def _compute_counts(self):
        for rec in self:
            items = rec.item_ids
            pass_n = sum(1 for i in items if i.result == "pass")
            minor_n = sum(1 for i in items if i.result == "minor")
            fail_n = sum(1 for i in items if i.result == "fail")
            pending = sum(1 for i in items if not i.result)
            rec.pass_count = pass_n
            rec.minor_count = minor_n
            rec.fail_count = fail_n
            rec.pending_count = pending
            if fail_n:
                rec.overall_result = "fail"
            elif minor_n:
                rec.overall_result = "pass_with_minor"
            elif items and not pending:
                rec.overall_result = "pass"
            else:
                rec.overall_result = False

    # ──────────────────────────────────────────────────────────────────
    # Actions
    # ──────────────────────────────────────────────────────────────────
    def action_open(self):
        """Move from draft → in_progress and auto-spawn items from
        the active templates if no items are present yet."""
        Item = self.env["southbrook.installer.punchlist.item"]
        Template = self.env["southbrook.installer.punchlist.template"]
        for rec in self:
            if rec.state != "draft":
                continue
            if not rec.item_ids:
                templates = Template.search(
                    [("active", "=", True)],
                    order="section, sequence, id",
                )
                Item.create([{
                    "punchlist_id": rec.id,
                    "section": t.section,
                    "description": t.description,
                    "sequence": t.sequence,
                    "template_id": t.id,
                    "require_photo_on_fail": t.require_photo_on_fail,
                } for t in templates])
            rec.write({"state": "in_progress"})
            rec.job_id.message_post(body=_(
                "📋 Punchlist opened — %d inspection item(s) staged.",
            ) % len(rec.item_ids))

    def action_submit_signoff(self):
        """Validate, capture sign-off, spawn fail-flags, create draft
        invoice (if overall is pass/pass_with_minor), and notify
        finance + dispatcher."""
        for rec in self:
            if rec.state == "complete":
                raise UserError(_(
                    "Punchlist %s already complete.") % rec.name)
            if rec.pending_count:
                raise UserError(_(
                    "Cannot sign off %(n)s — %(p)s items still "
                    "pending a result.",
                ) % {"n": rec.name, "p": rec.pending_count})
            if not rec.signature_data:
                raise UserError(_(
                    "Capture a builder signature on %s before "
                    "submitting sign-off.") % rec.name)
            if not (rec.signed_by_name or "").strip():
                raise UserError(_(
                    "Enter the printed name of the signer on %s.",
                ) % rec.name)

            # Validate each fail-item has its evidence
            for item in rec.item_ids.filtered(lambda i: i.result == "fail"):
                if item.require_photo_on_fail and not item.photo_ids:
                    raise UserError(_(
                        "Item '%(d)s' is a FAIL — attach at least "
                        "one photo before sign-off.",
                    ) % {"d": item.description})
                if not (item.notes or "").strip():
                    raise UserError(_(
                        "Item '%(d)s' is a FAIL — describe the "
                        "issue in Notes before sign-off.",
                    ) % {"d": item.description})

            # Spawn damage flags for every FAIL — these become the
            # builder's punch-list deliverable.
            rec._spawn_fail_flags()

            # Try to create the draft invoice — fail-soft if the
            # account/sale wiring isn't ready.
            if rec.overall_result in ("pass", "pass_with_minor"):
                try:
                    rec._create_draft_invoice()
                except UserError as e:
                    _logger.warning(
                        "Draft invoice skipped on %s: %s", rec.name, e)
                    rec.job_id.message_post(body=_(
                        "⚠ Draft invoice could not be auto-created: "
                        "%s. Finance must create manually.",
                    ) % str(e))

            rec.write({
                "state": "complete",
                "signed_at": fields.Datetime.now(),
                "completed_date": fields.Datetime.now(),
            })
            rec.job_id.message_post(body=_(
                "✍ Punchlist %(n)s signed off by <b>%(who)s</b> "
                "(<b>%(o)s</b>). %(p)s pass / %(m)s minor / %(f)s fail.",
            ) % {
                "n": rec.name,
                "who": rec.signed_by_name,
                "o": dict(OVERALL_RESULT).get(rec.overall_result, "?"),
                "p": rec.pass_count,
                "m": rec.minor_count,
                "f": rec.fail_count,
            })

    def _spawn_fail_flags(self):
        """For each FAIL item without an existing linked flag,
        create one as a non-blocking site_damage flag so dispatch
        gets visibility on the deliverable."""
        Flag = self.env["southbrook.damage.flag"]
        for rec in self:
            for item in rec.item_ids.filtered(
                lambda i: i.result == "fail" and not i.deficiency_flag_id
            ):
                # Punchlist FAIL items often don't map to a specific
                # product — we attribute them to a generic site issue.
                # If the item has a product_id pinned, use it; else
                # use the first product on the job's manifest as a
                # heuristic so the flag is creatable.
                product = (item.product_id
                           or rec.job_id.manifest_id.line_ids[:1].product_id)
                if not product:
                    rec.job_id.message_post(body=_(
                        "⚠ Punchlist FAIL on '%(d)s' could not spawn "
                        "a damage flag — no product context. "
                        "Dispatcher must create manually.",
                    ) % {"d": item.description})
                    continue
                flag = Flag.create({
                    "job_id": rec.job_id.id,
                    "product_id": product.id,
                    "issue_type": "site_damage",
                    "urgency": "non_blocking",
                    "qty_affected": 1.0,
                    "description": _(
                        "Punchlist FAIL — %(s)s: %(d)s\n%(notes)s",
                    ) % {
                        "s": dict(SECTION).get(item.section, item.section),
                        "d": item.description,
                        "notes": item.notes or "",
                    },
                    "photo_ids": [(6, 0, item.photo_ids.ids)],
                })
                item.write({"deficiency_flag_id": flag.id})

    def _create_draft_invoice(self):
        """Create a draft account.move (out_invoice) against the job's
        builder contact. Lines are NOT populated — finance picks
        them from the project's sale.order or manually.

        Raises UserError if essential pieces are missing — the caller
        swallows so sign-off still completes.
        """
        self.ensure_one()
        Move = self.env["account.move"]
        if self.invoice_id:
            return self.invoice_id

        partner = self.job_id.builder_contact_id
        if not partner:
            raise UserError(_(
                "Job %s has no builder contact — cannot draft "
                "invoice.") % self.job_id.name)
        # Use the partner's parent_id if it's a contact under a
        # company — invoices go to the company, not the individual.
        invoice_partner = partner.parent_id or partner

        move = Move.create({
            "move_type": "out_invoice",
            "partner_id": invoice_partner.id,
            "invoice_origin": "%s — %s" % (
                self.job_id.name, self.name),
            "ref": _("Cabinet Installation %s") % self.job_id.name,
            "narration": _(
                "Auto-drafted from Southbrook Installer punchlist "
                "%(p)s on job %(j)s (sign-off: %(s)s).\n"
                "Site: %(site)s — Unit %(u)s\n"
                "Finance: confirm lines + post."
            ) % {
                "p": self.name,
                "j": self.job_id.name,
                "s": dict(OVERALL_RESULT).get(self.overall_result, "?"),
                "site": self.job_id.site_address or "?",
                "u": self.job_id.unit_number or "?",
            },
        })
        self.write({"invoice_id": move.id})
        self.job_id.message_post(body=_(
            "💰 Draft invoice <b>%(m)s</b> created (no lines — "
            "Finance to action).",
        ) % {"m": move.name})
        return move

    def action_view_invoice(self):
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_("No invoice has been drafted yet."))
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.invoice_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_cancel(self):
        for rec in self:
            rec.write({"state": "cancelled"})

    def action_print_punchlist_report(self):
        return self.env.ref(
            "southbrook_installer.action_report_installer_job_summary"
        ).report_action(self.job_id)


class SouthbrookInstallerPunchlistItem(models.Model):
    _name = "southbrook.installer.punchlist.item"
    _description = "Installer Job Punchlist Item"
    _order = "punchlist_id, section, sequence, id"

    punchlist_id = fields.Many2one(
        "southbrook.installer.punchlist",
        required=True,
        ondelete="cascade",
        index=True,
    )
    template_id = fields.Many2one(
        "southbrook.installer.punchlist.template",
        ondelete="set null",
        readonly=True,
    )
    section = fields.Selection(SECTION, required=True, index=True)
    description = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    result = fields.Selection(RESULT, tracking=True)
    notes = fields.Text()
    photo_ids = fields.Many2many(
        "ir.attachment",
        "southbrook_installer_punchlist_item_photo_rel",
        "item_id",
        "attachment_id",
        string="Photos",
    )
    photo_count = fields.Integer(
        compute="_compute_photo_count",
        store=True,
    )
    require_photo_on_fail = fields.Boolean(default=True)
    product_id = fields.Many2one(
        "product.product",
        help="Optional product attribution — when set, a FAIL spawns "
             "a damage flag against this product (instead of the "
             "heuristic first-manifest-line fallback).",
    )
    deficiency_flag_id = fields.Many2one(
        "southbrook.damage.flag",
        readonly=True,
        copy=False,
        help="Auto-linked when this item is FAIL and the punchlist "
             "is signed off.",
    )

    @api.depends("photo_ids")
    def _compute_photo_count(self):
        for rec in self:
            rec.photo_count = len(rec.photo_ids)

    @api.constrains("result", "notes", "photo_ids")
    def _check_evidence_required(self):
        for rec in self:
            if rec.result == "minor":
                if not (rec.notes or "").strip():
                    raise ValidationError(_(
                        "Item '%s' marked Minor — notes are required.",
                    ) % rec.description)
            elif rec.result == "fail":
                if rec.require_photo_on_fail and not rec.photo_ids:
                    raise ValidationError(_(
                        "Item '%s' marked Fail — at least one photo "
                        "is required.",
                    ) % rec.description)
                if not (rec.notes or "").strip():
                    raise ValidationError(_(
                        "Item '%s' marked Fail — describe the issue "
                        "in Notes.",
                    ) % rec.description)
