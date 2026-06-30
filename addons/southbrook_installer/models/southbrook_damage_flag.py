# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.damage.flag — field defect + replacement order trigger.

This is the highest-value model in the installer suite (PRD 9.5/10).
On create it:

  1. Posts to the job's chatter with a bold flag summary.
  2. Triggers a bus notification on the ``sami_installer`` channel for
     the dispatcher dashboard (Phase 2.2).
  3. For BLOCKING urgency:
     - Auto-creates a draft purchase.order for the replacement.
     - Spawns a mail.activity on the job for the dispatcher with a
       2-hour deadline.
     - Best-effort SMS to dispatcher (try/except — sms install
       state is checked at runtime, NOT a hard dependency).

Vendor selection for auto-PO is deterministic per v1 spec:

  active seller → company/product match → sequence → min_qty fit →
  clear UserError if nothing qualifies.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


_logger = logging.getLogger(__name__)


ISSUE_TYPE = [
    ("damaged_transit", "Damaged in Transit"),
    ("wrong_sku", "Wrong SKU Delivered"),
    ("wrong_size", "Wrong Size"),
    ("wrong_finish", "Wrong Finish / Colour"),
    ("missing_hardware", "Hardware Missing from Pack"),
    ("site_damage", "Damaged On-Site (not transit)"),
    ("measurement_error", "Measurement Error — New Order"),
    ("qty_short", "Quantity Short"),
    ("missing_item", "Item Not Delivered"),
]


URGENCY = [
    ("blocking", "🔴 BLOCKING — Cannot Continue"),
    ("non_blocking", "🟡 Can Continue Without It"),
]


STATE = [
    ("open", "Open"),
    ("reorder_pending", "Replacement Ordered — Awaiting"),
    ("reorder_confirmed", "Replacement Confirmed by Vendor"),
    ("delivered", "Replacement Delivered"),
    ("resolved", "Resolved"),
    ("cancelled", "Cancelled — No Action Needed"),
]


# Issue types that should auto-fire a replacement PO when blocking.
AUTO_PO_ISSUE_TYPES = {
    "damaged_transit",
    "wrong_sku",
    "wrong_size",
    "wrong_finish",
    "missing_hardware",
    "site_damage",
    "qty_short",
    "missing_item",
}


