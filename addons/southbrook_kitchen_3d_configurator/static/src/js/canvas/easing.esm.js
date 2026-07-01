/** @odoo-module **/
/**
 * Southbrook Kitchen 3D Configurator — easing helpers.
 *
 * Rec D · Sprint 2d · Step 7 · pure-function extraction.
 *
 * Extracted verbatim from the inline `ease` closure inside
 * kitchen_configurator.js's `_animateCamera` (was line 1031). Zero
 * behaviour change; the future <KitchenCanvas> can share the same
 * curve for its own camera animations.
 */

/**
 * Cubic ease-in-out on the interval [0, 1].
 *
 *   x=0    → 0
 *   x=0.5  → 0.5
 *   x=1    → 1
 *
 * Symmetric S-curve; second derivative is continuous at x=0.5.
 *
 * @param {number} x — normalized progress in [0, 1]
 * @returns {number}
 */
export function easeInOutCubic(x) {
    return x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2;
}
