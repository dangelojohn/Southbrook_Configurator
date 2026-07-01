/** @odoo-module **/
/**
 * Southbrook Kitchen 3D Configurator — camera view specs.
 *
 * Rec D · Sprint 2d · Step 4 · pure-function extraction.
 *
 * Extracted from kitchen_configurator.js:962-999 (_recomputeViews).
 * The pre-2d method assigned into `this.T.viewSpecs`; the extracted
 * function returns the dict directly so the caller decides where
 * to stash it.
 *
 * Each entry is:
 *   { cam: 'ortho' | 'persp',
 *     pos: THREE.Vector3,
 *     target: THREE.Vector3,
 *     up: THREE.Vector3,
 *     vs?: number  (ortho frustum half-height in scene-feet; omitted for persp) }
 */

/**
 * Compute the {iso, top, front, left, right, persp} camera view
 * specs for a room of given scene-space dimensions.
 *
 * @param {typeof THREE} THREE — the vendored Three.js module (needed
 *   because the specs contain THREE.Vector3 instances tied to the
 *   caller's THREE build).
 * @param {number} rw — room width in scene units
 * @param {number} rh — room height in scene units
 * @param {number} rd — room depth in scene units
 * @returns {object} viewSpecs dictionary
 */
export function computeViewSpecs(THREE, rw, rh, rd) {
    const max3  = Math.max(rw, rd, rh);
    const max2  = Math.max(rw, rd);
    const wallH = Math.max(rw, rh);
    const sideH = Math.max(rd, rh);
    return {
        iso:   { cam: "ortho",
                 pos:    new THREE.Vector3(rw + 12, rh * 0.7 + 6, rd + 12),
                 target: new THREE.Vector3(rw / 2, rh * 0.28, rd / 2),
                 up:     new THREE.Vector3(0, 1, 0),
                 vs:     max3  * 0.68 + 4.5 },
        top:   { cam: "ortho",
                 pos:    new THREE.Vector3(rw / 2, rh + 20, rd / 2),
                 target: new THREE.Vector3(rw / 2, 0, rd / 2),
                 up:     new THREE.Vector3(0, 0, -1),
                 vs:     max2  * 0.60 + 3.0 },
        front: { cam: "ortho",
                 pos:    new THREE.Vector3(rw / 2, rh / 2, rd + 18),
                 target: new THREE.Vector3(rw / 2, rh / 2, 0),
                 up:     new THREE.Vector3(0, 1, 0),
                 vs:     wallH * 0.60 + 2.0 },
        left:  { cam: "ortho",
                 pos:    new THREE.Vector3(-18, rh / 2, rd / 2),
                 target: new THREE.Vector3(0, rh / 2, rd / 2),
                 up:     new THREE.Vector3(0, 1, 0),
                 vs:     sideH * 0.60 + 2.0 },
        right: { cam: "ortho",
                 pos:    new THREE.Vector3(rw + 18, rh / 2, rd / 2),
                 target: new THREE.Vector3(rw, rh / 2, rd / 2),
                 up:     new THREE.Vector3(0, 1, 0),
                 vs:     sideH * 0.60 + 2.0 },
        persp: { cam: "persp",
                 pos:    new THREE.Vector3(rw + 10, rh * 0.9, rd + 10),
                 target: new THREE.Vector3(rw / 2, rh * 0.35, rd / 2),
                 up:     new THREE.Vector3(0, 1, 0) },
    };
}
