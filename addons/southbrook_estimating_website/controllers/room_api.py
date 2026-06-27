# SPDX-License-Identifier: LGPL-3.0-only
"""Portal RPC endpoints — Phase 2.A of Room-First UX overhaul.

5 JSON-RPC endpoints under /southbrook/api/order/<id>/room/... backing
the upcoming Room Setup tab (Phase 2.B) and the 3-step wizard (Phase
2.C). Server-side only; no OWL changes ship in 2.A.

Auth + ownership reuse `_southbrook_resolve_order` from main.py via
class inheritance — `SouthbrookRoomApi` is a subclass of
`SouthbrookKitchenPlanner` so the helper resolves on `self` cleanly.

Error convention follows the existing add-line endpoint
(main.py:1223-1260): return `{"error": "<code>"}` strings; never raise
HTTP exceptions, never leak internals. Every path param is scope-
validated against the resolved order so a wrong room/wall/constraint
id surfaces as `forbidden` (not `not_found`) — avoids existence-oracle
leak per the spec at docs/superpowers/plans/.../2.A.
"""
import logging

from odoo import http
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request

from .main import SouthbrookKitchenPlanner

_logger = logging.getLogger(__name__)


def _serialize_room(room):
    """Return the room as a JSON-serialisable dict matching the contract.

    Matches the response shape documented in the Phase 2.A spec:
        {id, name, room_type, layout_shape, ceiling_height_mm,
         unit_preference, layout_complete, has_plumbing,
         total_linear_mm, wall_count, constraint_count,
         walls: [{id, name, length_mm, wall_order, has_upper_cabinets,
                  has_base_cabinets, has_tall_cabinets, used_mm,
                  remaining_mm, has_conflicts,
                  constraints: [{id, constraint_type,
                                 distance_from_left_mm, width_mm,
                                 height_mm, height_from_floor_mm,
                                 notes}]}]}
    """
    if not room:
        return None
    walls = []
    for w in room.wall_ids.sorted(key=lambda x: (x.wall_order, x.id)):
        constraints = [{
            "id": c.id,
            "constraint_type": c.constraint_type,
            "distance_from_left_mm": c.distance_from_left_mm,
            "width_mm": c.width_mm,
            "height_mm": c.height_mm,
            "height_from_floor_mm": c.height_from_floor_mm,
            "notes": c.notes or "",
        } for c in w.constraint_ids.sorted(key=lambda x: x.distance_from_left_mm)]
        walls.append({
            "id": w.id,
            "name": w.name,
            "length_mm": w.length_mm,
            "wall_order": w.wall_order,
            "has_upper_cabinets": w.has_upper_cabinets,
            "has_base_cabinets": w.has_base_cabinets,
            "has_tall_cabinets": w.has_tall_cabinets,
            "used_mm": w.used_mm,
            "remaining_mm": w.remaining_mm,
            "has_conflicts": w.has_conflicts,
            "constraints": constraints,
        })
    return {
        "id": room.id,
        "name": room.name,
        "room_type": room.room_type,
        "layout_shape": room.layout_shape,
        "ceiling_height_mm": room.ceiling_height_mm,
        "unit_preference": room.unit_preference,
        "layout_complete": room.layout_complete,
        "has_plumbing": room.has_plumbing,
        "total_linear_mm": room.total_linear_mm,
        "wall_count": room.wall_count,
        "constraint_count": room.constraint_count,
        "walls": walls,
    }


def _serialize_constraint(c):
    """Single constraint dict — used by the add endpoint."""
    if not c:
        return None
    return {
        "id": c.id,
        "constraint_type": c.constraint_type,
        "distance_from_left_mm": c.distance_from_left_mm,
        "width_mm": c.width_mm,
        "height_mm": c.height_mm,
        "height_from_floor_mm": c.height_from_floor_mm,
        "notes": c.notes or "",
    }


_ROOM_SCALAR_FIELDS = (
    "name", "room_type", "layout_shape", "ceiling_height_mm",
    "unit_preference",
)
_WALL_SCALAR_FIELDS = (
    "name", "length_mm", "wall_order", "has_upper_cabinets",
    "has_base_cabinets", "has_tall_cabinets",
)
_CONSTRAINT_SCALAR_FIELDS = (
    "distance_from_left_mm", "width_mm", "height_mm",
    "height_from_floor_mm", "notes",
)


