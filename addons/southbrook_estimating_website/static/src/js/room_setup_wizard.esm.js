/** @odoo-module **/
/*
 * SPDX-License-Identifier: LGPL-3.0-only
 *
 * Phase 2.C — Room Setup wizard (2026-06-27).
 *
 * Fullscreen OWL overlay launched from the Order Builder's Room Setup
 * tab ("Set Up Room" CTA). 3 steps + a live SVG floor-plan preview:
 *
 *   1. Room type (7 tiles) + layout shape (8 tiles).
 *   2. Wall dimensions — wall count auto-derived from the chosen
 *      shape; length input per wall + unit toggle (mm/imperial) +
 *      shared ceiling height.
 *   3. Fixed constraints — type chips + per-constraint inline form.
 *      Step is skippable.
 *
 * Submit POSTs to /southbrook/api/order/<id>/room/create (Phase 2.A
 * controller). On success the wizard hands the returned room dict
 * back to the OrderBuilder via onSubmitted(room); the OrderBuilder
 * caches it on state.room and switches the active tab to room_setup
 * so the user immediately sees the rendered summary from Phase 2.B.
 *
 * Five components in this file:
 *   - RoomSetupWizard       (parent — state machine + submit + close)
 *   - RoomTypeShapeStep     (Step 1 tiles)
 *   - WallDimensionsStep    (Step 2 wall length inputs)
 *   - ConstraintsStep       (Step 3 constraint chips + form)
 *   - RoomOutlinePreview    (sibling SVG, pure-render)
 *
 * v19 / OWL tokenizer gotchas honoured:
 *   - All `t-att-*` / `t-if` expressions use `||`, `&&`, `!` (never
 *     Python `or` / `and` / `not`).
 *   - `<` encoded as `&lt;` inside attribute expressions.
 *   - SVG sub-trees are plain XML — OWL handles the namespace.
 */
import {
    Component,
    useState,
    xml,
} from "@odoo/owl";
import { rpcJsonCall } from "@southbrook_estimating_website/js/portal_boot.esm";
import {
    wallSegmentsForShape,
    polylinePointsFromSegments,
} from "@southbrook_estimating_website/js/room_geometry.esm";

// ----------------------------------------------------------------------
// Static catalogues — the tiles + chip lists. Plain JS objects so the
// templates can iterate them via t-foreach without registering anything
// extra. Labels are user-facing; codes match the Phase 1 selection
// fields on southbrook.room / .room.wall / .room.constraint.
// ----------------------------------------------------------------------

const ROOM_TYPES = [
    { code: "kitchen",   label: "Kitchen",   blurb: "Cabinets, counters, appliances." },
    { code: "bath",      label: "Bath",      blurb: "Vanity, linen, medicine cabinet." },
    { code: "laundry",   label: "Laundry",   blurb: "Washer/dryer, utility sink." },
    { code: "office",    label: "Office",    blurb: "Built-in desk + shelving." },
    { code: "mudroom",   label: "Mudroom",   blurb: "Cubbies, hooks, bench." },
    { code: "closet",    label: "Closet",    blurb: "Reach-in or walk-in." },
    { code: "other",     label: "Other",     blurb: "General storage room." },
];

const LAYOUT_SHAPES = [
    { code: "straight",  label: "Straight",  walls: 1, sketch: "▭" },
    { code: "l_shape",   label: "L-Shape",   walls: 2, sketch: "L" },
    { code: "u_shape",   label: "U-Shape",   walls: 3, sketch: "U" },
    { code: "galley",    label: "Galley",    walls: 2, sketch: "‖" },
    { code: "g_shape",   label: "G-Shape",   walls: 4, sketch: "G" },
    { code: "island",    label: "Island",    walls: 1, sketch: "◇" },
    { code: "peninsula", label: "Peninsula", walls: 2, sketch: "T" },
    { code: "custom",    label: "Custom",    walls: 4, sketch: "✱" },
];

