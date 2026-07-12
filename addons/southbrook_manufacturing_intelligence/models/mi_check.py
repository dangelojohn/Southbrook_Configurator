# SPDX-License-Identifier: LGPL-3.0-only
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


_logger = logging.getLogger(__name__)

SEVERITY_RANK = {"blocker": 0, "warning": 1, "info": 2}

# W024 — Auto-fix mapping. Keys are MI check categories that have a
# known, deterministic remediation; values are the method name on this
# model that runs the fix. Categories absent from this mapping are not
# auto-fixable and the inline button hides.
#
# All handlers MUST be idempotent — re-firing on an already-fixed check
# is a no-op (and the MI recompute that runs at the end will erase
# the check entirely if the underlying condition cleared).
AUTO_FIX_DISPATCH = {
    "cut": "_action_auto_fix_cut",
    "cad": "_action_auto_fix_cad",
}


# W012 — base-level lifecycle state on mi.check.
#
# This is distinct from the inspector-extension `x_sbk_result`
# (pass/fail/rework/hold) added by southbrook_mrp_kitchen_workcenters.
# This `state` field tracks the DEVIATION-WAIVER lifecycle specifically
# so warranty-trace queries can filter on a single canonical column
# without depending on the inspector addon being installed.
#
#   draft                          : default — no deviation in flight
#   pending_deviation_approval     : QC submitted a waiver, eng to review
#   ship_with_deviation            : eng approved — cabinet ships
#
# The state never moves to a terminal "scrap" or "rework" — those flows
# are owned by the inspector extension's x_sbk_result. This Selection
# only models the eng-deviation path so it stays self-contained.
MI_CHECK_STATES = [
    ("draft", "Draft"),
    ("pending_deviation_approval", "Pending Deviation Approval"),
    ("ship_with_deviation", "Ship with Deviation"),
]


