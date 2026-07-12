# SPDX-License-Identifier: LGPL-3.0-only
"""mrp.workorder — kitchen-specific costing extensions.

Native Odoo 19 fields already cover the basics:
  duration            actual minutes worked
  duration_expected   expected minutes (Odoo's own)
  costs_hour          hourly cost from workcenter
  direct_cost         actual cost from Odoo's compute
  duration_percent    actual vs expected ratio

This module adds Southbrook-specific fields per brief §13 that the
kitchen reports need but Odoo doesn't:

  x_sbk_kitchen_expected_min   what the operation-template formula
                               produced (parallel to Odoo's
                               duration_expected; kept separate so
                               the planner can audit which engine
                               produced which number)
  x_sbk_variance_min           actual − x_sbk_kitchen_expected_min
  x_sbk_estimated_cost         x_sbk_kitchen_expected_min × hourly
  x_sbk_actual_cost            duration × hourly (mirrors direct_cost
                               but reads costs_hour from THE work
                               center, not whatever Odoo's compute
                               cached — useful when rates changed
                               mid-run)
  x_sbk_cost_variance          actual − estimated
  x_sbk_rework_count           # of rework checks tied to this WO
  x_sbk_rework_cost            cost contribution from rework
                               work orders linked back via
                               x_sbk_rework_workorder_id on the
                               mi.check
  x_sbk_downtime_min           sum of attached downtime durations
  x_sbk_downtime_cost          sum of attached downtime costs

W011 (2026-06-27) — form-open scan log
=====================================

When an operator opens a WO from the kanban/form (not by scanning a
QR), we synthesize a `southbrook.qr.scan.log` row with
``action='form_open'`` so the defect-context window in
``DefectQrKind._resolve_workorder_from_context`` still resolves to
the WO actually on screen. Without this, the first defect scan after
a tap-open silently falls back to the *previous* scan target — a
quiet attribution bug that R2.2 of MFG-REVIEW-R2 calls out as the
blocker for the tablet-kanban (W014) work.

Guards: only fires for single-record web_read calls made from a real
HTTP request that is NOT a cron, NOT a test harness, NOT the QR scan
controller itself (which already writes its own log row), and NOT
when the same user has form-opened the same WO within the last
``_FORM_OPEN_DEDUPE_SEC`` seconds.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


# Coalesce window for repeat form-opens of the same WO by the same
# user. Form views in v19 fire web_read on every reload / drawer flip
# / breadcrumb hop — without dedupe we'd write a row per render and
# pollute both the audit log AND the defect-context resolver (which
# only takes order desc, limit=1, so the spam doesn't break it but
# clutters investigation).
_FORM_OPEN_DEDUPE_SEC = 30


class MrpWorkorder(models.Model):
    # v19 core dropped mail.thread from mrp.workorder (prod's older build had
    # it). This module posts shop-floor chatter to the work order in several
    # places (downtime notify W069, raise-ECO W034, subcontract W066, report-
    # problem W040) — restore the mixin so wo.message_post / .message_ids work.
    _inherit = ["mrp.workorder", "southbrook.qr.mixin", "mail.thread"]
    _qr_kind = "wo"

    # ------------------------------------------------------------------
    # W014 — Tablet kanban surface (MFG-REVIEW R2.1 / R8.13)
    #
    # The kitchen "cabinet code" + "room" identifiers live on
    # mrp.production (the MO). The tablet kanban needs them rendered
    # inline on each WO card; expose them here as stored related fields
    # so the kanban template can read them and the search filter can
    # group by room without joining at query time.
    #
    # Stored so kanban grouping / list filters are cheap; the MO sets
    # these at MO-create time and they rarely change after, so the cost
    # of the related cache is negligible vs the read amplification a
    # non-stored related would inflict on every kanban refresh.
    # ------------------------------------------------------------------
    x_sbk_cabinet_code = fields.Char(
        string="Cabinet Code",
        related="production_id.x_sbk_cabinet_code",
        store=True,
        readonly=True,
        help="The cabinet identifier this WO produces. Surfaced from "
             "mrp.production for the tablet kanban (W014) so the "
             "operator sees what they're building without opening the "
             "WO form.",
    )
    x_sbk_kitchen_room = fields.Char(
        string="Kitchen Room",
        related="production_id.x_sbk_kitchen_room",
        store=True,
        readonly=True,
        help="The kitchen room (e.g. 'Main Kitchen', 'Pantry') this WO "
             "ships to. Surfaced from mrp.production for the tablet "
             "kanban (W014).",
    )

    # ------------------------------------------------------------------
    # Duration variance (M2 formula vs native expected)
    # ------------------------------------------------------------------
    x_sbk_kitchen_expected_min = fields.Float(
        string="Kitchen Expected (min)",
        help="Expected duration as computed by the operation-template "
             "duration formula. Parallel to Odoo's duration_expected "
             "so the planner can audit which estimate came from which "
             "engine.",
    )
    x_sbk_variance_min = fields.Float(
        string="Variance (min)",
        compute="_compute_x_sbk_variance",
        store=True,
        help="duration − x_sbk_kitchen_expected_min. Positive = over "
             "budget; negative = under.",
    )

    # ------------------------------------------------------------------
    # Costing fields
    # ------------------------------------------------------------------
    x_sbk_estimated_cost = fields.Float(
        string="Estimated Cost",
        compute="_compute_x_sbk_costs",
        store=True,
        digits="Product Price",
    )
    x_sbk_actual_cost = fields.Float(
        string="Actual Cost",
        compute="_compute_x_sbk_costs",
        store=True,
        digits="Product Price",
    )
    x_sbk_cost_variance = fields.Float(
        string="Cost Variance",
        compute="_compute_x_sbk_costs",
        store=True,
        digits="Product Price",
    )

    # ------------------------------------------------------------------
    # Rework metrics (rolls up southbrook.mi.check records)
    # ------------------------------------------------------------------
    x_sbk_rework_count = fields.Integer(
        string="Rework Checks",
        compute="_compute_x_sbk_rework_metrics",
        store=False,
    )
    x_sbk_rework_cost = fields.Float(
        string="Rework Cost",
        compute="_compute_x_sbk_rework_metrics",
        store=False,
        digits="Product Price",
        help="Sum of duration cost across rework work orders that "
             "trace back to this WO via x_sbk_rework_workorder_id on "
             "southbrook.mi.check records.",
    )

    # ------------------------------------------------------------------
    # Labor productivity (SAMI PRD N-13, 2026-06-25)
    # qty_producing / (duration / 60.0) → units per operator-hour.
    # Stored so MI dashboards + per-workcenter aggregations work.
    # ------------------------------------------------------------------
    x_sbk_units_per_op_hour = fields.Float(
        string="Units / Operator-Hour",
        compute="_compute_x_sbk_units_per_op_hour",
        store=True,
        digits=(8, 3),
        help="qty_producing divided by actual duration in hours. "
             "Cell-level productivity KPI per SAMI PRD N-13. "
             "Zero if duration is zero (WO not yet started or finished "
             "with no time logged).",
    )

    # ------------------------------------------------------------------
    # W054 (R2.12, 2026-06-27) — operator-visible time tracking.
    #
    # JTBD: operators are productivity-comp'd but the native "Time
    # Tracking" tab on the WO form is gated by mrp.group_mrp_manager
    # — they cannot audit their own time. Add a filtered surface that
    # shows ONLY the current user's productivity rows for this WO so
    # an operator can verify "did the system credit me for that 90min
    # block I logged before lunch?"
    #
    # Two fields:
    #   x_sbk_my_time_ids        — filtered One2many on time_ids
    #                               with domain user_id == uid
    #   x_sbk_my_time_today_min  — total minutes the current user has
    #                               logged on this WO so far today
    #
    # Both fields are non-stored / context-dependent (they vary per
    # viewer); the field semantics MUST resolve under env.uid at read
    # time. Implemented as @api.depends_context('uid') computes.
    #
    # Security: we filter by user_id on the native mrp.workcenter.
    # productivity rows, which is the only operator-attribution column
    # the native model carries in v19 CE. No employee-level filter is
    # possible at the productivity layer; this is the tightest filter
    # the model supports.
    # ------------------------------------------------------------------
    x_sbk_my_time_ids = fields.One2many(
        "mrp.workcenter.productivity",
        compute="_compute_x_sbk_my_time_ids",
        string="My Time Logs",
        help="Productivity rows on this WO that belong to the current "
             "user. Operators use this to audit their own credited "
             "time without seeing colleagues' rows.",
    )
    x_sbk_my_time_today_min = fields.Float(
        compute="_compute_x_sbk_my_time_today_min",
        string="My Time Today (min)",
        digits=(8, 1),
        help="Total minutes the current user has logged on this WO "
             "since 00:00 of the local server day. Surfaces on the "
             "tablet kanban card as a small badge so the operator "
             "sees their accumulated time at a glance.",
    )

    @api.depends_context("uid")
    @api.depends("time_ids", "time_ids.user_id")
    def _compute_x_sbk_my_time_ids(self):
        for wo in self:
            wo.x_sbk_my_time_ids = wo.time_ids.filtered(
                lambda t: t.user_id.id == self.env.uid
            )

    @api.depends_context("uid")
    @api.depends("time_ids", "time_ids.user_id",
                 "time_ids.duration", "time_ids.date_start")
    def _compute_x_sbk_my_time_today_min(self):
        from datetime import datetime, time as dtime
        # "Today" anchored to the current user's day in server-local
        # tz. We use a naive midnight on the server's date — Odoo's
        # date_start is stored UTC-naive but the human "today" is a
        # close-enough approximation for an at-a-glance badge. A
        # boundary-of-midnight off-by-one-hour is acceptable for a
        # progress badge that the operator reads as ballpark.
        today_start = datetime.combine(
            fields.Date.context_today(self), dtime.min)
        for wo in self:
            mine = wo.time_ids.filtered(
                lambda t: t.user_id.id == self.env.uid
                and t.date_start
                and t.date_start >= today_start
            )
            wo.x_sbk_my_time_today_min = sum(mine.mapped("duration"))

    # ------------------------------------------------------------------
    # W049 (R7.5, 2026-06-27) — shift attribution on KPIs.
    #
    # JTBD: "When I'm reviewing this week's KPIs, I want to know which
    # shift is leading/lagging so I can target coaching."
    #
    # Derive shift from date_start.hour against three configurable
    # boundary ICPs. Defaults are sensible for North American
    # kitchen-cabinet shops:
    #   morning   06:00 - 13:59
    #   afternoon 14:00 - 21:59
    #   night     22:00 - 05:59   (wraps midnight)
    #
    # ICP keys (in HOURS, 0..23):
    #   southbrook.shift_morning_start_hour       default 6
    #   southbrook.shift_afternoon_start_hour     default 14
    #   southbrook.shift_night_start_hour         default 22
    #
    # Stored so the pivot/graph group-by on downtime / throughput /
    # NCR is cheap. Empty when date_start is unset (planned WO not
    # yet started); reports treat empty as a separate bucket so the
    # supervisor can see the "not yet started" cohort.
    # ------------------------------------------------------------------
    x_sb_shift = fields.Selection(
        [
            ("morning", "Morning"),
            ("afternoon", "Afternoon"),
            ("night", "Night"),
        ],
        string="Shift",
        compute="_compute_x_sb_shift",
        store=True,
        index=True,
        help="Derived shift bucket for this WO based on the start time. "
             "Boundaries are configurable via the "
             "southbrook.shift_*_start_hour ICPs (defaults: 06/14/22). "
             "Empty when the WO has not started.",
    )

    # ------------------------------------------------------------------
    # Downtime aggregates
    # ------------------------------------------------------------------
    x_sbk_downtime_min = fields.Float(
        string="Downtime (min)",
        compute="_compute_x_sbk_downtime",
        store=False,
    )
    x_sbk_downtime_cost = fields.Float(
        string="Downtime Cost",
        compute="_compute_x_sbk_downtime",
        store=False,
        digits="Product Price",
    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

    @api.depends("duration", "x_sbk_kitchen_expected_min")
    def _compute_x_sbk_variance(self):
        for wo in self:
            wo.x_sbk_variance_min = (
                (wo.duration or 0.0) - (wo.x_sbk_kitchen_expected_min or 0.0)
            )

    @api.depends("duration", "x_sbk_kitchen_expected_min",
                 "workcenter_id.costs_hour")
    def _compute_x_sbk_costs(self):
        for wo in self:
            hourly = wo.workcenter_id.costs_hour or 0.0
            wo.x_sbk_estimated_cost = (
                (wo.x_sbk_kitchen_expected_min or 0.0) / 60.0 * hourly
            )
            wo.x_sbk_actual_cost = (
                (wo.duration or 0.0) / 60.0 * hourly
            )
            wo.x_sbk_cost_variance = (
                wo.x_sbk_actual_cost - wo.x_sbk_estimated_cost
            )

    @api.depends("production_id")
    def _compute_x_sbk_rework_metrics(self):
        Check = self.env["southbrook.mi.check"]
        for wo in self:
            checks = Check.search([
                ("x_sbk_rework_workorder_id", "=", wo.id),
            ])
            wo.x_sbk_rework_count = len(checks)
            # Cost is read off the rework WOs themselves — i.e. the
            # work orders that the checks point AT — not the inspection
            # cost. We're attributing the spend on the redo back to
            # the original WO that produced the defect.
            hourly = wo.workcenter_id.costs_hour or 0.0
            rework_duration = sum(checks.mapped(
                lambda c: (c.x_sbk_rework_workorder_id.duration or 0.0)
                if c.x_sbk_rework_workorder_id else 0.0
            ))
            wo.x_sbk_rework_cost = rework_duration / 60.0 * hourly

    @api.depends("qty_producing", "duration")
    def _compute_x_sbk_units_per_op_hour(self):
        for wo in self:
            hours = (wo.duration or 0.0) / 60.0
            wo.x_sbk_units_per_op_hour = (
                (wo.qty_producing or 0.0) / hours if hours > 0 else 0.0
            )

    # ------------------------------------------------------------------
    # W049 — shift attribution helpers
    # ------------------------------------------------------------------
    _SHIFT_DEFAULT_BOUNDARIES = (6, 14, 22)  # morning, afternoon, night

    @api.model
    def _sbk_shift_boundaries(self):
        """Read the 3 shift-boundary ICPs and return a sorted tuple of
        (morning_start, afternoon_start, night_start) hours, each
        clamped to [0, 23]. Falls back to defaults on bad config.

        Sortedness matters: the bucket-from-hour resolver below walks
        the boundaries in ascending order and shifts that wrap past
        midnight need the "night" boundary to come last."""
        Param = self.env["ir.config_parameter"].sudo()
        keys = (
            ("southbrook.shift_morning_start_hour",
             self._SHIFT_DEFAULT_BOUNDARIES[0]),
            ("southbrook.shift_afternoon_start_hour",
             self._SHIFT_DEFAULT_BOUNDARIES[1]),
            ("southbrook.shift_night_start_hour",
             self._SHIFT_DEFAULT_BOUNDARIES[2]),
        )
        out = []
        for key, default in keys:
            raw = Param.get_param(key, str(default))
            try:
                h = int(raw)
            except (TypeError, ValueError):
                h = default
            h = max(0, min(23, h))
            out.append(h)
        return tuple(out)

    @api.model
    def _sbk_shift_for_hour(self, hour):
        """Bucket an hour (0..23) into morning / afternoon / night per
        the configured boundaries. Returns False on invalid input.

        Algorithm: pair each shift label with its start hour, sort by
        hour ascending, and walk forward — the hour belongs to the
        last shift whose start <= hour. The night shift wraps midnight,
        so any hour < morning_start also belongs to night."""
        if hour is None or not isinstance(hour, int):
            return False
        if hour < 0 or hour > 23:
            return False
        morning, afternoon, night = self._sbk_shift_boundaries()
        # Pairs sorted by start hour. Tie-break is stable (morning
        # before afternoon before night) which matches what a
        # supervisor expects if two boundaries collide.
        pairs = sorted([
            ("morning", morning),
            ("afternoon", afternoon),
            ("night", night),
        ], key=lambda p: p[1])
        label = pairs[-1][0]  # default to the wrap-around shift
        for shift_label, start in pairs:
            if hour >= start:
                label = shift_label
        # Wrap: hour < smallest_start means we're in the shift whose
        # boundary is the LATEST in the day (night under defaults).
        if hour < pairs[0][1]:
            label = pairs[-1][0]
        return label

    @api.depends("date_start")
    def _compute_x_sb_shift(self):
        for wo in self:
            if not wo.date_start:
                wo.x_sb_shift = False
                continue
            try:
                wo.x_sb_shift = self._sbk_shift_for_hour(
                    wo.date_start.hour) or False
            except Exception:  # noqa: BLE001
                _logger.warning(
                    "W049 shift compute failed for WO %s",
                    wo.id, exc_info=True,
                )
                wo.x_sb_shift = False

    @api.depends("workcenter_id")
    def _compute_x_sbk_downtime(self):
        Downtime = self.env["southbrook.kitchen.workcenter.downtime"]
        for wo in self:
            rows = Downtime.search([
                ("workorder_id", "=", wo.id),
                ("state", "in", ("active", "closed")),
            ])
            wo.x_sbk_downtime_min = sum(rows.mapped("duration_min"))
            wo.x_sbk_downtime_cost = sum(rows.mapped("downtime_cost"))

    # ------------------------------------------------------------------
    # Convenience — the operation-template duration helper, called via
    # an inherited button in M4.
    # ------------------------------------------------------------------

    def action_open_scrap_wizard(self):
        """SAMI PRD MO-06 — open the stock.scrap wizard prefilled with
        this WO's production_id + workorder_id.

        v19 stock.scrap auto-computes location_id from workorder_id
        (uses production_id.location_src_id while MO is in-progress,
        location_dest_id once done). Operator picks the product from
        the MO's components/finished-goods, enters scrap qty + reason,
        and confirms — Odoo handles the inventory debit natively.

        We surface this as a button on the WO form to make it a
        first-class shop-floor action instead of a hidden 'More'
        item buried in the action menu.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Record Scrap"),
            "res_model": "stock.scrap",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_production_id": self.production_id.id,
                "default_workorder_id": self.id,
                "default_company_id": self.company_id.id,
                "default_origin": _("Scrap: %(wo)s", wo=self.name or self.id),
            },
        }

    # ------------------------------------------------------------------
    # W043 (R5.7, 2026-06-27) — re-inspection on rework WO completion.
    #
    # When a rework workorder finishes, find every southbrook.mi.check
    # whose x_sbk_rework_workorder_id == this WO and spawn a follow-up
    # re-inspection check (assigned to a user other than the original
    # inspector). The check carries x_sbk_result=False so the new
    # inspector has to take action — we never auto-pass.
    #
    # Wraps the spawn in try/except per check so a single failed spawn
    # never blocks the operator's button_finish click.
    # ------------------------------------------------------------------
    def button_finish(self):
        result = super().button_finish()
        try:
            Check = self.env["southbrook.mi.check"]
            originating = Check.search([
                ("x_sbk_rework_workorder_id", "in", self.ids),
                ("x_sbk_reinspection_check_id", "=", False),
            ])
            for check in originating:
                try:
                    check._sbk_spawn_reinspection_check()
                except Exception:  # noqa: BLE001
                    _logger.warning(
                        "W043 reinspection spawn failed for check %s",
                        check.id, exc_info=True,
                    )
        except Exception:  # noqa: BLE001
            _logger.warning(
                "W043 button_finish post-hook failed for WO %s",
                self.ids, exc_info=True,
            )
        return result

    def action_sbk_recalc_kitchen_duration(self):
        """Recompute x_sbk_kitchen_expected_min from the operation
        template bound to this WO's BoM operation. No-op when no
        template is bound — Odoo's native duration_expected still
        carries an estimate, the planner can fall back to that.
        """
        for wo in self:
            template = wo._sbk_kitchen_operation_template()
            if not template:
                continue
            driver = wo._sbk_kitchen_driver_value(template)
            complexity = (
                wo.production_id.x_sbk_complexity_factor or 1.0
                if wo.production_id else 1.0
            )
            wo.x_sbk_kitchen_expected_min = template.compute_expected_duration(
                driver_value=driver,
                complexity_factor=complexity,
            )
        return True

    def _sbk_kitchen_operation_template(self):
        """Resolve the operation template bound to this WO's BoM
        operation. Returns False when nothing is bound."""
        self.ensure_one()
        op = self.operation_id
        return op.x_sbk_operation_template_id if op else False

    def _sbk_kitchen_driver_value(self, template):
        """Pull the quantity driver for the template. Honours an
        explicit override on the routing operation, otherwise reads
        product_qty for per-unit templates and 0 for fixed-mode."""
        self.ensure_one()
        override = (
            self.operation_id.x_sbk_driver_override
            if self.operation_id else 0.0
        )
        if override:
            return override
        if template.quantity_driver_type == "fixed":
            return 0.0
        return self.production_id.product_qty or 0.0

    # ------------------------------------------------------------------
    # W026 — Rich WO traveler (MFG-REVIEW R2.5 / R8.2)
    #
    # The traveler PDF embeds:
    #   * a CAD render thumbnail (FreeCAD bridge render when present,
    #     else the product image — so the operator never builds the
    #     wrong spec from a missing drawing per R2.5)
    #   * 3 separate scan-QRs (START / PAUSE / DONE) so the operator
    #     can advance WO state with a single scan instead of opening
    #     the form + tapping — per R8.2 the wo handler already accepts
    #     these actions; this surface gives them a 0-tap entry point
    #     (W017 closes the loop once the OPL scheduling-engine gating
    #     is removed).
    #
    # The fields are computed-but-not-stored because:
    #   - cad_thumbnail is a derived Binary that follows the upstream
    #     FreeCAD attachment / product image; storing it would force
    #     us to invalidate on every product image edit + every render
    #     callback. Cheaper to re-derive at template-render time.
    #   - the 3 qr_action_* fields are derived from web.base.url +
    #     qr_payload (signed). The QR library spend is ~5ms/code on
    #     a Pi; the traveler renders one WO per page, so the worst
    #     case is ~15ms per page — fine for a PDF that's printed
    #     once per shift.
    # ------------------------------------------------------------------
    cad_thumbnail = fields.Binary(
        string="CAD Thumbnail",
        compute="_compute_cad_thumbnail",
        store=False,
        attachment=False,
        help="Cabinet render thumbnail for the WO traveler. Prefers "
             "the latest FreeCAD bridge artifact attached to the MO; "
             "falls back to the product image. Empty when neither is "
             "available — the traveler then skips the image block.",
    )
    qr_action_start_url = fields.Char(
        string="Start Scan URL",
        compute="_compute_qr_action_urls",
        store=False,
    )
    qr_action_pause_url = fields.Char(
        string="Pause Scan URL",
        compute="_compute_qr_action_urls",
        store=False,
    )
    qr_action_done_url = fields.Char(
        string="Done Scan URL",
        compute="_compute_qr_action_urls",
        store=False,
    )
    qr_action_start_b64 = fields.Char(
        string="Start QR (PNG b64)",
        compute="_compute_qr_action_images",
        store=False,
    )
    qr_action_pause_b64 = fields.Char(
        string="Pause QR (PNG b64)",
        compute="_compute_qr_action_images",
        store=False,
    )
    qr_action_done_b64 = fields.Char(
        string="Done QR (PNG b64)",
        compute="_compute_qr_action_images",
        store=False,
    )

    def _sbk_cad_thumbnail_binary(self):
        """Return the best-available image bytes for this WO's cabinet.

        Order of preference:
          1. FreeCAD bridge render — first image attachment on the MO
             via x_cad_attachment_ids whose mimetype is image/*
             (PNG/JPEG/SVG). The bridge writes DXF/SVG/PDF/STEP per
             panel + a top-level cabinet render thumbnail.
          2. product.image_1920 on the WO's finished product
             (Odoo's native ResImageField).

        Returns False when neither exists — the QWeb template renders
        the right column blank in that case rather than a broken img.
        """
        self.ensure_one()
        # Try FreeCAD bridge attachments first.
        mo = self.production_id
        if mo and "x_cad_attachment_ids" in mo._fields:
            try:
                for att in mo.x_cad_attachment_ids:
                    mime = (att.mimetype or "").lower()
                    if mime.startswith("image/") and att.datas:
                        return att.datas
            except Exception:  # noqa: BLE001
                # Bridge may not be installed / field may be empty —
                # fall through to the product image.
                pass
        # Fallback to the product image. image_1920 is the largest
        # native field; QWeb will resize via /web/image route.
        product = self.product_id
        if product and product.image_1920:
            return product.image_1920
        return False

    @api.depends("production_id", "product_id")
    def _compute_cad_thumbnail(self):
        for wo in self:
            try:
                wo.cad_thumbnail = wo._sbk_cad_thumbnail_binary()
            except Exception:  # noqa: BLE001
                _logger.warning(
                    "W026 cad_thumbnail compute failed for WO %s",
                    wo.id, exc_info=True,
                )
                wo.cad_thumbnail = False

    def _sbk_build_action_scan_url(self, action):
        """Build the absolute /sb/qr/scan URL for a given WO action.

        The signed sb://wo/<id>?t=...&s=... payload (from qr_payload)
        is URL-encoded into the `p=` query param; the `action=` query
        param picks the wo handler's start/pause/finish branch.
        Returns "" when web.base.url is unset (test sandboxes) so the
        template falls back gracefully.
        """
        from urllib.parse import quote
        self.ensure_one()
        if action not in ("start", "pause", "done"):
            raise UserError(_("Unknown WO scan action: %s") % action)
        # Map UI label "done" to the handler's "finish" action so
        # the URL is human-meaningful but still hits button_finish.
        handler_action = "finish" if action == "done" else action
        payload = self.qr_payload or ""
        if not payload:
            return ""
        Param = self.env["ir.config_parameter"].sudo()
        base = (Param.get_param("web.base.url") or "").rstrip("/")
        if not base:
            return ""
        return f"{base}/sb/qr/scan?p={quote(payload, safe='')}&action={handler_action}"

    @api.depends("qr_payload")
    def _compute_qr_action_urls(self):
        for wo in self:
            try:
                wo.qr_action_start_url = wo._sbk_build_action_scan_url("start")
                wo.qr_action_pause_url = wo._sbk_build_action_scan_url("pause")
                wo.qr_action_done_url = wo._sbk_build_action_scan_url("done")
            except Exception:  # noqa: BLE001
                _logger.warning(
                    "W026 qr_action_urls compute failed for WO %s",
                    wo.id, exc_info=True,
                )
                wo.qr_action_start_url = ""
                wo.qr_action_pause_url = ""
                wo.qr_action_done_url = ""

    @api.depends("qr_action_start_url", "qr_action_pause_url",
                 "qr_action_done_url")
    def _compute_qr_action_images(self):
        import base64
        import io
        for wo in self:
            try:
                import qrcode
            except ImportError:
                wo.qr_action_start_b64 = ""
                wo.qr_action_pause_b64 = ""
                wo.qr_action_done_b64 = ""
                continue
            for action, url_field, img_field in (
                ("start", "qr_action_start_url", "qr_action_start_b64"),
                ("pause", "qr_action_pause_url", "qr_action_pause_b64"),
                ("done", "qr_action_done_url", "qr_action_done_b64"),
            ):
                url = wo[url_field] or ""
                if not url:
                    wo[img_field] = ""
                    continue
                try:
                    img = qrcode.make(url, box_size=4, border=2)
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    wo[img_field] = base64.b64encode(
                        buf.getvalue()).decode("ascii")
                except Exception:  # noqa: BLE001
                    _logger.warning(
                        "W026 qr image render failed for WO %s action %s",
                        wo.id, action, exc_info=True,
                    )
                    wo[img_field] = ""

    # ------------------------------------------------------------------
    # W011 — form-open scan log (MFG-REVIEW-R2 §R2.2)
    # ------------------------------------------------------------------

    def web_read(self, specification):
        """Override v19 web_read to synthesise a `form_open` scan log
        row when an operator taps into a WO form. The defect-context
        window (`DefectQrKind._resolve_workorder_from_context`) walks
        `southbrook.qr.scan.log` for the user's most recent scan; this
        keeps that window working for the ~60% of WO opens that do NOT
        come from a QR scan."""
        res = super().web_read(specification)
        try:
            self._sbk_maybe_log_form_open()
        except Exception as exc:  # noqa: BLE001
            # Never let a logging glitch break a form open. The
            # underlying read succeeded; the worst case is we miss
            # one scan-log row and the operator has to type a WO
            # number on their next defect — annoying, not blocking.
            _logger.warning(
                "W011 form-open scan log failed for WO %s: %s",
                self.ids, exc,
            )
        return res

    def _sbk_maybe_log_form_open(self):
        """Create a `form_open` scan log row IF this web_read looks
        like a UI form-open. Guards:
          * single-record (form views fetch one record at a time;
            kanban/list views fetch many — we don't want to spam)
          * real HTTP request (skip RPC, cron, indirect calls)
          * not the QR scan controller (which already logs)
          * not a test run (test_enable context)
          * not already logged in the last `_FORM_OPEN_DEDUPE_SEC` for
            this (user, WO) pair (form views re-fire web_read on
            chatter refreshes / drawer flips)
        """
        if len(self) != 1:
            return
        env = self.env
        # Test-harness bypass — a caller (or test) sets test_enable in the
        # context to opt out of form-open logging. (The real guard against
        # non-UI callers is the bound-request check below.)
        if env.context.get("test_enable"):
            return
        # Cron / sudo / internal / test call with no bound HTTP request — skip.
        # `request` is a LocalProxy; accessing it (even `bool(request)` or
        # `getattr(request, "httprequest", ...)`) raises RuntimeError("object
        # is not bound") when there is no request context, so guard it.
        try:
            from odoo.http import request
        except Exception:  # noqa: BLE001
            return
        try:
            httprequest = getattr(request, "httprequest", None)
        except RuntimeError:
            return
        if not httprequest:
            return
        # The QR scan controller writes its own log row at
        # `/sb/qr/scan`; if web_read fires as a side effect of that
        # path (it shouldn't directly, but follow-up RPCs from the
        # redirect could), don't double-log.
        try:
            path = (request.httprequest.path or "")
        except Exception:  # noqa: BLE001
            path = ""
        if path.startswith("/sb/qr/"):
            return
        # The only paths that fire web_read on a single mrp.workorder
        # in a UI sense are /web/dataset/call_kw and /odoo/* — anything
        # else (xmlrpc, jsonrpc, REST) is server-to-server and we
        # don't want to attribute it to the operator's defect window.
        if not (path.startswith("/web/") or path.startswith("/odoo")):
            return
        wo = self
        Log = env["southbrook.qr.scan.log"].sudo()
        # Dedupe — same user + same WO within window already logged.
        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(seconds=_FORM_OPEN_DEDUPE_SEC)
        if Log.search_count([
            ("user_id", "=", env.uid),
            ("action", "=", "form_open"),
            ("target_model", "=", "mrp.workorder"),
            ("target_id", "=", wo.id),
            ("create_date", ">=", cutoff),
        ], limit=1):
            return
        try:
            ua = request.httprequest.headers.get("User-Agent") or ""
            ip = request.httprequest.remote_addr or ""
        except Exception:  # noqa: BLE001
            ua, ip = "", ""
        # `user_id` defaults to env.user via the model — but we're
        # using sudo() to bypass the write-restricted ACL, so set it
        # explicitly to keep attribution to the actual viewer.
        # W035 (R8.14): also resolve the PIN-bound operator (or the
        # session user's employee_id fallback) so the defect-context
        # window credits the right human, not the shared kiosk user.
        employee_id = False
        try:
            sess_emp = request.session.get(
                "sbk_operator_employee_id")
            if sess_emp:
                emp = env["hr.employee"].sudo().browse(sess_emp)
                if emp.exists() and emp.active:
                    employee_id = emp.id
            if not employee_id:
                employee_id = env.user.employee_id.id or False
        except Exception:  # noqa: BLE001
            pass
        Log.create({
            "user_id": env.uid,
            "employee_id": employee_id,
            "kind": "wo",
            "ident": str(wo.id),
            "action": "form_open",
            "result": "ok",
            "target_model": "mrp.workorder",
            "target_id": wo.id,
            "source_ip": ip[:255] if ip else False,
            "user_agent": ua[:255] if ua else False,
        })
