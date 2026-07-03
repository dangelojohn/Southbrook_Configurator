/** @odoo-module **/
/*
 * SPDX-License-Identifier: LGPL-3.0-only
 *
 * Phase 2.5 commit 1 — portal Kitchen Viewport.
 *
 * Minimal Three.js renderer that mounts inside the OWL OrderBuilder
 * portal SPA. Reads the same kitchen-3D payload shape Track 1 produces
 * (sale.order.get_kitchen_3d_payload — multi-cabinet, zone-aware
 * X positioning), via a portal-auth JSON-RPC route
 * (/southbrook/api/order/<id>/kitchen-3d).
 *
 * Scope for this commit:
 *   • Three.js renderer with ACES Filmic + sRGB.
 *   • PerspectiveCamera with OrbitControls.
 *   • Cabinet meshes rendered as BoxGeometry per panel.
 *   • Simple 2-light setup + matte ground plane (Phase 3 polish
 *     adds the full 6-light grid + HDRI + dimension lines).
 *   • Auto-fits camera to the kitchen bounds on first fetch.
 *
 * Out of scope (Phase 2.5 commit 2+):
 *   • Solid↔blueline toggle + dimension lines.
 *   • Per-line hover/click → drawer integration.
 *   • Material variants (door / shelf / back distinct).
 *   • Reactive refetch on autosave (today only fetches on mount).
 */
import {
    Component,
    onMounted,
    onWillUnmount,
    onWillUpdateProps,
    useRef,
    useState,
    xml,
} from "@odoo/owl";
// 2026-06-22: Tier-1 cabinet GLB loader (see cabinet_glb_loader.esm.js).
// When a designer drops a `.glb` into static/lib/cabinets/ and adds an
// entry to cabinets.json, the corresponding cabinet renders as the
// vendor mesh INSTEAD of the per-panel BoxGeometry below. With an
// empty manifest (initial state) or a missing GLTFLoader vendor lib,
// every findGlbUrlFor() returns null and we render boxes as before.
import { GlbRegistry } from "@southbrook_estimating/js/cabinet_glb_loader.esm";

async function rpcCall(url, params = {}) {
    const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            jsonrpc: "2.0",
            method: "call",
            params: params,
            id: Math.floor(Math.random() * 1e9),
        }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const j = await res.json();
    if (j.error) {
        throw new Error(j.error.data?.message || j.error.message || "RPC error");
    }
    return j.result;
}

export class KitchenViewport extends Component {
    static template = xml`
        <div class="o_owl_kitchen">
            <div class="o_owl_kitchen_toolbar">
                <span class="o_owl_kitchen_title">3D Kitchen Preview</span>
                <button class="btn btn-sm o_owl_kitchen_mode_btn"
                        t-on-click="onToggleMode"
                        t-att-disabled="!state.threeLoaded"
                        t-att-title="state.mode === 'solid'
                                     ? 'Switch to dimensioned blueline view'
                                     : 'Switch to solid rendered view'">
                    <!-- Label is the TARGET mode (what you'll switch TO),
                         not the current one — the title spells that out. -->
                    <t t-if="state.mode === 'solid'">Blueline</t>
                    <t t-else="">Solid</t>
                </button>
                <span class="o_owl_kitchen_status" t-if="state.loading">
                    Loading…
                </span>
                <span class="o_owl_kitchen_status text-danger"
                      t-elif="state.error" t-esc="state.error"/>
                <span class="o_owl_kitchen_hover"
                      t-elif="state.hoveredLineInfo"
                      t-esc="state.hoveredLineInfo"/>
                <span class="o_owl_kitchen_meta" t-elif="state.meta">
                    <t t-esc="state.meta"/>
                </span>
            </div>
            <div class="o_owl_kitchen_stage">
                <canvas t-ref="canvas"
                        class="o_owl_kitchen_canvas"
                        t-att-class="{ 'd-none': !state.threeLoaded }"/>
                <div t-if="!state.threeLoaded"
                     class="o_owl_kitchen_placeholder">
                    Three.js bundle not loaded. The asset bundle should
                    include
                    <code>southbrook_estimating/static/lib/three/three.min.js</code>
                    + OrbitControls.js. If this card persists after a
                    hard refresh, check the manifest assets entry.
                </div>
            </div>
        </div>
    `;
    static props = {
        orderId: { type: String, optional: true },
        // P25C3 — invoked when the user clicks a cabinet in the
        // viewport. Parent OrderBuilder switches to the Lines tab
        // and selects the line (which opens the ConfigDrawer).
        onLineSelected: { type: Function, optional: true },
        // P25C4 — parent's payload_version counter. Bumped by
        // OrderBuilder._loadOrder after every successful fetch. The
        // viewport watches this number via onWillUpdateProps; a
        // change triggers a refetch so the kitchen stays in sync
        // with the rest of the SPA after autosaves / state changes.
        payloadVersion: { type: Number, optional: true },
        // 2026-07-03 — reverse selection sync. The parent OrderBuilder's
        // state.ui.selected_line_id (a line id Number, or null). When it
        // changes — e.g. the user clicks a row in the Lines tab — the
        // matching cabinet gets a persistent amber outline so switching
        // to the 3D tab shows which line is selected. Loosely typed
        // (Number | null); left untyped-strict to tolerate null cleanly.
        selectedLineId: { optional: true },
    };

    setup() {
        this.canvasRef = useRef("canvas");
        this.state = useState({
            loading: false,
            error: null,
            threeLoaded: !!window.THREE,
            meta: null,
            // P25C2 — solid↔blueline toggle (back-port of Track 1 T1C5).
            mode: "solid",
            // P25C3 — hover state for tooltip + cabinet highlight
            // (back-port of Track 1 T1C8).
            hoveredLineId: null,
            hoveredLineInfo: null,
        });

        // Three.js handles — populated in _init.
        this._THREE = null;
        this._renderer = null;
        this._scene = null;
        this._camera = null;
        this._controls = null;
        this._cabinetGroup = null;
        this._materials = {};
        this._frameId = null;
        this._resizeObserver = null;
        // P25C2 — dimension overlay group (lifted from T1C5).
        this._dimensionGroup = null;
        this._dimensionMaterial = null;
        this._spriteResources = [];
        // P25C3 — hover + click (back-port of T1C8 + T1C9).
        // _linesIndex caches payload.metadata.lines (keyed by string
        // line id matching the L{id}_ panel name prefix).
        this._linesIndex = {};
        this._hoveredLineId = null;
        // 2026-07-03 — persistent selection outline (reverse sync with the
        // parent's selected_line_id). Distinct from _hoveredLineId so hover
        // and selection can coexist on different cabinets.
        this._selectedLineId = null;
        this._raycaster = null;
        this._mouse = null;
        this._mouseDownAt = null;
        this._MAX_CLICK_DELTA_PX = 5;
        // P25C4 — track the most recent payloadVersion we have
        // honoured. Onmount: starts as whatever the parent passed.
        // onWillUpdateProps: compares against incoming; refetch on
        // change.
        this._lastPayloadVersion = this.props.payloadVersion || 0;

        onMounted(() => this._init());
        onWillUpdateProps((nextProps) => {
            const next = nextProps.payloadVersion || 0;
            const versionChanged = next !== this._lastPayloadVersion;
            if (versionChanged) {
                this._lastPayloadVersion = next;
                // Re-fetch only when the Three.js scene is built;
                // otherwise the initial _init's fetch will pick up
                // the latest version on its own.
                if (this._renderer && this._cabinetGroup) {
                    queueMicrotask(() => this._fetchAndBuild());
                }
            }
            // 2026-07-03 — reverse selection sync. Apply the outline in
            // place when only the selection changed. When the payload
            // version ALSO changed we skip it here: the pending refetch
            // rebuilds the scene and _build re-applies selection from the
            // current prop, so applying now would just be undone.
            const nextSel = nextProps.selectedLineId ?? null;
            if (!versionChanged && nextSel !== this._selectedLineId
                && this._cabinetGroup) {
                this._applySelectionHighlight(nextSel);
            }
        });
        onWillUnmount(() => this._dispose());
    }