class SouthbrookMiCheck(models.Model):
    _name = "southbrook.mi.check"
    _description = "Southbrook Manufacturing Intelligence Check"
    # mail.thread + mail.activity.mixin (W001) give the NCR record
    # chatter, follower-routing, and activity scheduling — required for
    # the 4-tap photo-+-tag-+-route shop-floor workflow. The image
    # widget posts attachments via the chatter pipeline.
    _inherit = ["mail.thread", "mail.activity.mixin"]
    # Order by severity rank then category. Selection values sort by
    # stored string, so 'blocker'/'info'/'warning' alphabetical-DESC
    # produces warning > info > blocker — semantically wrong. We
    # store a numeric rank in `severity_rank` (compute below) and sort
    # by that, then by category for sibling-grouping.
    _order = "severity_rank asc, category, id"

    name = fields.Char(required=True)
    severity = fields.Selection(
        [
            ("info", "Info"),
            ("warning", "Warning"),
            ("blocker", "Blocker"),
        ],
        required=True,
        default="info",
        index=True,
    )
    category = fields.Selection(
        [
            ("cut", "Cut"),
            ("production", "Production"),
            ("assembly", "Assembly"),
            ("install", "Install"),
            ("cad", "CAD"),
            ("hardware", "Hardware"),
            # W025 — First Article Inspection: a category-tagged NCR
            # auto-created when an MO is started on a brand-new (or
            # freshly-versioned) mrp.bom whose `fai_required` flag is
            # True. The mi.check carries the FAI pass/fail buttons and
            # the SoD-enforced sign-off; passing the check flips the
            # BOM.fai_required=False so subsequent MOs on the same
            # BOM no longer get gated.
            ("fai", "First Article Inspection"),
        ],
        required=True,
        default="production",
        index=True,
    )
    message = fields.Text(required=True)
    recommendation = fields.Text()
    # W001 — defect photo captured from the shop floor. fields.Image
    # caps in-DB storage at max_width/max_height (resized server-side
    # on upload) so a 4032x3024 phone capture doesn't bloat the row.
    # 1920x1920 is enough resolution for QA review while staying under
    # ~400 KB per record. The 1st photo lives here; additional photos
    # go to chatter attachments (free via mail.thread inherit above).
    image = fields.Image(
        string="Defect Photo",
        max_width=1920,
        max_height=1920,
        help="Primary defect photo. Attach additional photos via the "
             "chatter below.",
    )
    production_id = fields.Many2one(
        "mrp.production", string="Manufacturing Order", ondelete="cascade", index=True
    )
    production_package_id = fields.Many2one(
        "sb.production.package", string="Production Package", ondelete="cascade", index=True
    )
    active = fields.Boolean(default=True)
    severity_rank = fields.Integer(
        compute="_compute_severity_rank", store=True, index=True,
        help="0 = blocker, 1 = warning, 2 = info. Used to drive _order so "
             "the list view shows the most urgent rows first.",
    )

    @api.depends("severity")
    def _compute_severity_rank(self):
        for rec in self:
            rec.severity_rank = SEVERITY_RANK.get(rec.severity, 99)

    # ------------------------------------------------------------------
    # W024 — Inline auto-fix on MI check rows
    # ------------------------------------------------------------------
    # Per R1.W5 (docs/MFG-REVIEW-R1-mo-lifecycle.md:190): the planner
    # today reads a recommendation sentence and hunts through 3 menus
    # to remediate. We expose an "Auto-Fix" button per row when the
    # check's category maps to a known deterministic remediation
    # (see AUTO_FIX_DISPATCH at module top).
    #
    # `auto_fixable` is a computed boolean (unstored) — the dispatch
    # table is static, the severity check is per-row, no need to burn
    # storage on it. The view uses `invisible="not auto_fixable"` to
    # hide the button where it can't help.
    auto_fixable = fields.Boolean(
        compute="_compute_auto_fixable", store=False,
        help="True iff this check's category maps to a known auto-fix "
             "and the check is currently raising a non-OK severity. "
             "Drives visibility of the inline Auto-Fix button.",
    )

    @api.depends("category", "severity")
    def _compute_auto_fixable(self):
        for rec in self:
            rec.auto_fixable = (
                rec.severity in ("blocker", "warning")
                and rec.category in AUTO_FIX_DISPATCH
            )

    # ------------------------------------------------------------------
    # C2 — 'ship_with_deviation' is the state that lets a cabinet ship WITH a
    # recorded defect; warranty-trace queries key off it. It must only ever be
    # reached through an APPROVED deviation waiver (which the waiver action sets
    # via sudo). The QC group has ORM write on this model, so a raw
    # write({"state": "ship_with_deviation"}) would launder a failing check
    # straight to ship — no waiver, no engineering sign-off, no customer ack.
    # Block the direct transition; only the sudo path (waiver approval) may set it.
    # ------------------------------------------------------------------
    def write(self, vals):
        if not self.env.su and vals.get("state") == "ship_with_deviation":
            raise AccessError(_(
                "A check can only be moved to 'Ship with Deviation' through an "
                "approved deviation waiver (Segregation of Duties + engineering "
                "sign-off + customer acknowledgement), not a direct edit."))
        return super().write(vals)

    def action_auto_fix(self):
        """Run the auto-fix for this check's category.

        Idempotent: re-firing on a check whose underlying condition has
        already been resolved by a prior call is a no-op (the dispatch
        handlers themselves check the current state, and the MI recompute
        at the end will erase the check entirely if it now passes).

        Bulk-safe: walks self, skips checks where auto_fixable is False
        (defensive — view layer already hides the button) or whose MO
        was unlinked between view-fetch and click.
        """
        engine = self.env["southbrook.mi.engine"]
        touched_productions = self.env["mrp.production"]

        for check in self:
            # Auto-fixing one check triggers an MI recompute that may unlink
            # sibling checks (and, if this check is an engine 'cut'/'cad'
            # blocker, this very one) — so a later record in `self` can already
            # be gone. Reading any field on it then raises MissingError. Skip
            # records that no longer exist rather than crash the whole batch.
            if not check.exists():
                continue
            if not check.auto_fixable:
                _logger.debug(
                    "W024 auto-fix: skip check %s — not auto_fixable",
                    check.id,
                )
                continue
            production = check.production_id
            if not production or not production.exists():
                _logger.debug(
                    "W024 auto-fix: skip check %s — no production_id",
                    check.id,
                )
                continue
            handler_name = AUTO_FIX_DISPATCH.get(check.category)
            if not handler_name:
                continue
            try:
                getattr(check, handler_name)()
                touched_productions |= production
            except UserError:
                # Bubble UserError up — it's intentional operator-
                # facing messaging (e.g. FreeCAD bridge disabled).
                raise
            except Exception:  # noqa: BLE001
                _logger.warning(
                    "W024 auto-fix: handler %s raised for check %s "
                    "(MO %s) — recording failure on chatter and "
                    "leaving the check in place.",
                    handler_name, check.id, production.id,
                    exc_info=True,
                )
                production.message_post(body=_(
                    "Auto-fix failed for MI check '%(name)s' "
                    "(category=%(category)s). See server log for "
                    "details; the check remains active.",
                    name=check.name,
                    category=check.category,
                ))

        # Recompute MI status across affected MOs so any blocker that
        # the handler cleared drops out of the check list.
        for production in touched_productions:
            try:
                engine._recompute_production(production)
            except Exception:  # noqa: BLE001
                _logger.warning(
                    "W024 auto-fix: post-fix MI recompute failed for "
                    "MO %s — UI may show stale check until next sweep.",
                    production.id, exc_info=True,
                )
        return True

    # ------------------------------------------------------------------
    # Per-category handlers. Each MUST be idempotent.
    # ------------------------------------------------------------------
    def _action_auto_fix_cut(self):
        """Attempt to generate the missing cutlist via the P3 builder.

        Idempotent: if a cutlist already exists on the production
        package, returns early. The recompute that follows in
        action_auto_fix will then erase the Missing-cutlist check.

        Falls through to a chatter note when:
          - the production has no source order line
          - the configurator config is incomplete (Door Style=Custom,
            missing Width attribute)
          - the build itself raises (logged via the engine's existing
            try/except)
        """
        self.ensure_one()
        engine = self.env["southbrook.mi.engine"]
        production = self.production_id
        if not production:
            return False

        # Idempotency check — cutlist already present.
        existing_cutlist = engine._production_cutlist(production)
        if existing_cutlist:
            production.message_post(body=_(
                "Auto-fix (W024): cutlist already exists for this MO "
                "— no action taken."
            ))
            return True

        order_line = engine._p3_source_order_line(production)
        if not order_line:
            production.message_post(body=_(
                "Auto-fix (W024): cannot auto-generate cutlist — no "
                "source sale.order.line resolvable for this MO."
            ))
            return False

        if not engine._p3_config_is_complete(order_line):
            production.message_post(body=_(
                "Auto-fix (W024): configurator config is incomplete "
                "(Door Style=Custom, or missing Width) — operator "
                "must complete the configuration before the cutlist "
                "can be generated deterministically."
            ))
            return False

        package = engine._p3_try_emit_package(order_line, production)
        if package:
            production.message_post(body=_(
                "Auto-fix (W024): cutlist generated for MO %(name)s "
                "via P3 builder.",
                name=production.name,
            ))
            return True
        # The engine logged the failure detail; surface a planner-
        # readable note on chatter.
        production.message_post(body=_(
            "Auto-fix (W024): P3 builder did not return a package. "
            "See server log for the failure detail."
        ))
        return False

    def _action_auto_fix_cad(self):
        """Re-fire the FreeCAD bridge render job for the parent MO.

        Idempotent: when x_cad_status is already 'done', returns early
        with a chatter note. When 'rendering', returns early (a job is
        already in flight). Otherwise re-POSTs the render job via the
        bridge's existing action_regenerate_cad.

        Falls through to a chatter note when the FreeCAD bridge addon
        isn't installed (no action_regenerate_cad method on the model)
        or when the bridge gate is disabled (UserError bubbles up).
        """
        self.ensure_one()
        production = self.production_id
        if not production:
            return False

        if not hasattr(production, "action_regenerate_cad"):
            production.message_post(body=_(
                "Auto-fix (W024): FreeCAD bridge addon is not "
                "installed; cannot regenerate CAD. Resolve the CAD "
                "artifact manually."
            ))
            return False

        cad_status = getattr(production, "x_cad_status", False)
        if cad_status == "done":
            production.message_post(body=_(
                "Auto-fix (W024): CAD is already 'done' for this MO "
                "— no action taken."
            ))
            return True
        if cad_status == "rendering":
            production.message_post(body=_(
                "Auto-fix (W024): CAD render is already in flight "
                "for this MO — no action taken (wait for callback)."
            ))
            return True

        production.action_regenerate_cad()
        production.message_post(body=_(
            "Auto-fix (W024): CAD render job re-posted to the FreeCAD "
            "bridge for MO %(name)s.",
            name=production.name,
        ))
        return True

    @api.model
    def action_auto_fix_all_selected(self):
        """Server-action entry point — runs auto_fix across every
        selected row that is auto_fixable. Skips the rest silently
        (per W024 spec: bulk-fix targets only the fixable subset).

        Resolves selection from context active_ids when called from
        a list-view server action; falls back to self when called
        from an arbitrary recordset.
        """
        rows = self
        active_ids = self.env.context.get("active_ids")
        if active_ids:
            rows = self.browse(active_ids)
        fixable = rows.filtered(lambda r: r.auto_fixable)
        if not fixable:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Auto-Fix"),
                    "message": _("No auto-fixable checks in the "
                                 "current selection."),
                    "type": "warning",
                    "sticky": False,
                },
            }
        fixable.action_auto_fix()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Auto-Fix"),
                "message": _("Ran auto-fix on %d check(s). "
                             "MI status recomputed."),
                "type": "success",
                "sticky": False,
            },
        }

    # ------------------------------------------------------------------
    # W012 — engineering deviation approval flow
    # ------------------------------------------------------------------
    state = fields.Selection(
        MI_CHECK_STATES,
        string="Deviation State",
        default="draft", required=True, tracking=True, index=True, copy=False,
        help="Lifecycle of the engineering-deviation path for this "
             "NCR. Draft = nothing in flight. pending_deviation_approval = "
             "QC submitted a waiver and eng is reviewing. "
             "ship_with_deviation = eng approved; cabinet ships with "
             "the recorded defect. See southbrook.deviation.waiver.",
    )
    deviation_waiver_id = fields.Many2one(
        "southbrook.deviation.waiver",
        string="Deviation Waiver",
        copy=False, readonly=True, index=True, tracking=True,
        help="Set by the deviation-approval wizard when QC submits a "
             "waiver against this NCR. One waiver per NCR — re-opening "
             "the same NCR for a second waiver requires the first to "
             "be rejected (state→draft).",
    )
    deviation_waiver_count = fields.Integer(
        compute="_compute_deviation_waiver_count",
        help="Smart-button counter — 0 or 1 (one waiver per NCR).",
    )

    @api.depends("deviation_waiver_id")
    def _compute_deviation_waiver_count(self):
        for rec in self:
            rec.deviation_waiver_count = 1 if rec.deviation_waiver_id else 0

    def action_approve_deviation(self):
        """Open the QC-side wizard to draft a deviation waiver.

        Per spec the inspector clicks this from the mi.check form,
        captures the defect summary + customer-ack details, and the
        wizard creates the southbrook.deviation.waiver in draft +
        flips this NCR to pending_deviation_approval on submit.
        """
        self.ensure_one()
        if self.deviation_waiver_id and \
                self.deviation_waiver_id.state in ("eng_review", "approved"):
            raise UserError(_(
                "This NCR already has an active waiver (%(name)s, "
                "state=%(state)s). Reject the existing waiver first if "
                "you need to start over.",
                name=self.deviation_waiver_id.name,
                state=self.deviation_waiver_id.state,
            ))
        Wizard = self.env["southbrook.deviation.approval.wizard"]
        wizard = Wizard.create({
            "mi_check_id": self.id,
            "defect_summary": (
                (self.message or "")
                + (("\n\nRecommendation:\n" + self.recommendation)
                   if self.recommendation else "")
            ).strip() or False,
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Request Deviation Approval"),
            "res_model": "southbrook.deviation.approval.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_open_deviation_waiver(self):
        """Smart button — open the waiver record from the NCR form."""
        self.ensure_one()
        if not self.deviation_waiver_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "southbrook.deviation.waiver",
            "res_id": self.deviation_waiver_id.id,
            "view_mode": "form",
            "target": "current",
        }

    # ------------------------------------------------------------------
    # W025 — First Article Inspection pass/fail buttons
    # ------------------------------------------------------------------
    # These run on the FAI mi.check that was auto-created when the first
    # MO of a `fai_required=True` BOM was created (see
    # mrp.production._auto_create_fai_check). They are idempotent:
    #
    #   * action_fai_pass on an already-passed BOM is a no-op (the BOM
    #     flag is already False; the MO fai_status is already 'passed'
    #     via the stored compute).
    #   * action_fai_fail on an already-failed check just refreshes the
    #     fail metadata + chatter line.
    #
    # SoD: the inspector firing pass MUST NOT be the user who created
    # the underlying BOM (or, when PG release is involved, the user who
    # executed the release). Pattern matches deviation_waiver.action_approve.
    def _check_fai_sod(self, bom):
        """Raise UserError if env.user == BOM creator (or release approver).

        Admin (base.group_system) bypasses — needed for test fixtures
        and emergency overrides.
        """
        if self.env.user.has_group("base.group_system"):
            return
        bom_creator = bom.create_uid
        if bom_creator and bom_creator == self.env.user:
            raise UserError(_(
                "Segregation of Duties: the engineer who created the BOM "
                "(%(creator)s) cannot also sign off the First Article "
                "Inspection. Have a second engineer or QC lead complete "
                "the FAI pass.",
                creator=bom_creator.display_name,
            ))
        # When PG-release is in play, also block the release approver
        # from being the FAI signer. The field may not exist if
        # product_graph_release isn't installed — soft check.
        pg_release_id = getattr(bom, "pg_release_id", False)
        if pg_release_id:
            released_by = getattr(pg_release_id, "released_by_id", False)
            if released_by and released_by == self.env.user:
                raise UserError(_(
                    "Segregation of Duties: the engineer who executed "
                    "the ProductGraph release (%(approver)s) cannot also "
                    "sign off the First Article Inspection.",
                    approver=released_by.display_name,
                ))

    def action_fai_pass(self):
        """Mark this FAI check as passed.

        Idempotent: if the BOM's fai_required flag is already False AND
        this check is already linked as the passing check, returns True
        with no writes. Otherwise:
          * SoD-checks the caller against the BOM creator
          * Stamps BOM.fai_passed_at + fai_passed_by + fai_passing_mi_check_id
          * Flips BOM.fai_required=False
          * Recomputes MO.fai_status (stored compute triggers off bom.fai_required)
        """
        self.ensure_one()
        if self.category != "fai":
            raise UserError(_(
                "action_fai_pass may only be called on a check with "
                "category='fai'. This one is '%(cat)s'.",
                cat=self.category,
            ))
        production = self.production_id
        if not production:
            raise UserError(_(
                "FAI check '%(name)s' has no linked manufacturing order.",
                name=self.name,
            ))
        bom = production.bom_id
        if not bom:
            raise UserError(_(
                "MO %(name)s has no bom_id — cannot complete FAI sign-off.",
                name=production.display_name,
            ))
        # Idempotency check.
        if not bom.fai_required and bom.fai_passing_mi_check_id == self:
            production.message_post(body=_(
                "FAI (W025): already passed for this BOM — no action taken."
            ))
            return True
        # SoD gate.
        self._check_fai_sod(bom)
        # Apply the pass. sudo() because the inspector may not have
        # write rights on mrp.bom directly; the sign-off authority IS
        # the QC role gate, which is enforced by the surrounding UI
        # being on a southbrook.mi.check the inspector owns.
        now = fields.Datetime.now()
        bom.sudo().write({
            "fai_required": False,
            "fai_passed_at": now,
            "fai_passed_by": self.env.user.id,
            "fai_passing_mi_check_id": self.id,
        })
        # Stamp + retire this check — it served its purpose.
        self.write({
            "severity": "info",
            "active": False,
        })
        production.message_post(body=_(
            "<strong>First Article Inspection PASSED</strong> by "
            "%(user)s for BOM <b>%(bom)s</b>. Subsequent MOs against "
            "this BOM will not be FAI-gated.",
            user=self.env.user.display_name,
            bom=bom.display_name,
        ))
        # Force a recompute on the MO so fai_status flips to 'passed'.
        production.modified(["fai_status"])
        return True

    def action_fai_fail(self):
        """Mark this FAI check as failed — MO stays blocked.

        Idempotent: re-firing just refreshes the fail chatter line +
        ensures severity='blocker' (so the MO is unambiguously gated).

        Does NOT flip BOM.fai_required — the BOM is still un-validated.
        The path forward is:
          * rework the cabinet via NCR + action_create_rework_workorder
          * OR raise a deviation waiver via action_approve_deviation
            (W012 flow) for a customer-ack ship-with-deviation
        """
        self.ensure_one()
        if self.category != "fai":
            raise UserError(_(
                "action_fai_fail may only be called on a check with "
                "category='fai'. This one is '%(cat)s'.",
                cat=self.category,
            ))
        production = self.production_id
        # Bump severity to blocker so the MI engine + ready-queue
        # surfaces this prominently.
        if self.severity != "blocker":
            self.write({"severity": "blocker"})
        if production:
            production.message_post(body=_(
                "<strong>First Article Inspection FAILED</strong> by "
                "%(user)s. MO remains blocked until rework completes "
                "(open a new rework WO) OR a deviation waiver is "
                "approved (W012 flow).",
                user=self.env.user.display_name,
            ))
            production.modified(["fai_status"])
        return True
