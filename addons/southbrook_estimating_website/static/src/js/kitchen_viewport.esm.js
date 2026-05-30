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
                <button class="btn btn-sm o_owl_kitchen_mode_btn"
                        t-on-click="onToggleMode"
                        t-att-disabled="!state.threeLoaded">
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
        this._raycaster = null;
        this._mouse = null;
        this._mouseDownAt = null;
        this._MAX_CLICK_DELTA_PX = 5;

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
            // P25C2 — blueline wireframe overlay.
            blueline: new THREE.MeshBasicMaterial({
                color: 0x2b4f6b, wireframe: true,
            }),
            // P25C3 — hover highlight (sky emissive over carcass base).
            highlight: new THREE.MeshStandardMaterial({
                color: 0xc89e85,
                emissive: 0x2b4f6b,
                emissiveIntensity: 0.4,
                roughness: 0.5,
                metalness: 0.1,
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
            if (m) mesh.userData.lineId = m[1];
            this._cabinetGroup.add(mesh);
        }

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

        this.state.mode = this.state.mode === "solid" ? "blueline" : "solid";
        if (!this._cabinetGroup) return;
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

        // Restore previously hovered cabinet's materials.
        if (this._hoveredLineId !== null && this._cabinetGroup) {
            this._cabinetGroup.traverse((obj) => {
                if (obj.isMesh
                    && obj.userData?.lineId === this._hoveredLineId
                    && obj.userData?._origMaterialHover) {
                    obj.material = obj.userData._origMaterialHover;
                    obj.userData._origMaterialHover = null;
                }
            });
        }

        this._hoveredLineId = lineId;
        this.state.hoveredLineId = lineId;

        if (lineId !== null && this._cabinetGroup && this._materials.highlight) {
            const hl = this._materials.highlight;
            this._cabinetGroup.traverse((obj) => {
                if (obj.isMesh && obj.userData?.lineId === lineId) {
                    if (!obj.userData._origMaterialHover) {
                        obj.userData._origMaterialHover = obj.material;
                    }
                    obj.material = hl;
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