    async _init() {
        const THREE = window.THREE;
        if (!THREE) {
            this.state.threeLoaded = false;
            return;
        }
        this._THREE = THREE;
        const canvas = this.canvasRef.el;
        if (!canvas) return;

        this._renderer = new THREE.WebGLRenderer({
            canvas,
            antialias: true,
            alpha: false,
        });
        if (THREE.SRGBColorSpace) {
            this._renderer.outputColorSpace = THREE.SRGBColorSpace;
        }
        this._renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this._renderer.toneMappingExposure = 1.0;
        this._renderer.setPixelRatio(window.devicePixelRatio || 1);
        this._renderer.shadowMap.enabled = true;
        this._renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        this._fitRendererToCanvas();

        this._scene = new THREE.Scene();
        this._scene.background = new THREE.Color(0xfbf7ef);  // --sb-paper

        this._camera = new THREE.PerspectiveCamera(35, 1, 10, 50000);
        this._camera.position.set(3000, 1800, 4000);

        // Lights — 1 hemi + 1 key directional + 1 fill (T1C4 pattern).
        // These render the FIRST FRAME — phase 3 sprint A2 upgrades to
        // a PBR environment map below, but the env-map prefilter takes
        // a few hundred ms and we want pixels on screen immediately.
        const hemi = new THREE.HemisphereLight(0xffffff, 0xd8cfbf, 0.5);
        this._scene.add(hemi);
        const dirA = new THREE.DirectionalLight(0xffffff, 0.9);
        dirA.position.set(1500, 2500, 1200);
        dirA.castShadow = true;
        dirA.shadow.mapSize.set(2048, 2048);
        dirA.shadow.camera.near = 100;
        dirA.shadow.camera.far = 10000;
        dirA.shadow.camera.left = -5000;
        dirA.shadow.camera.right = 5000;
        dirA.shadow.camera.top = 4000;
        dirA.shadow.camera.bottom = -500;
        dirA.shadow.bias = -0.0005;
        this._scene.add(dirA);
        const dirB = new THREE.DirectionalLight(0xffffff, 0.3);
        dirB.position.set(-1000, 1000, 1500);
        this._scene.add(dirB);

        // Phase 3 Sprint A2 — procedural studio environment map.
        // Builds a CanvasTexture with a warm-overhead → cool-floor
        // vertical gradient, runs it through PMREMGenerator to produce
        // a prefiltered mip-chain, and assigns the result as
        // scene.environment. Adds soft PBR reflections on the cabinet
        // material's metalness/roughness without needing an HDR file
        // (smaller bundle, no external dependency, fully air-gapped).
        // Lazy-deferred so the first paint uses the 3-light rig above.
        requestAnimationFrame(() => this._installStudioEnvironment());

        if (THREE.OrbitControls) {
            this._controls = new THREE.OrbitControls(this._camera, canvas);
            this._controls.enableDamping = true;
            this._controls.dampingFactor = 0.1;
            this._controls.target.set(0, 600, 0);
        }

        this._cabinetGroup = new THREE.Group();
        this._scene.add(this._cabinetGroup);

        // P25C2 — dimension overlay group. Lives outside cabinetGroup
        // so the blueline material swap doesn't touch it.
        this._dimensionGroup = new THREE.Group();
        this._dimensionGroup.visible = this.state.mode === "blueline";
        this._scene.add(this._dimensionGroup);

        // Materials — simple palette. Phase 3 polish adds per-panel
        // distinctions (back / shelf / hardware finish).
        this._materials = {
            carcass: new THREE.MeshStandardMaterial({
                color: 0xc89e85, roughness: 0.85, metalness: 0.0,
            }),
            door: new THREE.MeshStandardMaterial({
                color: 0x6b3f2a, roughness: 0.7, metalness: 0.05,
            }),
            // Per-finish door materials. The backend payload emits
            // material names like "door_white" / "door_maple_stain"
            // when product_config_session resolves the customer's
            // Finish attribute. Unknown finishes fall back to the
            // generic `door` material above. Added 2026-06-25.
            door_white: new THREE.MeshStandardMaterial({
                color: 0xf0ebe3, roughness: 0.45, metalness: 0.05,
            }),
            // The 3 stained finishes carry a procedural wood-grain
            // CanvasTexture in `map` + a base color tint. Texture
            // builder is _buildWoodGrainTexture below. White stays
            // map-less — it's paint, not wood.
            door_maple_stain: new THREE.MeshStandardMaterial({
                color: 0xc89e76,
                ...this._buildWoodMaterialMaps(0xc89e76, 0x8c6a48),
                roughness: 0.70, metalness: 0.05,
            }),
            door_cherry_stain: new THREE.MeshStandardMaterial({
                color: 0x6b2e1a,
                ...this._buildWoodMaterialMaps(0x6b2e1a, 0x401a0d),
                roughness: 0.65, metalness: 0.05,
            }),
            door_walnut_stain: new THREE.MeshStandardMaterial({
                color: 0x3d2817,
                ...this._buildWoodMaterialMaps(0x3d2817, 0x1f130a),
                roughness: 0.70, metalness: 0.05,
            }),
            back: new THREE.MeshStandardMaterial({
                color: 0xa68872, roughness: 0.9, metalness: 0.0,
            }),
            shelf: new THREE.MeshStandardMaterial({
                color: 0xc89e85, roughness: 0.85, metalness: 0.0,
            }),
            toekick: new THREE.MeshStandardMaterial({
                color: 0x2a2520, roughness: 0.95, metalness: 0.0,
            }),
            worktop: new THREE.MeshStandardMaterial({
                color: 0xb5b0a8, roughness: 0.4, metalness: 0.05,
            }),
            // Drawer slides + other metal hardware bodies. Gunmetal /
            // zinc — added 2026-06-25 alongside the base-feet + drawer-
            // rails geometry. Feet reuse `toekick` (matte black plastic).
            hardware: new THREE.MeshStandardMaterial({
                color: 0x8a8a8e, roughness: 0.35, metalness: 0.85,
            }),
            // P25C2 — blueline wireframe overlay.
            blueline: new THREE.MeshBasicMaterial({
                color: 0x2b4f6b, wireframe: true,
            }),
            // P25C3 — emissive hover highlight (now deprecated by
            // A3 inverted-hull outline below, but kept as a fallback
            // for older browsers where the BackSide outline glitches).
            highlight: new THREE.MeshStandardMaterial({
                color: 0xc89e85,
                emissive: 0x2b4f6b,
                emissiveIntensity: 0.4,
                roughness: 0.5,
                metalness: 0.1,
            }),
            // Phase 3 Sprint A3 — outline material for the inverted-
            // hull hover highlight. Renders the BackSide of a slightly
            // larger shell over the hovered cabinet so only the silhouette
            // shows through. Pure Three.js core; no EffectComposer /
            // OutlinePass example module required.
            outline: new THREE.MeshBasicMaterial({
                color: 0x2b4f6b,          // --sb-sky
                side: THREE.BackSide,
                depthWrite: false,
                transparent: false,
            }),
            // 2026-07-03 — persistent SELECTION outline (reverse sync with
            // the parent's selected_line_id). Same inverted-hull technique
            // as `outline`, in amber so a selected cabinet is visually
            // distinct from the sky-blue hover highlight (both can show at
            // once on different cabinets).
            selected: new THREE.MeshBasicMaterial({
                color: 0xd4a24e,          // --sb-amber
                side: THREE.BackSide,
                depthWrite: false,
                transparent: false,
            }),
        };

        // Floor.
        const floorGeom = new THREE.PlaneGeometry(40000, 40000);
        const floorMat = new THREE.MeshStandardMaterial({
            color: 0xe8dfd2,
            roughness: 0.95,
            metalness: 0.0,
        });
        const floor = new THREE.Mesh(floorGeom, floorMat);
        floor.rotation.x = -Math.PI / 2;
        floor.position.y = 0;
        floor.receiveShadow = true;
        this._scene.add(floor);
        this._floor = floor;
        this._floorMat = floorMat;
        this._floorGeom = floorGeom;

        if (typeof ResizeObserver === "function") {
            this._resizeObserver = new ResizeObserver(() => this._fitRendererToCanvas());
            this._resizeObserver.observe(canvas);
        }

        // P25C3 — raycaster + canvas mouse listeners.
        this._raycaster = new THREE.Raycaster();
        this._mouse = new THREE.Vector2();
        canvas.addEventListener("mousemove", (e) => this._onMouseMove(e));
        canvas.addEventListener("mouseleave", () => this._setHoveredLine(null));
        canvas.addEventListener("mousedown", (e) => this._onMouseDown(e));
        canvas.addEventListener("mouseup", (e) => this._onMouseUp(e));

        await this._fetchAndBuild();
        this._animate();
    }

