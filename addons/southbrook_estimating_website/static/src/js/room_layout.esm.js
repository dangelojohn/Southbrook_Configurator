/** @odoo-module **/
/*
 * SPDX-License-Identifier: LGPL-3.0-only
 *
 * Phase 3.B — Room Layout tab (2026-06-27).
 *
 * Two OWL components:
 *
 *   RoomLayoutTab  — parent. Hosts the floor-plan SVG + a per-wall
 *                    metrics panel + the Unplaced Cabinets sidebar.
 *                    Handles the empty states (no room / no walls /
 *                    no lines).
 *
 *   FloorPlanSVG   — pure render. Takes room + lines, emits one big
 *                    inline <svg> with: room outline (per-wall lines),
 *                    constraints, cabinets (zone-coloured polygons),
 *                    gap markers, and wall name labels.
 *
 * READ-ONLY in 3.B. Click/drag/elevation toggle is Phase 3.C.
 *
 * Geometry sourced from the shared room_geometry.esm.js helper so the
 * wizard preview (Phase 2.C RoomOutlinePreview) and this floor plan
 * agree on wall orientation. Cabinets are projected along each wall's
 * direction vector + the cabinet depth (zone-based default) into the
 * room interior via the wall's normal.
 *
 * v19 / OWL tokenizer rules honoured throughout:
 *   - All t-att-* / t-if expressions use ||, &&, ! (never Python or/and/not).
 *   - `<` encoded as &lt; in attribute expressions where needed.
 *   - SVG sub-trees are plain XML — OWL handles the namespace.
 */
import { Component } from "@odoo/owl";
import { wallSegmentsForShape } from "@southbrook_estimating_website/js/room_geometry.esm";

// ----------------------------------------------------------------------
// Zone-based cabinet depth defaults — mirror sale_order_line.py's
// _SB_DEFAULT_*_DEPTH_MM constants. Wall cabinets float higher and
// shallower; tall cabinets project deepest. The floor plan is a top-
// down view so depth = how far the cabinet rectangle sticks INTO the
// room from the wall.
//
// `zone` selection values come straight from sale.order.line.zone
// (base_run / wall / tall / island / accessory / other).
// ----------------------------------------------------------------------

const DEPTH_MM_BY_ZONE = {
    base_run:  580,
    wall:      310,
    tall:      600,
    island:    600,
    accessory: 300,
    other:     580,
};

// Zone → CSS variable lookup. Variables themselves resolve at paint
// time via the design token cascade in portal_root.scss. The CSS class
// `.sb-room-plan-cab--<zone>` carries the fill in room_layout.scss
// (preferred over inline style so the theme rebind catches it).
const ZONE_CLASS = (zone) =>
    "sb-room-plan-cab sb-room-plan-cab--" + (zone || "other");

// SVG canvas geometry. Single global scale applied to room mm
// coordinates so the bbox fits within (viewWidth - 2*padding) by
// (viewHeight - 2*padding).
const SVG_W = 1024;
const SVG_H = 720;
const SVG_PAD = 60;

// Minimum gap (mm) that's worth surfacing as a dashed marker. Smaller
// gaps are construction tolerance, not a usable space.
const MIN_GAP_MM = 200;

// Cabinet width (in viewBox px after scaling) below which we skip the
// in-cabinet text label — anything narrower than this just gets the
// fill rectangle.
const MIN_LABEL_VBOX_PX = 30;

// ----------------------------------------------------------------------
// Geometry helpers — kept module-local so FloorPlanSVG.setup() can call
// them straight from `this._project*` getters without dragging a
// service dependency in.
// ----------------------------------------------------------------------

function _depthFor(line) {
    const z = line && line.zone;
    return DEPTH_MM_BY_ZONE[z] || DEPTH_MM_BY_ZONE.other;
}

// Compute the 4 corners of a cabinet polygon in room (mm) coordinates,
// given the wall segment, position from left, width, and depth.
function _cabinetCornersMm(seg, posMm, widthMm, depthMm) {
    const cornerFL = [
        seg.x0 + posMm * seg.dx,
        seg.y0 + posMm * seg.dy,
    ];
    const cornerFR = [
        seg.x0 + (posMm + widthMm) * seg.dx,
        seg.y0 + (posMm + widthMm) * seg.dy,
    ];
    const cornerBR = [
        cornerFR[0] + depthMm * seg.normalX,
        cornerFR[1] + depthMm * seg.normalY,
    ];
    const cornerBL = [
        cornerFL[0] + depthMm * seg.normalX,
        cornerFL[1] + depthMm * seg.normalY,
    ];
    return [cornerFL, cornerFR, cornerBR, cornerBL];
}

