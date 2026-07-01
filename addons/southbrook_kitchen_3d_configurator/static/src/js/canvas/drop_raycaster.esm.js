/** @odoo-module **/
/**
 * Southbrook Kitchen 3D Configurator — drop-X raycast.
 *
 * Rec D · Sprint 2d · Step 10 · pure-function extraction.
 *
 * Extracted from kitchen_configurator.js:463-478 (_computeDropX).
 * The pre-2d method read `this.T.raycaster`, `this.T.activeCamera`,
 * `this.T.THREE`, and `this.state.room.width_in` from class state;
 * the extracted function takes them all explicitly so the future
 * <KitchenCanvas> can reuse the same math with a different scene.
 */

/**
 * Compute the world-inches X coordinate a cursor is pointing at on
 * the floor plane. Returns null when the ray doesn't hit the floor
 * (e.g. side views with orthographic rays parallel to y=0).
 *
 * Clamps the result inside the room + 6" right-edge headroom, then
 * snaps to the 6" grid.
 *
 * @param {typeof THREE} THREE
 * @param {THREE.Camera} camera — active camera (ortho or persp)
 * @param {THREE.Raycaster} raycaster — pre-configured raycaster
 * @param {{ x: number, y: number }} ndc — normalized-device-coords
 *   (from `ndcFromEvent`)
 * @param {number} roomWidthIn — room width in inches
 * @param {number} snapIn — snap grid size in inches (default 6)
 * @param {number} marginIn — right-edge headroom in inches (default 6)
 * @returns {number | null} snapped X in inches, or null on no-hit
 */
export function computeDropXIn(THREE, camera, raycaster, ndc, roomWidthIn,
                                snapIn = 6, marginIn = 6) {
    if (!camera || !raycaster || !THREE) return null;
    raycaster.setFromCamera(ndc, camera);
    const floor  = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
    const hit    = new THREE.Vector3();
    const result = raycaster.ray.intersectPlane(floor, hit);
    if (!result) return null;
    // hit.x is in scene-feet (IN = 1/12). Multiply by 12 to get inches.
    let xIn = hit.x * 12;
    const maxX = Math.max(0, roomWidthIn - marginIn);
    xIn = Math.max(0, Math.min(maxX, xIn));
    return Math.round(xIn / snapIn) * snapIn;
}
