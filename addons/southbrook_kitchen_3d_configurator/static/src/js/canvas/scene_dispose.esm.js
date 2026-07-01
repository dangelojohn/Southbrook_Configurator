/** @odoo-module **/
/**
 * Southbrook Kitchen 3D Configurator — scene disposal helper.
 *
 * Rec D · Sprint 2d · Step 21 · pure disposal extraction.
 *
 * Extracted from the renderer + orbit disposal in
 * kitchen_configurator.js:1211-1219. Handles the OrbitControls
 * disposal + WebGL renderer disposal + DOM-node cleanup. The
 * class method retains the `this`-scoped cleanup (auto-save
 * timer, resize observer, event listener removal) since those
 * bind to the OWL component's identity.
 */

/**
 * @param {object} T — the T-bag with {orbit?, renderer?} refs
 * @param {HTMLElement|null} mount — canvas host div (for DOM removal)
 */
export function destroyScene(T, mount) {
    if (T.orbit) {
        try { T.orbit.dispose(); } catch (_) { /* noop */ }
    }
    if (T.renderer) {
        T.renderer.dispose();
        if (mount && T.renderer.domElement && mount.contains(T.renderer.domElement)) {
            mount.removeChild(T.renderer.domElement);
        }
    }
}
