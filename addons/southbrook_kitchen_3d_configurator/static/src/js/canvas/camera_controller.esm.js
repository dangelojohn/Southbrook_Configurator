/** @odoo-module **/
/**
 * Southbrook Kitchen 3D Configurator — camera controller.
 *
 * Rec D · Sprint 2d · Step 22 · closure-body extraction.
 *
 * Owns the D1 multi-view camera system: view-switch (setView),
 * smooth-lerp between views (animateCamera), and wheel-zoom
 * (onWheel). Extracted from kitchen_configurator.js:987-1055.
 *
 * All three take `T` (the class' `this.T` bag) by reference so
 * the animation loop's `T.activeCamera !== cam` early-exit still
 * fires when the caller (setView) reassigns the active camera.
 * Do NOT destructure or shallow-copy T inside these functions.
 *
 * setView takes optional callback deps (applyOrthoFrustum,
 * animateCamera) so the class can inject its own wrappers rather
 * than the pure fn having to import them.
 */

/**
 * Swap to a named view. `instant=true` jumps; otherwise lerps 400ms.
 *
 * The OWL state write (`this.state.view = key`) MUST happen in the
 * class wrapper BEFORE calling this, so `_applyOrthoFrustum` picks
 * up the new view's `vs`.
 *
 * @param {object} T — the class T bag
 * @param {string} viewKey — one of iso/top/front/left/right/persp
 * @param {{
 *   instant: boolean,
 *   applyOrthoFrustum: () => void,
 *   animateCamera: (pos, target, up, ms) => void,
 * }} deps
 * @returns {boolean} true if the view was found + applied
 */
export function setView(T, viewKey, { instant, applyOrthoFrustum, animateCamera }) {
    if (!T.viewSpecs || !T.viewSpecs[viewKey]) return false;
    const spec = T.viewSpecs[viewKey];
    T.vsScale = 1;
    if (spec.cam === "ortho") {
        T.activeCamera = T.cameras.ortho;
        if (T.orbit) T.orbit.enabled = false;
    } else {
        T.activeCamera = T.cameras.persp;
        if (T.orbit) {
            T.orbit.enabled = true;
            T.orbit.target.copy(spec.target);
        }
    }
    const handleVisible = (viewKey === "iso" || viewKey === "top");
    if (T.handleMesh)  T.handleMesh.visible = handleVisible;
    if (T.arrowMeshes) T.arrowMeshes.forEach(m => { m.visible = handleVisible; });
    if (instant) {
        T.activeCamera.position.copy(spec.pos);
        T.activeCamera.up.copy(spec.up);
        T.activeCamera.lookAt(spec.target);
        T.currentTarget.copy(spec.target);
    } else {
        animateCamera(spec.pos, spec.target, spec.up, 400);
    }
    applyOrthoFrustum();
    return true;
}

/**
 * Smoothly lerp the active camera from its current pose to a new
 * (pos, target, up) over `ms` milliseconds. Sets T.animatingCamera
 * true while the animation is in flight; cancels itself cleanly
 * if `T.activeCamera` changes mid-animation (e.g. rapid view flip).
 *
 * @param {object} T
 * @param {THREE.Vector3} toPos
 * @param {THREE.Vector3} toTarget
 * @param {THREE.Vector3} toUp
 * @param {number} ms
 * @param {(x: number) => number} easeFn
 * @param {(cb: () => void) => number} raf
 */
export function animateCamera(T, toPos, toTarget, toUp, ms, easeFn, raf) {
    const cam = T.activeCamera;
    if (!cam) return;
    const fromPos = cam.position.clone();
    const fromTgt = T.currentTarget.clone();
    const t0 = performance.now();
    T.animatingCamera = true;
    const step = () => {
        if (!T.activeCamera || T.activeCamera !== cam) {
            T.animatingCamera = false;
            return;
        }
        const dt = Math.min(1, (performance.now() - t0) / ms);
        const k  = easeFn(dt);
        cam.position.lerpVectors(fromPos, toPos, k);
        const tgt = fromTgt.clone().lerp(toTarget, k);
        cam.up.copy(toUp);
        cam.lookAt(tgt);
        T.currentTarget.copy(tgt);
        if (T.orbit && T.orbit.enabled) T.orbit.target.copy(tgt);
        if (dt < 1) raf(step);
        else        T.animatingCamera = false;
    };
    step();
}

/**
 * Handle a wheel event on the canvas.
 *
 * Ortho views: bump the vsScale multiplier (clamp [0.3, 3.0]) and
 * re-apply the ortho frustum. Persp view: no-op, OrbitControls
 * handles wheel dolly natively.
 *
 * @param {object} T
 * @param {WheelEvent} e
 * @param {() => void} applyOrthoFrustum
 */
export function onWheel(T, e, applyOrthoFrustum) {
    e.preventDefault();
    if (T.activeCamera === T.cameras.persp && T.orbit) return;
    const k = e.deltaY > 0 ? 1.1 : 0.9;
    T.vsScale = Math.max(0.3, Math.min(3.0, (T.vsScale || 1) * k));
    applyOrthoFrustum();
}