// Constraints have no depth — but to render them as visible rects on
// the floor plan we give them a small "presence" depth that varies by
// type. Sized-on-wall (windows/doors) sit ON the wall and are barely
// inset; appliances (oven/cooktop/dishwasher) project a small distance
// to read as a fixture, not a graffiti label.
function _constraintDepthMm(type) {
    if (["window", "door", "structural_post", "power_outlet"].includes(type)) {
        return 40;
    }
    return 120;
}

function _constraintCornersMm(seg, c) {
    const posMm = c.distance_from_left_mm || 0;
    const widthMm = c.width_mm || 100;
    const depthMm = _constraintDepthMm(c.constraint_type);
    return _cabinetCornersMm(seg, posMm, widthMm, depthMm);
}

// ----------------------------------------------------------------------
// FloorPlanSVG — pure render. Computes geometry on every render; OWL
// reactivity batches into one paint per props change so no debounce.
// ----------------------------------------------------------------------

class FloorPlanSVG extends Component {
    static template = "southbrook_estimating_website.FloorPlanSVG";
    static props = {
        room: { type: Object, optional: true },
        lines: { type: Array, optional: true },
    };

    get _viewBox() {
        return "0 0 " + SVG_W + " " + SVG_H;
    }

    // Build the per-wall segment list using the shape geometry from
    // room_geometry.esm.js. When the helper returns null (shape we
    // don't render properly — g_shape, peninsula, island, custom) we
    // fall back to a stacked horizontal layout: each wall becomes its
    // own labelled horizontal segment one below the other.
    get _segments() {
        const room = this.props.room;
        if (!room || !room.walls || room.walls.length === 0) return [];
        const segs = wallSegmentsForShape(room.layout_shape, room.walls);
        if (segs) {
            // Carry the original wall record forward so cabinet
            // rendering can match by wall.id.
            for (let i = 0; i < segs.length; i += 1) {
                segs[i].wall = room.walls[i];
            }
            return segs;
        }
        // Fallback: stack each wall horizontally. We render at y =
        // offset per wall index so they don't overlap. Cabinets still
        // project +Y (interior "down") off each wall.
        const stack = [];
        const stride = 1500; // mm between stacked walls
        for (let i = 0; i < room.walls.length; i += 1) {
            const w = room.walls[i];
            const y = i * stride;
            stack.push({
                name: w.name || "Wall " + String.fromCharCode(65 + i),
                length_mm: Math.max(0, Number(w.length_mm) || 0),
                x0: 0,
                y0: y,
                x1: Math.max(0, Number(w.length_mm) || 0),
                y1: y,
                dx: 1,
                dy: 0,
                normalX: 0,
                normalY: 1,
                wall: w,
                fallback: true,
            });
        }
        return stack;
    }