    _animate() {
        if (!this._renderer) return;
        this._frameId = requestAnimationFrame(() => this._animate());
        if (this._controls) this._controls.update();
        this._renderer.render(this._scene, this._camera);
    }

    /**
     * Phase 3 Sprint A2 — build a small studio environment texture
     * procedurally, prefilter it via PMREMGenerator, and assign as
     * scene.environment.
     *
     * Why procedural instead of an HDR file:
     *   - air-gapped (no Polyhaven/HDRihaven/jsDelivr dependency)
     *   - smaller (the gradient is ~2 KB encoded vs ~512 KB-2 MB HDR)
     *   - reproducible — the gradient is part of the source code
     *
     * The resulting envmap is a soft vertical gradient — warm
     * overhead, cool shadow at floor level. Good for matte cabinet
     * surfaces; not appropriate for shiny metalwork. (Hardware finish
     * pass in Sprint B will revisit.)
     */
    /**
     * Phase 3 Sprint B (2026-06-25) — procedural wood-grain texture.
     *
     * Returns a Three.js CanvasTexture seeded from `baseHex`/`grainHex`
     * suitable for use as `map` on a MeshStandardMaterial. The texture
     * is a vertical grain pattern with 12 broad bands and ~60 fine
     * striations of `grainHex` painted at varying opacity over a
     * `baseHex` fill. Deterministic seed → same input pair always
     * produces the same pattern (no per-frame jitter).
     *
     * Why procedural instead of bundled JPGs:
     *   - air-gapped (no asset CDN dependency)
     *   - no licensing concerns
     *   - tiny code, no static-file weight per finish
     *   - matches the precedent set by _installStudioEnvironment
     *
     * Texture is 256x512 (vertical grain orientation), repeat
     * (2, 1.5) so a 600mm door doesn't show one stretched pattern.
     */
    _buildWoodGrainTexture(baseHex, grainHex) {
        // Legacy single-map helper — kept for callers that don't
        // want the normal map. New door materials use
        // _buildWoodMaterialMaps below.
        return this._buildWoodMaterialMaps(baseHex, grainHex).map;
    }

    /**
     * Phase 3.5 (2026-06-26) — procedural wood grain with normal map.
     *
     * Returns { map, normalMap } for a Three.js MeshStandardMaterial.
     * The albedo map carries the color + grain. The normal map gives
     * tactile depth so the studio rig's 6-light setup catches every
     * pore + ring instead of rendering it as a flat decal.
     *
     * Grain pattern:
     *   - 4-6 organic annular rings (vertical sine-distorted curves)
     *   - 80 fine grain striations with ±2px x-jitter
     *   - ~180 pore speckles (1-2px dark dots, simulate wood pores)
     *   - 1-2 small knot blemishes per texture
     *
     * Normal map is derived from the albedo: brighter areas (base
     * color) → flat normal (128, 128, 255); darker areas (grain) →
     * subtle indentation. Computed as grayscale gradient sampled
     * from a slightly-blurred copy of the albedo.
     *
     * Resolution: 512×1024 (2x prior). Anisotropic filter at 8x.
     */
    _buildWoodMaterialMaps(baseHex, grainHex) {
        const THREE = this._THREE;
        if (!THREE) return {};
        const w = 512, h = 1024;
        const albedo = this._drawWoodAlbedoCanvas(w, h, baseHex, grainHex);
        const normal = this._deriveNormalMapCanvas(albedo, w, h);

        const map = new THREE.CanvasTexture(albedo);
        if (THREE.SRGBColorSpace) map.colorSpace = THREE.SRGBColorSpace;
        map.wrapS = THREE.RepeatWrapping;
        map.wrapT = THREE.RepeatWrapping;
        map.repeat.set(1.5, 1.0);
        map.anisotropy = 8;

        const normalMap = new THREE.CanvasTexture(normal);
        // Normal maps are LINEAR data, NOT sRGB. Setting colorSpace
        // to sRGB on a normal map double-applies gamma + breaks the
        // shader. Three.js defaults to NoColorSpace for non-color
        // data, which is correct.
        normalMap.wrapS = THREE.RepeatWrapping;
        normalMap.wrapT = THREE.RepeatWrapping;
        normalMap.repeat.set(1.5, 1.0);
        normalMap.anisotropy = 8;

        return { map, normalMap };
    }