const CONSTRAINT_TYPES = [
    { code: "window",          label: "Window" },
    { code: "door",            label: "Door" },
    { code: "sink",            label: "Sink" },
    { code: "cooktop",         label: "Cooktop" },
    { code: "oven",            label: "Oven" },
    { code: "dishwasher",      label: "Dishwasher" },
    { code: "rangehood",       label: "Rangehood" },
    { code: "fridge_space",    label: "Fridge Space" },
    { code: "power_outlet",    label: "Power Outlet" },
    { code: "structural_post", label: "Structural Post" },
    { code: "other",           label: "Other" },
];

// Wall count per shape — pre-populates state.walls when the user picks
// a shape in Step 1. Island carries 1 placeholder wall; custom seeds 4
// so the user has scaffolding to edit.
function wallsForShape(shape) {
    return {
        straight:  1,
        l_shape:   2,
        u_shape:   3,
        galley:    2,
        g_shape:   4,
        island:    1,
        peninsula: 2,
        custom:    4,
    }[shape] || 2;
}

function defaultWalls(n) {
    const out = [];
    for (let i = 0; i < n; i += 1) {
        out.push({
            name: "Wall " + String.fromCharCode(65 + i),  // Wall A, B, C…
            length_mm: 0,
            wall_order: i,
        });
    }
    return out;
}

// ----------------------------------------------------------------------
// RoomOutlinePreview — pure-render SVG. Re-renders on every parent
// state change via OWL reactivity (no internal state, no debounce).
//
// Supported shapes get a real outline (straight, l_shape, u_shape,
// galley). Other shapes fall back to a labelled rectangle + a
// "preview not yet rendered for this shape" note inside the SVG.
// ----------------------------------------------------------------------

class RoomOutlinePreview extends Component {
    static template = "southbrook_estimating_website.RoomOutlinePreview";
    static props = {
        shape: { type: [String, { value: null }], optional: true },
        walls: { type: Array, optional: true },
    };

    // Bounding-box fitting: compute path points in raw mm, then scale
    // into the 720x540 viewBox with 40px padding. Padding doubles as
    // the gutter the SVG label text needs.
    get _viewBox() {
        return "0 0 720 540";
    }

    get _polylinePoints() {
        const shape = this.props.shape;
        const walls = (this.props.walls || []).map(
            (w) => Math.max(0, Number(w.length_mm) || 0),
        );
        const pts = this._rawPoints(shape, walls);
        if (!pts || pts.length === 0) return "";
        // Fit bounding box into 640x460 (= 720x540 minus 40px padding
        // each side). Maintain aspect ratio — pick the smaller of the
        // x/y scales so the whole outline fits.
        let minX = Infinity;
        let minY = Infinity;
        let maxX = -Infinity;
        let maxY = -Infinity;
        for (const [x, y] of pts) {
            if (x < minX) minX = x;
            if (y < minY) minY = y;
            if (x > maxX) maxX = x;
            if (y > maxY) maxY = y;
        }
        const bw = Math.max(1, maxX - minX);
        const bh = Math.max(1, maxY - minY);
        const scale = Math.min(640 / bw, 460 / bh);
        const offX = 40 + (640 - bw * scale) / 2;
        const offY = 40 + (460 - bh * scale) / 2;
        return pts
            .map(([x, y]) => {
                const px = offX + (x - minX) * scale;
                const py = offY + (y - minY) * scale;
                return px.toFixed(1) + "," + py.toFixed(1);
            })
            .join(" ");
    }

    // Pure mm-space geometry per shape. Delegates to the shared
    // wallSegmentsForShape() helper (room_geometry.esm.js) which is
    // also consumed by Phase 3.B's FloorPlanSVG. Returns an array of
    // [x, y] points; unsupported shapes return null → fallback
    // rectangle path.
    //
    // Galley gap is computed from the wall lengths (not a fixed mm)
    // to keep the live preview visually balanced as the user types —
    // a 6m galley needs a wider rendered aisle than a 2m one to read
    // correctly inside the 720x540 viewBox. The Phase 3.B Room Layout
    // tab uses a fixed 1200 mm aisle (real-world typical) instead.
    _rawPoints(shape, walls) {
        const safeWalls = (walls || []).map((mm, i) => ({
            name: "Wall " + String.fromCharCode(65 + i),
            length_mm: mm,
        }));
        // Match the previous wizard galley behaviour: gap scales with
        // wall length so the preview stays balanced for both small +
        // large kitchens.
        const wA = walls[0] || 1000;
        const wB = walls[1] || 1000;
        const galleyGap = shape === "galley"
            ? Math.max(wA, wB) * 0.6
            : undefined;
        const segs = wallSegmentsForShape(shape, safeWalls, {
            galleyGapMm: galleyGap,
        });
        if (!segs) return null;
        return polylinePointsFromSegments(segs);
    }