class SouthbrookRoomApi(SouthbrookKitchenPlanner):
    """Room CRUD JSON-RPC endpoints — Phase 2.A of Room-First UX."""

    # ------------------------------------------------------------------
    # Scope guards
    # ------------------------------------------------------------------

    def _get_room_scoped(self, order, room_id):
        """Resolve a southbrook.room and verify it belongs to `order`.

        Wrong order → AccessError (NOT MissingError) to avoid the
        existence-oracle leak (a client probing IDs across orders gets
        `forbidden` not `not_found`, so they can't infer whether the
        room exists).
        """
        room = request.env["southbrook.room"].sudo().browse(room_id).exists()
        if not room or room.order_id.id != order.id:
            raise AccessError("room not in order")
        return room

    def _get_wall_scoped(self, room, wall_id):
        wall = room.wall_ids.filtered(lambda w: w.id == wall_id)
        if not wall:
            raise AccessError("wall not in room")
        return wall

    def _get_constraint_scoped(self, wall, constraint_id):
        c = wall.constraint_ids.filtered(lambda x: x.id == constraint_id)
        if not c:
            raise AccessError("constraint not on wall")
        return c

    # ------------------------------------------------------------------
    # POST /southbrook/api/order/<order_id>/room/get
    # ------------------------------------------------------------------
    @http.route(
        "/southbrook/api/order/<int:order_id>/room/get",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def southbrook_api_room_get(self, order_id, **kw):
        try:
            order = self._southbrook_resolve_order(order_id)
        except MissingError:
            return {"error": "not_found"}
        except AccessError:
            return {"error": "forbidden"}

        room = order.room_ids[:1]
        return {"ok": True, "room": _serialize_room(room) if room else None}

    # ------------------------------------------------------------------
    # POST /southbrook/api/order/<order_id>/room/create
    # ------------------------------------------------------------------
    @http.route(
        "/southbrook/api/order/<int:order_id>/room/create",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def southbrook_api_room_create(
        self,
        order_id,
        name=None,
        room_type=None,
        layout_shape=None,
        ceiling_height_mm=None,
        unit_preference=None,
        walls=None,
        constraints=None,
        **kw,
    ):
        try:
            order = self._southbrook_resolve_order(order_id)
        except MissingError:
            return {"error": "not_found"}
        except AccessError:
            return {"error": "forbidden"}

        # Idempotency: one room per order in Phase 2.A. If a room
        # already exists, surface the existing room so the caller can
        # switch to update flow without losing state.
        if len(order.room_ids) >= 1:
            return {
                "error": "room_already_exists",
                "room": _serialize_room(order.room_ids[:1]),
            }

        if not layout_shape:
            return {"error": "invalid", "detail": "layout_shape required"}

        walls_payload = walls or []
        constraints_payload = constraints or []

        # Bounds-check constraint wall_index up front so we don't half-
        # create a room then bail.
        for idx, c in enumerate(constraints_payload):
            wi = c.get("wall_index")
            if wi is None or not isinstance(wi, int):
                return {
                    "error": "invalid",
                    "detail": f"constraints[{idx}].wall_index missing or non-int",
                }
            if wi < 0 or wi >= len(walls_payload):
                return {
                    "error": "invalid",
                    "detail": f"constraints[{idx}].wall_index {wi} out of bounds",
                }

        try:
            # Step 1: create the room + walls in one shot via O2m
            # commands. Walls keep their array order so wall_index
            # mapping works.
            wall_cmds = []
            for idx, w in enumerate(walls_payload):
                vals = {k: w[k] for k in _WALL_SCALAR_FIELDS if k in w}
                # Default wall_order so a fresh room without explicit
                # ordering still renders deterministically.
                vals.setdefault("wall_order", (idx + 1) * 10)
                vals.setdefault("name", f"Wall {chr(ord('A') + idx)}")
                wall_cmds.append((0, 0, vals))

            room_vals = {
                "order_id": order.id,
                "name": name or "Main Kitchen",
                "room_type": room_type or "kitchen",
                "layout_shape": layout_shape,
                "ceiling_height_mm": (
                    int(ceiling_height_mm) if ceiling_height_mm is not None
                    else 2400
                ),
                "unit_preference": unit_preference or "mm",
                "wall_ids": wall_cmds,
            }
            room = request.env["southbrook.room"].sudo().create(room_vals)

            # Step 2: resolve wall_index → wall_id for constraint
            # creation. The freshly-created walls live on room.wall_ids
            # in insertion order (matches walls_payload order).
            created_walls = room.wall_ids.sorted(key=lambda w: w.id)
            if constraints_payload:
                cons_cmds = []
                for c in constraints_payload:
                    wi = c["wall_index"]
                    wall_id = created_walls[wi].id
                    vals = {k: c[k] for k in _CONSTRAINT_SCALAR_FIELDS if k in c}
                    if "constraint_type" not in c:
                        return {
                            "error": "invalid",
                            "detail": "constraint missing constraint_type",
                        }
                    vals["constraint_type"] = c["constraint_type"]
                    vals["wall_id"] = wall_id
                    cons_cmds.append(vals)
                if cons_cmds:
                    request.env["southbrook.room.constraint"].sudo().create(
                        cons_cmds
                    )
        except (ValidationError, ValueError) as e:
            # Selection field bad-enum (e.g. unit_preference="bogus")
            # raises ValueError, not ValidationError — surface both
            # cleanly so a hand-crafted curl doesn't get a JSON-RPC
            # 500 (review #6).
            return {"error": "invalid", "detail": str(e)}

        return {"ok": True, "room": _serialize_room(room)}

    # ------------------------------------------------------------------
    # POST /southbrook/api/order/<order_id>/room/<room_id>/update
    # ------------------------------------------------------------------
    @http.route(
        "/southbrook/api/order/<int:order_id>/room/<int:room_id>/update",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def southbrook_api_room_update(
        self,
        order_id,
        room_id,
        walls=None,
        **kw,
    ):
        try:
            order = self._southbrook_resolve_order(order_id)
        except MissingError:
            return {"error": "not_found"}
        except AccessError:
            return {"error": "forbidden"}

        try:
            room = self._get_room_scoped(order, room_id)
        except AccessError:
            return {"error": "forbidden"}

        # Partial scalar update — only fields actually present in the
        # request body are written. kw catches the JSON-RPC layer's
        # extras; we filter via the allowlist.
        scalar_updates = {
            k: kw[k] for k in _ROOM_SCALAR_FIELDS if k in kw
        }
        # Caller may pass scalars at the top level too. The decorator
        # binds **kw rather than capturing one positional dict, so
        # name/room_type/etc. are routed through kw above.

        # ceiling_height_mm is integer; coerce defensively.
        if "ceiling_height_mm" in scalar_updates:
            try:
                scalar_updates["ceiling_height_mm"] = int(
                    scalar_updates["ceiling_height_mm"]
                )
            except (TypeError, ValueError):
                return {
                    "error": "invalid",
                    "detail": "ceiling_height_mm not int",
                }

        walls_payload = walls or []
        if not scalar_updates and not walls_payload:
            return {"error": "invalid", "detail": "no fields to update"}

        try:
            if scalar_updates:
                room.sudo().write(scalar_updates)

            # Walls upsert. id-bearing items update; id-less create.
            # Out-of-scope wall_id (belongs to a different room) →
            # forbidden, not silent.
            for item in walls_payload:
                wid = item.get("id")
                wall_vals = {
                    k: item[k] for k in _WALL_SCALAR_FIELDS if k in item
                }
                if wid:
                    # Scope-check then update.
                    wall = self._get_wall_scoped(room, wid)
                    if wall_vals:
                        wall.sudo().write(wall_vals)
                else:
                    # Create new wall.
                    wall_vals.setdefault("name", "Wall")
                    wall_vals["room_id"] = room.id
                    request.env["southbrook.room.wall"].sudo().create(wall_vals)
        except AccessError:
            return {"error": "forbidden"}
        except (ValidationError, ValueError) as e:
            # Selection field bad-enum (e.g. unit_preference="bogus")
            # raises ValueError, not ValidationError — surface both
            # cleanly so a hand-crafted curl doesn't get a JSON-RPC
            # 500 (review #6).
            return {"error": "invalid", "detail": str(e)}

        # Refresh ORM cache so computes reflect the writes.
        room.invalidate_recordset()
        return {"ok": True, "room": _serialize_room(room)}

    # ------------------------------------------------------------------
    # POST /southbrook/api/order/<order_id>/room/<room_id>/wall/<wall_id>/constraint/add
    # ------------------------------------------------------------------
    @http.route(
        "/southbrook/api/order/<int:order_id>/room/<int:room_id>"
        "/wall/<int:wall_id>/constraint/add",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def southbrook_api_constraint_add(
        self,
        order_id,
        room_id,
        wall_id,
        constraint_type=None,
        distance_from_left_mm=None,
        width_mm=None,
        height_mm=None,
        height_from_floor_mm=None,
        notes=None,
        **kw,
    ):
        try:
            order = self._southbrook_resolve_order(order_id)
        except MissingError:
            return {"error": "not_found"}
        except AccessError:
            return {"error": "forbidden"}

        try:
            room = self._get_room_scoped(order, room_id)
            wall = self._get_wall_scoped(room, wall_id)
        except AccessError:
            return {"error": "forbidden"}

        if not constraint_type:
            return {"error": "invalid", "detail": "constraint_type required"}

        # Dynamic selection lookup — future constraint types added to
        # the model don't need a controller edit.
        valid_types = {
            key for key, _label in request.env["southbrook.room.constraint"]
            ._fields["constraint_type"].selection
        }
        if constraint_type not in valid_types:
            return {
                "error": "invalid",
                "detail": f"unknown constraint_type {constraint_type!r}",
            }

        vals = {
            "wall_id": wall.id,
            "constraint_type": constraint_type,
            "distance_from_left_mm": int(distance_from_left_mm or 0),
            "width_mm": int(width_mm or 0),
        }
        if height_mm is not None:
            vals["height_mm"] = int(height_mm)
        if height_from_floor_mm is not None:
            vals["height_from_floor_mm"] = int(height_from_floor_mm)
        if notes is not None:
            vals["notes"] = notes

        try:
            c = request.env["southbrook.room.constraint"].sudo().create(vals)
        except (ValidationError, ValueError) as e:
            # Selection field bad-enum (e.g. unit_preference="bogus")
            # raises ValueError, not ValidationError — surface both
            # cleanly so a hand-crafted curl doesn't get a JSON-RPC
            # 500 (review #6).
            return {"error": "invalid", "detail": str(e)}

        return {"ok": True, "constraint": _serialize_constraint(c)}

    # ------------------------------------------------------------------
    # POST /southbrook/api/order/<order_id>/room/<room_id>/wall/<wall_id>/constraint/<constraint_id>/delete
    # ------------------------------------------------------------------
    @http.route(
        "/southbrook/api/order/<int:order_id>/room/<int:room_id>"
        "/wall/<int:wall_id>/constraint/<int:constraint_id>/delete",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def southbrook_api_constraint_delete(
        self, order_id, room_id, wall_id, constraint_id, **kw,
    ):
        try:
            order = self._southbrook_resolve_order(order_id)
        except MissingError:
            return {"error": "not_found"}
        except AccessError:
            return {"error": "forbidden"}

        try:
            room = self._get_room_scoped(order, room_id)
            wall = self._get_wall_scoped(room, wall_id)
            constraint = self._get_constraint_scoped(wall, constraint_id)
        except AccessError:
            return {"error": "forbidden"}

        constraint.sudo().unlink()
        return {"ok": True}

    # ------------------------------------------------------------------
    # POST /southbrook/api/order/<order_id>/line/<line_id>/place-on-wall
    # ------------------------------------------------------------------
    #
    # Phase 3.A — wall placement for cabinet lines. Backs the Room
    # Layout tab drag-and-drop interactivity coming in Phase 3.C. The
    # response returns BOTH the updated line dict AND the after-mutation
    # wall metrics (used_mm / remaining_mm / has_conflicts) so the
    # caller can refresh the line list AND the floor-plan SVG in one
    # round-trip without a follow-up /room/get fetch.
    #
    # wall_id=null is the unplace path (line.wall_id cleared + position
    # zeroed); the `wall` key in the response is null in that case.
    @http.route(
        "/southbrook/api/order/<int:order_id>/line/<int:line_id>"
        "/place-on-wall",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def southbrook_api_line_place_on_wall(
        self,
        order_id,
        line_id,
        wall_id=None,
        position_from_left_mm=0,
        **kw,
    ):
        try:
            order = self._southbrook_resolve_order(order_id)
        except MissingError:
            return {"error": "not_found"}
        except AccessError:
            return {"error": "forbidden"}

        # Position bounds — accept 0, reject negatives. Coerce to int so
        # a JSON string from a hand-crafted curl doesn't 500 the worker.
        try:
            pos_mm = int(position_from_left_mm or 0)
        except (TypeError, ValueError):
            return {
                "error": "invalid",
                "detail": "position_from_left_mm must be an integer",
            }
        if pos_mm < 0:
            return {
                "error": "invalid",
                "detail": "position_from_left_mm must be >= 0",
            }

        # Line ownership — must belong to the resolved order. Mismatch
        # surfaces as forbidden (NOT not_found) to match the Phase 2.A
        # no-existence-oracle convention.
        line = request.env["sale.order.line"].sudo().browse(line_id).exists()
        if not line or line.order_id.id != order.id:
            return {"error": "forbidden"}

        # Resolve target wall (None → unplace). The wall must live on a
        # room that lives on `order`; verify by walking room→wall via
        # the scope helpers so the existing AccessError → forbidden path
        # applies uniformly.
        wall = None
        if wall_id is not None:
            wall_rs = request.env["southbrook.room.wall"].sudo().browse(
                wall_id
            ).exists()
            if not wall_rs or not wall_rs.room_id:
                return {"error": "forbidden"}
            try:
                room = self._get_room_scoped(order, wall_rs.room_id.id)
                wall = self._get_wall_scoped(room, wall_rs.id)
            except AccessError:
                return {"error": "forbidden"}

        # Phase 3.C.1 — off-the-end overflow check. The drag/click UX
        # in 3.C.2a will surface this as a user-facing error path; better
        # to land the gate now so the caller can render a clean modal.
        # Skip when sb_width_mm == 0 — width is a computed field that
        # could fall through to 0 for malformed seed data, and rejecting
        # in that case would block placement entirely until the data is
        # fixed.
        if wall is not None and line.sb_width_mm and (
            pos_mm + int(line.sb_width_mm)
        ) > (wall.length_mm or 0):
            overshoot = (
                pos_mm + int(line.sb_width_mm)
            ) - (wall.length_mm or 0)
            return {
                "error": "out_of_bounds",
                "detail": (
                    f"Cabinet extends past wall edge by {overshoot}mm"
                ),
            }

        # Phase 3.C.1 — capture the previous wall recordset BEFORE the
        # write so the response can carry its post-move metrics too.
        # Empty recordset when the line was unplaced before this call.
        previous_wall_rec = line.wall_id

        try:
            if wall is None:
                line.sudo().write({
                    "wall_id": False,
                    "position_from_left_mm": 0,
                })
            else:
                line.sudo().write({
                    "wall_id": wall.id,
                    "position_from_left_mm": pos_mm,
                })
        except (ValidationError, ValueError) as e:
            return {"error": "invalid", "detail": str(e)}

        # Refresh ORM cache so wall.used_mm / remaining_mm / has_conflicts
        # reflect the just-written placement.
        line.invalidate_recordset()
        if wall is not None:
            wall.invalidate_recordset()
        # Phase 3.C.1 — when the line moved between walls, the FROM
        # wall's computed metrics are stale too (cabinet_line_ids O2m
        # membership flipped) — invalidate so the response carries
        # fresh used_mm / remaining_mm / has_conflicts.
        if previous_wall_rec and (
            wall is None or previous_wall_rec.id != wall.id
        ):
            previous_wall_rec.invalidate_recordset(
                ["used_mm", "remaining_mm", "has_conflicts"]
            )

        line_dict = {
            "id": line.id,
            "wall_id": line.wall_id.id if line.wall_id else False,
            "position_from_left_mm": line.position_from_left_mm,
            "is_positioned": line.is_positioned,
        }
        wall_dict = None
        if wall is not None:
            wall_dict = {
                "id": wall.id,
                "used_mm": wall.used_mm,
                "remaining_mm": wall.remaining_mm,
                "has_conflicts": wall.has_conflicts,
            }
        # Phase 3.C.1 — previous_wall is only meaningful when the line
        # MOVED off a different wall (not unplace-from-same / first-place).
        previous_wall_dict = None
        if previous_wall_rec and (
            wall is None or previous_wall_rec.id != wall.id
        ):
            previous_wall_dict = {
                "id": previous_wall_rec.id,
                "used_mm": previous_wall_rec.used_mm,
                "remaining_mm": previous_wall_rec.remaining_mm,
                "has_conflicts": previous_wall_rec.has_conflicts,
            }
        return {
            "ok": True,
            "line": line_dict,
            "wall": wall_dict,
            "previous_wall": previous_wall_dict,
        }