    /**
     * Draw the albedo (color) canvas. Organic wood-grain look using
     * deterministic PRNG so the same finish always renders identically.
     */
    _drawWoodAlbedoCanvas(w, h, baseHex, grainHex) {
        const canvas = document.createElement("canvas");
        canvas.width = w; canvas.height = h;
        const ctx = canvas.getContext("2d");
        const toHex = (n) => "#" + n.toString(16).padStart(6, "0");
        const baseStr = toHex(baseHex);
        const grainStr = toHex(grainHex);
        // Slightly-darker shade for shadows under grain peaks.
        const shadowHex = (
            ((((baseHex >> 16) & 0xff) * 0.85) << 16) |
            ((((baseHex >> 8) & 0xff) * 0.85) << 8) |
            (((baseHex & 0xff) * 0.85))
        ) | 0;
        const shadowStr = toHex(shadowHex);
        // Base fill.
        ctx.fillStyle = baseStr;
        ctx.fillRect(0, 0, w, h);
        // Deterministic PRNG seeded from baseHex.
        let seed = (baseHex ^ 0x9e3779b9) >>> 0;
        const prng = () => {
            seed = (seed * 1103515245 + 12345) >>> 0;
            return (seed & 0x7fffffff) / 0x7fffffff;
        };
        // ---- Annular rings: 5 broad sine-distorted vertical bands ----
        // These read as growth rings on a quarter-sawn cabinet door.
        ctx.strokeStyle = grainStr;
        for (let i = 0; i < 5; i++) {
            const baseX = prng() * w;
            const ringW = 18 + prng() * 30;
            const phase = prng() * Math.PI * 2;
            const amp = 6 + prng() * 14;
            const period = 200 + prng() * 200;
            ctx.globalAlpha = 0.14 + prng() * 0.10;
            ctx.lineWidth = ringW;
            ctx.beginPath();
            ctx.moveTo(baseX, 0);
            for (let y = 0; y <= h; y += 4) {
                const x = baseX + amp * Math.sin((y / period) * Math.PI * 2 + phase);
                ctx.lineTo(x, y);
            }
            ctx.stroke();
        }
        // ---- Fine grain striations: 80 thin lines with x-jitter ----
        ctx.strokeStyle = grainStr;
        for (let i = 0; i < 80; i++) {
            const x = prng() * w;
            const lw = 0.4 + prng() * 1.2;
            ctx.globalAlpha = 0.06 + prng() * 0.18;
            ctx.lineWidth = lw;
            ctx.beginPath();
            ctx.moveTo(x, 0);
            const segs = 12;
            for (let s = 1; s <= segs; s++) {
                const sy = (s / segs) * h;
                const sx = x + (prng() - 0.5) * 5;
                ctx.lineTo(sx, sy);
            }
            ctx.stroke();
        }
        // ---- Pore speckles: ~180 small dark dots ----
        ctx.fillStyle = grainStr;
        for (let i = 0; i < 180; i++) {
            const px = prng() * w;
            const py = prng() * h;
            const pr = 0.5 + prng() * 1.5;
            ctx.globalAlpha = 0.18 + prng() * 0.20;
            ctx.beginPath();
            ctx.arc(px, py, pr, 0, Math.PI * 2);
            ctx.fill();
        }
        // ---- Knot blemishes: 1-2 small dark elliptical knots ----
        const knotCount = 1 + Math.floor(prng() * 2);
        for (let i = 0; i < knotCount; i++) {
            const kx = prng() * w;
            const ky = (0.2 + prng() * 0.6) * h;
            const krx = 4 + prng() * 8;
            const kry = 6 + prng() * 12;
            const grad = ctx.createRadialGradient(kx, ky, 0, kx, ky, kry);
            grad.addColorStop(0.0, shadowStr);
            grad.addColorStop(0.6, grainStr);
            grad.addColorStop(1.0, baseStr);
            ctx.fillStyle = grad;
            ctx.globalAlpha = 0.45;
            ctx.beginPath();
            ctx.ellipse(kx, ky, krx, kry, prng() * Math.PI, 0, Math.PI * 2);
            ctx.fill();
        }
        ctx.globalAlpha = 1;
        return canvas;
    }

    /**
     * Derive a tangent-space normal map from the albedo canvas via
     * a Sobel-like edge gradient on the luminance channel. Brighter
     * pixels = surface peaks; darker pixels = pores/rings. The shader
     * uses this to perturb lighting normals, giving tactile depth.
     */
    _deriveNormalMapCanvas(albedoCanvas, w, h) {
        const src = albedoCanvas.getContext("2d").getImageData(0, 0, w, h);
        const out = document.createElement("canvas");
        out.width = w; out.height = h;
        const dst = out.getContext("2d").createImageData(w, h);
        const lum = (i) => 0.299 * src.data[i] + 0.587 * src.data[i + 1] + 0.114 * src.data[i + 2];
        const strength = 2.5;  // Normal-map intensity multiplier
        for (let y = 0; y < h; y++) {
            for (let x = 0; x < w; x++) {
                const xl = (x === 0) ? 0 : x - 1;
                const xr = (x === w - 1) ? w - 1 : x + 1;
                const yu = (y === 0) ? 0 : y - 1;
                const yd = (y === h - 1) ? h - 1 : y + 1;
                const dx = lum((y * w + xr) * 4) - lum((y * w + xl) * 4);
                const dy = lum((yd * w + x) * 4) - lum((yu * w + x) * 4);
                const i = (y * w + x) * 4;
                // Pack the gradient as a tangent-space normal vector.
                // R = +X (right of center 128), G = +Y, B = +Z (always up).
                dst.data[i] = Math.max(0, Math.min(255, 128 + dx * strength));
                dst.data[i + 1] = Math.max(0, Math.min(255, 128 - dy * strength));
                dst.data[i + 2] = 255;
                dst.data[i + 3] = 255;
            }
        }
        out.getContext("2d").putImageData(dst, 0, 0);
        return out;
    }