    // Fallback-rectangle path used for shapes we don't render properly.
    get _fallbackBox() {
        // 640x340 rectangle inside the 40px padding band, leaving room
        // for a label below.
        return { x: 40, y: 40, w: 640, h: 340 };
    }

    get _supportsShape() {
        return ["straight", "l_shape", "u_shape", "galley"].includes(
            this.props.shape,
        );
    }

    get _shapeLabel() {
        const found = LAYOUT_SHAPES.find((s) => s.code === this.props.shape);
        return found ? found.label : (this.props.shape || "(no shape picked)");
    }

    get _totalLinear() {
        return (this.props.walls || []).reduce(
            (sum, w) => sum + (Number(w.length_mm) || 0),
            0,
        );
    }
}

// ----------------------------------------------------------------------
// RoomTypeShapeStep — Step 1.
//
// Two grids: 7 room-type tiles + 8 layout-shape tiles. Selecting a
// shape calls onShapePicked so the parent can pre-populate the walls
// array for Step 2.
// ----------------------------------------------------------------------

class RoomTypeShapeStep extends Component {
    static template = "southbrook_estimating_website.RoomTypeShapeStep";
    static props = {
        room: Object,
        onRoomTypePicked: Function,
        onShapePicked: Function,
        onNameChanged: Function,
    };

    get _roomTypes() { return ROOM_TYPES; }
    get _layoutShapes() { return LAYOUT_SHAPES; }
}

// ----------------------------------------------------------------------
// WallDimensionsStep — Step 2.
//
// Renders one numeric input per wall (length in the current unit) plus
// the shared ceiling-height field and the unit toggle. Edits flow back
// through the parent's onWallChanged / onCeilingChanged / onUnitChanged
// callbacks so the parent owns the canonical state (single source of
// truth for the preview).
//
// Display unit is decoupled from storage: state.walls store mm always;
// the input shows the unit-converted value when imperial is selected.
// ----------------------------------------------------------------------

class WallDimensionsStep extends Component {
    static template = "southbrook_estimating_website.WallDimensionsStep";
    static props = {
        room: Object,
        walls: Array,
        onWallLengthChanged: Function,
        onWallNameChanged: Function,
        onCeilingChanged: Function,
        onUnitChanged: Function,
    };

    // Conversion helpers. Imperial unit shows inches (decimal) for v1;
    // Phase 3 polish can layer feet+inches parsing on top.
    _toDisplay(mm) {
        if (this.props.room.unit_preference === "imperial") {
            return (mm / 25.4).toFixed(1);
        }
        return String(Math.round(mm));
    }

    _fromDisplay(raw) {
        const n = parseFloat(raw);
        if (!Number.isFinite(n)) return 0;
        if (this.props.room.unit_preference === "imperial") {
            return Math.round(n * 25.4);
        }
        return Math.round(n);
    }

    _onLenInput(idx, ev) {
        const mm = this._fromDisplay(ev.target.value);
        this.props.onWallLengthChanged(idx, mm);
    }

    _onNameInput(idx, ev) {
        this.props.onWallNameChanged(idx, ev.target.value);
    }

    _onCeilingInput(ev) {
        const mm = this._fromDisplay(ev.target.value);
        this.props.onCeilingChanged(mm);
    }

    _unitLabel() {
        return this.props.room.unit_preference === "imperial" ? "in" : "mm";
    }
}

// ----------------------------------------------------------------------
// ConstraintsStep — Step 3.
//
// User picks a wall + constraint type, fills the inline form, clicks
// "Add". Constraints accumulate in a list above the form; each row
// has a remove button. Skippable — the wizard's Submit button is the
// path forward whether or not any constraints are entered.
// ----------------------------------------------------------------------

