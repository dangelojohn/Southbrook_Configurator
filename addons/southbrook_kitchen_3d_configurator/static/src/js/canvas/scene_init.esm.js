/** @odoo-module **/
/**
 * Southbrook Kitchen 3D Configurator — scene + cameras + renderer +
 * lighting rig + orbit setup.
 *
 * Rec D · Sprint 2d · Step 20 · pure setup extraction.
 *
 * Extracted from kitchen_configurator.js:776-869 verbatim. Builds
 * the DOM-independent bulk of _initScene — everything that doesn't
 * need `this` bindings. Returns the T-shape dict; the class method
 * assigns it to `this.T`, then wires up the animation loop, resize
 * observer, and event listeners (all of which need `this`).
 *
 * The mount element MUST be non-null; callers should short-circuit
 * before invoking.
 */

/**
 * @param {typeof THREE} THREE
 * @param {HTMLElement} mount — the canvas host div
 * @param {{ scene: number }} palette
 * @returns {{
 *   scene: THREE.Scene,
 *   cameras: { ortho: THREE.OrthographicCamera, persp: THREE.PerspectiveCamera },
 *   activeCamera: THREE.Camera,
 *   currentTarget: THREE.Vector3,
 *   renderer: THREE.WebGLRenderer,
 *   orbit: THREE.OrbitControls | null,
 * }}
 */
export function initScene(THREE, mount, palette) {
    const W = mount.clientWidth  || 900;
    const H = mount.clientHeight || 560;

    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(palette.scene);

    // D1 — Two camera instances: orthographic for the locked angles
    // (iso/top/front/left/right) and perspective for free-orbit.
    // Swap between them on view change. The vs scalar is bootstrap
    // only; _recomputeViews + _applyOrthoFrustum take over once
    // _buildScene runs.
    const asp = W / H, vs = 9;
    const ortho = new THREE.OrthographicCamera(-vs * asp, vs * asp, vs, -vs, 0.1, 300);
    ortho.position.set(20, 14, 20);
    ortho.lookAt(4, 2.5, 1.5);
    ortho.up.set(0, 1, 0);

    const persp = new THREE.PerspectiveCamera(45, asp, 0.1, 300);
    persp.position.set(20, 14, 20);
    persp.lookAt(4, 2.5, 1.5);
    persp.up.set(0, 1, 0);

    // Renderer — ACES Filmic + sRGB for the canonical Southbrook PBR
    // pipeline (matches cabinet_viewport.esm.js Phase 2.5 spec).
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(W, H);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type    = THREE.PCFSoftShadowMap;
    if (THREE.SRGBColorSpace) {
        renderer.outputColorSpace = THREE.SRGBColorSpace;
    }
    renderer.toneMapping         = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.0;
    mount.appendChild(renderer.domElement);

    // Lighting — 4-light rig (hemi + key/fill/front directional)
    // ported from southbrook_estimating/cabinet_viewport.esm.js.
    const hemi = new THREE.HemisphereLight(0xffffff, 0xd8cfbf, 0.5);
    scene.add(hemi);

    const dirA = new THREE.DirectionalLight(0xffffff, 0.9);
    dirA.position.set(20, 30, 20);
    dirA.castShadow = true;
    dirA.shadow.mapSize.set(2048, 2048);
    Object.assign(dirA.shadow.camera, {
        left: -25, right: 25, top: 25, bottom: -25, near: 0.1, far: 120,
    });
    dirA.shadow.bias = -0.0005;
    scene.add(dirA);

    const dirB = new THREE.DirectionalLight(0xffffff, 0.3);
    dirB.position.set(-10, 12, -8);
    scene.add(dirB);

    const dirFront = new THREE.DirectionalLight(0xffffff, 0.4);
    dirFront.position.set(0, 8, 25);
    scene.add(dirFront);

    // D1 — OrbitControls on the persp camera, disabled until persp
    // view is activated. Defensive: skip if THREE.OrbitControls
    // didn't load (e.g. asset bundle didn't include the UMD shim).
    let orbit = null;
    if (THREE.OrbitControls) {
        orbit = new THREE.OrbitControls(persp, renderer.domElement);
        orbit.enableDamping = true;
        orbit.dampingFactor = 0.08;
        orbit.minDistance   = 4;
        orbit.maxDistance   = 80;
        orbit.maxPolarAngle = Math.PI / 2 - 0.05;   // never under floor
        orbit.enabled       = false;
    }

    return {
        scene,
        cameras: { ortho, persp },
        activeCamera: ortho,
        currentTarget: new THREE.Vector3(4, 2.5, 1.5),
        renderer,
        orbit,
    };
}
