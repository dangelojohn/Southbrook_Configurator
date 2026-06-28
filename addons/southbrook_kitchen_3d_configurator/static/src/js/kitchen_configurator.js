/** @odoo-module **/
/**
 * Southbrook Kitchen 3D Configurator
 * OWL 2 component with real Three.js isometric scene.
 *
 * Architecture:
 *  - OWL manages reactive state (room dims, products, selection, saving)
 *  - Three.js renders the 3D scene inside a <div t-ref="canvas3d">
 *  - JSON-RPC controller provides live Odoo product data
 *  - Scene rebuilds whenever room dimensions or product list change
 */

import { Component, onMounted, onWillStart, onWillUnmount, useRef, useState, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

const actionRegistry = registry.category("actions");

// ─── Cabinet constants (inches) ──────────────────────────────────────────────
const IN  = 1 / 12;          // 1 inch in scene-feet
const BW  = 24 * IN;         // base cabinet width  (2 ft)
const BH  = 34.5 * IN;       // base cabinet height (34.5")
const BD  = 24 * IN;         // base cabinet depth  (2 ft)
const WW  = 24 * IN;         // wall cabinet width
const WH  = 30 * IN;         // wall cabinet height (30")
const WD  = 12 * IN;         // wall cabinet depth  (1 ft)
const CTR = 1.5 * IN;        // countertop thickness
const GAP = 18 * IN;         // clearance between counter and wall cab bottom
const WBY = BH + CTR + GAP;  // wall cabinet bottom Y

// ─── Colour palette ───────────────────────────────────────────────────────────
const P = {
    scene:   0xECE9E3,
    floor:   0xCFC4A8,
    wall1:   0xE7E2D9,   // back wall
    wall2:   0xDED8CE,   // left wall
    grid:    0xBAB4A8,
    cab:     0xC9C4BC,
    cabDark: 0xA9A59E,
    counter: 0xE1DDD6,
    handle:  0x3A3530,
    sel:     0x1866D4,
    drag:    0x1866D4,
    toekick: 0x8A857E,
    arrow:   0x1866D4,
};

// ─── Three.js loader ──────────────────────────────────────────────────────────
// As of 19.0.3.0.0 we depend on southbrook_estimating, which ships a
// vendored r160 build of THREE in web.assets_backend (via this addon's
// manifest). The previous CDN load of three@0.128 was dropped — it
// lacked SRGBColorSpace / ACESFilmicToneMapping (r152+) and double-
// loaded against the catalog's local copy. window.THREE is guaranteed
// to be present at module load time.
function loadThreeJS() {
    if (window.THREE) return Promise.resolve(window.THREE);
    return Promise.reject(new Error(
        "Three.js not available. southbrook_estimating's vendored " +
        "three.min.js must load before kitchen_configurator.js (see manifest)."
    ));
}

// ─── OWL Component ────────────────────────────────────────────────────────────
class SouthbrookKitchenConfigurator extends Component {
    setup() {
        this.notification = useService("notification");
        this.action       = useService("action");
        this.canvas3dRef  = useRef("canvas3d");

        // ── Reactive state ────────────────────────────────────────────────────
        this.state = useState({
            loading:  true,
            saving:   false,
            error:    "",
            room: {
                width_in:  this.props.room_width_in  || 12,
                depth_in:  this.props.room_depth_in  || 24,
                height_in: this.props.room_height_in || 96,
            },
            products:  [],
            items:     [],
            selected:  null,
            summary:   { base_count: 0, wall_count: 0, total: 0, price: 0, remainder_in: 0 },
            designId:  this.props.design_id || null,
            designName: this.props.design_name || "",
        });

        // ── Three.js scene state (not reactive — managed imperatively) ────────
        this.T = {
            THREE: null, scene: null, camera: null, renderer: null,
            raycaster: null,
            roomObjs: [], cabObjs: [], clickable: [],
            handleMesh: null,
            dragging: false, dragX0: 0, dragW0: 0,
            animId: null,
        };

        this._onMouseDown = this._onMouseDown.bind(this);
        this._onMouseMove = this._onMouseMove.bind(this);
        this._onMouseUp   = this._onMouseUp.bind(this);
        this._onMouseOver = this._onMouseOver.bind(this);

        // ── Lifecycle ─────────────────────────────────────────────────────────
        onWillStart(async () => {
            const [THREE] = await Promise.all([
                loadThreeJS(),
                this._loadProducts(),
            ]);
            this.T.THREE    = THREE;
            this.T.raycaster = new THREE.Raycaster();
            await this._refreshLayout();
            this.state.loading = false;
        });

        onMounted(() => {
            if (this.T.THREE) {
                this._initScene();
                this._buildScene();
            }
        });

        onWillUnmount(() => {
            this._destroyScene();
        });
    }

    // ─── Odoo data ──────────────────────────────────────────────────────────────
    async _loadProducts() {
        try {
            this.state.products = await rpc("/southbrook_kitchen/configurator/products", {});
        } catch (_) {
            this.state.products = [];
        }
    }

    async _refreshLayout() {
        try {
            const result = await rpc("/southbrook_kitchen/configurator/layout", {
                room_width_in:  this.state.room.width_in,
                room_depth_in:  this.state.room.depth_in,
                room_height_in: this.state.room.height_in,
            });
            this.state.error   = result.error || "";
            this.state.items   = result.items  || [];
            this.state.summary = result.summary || this.state.summary;
            if (!this.state.selected && this.state.items.length) {
                this.state.selected = this.state.items[0];
            }
            // Rebuild 3D after data refresh
            if (this.T.scene) this._buildScene();
        } catch (e) {
            this.state.error = "Layout error: " + (e.message || e);
        }
    }

    // ─── Room controls ──────────────────────────────────────────────────────────
    async _changeRoom(field, raw) {
        const v = parseFloat(raw);
        if (!Number.isFinite(v)) return;
        const min = { width_in: 12, depth_in: 12, height_in: 84 };
        this.state.room[field] = Math.max(min[field] || 12, v);
        await this._refreshLayout();
    }

    async _stretchWidth(delta) {
        this.state.room.width_in = Math.max(12, this.state.room.width_in + delta);
        await this._refreshLayout();
    }

    _selectCabinet(item) {
        this.state.selected = item;
        this._highlightSelected(item);
    }

    // ─── Three.js initialisation ────────────────────────────────────────────────
    _initScene() {
        const THREE  = this.T.THREE;
        const mount  = this.canvas3dRef.el;
        if (!mount) return;

        const W = mount.clientWidth  || 900;
        const H = mount.clientHeight || 560;

        // Scene
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(P.scene);
        this.T.scene = scene;

        // Orthographic isometric camera
        const asp = W / H, vs = 9;
        const camera = new THREE.OrthographicCamera(-vs * asp, vs * asp, vs, -vs, 0.1, 300);
        camera.position.set(20, 14, 20);
        camera.lookAt(4, 2.5, 1.5);
        this.T.camera = camera;

        // Renderer — ACES Filmic + sRGB for the canonical Southbrook
        // PBR pipeline (matches cabinet_viewport.esm.js Phase 2.5 spec).
        // The previous NoToneMapping + MeshLambertMaterial combo crushed
        // mid-tones and made the cabinets look uniformly dark.
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
        this.T.renderer = renderer;

        // Lighting — 4-light rig (hemi + key/fill/front directional)
        // ported from southbrook_estimating/cabinet_viewport.esm.js.
        // HemisphereLight does the heavy lift for "cabinets aren't dark";
        // the key + fill + front trio gives every face direct illumination
        // without flat shadowing.
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

        // PBR env map — async, non-blocking. Falls back silently if the
        // PMREM step fails on the user's GL stack; the direct-lit rig
        // above still renders the scene fine.
        this._installPbrEnvMap();

        // Render loop
        const tick = () => {
            this.T.animId = requestAnimationFrame(tick);
            renderer.render(scene, camera);
        };
        tick();

        // Resize observer
        this._resizeObserver = new ResizeObserver(() => {
            const nw = mount.clientWidth, nh = mount.clientHeight;
            if (!nw || !nh) return;
            const na = nw / nh, nvs = 9;
            camera.left = -nvs * na; camera.right = nvs * na;
            camera.top  = nvs;       camera.bottom = -nvs;
            camera.updateProjectionMatrix();
            renderer.setSize(nw, nh);
        });
        this._resizeObserver.observe(mount);

        // Events
        mount.addEventListener("mousedown",  this._onMouseDown);
        mount.addEventListener("mousemove",  this._onMouseMove);
        mount.addEventListener("mouseup",    this._onMouseUp);
        mount.addEventListener("mouseleave", this._onMouseUp);
        mount.addEventListener("mousemove",  this._onMouseOver);
    }

    // ─── PBR environment map (PMREM) ────────────────────────────────────────────
    // Builds a small studio HDR-equivalent from a vertical gradient on a
    // canvas, runs it through PMREMGenerator, and assigns the result as
    // scene.environment. Adds soft PBR reflections on MeshStandardMaterial
    // metalness/roughness without needing an HDR file at runtime.
    // Mirrors southbrook_estimating_website/kitchen_viewport.esm.js.
    _installPbrEnvMap() {
        const { THREE, scene, renderer } = this.T;
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

    _destroyScene() {
        const t = this.T;
        if (t.animId) cancelAnimationFrame(t.animId);
        if (this._resizeObserver) this._resizeObserver.disconnect();
        const mount = this.canvas3dRef.el;
        if (mount) {
            mount.removeEventListener("mousedown",  this._onMouseDown);
            mount.removeEventListener("mousemove",  this._onMouseMove);
            mount.removeEventListener("mouseup",    this._onMouseUp);
            mount.removeEventListener("mouseleave", this._onMouseUp);
            mount.removeEventListener("mousemove",  this._onMouseOver);
        }
        if (t.renderer) {
            t.renderer.dispose();
            if (mount && t.renderer.domElement && mount.contains(t.renderer.domElement)) {
                mount.removeChild(t.renderer.domElement);
            }
        }
    }

    // ─── Scene builder ──────────────────────────────────────────────────────────
    _buildScene() {
        const { THREE, scene, camera, renderer } = this.T;
        if (!scene || !camera || !renderer) return;

        const rw = this.state.room.width_in  * IN;
        const rd = this.state.room.depth_in  * IN;
        const rh = this.state.room.height_in * IN;

        // Dispose previous geometry
        [...this.T.roomObjs, ...this.T.cabObjs].forEach(m => {
            if (m.geometry) m.geometry.dispose();
            if (m.material) {
                if (Array.isArray(m.material)) m.material.forEach(x => x.dispose());
                else m.material.dispose();
            }
            scene.remove(m);
        });
        if (this.T.handleMesh) {
            scene.remove(this.T.handleMesh);
            this.T.handleMesh.geometry?.dispose();
            this.T.handleMesh.material?.dispose();
        }
        this.T.roomObjs = []; this.T.cabObjs = []; this.T.clickable = []; this.T.handleMesh = null;

        // Helper: make + add mesh — now PBR (MeshStandardMaterial).
        // opts.rough / opts.metal control the PBR contract; if absent
        // we default to a matte-carcass profile (rough=0.7, metal=0.0).
        // cs/rs flags toggle shadow casting/receiving as before.
        const mk = (geo, color, pos, rotE, opts = {}) => {
            const mat = new THREE.MeshStandardMaterial({
                color,
                roughness: opts.rough != null ? opts.rough : 0.7,
                metalness: opts.metal != null ? opts.metal : 0.0,
            });
            const m = new THREE.Mesh(geo, mat);
            m.position.set(...pos);
            if (rotE) { m.rotation.x = rotE[0]; m.rotation.y = rotE[1]; m.rotation.z = rotE[2]; }
            if (opts.cs) m.castShadow    = true;
            if (opts.rs) m.receiveShadow = true;
            if (opts.ud) m.userData      = opts.ud;
            scene.add(m);
            return m;
        };

        // ── Room shell ── (matte plaster + flooring; high roughness)
        const floor = mk(new THREE.PlaneGeometry(rw, rd), P.floor, [rw/2, 0, rd/2], [-Math.PI/2, 0, 0], { rs: true, rough: 0.95, metal: 0.0 });
        const bwall = mk(new THREE.PlaneGeometry(rw, rh), P.wall1, [rw/2, rh/2, 0],  null,              { rs: true, rough: 0.9,  metal: 0.0 });
        const lwall = mk(new THREE.PlaneGeometry(rd, rh), P.wall2, [0, rh/2, rd/2],  [0, Math.PI/2, 0], { rs: true, rough: 0.9,  metal: 0.0 });

        // Wainscoting rail on back wall — semi-gloss wood trim
        const railY = 36 * IN;
        this.T.roomObjs.push(
            floor, bwall, lwall,
            mk(new THREE.BoxGeometry(rw, 0.012, 0.02), P.cabDark, [rw/2, railY, 0.01], null, { rough: 0.55, metal: 0.0 })
        );

        // Floor grid
        const gSz = Math.max(rw, rd) + 6;
        const grid = new THREE.GridHelper(gSz, Math.ceil(gSz * 2), P.grid, P.grid);
        grid.position.set(rw/2, 0.002, rd/2);
        grid.material.transparent = true;
        grid.material.opacity     = 0.18;
        scene.add(grid);
        this.T.roomObjs.push(grid);

        // ── Cabinet fill ──
        const items = this.state.items;
        // Group base and wall items for geometry creation
        const baseItems = items.filter(it => it.cabinet_type === "base");
        const wallItems = items.filter(it => it.cabinet_type === "wall");
        const fillerItems = items.filter(it => it.cabinet_type === "filler");

        baseItems.forEach((item, i) => {
            const x   = item.x_position_in * IN;
            const cbW = item.width_in  * IN;
            const cbH = item.height_in * IN;
            const cbD = item.depth_in  * IN;

            // Toe kick — flat black/matte
            this.T.cabObjs.push(mk(
                new THREE.BoxGeometry(cbW - 0.01, 3.5 * IN, cbD - 0.01), P.toekick,
                [x + cbW/2, 3.5*IN/2, cbD/2], null, { cs: true, rough: 0.95, metal: 0.0 }
            ));

            // Cabinet body — satin-lacquer carcass
            const body = mk(
                new THREE.BoxGeometry(cbW - 0.02, cbH - 3.5*IN, cbD - 0.02), P.cab,
                [x + cbW/2, 3.5*IN + (cbH - 3.5*IN)/2, cbD/2], null,
                { cs: true, rs: true, rough: 0.55, metal: 0.0, ud: { cab: true, cabType: "base", item } }
            );
            this.T.cabObjs.push(body);
            this.T.clickable.push(body);

            // Shaker door upper inset — slightly glossier than carcass
            const dH = (cbH - 3.5*IN) * 0.60;
            this.T.cabObjs.push(mk(
                new THREE.BoxGeometry(cbW - 0.10, dH, 0.016), P.cabDark,
                [x + cbW/2, 3.5*IN + (cbH - 3.5*IN) * 0.72 - dH/2, cbD - 0.001], null,
                { rough: 0.6, metal: 0.05, ud: { cab: true, cabType: "base", item } }
            ));

            // Drawer face
            this.T.cabObjs.push(mk(
                new THREE.BoxGeometry(cbW - 0.10, (cbH - 3.5*IN) * 0.21, 0.016), P.cab,
                [x + cbW/2, 3.5*IN + (cbH - 3.5*IN) * 0.13, cbD - 0.001], null,
                { rough: 0.55, metal: 0.0, ud: { cab: true, cabType: "base", item } }
            ));

            // Door handle — brushed metal (this is the realism win — handles
            // were the flattest part of the old Lambert pass)
            this.T.cabObjs.push(mk(
                new THREE.BoxGeometry(cbW * 0.44, 0.025, 0.040), P.handle,
                [x + cbW/2, 3.5*IN + (cbH - 3.5*IN) * 0.42, cbD + 0.018], null,
                { rough: 0.35, metal: 0.85 }
            ));
            // Drawer handle — same brushed metal
            this.T.cabObjs.push(mk(
                new THREE.BoxGeometry(cbW * 0.30, 0.025, 0.038), P.handle,
                [x + cbW/2, 3.5*IN + (cbH - 3.5*IN) * 0.13, cbD + 0.018], null,
                { rough: 0.35, metal: 0.85 }
            ));

            // Countertop — quartz/stone (low roughness, faint specular)
            this.T.cabObjs.push(mk(
                new THREE.BoxGeometry(cbW + 0.005, CTR, cbD + 0.07), P.counter,
                [x + cbW/2, cbH + CTR/2, cbD/2 + 0.03], null,
                { cs: true, rough: 0.4, metal: 0.05 }
            ));
            // Countertop drip edge
            this.T.cabObjs.push(mk(
                new THREE.BoxGeometry(cbW + 0.005, CTR * 0.6, 0.022), P.cabDark,
                [x + cbW/2, cbH + CTR * 0.3, cbD + 0.07], null,
                { rough: 0.5, metal: 0.05 }
            ));
        });

        wallItems.forEach((item, i) => {
            const x   = item.x_position_in * IN;
            const wbW = item.width_in  * IN;
            const wbH = item.height_in * IN;
            const wbD = item.depth_in  * IN;
            const wbY = WBY;   // wall cabinet bottom

            // Wall body — satin-lacquer carcass
            const wbody = mk(
                new THREE.BoxGeometry(wbW - 0.02, wbH, wbD - 0.02), P.cab,
                [x + wbW/2, wbY + wbH/2, wbD/2], null,
                { cs: true, rs: true, rough: 0.55, metal: 0.0, ud: { cab: true, cabType: "wall", item } }
            );
            this.T.cabObjs.push(wbody);
            this.T.clickable.push(wbody);

            // Shaker door
            this.T.cabObjs.push(mk(
                new THREE.BoxGeometry(wbW - 0.10, wbH - 0.10, 0.016), P.cabDark,
                [x + wbW/2, wbY + wbH/2, wbD - 0.001], null,
                { rough: 0.6, metal: 0.05, ud: { cab: true, cabType: "wall", item } }
            ));
            // Wall handle — brushed metal
            this.T.cabObjs.push(mk(
                new THREE.BoxGeometry(wbW * 0.38, 0.025, 0.038), P.handle,
                [x + wbW/2, wbY + wbH * 0.60, wbD + 0.018], null,
                { rough: 0.35, metal: 0.85 }
            ));
            // Bottom rail — matches the countertop sheen
            this.T.cabObjs.push(mk(
                new THREE.BoxGeometry(wbW - 0.02, 0.025, wbD - 0.02), P.counter,
                [x + wbW/2, wbY - 0.010, wbD/2], null,
                { rough: 0.4, metal: 0.05 }
            ));
        });

        // Filler panels — matte/satin matching the door style
        fillerItems.forEach(item => {
            const x   = item.x_position_in * IN;
            const fpW = item.width_in * IN;
            this.T.cabObjs.push(mk(
                new THREE.BoxGeometry(fpW, BH, 0.042), P.cabDark,
                [x + fpW/2, BH/2, 0.021], null,
                { rough: 0.55, metal: 0.0 }
            ));
        });

        // ── Drag handle ── (PBR sphere with self-emissive glow so it
        // pops out of the scene against any background/exposure)
        const THREE3 = this.T.THREE;
        const hdl = new THREE3.Mesh(
            new THREE3.SphereGeometry(0.18, 20, 20),
            new THREE3.MeshStandardMaterial({
                color: P.drag, emissive: 0x001166, emissiveIntensity: 0.4,
                roughness: 0.3, metalness: 0.1,
            })
        );
        hdl.position.set(rw + 0.08, 0.18, rd / 2);
        hdl.userData = { isDragHandle: true };
        scene.add(hdl);
        this.T.handleMesh = hdl;

        // Arrow cones flanking handle
        [{ offset: -0.42, rotZ: Math.PI/2 }, { offset: 0.42, rotZ: -Math.PI/2 }].forEach(({ offset, rotZ }) => {
            const arr = new THREE3.Mesh(
                new THREE3.ConeGeometry(0.08, 0.22, 8),
                new THREE3.MeshStandardMaterial({
                    color: P.arrow, roughness: 0.4, metalness: 0.1,
                })
            );
            arr.rotation.z = rotZ;
            arr.position.set(rw + offset, 0.18, rd / 2);
            scene.add(arr);
            this.T.roomObjs.push(arr);
        });

        // ── Re-frame camera ──
        const maxDim = Math.max(rw, rd, rh);
        const vs     = maxDim * 0.68 + 4.5;
        const asp    = renderer.domElement.width / renderer.domElement.height;
        camera.left = -vs * asp; camera.right = vs * asp;
        camera.top  = vs;        camera.bottom = -vs;
        camera.updateProjectionMatrix();
        camera.position.set(rw + 12, rh * 0.7 + 6, rd + 12);
        camera.lookAt(rw / 2, rh * 0.28, rd / 2);

        // Re-apply selection highlight after rebuild
        if (this.state.selected) {
            this._highlightSelected(this.state.selected);
        }
    }

    _highlightSelected(item) {
        if (!item) return;
        // Reset all cabinet colours
        this.T.cabObjs.forEach(m => {
            if (m.userData?.cab) m.material.color.setHex(P.cab);
        });
        // Highlight matching item
        this.T.cabObjs.forEach(m => {
            if (m.userData?.cab &&
                m.userData.item?.layout_key === item.layout_key) {
                m.material.color.setHex(P.sel);
            }
        });
    }

    // ─── Mouse events ────────────────────────────────────────────────────────────
    _ndcFromEvent(e) {
        const rect = this.canvas3dRef.el?.getBoundingClientRect();
        if (!rect) return { x: 0, y: 0 };
        return {
            x:  ((e.clientX - rect.left) / rect.width)  * 2 - 1,
            y: -((e.clientY - rect.top)  / rect.height) * 2 + 1,
        };
    }

    _onMouseDown(e) {
        const { camera, raycaster, handleMesh, clickable } = this.T;
        if (!camera || !raycaster) return;

        raycaster.setFromCamera(this._ndcFromEvent(e), camera);

        // Priority 1: drag handle
        if (handleMesh && raycaster.intersectObject(handleMesh).length) {
            this.T.dragging = true;
            this.T.dragX0   = e.clientX;
            this.T.dragW0   = this.state.room.width_in;
            e.preventDefault();
            return;
        }

        // Priority 2: cabinet selection
        const hits = raycaster.intersectObjects(clickable, false);
        if (hits.length) {
            const h = hits[0].object;
            if (h.userData?.item) {
                this._selectCabinet(h.userData.item);
            }
        }
    }

    _onMouseMove(e) {
        if (!this.T.dragging) return;
        const dx = e.clientX - this.T.dragX0;
        // ~55 px ≈ 1 ft at typical zoom
        const nw = Math.max(12, Math.min(288, this.T.dragW0 + dx * (12 / 55)));
        this.state.room.width_in = Math.round(nw / 6) * 6; // snap to 6-inch grid
    }

    _onMouseUp() {
        if (this.T.dragging) {
            this.T.dragging = false;
            this._refreshLayout();
        }
    }

    _onMouseOver(e) {
        const mount = this.canvas3dRef.el;
        if (!mount || !this.T.camera || !this.T.raycaster) return;
        this.T.raycaster.setFromCamera(this._ndcFromEvent(e), this.T.camera);
        const onH = this.T.handleMesh &&
            this.T.raycaster.intersectObject(this.T.handleMesh).length > 0;
        const onC = !onH &&
            this.T.raycaster.intersectObjects(this.T.clickable, false).length > 0;
        const cvs = this.T.renderer?.domElement;
        if (cvs) cvs.style.cursor = this.T.dragging ? "ew-resize" : onH ? "ew-resize" : onC ? "pointer" : "default";
    }

    // ─── Save ─────────────────────────────────────────────────────────────────────
    async _saveDesign() {
        this.state.saving = true;
        try {
            const result = await rpc("/southbrook_kitchen/configurator/save", {
                name:      this.state.designName ||
                           `Kitchen ${this.state.room.width_in}"`,
                room:      this.state.room,
                items:     this.state.items,
                design_id: this.state.designId || false,
            });
            this.state.designId   = result.id;
            this.state.designName = result.name;
            this.notification.add(`Saved: ${result.name}`, { type: "success" });
        } catch (e) {
            this.notification.add("Save failed: " + (e.message || e), { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    async _openDesigns() {
        return this.action.doAction(
            "southbrook_kitchen_3d_configurator.action_sbk_kitchen_designs"
        );
    }

    // ─── Formatting helpers ───────────────────────────────────────────────────────
    _money(v) { return `$${Number(v || 0).toFixed(2)}`; }

    _materialLabel(k) {
        return ({
            white_melamine: "White Melamine",
            grey_melamine:  "Grey Melamine",
            maple_veneer:   "Maple Veneer",
            oak_veneer:     "Oak Veneer",
            painted_mdf:    "Painted MDF",
            thermoplastic:  "Thermoplastic",
        })[k] || k;
    }
}

// ─── OWL Template ─────────────────────────────────────────────────────────────
SouthbrookKitchenConfigurator.template = xml`
<div class="o_sbk_root">

  <!-- Top bar -->
  <header class="o_sbk_topbar">
    <div class="o_sbk_brand_block">
      <div class="o_sbk_logo">
        <div class="o_sbk_logo_inner"/>
      </div>
      <div>
        <div class="o_sbk_brand_label">SOUTHBROOK KITCHEN</div>
        <h1 class="o_sbk_title">3D Room Configurator</h1>
      </div>
    </div>
    <div class="o_sbk_actions">
      <button class="o_sbk_btn o_sbk_btn_ghost"
              t-on-click="() => this._stretchWidth(-24)"
              t-att-disabled="state.room.width_in &lt;= 12">
        − 24 in
      </button>
      <button class="o_sbk_btn o_sbk_btn_ghost"
              t-on-click="() => this._stretchWidth(24)">
        + 24 in
      </button>
      <button class="o_sbk_btn o_sbk_btn_outline"
              t-on-click="_openDesigns">
        Kitchen Designs
      </button>
      <button class="o_sbk_btn o_sbk_btn_primary"
              t-att-disabled="state.saving || !state.items.length"
              t-on-click="_saveDesign">
        <t t-if="state.saving">Saving…</t>
        <t t-else="">Save Design</t>
      </button>
    </div>
  </header>

  <!-- Loading splash -->
  <div t-if="state.loading" class="o_sbk_loading">
    <div class="o_sbk_spinner"/>
    <span>Loading cabinet inventory…</span>
  </div>

  <!-- Main workspace -->
  <div t-else="" class="o_sbk_workspace">

    <!-- Left controls -->
    <aside class="o_sbk_controls">
      <h3>Room</h3>

      <label class="o_sbk_field">
        <span>Width (in)</span>
        <div class="o_sbk_input_row">
          <input type="number" min="12" step="6"
                 t-att-value="state.room.width_in"
                 t-on-change="(ev) => this._changeRoom('width_in', ev.target.value)"/>
          <span class="o_sbk_unit"><t t-esc="(state.room.width_in / 12).toFixed(1)"/> ft</span>
        </div>
      </label>

      <label class="o_sbk_field">
        <span>Depth (in)</span>
        <input type="number" min="12" step="6"
               t-att-value="state.room.depth_in"
               t-on-change="(ev) => this._changeRoom('depth_in', ev.target.value)"/>
      </label>

      <label class="o_sbk_field">
        <span>Height (in)</span>
        <input type="number" min="84" step="6"
               t-att-value="state.room.height_in"
               t-on-change="(ev) => this._changeRoom('height_in', ev.target.value)"/>
      </label>

      <!-- Summary metrics -->
      <div class="o_sbk_divider"/>

      <div class="o_sbk_metric">
        <strong><t t-esc="state.summary.base_count"/></strong>
        base cabinets
      </div>
      <div class="o_sbk_metric">
        <strong><t t-esc="state.summary.wall_count"/></strong>
        wall cabinets
      </div>
      <div class="o_sbk_metric o_sbk_metric_price">
        <strong><t t-esc="_money(state.summary.price)"/></strong>
        estimate
      </div>

      <div t-if="state.summary.remainder_in > 0" class="o_sbk_remainder">
        <span class="o_sbk_remainder_icon">▤</span>
        <t t-esc="state.summary.remainder_in.toFixed(1)"/> in filler needed
      </div>

      <div t-if="state.error" class="o_sbk_error" t-esc="state.error"/>
    </aside>

    <!-- 3D Scene panel -->
    <main class="o_sbk_scene_panel">
      <div t-ref="canvas3d" class="o_sbk_canvas3d"/>

      <!-- Dimension ruler overlay -->
      <div class="o_sbk_ruler">
        <t t-foreach="[0, 24, 48, 72, 96, 120, 144]" t-as="mark" t-key="mark">
          <span t-if="mark &lt;= state.room.width_in" class="o_sbk_mark">
            <t t-esc="mark"/> in
          </span>
        </t>
      </div>

      <!-- View label -->
      <div class="o_sbk_viewlabel">⬡ Isometric</div>
      <div class="o_sbk_draghint">Drag ● to resize • Click cabinet to select</div>
    </main>

    <!-- Right inventory + detail panel -->
    <aside class="o_sbk_inventory">

      <h3>Cabinet Inventory</h3>

      <!-- Column header -->
      <div class="o_sbk_inv_header">
        <span>Product</span><span>SKU</span><span>Width</span><span>Qty</span><span>Price</span>
      </div>

      <!-- Product rows -->
      <div class="o_sbk_product_list">
        <button t-foreach="state.products" t-as="product" t-key="product.product_id"
            t-att-class="'o_sbk_product_row' + (state.selected &amp;&amp; state.selected.product_id === product.product_id ? ' is-selected' : '')"
            t-on-click="() => this._selectCabinet(product)">
          <div class="o_sbk_prod_thumb">
            <img t-att-src="product.image_url" alt="" loading="lazy"/>
          </div>
          <div class="o_sbk_prod_info">
            <strong t-esc="product.name"/>
            <small><t t-esc="product.cabinet_type"/> | <t t-esc="product.material"/></small>
          </div>
          <span class="o_sbk_prod_sku"  t-esc="product.sku"/>
          <span class="o_sbk_prod_dim"  t-esc="product.width_in + '&quot;'"/>
          <span t-att-class="'o_sbk_prod_qty' + (product.available_qty > 50 ? ' ok' : ' low')"
                t-esc="product.available_qty"/>
          <span class="o_sbk_prod_price" t-esc="_money(product.price)"/>
        </button>
      </div>

      <!-- Selected cabinet detail -->
      <div t-if="state.selected" class="o_sbk_detail">
        <h4>Selected Cabinet</h4>
        <div class="o_sbk_detail_card">
          <div class="o_sbk_detail_img">
            <img t-if="state.selected.image_url" t-att-src="state.selected.image_url" alt=""/>
            <div t-else="" class="o_sbk_detail_img_placeholder">🗄</div>
          </div>
          <div class="o_sbk_detail_info">
            <p class="o_sbk_detail_name"><t t-esc="state.selected.name"/></p>
            <p class="o_sbk_detail_type"><t t-esc="state.selected.cabinet_type"/> cabinet</p>
          </div>
        </div>
        <dl class="o_sbk_spec_grid">
          <dt>SKU</dt>      <dd><t t-esc="state.selected.sku || '—'"/></dd>
          <dt>Width</dt>    <dd><t t-esc="state.selected.width_in"/> in</dd>
          <dt>Height</dt>   <dd><t t-esc="state.selected.height_in"/> in</dd>
          <dt>Depth</dt>    <dd><t t-esc="state.selected.depth_in"/> in</dd>
          <dt>Material</dt> <dd><t t-esc="_materialLabel(state.selected.material)"/></dd>
          <dt>Available</dt><dd t-att-class="state.selected.available_qty > 0 ? 'ok' : 'low'">
            <t t-esc="state.selected.available_qty"/> pcs
          </dd>
          <dt>BoM</dt>      <dd><t t-if="state.selected.bom_available">✓ Available</t><t t-else="">—</t></dd>
          <dt>Price</dt>    <dd class="price"><t t-esc="_money(state.selected.price)"/></dd>
        </dl>
      </div>

    </aside>
  </div>
</div>`;

SouthbrookKitchenConfigurator.props = {
    design_id:     { type: Number,  optional: true },
    design_name:   { type: String,  optional: true },
    room_width_in:  { type: Number, optional: true },
    room_depth_in:  { type: Number, optional: true },
    room_height_in: { type: Number, optional: true },
};
SouthbrookKitchenConfigurator.defaultProps = {};

actionRegistry.add("southbrook_kitchen_configurator", SouthbrookKitchenConfigurator);