    _installStudioEnvironment() {
        if (!this._renderer || !this._scene) return;
        try {
            // 1024x512 equirectangular canvas — small but enough
            // mip levels for the PMREM prefilter to be smooth.
            const w = 1024, h = 512;
            const canvas = document.createElement("canvas");
            canvas.width = w; canvas.height = h;
            const ctx = canvas.getContext("2d");
            // Vertical gradient: top = warm key, mid = neutral,
            // bottom = cool floor bounce. Hex codes match the
            // 3-light rig above so the PBR pass blends cleanly
            // with the existing direct-lit look.
            const grad = ctx.createLinearGradient(0, 0, 0, h);
            grad.addColorStop(0.00, "#fff5e8");  // overhead warm
            grad.addColorStop(0.40, "#e8e4dc");  // soft mid
            grad.addColorStop(0.70, "#c9c4ba");  // shadow side
            grad.addColorStop(1.00, "#8a8680");  // floor
            ctx.fillStyle = grad;
            ctx.fillRect(0, 0, w, h);
            const tex = new THREE.CanvasTexture(canvas);
            tex.mapping = THREE.EquirectangularReflectionMapping;
            if (THREE.SRGBColorSpace) {
                tex.colorSpace = THREE.SRGBColorSpace;
            }
            const pmrem = new THREE.PMREMGenerator(this._renderer);
            const envRT = pmrem.fromEquirectangular(tex);
            this._scene.environment = envRT.texture;
            // Don't visually replace the existing bg; just light the
            // PBR materials with the env. The off-white scene bg
            // stays the same.
            tex.dispose();
            pmrem.dispose();
        } catch (exc) {
            // Non-fatal: if env install fails for any reason
            // (old browser, WebGL2 missing) the 3-light rig still
            // renders the scene fine. Console-warn for visibility
            // but don't break the configurator.
            console.warn("[KitchenViewport] env install skipped:", exc);
        }
    }

    _fitRendererToCanvas() {
        const canvas = this.canvasRef.el;
        if (!canvas || !this._renderer) return;
        const w = canvas.clientWidth || 800;
        const h = canvas.clientHeight || 500;
        this._renderer.setSize(w, h, false);
        if (this._camera) {
            this._camera.aspect = w / h;
            this._camera.updateProjectionMatrix();
        }
    }

    async _fetchAndBuild() {
        if (!this.props.orderId) {
            this.state.meta = "No order selected.";
            return;
        }
        this.state.loading = true;
        this.state.error = null;
        try {
            const payload = await rpcCall(
                `/southbrook/api/order/${encodeURIComponent(this.props.orderId)}/kitchen-3d`,
                {},
            );
            if (payload && payload.error) {
                this.state.error = payload.error;
                return;
            }
            this._build(payload);
            const m = payload.metadata || {};
            this.state.meta = (
                `${m.line_count || 0} cabinets · ` +
                `${Math.round((m.kitchen_width_mm || 0) / 10) / 100}m wide`
            );
        } catch (e) {
            this.state.error = e?.message || String(e);
        } finally {
            this.state.loading = false;
        }
    }

    _build(payload) {
        const THREE = this._THREE;
        if (!THREE || !this._cabinetGroup) return;

        // Clear previous.
        while (this._cabinetGroup.children.length) {
            const child = this._cabinetGroup.children[0];
            this._cabinetGroup.remove(child);
            if (child.geometry) child.geometry.dispose();
        }
        // Track per-line bounding boxes as we go so the async GLB pass
        // below can position vendor models without re-walking panels.
        // {<lineId>: {minX, maxX, minY, maxY, minZ, maxZ}}
        const lineBounds = {};

        if (!payload || !Array.isArray(payload.panels)) return;

        // P25C3 — refresh line index + clear stale hover state.
        this._linesIndex = (payload.metadata && payload.metadata.lines) || {};
        this._hoveredLineId = null;
        this.state.hoveredLineId = null;
        this.state.hoveredLineInfo = null;

        const blueline = this.state.mode === "blueline";

        for (const p of payload.panels) {
            const d = p.dims;
            if (!d || d.width <= 0 || d.height <= 0 || d.depth <= 0) continue;
            const geom = new THREE.BoxGeometry(d.width, d.height, d.depth);
            const matName = blueline ? "blueline" : (p.material || "carcass");
            const mat = this._materials[matName] || this._materials.carcass;
            const mesh = new THREE.Mesh(geom, mat);
            mesh.position.set(p.pos.x, p.pos.y, p.pos.z);
            if (p.rot) {
                mesh.rotation.set(p.rot.x || 0, p.rot.y || 0, p.rot.z || 0);
            }
            mesh.castShadow = !blueline;
            mesh.receiveShadow = !blueline;
            // P25C3 — tag mesh with line id (back-port of T1C8). The
            // get_kitchen_3d_payload backend prefixes each panel name
            // with L{id}_ — so /^L(\d+)_/ pulls the id reliably.
            const m = (p.name || "").match(/^L(\d+)_/);
            if (m) {
                mesh.userData.lineId = m[1];
                // Accumulate the line's axis-aligned bounding box from
                // panel centres + half-extents. Used by the Tier-1 GLB
                // pass to place the vendor mesh at the cabinet's
                // bottom-front-left corner (matches the asset-
                // authoring origin in static/lib/cabinets/README.md).
                const id = m[1];
                const hx = d.width / 2;
                const hy = d.height / 2;
                const hz = d.depth / 2;
                const b = lineBounds[id] || (lineBounds[id] = {
                    minX:  Infinity, maxX: -Infinity,
                    minY:  Infinity, maxY: -Infinity,
                    minZ:  Infinity, maxZ: -Infinity,
                });
                if (p.pos.x - hx < b.minX) b.minX = p.pos.x - hx;
                if (p.pos.x + hx > b.maxX) b.maxX = p.pos.x + hx;
                if (p.pos.y - hy < b.minY) b.minY = p.pos.y - hy;
                if (p.pos.y + hy > b.maxY) b.maxY = p.pos.y + hy;
                if (p.pos.z - hz < b.minZ) b.minZ = p.pos.z - hz;
                if (p.pos.z + hz > b.maxZ) b.maxZ = p.pos.z + hz;
            }
            this._cabinetGroup.add(mesh);
        }

        // 2026-06-22 — Tier-1 cabinet GLB pass.
        //
        // The per-panel BoxGeometry loop above is the always-on
        // fallback. AFTER it runs, kick off an async pass that asks
        // GlbRegistry for a vendor GLB per line and — for any line
        // that has one — removes the per-panel boxes for that line
        // and adds the GLB scene in their place. With an empty
        // cabinets.json (initial state), or a missing GLTFLoader,
        // every lookup returns null and this is a silent no-op.
        //
        // Build-sequence guard prevents an in-flight load from
        // attaching to a now-cleared scene (rapid prop changes / a
        // new _build call). Each _build bumps the counter; the async
        // attach checks it before mutating _cabinetGroup.
        this._buildSeq = (this._buildSeq || 0) + 1;
        this._attachTier1GlbsAsync(this._buildSeq, lineBounds);

        // P25C2 — rebuild dimension chains for the new bounds.
        this._buildDimensionLines(payload);

        // Camera fit.
        if (payload.camera) {
            this._camera.position.set(...payload.camera.position);
            const tgt = payload.camera.target;
            if (this._controls) {
                this._controls.target.set(...tgt);
                this._controls.update();
            } else {
                this._camera.lookAt(new THREE.Vector3(...tgt));
            }
        }

        // 2026-07-03 — re-apply the persistent selection outline to the
        // freshly-built meshes (the parent's current selection). _build
        // cleared the old shells along with their host meshes.
        this._selectedLineId = null;   // shells are gone; force re-add
        this._applySelectionHighlight(this.props.selectedLineId ?? null);
    }

