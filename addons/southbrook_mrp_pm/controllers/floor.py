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


# In-flight WO states we surface. Same as M14's MO states but at
# the work-order layer:
#   ready    — upstream done, this WO is the head of the queue
#   waiting  — blocked by an upstream WO that isn't done
#   progress — currently being run on the floor
#   pending  — initial state before MO confirm wakes it up
IN_FLIGHT_WO_STATES = ("pending", "waiting", "ready", "progress")


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
        # Start only from ready / pending. Direct state write (not
        # button_start) because Odoo's button_start has side-effects
        # — component reservations, mrp_workorder timer rows, MO
        # state cascade — that the floor MVP isn't wired for. Floor
        # operator gets the state flip + date_start stamp; PMs who
        # need the full mrp flow use the backend.
        from odoo import fields as odoo_fields
        if wo.state in ("pending", "ready", "waiting"):
            wo.write({
                "state": "progress",
                "date_start": odoo_fields.Datetime.now(),
            })
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
        from odoo import fields as odoo_fields
        if wo.state == "progress":
            # Same shortcut pattern as start — direct write of
            # terminal state. The parent MO does NOT auto-close on
            # this write (Odoo expects button_finish to cascade);
            # PMs reconcile via the backend when the whole order
            # finishes upstream.
            wo.write({
                "state": "done",
                "date_finished": odoo_fields.Datetime.now(),
            })
            # Bump the next non-done sibling WO to 'ready' so the
            # floor portal reflects what the next operator should
            # see. Odoo's stock auto-cascade happens via
            # button_finish; since we bypassed it, do it manually.
            # Filter captures Odoo's gate states: blocked / waiting /
            # pending / ready (already-ready is a no-op via the
            # state write).
            mo = wo.production_id
            next_pending = mo.workorder_ids.filtered(
                lambda w: w.state not in ("done", "cancel", "progress")
                and w.sequence > wo.sequence,
            )
            if next_pending:
                next_wo = min(
                    next_pending, key=lambda w: w.sequence,
                )
                if next_wo.state != "ready":
                    next_wo.write({"state": "ready"})
        return request.redirect(
            "/my/southbrook/floor/%s" % wo.workcenter_id.id
        )

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
        Wo = request.env["mrp.workorder"].sudo()
        Equip = request.env["maintenance.equipment"].sudo()

        wc = Wc.browse(workcenter_id).exists()
        if not wc:
            return request.redirect("/my/southbrook/floor")

        # In-flight work orders at this station — sorted by parent
        # MO date_deadline so the most-urgent station queue floats
        # to the top.
        wos = Wo.search(
            [
                ("workcenter_id", "=", wc.id),
                ("state", "in", list(IN_FLIGHT_WO_STATES)),
            ],
            order="production_id, sequence",
        )
        # Group rows by MO so the operator sees per-cabinet context.
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

        # Sort groups by MO deadline ASC (None last).
        ordered_groups = sorted(
            wo_groups.values(),
            key=lambda r: (r["deadline"] is None, r["deadline"]),
        )

        # Equipment attached to this workcenter — list with the
        # M13 condition pill values.
        equipment = Equip.search([
            ("workcenter_id", "=", wc.id),
        ])
        equipment_rows = [
            {
                "id": eq.id,
                "name": eq.name,
                "condition": eq.southbrook_condition or "good",
                "last_updated": eq.southbrook_condition_last_updated,
            }
            for eq in equipment
        ]

        values = self._prepare_portal_layout_values()
        values.update({
            "page_name": "southbrook_floor_wc",
            "wc": {
                "id": wc.id,
                "code": wc.code or "",
                "name": wc.name,
                "oee_target": wc.oee_target,
            },
            "wo_groups": ordered_groups,
            "equipment": equipment_rows,
        })
        return request.render(
            "southbrook_mrp_pm.portal_floor_workcenter", values,
        )