    // Bounding box + global scale + offset. Computed once per render
    // over every point the SVG will draw — wall endpoints, cabinet
    // corners, constraint corners. Cached on `this` for the duration
    // of this render via the OWL component lifecycle (a fresh instance
    // for each render in practice).
    get _transform() {
        const segs = this._segments;
        if (segs.length === 0) {
            return { scale: 1, offX: SVG_PAD, offY: SVG_PAD, minX: 0, minY: 0 };
        }
        let minX = Infinity;
        let minY = Infinity;
        let maxX = -Infinity;
        let maxY = -Infinity;
        const acc = (x, y) => {
            if (x < minX) minX = x;
            if (y < minY) minY = y;
            if (x > maxX) maxX = x;
            if (y > maxY) maxY = y;
        };
        // Walls themselves.
        for (const s of segs) {
            acc(s.x0, s.y0);
            acc(s.x1, s.y1);
            // Constraints projected off this wall.
            const wall = s.wall || {};
            const constraints = wall.constraints || [];
            for (const c of constraints) {
                const corners = _constraintCornersMm(s, c);
                for (const [x, y] of corners) acc(x, y);
            }
        }
        // Cabinets.
        const linesByWall = this._linesByWallId;
        for (const s of segs) {
            const wallId = s.wall && s.wall.id;
            if (!wallId) continue;
            const lines = linesByWall.get(wallId) || [];
            for (const line of lines) {
                const corners = _cabinetCornersMm(
                    s,
                    line.position_from_left_mm || 0,
                    line.sb_width_mm || 600,
                    _depthFor(line),
                );
                for (const [x, y] of corners) acc(x, y);
            }
        }
        if (!Number.isFinite(minX)) {
            return { scale: 1, offX: SVG_PAD, offY: SVG_PAD, minX: 0, minY: 0 };
        }
        const bw = Math.max(1, maxX - minX);
        const bh = Math.max(1, maxY - minY);
        const scale = Math.min(
            (SVG_W - 2 * SVG_PAD) / bw,
            (SVG_H - 2 * SVG_PAD) / bh,
        );
        // Centre the bbox in the viewport.
        const offX = SVG_PAD + ((SVG_W - 2 * SVG_PAD) - bw * scale) / 2;
        const offY = SVG_PAD + ((SVG_H - 2 * SVG_PAD) - bh * scale) / 2;
        return { scale, offX, offY, minX, minY };
    }

    // Map wall.id → array of placed lines on that wall, sorted by
    // position_from_left_mm. Cached as a getter — OWL re-derives per
    // render which is what we want (props changes invalidate).
    get _linesByWallId() {
        const out = new Map();
        const lines = this.props.lines || [];
        for (const l of lines) {
            if (!l.wall_id) continue;
            if (!out.has(l.wall_id)) out.set(l.wall_id, []);
            out.get(l.wall_id).push(l);
        }
        for (const arr of out.values()) {
            arr.sort(
                (a, b) =>
                    (a.position_from_left_mm || 0)
                    - (b.position_from_left_mm || 0),
            );
        }
        return out;
    }

    // Project a single (x, y) in room mm to viewBox px.
    _proj(x, y) {
        const t = this._transform;
        return [
            t.offX + (x - t.minX) * t.scale,
            t.offY + (y - t.minY) * t.scale,
        ];
    }

    // Wall lines — one entry per segment, projected to viewBox px.
    get _wallLines() {
        const out = [];
        for (const s of this._segments) {
            const [x1, y1] = this._proj(s.x0, s.y0);
            const [x2, y2] = this._proj(s.x1, s.y1);
            out.push({
                key: s.wall && s.wall.id ? "w-" + s.wall.id : "w-" + out.length,
                x1, y1, x2, y2,
                name: s.name,
                hasConflicts: !!(s.wall && s.wall.has_conflicts),
            });
        }
        return out;
    }

    // Wall name labels — placed at the segment midpoint, offset
    // OUTWARD (opposite the interior normal) by 20 viewBox-px so the
    // label sits outside the room rather than overlapping cabinets.
    get _wallLabels() {
        const out = [];
        for (const s of this._segments) {
            const [mx, my] = this._proj(
                (s.x0 + s.x1) / 2,
                (s.y0 + s.y1) / 2,
            );
            // Outward normal = negative of interior normal (viewBox px).
            const ox = mx - s.normalX * 24;
            const oy = my - s.normalY * 24 + 4;  // +4 baseline nudge
            out.push({
                key: "wl-" + (s.wall && s.wall.id ? s.wall.id : out.length),
                x: ox,
                y: oy,
                name: s.name,
            });
        }
        return out;
    }

    // Constraints — one polygon per constraint, projected to px.
    get _constraintPolys() {
        const out = [];
        for (const s of this._segments) {
            const wall = s.wall || {};
            const constraints = wall.constraints || [];
            for (const c of constraints) {
                const corners = _constraintCornersMm(s, c);
                const pts = corners
                    .map(([x, y]) => {
                        const [px, py] = this._proj(x, y);
                        return px.toFixed(1) + "," + py.toFixed(1);
                    })
                    .join(" ");
                // Label centroid (4-corner centroid is fine for a quad).
                let cx = 0;
                let cy = 0;
                for (const [x, y] of corners) {
                    const [px, py] = this._proj(x, y);
                    cx += px;
                    cy += py;
                }
                cx /= 4;
                cy /= 4;
                out.push({
                    key: "c-" + c.id,
                    points: pts,
                    type: c.constraint_type,
                    label: this._humanConstraint(c.constraint_type),
                    cx,
                    cy,
                });
            }
        }
        return out;
    }

