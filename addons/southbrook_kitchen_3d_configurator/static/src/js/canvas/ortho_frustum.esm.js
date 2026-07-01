/** @odoo-module **/
/**
 * Southbrook Kitchen 3D Configurator — orthographic frustum helper.
 *
 * Rec D · Sprint 2d · Step 8 · pure-function extraction.
 *
 * Extracted from the math inside kitchen_configurator.js's
 * `_applyOrthoFrustum` (was line 1003-1017). Zero behaviour change;
 * the future <KitchenCanvas> can compute frustum params without
 * carrying the same math inline.
 */

/**
 * Compute the six orthographic frustum params (left/right/top/bottom/
 * near/far) for a room-view spec, given a wheel-zoom multiplier and
 * the renderer's current pixel dimensions.
 *
 * @param {number} specVs — the view spec's `vs` half-height in scene-feet
 * @param {number} vsScale — wheel-zoom multiplier (1.0 = default)
 * @param {number} rendererW — renderer.domElement.width
 * @param {number} rendererH — renderer.domElement.height
 * @returns {{ left: number, right: number, top: number, bottom: number,
 *            near: number, far: number }}
 */
export function computeOrthoFrustum(specVs, vsScale, rendererW, rendererH) {
    const baseVs = specVs || 9;
    const vs = baseVs * (vsScale || 1);
    const asp = (rendererW && rendererH) ? rendererW / rendererH : 1;
    return {
        left:   -vs * asp,
        right:   vs * asp,
        top:     vs,
        bottom: -vs,
        near:    0.1,
        far:     300,
    };
}
