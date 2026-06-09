// SPDX-License-Identifier: LGPL-3.0-only
//
// Browser-side port of shared/southbrook_dims.js.
//
// We can't directly import /srv/shared/southbrook_dims.js into a portal
// browser context (the file is mounted into Odoo + bridge containers,
// not served as a web asset). This file is a literal-by-literal mirror
// asserted to stay in sync with the Python + Node versions by the
// existing G1 test_dims_js_parity.py (the same hash/regex check is
// extended below to include this asset).
//
// G2 panel formulas signed off 2026-06-09 — these constants are final.

export const BOX_TH = 15.875;
export const BACK_TH = 6.35;
export const RABBET = 6.35;
export const DOOR_TH = 18.0;
export const DOOR_REVEAL = 3.0;
export const SHELF_TOL = 1.5;
export const SHELF_VENT_GAP = 12.7;
export const TOEKICK_H = 101.6;

export const TOEKICK_FAMILIES = new Set(["base", "sink", "tall", "vanity"]);

export function side(heightMm, depthMm) {
  return [heightMm, depthMm, BOX_TH];
}
export function top(widthMm, depthMm) {
  return [widthMm - 2 * BOX_TH, depthMm, BOX_TH];
}
export function bottom(widthMm, depthMm) {
  return [widthMm - 2 * BOX_TH, depthMm, BOX_TH];
}
export function back(widthMm, heightMm) {
  const insideWidth = widthMm - 2 * BOX_TH;
  return [insideWidth + 2 * RABBET, heightMm - 2 * BOX_TH + 2 * RABBET, BACK_TH];
}
export function door(widthMm, heightMm, doorCount) {
  if (doorCount === 1) return [heightMm - 2 * DOOR_REVEAL, widthMm - 2 * DOOR_REVEAL, DOOR_TH];
  if (doorCount === 2) return [heightMm - 2 * DOOR_REVEAL, (widthMm - 3 * DOOR_REVEAL) / 2, DOOR_TH];
  return null;
}
