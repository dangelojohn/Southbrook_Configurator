// SPDX-License-Identifier: LGPL-3.0-only
//
// SAMI / Southbrook Cabinetry — canonical 7-panel formulas (single source, JS twin).
//
// Peter Tuschak signed off these formulas on 2026-06-09 (G2 closed). Treat as final.
// Geometric conventions: NF14 (frameless euro construction, metric mm).
//
// This file is the byte-for-byte counterpart to ../shared/southbrook_dims.py.
// The two MUST stay in lockstep — Module 2's G1 gate compares Odoo BoM output
// against the .py file; the Three.js renderer uses this .js file; any drift
// between .py and .js will make customer-facing geometry diverge from the
// manufactured product, which is the single most expensive failure mode the
// project has to avoid.
//
// Consumed by:
//   - addons/southbrook_estimating_website/static/src/js/parametric_carcass.esm.js
//   - Module-8 customer portal Three.js KitchenCanvas component (when built)
//
// A panel cut is the 3-tuple [length_mm, width_mm, thickness_mm].

// --- Geometric constants (signed off 2026-06-09, G2 closed) ---
export const BOX_TH = 15.875;       // 5/8" melamine
export const BACK_TH = 6.35;        // 1/4" hardboard
export const RABBET = 6.35;
export const DOOR_TH = 18.0;        // 3/4" slab/5-piece
export const DOOR_REVEAL = 3.0;
export const SHELF_TOL = 1.5;
export const SHELF_VENT_GAP = 12.7;
export const TOEKICK_H = 101.6;     // 4" — integrated into sides, see toeKick()

export const TOEKICK_FAMILIES = new Set(["base", "sink", "tall", "vanity"]);

// --- 7 canonical panel formulas ---
export function side(heightMm, depthMm) {
  return [heightMm, depthMm, BOX_TH];
}

export function top(widthMm, depthMm) {
  const insideWidth = widthMm - 2 * BOX_TH;
  return [insideWidth, depthMm, BOX_TH];
}

export function bottom(widthMm, depthMm) {
  const insideWidth = widthMm - 2 * BOX_TH;
  return [insideWidth, depthMm, BOX_TH];
}

export function back(widthMm, heightMm) {
  const insideWidth = widthMm - 2 * BOX_TH;
  const length = insideWidth + 2 * RABBET;
  const width = (heightMm - 2 * BOX_TH) + 2 * RABBET;
  return [length, width, BACK_TH];
}

export function adjustableShelf(widthMm, depthMm) {
  const insideWidth = widthMm - 2 * BOX_TH;
  const length = insideWidth - SHELF_TOL;
  const width = depthMm - BACK_TH - RABBET - SHELF_VENT_GAP;
  return [length, width, BOX_TH];
}

export function shelfCount(heightMm) {
  if (heightMm <= 600) return 1;
  if (heightMm <= 900) return 2;
  return 3;
}

export function door(widthMm, heightMm, doorCount) {
  if (doorCount === 1) {
    return [heightMm - 2 * DOOR_REVEAL, widthMm - 2 * DOOR_REVEAL, DOOR_TH];
  }
  if (doorCount === 2) {
    return [heightMm - 2 * DOOR_REVEAL, (widthMm - 3 * DOOR_REVEAL) / 2, DOOR_TH];
  }
  return null;
}

// Toe-kick is INTEGRATED into the side panels (notch route, no separate cut).
// This returns a metadata descriptor, NOT a panel cut, so renderers know to
// draw the notch but cut-list code does not emit a separate piece.
export function toeKick(family, widthMm) {
  if (!TOEKICK_FAMILIES.has(family)) return null;
  return {
    integratedIntoSides: true,
    heightMm: TOEKICK_H,
    thicknessMm: BOX_TH,
  };
}

export function panelCutList(widthMm, heightMm, depthMm, family = "base", doorCount = 1) {
  const shelves = shelfCount(heightMm);
  return {
    sideL: side(heightMm, depthMm),
    sideR: side(heightMm, depthMm),
    top: top(widthMm, depthMm),
    bottom: bottom(widthMm, depthMm),
    back: back(widthMm, heightMm),
    adjustableShelf: shelves > 0 ? adjustableShelf(widthMm, depthMm) : null,
    shelfCount: shelves,
    door: door(widthMm, heightMm, doorCount),
    doorCount,
    toeKick: toeKick(family, widthMm),
  };
}
