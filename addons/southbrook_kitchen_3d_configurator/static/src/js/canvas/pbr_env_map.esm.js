/** @odoo-module **/
/**
 * Southbrook Kitchen 3D Configurator — PBR environment map installer.
 *
 * Rec D · Sprint 2d · Step 14 · pure-function extraction.
 *
 * Extracted from kitchen_configurator.js:906-933 (_installPbrEnvMap).
 * Builds a small studio HDR-equivalent from a vertical gradient on
 * a canvas, runs it through PMREMGenerator, and assigns the result
 * as scene.environment. Adds soft PBR reflections on
 * MeshStandardMaterial metalness/roughness without needing an HDR
 * file at runtime.
 *
 * Mirrors the same helper in
 * southbrook_estimating_website/kitchen_viewport.esm.js. Once
 * <KitchenCanvas> ships (Sprint 2d step ~20), both classes should
 * import this shared version and the viewport twin can be deleted.
 *
 * Silent on any THREE feature-detect miss (older builds without
 * PMREMGenerator). Logs a warning on runtime exception; never
 * throws to the caller.
 */

/**
 * @param {typeof THREE} THREE
 * @param {THREE.Scene} scene
 * @param {THREE.WebGLRenderer} renderer
 */
export function installPbrEnvMap(THREE, scene, renderer) {
    if (!THREE || !scene || !renderer) return;
    if (!THREE.PMREMGenerator)        return;
    try {
        const canvas = document.createElement("canvas");
        const w = 512, h = 256;
        canvas.width = w; canvas.height = h;
        const ctx = canvas.getContext("2d");
        const grad = ctx.createLinearGradient(0, 0, 0, h);
        grad.addColorStop(0.00, "#fff5e8");   // overhead warm
        grad.addColorStop(0.40, "#e8e4dc");   // soft mid
        grad.addColorStop(0.70, "#c9c4ba");   // shadow side
        grad.addColorStop(1.00, "#8a8680");   // floor
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, w, h);
        const tex = new THREE.CanvasTexture(canvas);
        tex.mapping = THREE.EquirectangularReflectionMapping;
        if (THREE.SRGBColorSpace) tex.colorSpace = THREE.SRGBColorSpace;
        const pmrem = new THREE.PMREMGenerator(renderer);
        const envRT = pmrem.fromEquirectangular(tex);
        scene.environment = envRT.texture;
        tex.dispose();
        pmrem.dispose();
    } catch (exc) {
        console.warn("[SouthbrookKitchenConfigurator] PBR env install skipped:", exc);
    }
}
