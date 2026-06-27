/** @odoo-module **/
/*
 * SPDX-License-Identifier: LGPL-3.0-only
 *
 * Phase 3.B — Room geometry helper (2026-06-27).
 *
 * Pure function shared by:
 *   - RoomOutlinePreview (Phase 2.C wizard) — needs the polyline
 *     vertices to draw a rough outline as the user types wall lengths.
 *   - FloorPlanSVG (Phase 3.B Room Layout tab) — needs the per-wall
 *     direction + normal vectors to orient cabinet polygons correctly
 *     along each wall.
 *
 * Output:  an array of `{name, length_mm, x0, y0, x1, y1, dx, dy,
 *           normalX, normalY}` — one entry per wall, in the user's
 *           original wall order.
 *
 * Coordinates use "screen axes": +x right, +y down (matches SVG).
 * Normals point INTO the room interior (so cabinets project off the
 * wall toward the interior when drawn at `+normal * depth`).
 *
 * Geometry contract per shape:
 *   - straight  (1 wall)  : A horizontal across the top, normal +Y
 *   - l_shape   (2 walls) : A across top, B down right side, both normals interior
 *   - u_shape   (3 walls) : A across top, B down right, C across bottom
 *   - galley    (2 walls) : two parallel horizontal walls (gap = 1200 mm default)
 *
 * Unsupported shapes (g_shape, peninsula, island, custom) return
 * `null` — callers should fall back to a flat "stacked wall list"
 * rendering. Phase 3.B's FloorPlanSVG implements that fallback so the
 * tab never crashes on an exotic shape — it just renders less prettily.
 */

const DEFAULT_GALLEY_GAP_MM = 1200;

/**
 * Compute 2D geometry for every wall of a room.
 *
 * @param {string|null} shape         layout_shape selection value
 * @param {Array<{name, length_mm}>} walls   one entry per wall, in order
 * @param {object} [opts]
 * @param {number} [opts.galleyGapMm] override the galley aisle width
 * @returns {Array<object>|null} per-wall geometry or null if the shape
 *                               has no first-class polyline support
 */
export function wallSegmentsForShape(shape, walls, opts = {}) {
    const galleyGap = opts.galleyGapMm || DEFAULT_GALLEY_GAP_MM;
    const safeWalls = (walls || []).map((w) => ({
        name: w.name || "",
        length_mm: Math.max(0, Number(w.length_mm) || 0),
        raw: w,
    }));

    if (shape === "straight" && safeWalls.length >= 1) {
        const A = safeWalls[0];
        // Wall A horizontal across the top, room interior below → normal +Y
        return [_seg(A, 0, 0, A.length_mm, 0, 0, 1)];
    }

    if (shape === "l_shape" && safeWalls.length >= 2) {
        const A = safeWalls[0];
        const B = safeWalls[1];
        // A: (0,0) → (lenA, 0)  ; interior is below → normal +Y
        // B: (lenA, 0) → (lenA, lenB) ; interior is to the left → normal -X
        return [
            _seg(A, 0, 0, A.length_mm, 0, 0, 1),
            _seg(B, A.length_mm, 0, A.length_mm, B.length_mm, -1, 0),
        ];
    }

    if (shape === "u_shape" && safeWalls.length >= 3) {
        const A = safeWalls[0];
        const B = safeWalls[1];
        const C = safeWalls[2];
        // A: (0,0) → (lenA, 0) — top wall, normal +Y (interior below)
        // B: (lenA, 0) → (lenA, lenB) — right wall, normal -X (interior left)
        // C: (lenA, lenB) → (lenA - lenC, lenB) — bottom wall, normal -Y
        return [
            _seg(A, 0, 0, A.length_mm, 0, 0, 1),
            _seg(B, A.length_mm, 0, A.length_mm, B.length_mm, -1, 0),
            _seg(C, A.length_mm, B.length_mm,
                 A.length_mm - C.length_mm, B.length_mm, 0, -1),
        ];
    }

    if (shape === "galley" && safeWalls.length >= 2) {
        const A = safeWalls[0];
        const B = safeWalls[1];
        // A: (0,0) → (lenA, 0)  ; normal +Y (interior below A)
        // B: (0, gap) → (lenB, gap) ; normal -Y (interior above B)
        return [
            _seg(A, 0, 0, A.length_mm, 0, 0, 1),
            _seg(B, 0, galleyGap, B.length_mm, galleyGap, 0, -1),
        ];
    }

    // No first-class geometry for this shape — caller renders the
    // stacked-wall fallback.
    return null;
}

// Build a single wall segment record. Computes dx/dy unit vector along
// the wall direction so cabinet placement helpers can project a
// position_from_left_mm distance into world coordinates.
function _seg(wall, x0, y0, x1, y1, nx, ny) {
    const dxRaw = x1 - x0;
    const dyRaw = y1 - y0;
    const len = Math.sqrt(dxRaw * dxRaw + dyRaw * dyRaw) || 1;
    return {
        name: wall.name,
        length_mm: wall.length_mm,
        raw: wall.raw,
        x0,
        y0,
        x1,
        y1,
        dx: dxRaw / len,
        dy: dyRaw / len,
        normalX: nx,
        normalY: ny,
    };
}

/**
 * Convenience: collapse wall segments to a polyline points array. Used
 * by RoomOutlinePreview which only wants the vertex list, not the
 * direction vectors.
 *
 * Two distinct walls that don't share an endpoint (e.g. galley) emit
 * separate sub-paths — we just connect them with a polyline jump for
 * the wizard preview. The Phase 3.B SVG renders each wall as its own
 * `<line>` so this jump only ever shows in the wizard preview.
 *
 * @param {Array<object>} segments  output of wallSegmentsForShape
 * @returns {Array<[number, number]>} polyline vertices
 */
export function polylinePointsFromSegments(segments) {
    if (!segments || segments.length === 0) return [];
    const out = [];
    for (let i = 0; i < segments.length; i += 1) {
        const s = segments[i];
        if (i === 0) {
            out.push([s.x0, s.y0]);
        } else {
            const prev = out[out.length - 1];
            // Connect only if the next segment doesn't continue the
            // previous endpoint (galley case).
            if (prev[0] !== s.x0 || prev[1] !== s.y0) {
                out.push([s.x0, s.y0]);
            }
        }
        out.push([s.x1, s.y1]);
    }
    return out;
}