    // Cabinet polygons — zone-coloured, conflict-bordered when the
    // wall has conflicts. Labels (short SKU) only render when the
    // cabinet's projected width is wide enough to fit them.
    get _cabinetPolys() {
        const out = [];
        const lbw = this._linesByWallId;
        for (const s of this._segments) {
            const wall = s.wall || {};
            const wallId = wall.id;
            if (!wallId) continue;
            const lines = lbw.get(wallId) || [];
            for (const line of lines) {
                const width = line.sb_width_mm || 600;
                const depth = _depthFor(line);
                const corners = _cabinetCornersMm(
                    s,
                    line.position_from_left_mm || 0,
                    width,
                    depth,
                );
                const pts = corners
                    .map(([x, y]) => {
                        const [px, py] = this._proj(x, y);
                        return px.toFixed(1) + "," + py.toFixed(1);
                    })
                    .join(" ");
                // Centroid for label placement.
                let cx = 0;
                let cy = 0;
                for (const [x, y] of corners) {
                    const [px, py] = this._proj(x, y);
                    cx += px;
                    cy += py;
                }
                cx /= 4;
                cy /= 4;
                // Approximate the cabinet's projected width in viewBox
                // px to decide whether to render the inline label.
                const widthPx = width * this._transform.scale;
                out.push({
                    key: "cab-" + line.id,
                    points: pts,
                    zoneClass: ZONE_CLASS(line.zone),
                    conflict: !!wall.has_conflicts,
                    label: this._shortLabel(line.name || ""),
                    cx,
                    cy,
                    showLabel: widthPx >= MIN_LABEL_VBOX_PX,
                });
            }
        }
        return out;
    }

    // Gap markers — for each wall, walk the sorted cabinet list and
    // emit a dashed rectangle for every contiguous unused stretch
    // >= MIN_GAP_MM. Uses cabinet depth = 200 mm for visual presence
    // (gaps don't have a real depth).
    get _gapMarkers() {
        const out = [];
        const lbw = this._linesByWallId;
        for (const s of this._segments) {
            const wall = s.wall || {};
            const wallId = wall.id;
            if (!wallId) continue;
            const lines = lbw.get(wallId) || [];
            const len = wall.length_mm || s.length_mm || 0;
            let cursor = 0;
            const ranges = [];
            for (const line of lines) {
                const lo = line.position_from_left_mm || 0;
                const hi = lo + (line.sb_width_mm || 0);
                if (lo > cursor) ranges.push([cursor, lo]);
                cursor = Math.max(cursor, hi);
            }
            if (cursor < len) ranges.push([cursor, len]);
            for (const [lo, hi] of ranges) {
                const gap = hi - lo;
                if (gap < MIN_GAP_MM) continue;
                const corners = _cabinetCornersMm(s, lo, gap, 200);
                const pts = corners
                    .map(([x, y]) => {
                        const [px, py] = this._proj(x, y);
                        return px.toFixed(1) + "," + py.toFixed(1);
                    })
                    .join(" ");
                let cx = 0;
                let cy = 0;
                for (const [x, y] of corners) {
                    const [px, py] = this._proj(x, y);
                    cx += px;
                    cy += py;
                }
                cx /= 4;
                cy /= 4;
                const widthPx = gap * this._transform.scale;
                out.push({
                    key: "g-" + wallId + "-" + lo,
                    points: pts,
                    label: gap + " mm gap",
                    cx,
                    cy,
                    showLabel: widthPx >= 40,
                });
            }
        }
        return out;
    }

    // Background bbox rect for the room interior — provides a subtle
    // floor colour behind the walls. Sized to the bbox so it stays
    // tight around the room geometry rather than filling the whole
    // viewport.
    get _bgRect() {
        const t = this._transform;
        const segs = this._segments;
        if (segs.length === 0) return null;
        let minX = Infinity;
        let minY = Infinity;
        let maxX = -Infinity;
        let maxY = -Infinity;
        for (const s of segs) {
            for (const [x, y] of [
                [s.x0, s.y0], [s.x1, s.y1],
            ]) {
                if (x < minX) minX = x;
                if (y < minY) minY = y;
                if (x > maxX) maxX = x;
                if (y > maxY) maxY = y;
            }
        }
        const [px1, py1] = [t.offX + (minX - t.minX) * t.scale,
                            t.offY + (minY - t.minY) * t.scale];
        const [px2, py2] = [t.offX + (maxX - t.minX) * t.scale,
                            t.offY + (maxY - t.minY) * t.scale];
        return {
            x: px1 - 8,
            y: py1 - 8,
            w: (px2 - px1) + 16,
            h: (py2 - py1) + 16,
        };
    }

