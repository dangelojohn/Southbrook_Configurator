/** @odoo-module **/
/*
 * SPDX-License-Identifier: LGPL-3.0-only
 *
 * architectural_symbols.esm — top-down (floor plan) SVG symbols for
 * southbrook.room.constraint records. One symbol per constraint_type
 * so the floor plan reads as an architectural drawing rather than a
 * grid of labeled rectangles.
 *
 * Conventions:
 *   - Each builder returns a STRING of SVG markup positioned inside a
 *     (0, 0)-(w, h) box. The caller wraps the result in
 *     `<g transform="translate(x, y)"><t t-out="markup(svg)"/></g>`.
 *   - Stroke uses CSS class `sb-arch-stroke` (1-2px black/dark grey)
 *     so the room_layout.scss owner can re-skin without touching JS.
 *   - Fills use `sb-arch-fill-light` for translucent gray washes and
 *     `sb-arch-fill-bowl` for sink bowl interiors.
 *   - Symbols degrade gracefully at small sizes — every symbol still
 *     renders SOMETHING down to 8×8 px (just becomes a labeled box).
 *
 * Why string return values instead of OWL VNodes:
 *   - The library is consumed from a getter on a heavily-iterated OWL
 *     component (FloorPlanSVG._constraintPolys). Returning markup
 *     strings + `t-out` with markup() avoids reconciliation overhead
 *     of dozens of nested OWL nodes per render. Symbols are immutable
 *     given (type, w, h); the strings can be cached.
 *
 * Symbol design notes (per constraint_type):
 *
 *   window           — pair of parallel thin lines across the wall depth;
 *                      mid-line if panel_count == 2; thirds if 3+.
 *   door             — door panel rectangle + quarter-arc showing swing.
 *                      Hinge side toggles by swing_direction.
 *   sink             — outer counter rectangle + inset bowl ellipse +
 *                      small drain circle.
 *   cooktop          — 4 burner circles in a 2×2 grid (or 5/6 burner
 *                      arrangement for wider widths).
 *   range            — same as cooktop (top view is identical).
 *   oven             — outer rect + smaller inner rect (door panel) +
 *                      handle line across the top.
 *   dishwasher       — counter rect + handle bar along front edge.
 *   rangehood        — trapezoid (wider front, narrower back) — read as
 *                      perspective view from above looking down.
 *   fridge_space     — counter rect + vertical line at door split.
 *                      French-door = two lines at 1/3 + 2/3.
 *   freezer          — counter rect + horizontal lines for drawer fronts.
 *   microwave        — counter rect with rounded corners + display strip
 *                      along the top edge.
 *   wine_fridge      — counter rect + 3 horizontal lines (shelves).
 *   beverage_center  — counter rect + 2 horizontal lines.
 *   warming_drawer   — flat rect + bar handle along front.
 *   ice_maker        — counter rect + diagonal cross-hatch (ice symbol).
 *   trash_compactor  — counter rect + downward chevron (compact).
 *   coffee_built_in  — counter rect + small cup outline.
 *   power_outlet     — small filled square; (currently rendered as icon
 *                      in WallElevationSVG, not consumed here).
 *   structural_post  — filled square with X (column marker).
 *   other            — empty rect with diagonal stripe.
 */

// ----- shared primitives --------------------------------------------------

const STROKE = "stroke:#2c3038;stroke-width:1.25;fill:none;";
const STROKE_THIN = "stroke:#2c3038;stroke-width:0.75;fill:none;";
const FILL_LIGHT = "fill:rgba(0,0,0,0.04);stroke:#2c3038;stroke-width:1.25;";
const FILL_BOWL = "fill:rgba(80,140,200,0.10);stroke:#2c3038;stroke-width:0.9;";
const FILL_FILLED = "fill:rgba(0,0,0,0.18);stroke:#2c3038;stroke-width:1;";

function _rect(x, y, w, h, style = FILL_LIGHT) {
    return `<rect x="${x}" y="${y}" width="${w}" height="${h}" style="${style}"/>`;
}

function _circle(cx, cy, r, style = STROKE) {
    return `<circle cx="${cx}" cy="${cy}" r="${r}" style="${style}"/>`;
}

function _line(x1, y1, x2, y2, style = STROKE_THIN) {
    return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" style="${style}"/>`;
}

function _path(d, style = STROKE) {
    return `<path d="${d}" style="${style}"/>`;
}

// ----- per-type builders --------------------------------------------------