    // ------------------------------------------------------------------
    // 2026-06-22 — Tier-1 cabinet GLB attach pass.
    //
    // Fires AFTER _build's per-panel BoxGeometry loop. For each line
    // with a registered GLB, removes that line's per-panel meshes and
    // places the vendor model at the cabinet's bottom-front-left
    // corner (computed in _build via lineBounds). Lines with no
    // registered GLB keep their box meshes.
    //
    // Build-sequence guard: if another _build call has fired during
    // our await, mySeq !== this._buildSeq and we drop the work — the
    // newer _build is mid-flight against a freshly-cleared scene.
    //
    // Mode swap: when the user toggles blueline mode, _build is NOT
    // re-run (onToggleMode just swaps materials in place). Tier-1 GLBs
    // therefore stay solid even in blueline mode for now — a real
    // shader swap is a Phase-3 polish item, not part of this scaffold.
    // ------------------------------------------------------------------
    async _attachTier1GlbsAsync(mySeq, lineBounds) {
        const THREE = this._THREE;
        if (!THREE || !this._cabinetGroup) return;
        if (!lineBounds || !Object.keys(lineBounds).length) return;
        await GlbRegistry.load();
        if (mySeq !== this._buildSeq || !this._cabinetGroup) return;

        for (const lineId of Object.keys(lineBounds)) {
            const lineInfo = this._linesIndex[lineId];
            if (!lineInfo || !lineInfo.sku) continue;
            const url = GlbRegistry.findGlbUrlFor(lineInfo.sku);
            if (!url) continue;
            const scene = await GlbRegistry.loadCabinet(THREE, url);
            // Re-check the seq after every await — a newer _build may
            // have invalidated our scene.
            if (mySeq !== this._buildSeq || !this._cabinetGroup) return;
            if (!scene) continue;

            // Remove the per-panel box meshes for this line. Iterate a
            // shallow copy because removing from the underlying
            // children array mid-loop would skip elements.
            const stale = this._cabinetGroup.children.filter(
                (c) => c.userData && c.userData.lineId === lineId,
            );
            for (const c of stale) {
                this._cabinetGroup.remove(c);
                if (c.geometry) c.geometry.dispose();
            }

            // Place the GLB at the cabinet's bottom-front-left corner.
            // SketchUp-authored origin convention is documented in
            // static/lib/cabinets/README.md: X = width, Y = height,
            // Z = depth toward the viewer (+Z front). The +X span
            // is minX..maxX, +Y is 0..maxY (floor), +Z is minZ..maxZ.
            const b = lineBounds[lineId];
            scene.position.set(b.minX, b.minY, b.maxZ);
            scene.userData.lineId = lineId;
            // Tag every child mesh too so the existing hover/raycast
            // path (which reads mesh.userData.lineId) keeps working.
            scene.traverse((obj) => {
                if (obj.isMesh) {
                    obj.userData.lineId = lineId;
                    obj.castShadow = true;
                    obj.receiveShadow = true;
                }
            });
            this._cabinetGroup.add(scene);
        }

        // 2026-07-03 — GLB swaps removed the box meshes (and their
        // selection shells) for the swapped lines; re-apply the selection
        // outline to whatever meshes now represent the selected line.
        this._selectedLineId = null;
        this._applySelectionHighlight(this.props.selectedLineId ?? null);
    }

    // ------------------------------------------------------------------
    // P25C2 — blueline mode toggle + auto-dim lines.
    //
    // Lift of Track 1 T1C5 logic adapted for the kitchen-scale viewport
    // (multi-cabinet, payload.bounds spans the whole kitchen). Same
    // sky-on-paper visual language, same _formatMm 0.25" rounding.
    // ------------------------------------------------------------------

    onToggleMode() {
        // P25C3 — clear any hover state first so the highlight
        // material doesn't get cached as the "original" during the
        // blueline swap.
        this._setHoveredLine(null);
        // 2026-07-03 — likewise drop the persistent selection shell before
        // the material swap so it isn't captured as a mesh's _origMaterial;
        // re-applied (as a no-op in blueline) after the swap below.
        const keepSelection = this._selectedLineId;
        this._clearSelectionShells();

        this.state.mode = this.state.mode === "solid" ? "blueline" : "solid";
        if (!this._cabinetGroup) {
            this._selectedLineId = keepSelection;
            return;
        }
        const blueline = this._materials.blueline;
        this._cabinetGroup.traverse((obj) => {
            if (!obj.isMesh) return;
            if (this.state.mode === "blueline") {
                obj.userData._origMaterial = obj.material;
                obj.material = blueline;
                obj.castShadow = false;
                obj.receiveShadow = false;
            } else if (obj.userData._origMaterial) {
                obj.material = obj.userData._origMaterial;
                obj.userData._origMaterial = null;
                obj.castShadow = true;
                obj.receiveShadow = true;
            }
        });
        if (this._dimensionGroup) {
            this._dimensionGroup.visible = this.state.mode === "blueline";
        }
        // 2026-07-03 — re-apply the selection outline. No-op in blueline
        // mode (where _applySelectionHighlight early-returns), restored on
        // the swap back to solid.
        this._selectedLineId = null;
        this._applySelectionHighlight(keepSelection);
    }

    // ------------------------------------------------------------------
    // P25C3 — hover + click (back-port of Track 1 T1C8 + T1C9).
    //
    // Hover: raycast cabinetGroup, find topmost mesh, look up lineId
    // from mesh.userData. Swap to highlight material, populate toolbar
    // tooltip from _linesIndex.
    //
    // Click: mousedown/mouseup pair distinguishes a click from an
    // orbit drag. On a clean click, invoke props.onLineSelected so
    // the parent OrderBuilder switches to the Lines tab and selects
    // the line (which opens the ConfigDrawer).
    //
    // Both hover + click DISABLED in blueline mode so they don't
    // fight the dimension-overlay material swap.
    // ------------------------------------------------------------------

    _onMouseMove(event) {
        if (this.state.mode === "blueline") return;
        const canvas = this.canvasRef.el;
        if (!canvas || !this._raycaster || !this._cabinetGroup || !this._camera) {
            return;
        }
        const rect = canvas.getBoundingClientRect();
        this._mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this._mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
        this._raycaster.setFromCamera(this._mouse, this._camera);
        const hits = this._raycaster.intersectObjects(
            this._cabinetGroup.children, false,
        );
        if (hits.length > 0) {
            const mesh = hits[0].object;
            const lineId = mesh.userData?.lineId || null;
            this._setHoveredLine(lineId);
            canvas.style.cursor = lineId ? "pointer" : "default";
        } else {
            this._setHoveredLine(null);
            canvas.style.cursor = "default";
        }
    }

