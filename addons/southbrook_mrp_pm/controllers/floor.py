# SPDX-License-Identifier: LGPL-3.0-only
"""Floor Manager portal routes.

M16 (Manufacturing PM JTBD 2026-06-01): tablet-friendly read-only
view of the work-order queue per work center. Two routes:

    GET /my/southbrook/floor
        Landing page — lists every active work center with its
        in-flight work-order count + a 'View Queue' link.

    GET /my/southbrook/floor/<int:workcenter_id>
        Per-station queue page — lists the ready / in-progress /
        blocked work orders for that station, with parent MO,
        expected cycle time, current state, and (Phase-2) the
        single-tap start/finish + equipment-condition pill.

Auth model: auth='user' + a runtime check that the user is in
group_floor_manager OR an internal user (whose existing mrp
access already covers the same fields). Portal users not in the
group get a 403 redirect to /my.

Phase-2 commits (not in this one):
    - POST /my/southbrook/floor/wo/<id>/start
    - POST /my/southbrook/floor/wo/<id>/finish
    - POST /my/southbrook/floor/equipment/<id>/condition
"""
from odoo import _, fields, http
from odoo.exceptions import AccessError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


# In-flight WO states we surface. These are the ACTUAL Odoo 19 CE
# mrp.workorder.state values (verified against core mrp: the selection
# is blocked/ready/progress/done/cancel — there is NO 'pending' or
# 'waiting' state). The prior list used those two non-existent tokens,
# which silently dropped every BLOCKED work order from the floor queue,
# the kiosk, and the per-station counters — hiding the bulk of real WIP.
#   blocked  — waiting on an upstream WO (the dependency head isn't done)
#   ready    — upstream done, this WO is the head of the queue
#   progress — currently being run on the floor
IN_FLIGHT_WO_STATES = ("blocked", "ready", "progress")