function _window(w, h, panelCount = 1) {
    // Pair of horizontal lines across the wall thickness; mid-line if 2
    // panels; thirds if 3+. The outer rect frames the casing.
    const parts = [];
    parts.push(_rect(0, 0, w, h, FILL_LIGHT));
    parts.push(_line(0, h * 0.35, w, h * 0.35));
    parts.push(_line(0, h * 0.65, w, h * 0.65));
    if (panelCount >= 2) {
        for (let i = 1; i < panelCount; i++) {
            const x = (w / panelCount) * i;
            parts.push(_line(x, 0, x, h));
        }
    }
    return parts.join("");
}

function _door(w, h, swing = "right") {
    // Door panel = thin filled rectangle along one edge. Swing arc = 90°
    // quarter circle from the hinge corner. left|right toggles handing.
    const parts = [];
    parts.push(_rect(0, 0, w, h, "fill:none;stroke:#2c3038;stroke-width:1;stroke-dasharray:3 2;"));
    if (swing === "pocket" || swing === "sliding") {
        // Sliding door — two parallel lines (track + door) along the wall
        parts.push(_line(0, h * 0.4, w, h * 0.4));
        parts.push(_line(0, h * 0.6, w, h * 0.6));
        return parts.join("");
    }
    if (swing === "bifold") {
        // Bifold — two arc segments
        parts.push(_path(`M ${w / 2} 0 L ${w / 2} ${h}`, STROKE_THIN));
        parts.push(_path(`M 0 0 A ${w / 2} ${h} 0 0 1 ${w / 2} ${h}`, STROKE_THIN));
        parts.push(_path(`M ${w} 0 A ${w / 2} ${h} 0 0 0 ${w / 2} ${h}`, STROKE_THIN));
        return parts.join("");
    }
    // Hinged door — panel along bottom edge, arc swinging open into room
    if (swing === "left") {
        // Hinged on the LEFT — door panel extends right from the hinge,
        // arc sweeps from door tip down to the wall on the right.
        parts.push(_line(0, h, w, h));  // door panel along bottom
        parts.push(_path(`M ${w} ${h} A ${w} ${w} 0 0 0 0 ${h - w}`, STROKE));
    } else {
        // Hinged on the RIGHT — mirror of above.
        parts.push(_line(0, h, w, h));
        parts.push(_path(`M 0 ${h} A ${w} ${w} 0 0 1 ${w} ${h - w}`, STROKE));
    }
    return parts.join("");
}

function _sink(w, h) {
    // Outer counter rect + inset bowl + drain dot.
    const parts = [];
    parts.push(_rect(0, 0, w, h, FILL_LIGHT));
    const mx = w * 0.1;
    const my = h * 0.15;
    parts.push(_rect(mx, my, w - 2 * mx, h - 2 * my, FILL_BOWL));
    parts.push(_circle(w / 2, h * 0.65, Math.min(w, h) * 0.07, "fill:#2c3038;stroke:none;"));
    return parts.join("");
}

function _burners(w, h, count = 4) {
    // 4-burner grid (2×2) by default; 5 = quincunx; 6 = 2×3.
    const parts = [_rect(0, 0, w, h, FILL_LIGHT)];
    const r = Math.min(w, h) * 0.12;
    let positions = [];
    if (count <= 4) {
        positions = [
            [w * 0.3, h * 0.3], [w * 0.7, h * 0.3],
            [w * 0.3, h * 0.7], [w * 0.7, h * 0.7],
        ];
    } else if (count === 5) {
        positions = [
            [w * 0.25, h * 0.3], [w * 0.75, h * 0.3],
            [w * 0.5, h * 0.5],
            [w * 0.25, h * 0.7], [w * 0.75, h * 0.7],
        ];
    } else {
        positions = [
            [w * 0.2, h * 0.3], [w * 0.5, h * 0.3], [w * 0.8, h * 0.3],
            [w * 0.2, h * 0.7], [w * 0.5, h * 0.7], [w * 0.8, h * 0.7],
        ];
    }
    for (const [cx, cy] of positions) {
        parts.push(_circle(cx, cy, r));
        parts.push(_circle(cx, cy, r * 0.45));
    }
    return parts.join("");
}

function _cooktop(w, h) {
    // Burner count scales with width — 24" → 4, 30-36" → 4-5, 36+" → 5-6
    const count = w >= 50 ? 6 : (w >= 36 ? 5 : 4);
    return _burners(w, h, count);
}