class SouthbrookDamageFlag(models.Model):
    _name = "southbrook.damage.flag"
    _description = "Southbrook Installer Damage Flag"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"
    _rec_name = "name"

    name = fields.Char(
        default=lambda self: _("New"),
        required=True,
        copy=False,
        readonly=True,
        index=True,
    )
    job_id = fields.Many2one(
        "southbrook.installer.job",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    manifest_line_id = fields.Many2one(
        "southbrook.delivery.manifest.line",
        string="Source Manifest Line",
        ondelete="set null",
        help="Populated when this flag was raised from the delivery "
             "manifest (vs. mid-installation).",
    )
    product_id = fields.Many2one(
        "product.product",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    lot_id = fields.Many2one("stock.lot", ondelete="set null")
    issue_type = fields.Selection(
        ISSUE_TYPE,
        required=True,
        tracking=True,
    )
    description = fields.Text(
        required=True,
        help="Describe the issue — what was wrong, what is needed.",
    )
    qty_affected = fields.Float(
        required=True,
        default=1.0,
        digits=(12, 3),
    )
    urgency = fields.Selection(
        URGENCY,
        required=True,
        default="non_blocking",
        tracking=True,
        index=True,
    )
    state = fields.Selection(
        STATE,
        default="open",
        required=True,
        tracking=True,
        index=True,
    )

    photo_ids = fields.Many2many(
        "ir.attachment",
        "southbrook_damage_flag_photo_rel",
        "flag_id",
        "attachment_id",
        string="Damage Photos",
    )
    photo_count = fields.Integer(
        compute="_compute_photo_count",
        store=True,
    )

    reported_by_id = fields.Many2one(
        "hr.employee",
        readonly=True,
        copy=False,
    )
    reported_time = fields.Datetime(
        default=fields.Datetime.now,
        readonly=True,
        copy=False,
    )

    # ── Replacement workflow ────────────────────────────────────────
    replacement_po_id = fields.Many2one(
        "purchase.order",
        string="Replacement PO",
        ondelete="set null",
        copy=False,
        readonly=True,
        help="Auto-created on blocking damage flag for "
             "replacement-eligible issue types.",
    )
    replacement_product_id = fields.Many2one(
        "product.product",
        string="Replacement Product",
        help="Defaults to product_id. Override when the replacement "
             "is a different SKU (e.g. correct-size replacement).",
    )
    replacement_qty = fields.Float(digits=(12, 3))
    replacement_eta = fields.Datetime(
        string="Expected Replacement ETA",
    )
    replacement_confirmed_by_id = fields.Many2one(
        "hr.employee",
        readonly=True,
        copy=False,
    )
    return_manifest_line_id = fields.Many2one(
        "southbrook.delivery.manifest.line",
        string="Return Manifest Line",
        help="Populated by Phase 1.3 close-out — the line on the "
             "return manifest that ships the damaged item back.",
    )
    dispatcher_notes = fields.Text(
        string="Dispatcher Resolution Notes",
    )
    resolution_time = fields.Datetime(readonly=True, copy=False)
    resolution_duration_hrs = fields.Float(
        compute="_compute_resolution_duration",
        store=True,
        digits=(6, 2),
    )

    # ── Display ─────────────────────────────────────────────────────
    display_name = fields.Char(
        compute="_compute_display_name",
        store=False,
        recursive=False,
    )

    @api.depends("name", "job_id.name", "product_id.display_name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s / %s — %s" % (
                rec.name or "?",
                rec.job_id.name or "?",
                rec.product_id.display_name or "?",
            )

    # ── Constraints ─────────────────────────────────────────────────
    @api.constrains("photo_ids", "state")
    def _check_photo_required(self):
        """At least one photo on submission. Open + draft work-states
        can be created without photos (the operator may attach in a
        follow-up write) — but transitioning to reorder_pending or
        beyond requires evidence."""
        for flag in self:
            if flag.state in ("reorder_pending", "reorder_confirmed",
                              "delivered", "resolved"):
                if not flag.photo_ids:
                    raise ValidationError(_(
                        "Damage flag %(n)s needs at least one photo "
                        "before moving to '%(s)s'.",
                    ) % {"n": flag.name, "s": flag.state})

    @api.constrains("qty_affected", "replacement_qty")
    def _check_qty_positive(self):
        for flag in self:
            if flag.qty_affected <= 0:
                raise ValidationError(_(
                    "Qty Affected must be positive on flag %s.",
                ) % flag.name)
            if flag.replacement_qty and flag.replacement_qty < 0:
                raise ValidationError(_(
                    "Replacement Qty cannot be negative on flag %s.",
                ) % flag.name)

    # ── Computes ────────────────────────────────────────────────────
    @api.depends("photo_ids")
    def _compute_photo_count(self):
        for rec in self:
            rec.photo_count = len(rec.photo_ids)

    @api.depends("reported_time", "resolution_time")
    def _compute_resolution_duration(self):
        for rec in self:
            if rec.reported_time and rec.resolution_time:
                delta = rec.resolution_time - rec.reported_time
                rec.resolution_duration_hrs = delta.total_seconds() / 3600.0
            else:
                rec.resolution_duration_hrs = 0.0

    # ── Onchange ────────────────────────────────────────────────────
    @api.onchange("product_id")
    def _onchange_product_id(self):
        for rec in self:
            if rec.product_id and not rec.replacement_product_id:
                rec.replacement_product_id = rec.product_id
            if rec.qty_affected and not rec.replacement_qty:
                rec.replacement_qty = rec.qty_affected

    # ==================================================================
    # CRUD — the centerpiece of this model
    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        """Allocate sequence, post chatter, fire bus, auto-PO + activity
        + SMS for blocking flags."""
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "southbrook.damage.flag"
                ) or _("FLAG/New")
            # Default replacement_product_id to product_id and
            # replacement_qty to qty_affected if caller didn't set them.
            if vals.get("product_id") and not vals.get("replacement_product_id"):
                vals["replacement_product_id"] = vals["product_id"]
            if vals.get("qty_affected") and not vals.get("replacement_qty"):
                vals["replacement_qty"] = vals["qty_affected"]
            if not vals.get("reported_by_id"):
                emp = self.env.user.employee_id
                if emp:
                    vals["reported_by_id"] = emp.id

        flags = super().create(vals_list)
        for flag in flags:
            flag._post_create_workflow()
        return flags

    def _post_create_workflow(self):
        """Fire all the side effects on a new flag. Each effect is
        wrapped to fail-soft — a failed SMS or bus call must NOT roll
        back the flag itself."""
        self.ensure_one()

        # 1. Chatter on the parent job
        urgency_label = dict(URGENCY).get(self.urgency, self.urgency)
        issue_label = dict(ISSUE_TYPE).get(self.issue_type, self.issue_type)
        self.job_id.message_post(body=_(
            "🚨 <b>%(u)s</b> flag raised by %(reporter)s: %(issue)s on "
            "<b>%(product)s</b> (%(name)s).",
        ) % {
            "u": urgency_label,
            "reporter": self.env.user.display_name,
            "issue": issue_label,
            "product": self.product_id.display_name,
            "name": self.name,
        })

        # 2. Bus notification — dispatcher dashboard listens here.
        try:
            self._notify_dispatcher_bus("flag_created")
        except Exception:  # noqa: BLE001
            _logger.exception(
                "Bus notify failed for flag %s — non-fatal", self.name)

        # 3. Blocking-only side effects
        if self.urgency == "blocking":
            # 3a. Try the auto-PO if this issue type is eligible AND a
            # vendor exists.
            if self.issue_type in AUTO_PO_ISSUE_TYPES:
                try:
                    self._try_create_replacement_po()
                except UserError as e:
                    # No vendor / config issue — log, post to chatter,
                    # don't roll back the flag. Dispatcher handles it.
                    _logger.warning(
                        "Auto-PO skipped on flag %s: %s", self.name, e)
                    self.job_id.message_post(body=_(
                        "⚠ Auto-PO skipped on flag %(n)s: %(reason)s. "
                        "Dispatcher must order manually.",
                    ) % {"n": self.name, "reason": str(e)})
                except Exception:  # noqa: BLE001
                    _logger.exception(
                        "Auto-PO crashed on flag %s — non-fatal", self.name)

            # 3b. Dispatcher activity with 2h deadline
            try:
                self._spawn_dispatcher_activity()
            except Exception:  # noqa: BLE001
                _logger.exception(
                    "Activity spawn failed for flag %s — non-fatal", self.name)

            # 3c. Best-effort SMS
            try:
                self._try_sms_dispatcher()
            except Exception:  # noqa: BLE001
                _logger.exception(
                    "SMS dispatcher failed for flag %s — non-fatal", self.name)

    # ==================================================================
    # Side-effect helpers
    # ==================================================================
    def _notify_dispatcher_bus(self, event_type):
        """Posts on the `sami_installer` bus channel (consumed by the
        OWL dispatcher dashboard in Phase 2.2)."""
        self.ensure_one()
        payload = {
            "job_id": self.job_id.id,
            "job_ref": self.job_id.name,
            "event": event_type,
            "flag_id": self.id,
            "flag_ref": self.name,
            "urgency": self.urgency,
            "issue_type": self.issue_type,
            "product": self.product_id.display_name,
            "state": self.state,
            "timestamp": fields.Datetime.now().isoformat(),
        }
        self.env["bus.bus"]._sendmany([
            ("sami_installer", "installer_update", payload),
        ])

    def _spawn_dispatcher_activity(self):
        """Create a mail.activity on the JOB with a 2-hour deadline,
        assigned to the dispatcher group's first available user."""
        self.ensure_one()
        Activity = self.env["mail.activity.type"]
        # Reuse the generic 'Action To Do' activity if no installer-
        # specific type exists (avoiding a hard dep on a custom type).
        todo = Activity.search(
            [("category", "=", "default")], limit=1
        ) or Activity.search([], limit=1)
        if not todo:
            return
        dispatcher_user = self._find_dispatcher_user()
        if not dispatcher_user:
            return
        self.job_id.activity_schedule(
            activity_type_id=todo.id,
            summary=_("⚠ Blocking damage flag: %s") % self.name,
            note=_(
                "Issue: %(issue)s on %(product)s.\n"
                "Description: %(desc)s\n"
                "Reported by: %(by)s\n"
                "Action: order replacement / authorise on-site fix."
            ) % {
                "issue": dict(ISSUE_TYPE).get(self.issue_type, self.issue_type),
                "product": self.product_id.display_name,
                "desc": self.description,
                "by": self.env.user.display_name,
            },
            user_id=dispatcher_user.id,
            date_deadline=fields.Date.context_today(self),
        )

    def _find_dispatcher_user(self):
        """Return the first active user in the Dispatcher group, or
        the job's lead installer's user as fallback, or False."""
        Users = self.env["res.users"]
        dispatcher_group = self.env.ref(
            "southbrook_installer.group_sami_dispatcher",
            raise_if_not_found=False,
        )
        if dispatcher_group:
            # v19: res.users field is `group_ids`, not `groups_id`
            # (see [[odoo19_res_users_group_ids_rename]]).
            user = Users.search([
                ("group_ids", "in", dispatcher_group.id),
                ("active", "=", True),
            ], limit=1)
            if user:
                return user
        lead = self.job_id.lead_installer_id
        if lead and lead.user_id:
            return lead.user_id
        return False

    def _try_sms_dispatcher(self):
        """Best-effort SMS to dispatcher's phone, if sms is installed
        and a dispatcher with a phone number exists. Failures are
        swallowed by the caller — _post_create_workflow."""
        self.ensure_one()
        dispatcher = self._find_dispatcher_user()
        if not dispatcher or not dispatcher.partner_id:
            return
        partner = dispatcher.partner_id
        phone = partner.mobile or partner.phone
        if not phone:
            return
        # sms module may not be loaded — guard with try.
        SmsApi = self.env.get("sms.api")
        if SmsApi is None:
            return
        body = _("🚨 BLOCKING flag %(n)s on job %(j)s: %(p)s — %(i)s") % {
            "n": self.name,
            "j": self.job_id.name,
            "p": self.product_id.display_name,
            "i": dict(ISSUE_TYPE).get(self.issue_type, self.issue_type),
        }
        SmsApi._send_sms_batch([{
            "res_id": self.id,
            "number": phone,
            "content": body,
        }])

    # ==================================================================
    # Replacement-PO workflow
    # ==================================================================
    def _try_create_replacement_po(self):
        """Public-ish wrapper that picks a vendor + creates a draft PO.
        Raises UserError if no vendor is configured (caller swallows)."""
        self.ensure_one()
        if self.replacement_po_id:
            return self.replacement_po_id

        product = self.replacement_product_id or self.product_id
        qty = self.replacement_qty or self.qty_affected
        if qty <= 0:
            raise UserError(_(
                "Replacement quantity must be positive."))

        seller = self._pick_replacement_vendor(product, qty)
        po = self._build_replacement_po(seller, product, qty)
        self.write({
            "replacement_po_id": po.id,
            "state": "reorder_pending",
        })
        self.job_id.message_post(body=_(
            "🛒 Auto-PO <b>%(po)s</b> created against %(vendor)s for "
            "%(qty)s × %(product)s (flag %(flag)s).",
        ) % {
            "po": po.name,
            "vendor": seller.partner_id.display_name,
            "qty": qty,
            "product": product.display_name,
            "flag": self.name,
        })
        return po

    def _pick_replacement_vendor(self, product, qty):
        """Deterministic seller selection per v1 spec:

          1. Filter to ``product.seller_ids`` with no end date
             (i.e. active sellers).
          2. Prefer sellers in the current company (or no company).
          3. Sort by ``sequence`` ascending.
          4. Take the first seller whose ``min_qty <= qty``; if no
             seller meets min_qty, fall back to the lowest-sequence
             active seller (we'll write a NOTE on the PO).
          5. Raise UserError if no active seller exists at all.
        """
        self.ensure_one()
        today = fields.Date.context_today(self)
        company = self.env.company

        # supplierinfo is keyed off product.template; v19 uses product_tmpl_id
        sellers = product.seller_ids.filtered(
            lambda s: (not s.date_end or s.date_end >= today)
            and (not s.company_id or s.company_id == company)
        ).sorted(key=lambda s: (s.sequence or 0, s.id))

        if not sellers:
            raise UserError(_(
                "No active seller configured for %s. Configure a "
                "vendor on the product before raising replacement "
                "damage flags.",
            ) % product.display_name)

        fitting = sellers.filtered(lambda s: (s.min_qty or 0) <= qty)
        return fitting[0] if fitting else sellers[0]

    def _build_replacement_po(self, seller, product, qty):
        """Build the draft PO from a chosen seller. Encapsulated so
        Phase 2.x can override (e.g. for vendor portals)."""
        self.ensure_one()
        # Vendor-specific product code if set; else product default
        po_vals = {
            "partner_id": seller.partner_id.id,
            "origin": "%s — %s" % (self.job_id.name, self.name),
            "priority": "1" if self.urgency == "blocking" else "0",
            "order_line": [(0, 0, {
                "product_id": product.id,
                "product_qty": qty,
                # v19 removed product.uom_po_id; the single product
                # UoM is product.uom_id, with seller-specific override
                # on the supplierinfo if needed.
                "product_uom_id": (
                    seller.product_uom_id.id if hasattr(seller, "product_uom_id")
                    and seller.product_uom_id else product.uom_id.id
                ),
                "price_unit": seller.price or 0.0,
                "name": "URGENT REPLACEMENT — %(jr)s — %(fr)s\n%(desc)s" % {
                    "jr": self.job_id.name,
                    "fr": self.name,
                    "desc": self.description or "",
                },
                "date_planned": fields.Datetime.now(),
            })],
            # purchase.order field is `note` (singular) in v19,
            # NOT `notes`. Wrong name silently rolls back the create.
            "note": _(
                "Auto-generated by Southbrook Installer damage flag "
                "%(flag)s.\nJob: %(job)s — Site: %(site)s\nIssue: "
                "%(issue)s\nDescription: %(desc)s",
            ) % {
                "flag": self.name,
                "job": self.job_id.name,
                "site": self.job_id.site_address or "(no site)",
                "issue": dict(ISSUE_TYPE).get(self.issue_type, self.issue_type),
                "desc": self.description or "",
            },
        }
        return self.env["purchase.order"].create(po_vals)

    # ==================================================================
    # State-change actions
    # ==================================================================
    def action_create_replacement_po(self):
        """Operator-button equivalent of _try_create_replacement_po.
        Surfaces the UserError so dispatcher sees it directly."""
        for flag in self:
            flag._try_create_replacement_po()
        return True

    def action_confirm_vendor(self):
        """Mark replacement confirmed by vendor (after PO confirmed)."""
        for flag in self:
            if flag.state not in ("reorder_pending",):
                raise UserError(_(
                    "Cannot confirm vendor — flag %s is in state %s.",
                ) % (flag.name, flag.state))
            flag.write({"state": "reorder_confirmed"})
            flag.job_id.message_post(body=_(
                "✅ Vendor confirmed replacement for flag %s.") % flag.name)

    def action_confirm_replacement_delivery(self):
        """Installer confirms the physical replacement on site."""
        for flag in self:
            if not flag.photo_ids:
                raise UserError(_(
                    "Attach at least one photo of the replacement "
                    "before confirming delivery on flag %s.",
                ) % flag.name)
            emp = self.env.user.employee_id
            flag.write({
                "state": "delivered",
                "replacement_confirmed_by_id": emp.id if emp else False,
            })
            flag.job_id.message_post(body=_(
                "📦 Replacement for %(p)s confirmed received on flag %(n)s.",
            ) % {"p": flag.product_id.display_name, "n": flag.name})

    def action_resolve(self):
        """Final terminal-state transition. Triggers job-level
        recompute of is_blocked via the computed field's depends."""
        for flag in self:
            flag.write({
                "state": "resolved",
                "resolution_time": fields.Datetime.now(),
            })
            try:
                flag._notify_dispatcher_bus("flag_resolved")
            except Exception:  # noqa: BLE001
                _logger.exception(
                    "Bus notify failed on resolve %s", flag.name)
            flag.job_id.message_post(body=_(
                "✅ Damage flag %s resolved.") % flag.name)

    def action_cancel(self):
        """Cancel a flag that turned out to be a non-issue."""
        for flag in self:
            flag.write({
                "state": "cancelled",
                "resolution_time": fields.Datetime.now(),
            })
            flag.job_id.message_post(body=_(
                "❌ Damage flag %s cancelled.") % flag.name)

    def action_view_po(self):
        self.ensure_one()
        if not self.replacement_po_id:
            raise UserError(_("No PO is linked to this flag."))
        return {
            "type": "ir.actions.act_window",
            "res_model": "purchase.order",
            "res_id": self.replacement_po_id.id,
            "view_mode": "form",
            "target": "current",
        }