class SouthbrookFloorPortal(CustomerPortal):

    def _floor_user_authorized(self):
        """True when the current user can use the floor portal.

        Strict check: require Floor Manager group OR Manufacturing
        User group. Anonymous + portal users without either group
        are rejected.

        Why SQL instead of user.has_group(): in the earlier MVP we
        observed has_group() returning False for users whose
        group_ids had been mutated via direct SQL INSERT between
        sessions — Odoo caches the user's groups in the env and
        the cache lagged behind the DB. Direct query of
        res_groups_users_rel sidesteps the cache entirely.
        """
        user = request.env.user
        if hasattr(user, "_is_public") and user._is_public():
            return False

        # xml_id → numeric group id, sudo'd because portal users
        # cannot read res.groups directly.
        ImD = request.env["ir.model.data"].sudo()
        floor_gid = ImD._xmlid_to_res_id(
            "southbrook_mrp_pm.group_floor_manager",
            raise_if_not_found=False,
        )
        mrp_gid = ImD._xmlid_to_res_id(
            "mrp.group_mrp_user",
            raise_if_not_found=False,
        )
        candidate_ids = [g for g in (floor_gid, mrp_gid) if g]
        if not candidate_ids:
            return False

        # Direct rel-table lookup — no cache to worry about.
        self.env.cr.execute(
            """
            SELECT 1 FROM res_groups_users_rel
            WHERE uid = %s AND gid IN %s
            LIMIT 1
            """,
            (user.id, tuple(candidate_ids)),
        )
        return bool(self.env.cr.fetchone())

    @http.route(
        "/my/southbrook/floor",
        type="http",
        auth="user",
        website=True,
    )
    def southbrook_floor_index(self, **kw):
        if not self._floor_user_authorized():
            return request.redirect("/my")

        Wc = request.env["mrp.workcenter"].sudo()
        Wo = request.env["mrp.workorder"].sudo()
        wcs = Wc.search([("active", "=", True)], order="code")
        wc_rows = []
        for wc in wcs:
            inflight = Wo.search_count([
                ("workcenter_id", "=", wc.id),
                ("state", "in", list(IN_FLIGHT_WO_STATES)),
            ])
            wc_rows.append({
                "id": wc.id,
                "code": wc.code or "",
                "name": wc.name,
                "inflight": inflight,
            })

        values = self._prepare_portal_layout_values()
        values.update({
            "page_name": "southbrook_floor",
            "wc_rows": wc_rows,
        })
        return request.render(
            "southbrook_mrp_pm.portal_floor_index", values,
        )

    # ==================================================================
    # M16 Phase-2 — start/finish/condition action handlers
    # ==================================================================
    #
    # Three POST routes, all CSRF-protected via Odoo's default
    # csrf=True. Each performs its mutation and redirects back to
    # the workcenter page so the operator's tablet refreshes with
    # the new state.

    @http.route(
        "/my/southbrook/floor/wo/<int:wo_id>/start",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def southbrook_floor_wo_start(self, wo_id, **kw):
        if not self._floor_user_authorized():
            return request.redirect("/my")
        Wo = request.env["mrp.workorder"].sudo()
        wo = Wo.browse(wo_id).exists()
        if not wo:
            return request.redirect("/my/southbrook/floor")
        # A WO can only be STARTED from 'ready' (its dependency head is
        # done). 'blocked' WOs show in the queue but have no Start button.
        #
        # We deliberately do NOT call button_start(): on this deployment
        # WOs are confirmed but never planned, so button_start() raises
        # "This work order has not been scheduled yet" (verified against
        # production 2026-07-06). Instead we flip the state directly AND
        # open a real productivity time row, so the OEE / throughput KPIs
        # (which read time_ids / duration) get true run-time data — the
        # piece the original MVP omitted and the E2E review flagged.
        if wo.state == "ready":
            wo.write({
                "state": "progress",
                "date_start": fields.Datetime.now(),
            })
            self._sbk_open_productive_time(wo)
        return request.redirect(
            "/my/southbrook/floor/%s" % wo.workcenter_id.id
        )

    @http.route(
        "/my/southbrook/floor/wo/<int:wo_id>/finish",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def southbrook_floor_wo_finish(self, wo_id, **kw):
        if not self._floor_user_authorized():
            return request.redirect("/my")
        Wo = request.env["mrp.workorder"].sudo()
        wo = Wo.browse(wo_id).exists()
        if not wo:
            return request.redirect("/my/southbrook/floor")
        if wo.state == "progress":
            # Close the open productivity time row FIRST so `duration`
            # captures real elapsed run-time, then flip to done. We avoid
            # button_finish() because it posts stock-valuation account
            # moves that fail on this config (account_move.journal_id
            # NOT NULL, verified against production 2026-07-06).
            self._sbk_close_productive_time(wo)
            wo.write({
                "state": "done",
                "date_finished": fields.Datetime.now(),
            })
            # Release the next work order in the chain to 'ready'. Native
            # Odoo does this via button_finish's qty cascade; since we
            # bypass it, we advance the lowest-sequence 'blocked' sibling
            # manually so the next operator sees a Start button.
            mo = wo.production_id
            next_blocked = mo.workorder_ids.filtered(
                lambda w: w.state == "blocked" and w.sequence > wo.sequence,
            )
            if next_blocked:
                next_wo = min(next_blocked, key=lambda w: w.sequence)
                next_wo.write({"state": "ready"})
        return request.redirect(
            "/my/southbrook/floor/%s" % wo.workcenter_id.id
        )

    # ------------------------------------------------------------------
    # Productivity time-row helpers (M16 P0 truth-fix 2026-07-06).
    #
    # The floor Start/Finish shortcuts bypass button_start/button_finish
    # (which raise on this deployment — unplanned WOs + accounting config,
    # verified). To stop OEE/throughput KPIs from silently under-reporting
    # work done through the portal, we open a 'Fully Productive Time' row
    # on Start and close it on Finish, exactly as button_start/finish
    # would. `duration` then reflects true elapsed time.
    # ------------------------------------------------------------------
    def _sbk_open_productive_time(self, wo):
        Prod = request.env["mrp.workcenter.productivity"].sudo()
        loss = request.env["mrp.workcenter.productivity.loss"].sudo().search(
            [("loss_type", "=", "productive")], limit=1)
        if not loss:
            return
        vals = {
            "workorder_id": wo.id,
            "workcenter_id": wo.workcenter_id.id,
            "date_start": fields.Datetime.now(),
            "loss_id": loss.id,
            "user_id": request.env.uid,
        }
        if "employee_id" in Prod._fields:
            emp = request.env.user.employee_id
            if emp:
                vals["employee_id"] = emp.id
        Prod.create(vals)

    def _sbk_close_productive_time(self, wo):
        open_rows = request.env["mrp.workcenter.productivity"].sudo().search([
            ("workorder_id", "=", wo.id),
            ("date_end", "=", False),
        ])
        if open_rows:
            open_rows.write({"date_end": fields.Datetime.now()})

    @http.route(
        "/my/southbrook/floor/equipment/<int:eq_id>/condition",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def southbrook_floor_equipment_condition(
        self, eq_id, condition=None, **kw,
    ):
        if not self._floor_user_authorized():
            return request.redirect("/my")
        Equip = request.env["maintenance.equipment"].sudo()
        eq = Equip.browse(eq_id).exists()
        if not eq:
            return request.redirect("/my/southbrook/floor")
        valid = {"good", "fair", "watch", "critical", "offline"}
        if condition in valid:
            # The write() override on maintenance.equipment (M13)
            # stamps southbrook_condition_last_updated +
            # southbrook_condition_updated_by automatically.
            eq.write({"southbrook_condition": condition})
        redirect_wc = eq.workcenter_id.id if eq.workcenter_id else None
        if redirect_wc:
            return request.redirect(
                "/my/southbrook/floor/%s" % redirect_wc
            )
        return request.redirect("/my/southbrook/floor")

    # ==================================================================
    # M12 — kiosk display mode for factory wall-mounted TV
    # ==================================================================
    #
    # /my/southbrook/floor/kiosk renders the same data as the floor
    # index, but in a layout designed for an HDMI-attached TV mounted
    # over the shop floor: dark background, very large numbers,
    # higher-contrast condition pills, no portal chrome. The view
    # auto-refreshes every 30s so the floor sees state changes
    # without anyone touching it.
    #
    # Auth: same _floor_user_authorized() gate as the operator
    # tablet views — the device that's connected to the TV runs a
    # browser logged in as a portal user in the Floor Manager group.
    # Once that session is established, the kiosk URL just loads.

    @http.route(
        "/my/southbrook/floor/kiosk",
        type="http",
        auth="user",
        website=True,
    )
    def southbrook_floor_kiosk(self, **kw):
        if not self._floor_user_authorized():
            return request.redirect("/my")
        Wc = request.env["mrp.workcenter"].sudo()
        Mo = request.env["mrp.production"].sudo()
        Fam = request.env["southbrook.cabinet.family"].sudo()

        # Re-use the existing computed fields on mrp.workcenter
        # (M10) and southbrook.cabinet.family (M11).
        wcs = Wc.search([("active", "=", True)], order="code")
        wc_rows = [
            {
                "id": wc.id,
                "code": wc.code or "",
                "name": wc.name,
                "inflight": wc.southbrook_pm_inflight_count,
                "done_today": wc.southbrook_pm_throughput_today,
                "late": wc.southbrook_pm_late_count,
                "alerts": wc.southbrook_pm_equipment_alerts,
            }
            for wc in wcs
        ]
        fams = Fam.search([], order="sequence")
        family_rows = [
            {
                "id": f.id,
                "code": f.code,
                "name": f.name,
                "inflight": f.inflight_count,
                "done_today": f.throughput_today,
                "late": f.late_count,
            }
            for f in fams
        ]
        total_late = Mo.search_count([
            ("state", "not in", ["done", "cancel"]),
            ("date_deadline", "<", fields.Datetime.now()),
        ])

        return request.render(
            "southbrook_mrp_pm.portal_floor_kiosk",
            {
                "wc_rows": wc_rows,
                "family_rows": family_rows,
                "total_late": total_late,
                "now": fields.Datetime.now(),
            },
        )

    # ------------------------------------------------------------------
    # W056 — shared per-workcenter queue snapshot
    # ------------------------------------------------------------------
    # Builds the dict consumed by BOTH the HTML render and the JSON
    # poll endpoint, so they cannot drift out of sync.
    def _floor_wc_snapshot(self, wc):
        """Return {wc, wo_groups, equipment} for a single workcenter."""
        Wo = request.env["mrp.workorder"].sudo()
        Equip = request.env["maintenance.equipment"].sudo()
        wos = Wo.search(
            [
                ("workcenter_id", "=", wc.id),
                ("state", "in", list(IN_FLIGHT_WO_STATES)),
            ],
            order="production_id, sequence",
        )
        wo_groups = {}
        for wo in wos:
            mo = wo.production_id
            wo_groups.setdefault(mo.id, {
                "mo_id": mo.id,
                "mo_name": mo.name,
                "mo_state": mo.state,
                "mo_origin": mo.origin or "",
                "product_sku": (
                    mo.product_id.default_code
                    or (mo.product_id.product_tmpl_id.default_code
                        if mo.product_id else "")
                    or ""
                ),
                "deadline": mo.date_deadline,
                "wos": [],
            })["wos"].append({
                "id": wo.id,
                "name": wo.name,
                "state": wo.state,
                "sequence": wo.sequence,
                "duration_expected": wo.duration_expected,
            })
        ordered_groups = sorted(
            wo_groups.values(),
            key=lambda r: (r["deadline"] is None, r["deadline"]),
        )
        equipment = Equip.search([("workcenter_id", "=", wc.id)])
        equipment_rows = [
            {
                "id": eq.id,
                "name": eq.name,
                "condition": eq.southbrook_condition or "good",
                "last_updated": eq.southbrook_condition_last_updated,
            }
            for eq in equipment
        ]
        return {
            "wc": {
                "id": wc.id,
                "code": wc.code or "",
                "name": wc.name,
                "oee_target": wc.oee_target,
            },
            "wo_groups": ordered_groups,
            "equipment": equipment_rows,
        }

    @http.route(
        "/my/southbrook/floor/<int:workcenter_id>",
        type="http",
        auth="user",
        website=True,
    )
    def southbrook_floor_workcenter(self, workcenter_id, **kw):
        if not self._floor_user_authorized():
            return request.redirect("/my")

        Wc = request.env["mrp.workcenter"].sudo()
        wc = Wc.browse(workcenter_id).exists()
        if not wc:
            return request.redirect("/my/southbrook/floor")

        snapshot = self._floor_wc_snapshot(wc)
        values = self._prepare_portal_layout_values()
        values.update({
            "page_name": "southbrook_floor_wc",
            **snapshot,
        })
        return request.render(
            "southbrook_mrp_pm.portal_floor_workcenter", values,
        )

    # ------------------------------------------------------------------
    # W056 / R1.11 — lighter JSON polling endpoint
    # ------------------------------------------------------------------
    # The floor portal previously did a full-page reload every 30s via
    # <meta http-equiv="refresh">. The full reload flushed the operator's
    # mid-interaction scroll position and re-shipped portal chrome on
    # every poll. This endpoint returns just the queue snapshot as JSON;
    # the template-side setInterval() updates the DOM in place.
    #
    # The meta-refresh tag is RETAINED in the template as the JS-off
    # fallback — if scripts are disabled (or fail to load), the page
    # still refreshes every 30s the old way. The JS path runs the same
    # 30s interval and supersedes by virtue of running first.
    @http.route(
        "/my/southbrook/floor/<int:workcenter_id>/queue.json",
        type="http",
        auth="user",
        methods=["GET"],
        csrf=False,
    )
    def southbrook_floor_workcenter_queue_json(self, workcenter_id, **kw):
        """Return the per-workcenter queue snapshot as JSON.

        Auth: same _floor_user_authorized() gate as the HTML route.
        Unauthorized → 403 with an empty body (the poller stops on 403).
        """
        import json
        if not self._floor_user_authorized():
            return request.make_response(
                json.dumps({"ok": False, "error": "forbidden"}),
                headers=[("Content-Type", "application/json")],
                status=403,
            )
        Wc = request.env["mrp.workcenter"].sudo()
        wc = Wc.browse(workcenter_id).exists()
        if not wc:
            return request.make_response(
                json.dumps({"ok": False, "error": "workcenter not found"}),
                headers=[("Content-Type", "application/json")],
                status=404,
            )
        snapshot = self._floor_wc_snapshot(wc)
        # Datetime → ISO string for JSON serialization.
        for grp in snapshot["wo_groups"]:
            if grp.get("deadline"):
                grp["deadline"] = fields.Datetime.to_string(grp["deadline"])
        for eq in snapshot["equipment"]:
            if eq.get("last_updated"):
                eq["last_updated"] = fields.Datetime.to_string(
                    eq["last_updated"])
        return request.make_response(
            json.dumps({"ok": True, **snapshot}),
            headers=[
                ("Content-Type", "application/json"),
                ("Cache-Control", "no-store"),
            ],
        )