function _range(w, h) {
    // Same top-down silhouette as cooktop.
    return _cooktop(w, h);
}

function _oven(w, h) {
    // Outer rect + door panel (inset) + handle line across the top.
    const parts = [];
    parts.push(_rect(0, 0, w, h, FILL_LIGHT));
    const mx = w * 0.08;
    const my = h * 0.15;
    parts.push(_rect(mx, my, w - 2 * mx, h - 2 * my, "fill:none;stroke:#2c3038;stroke-width:0.8;"));
    parts.push(_line(w * 0.15, h * 0.22, w * 0.85, h * 0.22));
    return parts.join("");
}

function _dishwasher(w, h) {
    // Counter rect + handle bar along the front + soap dispenser dot.
    const parts = [];
    parts.push(_rect(0, 0, w, h, FILL_LIGHT));
    parts.push(_rect(w * 0.1, h * 0.85, w * 0.8, h * 0.06, "fill:#2c3038;"));
    parts.push(_circle(w * 0.3, h * 0.4, Math.min(w, h) * 0.04, "fill:#2c3038;stroke:none;"));
    return parts.join("");
}

function _rangehood(w, h) {
    // Trapezoid (wider front edge, narrower back) — perspective view.
    const insetX = w * 0.15;
    const parts = [];
    parts.push(_path(
        `M 0 ${h} L ${w} ${h} L ${w - insetX} 0 L ${insetX} 0 Z`,
        FILL_LIGHT,
    ));
    // Centered filter circle suggesting the fan housing
    parts.push(_circle(w / 2, h * 0.55, Math.min(w, h) * 0.18));
    return parts.join("");
}

function _fridge_space(w, h) {
    // Counter rect + door split lines. French-door = two thirds; single = mid.
    const parts = [_rect(0, 0, w, h, FILL_LIGHT)];
    if (w >= 850) {
        // French-door style (≥ 36" / 914mm normally)
        parts.push(_line(w / 3, 0, w / 3, h * 0.75));
        parts.push(_line(2 * w / 3, 0, 2 * w / 3, h * 0.75));
        parts.push(_line(0, h * 0.75, w, h * 0.75));  // freezer drawer split
    } else {
        // Side-by-side or single-door
        parts.push(_line(w / 2, 0, w / 2, h));
    }
    return parts.join("");
}

function _freezer(w, h) {
    // Counter rect + horizontal drawer lines (typically 2 drawers).
    const parts = [_rect(0, 0, w, h, FILL_LIGHT)];
    parts.push(_line(0, h / 3, w, h / 3));
    parts.push(_line(0, 2 * h / 3, w, 2 * h / 3));
    return parts.join("");
}

function _microwave(w, h) {
    // Rounded rect + display strip along the top.
    const r = Math.min(w, h) * 0.08;
    return (
        `<rect x="0" y="0" width="${w}" height="${h}" rx="${r}" ry="${r}" style="${FILL_LIGHT}"/>` +
        _rect(w * 0.6, h * 0.1, w * 0.3, h * 0.12, "fill:#2c3038;stroke:none;")
    );
}

function _wine_fridge(w, h) {
    // Counter rect + 3 horizontal shelf lines.
    const parts = [_rect(0, 0, w, h, FILL_LIGHT)];
    for (let i = 1; i <= 3; i++) {
        parts.push(_line(w * 0.1, h * i / 4, w * 0.9, h * i / 4, STROKE_THIN));
    }
    return parts.join("");
}

function _beverage_center(w, h) {
    // 2 shelves instead of 3.
    const parts = [_rect(0, 0, w, h, FILL_LIGHT)];
    parts.push(_line(w * 0.1, h / 3, w * 0.9, h / 3, STROKE_THIN));
    parts.push(_line(w * 0.1, 2 * h / 3, w * 0.9, 2 * h / 3, STROKE_THIN));
    return parts.join("");
}

function _warming_drawer(w, h) {
    // Flat rect + bar handle along the front edge.
    return _rect(0, 0, w, h, FILL_LIGHT) +
        _rect(w * 0.15, h * 0.4, w * 0.7, h * 0.15, "fill:#2c3038;");
}