class ConstraintsStep extends Component {
    static template = "southbrook_estimating_website.ConstraintsStep";
    static props = {
        walls: Array,
        constraints: Array,
        onAddConstraint: Function,
        onRemoveConstraint: Function,
    };

    setup() {
        this.draft = useState({
            wall_index: 0,
            constraint_type: "window",
            distance_from_left_mm: 0,
            width_mm: 600,
        });
    }

    get _constraintTypes() { return CONSTRAINT_TYPES; }

    _wallLabel(idx) {
        const w = this.props.walls[idx];
        return w ? w.name : "Wall " + (idx + 1);
    }

    _humanType(code) {
        const found = CONSTRAINT_TYPES.find((c) => c.code === code);
        return found ? found.label : code;
    }

    _onPickType(code) {
        this.draft.constraint_type = code;
    }

    _onWallSelect(ev) {
        this.draft.wall_index = parseInt(ev.target.value, 10) || 0;
    }

    _onDistanceInput(ev) {
        const n = parseInt(ev.target.value, 10);
        this.draft.distance_from_left_mm = Number.isFinite(n) ? n : 0;
    }

    _onWidthInput(ev) {
        const n = parseInt(ev.target.value, 10);
        this.draft.width_mm = Number.isFinite(n) ? n : 0;
    }

    _add() {
        this.props.onAddConstraint({
            wall_index: this.draft.wall_index,
            constraint_type: this.draft.constraint_type,
            distance_from_left_mm: this.draft.distance_from_left_mm,
            width_mm: this.draft.width_mm,
        });
        // Reset distance + width for the next entry; keep the picked
        // type + wall so a sequence of windows on the same wall is fast.
        this.draft.distance_from_left_mm = 0;
        this.draft.width_mm = 600;
    }
}

// ----------------------------------------------------------------------
// RoomSetupWizard — parent. State machine: 1 → 2 → 3 → submitting →
// done | error. Close on backdrop click / × button. Submit handler
// hits the Phase 2.A controller and forwards the returned room to the
// OrderBuilder via onSubmitted.
// ----------------------------------------------------------------------

export class RoomSetupWizard extends Component {
    static template = "southbrook_estimating_website.RoomSetupWizard";
    static components = {
        RoomTypeShapeStep,
        WallDimensionsStep,
        ConstraintsStep,
        RoomOutlinePreview,
    };
    static props = {
        orderId: { type: [String, Number] },
        onClose: Function,
        onSubmitted: Function,
    };

    setup() {
        this.state = useState({
            step: 1,
            room: {
                name: "Main Kitchen",
                room_type: "kitchen",
                layout_shape: null,
                ceiling_height_mm: 2400,
                unit_preference: "mm",
            },
            walls: [],
            constraints: [],
            errorMessage: null,
        });
    }

    // ------------------------------------------------------------------
    // Step 1 callbacks
    // ------------------------------------------------------------------

    _onRoomTypePicked = (code) => {
        this.state.room.room_type = code;
    };

    _onShapePicked = (code) => {
        this.state.room.layout_shape = code;
        // Pre-populate walls with the default count for this shape so
        // Step 2 has scaffolding to edit. Don't clobber existing walls
        // if the user is re-picking the same shape. When the count
        // changes, preserve overlap — keep already-entered length_mm
        // and name for the first min(old, want) walls (review #7).
        const want = wallsForShape(code);
        if (this.state.walls.length !== want) {
            const fresh = defaultWalls(want);
            const keep = Math.min(this.state.walls.length, want);
            for (let i = 0; i < keep; i++) {
                if (this.state.walls[i].length_mm) {
                    fresh[i].length_mm = this.state.walls[i].length_mm;
                }
                if (this.state.walls[i].name) {
                    fresh[i].name = this.state.walls[i].name;
                }
            }
            this.state.walls = fresh;
            // Drop constraints that pointed at walls that no longer exist.
            this.state.constraints = this.state.constraints.filter(
                (c) => c.wall_index < want,
            );
        }
    };

    _onNameChanged = (ev) => {
        this.state.room.name = ev.target.value;
    };

