/** @odoo-module **/
/**
 * Southbrook Kitchen 3D Configurator — reusable 3D canvas component.
 *
 * Rec D · Sprint 2d · Step 24b · hidden-sibling mount.
 *
 * 24b materialises a live Three.js scene from props into an off-
 * screen div (display:none + position:absolute; left:-9999px) so
 * the parent's <div t-ref="canvas3d"/> remains the visible surface.
 * Two WebGLRenderers now run side-by-side: each owns its own
 * THREE.WebGLRenderer instance (no shared singleton) so parent's
 * hit-testing is unaffected. Pointer, camera, selection, and
 * lane visibility helpers land in 24c-e once the visible surface
 * swaps.
 */

import {
    Component, onMounted, onWillUnmount, onWillUpdateProps, useRef, xml,
} from "@odoo/owl";

// ── Canvas helpers — all with .esm suffix (Sprint 2d rollback fix). ──
import { IN, P }             from "@southbrook_kitchen_3d_configurator/js/canvas/constants.esm";
import { loadThreeJS }       from "@southbrook_kitchen_3d_configurator/js/canvas/three_loader.esm";
import { initScene }         from "@southbrook_kitchen_3d_configurator/js/canvas/scene_init.esm";
import { destroyScene }      from "@southbrook_kitchen_3d_configurator/js/canvas/scene_dispose.esm";
import { installPbrEnvMap }  from "@southbrook_kitchen_3d_configurator/js/canvas/pbr_env_map.esm";
import { makeMesh }          from "@southbrook_kitchen_3d_configurator/js/canvas/mesh_factory.esm";
import { buildRoomShell }    from "@southbrook_kitchen_3d_configurator/js/canvas/room_shell.esm";
import { buildDragHandle }   from "@southbrook_kitchen_3d_configurator/js/canvas/drag_handle.esm";
import { buildDropLanes }    from "@southbrook_kitchen_3d_configurator/js/canvas/drop_lanes.esm";
import { buildBaseCabinet }  from "@southbrook_kitchen_3d_configurator/js/canvas/base_cabinet.esm";
import { buildWallCabinet }  from "@southbrook_kitchen_3d_configurator/js/canvas/wall_cabinet.esm";
import {
    buildOtherCabinet, buildFillerPanel, buildEndCapPanel,
} from "@southbrook_kitchen_3d_configurator/js/canvas/other_cabinets.esm";

/**
 * @typedef {Object} KitchenCanvasProps
 * @property {Array}   items
 * @property {Object}  room
 * @property {string}  view
 * @property {Object?} selected
 * @property {Object?} draggedProduct
 * @property {boolean} dragHover
 * @property {Function} onSelectItem
 * @property {Function} onMoveItem
 * @property {Function} onResizeRoom
 * @property {Function} onViewChange
 */

export class KitchenCanvas extends Component {
    static template = xml`
        <div t-ref="kitchenCanvas" class="o_sbk_kitchen_canvas"
             style="display:none; width:400px; height:300px; position:absolute; top:0; left:-9999px;"/>
    `;
    static props = {
        items:          { type: Array, optional: true },
        room:           { type: Object, optional: true },
        view:           { type: String, optional: true },
        selected:       { type: [Object, { value: null }], optional: true },
        draggedProduct: { type: [Object, { value: null }], optional: true },
        dragHover:      { type: Boolean, optional: true },
        onSelectItem:   { type: Function, optional: true },
        onMoveItem:     { type: Function, optional: true },
        onResizeRoom:   { type: Function, optional: true },
        onViewChange:   { type: Function, optional: true },
    };
    static defaultProps = {
        items: [],
        room: {},
        view: "iso",
        selected: null,
        draggedProduct: null,
        dragHover: false,
    };

