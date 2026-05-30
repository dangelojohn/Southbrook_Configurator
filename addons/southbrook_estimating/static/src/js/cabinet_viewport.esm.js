/** @odoo-module **/
/*
 * SPDX-License-Identifier: LGPL-3.0-only
 *
 * Cabinet Viewport — OWL view widget that renders a parametric cabinet
 * in 3D for the OCA product_configurator wizard. Track 1 of Phase 2
 * charter amendment 1 (2026-05-30).
 *
 * Mount point: inherited product.configurator wizard form view
 *   (see views/product_configurator_3d_view.xml).
 *
 * RPC: product.config.session.get_3d_payload() — returns a per-panel
 * 3D layout derived from Phase-1 routine #1 (_compute_panel_dimensions).
 *
 * Three.js: required as window.THREE plus window.THREE.OrbitControls.
 * If absent, the component shows a friendly "not loaded" placeholder
 * pointing to addons/southbrook_estimating/static/lib/three/README.md
 * for vendoring instructions.
 */
import {
    Component,
    onMounted,
    onWillUnmount,
    onWillUpdateProps,
    useRef,
    useState,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class CabinetViewport extends Component {
    static template = "southbrook_estimating.CabinetViewport";
    static props = {
        record: { type: Object, optional: true },
        readonly: { type: Boolean, optional: true },
        name: { type: String, optional: true },
        "*": true,
    };

    setup() {
        this.canvasRef = useRef("canvas");
        this.orm = useService("orm");
        this.state = useState({
            mode: "solid",
            loading: false,
            error: null,
            threeLoaded: !!window.THREE,
            renderedAt: null,
        });

        // Three.js scene handles — populated in _initThreeScene().
        this._THREE = null;
        this._renderer = null;
        this._scene = null;
        this._camera = null;
        this._controls = null;
        this._cabinetGroup = null;
        this._materials = {};
        this._frameId = null;
        this._resizeObserver = null;

        // Reactivity state — used by onWillUpdateProps + debounced refresh.
        // Track 1 commit 2 reactivity contract:
        //   • _lastSessionId tracks which session we last fetched for.
        //   • _lastValueIdsKey is a stable join of the current value_ids;
        //     a change means the user picked / unpicked an attribute and
        //     we must re-fetch the payload.
        //   • _refreshTimer debounces rapid picks (the user can step
        //     through several attributes in <200ms; each onchange would
        //     otherwise fire an RPC).
        this._lastSessionId = null;
        this._lastValueIdsKey = null;
        this._refreshTimer = null;
        this._refreshDebounceMs = 150;

        onMounted(() => this._initThreeScene());
        onWillUpdateProps((nextProps) => {
            // The OCA wizard updates the record on every attribute pick:
            // the onchange handler writes the new value_ids onto the
            // session and back onto the wizard. fieldDependencies (below
            // at registry.add) ensures this widget receives those props.
            this._reactToRecord(nextProps.record);
        });
        onWillUnmount(() => this._dispose());
    }

    // ------------------------------------------------------------------
    // Init / dispose
    // ------------------------------------------------------------------

    async _initThreeScene() {
        const THREE = window.THREE;
        if (!THREE) {
            this.state.threeLoaded = false;
            return;
        }
        this._THREE = THREE;
        const canvas = this.canvasRef.el;
        if (!canvas) return;

        // Renderer — ACES Filmic per PRODBOARD_MANIFEST §10.
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
        this._fitRendererToCanvas();

        // Scene — paper-warm background to match the Southbrook palette.
        this._scene = new THREE.Scene();
        this._scene.background = new THREE.Color(0xfbf7ef);

        // Camera — sane defaults; payload.camera overrides on first build.
        this._camera = new THREE.PerspectiveCamera(35, 1, 10, 10000);
        this._camera.position.set(1200, 900, 1500);

        // Lights — 2 directional + 1 hemi (Phase 1 simplification of the
        // 6-light setup from PRODBOARD_MANIFEST §10; full set lands in
        // Phase 3 polish).
        const hemi = new THREE.HemisphereLight(0xffffff, 0xd8cfbf, 0.5);
        this._scene.add(hemi);
        const dirA = new THREE.DirectionalLight(0xffffff, 0.9);
        dirA.position.set(800, 1200, 600);
        this._scene.add(dirA);
        const dirB = new THREE.DirectionalLight(0xffffff, 0.3);
        dirB.position.set(-500, 500, 800);
        this._scene.add(dirB);

        // OrbitControls — drag-rotate, scroll-zoom.
        if (THREE.OrbitControls) {
            this._controls = new THREE.OrbitControls(this._camera, canvas);
            this._controls.enableDamping = true;
            this._controls.dampingFactor = 0.1;
            this._controls.target.set(0, 400, 0);
        }

        // Cabinet group — child of scene; cleared + repopulated per payload.
        this._cabinetGroup = new THREE.Group();
        this._scene.add(this._cabinetGroup);

        // Material registry — referenced by panel.material name.
        // Track 1 commit 3 added `toekick` + `worktop` for the family-
        // dispatched payloads (drawer_bank, base/sink/tall/vanity,
        // worktop slabs).
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
            // Toe-kick — typically painted matte black or recessed in
            // shadow. We use near-black with high roughness to read
            // visually as "the dark gap below the cabinet".
            toekick: new THREE.MeshStandardMaterial({
                color: 0x2a2520, roughness: 0.95, metalness: 0.0,
            }),
            // Worktop — light grey quartz/Caesarstone stand-in. When
            // the canonical worktop catalog lands (Caesarstone vs
            // butcher-block vs marble), this becomes attribute-driven.
            worktop: new THREE.MeshStandardMaterial({
                color: 0xb5b0a8, roughness: 0.4, metalness: 0.05,
            }),
            blueline: new THREE.MeshBasicMaterial({
                color: 0x2b4f6b, wireframe: true,
            }),
        };

        // Resize hook.
        if (typeof ResizeObserver === "function") {
            this._resizeObserver = new ResizeObserver(() => this._fitRendererToCanvas());
            this._resizeObserver.observe(canvas);
        }

        // Initial fetch + animate. Also prime the reactivity baseline
        // so the first onWillUpdateProps sees a populated _lastValueIdsKey
        // and only fires when the user actually picks something.
        const initialSid = this._sessionIdFromRecord(this.props.record);
        this._lastSessionId = initialSid;
        this._lastValueIdsKey = this._valueIdsKey(this.props.record);
        await this._fetchAndRebuild(initialSid);
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
        const w = canvas.clientWidth || 400;
        const h = canvas.clientHeight || 400;
        this._renderer.setSize(w, h, false);
        if (this._camera) {
            this._camera.aspect = w / h;
            this._camera.updateProjectionMatrix();
        }
    }

    _dispose() {
        if (this._frameId) cancelAnimationFrame(this._frameId);
        if (this._refreshTimer) clearTimeout(this._refreshTimer);
        if (this._resizeObserver) this._resizeObserver.disconnect();
        if (this._cabinetGroup) {
            this._cabinetGroup.traverse((obj) => {
                if (obj.geometry) obj.geometry.dispose();
            });
        }
        if (this._materials) {
            for (const m of Object.values(this._materials)) m.dispose?.();
        }
        if (this._renderer) this._renderer.dispose();
    }

    // ------------------------------------------------------------------
    // Record helpers
    // ------------------------------------------------------------------

    _sessionIdFromRecord(record) {
        if (!record || !record.data) return null;
        const m2o = record.data.config_session_id;
        if (!m2o) return null;
        if (Array.isArray(m2o)) return m2o[0] || null;
        return m2o.id || m2o.resId || null;
    }

    /**
     * Produce a stable string key from record.data.value_ids that
     * changes iff the set of selected attribute values changes.
     *
     * Odoo 19 exposes x2many record data through several shapes
     * depending on the source view; we try the documented APIs in
     * order and fall back to empty-string when nothing matches
     * (which makes the early "no values yet" state stable).
     */
    _valueIdsKey(record) {
        if (!record || !record.data) return "";
        const field = record.data.value_ids;
        if (!field) return "";
        const ids =
            field.currentIds ||
            field.resIds ||
            field.ids ||
            (Array.isArray(field) ? field : null);
        if (!Array.isArray(ids)) return "";
        return ids.slice().sort((a, b) => a - b).join(",");
    }

    /**
     * Decide whether the new record state warrants a re-fetch, and
     * schedule a debounced refresh if so. Called from onWillUpdateProps
     * on every record diff.
     */
    _reactToRecord(record) {
        const sid = this._sessionIdFromRecord(record);
        if (!sid) return;
        const key = this._valueIdsKey(record);
        const sidChanged = sid !== this._lastSessionId;
        const valuesChanged = key !== this._lastValueIdsKey;
        if (!sidChanged && !valuesChanged) return;
        this._lastSessionId = sid;
        this._lastValueIdsKey = key;
        this._scheduleRefresh(sid);
    }

    /**
     * Debounce wrapper around _fetchAndRebuild. The user can step
     * through several attribute picks in <200ms; without this we'd
     * fire an RPC per pick.
     */
    _scheduleRefresh(sessionId) {
        if (this._refreshTimer) {
            clearTimeout(this._refreshTimer);
        }
        this._refreshTimer = setTimeout(() => {
            this._refreshTimer = null;
            this._fetchAndRebuild(sessionId);
        }, this._refreshDebounceMs);
    }

    // ------------------------------------------------------------------
    // Fetch + rebuild
    // ------------------------------------------------------------------

    async _fetchAndRebuild(sessionId) {
        if (!sessionId) {
            this._buildScene(null);
            return;
        }
        this._lastSessionId = sessionId;
        this.state.loading = true;
        this.state.error = null;
        try {
            const payload = await this.orm.call(
                "product.config.session",
                "get_3d_payload",
                [[sessionId]],
            );
            this._buildScene(payload);
            this.state.renderedAt = new Date().toLocaleTimeString();
        } catch (e) {
            this.state.error =
                e?.data?.message || e?.message || String(e);
        }
        this.state.loading = false;
    }

    _buildScene(payload) {
        const THREE = this._THREE;
        if (!THREE || !this._cabinetGroup) return;

        // Dispose existing geometries.
        while (this._cabinetGroup.children.length) {
            const child = this._cabinetGroup.children[0];
            this._cabinetGroup.remove(child);
            if (child.geometry) child.geometry.dispose();
        }

        if (!payload || !Array.isArray(payload.panels)) return;

        // Build each panel.
        for (const p of payload.panels) {
            const d = p.dims;
            if (!d || d.width <= 0 || d.height <= 0 || d.depth <= 0) continue;
            const geom = new THREE.BoxGeometry(d.width, d.height, d.depth);
            const matName =
                this.state.mode === "blueline" ? "blueline" : (p.material || "carcass");
            const material = this._materials[matName] || this._materials.carcass;
            const mesh = new THREE.Mesh(geom, material);
            mesh.position.set(p.pos.x, p.pos.y, p.pos.z);
            if (p.rot) {
                mesh.rotation.set(p.rot.x || 0, p.rot.y || 0, p.rot.z || 0);
            }
            this._cabinetGroup.add(mesh);
        }

        // Camera framing.
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
    // Toolbar actions
    // ------------------------------------------------------------------

    onToggleMode() {
        this.state.mode = this.state.mode === "solid" ? "blueline" : "solid";
        if (!this._cabinetGroup) return;
        const blueline = this._materials.blueline;
        this._cabinetGroup.traverse((obj) => {
            if (!obj.isMesh) return;
            if (this.state.mode === "blueline") {
                obj._solidMaterial = obj.material;
                obj.material = blueline;
            } else if (obj._solidMaterial) {
                obj.material = obj._solidMaterial;
            }
        });
    }

    async onRefresh() {
        const sid = this._sessionIdFromRecord(this.props.record);
        if (sid) await this._fetchAndRebuild(sid);
    }
}

registry.category("view_widgets").add("cabinet_viewport", {
    component: CabinetViewport,
    // fieldDependencies: list every record field the widget reads. Odoo's
    // form view uses this list to decide WHEN to re-render the widget.
    // Without value_ids here, the widget would miss attribute picks
    // (the m2m field updates on the record but the widget's prop diff
    //  never includes it). Track 1 commit 2 makes the widget reactive.
    fieldDependencies: [
        { name: "config_session_id", type: "many2one" },
        {
            name: "value_ids",
            type: "many2many",
            relation: "product.attribute.value",
        },
    ],
});