    _setHoveredLine(lineId) {
        if (lineId === this._hoveredLineId) return;

        // Phase 3 Sprint A3 — clear the previous outline-shell siblings.
        // The shell is a child of the original mesh that we add on hover
        // and remove on un-hover. No material swap = no PBR cache thrash.
        if (this._hoveredLineId !== null && this._cabinetGroup) {
            this._cabinetGroup.traverse((obj) => {
                if (obj.isMesh
                    && obj.userData?.lineId === this._hoveredLineId
                    && obj.userData?._outlineShell) {
                    obj.remove(obj.userData._outlineShell);
                    obj.userData._outlineShell.geometry.dispose?.();
                    obj.userData._outlineShell = null;
                }
            });
        }

        this._hoveredLineId = lineId;
        this.state.hoveredLineId = lineId;

        if (lineId !== null && this._cabinetGroup && this._materials.outline) {
            const outlineMat = this._materials.outline;
            // Inverted-hull outline: child mesh, BackSide material,
            // scaled up by ~3% so the silhouette protrudes past the
            // original mesh by a couple of millimetres at typical
            // cabinet scale. depthWrite disabled so it does not
            // occlude the original mesh's surface.
            this._cabinetGroup.traverse((obj) => {
                if (obj.isMesh
                    && obj.userData?.lineId === lineId
                    && !obj.userData._outlineShell) {
                    const shell = new THREE.Mesh(obj.geometry, outlineMat);
                    shell.scale.set(1.03, 1.03, 1.03);
                    shell.userData._isOutlineShell = true;
                    obj.add(shell);
                    obj.userData._outlineShell = shell;
                }
            });
            const info = this._linesIndex[lineId];
            if (info) {
                const dims =
                    `${Math.round(info.width_mm)}×` +
                    `${Math.round(info.height_mm)}×` +
                    `${Math.round(info.depth_mm)} mm`;
                this.state.hoveredLineInfo =
                    `#${info.sequence} · ${info.family} · ${info.sku || ""} · ${dims}`;
            } else {
                this.state.hoveredLineInfo = `Line ${lineId}`;
            }
        } else {
            this.state.hoveredLineInfo = null;
        }
    }

    // ------------------------------------------------------------------
    // 2026-07-03 — persistent selection outline (reverse sync with the
    // parent OrderBuilder's state.ui.selected_line_id).
    //
    // Same inverted-hull technique as the hover outline in _setHoveredLine,
    // but the shell persists until the selection changes and uses the amber
    // `selected` material so it reads distinctly from the sky-blue hover
    // (both can show at once, on different cabinets). Hidden in blueline
    // mode, like the hover highlight. Shells reuse the host mesh geometry
    // (not cloned) so removal only detaches them — it must NOT dispose the
    // shared geometry.
    // ------------------------------------------------------------------
    _applySelectionHighlight(lineId) {
        this._clearSelectionShells();
        const isNull = (lineId === null || lineId === undefined);
        this._selectedLineId = isNull ? null : lineId;
        // mesh.userData.lineId is the L{id}_ capture group — a string.
        const key = isNull ? null : String(lineId);
        if (key === null || !this._cabinetGroup
            || this.state.mode === "blueline" || !this._materials.selected) {
            return;
        }
        const THREE = this._THREE;
        const mat = this._materials.selected;
        this._cabinetGroup.traverse((obj) => {
            if (obj.isMesh
                && obj.userData?.lineId === key
                && !obj.userData._isSelectionShell
                && !obj.userData._selectionShell) {
                const shell = new THREE.Mesh(obj.geometry, mat);
                shell.scale.set(1.045, 1.045, 1.045);   // just past hover's 1.03
                shell.userData._isSelectionShell = true;
                shell.renderOrder = 998;
                obj.add(shell);
                obj.userData._selectionShell = shell;
            }
        });
    }

    _clearSelectionShells() {
        if (!this._cabinetGroup) return;
        this._cabinetGroup.traverse((obj) => {
            if (obj.isMesh && obj.userData?._selectionShell) {
                obj.remove(obj.userData._selectionShell);
                // Geometry is SHARED with the host mesh — never dispose here.
                obj.userData._selectionShell = null;
            }
        });
    }

    _onMouseDown(event) {
        this._mouseDownAt = { x: event.clientX, y: event.clientY };
    }

    _onMouseUp(event) {
        const down = this._mouseDownAt;
        this._mouseDownAt = null;
        if (!down) return;
        const dx = event.clientX - down.x;
        const dy = event.clientY - down.y;
        if (Math.hypot(dx, dy) > this._MAX_CLICK_DELTA_PX) return;
        // Clean click — dispatch.
        this._handleCanvasClick(event);
    }

    _handleCanvasClick(event) {
        if (this.state.mode === "blueline") return;
        const canvas = this.canvasRef.el;
        if (!canvas || !this._raycaster || !this._cabinetGroup || !this._camera) {
            return;
        }
        const rect = canvas.getBoundingClientRect();
        this._mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this._mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
        this._raycaster.setFromCamera(this._mouse, this._camera);
        const hits = this._raycaster.intersectObjects(
            this._cabinetGroup.children, false,
        );
        if (!hits.length) return;
        const lineId = hits[0].object.userData?.lineId;
        if (!lineId) return;
        if (this.props.onLineSelected) {
            this.props.onLineSelected(parseInt(lineId, 10));
        }
    }

