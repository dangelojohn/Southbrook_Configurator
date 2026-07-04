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
    onMounted,
    useState,
    xml,
} from "@odoo/owl";
// rpcJsonCall is defined locally to avoid a circular dependency with
// portal_boot.esm (which imports RoomSetupWizard from this module).
async function rpcJsonCall(url, params = {}) {
    const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", method: "call", params, id: Math.floor(Math.random() * 1e9) }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`);
    const json = await res.json();
    if (json.error) {
        const msg = json.error.data?.message || json.error.message || "RPC error";
        throw new Error(msg);
    }
    return json.result;
}
import {
    wallSegmentsForShape,
} from "@southbrook_estimating_website/js/room_geometry.esm";

// ----------------------------------------------------------------------
// Unit helpers (2026-07-03 QA fix — one display format everywhere).
//
// Canonical imperial display is feet-inches ("9' 10\"" / "10\"") to match
// the Room Setup summary, the Room Layout tab, and the Customer Spec Sheet
// PDF. The wizard's editable inputs are therefore `type="text"` (a number
// input can't hold `'` / `"`); parseImperialToMm() is deliberately
// tolerant so a contractor can type `9' 10"`, `9'10`, `9 ft 10 in`, `118`,
// or `118"` and get the same result. Storage is always mm.
//
// Negatives clamp to 0 (never enter a total); the server re-validates.
// ----------------------------------------------------------------------
function mmToImperial(mm) {
    const inches = Math.round((Number(mm) || 0) / 25.4);
    const feet = Math.floor(inches / 12);
    const rem = inches - feet * 12;
    if (feet === 0) return `${rem}"`;
    if (rem === 0) return `${feet}'`;
    return `${feet}' ${rem}"`;
}

