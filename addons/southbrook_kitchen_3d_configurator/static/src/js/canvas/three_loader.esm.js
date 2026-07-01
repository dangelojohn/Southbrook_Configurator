/** @odoo-module **/
/**
 * Southbrook Kitchen 3D Configurator — Three.js loader.
 *
 * Rec D · Sprint 2d · Step 2 · pure-function extraction.
 *
 * Extracted verbatim from kitchen_configurator.js:56-62. Zero
 * behaviour change; the function body is byte-for-byte identical.
 * Consumers:
 *   - kitchen_configurator.js (existing internal client action)
 *   - future <KitchenCanvas> shared component
 */

// As of 19.0.3.0.0 we depend on southbrook_estimating, which ships a
// vendored r160 build of THREE in web.assets_backend (via this addon's
// manifest). The previous CDN load of three@0.128 was dropped — it
// lacked SRGBColorSpace / ACESFilmicToneMapping (r152+) and double-
// loaded against the catalog's local copy. window.THREE is guaranteed
// to be present at module load time.
export function loadThreeJS() {
    if (window.THREE) return Promise.resolve(window.THREE);
    return Promise.reject(new Error(
        "Three.js not available. southbrook_estimating's vendored " +
        "three.min.js must load before kitchen_configurator.js (see manifest)."
    ));
}