    // Translate enum codes → user-readable label. Kept local rather
    // than imported from portal_boot.esm.js so this component stays
    // a pure leaf (room_layout depends on portal_boot's rpcJsonCall
    // helper transitively via the wizard, but we don't need it here).
    _humanConstraint(code) {
        return {
            window: "Window",
            door: "Door",
            sink: "Sink",
            cooktop: "Cooktop",
            oven: "Oven",
            dishwasher: "Dishwasher",
            rangehood: "Rangehood",
            fridge_space: "Fridge",
            power_outlet: "Outlet",
            structural_post: "Post",
            other: "Other",
        }[code] || code;
    }

    // Truncate cabinet display name to ~8 chars. Many lines come back
    // as "Base Cabinet 24\" 2 Door" — too long to render inside a
    // small polygon; the right side (size + door count) is what
    // distinguishes them visually so we keep the tail.
    _shortLabel(name) {
        if (!name) return "";
        // Prefer the first whitespace-delimited token if it looks
        // SKU-like (no spaces in the first 8 chars), else clip.
        const trimmed = name.trim();
        if (trimmed.length <= 8) return trimmed;
        return trimmed.slice(0, 8);
    }
}

// ----------------------------------------------------------------------
// RoomLayoutTab — parent. Hosts the SVG + sidebar + per-wall metrics.
// Owns the empty-state messaging.
// ----------------------------------------------------------------------

export class RoomLayoutTab extends Component {
    static template = "southbrook_estimating_website.RoomLayoutTab";
    static components = { FloorPlanSVG };
    static props = {
        room: { type: [Object, { value: null }], optional: true },
        lines: { type: Array, optional: true },
    };

    // ------------------------------------------------------------------
    // Empty-state predicates — drive the t-if/t-elif cascade in the
    // template.
    // ------------------------------------------------------------------

    get _hasRoom() {
        return !!this.props.room;
    }

    get _hasWalls() {
        return !!(this.props.room && this.props.room.walls
                  && this.props.room.walls.length > 0);
    }

    get _hasLines() {
        return !!(this.props.lines && this.props.lines.length > 0);
    }

    // ------------------------------------------------------------------
    // Sidebar — unplaced cabinets list. Pure derived data; OWL re-
    // computes on props change.
    // ------------------------------------------------------------------

    get _unplacedLines() {
        const lines = this.props.lines || [];
        return lines.filter((l) => !l.wall_id);
    }

    get _unplacedCount() {
        return this._unplacedLines.length;
    }

    // ------------------------------------------------------------------
    // Per-wall metrics row. One entry per wall; the template renders
    // it as a small table next to the SVG.
    // ------------------------------------------------------------------

    get _wallMetrics() {
        const room = this.props.room;
        if (!room || !room.walls) return [];
        return room.walls.map((w) => ({
            id: w.id,
            name: w.name,
            length_mm: w.length_mm || 0,
            used_mm: w.used_mm || 0,
            remaining_mm: w.remaining_mm || 0,
            has_conflicts: !!w.has_conflicts,
            // Conflict count isn't directly exposed by Phase 1/2 — we
            // surface the boolean as 0 or 1. Phase 3.C upgrade can
            // count overlapping constraint×cabinet pairs.
            conflict_count: w.has_conflicts ? 1 : 0,
        }));
    }

    // Totals row at the bottom of the metrics table. Aggregates the
    // per-wall numbers so the user has a one-glance order summary
    // without scanning every wall.
    get _wallTotals() {
        const metrics = this._wallMetrics;
        const length_mm = metrics.reduce((a, m) => a + m.length_mm, 0);
        const used_mm = metrics.reduce((a, m) => a + m.used_mm, 0);
        const remaining_mm = length_mm - used_mm;
        return { length_mm, used_mm, remaining_mm };
    }
}
