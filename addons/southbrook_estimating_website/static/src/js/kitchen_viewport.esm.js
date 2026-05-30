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
    useRef,
    useState,
    xml,
} from "@odoo/owl";

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
                <span class="o_owl_kitchen_status" t-if="state.loading">
                    Loading…
                </span>
                <span class="o_owl_kitchen_status text-danger"
                      t-elif="state.error" t-esc="state.error"/>
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
    };

    setup() {
        this.canvasRef = useRef("canvas");
        this.state = useState({
            loading: false,
            error: null,
            threeLoaded: !!window.THREE,
            meta: null,
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

        onMounted(() => this._init());
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

        if (THREE.OrbitControls) {
            this._controls = new THREE.OrbitControls(this._camera, canvas);
            this._controls.enableDamping = true;
            this._controls.dampingFactor = 0.1;
            this._controls.target.set(0, 600, 0);
        }

        this._cabinetGroup = new THREE.Group();
        this._scene.add(this._cabinetGroup);

        // Materials — simple palette. Phase 3 polish adds per-panel
        // distinctions (back / shelf / hardware finish).
        this._materials = {
            carcass: new THREE.MeshStandardMaterial({
                color: 0xc89e85, roughness: 0.85, metalness: 0.0,
            }),
            door: new THREE.MeshStandardMaterial({
                color: 0x6b3f2a, roughness: 0.7, metalness: 0.05,
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

        await this._fetchAndBuild();
        this._animate();
    }

    _animate() {
        if (!this._renderer) return;
        this._frameId = requestAnimationFrame(() => this._animate());
        if (this._controls) this._controls.update();
        this._renderer.render(this._scene, this._camera);
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

        if (!payload || !Array.isArray(payload.panels)) return;

        for (const p of payload.panels) {
            const d = p.dims;
            if (!d || d.width <= 0 || d.height <= 0 || d.depth <= 0) continue;
            const geom = new THREE.BoxGeometry(d.width, d.height, d.depth);
            const mat = this._materials[p.material || "carcass"]
                || this._materials.carcass;
            const mesh = new THREE.Mesh(geom, mat);
            mesh.position.set(p.pos.x, p.pos.y, p.pos.z);
            if (p.rot) {
                mesh.rotation.set(p.rot.x || 0, p.rot.y || 0, p.rot.z || 0);
            }
            mesh.castShadow = true;
            mesh.receiveShadow = true;
            this._cabinetGroup.add(mesh);
        }

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
        if (this._renderer) this._renderer.dispose();
    }
}