function parseImperialToMm(raw) {
    if (raw === null || raw === undefined) return 0;
    const s = String(raw).trim();
    if (!s) return 0;
    let inches = 0;
    let matched = false;
    const feetMatch = s.match(/(-?\d+(?:\.\d+)?)\s*(?:'|ft\b|feet\b)/i);
    if (feetMatch) {
        inches += parseFloat(feetMatch[1]) * 12;
        matched = true;
    }
    const inchMatch = s.match(/(-?\d+(?:\.\d+)?)\s*(?:"|″|in\b|inch|inches)/i);
    if (inchMatch) {
        inches += parseFloat(inchMatch[1]);
        matched = true;
    } else if (feetMatch) {
        // "9' 10" with no inch token — grab the trailing number after feet.
        const after = s.slice(s.indexOf(feetMatch[0]) + feetMatch[0].length);
        const trailing = after.match(/(-?\d+(?:\.\d+)?)/);
        if (trailing) inches += parseFloat(trailing[1]);
    }
    if (!matched) {
        const n = parseFloat(s);
        inches = Number.isFinite(n) ? n : 0;
    }
    const mm = Math.round(inches * 25.4);
    return mm < 0 ? 0 : mm;
}

// Display an mm value in the active unit. mm mode shows whole millimetres.
function mmDisplay(mm, unit) {
    if (unit === "imperial") return mmToImperial(mm);
    return String(Math.round(Number(mm) || 0));
}

// Parse a raw input string in the active unit → non-negative mm.
function parseDisplayToMm(raw, unit) {
    if (unit === "imperial") return parseImperialToMm(raw);
    const n = parseFloat(raw);
    if (!Number.isFinite(n)) return 0;
    return Math.max(0, Math.round(n));
}

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
        // 2026-07-03 QA fix — the preview now also renders constraint
        // markers + wall labels + dimension annotations, and honours the
        // unit toggle in its caption.
        constraints: { type: Array, optional: true },
        unitPreference: { type: String, optional: true },
    };

    NOMINAL_MM = 3000;      // placeholder wall length before dims exist
    CONSTRAINT_DEPTH_MM = 320;

    get _viewBox() {
        return "0 0 720 540";
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

    // Real (typed) wall lengths in mm, 0 where not yet entered.
    _rawLengths() {
        return (this.props.walls || []).map(
            (w) => Math.max(0, Number(w.length_mm) || 0),
        );
    }

    get _totalLinearLabel() {
        const total = this._rawLengths().reduce((a, b) => a + b, 0);
        return mmDisplay(total, this.props.unitPreference || "mm")
            + (this.props.unitPreference === "imperial" ? "" : " mm");
    }

    // ------------------------------------------------------------------
    // The whole projected drawing, computed once per render. `segments`
    // carry projected endpoints + a mid-point label (name + dimension);
    // `constraints` carry a projected quad + a label, flagged red when
    // out of bounds. When no dimensions exist yet (Step 1) we substitute
    // a nominal length per wall so the SHAPE still renders — the label
    // then reads "—" so we don't imply a real measurement.
    // ------------------------------------------------------------------
    get _layout() {
        const shape = this.props.shape;
        if (!this._supportsShape) return null;
        const raw = this._rawLengths();
        const geom = raw.map((mm) => (mm > 0 ? mm : this.NOMINAL_MM));
        const geomWalls = geom.map((mm, i) => ({
            name: "Wall " + String.fromCharCode(65 + i),
            length_mm: mm,
        }));
        const wA = geom[0] || this.NOMINAL_MM;
        const wB = geom[1] || this.NOMINAL_MM;
        const galleyGap = shape === "galley"
            ? Math.max(wA, wB) * 0.6
            : undefined;
        const segs = wallSegmentsForShape(shape, geomWalls, {
            galleyGapMm: galleyGap,
        });
        if (!segs) return null;

        const unit = this.props.unitPreference || "mm";
        const depth = this.CONSTRAINT_DEPTH_MM;

        // --- collect every mm-space point for the bbox fit ---
        const pts = [];
        for (const s of segs) {
            pts.push([s.x0, s.y0], [s.x1, s.y1]);
        }
        const cons = (this.props.constraints || []);
        for (const c of cons) {
            const s = segs[c.wall_index];
            if (!s) continue;
            const start = Math.max(0, Number(c.distance_from_left_mm) || 0);
            const width = Math.max(0, Number(c.width_mm) || 0);
            const p0x = s.x0 + s.dx * start;
            const p0y = s.y0 + s.dy * start;
            const p1x = s.x0 + s.dx * (start + width);
            const p1y = s.y0 + s.dy * (start + width);
            pts.push([p0x + s.normalX * depth, p0y + s.normalY * depth]);
            pts.push([p1x + s.normalX * depth, p1y + s.normalY * depth]);
        }

        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
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
        const proj = (x, y) => [
            offX + (x - minX) * scale,
            offY + (y - minY) * scale,
        ];

        // --- wall segments + labels ---
        const segments = segs.map((s, i) => {
            const [x0, y0] = proj(s.x0, s.y0);
            const [x1, y1] = proj(s.x1, s.y1);
            const lx = (x0 + x1) / 2 - s.normalX * 20;
            const ly = (y0 + y1) / 2 - s.normalY * 20;
            const dimLabel = raw[i] > 0 ? mmDisplay(raw[i], unit)
                + (unit === "imperial" ? "" : " mm") : "—";
            return {
                x0: x0.toFixed(1), y0: y0.toFixed(1),
                x1: x1.toFixed(1), y1: y1.toFixed(1),
                lx: lx.toFixed(1), ly: ly.toFixed(1),
                label: String.fromCharCode(65 + i) + "  " + dimLabel,
            };
        });

        // --- constraint markers ---
        const constraints = [];
        for (const c of cons) {
            const s = segs[c.wall_index];
            if (!s) continue;
            const start = Math.max(0, Number(c.distance_from_left_mm) || 0);
            const width = Math.max(0, Number(c.width_mm) || 0);
            if (width <= 0) continue;
            const a = proj(s.x0 + s.dx * start, s.y0 + s.dy * start);
            const b = proj(s.x0 + s.dx * (start + width),
                           s.y0 + s.dy * (start + width));
            const cc = proj(s.x0 + s.dx * (start + width) + s.normalX * depth,
                            s.y0 + s.dy * (start + width) + s.normalY * depth);
            const d = proj(s.x0 + s.dx * start + s.normalX * depth,
                           s.y0 + s.dy * start + s.normalY * depth);
            const realLen = raw[c.wall_index] || 0;
            const oob = realLen > 0 && (start + width) > realLen;
            constraints.push({
                points: `${a[0].toFixed(1)},${a[1].toFixed(1)} `
                    + `${b[0].toFixed(1)},${b[1].toFixed(1)} `
                    + `${cc[0].toFixed(1)},${cc[1].toFixed(1)} `
                    + `${d[0].toFixed(1)},${d[1].toFixed(1)}`,
                cx: ((a[0] + b[0]) / 2).toFixed(1),
                cy: ((a[1] + b[1]) / 2 - 6).toFixed(1),
                label: this._constraintLabel(c.constraint_type),
                oob,
            });
        }

        return { segments, constraints };
    }

    _constraintLabel(code) {
        const found = CONSTRAINT_TYPES.find((c) => c.code === code);
        return found ? found.label : (code || "");
    }

    get _fallbackBox() {
        return { x: 40, y: 40, w: 640, h: 340 };
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
        // Phase 6.2 — Room Templates library. Both optional so the step
        // still renders cleanly if the parent hasn't wired the templates
        // fetch (e.g. older tests that instantiate the step directly).
        templates: { type: Array, optional: true },
        onApplyTemplate: { type: Function, optional: true },
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
        // Phase 6.2 — when a Room Template seeded Step 2, surface a
        // gentle "Applied template: X — edit anything below" notice so
        // the user knows the form isn't blank by accident. Optional —
        // null when the user picked a custom shape on Step 1.
        appliedTemplateName: { type: [String, { value: null }], optional: true },
    };

    // Conversion helpers — feet-inches in imperial mode (canonical
    // display, matches the summary + PDF), whole mm otherwise. Inputs are
    // type="text" so the imperial `'`/`"` tokens are accepted.
    _toDisplay(mm) {
        return mmDisplay(mm, this.props.room.unit_preference);
    }

    _fromDisplay(raw) {
        return parseDisplayToMm(raw, this.props.room.unit_preference);
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
        // 2026-07-03 QA fix — Step 3 now respects the unit toggle rather
        // than hardcoding "(mm)". `room` carries unit_preference.
        room: Object,
        // Client-side geometry validation surfaced inline (out-of-bounds
        // errors + overlap warnings) — computed by the parent so the
        // Save button and this list agree.
        geometryErrors: { type: Array, optional: true },
        geometryWarnings: { type: Array, optional: true },
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

    _unit() { return this.props.room.unit_preference || "mm"; }
    _unitLabel() { return this._unit() === "imperial" ? "in" : "mm"; }
    _disp(mm) { return mmDisplay(mm, this._unit()); }
    _dispWithUnit(mm) {
        return this._unit() === "imperial"
            ? mmDisplay(mm, "imperial")
            : mmDisplay(mm, "mm") + " mm";
    }

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
        this.draft.distance_from_left_mm = parseDisplayToMm(
            ev.target.value, this._unit());
    }

    _onWidthInput(ev) {
        this.draft.width_mm = parseDisplayToMm(ev.target.value, this._unit());
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
        // 2026-07-03 QA fix — edit mode. When the OrderBuilder opens the
        // wizard on an already-saved room it passes the serialized room
        // dict here; the wizard hydrates every field and switches its
        // submit to /room/<id>/update. Null / absent → fresh create.
        existingRoom: { type: [Object, { value: null }], optional: true },
    };

    setup() {
        const existing = this.props.existingRoom || null;
        this.state = useState({
            step: 1,
            // Edit-mode identity + the furthest step the user may jump to
            // via the (now-clickable) stepper badges.
            isEdit: !!existing,
            roomId: existing ? existing.id : null,
            maxStepReached: existing ? 3 : 1,
            dirty: false,
            confirmDiscard: false,
            room: {
                name: existing ? (existing.name || "Main Kitchen") : "Main Kitchen",
                room_type: existing ? (existing.room_type || "kitchen") : "kitchen",
                layout_shape: existing ? existing.layout_shape : null,
                ceiling_height_mm: existing
                    ? (existing.ceiling_height_mm || 2400) : 2400,
                unit_preference: existing
                    ? (existing.unit_preference || "mm") : "mm",
            },
            walls: existing ? this._hydrateWalls(existing) : [],
            constraints: existing ? this._hydrateConstraints(existing) : [],
            // Phase 6.2 — Room Templates library. Populated by a single
            // fetch on mount; an empty list means the wizard renders the
            // Step 1 templates section invisibly (existing custom-shape
            // picker still works either way, fail-silent UX).
            templates: [],
            appliedTemplateName: null,
            errorMessage: null,
        });
        onMounted(() => {
            rpcJsonCall("/southbrook/api/room-templates/list", {})
                .then((r) => {
                    if (r && r.ok && Array.isArray(r.templates)) {
                        this.state.templates = r.templates;
                    }
                })
                .catch(() => {
                    // Silent fail — wizard still works without templates.
                });
        });
    }

    // ------------------------------------------------------------------
    // Edit-mode hydration (2026-07-03 QA fix). The serialized room dict
    // carries walls (in wall_order) each with nested constraints. We
    // flatten to the wizard's flat state.walls + state.constraints
    // (wall_index = the wall's position in the ordered array). Wall ids
    // ride along so the update endpoint reconciles in place instead of
    // creating duplicates.
    // ------------------------------------------------------------------
    _hydrateWalls(room) {
        return (room.walls || []).map((w, i) => ({
            id: w.id,
            name: w.name || ("Wall " + String.fromCharCode(65 + i)),
            length_mm: Math.max(0, Number(w.length_mm) || 0),
            wall_order: w.wall_order,
        }));
    }

    _hydrateConstraints(room) {
        const out = [];
        (room.walls || []).forEach((w, i) => {
            (w.constraints || []).forEach((c) => {
                out.push({
                    wall_index: i,
                    constraint_type: c.constraint_type,
                    distance_from_left_mm: Math.max(
                        0, Number(c.distance_from_left_mm) || 0),
                    width_mm: Math.max(0, Number(c.width_mm) || 0),
                    height_mm: c.height_mm || 0,
                });
            });
        });
        return out;
    }

    // Every state-mutating callback routes through here so Cancel / × can
    // warn before discarding unsaved input.
    _markDirty() {
        this.state.dirty = true;
    }

    // ------------------------------------------------------------------
    // Phase 6.2 — apply a Room Template. Clones the template's walls +
    // constraints into the wizard state and jumps to Step 2 so the user
    // tweaks lengths rather than starting from a blank slate.
    // ------------------------------------------------------------------
    _onApplyTemplate = (template) => {
        if (!template) return;
        this.state.room.layout_shape = template.layout_shape;
        this.state.room.room_type = template.room_type;
        this.state.room.ceiling_height_mm = template.ceiling_height_mm;
        this.state.walls = (template.walls || []).map((w) => ({
            name: w.name,
            length_mm: w.length_mm,
            wall_order: w.wall_order,
        }));
        this.state.constraints = (template.constraints || []).map((c) => ({
            wall_index: c.wall_index,
            constraint_type: c.constraint_type,
            distance_from_left_mm: c.distance_from_left_mm,
            width_mm: c.width_mm,
            height_mm: c.height_mm || 0,
        }));
        this.state.appliedTemplateName = template.name;
        this.state.step = 2;
        this.state.maxStepReached = Math.max(this.state.maxStepReached, 2);
        this._markDirty();
    };

    // ------------------------------------------------------------------
    // Step 1 callbacks
    // ------------------------------------------------------------------

    _onRoomTypePicked = (code) => {
        this.state.room.room_type = code;
        this._markDirty();
    };

    _onShapePicked = (code) => {
        this.state.room.layout_shape = code;
        this._markDirty();
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
        this._markDirty();
    };

    // ------------------------------------------------------------------
    // Step 2 callbacks
    // ------------------------------------------------------------------

    _onWallLengthChanged = (idx, mm) => {
        if (this.state.walls[idx]) {
            this.state.walls[idx].length_mm = mm;
            this._markDirty();
        }
    };

    _onWallNameChanged = (idx, name) => {
        if (this.state.walls[idx]) {
            this.state.walls[idx].name = name;
            this._markDirty();
        }
    };

    _onCeilingChanged = (mm) => {
        this.state.room.ceiling_height_mm = mm;
        this._markDirty();
    };

    _onUnitChanged = (unit) => {
        this.state.room.unit_preference = unit;
        this._markDirty();
    };

    // ------------------------------------------------------------------
    // Step 3 callbacks
    // ------------------------------------------------------------------

    _onAddConstraint = (c) => {
        this.state.constraints.push({ ...c });
        this._markDirty();
    };

    _onRemoveConstraint = (idx) => {
        this.state.constraints.splice(idx, 1);
        this._markDirty();
    };

    // ------------------------------------------------------------------
    // Step navigation
    // ------------------------------------------------------------------

    // Client mirror of southbrook.room.validate_geometry — instant
    // feedback. Out-of-bounds constraints BLOCK Save; overlaps only WARN.
    _geometryErrors() {
        const errs = [];
        const walls = this.state.walls || [];
        this.state.constraints.forEach((c, i) => {
            const wall = walls[c.wall_index];
            const start = Math.max(0, Number(c.distance_from_left_mm) || 0);
            const width = Math.max(0, Number(c.width_mm) || 0);
            if (wall && (wall.length_mm || 0) > 0
                && start + width > wall.length_mm) {
                const over = start + width - wall.length_mm;
                errs.push(`${this._humanShapeType(c.constraint_type)} on `
                    + `${wall.name || ("Wall " + String.fromCharCode(65 + c.wall_index))}`
                    + ` extends ${this._dispMm(over)} past the wall edge.`);
            }
        });
        return errs;
    }

    _geometryWarnings() {
        const warns = [];
        const byWall = {};
        this.state.constraints.forEach((c) => {
            if ((c.width_mm || 0) <= 0) return;
            if (["power_outlet", "structural_post"].includes(c.constraint_type)) return;
            (byWall[c.wall_index] = byWall[c.wall_index] || []).push(c);
        });
        Object.keys(byWall).forEach((wi) => {
            const list = byWall[wi].slice().sort(
                (a, b) => a.distance_from_left_mm - b.distance_from_left_mm);
            for (let i = 1; i < list.length; i++) {
                const prev = list[i - 1];
                const cur = list[i];
                if (cur.distance_from_left_mm
                    < prev.distance_from_left_mm + prev.width_mm) {
                    const wall = this.state.walls[wi];
                    warns.push(`${this._humanShapeType(prev.constraint_type)} and `
                        + `${this._humanShapeType(cur.constraint_type)} overlap on `
                        + `${(wall && wall.name) || ("Wall " + String.fromCharCode(65 + Number(wi)))}.`);
                }
            }
        });
        return warns;
    }

    _humanShapeType(code) {
        const found = CONSTRAINT_TYPES.find((c) => c.code === code);
        return found ? found.label : code;
    }

    _dispMm(mm) {
        return mmDisplay(mm, this.state.room.unit_preference)
            + (this.state.room.unit_preference === "imperial" ? "" : " mm");
    }

    _canAdvance() {
        if (this.state.step === 1) {
            return !!this.state.room.room_type && !!this.state.room.layout_shape;
        }
        if (this.state.step === 2) {
            // All walls must have a positive length.
            return this.state.walls.length > 0
                && this.state.walls.every((w) => (w.length_mm || 0) > 0);
        }
        if (this.state.step === 3) {
            // Out-of-bounds constraints block Save (overlaps only warn).
            return this._geometryErrors().length === 0;
        }
        return true;
    }

    // Inline hint explaining why Next / Save is disabled (empty when the
    // button is enabled).
    _advanceBlockedReason() {
        if (this.state.step === 1) {
            if (!this.state.room.room_type) return "Pick a room type to continue.";
            if (!this.state.room.layout_shape) return "Pick a layout shape to continue.";
        }
        if (this.state.step === 2) {
            if (!this.state.walls.length) return "Pick a layout shape first.";
            if (this.state.walls.some((w) => (w.length_mm || 0) <= 0)) {
                return "Enter a length for every wall.";
            }
        }
        if (this.state.step === 3) {
            const errs = this._geometryErrors();
            if (errs.length) return errs[0];
        }
        return "";
    }

    // Clickable stepper — jump to any step already reached. Guards on
    // maxStepReached so the user can't skip ahead past unfilled data.
    _goToStep = (n) => {
        if (typeof this.state.step !== "number") return;
        if (n < 1 || n > 3) return;
        if (n > this.state.maxStepReached) return;
        this.state.step = n;
    };

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
            this.state.maxStepReached = Math.max(
                this.state.maxStepReached, this.state.step);
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
        // Guard against backdrop-click closing the wizard mid-submit —
        // would orphan the server-created room while the user thinks
        // they cancelled. Submit-in-flight blocks close.
        if (this.state.step === "submitting") return;
        // Unsaved-changes guard (2026-07-03 QA fix) — an accidental
        // backdrop / × click must not silently drop a fully-entered
        // configuration. Show an in-wizard confirm instead of a native
        // dialog (native dialogs block the OWL event loop).
        if (this.state.dirty
            && this.state.step !== "done"
            && this.state.step !== "error") {
            this.state.confirmDiscard = true;
            return;
        }
        this.props.onClose();
    };

    _confirmDiscard = () => {
        this.state.confirmDiscard = false;
        this.props.onClose();
    };

    _cancelDiscard = () => {
        this.state.confirmDiscard = false;
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
            // Renumber wall_order by array position so the saved room
            // renders in the exact order shown in the wizard (new walls
            // added during an edit would otherwise all default to the
            // same wall_order and sort ambiguously).
            const walls = this.state.walls.map((w, i) => ({
                ...w,
                wall_order: (i + 1) * 10,
            }));
            const body = {
                name: this.state.room.name,
                room_type: this.state.room.room_type,
                layout_shape: this.state.room.layout_shape,
                ceiling_height_mm: this.state.room.ceiling_height_mm,
                unit_preference: this.state.room.unit_preference,
                walls: walls,
                constraints: this.state.constraints,
            };
            // Edit mode → UPDATE the existing room (reconcile walls +
            // replace constraints) so we never duplicate or blank it out.
            const url = this.state.isEdit
                ? "/southbrook/api/order/"
                    + encodeURIComponent(this.props.orderId)
                    + "/room/" + encodeURIComponent(this.state.roomId)
                    + "/update"
                : "/southbrook/api/order/"
                    + encodeURIComponent(this.props.orderId)
                    + "/room/create";
            const r = await rpcJsonCall(url, body);
            // Idempotency: server returns room_already_exists when the
            // order has a prior room — treat as success and hand the
            // existing room back, not as failure (review #2).
            if (r && r.error === "room_already_exists" && r.room) {
                this.state.step = "done";
                this.props.onSubmitted(r.room);
                return;
            }
            if (!r || r.error) {
                // Geometry errors carry a friendly detail string.
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
        if (this.state.step === 3) {
            return this.state.isEdit ? "Save Changes" : "Save Room";
        }
        return "Next";
    }
}
