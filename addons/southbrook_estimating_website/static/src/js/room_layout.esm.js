/** @odoo-module **/
/*
 * SPDX-License-Identifier: LGPL-3.0-only
 *
 * Phase 3.B — Room Layout tab (2026-06-27).
 * Phase 3.C.2a — tap interactivity layer (2026-06-27).
 * Phase 3.C.2c — Floor ↔ Elevation view toggle (2026-06-27).
 * Phase 3.C.2d — interactive wall resize (2026-06-27).
 *
 * Components:
 *
 *   RoomLayoutTab     — parent. Hosts the floor-plan SVG + a per-wall
 *                       metrics panel + the Unplaced Cabinets sidebar.
 *                       Handles the empty states (no room / no walls /
 *                       no lines). 3.C.2a adds three click affordances:
 *                       cabinet poly → highlight line, gap rect → catalog
 *                       w/ auto-place, unplaced "Assign..." → modal.
 *                       3.C.2c adds a "View: [Floor | Elevation]" toggle
 *                       above the canvas; in elevation mode a single
 *                       wall is rendered side-on (read-only).
 *
 *   FloorPlanSVG      — pure render. Takes room + lines, emits one big
 *                       inline <svg> with: room outline (per-wall lines),
 *                       constraints, cabinets (zone-coloured polygons),
 *                       gap markers, and wall name labels. 3.C.2a wires
 *                       click handlers on cabinet polygons + gap rects.
 *
 *   WallElevationSVG  — pure render. Phase 3.C.2c. Side-on cross-section
 *                       of a single wall: cabinets as front-face rectangles
 *                       stacked by zone (base_run 0-900, wall 1400-2100,
 *                       tall 0-2100, others 0-900), floor / ceiling /
 *                       worktop reference lines, constraint cutouts.
 *                       Read-only — no drag/click handlers.
 *
 *   AssignToWallModal — overlay opened when the user clicks "Assign..."
 *                       on an unplaced cabinet. Wall dropdown + position
 *                       input + Cancel/Assign. Parent owns the RPC.
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
import { Component, useExternalListener, useRef, useState } from "@odoo/owl";
import { wallSegmentsForShape } from "@southbrook_estimating_website/js/room_geometry.esm";

// ----------------------------------------------------------------------
// Phase 4 — mm ↔ ft/in conversion helpers (module-local).
//
// Mirrors OrderBuilder._imperialFromMm / _humanLen so the room_layout
// surface can render length labels in the unit the user picked on the
// Room Setup tab's segmented toggle — without reaching back into the
// parent reactive store. Module-local (not class-bound) so all three
// components (RoomLayoutTab, FloorPlanSVG, AssignToWallModal) share one
// canonical implementation.
//
// Helpers are intentionally tiny + pure: extraction into a shared util
// module would just move the dependency around — keeping them next to
// their callers keeps the diff readable.
// ----------------------------------------------------------------------

function _imperialFromMm(mm) {
    const inches = Math.round((Number(mm) || 0) / 25.4);
    const feet = Math.floor(inches / 12);
    const remIn = inches - feet * 12;
    if (feet === 0) return `${remIn}"`;
    if (remIn === 0) return `${feet}'`;
    return `${feet}' ${remIn}"`;
}

function _humanLenWithPref(mm, pref) {
    if (!mm && mm !== 0) return "—";
    if (pref === "imperial") return _imperialFromMm(mm);
    return `${Math.round(Number(mm) || 0)} mm`;
}

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

// ----------------------------------------------------------------------
// Phase 3.C.2c — elevation Y-range per zone, in mm above floor.
//
// Returns [y0_mm, y1_mm] — the bottom and top of the cabinet's front
// face when viewed from the side. Mirror the standard cabinet stacking
// used in the BOM rollup:
//   - base_run / island / accessory / other → sit on the floor, 900mm
//     to the worktop underside.
//   - wall → float at 1400mm above floor (worktop + 4" reveal +
//     backsplash height), 700mm tall → top at 2100mm.
//   - tall → floor-to-ceiling pantry / oven tower, 0 → 2100mm.
//
// Anything taller than this clamps via `maxHeight = max(ceiling, 2100)`
// in WallElevationSVG._transform so the cabinet still fits the view.
// ----------------------------------------------------------------------

const ELEVATION_BY_ZONE = {
    base_run:  [0,    900],
    wall:      [1400, 2100],
    tall:      [0,    2100],
    island:    [0,    900],
    accessory: [0,    900],
    other:     [0,    900],
};

function _elevationRangeFor(line) {
    const z = (line && line.zone) || "other";
    return ELEVATION_BY_ZONE[z] || ELEVATION_BY_ZONE.other;
}

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
        // Phase 3.C.2a — click affordances. Both optional so the
        // component still renders read-only when used without
        // interactivity (e.g. inside the wizard preview pane).
        onCabinetClick: { type: Function, optional: true },
        onGapClick: { type: Function, optional: true },
        // Phase 3.C.2b — drag-along-wall. Fires with the snapped
        // (25mm) new position_from_left_mm. Cross-wall drag is
        // NOT supported here — the position is clamped to the
        // current wall; cross-wall changes still go through the
        // AssignToWallModal. Also fired by the ± shifter buttons
        // surfaced for coarse-pointer (touch) devices.
        onCabinetDragEnd: { type: Function, optional: true },
        // Phase 3.C.2d — wall-resize drag end. Fires with the snapped
        // (25mm) new wall length_mm. Only fired for walls whose
        // layout_shape is in _isResizable (straight | island today —
        // see the helper for why multi-wall shapes are deferred). For
        // multi-wall shapes the per-wall sidebar surfaces ± 100mm
        // buttons that call this same handler instead.
        onWallResizeEnd: { type: Function, optional: true },
        // Phase 4 — unit preference (mm | imperial) for any length
        // labels rendered inside the SVG (today: gap markers).
        unitPreference: { type: String, optional: true },
    };

    // Phase 3.C.2b — drag state + global pointer listeners.
    //
    // Drag detection rules (mirror the 3.C.2a comment block):
    //   - pointerdown on a cabinet polygon arms the drag (records
    //     lineId, original mm, downXY, moved=false).
    //   - pointermove flips `moved = true` only after the cursor has
    //     travelled > 5px from downXY (the click-vs-drag threshold).
    //   - pointerup with moved=true → snap to 25mm + onCabinetDragEnd.
    //     pointerup with moved=false → onCabinetClick (the existing tap).
    //
    // Pointer move/up are registered at the document level so dragging
    // outside the polygon bounds still flows. `setPointerCapture` on
    // the polygon is the belt-and-braces equivalent — keeps events
    // routed to the originating element even when the cursor exits.
    setup() {
        this.dragState = useState({
            lineId: null,
            originalMm: null,
            currentMm: null,
            downXY: null,
            moved: false,
        });
        // Phase 3.C.2d — wall-resize drag state. Kept SEPARATE from
        // the cabinet dragState above so a stray pointermove cannot
        // conflate the two (the document-level listener routes by
        // checking which state has an active id). Same lifecycle as
        // the cabinet drag — armed on pointerdown, flipped to
        // `moved` after the 5px threshold, snapped + RPC'd on
        // pointerup.
        this.wallDragState = useState({
            wallId: null,
            originalLengthMm: null,
            currentLengthMm: null,
            downXY: null,
            moved: false,
        });
        // SVG element ref for coordinate transforms (getScreenCTM +
        // createSVGPoint live on the SVGSVGElement).
        this.svgRef = useRef("svgRoot");
        // Document-level move/up so drag continues even when the
        // cursor leaves the cabinet polygon. OWL auto-cleans on
        // unmount; no need for manual removeEventListener.
        useExternalListener(document, "pointermove", this._onPointerMove);
        useExternalListener(document, "pointerup", this._onPointerUp);
    }

    // Phase 3.C.2d — V1 scope gate. Only single-wall topologies get
    // SVG drag handles: there is no shared corner to displace, so
    // resizing is unambiguous. Multi-wall shapes (l_shape, u_shape,
    // galley, g_shape) defer to the sidebar's ± 100mm buttons in
    // RoomLayoutTab — same /room/<rid>/update RPC, simpler topology.
    // SVG drag for multi-wall shapes is a follow-up that needs to
    // resolve the "drag the corner OR drag the outer end" UX choice.
    _isResizable(shape) {
        return shape === "straight" || shape === "island";
    }

    // Phase 3.C.2a — click handlers. Both no-op when the parent didn't
    // wire a callback so the SVG falls back to read-only.
    _onCabinetClick(lineId) {
        if (this.props.onCabinetClick) this.props.onCabinetClick(lineId);
    }

    _onGapClick(wallId, gapMm, positionMm) {
        if (this.props.onGapClick) this.props.onGapClick(wallId, gapMm, positionMm);
    }

    // Phase 3.C.2b — pointerdown on a cabinet polygon. Arms drag
    // state; tap-vs-drag decision is deferred to pointerup based on
    // whether `moved` got flipped (> 5px movement) in the interim.
    _onCabinetPointerDown = (line, ev) => {
        // Without onCabinetDragEnd wired, fall through to the existing
        // tap path — the polygon's t-on-click handler still fires.
        if (!this.props.onCabinetDragEnd) return;
        // Inhibit default text selection / image-drag ghost — without
        // this Chrome will start a native HTML drag on the SVG node.
        ev.preventDefault();
        this.dragState.lineId = line.id;
        this.dragState.originalMm = line.position_from_left_mm || 0;
        this.dragState.currentMm = line.position_from_left_mm || 0;
        this.dragState.downXY = { x: ev.clientX, y: ev.clientY };
        this.dragState.moved = false;
        // Keep pointermove flowing to this element even when the
        // cursor leaves the polygon. Optional-chained because some
        // older browsers don't expose setPointerCapture on SVG nodes.
        if (ev.target && ev.target.setPointerCapture) {
            try {
                ev.target.setPointerCapture(ev.pointerId);
            } catch (_e) {
                // Some browsers throw if the pointer isn't down on
                // this element (race). Safe to swallow.
            }
        }
    };

    _onPointerMove = (ev) => {
        // Phase 3.C.2d — wall-resize branch first so a wall drag
        // doesn't fall through into the cabinet drag path. The two
        // states are mutually exclusive in practice (a pointerdown
        // arms one or the other, never both) but the explicit
        // ordering keeps the conditional cheap.
        if (this.wallDragState.wallId !== null) {
            this._onWallPointerMove(ev);
            return;
        }
        if (this.dragState.lineId === null) return;
        const dx = ev.clientX - this.dragState.downXY.x;
        const dy = ev.clientY - this.dragState.downXY.y;
        const dist2 = dx * dx + dy * dy;
        if (!this.dragState.moved && dist2 < 25) {
            // Under the 5px threshold — still a tap candidate.
            return;
        }
        this.dragState.moved = true;
        // Project to mm along the wall. _pxToMmAlongWall handles the
        // CTM inverse + reverse _transform + projection onto the
        // wall unit vector.
        const line = this._draggingLine;
        if (!line) return;
        const seg = this._segments.find(
            (s) => s.wall && s.wall.id === line.wall_id,
        );
        if (!seg) return;
        const raw = this._pxToMmAlongWall(seg, ev.clientX, ev.clientY);
        if (raw === null) return;
        const wallLen = (seg.wall && seg.wall.length_mm) || seg.length_mm || 0;
        const cabW = line.sb_width_mm || 0;
        const maxPos = Math.max(0, wallLen - cabW);
        const clamped = Math.max(0, Math.min(maxPos, raw));
        this.dragState.currentMm = clamped;
    };

    _onPointerUp = (_ev) => {
        // Phase 3.C.2d — wall-resize branch (mirror _onPointerMove).
        if (this.wallDragState.wallId !== null) {
            this._onWallPointerUp(_ev);
            return;
        }
        if (this.dragState.lineId === null) return;
        const lineId = this.dragState.lineId;
        const moved = this.dragState.moved;
        const currentMm = this.dragState.currentMm;
        // Reset drag state first so the next render skips the
        // semi-transparent overlay even if the RPC takes a moment.
        this.dragState.lineId = null;
        this.dragState.originalMm = null;
        this.dragState.currentMm = null;
        this.dragState.downXY = null;
        this.dragState.moved = false;
        if (moved) {
            // Snap to 25mm grid on drop.
            const snapped = Math.round(currentMm / 25) * 25;
            if (this.props.onCabinetDragEnd) {
                this.props.onCabinetDragEnd(lineId, snapped);
            }
        } else {
            // No movement — treat as a tap.
            this._onCabinetClick(lineId);
        }
    };

    // ------------------------------------------------------------------
    // Phase 3.C.2d — wall resize handlers.
    //
    // Mental model:
    //   - The wall starts at (x0, y0) and grows in the (dx, dy)
    //     unit-vector direction. Resizing keeps (x0, y0) fixed and
    //     moves (x1, y1) outward / inward along the wall axis.
    //   - Min length 200mm prevents the wall collapsing to zero
    //     (which would break the SVG bbox + auto-place semantics).
    //   - Snap to 25mm on drop, same grid as cabinet drag.
    //
    // The handle is a small circle at the OUTER endpoint. For the
    // V1 (straight + island only) "outer" is unambiguously (x1, y1)
    // because there's no shared corner with another wall.
    // ------------------------------------------------------------------

    _onWallPointerDown = (wall, ev) => {
        if (!this.props.onWallResizeEnd) return;
        if (!wall || !wall.id) return;
        // Inhibit default text selection / native HTML drag (same
        // rationale as the cabinet drag path).
        ev.preventDefault();
        // Belt-and-braces — stopPropagation so the underlying SVG
        // background never receives this pointerdown (we don't want
        // a click affordance under the handle to misfire).
        if (ev.stopPropagation) ev.stopPropagation();
        this.wallDragState.wallId = wall.id;
        this.wallDragState.originalLengthMm = wall.length_mm || 0;
        this.wallDragState.currentLengthMm = wall.length_mm || 0;
        this.wallDragState.downXY = { x: ev.clientX, y: ev.clientY };
        this.wallDragState.moved = false;
        if (ev.target && ev.target.setPointerCapture) {
            try {
                ev.target.setPointerCapture(ev.pointerId);
            } catch (_e) {
                // Pointer capture races — safe to swallow.
            }
        }
    };

    _onWallPointerMove = (ev) => {
        if (this.wallDragState.wallId === null) return;
        const dx = ev.clientX - this.wallDragState.downXY.x;
        const dy = ev.clientY - this.wallDragState.downXY.y;
        const dist2 = dx * dx + dy * dy;
        if (!this.wallDragState.moved && dist2 < 25) {
            // Under the 5px threshold — no-op (the wall handle has
            // no tap semantics, but the threshold keeps the drag
            // from firing on a stationary click).
            return;
        }
        this.wallDragState.moved = true;
        const seg = this._segments.find(
            (s) => s.wall && s.wall.id === this.wallDragState.wallId,
        );
        if (!seg) return;
        // Project the cursor onto the wall direction vector to get the
        // signed mm offset from (x0, y0) — same projection math as the
        // cabinet drag, just used as a length not a position.
        const raw = this._pxToMmAlongWall(seg, ev.clientX, ev.clientY);
        if (raw === null) return;
        // Min length 200mm — prevents wall collapse + keeps the SVG
        // bbox from degenerating. No max — long runs are valid.
        this.wallDragState.currentLengthMm = Math.max(200, raw);
    };

    _onWallPointerUp = (_ev) => {
        if (this.wallDragState.wallId === null) return;
        const wallId = this.wallDragState.wallId;
        const moved = this.wallDragState.moved;
        const currentLen = this.wallDragState.currentLengthMm;
        // Reset state first so the dashed-ghost overlay disappears
        // immediately on drop, even before the RPC returns.
        this.wallDragState.wallId = null;
        this.wallDragState.originalLengthMm = null;
        this.wallDragState.currentLengthMm = null;
        this.wallDragState.downXY = null;
        this.wallDragState.moved = false;
        if (!moved) return;
        // Snap to 25mm + min 200mm clamp, then fire the parent's
        // RPC handler.
        const snapped = Math.max(200, Math.round(currentLen / 25) * 25);
        if (this.props.onWallResizeEnd) {
            this.props.onWallResizeEnd(wallId, snapped);
        }
    };

    // Phase 3.C.2b — touch shifter (± 25mm). Each click bumps the
    // line's position_from_left_mm by ±25mm via the same drag-end
    // RPC. Clamped to [0, wall.length_mm - cabinet.sb_width_mm].
    _onCabinetShift = (line, deltaMm) => {
        if (!this.props.onCabinetDragEnd) return;
        const seg = this._segments.find(
            (s) => s.wall && s.wall.id === line.wall_id,
        );
        const wallLen = seg
            ? ((seg.wall && seg.wall.length_mm) || seg.length_mm || 0)
            : 0;
        const cabW = line.sb_width_mm || 0;
        const maxPos = Math.max(0, wallLen - cabW);
        const cur = line.position_from_left_mm || 0;
        const next = Math.max(0, Math.min(maxPos, cur + deltaMm));
        this.props.onCabinetDragEnd(line.id, next);
    };

    // Lookup the line currently being dragged out of props.lines. Used
    // by _onPointerMove to project the cursor against the right wall.
    get _draggingLine() {
        if (this.dragState.lineId === null) return null;
        const lines = this.props.lines || [];
        return lines.find((l) => l.id === this.dragState.lineId) || null;
    }

    // Convert a screen-space (clientX, clientY) into a position along
    // the wall segment, in mm. Path:
    //   1. screen → SVG viewBox via getScreenCTM().inverse()
    //   2. viewBox → mm via reverse of _transform (offX/offY/scale)
    //   3. (mmX, mmY) relative to wall start, projected onto the wall
    //      unit vector (dx, dy) → the signed mm offset along the wall.
    _pxToMmAlongWall(seg, screenX, screenY) {
        const svg = this.svgRef.el;
        if (!svg) return null;
        const ctm = svg.getScreenCTM && svg.getScreenCTM();
        if (!ctm) return null;
        const pt = svg.createSVGPoint();
        pt.x = screenX;
        pt.y = screenY;
        const svgPt = pt.matrixTransform(ctm.inverse());
        const t = this._transform;
        if (!t || !t.scale) return null;
        const mmX = (svgPt.x - t.offX) / t.scale + t.minX;
        const mmY = (svgPt.y - t.offY) / t.scale + t.minY;
        const proj = (mmX - seg.x0) * seg.dx + (mmY - seg.y0) * seg.dy;
        return proj;
    }

    // Phase 4 — length formatter honouring props.unitPreference. Pure
    // wrapper around the module-local helper so the template can read
    // `_humanLen(mm)` without spelling out the pref every time.
    _humanLen(mm) {
        return _humanLenWithPref(mm, this.props.unitPreference || "mm");
    }

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

    // Phase 3.C.2d — outer-endpoint handle positions, in viewBox px.
    // Only emitted when the room's layout_shape passes _isResizable
    // (straight | island). For each resizable wall the outer end is
    // unambiguously (x1, y1) — no shared corner ambiguity in single-
    // wall topologies. Multi-wall shapes get the empty list (handles
    // never render), and the sidebar's ± 100mm buttons handle them.
    get _resizableWalls() {
        const room = this.props.room || {};
        if (!this._isResizable(room.layout_shape)) return [];
        if (!this.props.onWallResizeEnd) return [];
        const out = [];
        for (const s of this._segments) {
            if (!s.wall || !s.wall.id) continue;
            const [cx, cy] = this._proj(s.x1, s.y1);
            out.push({ wall: s.wall, cx, cy });
        }
        return out;
    }

    // Phase 3.C.2d — dashed-ghost preview line endpoints, in viewBox px.
    // Computed from the live wallDragState.currentLengthMm projected
    // along the dragged wall's direction vector. Returns null when no
    // wall drag is active or the source segment can't be matched (e.g.
    // the wall was deleted server-side mid-drag — defensive).
    get _wallDragPreview() {
        const id = this.wallDragState.wallId;
        if (id === null) return null;
        if (!this.wallDragState.moved) return null;
        const seg = this._segments.find(
            (s) => s.wall && s.wall.id === id,
        );
        if (!seg) return null;
        const len = this.wallDragState.currentLengthMm || 0;
        const [x1, y1] = this._proj(seg.x0, seg.y0);
        const [x2, y2] = this._proj(
            seg.x0 + len * seg.dx,
            seg.y0 + len * seg.dy,
        );
        return { x1, y1, x2, y2 };
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
    //
    // Phase 3.C.2b — each entry also carries:
    //   - `lineRef`: the raw line object (so the template's shifter
    //     handler can read sb_width_mm + wall_id without a re-lookup).
    //   - `isDragging`: true when the user is mid-drag of THIS cabinet
    //     and has crossed the 5px threshold. The template branches on
    //     this to render two polygons (ghost at original + semi-opaque
    //     preview at dragState.currentMm).
    //   - `dragPoints`: the polygon points string at currentMm, only
    //     populated when isDragging is true.
    //   - `dragCx` / `dragCy`: centroid of the dragging polygon (so
    //     the label rides along with the cabinet during drag).
    get _cabinetPolys() {
        const out = [];
        const lbw = this._linesByWallId;
        const ds = this.dragState || {};
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

                // Phase 3.C.2b — drag preview overlay. Computed up-
                // front (cheap; the polygon math is the same) so the
                // template can stay declarative.
                const isDragging = (
                    ds.lineId === line.id && ds.moved === true
                );
                let dragPoints = "";
                let dragCx = cx;
                let dragCy = cy;
                if (isDragging) {
                    const dCorners = _cabinetCornersMm(
                        s,
                        ds.currentMm || 0,
                        width,
                        depth,
                    );
                    dragPoints = dCorners
                        .map(([x, y]) => {
                            const [px, py] = this._proj(x, y);
                            return px.toFixed(1) + "," + py.toFixed(1);
                        })
                        .join(" ");
                    let dcx = 0;
                    let dcy = 0;
                    for (const [x, y] of dCorners) {
                        const [px, py] = this._proj(x, y);
                        dcx += px;
                        dcy += py;
                    }
                    dragCx = dcx / 4;
                    dragCy = dcy / 4;
                }

                out.push({
                    key: "cab-" + line.id,
                    // Phase 3.C.2a — surface the line id explicitly so
                    // the template's t-on-click can call back into the
                    // parent without re-parsing the key string.
                    lineId: line.id,
                    // Phase 3.C.2b — the raw line ref so the shifter
                    // (± buttons) can read sb_width_mm + wall_id +
                    // position_from_left_mm without a re-lookup.
                    lineRef: line,
                    points: pts,
                    zoneClass: ZONE_CLASS(line.zone),
                    conflict: !!wall.has_conflicts,
                    label: this._shortLabel(line.name || ""),
                    cx,
                    cy,
                    showLabel: widthPx >= MIN_LABEL_VBOX_PX,
                    // Phase 3.C.2b — drag overlay.
                    isDragging,
                    dragPoints,
                    dragCx,
                    dragCy,
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
                    // Phase 4 — gap label honours the unit preference.
                    label: this._humanLen(gap) + " gap",
                    cx,
                    cy,
                    showLabel: widthPx >= 40,
                    // Phase 3.C.2a — surface the click target context so
                    // the gap-click handler can stash a placement intent
                    // before the catalog modal opens. position = gap-left
                    // edge in mm (where the cabinet will start). The
                    // parent's _onPlanGapClick adjusts as needed (e.g.
                    // centering inside the gap is a Phase-3.D nicety).
                    wallId: wallId,
                    gapMm: gap,
                    positionMm: lo,
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
// WallElevationSVG — Phase 3.C.2c.
//
// Pure render. Side-on cross-section of a SINGLE wall picked by the
// parent's selectedWallId. No interactivity — elevation is reference-
// only; placement edits stay on the floor plan.
//
// Coordinate system:
//   - X mm = position_from_left_mm along the wall (left → right as the
//     user faces the wall from inside the room).
//   - Y mm = height above floor (0 = floor, ceiling_height_mm = top).
//     SVG Y grows DOWNWARD, so _projY flips on the way out.
//
// Layers, painter's order (back → front):
//   1. Background rect (paper)
//   2. Floor / ceiling / worktop reference lines
//   3. Constraint cutouts (window/door rectangles, outlet/post icons)
//   4. Cabinet front-face rectangles (zone-coloured)
//   5. Cabinet labels + axis labels (floor / worktop / ceiling)
//
// Empty cases:
//   - props.wall null     → render "Pick a wall" placeholder.
//   - No cabinets on wall → render outline + constraints only (no skip).
// ----------------------------------------------------------------------

const ELEV_VIEW_W = 1024;
const ELEV_VIEW_H = 600;
const ELEV_PAD = 40;
const ELEV_INNER_W = ELEV_VIEW_W - 2 * ELEV_PAD;   // 944
const ELEV_INNER_H = ELEV_VIEW_H - 2 * ELEV_PAD;   // 520

class WallElevationSVG extends Component {
    static template = "southbrook_estimating_website.WallElevationSVG";
    static props = {
        room: Object,
        wall: { type: Object, optional: true },
        lines: Array,
        unitPreference: { type: String, optional: true },
    };

    // Phase 4 length formatter — honours props.unitPreference.
    _humanLen(mm) {
        return _humanLenWithPref(mm, this.props.unitPreference || "mm");
    }

    get _viewBox() {
        return "0 0 " + ELEV_VIEW_W + " " + ELEV_VIEW_H;
    }

    // Effective ceiling: max of the room's actual ceiling and 2100mm so
    // tall (floor-to-ceiling) cabinets always fit when the room is short.
    get _maxHeight() {
        const room = this.props.room || {};
        const ceil = Number(room.ceiling_height_mm) || 0;
        return Math.max(ceil, 2100);
    }

    // Fit (wall length × maxHeight) into the 944×520 inner area with a
    // single uniform scale. Offsets centre the bbox.
    get _transform() {
        const wall = this.props.wall;
        if (!wall) {
            return { scale: 1, offX: ELEV_PAD, offY: ELEV_PAD };
        }
        const wallLen = Math.max(1, Number(wall.length_mm) || 1);
        const maxH = this._maxHeight;
        const scale = Math.min(ELEV_INNER_W / wallLen, ELEV_INNER_H / maxH);
        const offX = ELEV_PAD + (ELEV_INNER_W - wallLen * scale) / 2;
        const offY = ELEV_PAD + (ELEV_INNER_H - maxH * scale) / 2;
        return { scale, offX, offY };
    }

    _projX(mm) {
        const t = this._transform;
        return t.offX + (Number(mm) || 0) * t.scale;
    }

    // SVG Y grows downward; mm above floor grows upward. Subtract from
    // maxHeight so floor (0 mm) lands at the BOTTOM of the inner area.
    _projY(mm) {
        const t = this._transform;
        return t.offY + (this._maxHeight - (Number(mm) || 0)) * t.scale;
    }

    get _floorY() {
        return this._projY(0);
    }

    get _ceilingY() {
        const room = this.props.room || {};
        return this._projY(Number(room.ceiling_height_mm) || 0);
    }

    get _worktopY() {
        return this._projY(900);
    }

    // Cabinets placed on the selected wall, sorted left → right.
    get _cabinetsForWall() {
        const wall = this.props.wall;
        if (!wall) return [];
        const lines = this.props.lines || [];
        return lines
            .filter((l) => l.wall_id === wall.id)
            .sort(
                (a, b) =>
                    (a.position_from_left_mm || 0)
                    - (b.position_from_left_mm || 0),
            );
    }

    // Cabinet rectangles for the template iteration.
    get _cabinetRects() {
        const wall = this.props.wall;
        if (!wall) return [];
        const out = [];
        for (const line of this._cabinetsForWall) {
            const [y0mm, y1mm] = _elevationRangeFor(line);
            const pos = line.position_from_left_mm || 0;
            const widthMm = line.sb_width_mm || 600;
            const x = this._projX(pos);
            const w = Math.max(1, widthMm * this._transform.scale);
            // y is the TOP of the rect in SVG space (y1mm in physical mm).
            const y = this._projY(y1mm);
            const h = Math.max(1, (y1mm - y0mm) * this._transform.scale);
            out.push({
                key: "elev-cab-" + line.id,
                x,
                y,
                w,
                h,
                cx: x + w / 2,
                cy: y + h / 2,
                label: this._shortLabel(line.name || ""),
                zone: line.zone || "other",
                zoneClass: ZONE_CLASS(line.zone),
                isConflict: !!wall.has_conflicts,
                showLabel: w >= MIN_LABEL_VBOX_PX,
            });
        }
        return out;
    }

    // Constraint rectangles + icon-only fallbacks. Power outlets and
    // structural posts have no height contribution in the source data —
    // render them as a small badge floating just above the floor line
    // rather than dropping them entirely.
    get _constraintRects() {
        const wall = this.props.wall;
        if (!wall) return [];
        const constraints = wall.constraints || [];
        const out = [];
        for (const c of constraints) {
            const type = c.constraint_type || "other";
            const posMm = c.distance_from_left_mm || 0;
            const widthMm = c.width_mm || 100;
            // Outlet / structural post — icon-only badge at sill height
            // (default 1100mm — eye-level for outlets, neutral for posts).
            if (type === "power_outlet" || type === "structural_post") {
                const yMm = c.height_from_floor_mm || 1100;
                const x = this._projX(posMm);
                const y = this._projY(yMm);
                out.push({
                    key: "elev-con-" + c.id,
                    type: type,
                    isIcon: true,
                    x,
                    y,
                    w: 14,
                    h: 14,
                    cx: x + 7,
                    cy: y + 7,
                    label: this._humanConstraint(type),
                    showLabel: false,
                });
                continue;
            }
            // Sized cutout (window / door / appliance). Fall back to
            // sensible default heights for entries that lack dimensions.
            let heightMm = Number(c.height_mm) || 0;
            let fromFloorMm = Number(c.height_from_floor_mm);
            if (!Number.isFinite(fromFloorMm)) fromFloorMm = 0;
            if (heightMm <= 0) {
                // Type-aware default heights — kept conservative; the
                // user can edit the constraint to set real dimensions.
                if (type === "door") {
                    heightMm = 2030;
                    fromFloorMm = 0;
                } else if (type === "window") {
                    heightMm = 1200;
                    if (!fromFloorMm) fromFloorMm = 900;
                } else {
                    heightMm = 600;
                }
            }
            const y1mm = fromFloorMm + heightMm;
            const x = this._projX(posMm);
            const w = Math.max(1, widthMm * this._transform.scale);
            const y = this._projY(y1mm);
            const h = Math.max(1, heightMm * this._transform.scale);
            out.push({
                key: "elev-con-" + c.id,
                type: type,
                isIcon: false,
                x,
                y,
                w,
                h,
                cx: x + w / 2,
                cy: y + h / 2,
                label: this._humanConstraint(type),
                showLabel: w >= MIN_LABEL_VBOX_PX,
            });
        }
        return out;
    }

    // Y-axis tick labels — floor (0), worktop (900), ceiling.
    get _axisLabels() {
        const room = this.props.room || {};
        const ceil = Number(room.ceiling_height_mm) || 0;
        const t = this._transform;
        const x = t.offX - 6;
        const out = [
            {
                key: "ax-floor",
                x: x,
                y: this._floorY,
                text: this._humanLen(0) + " · floor",
            },
            {
                key: "ax-worktop",
                x: x,
                y: this._worktopY,
                text: this._humanLen(900) + " · worktop",
            },
        ];
        if (ceil > 0) {
            out.push({
                key: "ax-ceil",
                x: x,
                y: this._ceilingY,
                text: this._humanLen(ceil) + " · ceiling",
            });
        }
        return out;
    }

    // Right-edge of the wall vertical guide — mm at left=0 + mm at
    // right=wall_length so the user can read the wall span visually.
    get _wallEnds() {
        const wall = this.props.wall;
        if (!wall) return null;
        const len = Number(wall.length_mm) || 0;
        return {
            leftX: this._projX(0),
            rightX: this._projX(len),
            topY: this._ceilingY,
            bottomY: this._floorY,
            label: this._humanLen(len),
        };
    }

    // Mirror FloorPlanSVG._humanConstraint — kept inline so this
    // component stays a pure leaf (avoid cross-class import).
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

    _shortLabel(name) {
        if (!name) return "";
        const trimmed = name.trim();
        if (trimmed.length <= 10) return trimmed;
        return trimmed.slice(0, 10);
    }
}

// ----------------------------------------------------------------------
// RoomLayoutTab — parent. Hosts the SVG + sidebar + per-wall metrics.
// Owns the empty-state messaging.
// ----------------------------------------------------------------------

export class RoomLayoutTab extends Component {
    static template = "southbrook_estimating_website.RoomLayoutTab";
    static components = { FloorPlanSVG, WallElevationSVG };
    static props = {
        room: { type: [Object, { value: null }], optional: true },
        lines: { type: Array, optional: true },
        // Phase 3.C.2a — tap interactivity callbacks. All optional so
        // the tab stays read-only when wired without these. The parent
        // OrderBuilder threads three handlers through:
        //   onCabinetClick(lineId)              — clicked a placed cabinet
        //   onGapClick(wallId, gapMm, posMm)    — clicked an empty gap
        //   onAssignFromSidebar(lineId)         — clicked sidebar "Assign..."
        onCabinetClick: { type: Function, optional: true },
        onGapClick: { type: Function, optional: true },
        onAssignFromSidebar: { type: Function, optional: true },
        // Phase 3.C.2b — drag-along-wall + touch ± shifter handler.
        // Threaded straight through to FloorPlanSVG; the parent
        // OrderBuilder owns the /place-on-wall RPC.
        onCabinetDragEnd: { type: Function, optional: true },
        // Phase 3.C.2d — wall-resize drag end (SVG handle in single-
        // wall shapes) + ± 100mm sidebar buttons (multi-wall shapes).
        // The parent OrderBuilder owns the /room/<rid>/update RPC.
        onWallResizeEnd: { type: Function, optional: true },
        // Phase 4 — unit preference (mm | imperial) for every length
        // label rendered by this tab. Flipped from the Room Setup tab's
        // segmented toggle; FloorPlanSVG receives it via passthrough.
        unitPreference: { type: String, optional: true },
    };

    // Phase 3.C.2c — view-mode + selected-wall state. Floor is the
    // default; elevation auto-picks the first wall on first switch so
    // the toggle "just works" without an extra click.
    setup() {
        this.state = useState({
            viewMode: "floor",
            selectedWallId: null,
        });
    }

    _setViewMode(mode) {
        this.state.viewMode = mode;
        if (mode === "elevation" && !this.state.selectedWallId) {
            const walls = (this.props.room && this.props.room.walls) || [];
            if (walls.length > 0) {
                this.state.selectedWallId = walls[0].id;
            }
        }
    }

    _setSelectedWall(wallId) {
        this.state.selectedWallId = wallId;
    }

    // The wall record the elevation view is currently rendering. Falls
    // back to the first wall when the stored selectedWallId is null or
    // doesn't match any wall on the current room (e.g. wall deleted).
    get _selectedWall() {
        const walls = (this.props.room && this.props.room.walls) || [];
        if (walls.length === 0) return null;
        const match = walls.find((w) => w.id === this.state.selectedWallId);
        return match || walls[0];
    }

    // Phase 3.C.2a — sidebar Assign... button handler. No-op when the
    // parent didn't wire a callback (defensive — every production
    // mount wires this).
    _onAssignClick(lineId) {
        if (this.props.onAssignFromSidebar) {
            this.props.onAssignFromSidebar(lineId);
        }
    }

    // Phase 4 — template-facing length formatter. Honours the
    // unit-preference passed in from the parent OrderBuilder.
    _humanLen(mm) {
        return _humanLenWithPref(mm, this.props.unitPreference || "mm");
    }

    // Phase 3.C.2d — sidebar ± 100mm wall-length shifter. Clamps to
    // min 200mm (same floor as the SVG drag). Fires the same RPC
    // handler the SVG handle uses so the parent has one code path
    // to maintain.
    _onWallShift = (wallId, currentMm, deltaMm) => {
        if (!this.props.onWallResizeEnd) return;
        const next = Math.max(200, (Number(currentMm) || 0) + deltaMm);
        this.props.onWallResizeEnd(wallId, next);
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

// ----------------------------------------------------------------------
// AssignToWallModal — Phase 3.C.2a.
//
// Fullscreen overlay launched from the Room Layout sidebar's
// "Assign..." button on each unplaced cabinet. Wall dropdown + position
// input; on Assign click the parent OrderBuilder owns the RPC via the
// onAssign(wallId, positionMm) callback.
//
// Position seeded from the picked wall's used_mm (i.e. the cabinet
// starts where the last placed cabinet ends — sensible default). The
// user can override before submitting.
//
// Visual chrome mirrors the RoomSetupWizard backdrop so the two
// overlays read as the same UI vocabulary. Sub-prefix `sb-room-plan-
// modal-*` keeps the new selectors isolated from the wizard's.
// ----------------------------------------------------------------------

export class AssignToWallModal extends Component {
    static template = "southbrook_estimating_website.AssignToWallModal";
    static props = {
        line: Object,
        room: Object,
        onAssign: Function,
        onCancel: Function,
        // Phase 4 — unit preference. The position input stays in raw
        // mm always (numeric input — mm is simpler than parsing
        // `3' 6"` strings), but the dropdown options + cabinet width
        // summary flip to ft/in when the room is on imperial.
        unitPreference: { type: String, optional: true },
    };

    setup() {
        const walls = (this.props.room && this.props.room.walls) || [];
        const firstWall = walls[0] || null;
        this.state = useState({
            // Stored as strings so the <select> + <input> bind cleanly;
            // coerced to int on submit.
            wallId: firstWall ? String(firstWall.id) : "",
            // Seed position to the wall's used_mm so the cabinet appends
            // to the end of the existing run. Falls back to 0 when the
            // wall is empty.
            positionMm: firstWall ? String(firstWall.used_mm || 0) : "0",
            submitting: false,
            error: null,
        });
    }

    // Sorted-by-name wall list so the dropdown stays predictable.
    get _wallOptions() {
        const walls = (this.props.room && this.props.room.walls) || [];
        return walls.map((w) => ({
            id: w.id,
            name: w.name || "Wall",
            length_mm: w.length_mm || 0,
            remaining_mm: typeof w.remaining_mm === "number" ? w.remaining_mm : 0,
            used_mm: w.used_mm || 0,
        }));
    }

    // Re-seed position when the user switches walls — start at the
    // newly-picked wall's used_mm (append-to-end default).
    _onWallChange = (ev) => {
        const newId = ev.target.value;
        this.state.wallId = newId;
        const w = this._wallOptions.find((o) => String(o.id) === String(newId));
        if (w) {
            this.state.positionMm = String(w.used_mm || 0);
        }
    };

    _onPositionInput = (ev) => {
        this.state.positionMm = ev.target.value;
    };

    _onCancelClick = () => {
        if (this.state.submitting) return;
        this.props.onCancel();
    };

    _onAssignClick = async () => {
        if (this.state.submitting) return;
        const wallIdNum = parseInt(this.state.wallId, 10);
        const posNum = parseFloat(this.state.positionMm);
        if (!Number.isFinite(wallIdNum) || wallIdNum <= 0) {
            this.state.error = "Pick a wall.";
            return;
        }
        if (!Number.isFinite(posNum) || posNum < 0) {
            this.state.error = "Position must be 0 or greater.";
            return;
        }
        this.state.submitting = true;
        this.state.error = null;
        try {
            await this.props.onAssign(wallIdNum, posNum);
        } catch (e) {
            this.state.error = e && e.message ? e.message : String(e);
        } finally {
            this.state.submitting = false;
        }
    };

    // Cabinet width used in the body summary so the user can sanity-
    // check the placement (e.g. "600mm cabinet → wall has 1200mm left").
    get _cabinetWidthMm() {
        return (this.props.line && this.props.line.sb_width_mm) || 0;
    }

    // Phase 4 — template-facing length formatter. Honours the
    // unit-preference passed in from the parent OrderBuilder.
    _humanLen(mm) {
        return _humanLenWithPref(mm, this.props.unitPreference || "mm");
    }
}

// ----------------------------------------------------------------------
// GapRecommendModal — Phase 6.1.
//
// Fullscreen overlay launched from a Room Layout gap-click (replacing
// the 3.C.2a direct-to-catalog flow). Renders the top-3 recommended
// cabinet templates returned by the recommend endpoint as a stacked
// list of cards, plus a "Browse all cabinets…" fallback that escapes
// to the full catalog modal.
//
// Pure presentation — the parent OrderBuilder owns the RPCs (template
// pick → /add-line + /place-on-wall via the existing pendingGapPlacement
// stash; Browse all → _openCatalog). The empty-state branch (no
// recommendations + note=gap_too_small) collapses the card list and
// shows a friendly note above the Browse all button.
//
// Visual chrome mirrors AssignToWallModal (sb-room-plan-modal-* base
// classes) so the two overlays read as the same UI vocabulary; the
// recommendation-specific styles live under sb-room-plan-recommend-*.
// Backdrop click / ESC don't close — consistent with AssignToWallModal
// (the SHOULD-FIX is parked for both).
// ----------------------------------------------------------------------

export class GapRecommendModal extends Component {
    static template = "southbrook_estimating_website.GapRecommendModal";
    static props = {
        gapInfo: Object,
        recommendations: Array,
        onPick: Function,
        onBrowseAll: Function,
        onCancel: Function,
    };

    setup() {
        this.state = useState({
            // Per-card busy flag so the user gets a "Adding…" state on
            // the clicked card while the parent's _onPickCabinet
            // pipeline is in-flight (add-line + place-on-wall). The
            // other cards stay enabled so a slow network doesn't lock
            // them out of trying a different pick.
            pickingTemplateId: null,
        });
    }

    _onPickClick = async (templateId) => {
        if (this.state.pickingTemplateId !== null) return;
        this.state.pickingTemplateId = templateId;
        try {
            // Parent closes this modal on success (clears
            // state.ui.gapRecommend); the try/finally just unblocks
            // the per-card spinner if the await rejects.
            await this.props.onPick(templateId);
        } finally {
            this.state.pickingTemplateId = null;
        }
    };

    _onBrowseAllClick = () => {
        if (this.state.pickingTemplateId !== null) return;
        this.props.onBrowseAll();
    };

    _onCancelClick = () => {
        if (this.state.pickingTemplateId !== null) return;
        this.props.onCancel();
    };

    // Template helpers — declared on the instance so OWL can call them
    // without a binding shim. `gapInfo.gapMm` is the source of truth
    // for the gap label.
    get _gapMm() {
        return (this.props.gapInfo && this.props.gapInfo.gapMm) || 0;
    }

    _formatMm(mm) {
        return `${Math.round(Number(mm) || 0)} mm`;
    }

    // Best fit as a fraction (rounded down) of the gap — used as a
    // chip badge on each card to make the score legible. "85% of gap"
    // is more useful than "score 0.85" for the trade audience.
    _pctOfGap(bestMm) {
        const g = this._gapMm;
        if (!g) return "—";
        return `${Math.floor(((Number(bestMm) || 0) / g) * 100)}%`;
    }
}