    // ------------------------------------------------------------------
    // Step 2 callbacks
    // ------------------------------------------------------------------

    _onWallLengthChanged = (idx, mm) => {
        if (this.state.walls[idx]) {
            this.state.walls[idx].length_mm = mm;
        }
    };

    _onWallNameChanged = (idx, name) => {
        if (this.state.walls[idx]) {
            this.state.walls[idx].name = name;
        }
    };

    _onCeilingChanged = (mm) => {
        this.state.room.ceiling_height_mm = mm;
    };

    _onUnitChanged = (unit) => {
        this.state.room.unit_preference = unit;
    };

    // ------------------------------------------------------------------
    // Step 3 callbacks
    // ------------------------------------------------------------------

    _onAddConstraint = (c) => {
        this.state.constraints.push({ ...c });
    };

    _onRemoveConstraint = (idx) => {
        this.state.constraints.splice(idx, 1);
    };

    // ------------------------------------------------------------------
    // Step navigation
    // ------------------------------------------------------------------

    _canAdvance() {
        if (this.state.step === 1) {
            return !!this.state.room.room_type && !!this.state.room.layout_shape;
        }
        if (this.state.step === 2) {
            // All walls must have a positive length.
            return this.state.walls.length > 0
                && this.state.walls.every((w) => (w.length_mm || 0) > 0);
        }
        return true;
    }

    _next = () => {
        // In-flight guard — prevents double-click double-submit (review #1).
        if (this.state.step === "submitting") return;
        if (!this._canAdvance()) return;
        if (this.state.step === 3) {
            this._submit();
            return;
        }
        if (typeof this.state.step === "number") {
            this.state.step += 1;
        }
    };

    _back = () => {
        if (typeof this.state.step === "number" && this.state.step > 1) {
            this.state.step -= 1;
        } else if (this.state.step === "error") {
            // From the error screen, send the user back to step 3 so
            // they can adjust and retry.
            this.state.step = 3;
            this.state.errorMessage = null;
        }
    };

    _close = () => {
        this.props.onClose();
    };

    // ------------------------------------------------------------------
    // Submit
    // ------------------------------------------------------------------

    async _submit() {
        // In-flight guard — _next() also gates but a direct caller path
        // (e.g. the error-screen "Retry" button) needs its own guard (review #1).
        if (this.state.step === "submitting") return;
        this.state.step = "submitting";
        this.state.errorMessage = null;
        try {
            const body = {
                name: this.state.room.name,
                room_type: this.state.room.room_type,
                layout_shape: this.state.room.layout_shape,
                ceiling_height_mm: this.state.room.ceiling_height_mm,
                unit_preference: this.state.room.unit_preference,
                walls: this.state.walls,
                constraints: this.state.constraints,
            };
            const r = await rpcJsonCall(
                "/southbrook/api/order/"
                + encodeURIComponent(this.props.orderId)
                + "/room/create",
                body,
            );
            // Idempotency: server returns room_already_exists when the
            // order has a prior room — treat as success and hand the
            // existing room back, not as failure (review #2).
            if (r && r.error === "room_already_exists" && r.room) {
                this.state.step = "done";
                this.props.onSubmitted(r.room);
                return;
            }
            if (!r || r.error) {
                this.state.errorMessage = (r && (r.detail || r.error))
                    || "The room could not be saved.";
                this.state.step = "error";
                return;
            }
            this.state.step = "done";
            // Hand the returned room back to the OrderBuilder; it will
            // cache it on state.room and close the wizard.
            this.props.onSubmitted(r.room || r);
        } catch (e) {
            this.state.errorMessage = (e && e.message) || String(e);
            this.state.step = "error";
        }
    }

    // ------------------------------------------------------------------
    // Template helpers
    // ------------------------------------------------------------------

    _stepLabel(n) {
        return {
            1: "Room & Shape",
            2: "Wall Dimensions",
            3: "Fixed Constraints",
        }[n] || "";
    }

    _isStep(n) {
        return this.state.step === n;
    }

    _isNumberStep() {
        return typeof this.state.step === "number";
    }

    _nextLabel() {
        if (this.state.step === 3) return "Save Room";
        return "Next";
    }
}