    setup() {
        this.canvasRef = useRef("kitchenCanvas");
        // Mirror the parent's T bag so shared helpers can be pointed
        // at it verbatim in 24c-e.
        this.T = {
            THREE: null, scene: null, renderer: null,
            cameras: { ortho: null, persp: null },
            activeCamera: null, currentTarget: null,
            viewSpecs: null, vsScale: 1,
            orbit: null, raycaster: null,
            roomObjs: [], cabObjs: [], clickable: [],
            handleMesh: null, arrowMeshes: [],
            laneMeshes: null,
            animId: null,
        };

        onMounted(async () => {
            // TRIPWIRE:kitchen_canvas_mount
            const mount = this.canvasRef.el;
            if (!mount) return;
            const THREE = await loadThreeJS();
            this.T.THREE = THREE;
            this.T.raycaster = new THREE.Raycaster();
            // Each child renderer is its own WebGL context — never
            // shared with the parent. Chrome caps ~8-16 contexts per
            // page; two is well within budget.
            Object.assign(this.T, initScene(THREE, mount, P));
            installPbrEnvMap(THREE, this.T.scene, this.T.renderer);
            // Independent animation loop; parent's tick is untouched.
            const tick = () => {
                this.T.animId = requestAnimationFrame(tick);
                if (this.T.orbit && this.T.orbit.enabled) this.T.orbit.update();
                this.T.renderer.render(this.T.scene, this.T.activeCamera);
            };
            tick();
            this._buildScene(this.props);
        });

        onWillUpdateProps((next) => {
            if (!this.T.scene) return;
            // Identity-compare items/room refs — parent mutates arrays
            // by re-assignment in _refreshLayout, so ref-check is sound.
            const roomChanged  = next.room  !== this.props.room;
            const itemsChanged = next.items !== this.props.items;
            if (roomChanged || itemsChanged) this._buildScene(next);
        });

        onWillUnmount(() => {
            if (this.T.animId) cancelAnimationFrame(this.T.animId);
            destroyScene(this.T, this.canvasRef.el);
        });
    }

    // Mirrors the parent's _buildScene enough to prove the child can
    // materialise a valid scene from the read-only prop snapshot.
    // NB: no _savePinnedPosition, no RPC, no state mutation — parent
    // still owns every side effect in 24b.
    _buildScene(props) {
        const { THREE, scene } = this.T;
        if (!scene) return;

        const room = props.room || {};
        const rw = (room.width_in  || 12) * IN;
        const rd = (room.depth_in  || 24) * IN;
        const rh = (room.height_in || 96) * IN;

        const dispose = (n) => {
            if (!n) return;
            if (n.geometry) n.geometry.dispose();
            if (n.material) {
                if (Array.isArray(n.material)) n.material.forEach(x => x.dispose());
                else n.material.dispose();
            }
        };
        [...this.T.roomObjs, ...this.T.cabObjs].forEach(m => {
            if (m && typeof m.traverse === "function") m.traverse(dispose);
            else dispose(m);
            scene.remove(m);
        });
        if (this.T.handleMesh) { scene.remove(this.T.handleMesh); dispose(this.T.handleMesh); }
        if (this.T.laneMeshes) {
            for (const k of ["base", "wall", "tall"]) {
                const m = this.T.laneMeshes[k];
                if (!m) continue;
                scene.remove(m); dispose(m);
            }
            this.T.laneMeshes = null;
        }
        this.T.roomObjs = []; this.T.cabObjs = []; this.T.clickable = [];
        this.T.handleMesh = null; this.T.arrowMeshes = [];

        const mk = (geo, color, pos, rotE, opts) =>
            makeMesh(THREE, scene, geo, color, pos, rotE, opts);

        const { objects: shellObjects } =
            buildRoomShell(THREE, scene, mk, P, rw, rh, rd);
        this.T.roomObjs.push(...shellObjects);

        const items = props.items || [];
        const known = new Set(["base", "wall", "filler", "panel"]);
        const push = ({ objects, clickable }) => {
            this.T.cabObjs.push(...objects);
            if (clickable) this.T.clickable.push(...clickable);
        };
        items.filter(it => it.cabinet_type === "base").forEach(it => push(buildBaseCabinet(THREE, mk, P, it)));
        items.filter(it => it.cabinet_type === "wall").forEach(it => push(buildWallCabinet(THREE, mk, P, it)));
        items.filter(it => !known.has(it.cabinet_type)).forEach(it => push(buildOtherCabinet(THREE, mk, P, it)));
        items.filter(it => it.cabinet_type === "filler").forEach(it => {
            this.T.cabObjs.push(buildFillerPanel(THREE, mk, P, it));
        });
        items.filter(it => it.cabinet_type === "panel").forEach(it => push(buildEndCapPanel(THREE, mk, P, it)));

        const { handleMesh, arrowMeshes } =
            buildDragHandle(THREE, scene, P, rw, rd);
        this.T.handleMesh = handleMesh;
        this.T.arrowMeshes.push(...arrowMeshes);
        this.T.laneMeshes = buildDropLanes(THREE, scene, rw, rh);
    }
}
