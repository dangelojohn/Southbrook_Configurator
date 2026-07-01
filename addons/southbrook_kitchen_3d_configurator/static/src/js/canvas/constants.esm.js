/** @odoo-module **/
/**
 * Southbrook Kitchen 3D Configurator — canvas constants.
 *
 * Rec D · Sprint 2d · Step 1 · pure-literal extraction.
 *
 * Extracted verbatim from kitchen_configurator.js:20-47 to unlock
 * reuse by future shared canvas components (Sprint 2d step 5).
 * NO behaviour change — every constant value is identical to the
 * pre-2d state; only the module home moved.
 *
 * Consumers:
 *   - static/src/js/kitchen_configurator.js (existing internal client action)
 *   - future <KitchenCanvas> shared component (Sprint 2d step 5)
 *   - future /kitchen-planner mount (Sprint 2f)
 */

// ─── Cabinet constants (inches) ──────────────────────────────────────────────
export const IN  = 1 / 12;          // 1 inch in scene-feet
export const BW  = 24 * IN;         // base cabinet width  (2 ft)
export const BH  = 34.5 * IN;       // base cabinet height (34.5")
export const BD  = 24 * IN;         // base cabinet depth  (2 ft)
export const WW  = 24 * IN;         // wall cabinet width
export const WH  = 30 * IN;         // wall cabinet height (30")
export const WD  = 12 * IN;         // wall cabinet depth  (1 ft)
export const CTR = 1.5 * IN;        // countertop thickness
export const GAP = 18 * IN;         // clearance between counter and wall cab bottom
export const WBY = BH + CTR + GAP;  // wall cabinet bottom Y

// ─── Colour palette ───────────────────────────────────────────────────────────
export const P = {
    scene:   0xECE9E3,
    floor:   0xCFC4A8,
    wall1:   0xE7E2D9,   // back wall
    wall2:   0xDED8CE,   // left wall
    grid:    0xBAB4A8,
    cab:     0xC9C4BC,
    cabDark: 0xA9A59E,
    counter: 0xE1DDD6,
    handle:  0x3A3530,
    sel:     0x1866D4,
    drag:    0x1866D4,
    toekick: 0x8A857E,
    arrow:   0x1866D4,
};