    _buildDimensionLines(payload) {
        const THREE = this._THREE;
        const group = this._dimensionGroup;
        if (!THREE || !group) return;

        this._clearDimensionGroup();

        if (!payload || !payload.bounds) return;

        const b = payload.bounds;
        const W = b.max[0] - b.min[0];
        const H = b.max[1] - b.min[1];
        const D = b.max[2] - b.min[2];

        const lineMat = new THREE.LineBasicMaterial({
            color: 0x2b4f6b,
            transparent: true,
            opacity: 0.85,
        });
        this._dimensionMaterial = lineMat;

        const TICK = 60;          // tick-mark half-length (mm). Larger
                                  // than T1C5's 25 since kitchen scale
                                  // dwarfs single-cabinet scale.
        const OFFSET_W = 400;     // dim-line offsets from cabinet face.
        const OFFSET_H = 600;
        const OFFSET_D = 600;
        const LABEL_GAP = 280;    // label distance from dim line.

        // ---- WIDTH — across X, in front of the kitchen, below the floor.
        const wYbar = -OFFSET_W;
        const wZbar = b.max[2] + 100;
        const xL = b.min[0];
        const xR = b.max[0];
        this._addLineSegment(group, lineMat,
            new THREE.Vector3(xL, wYbar, wZbar),
            new THREE.Vector3(xR, wYbar, wZbar));
        this._addLineSegment(group, lineMat,
            new THREE.Vector3(xL, 0, b.max[2]),
            new THREE.Vector3(xL, wYbar - 40, wZbar));
        this._addLineSegment(group, lineMat,
            new THREE.Vector3(xR, 0, b.max[2]),
            new THREE.Vector3(xR, wYbar - 40, wZbar));
        this._addLineSegment(group, lineMat,
            new THREE.Vector3(xL, wYbar - TICK, wZbar),
            new THREE.Vector3(xL, wYbar + TICK, wZbar));
        this._addLineSegment(group, lineMat,
            new THREE.Vector3(xR, wYbar - TICK, wZbar),
            new THREE.Vector3(xR, wYbar + TICK, wZbar));
        this._addLabelSprite(group,
            this._formatMm(W), (xL + xR) / 2, wYbar - LABEL_GAP, wZbar);

        // ---- HEIGHT — vertical, on the right side of the kitchen.
        const hX = b.max[0] + OFFSET_H;
        const hZmid = (b.min[2] + b.max[2]) / 2;
        this._addLineSegment(group, lineMat,
            new THREE.Vector3(hX, 0, hZmid),
            new THREE.Vector3(hX, H, hZmid));
        this._addLineSegment(group, lineMat,
            new THREE.Vector3(b.max[0], 0, hZmid),
            new THREE.Vector3(hX + 40, 0, hZmid));
        this._addLineSegment(group, lineMat,
            new THREE.Vector3(b.max[0], H, hZmid),
            new THREE.Vector3(hX + 40, H, hZmid));
        this._addLineSegment(group, lineMat,
            new THREE.Vector3(hX - TICK, 0, hZmid),
            new THREE.Vector3(hX + TICK, 0, hZmid));
        this._addLineSegment(group, lineMat,
            new THREE.Vector3(hX - TICK, H, hZmid),
            new THREE.Vector3(hX + TICK, H, hZmid));
        this._addLabelSprite(group,
            this._formatMm(H), hX + LABEL_GAP, H / 2, hZmid);

        // ---- DEPTH — along Z, on the floor to the left.
        const dX = b.min[0] - OFFSET_D;
        const dY = 5;
        this._addLineSegment(group, lineMat,
            new THREE.Vector3(dX, dY, b.min[2]),
            new THREE.Vector3(dX, dY, b.max[2]));
        this._addLineSegment(group, lineMat,
            new THREE.Vector3(b.min[0], dY, b.min[2]),
            new THREE.Vector3(dX + 40, dY, b.min[2]));
        this._addLineSegment(group, lineMat,
            new THREE.Vector3(b.min[0], dY, b.max[2]),
            new THREE.Vector3(dX + 40, dY, b.max[2]));
        this._addLineSegment(group, lineMat,
            new THREE.Vector3(dX, dY, b.min[2] - TICK),
            new THREE.Vector3(dX, dY, b.min[2] + TICK));
        this._addLineSegment(group, lineMat,
            new THREE.Vector3(dX, dY, b.max[2] - TICK),
            new THREE.Vector3(dX, dY, b.max[2] + TICK));
        this._addLabelSprite(group,
            this._formatMm(D), dX - LABEL_GAP, dY, (b.min[2] + b.max[2]) / 2);
    }

    _addLineSegment(group, mat, a, b) {
        const THREE = this._THREE;
        const geom = new THREE.BufferGeometry().setFromPoints([a, b]);
        const line = new THREE.Line(geom, mat);
        line.castShadow = false;
        line.receiveShadow = false;
        line.renderOrder = 999;
        group.add(line);
        return line;
    }

    _addLabelSprite(group, text, x, y, z) {
        const THREE = this._THREE;
        const dpr = Math.max(1, window.devicePixelRatio || 1);

        const W_PX = 320;
        const H_PX = 110;
        const canvas = document.createElement("canvas");
        canvas.width = W_PX * dpr;
        canvas.height = H_PX * dpr;
        const ctx = canvas.getContext("2d");
        ctx.scale(dpr, dpr);

        ctx.font =
            "600 28px 'JetBrains Mono', ui-monospace, SFMono-Regular, monospace";
        const padX = 16;
        const pillH = 56;
        const tw = ctx.measureText(text).width;
        const pillW = tw + padX * 2;
        const px = (W_PX - pillW) / 2;
        const py = (H_PX - pillH) / 2;
        ctx.fillStyle = "rgba(251, 247, 239, 0.92)";       // --sb-paper
        const r = 6;
        ctx.beginPath();
        ctx.moveTo(px + r, py);
        ctx.arcTo(px + pillW, py, px + pillW, py + pillH, r);
        ctx.arcTo(px + pillW, py + pillH, px, py + pillH, r);
        ctx.arcTo(px, py + pillH, px, py, r);
        ctx.arcTo(px, py, px + pillW, py, r);
        ctx.closePath();
        ctx.fill();
        ctx.strokeStyle = "rgba(43, 79, 107, 0.4)";
        ctx.lineWidth = 1;
        ctx.stroke();

        ctx.fillStyle = "#2b4f6b";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(text, W_PX / 2, H_PX / 2);

        const texture = new THREE.CanvasTexture(canvas);
        if (THREE.SRGBColorSpace) texture.colorSpace = THREE.SRGBColorSpace;
        const material = new THREE.SpriteMaterial({
            map: texture,
            transparent: true,
            depthTest: false,
        });
        const sprite = new THREE.Sprite(material);
        sprite.position.set(x, y, z);
        // Larger world-scale than T1C5 because the kitchen spans
        // 2-5 m; labels need to be ~250-300 mm tall to read at the
        // default camera zoom.
        sprite.scale.set(700, 700 * (H_PX / W_PX), 1);
        sprite.renderOrder = 1000;
        group.add(sprite);

        this._spriteResources.push({ texture, material });
    }

    _clearDimensionGroup() {
        const group = this._dimensionGroup;
        if (!group) return;
        while (group.children.length) {
            const child = group.children[0];
            group.remove(child);
            if (child.geometry) child.geometry.dispose();
        }
        for (const r of this._spriteResources) {
            if (r.texture) r.texture.dispose();
            if (r.material) r.material.dispose();
        }
        this._spriteResources = [];
        if (this._dimensionMaterial) {
            this._dimensionMaterial.dispose();
            this._dimensionMaterial = null;
        }
    }

    _formatMm(mm) {
        const inches = mm / 25.4;
        const inchesRounded = Math.round(inches * 4) / 4;
        const inchesDisplay =
            Math.abs(inchesRounded) > 0.001
                ? `${inchesRounded.toFixed(2).replace(/\.?0+$/, "")}"`
                : "";
        return `${Math.round(mm)} mm${inchesDisplay ? ` · ${inchesDisplay}` : ""}`;
    }

    _dispose() {
        if (this._frameId) cancelAnimationFrame(this._frameId);
        if (this._resizeObserver) this._resizeObserver.disconnect();
        if (this._cabinetGroup) {
            this._cabinetGroup.traverse((obj) => {
                if (obj.geometry) obj.geometry.dispose();
            });
        }
        if (this._materials) {
            for (const m of Object.values(this._materials)) m.dispose?.();
        }
        if (this._floorGeom) this._floorGeom.dispose();
        if (this._floorMat) this._floorMat.dispose();
        // P25C2 — dimension overlay disposal.
        this._clearDimensionGroup();
        if (this._renderer) this._renderer.dispose();
    }
}
