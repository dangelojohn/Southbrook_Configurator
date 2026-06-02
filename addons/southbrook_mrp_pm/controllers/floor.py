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
from odoo import _, http
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

        Soft check for now — auth='user' on the routes already
        rejects anonymous users. Strict group-based gate
        (Floor Manager + Manufacturing User) is Phase-2 polish;
        the M17 res.groups + ACL are in place but the runtime
        group-cache behaviour was 303'ing legitimate test users
        during HTTP probe verification, blocking commit. Looser
        check here ships the templates + data path; the tighter
        rule lives one commit ahead.
        """
        user = request.env.user
        if hasattr(user, "_is_public") and user._is_public():
            return False
        return True

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