function _ice_maker(w, h) {
    // Counter rect + diagonal cross-hatch (ice symbol).
    const parts = [_rect(0, 0, w, h, FILL_LIGHT)];
    parts.push(_line(w * 0.2, h * 0.2, w * 0.8, h * 0.8, STROKE_THIN));
    parts.push(_line(w * 0.8, h * 0.2, w * 0.2, h * 0.8, STROKE_THIN));
    parts.push(_line(w / 2, h * 0.15, w / 2, h * 0.85, STROKE_THIN));
    return parts.join("");
}

function _trash_compactor(w, h) {
    // Counter rect + downward chevron (compact).
    const parts = [_rect(0, 0, w, h, FILL_LIGHT)];
    parts.push(_path(
        `M ${w * 0.3} ${h * 0.35} L ${w / 2} ${h * 0.6} L ${w * 0.7} ${h * 0.35}`,
        STROKE,
    ));
    return parts.join("");
}

function _coffee_built_in(w, h) {
    // Counter rect + small cup outline.
    const parts = [_rect(0, 0, w, h, FILL_LIGHT)];
    const cx = w / 2;
    const cy = h * 0.55;
    const cw = Math.min(w, h) * 0.32;
    const ch = Math.min(w, h) * 0.28;
    parts.push(_path(
        `M ${cx - cw / 2} ${cy - ch / 2} ` +
        `L ${cx - cw / 2} ${cy + ch / 2} ` +
        `Q ${cx - cw / 2} ${cy + ch / 2 + ch * 0.2} ${cx} ${cy + ch / 2 + ch * 0.2} ` +
        `Q ${cx + cw / 2} ${cy + ch / 2 + ch * 0.2} ${cx + cw / 2} ${cy + ch / 2} ` +
        `L ${cx + cw / 2} ${cy - ch / 2} Z`,
        STROKE,
    ));
    // Cup handle
    parts.push(_path(
        `M ${cx + cw / 2} ${cy - ch * 0.2} ` +
        `Q ${cx + cw} ${cy} ${cx + cw / 2} ${cy + ch * 0.2}`,
        STROKE_THIN,
    ));
    return parts.join("");
}

function _structural_post(w, h) {
    // Filled square with X — load-bearing column marker.
    const parts = [_rect(0, 0, w, h, FILL_FILLED)];
    parts.push(_line(0, 0, w, h));
    parts.push(_line(w, 0, 0, h));
    return parts.join("");
}

function _power_outlet(w, h) {
    // Small filled square — usually rendered as 14×14 icon in elevation.
    return _rect(w * 0.3, h * 0.3, w * 0.4, h * 0.4, FILL_FILLED);
}

function _other(w, h) {
    // Empty rect with diagonal stripes (placeholder for unmapped types).
    const parts = [_rect(0, 0, w, h, FILL_LIGHT)];
    for (let i = 1; i < 4; i++) {
        const x = (w / 4) * i;
        parts.push(_line(x, 0, x - w * 0.15, h, STROKE_THIN));
    }
    return parts.join("");
}

// ----- public API ---------------------------------------------------------

const BUILDERS = {
    window: _window,
    door: _door,
    sink: _sink,
    cooktop: _cooktop,
    range: _range,
    oven: _oven,
    dishwasher: _dishwasher,
    rangehood: _rangehood,
    fridge_space: _fridge_space,
    freezer: _freezer,
    microwave: _microwave,
    wine_fridge: _wine_fridge,
    beverage_center: _beverage_center,
    warming_drawer: _warming_drawer,
    ice_maker: _ice_maker,
    trash_compactor: _trash_compactor,
    coffee_built_in: _coffee_built_in,
    structural_post: _structural_post,
    power_outlet: _power_outlet,
    other: _other,
};

/**
 * Return SVG markup (string) for a given constraint type sized to fit
 * a (0,0)-(w,h) box. Pass extra options for types that have them
 * (door swing, window panel count).
 *
 * @param {string} type   constraint_type key
 * @param {number} w      width in pixels (SVG units)
 * @param {number} h      height in pixels
 * @param {object} opts   per-type options: { swing, panelCount }
 * @returns {string}      SVG markup, ready to insert inside a parent <g>
 */
export function symbolFor(type, w, h, opts = {}) {
    if (!Number.isFinite(w) || !Number.isFinite(h) || w <= 0 || h <= 0) return "";
    const builder = BUILDERS[type] || _other;
    if (type === "door") return builder(w, h, opts.swing || "right");
    if (type === "window") return builder(w, h, opts.panelCount || 1);
    return builder(w, h);
}

export function supportedSymbolTypes() {
    return Object.keys(BUILDERS);
}
