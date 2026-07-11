/** @odoo-module **/
/**
 * Southbrook Kitchen 3D Configurator — reusable 3D canvas component.
 *
 * Rec D · Sprint 2d · Step 24c · visible-surface swap.
 *
 * The parent's <div t-ref="canvas3d"/> is gone. This component's own
 * <div t-ref="kitchenCanvas"> is now the ONLY visible 3D surface. It
 * owns:
 *   - the single WebGL context (parent's _initScene is a no-op stub)
 *   - the pointer pipeline (mousedown/move/up/leave/over on its own div)
 *   - the wheel-zoom on its own div
 *   - the camera controller (setView / animateCamera / applyOrthoFrustum)
 *   - the drop-lane visualisation
 *   - the selection highlight (post-hit + on-selected-prop-change)
 *
 * State-mutating side effects flow to the parent via 4 typed callbacks:
 *   props.onSelectItem(item)                    — cabinet click
 *   props.onMoveItem({item, x_position_in,
 *                     pinnable})                — move-drag commit
 *   props.onResizeRoom(newWidthIn, inFlight)    — room-width drag
 *   props.onResizeRoomDepth(newDepthIn, inFlight) — room-depth drag
 *   props.onViewChange(view)                    — post-setView ack
 *
 * Parent-scoped keyboard + HTML5 drop handlers reach into this
 * component via `props.onReady(api)`, which yields:
 *   api.setView(key)         — imperative view change
 *   api.zoomBy(k)            — imperative ortho zoom
 *   api.computeDropX(ev)     — floor-plane raycast for drop targets
 */

import {
    Component, onMounted, onWillUnmount, onWillUpdateProps, useRef, xml,
} from "@odoo/owl";

import { IN, P }             from "@southbrook_kitchen_3d_configurator/js/canvas/constants.esm";
import { loadThreeJS }       from "@southbrook_kitchen_3d_configurator/js/canvas/three_loader.esm";
import { initScene }         from "@southbrook_kitchen_3d_configurator/js/canvas/scene_init.esm";
import { destroyScene }      from "@southbrook_kitchen_3d_configurator/js/canvas/scene_dispose.esm";
import { installPbrEnvMap }  from "@southbrook_kitchen_3d_configurator/js/canvas/pbr_env_map.esm";
import { makeMesh }          from "@southbrook_kitchen_3d_configurator/js/canvas/mesh_factory.esm";
import { buildRoomShell }    from "@southbrook_kitchen_3d_configurator/js/canvas/room_shell.esm";
import { buildDragHandle, buildDepthHandle } from "@southbrook_kitchen_3d_configurator/js/canvas/drag_handle.esm";
import { buildDropLanes }    from "@southbrook_kitchen_3d_configurator/js/canvas/drop_lanes.esm";
import { buildBaseCabinet }  from "@southbrook_kitchen_3d_configurator/js/canvas/base_cabinet.esm";
import { buildWallCabinet }  from "@southbrook_kitchen_3d_configurator/js/canvas/wall_cabinet.esm";
import {
    buildOtherCabinet, buildFillerPanel, buildEndCapPanel,
} from "@southbrook_kitchen_3d_configurator/js/canvas/other_cabinets.esm";
import { ndcFromEvent }      from "@southbrook_kitchen_3d_configurator/js/canvas/pointer_helpers.esm";
import { computeViewSpecs }  from "@southbrook_kitchen_3d_configurator/js/canvas/view_specs.esm";
import { computeOrthoFrustum } from "@southbrook_kitchen_3d_configurator/js/canvas/ortho_frustum.esm";
import { highlightSelected } from "@southbrook_kitchen_3d_configurator/js/canvas/selection.esm";
import { computeDropXIn }    from "@southbrook_kitchen_3d_configurator/js/canvas/drop_raycaster.esm";
import { easeInOutCubic }    from "@southbrook_kitchen_3d_configurator/js/canvas/easing.esm";
import {
    setView as setViewShared,
    animateCamera as animateCameraShared,
    onWheel as onWheelShared,
} from "@southbrook_kitchen_3d_configurator/js/canvas/camera_controller.esm";
import {
    isHandleActiveView, resolveRoomWidthFromDrag, resolveRoomDepthFromDrag,
    isCabinetDragCommitted, isPinnable, cursorForPointerState,
} from "@southbrook_kitchen_3d_configurator/js/canvas/pointer_pipeline.esm";

export class KitchenCanvas extends Component {
    static template = xml`
        <div t-ref="kitchenCanvas" class="o_sbk_canvas3d"/>
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
        onResizeRoomDepth: { type: Function, optional: true },
        onViewChange:   { type: Function, optional: true },
        onReady:        { type: Function, optional: true },
    };
    static defaultProps = {
        items: [], room: {}, view: "iso",
        selected: null, draggedProduct: null, dragHover: false,
    };

    setup() {
        this.canvasRef = useRef("kitchenCanvas");
        this._currentView    = this.props.view || "iso";
        this._lastResizeWidth = null;
        this._lastResizeDepth = null;
        this._resizeObserver  = null;
        this.T = {
            THREE: null, scene: null, renderer: null,
            cameras: { ortho: null, persp: null },
            activeCamera: null, currentTarget: null,
            viewSpecs: null, vsScale: 1,
            orbit: null, raycaster: null,
            roomObjs: [], cabObjs: [], clickable: [],
            handleMesh: null, arrowMeshes: [],
            depthHandleMesh: null, depthArrowMeshes: [],
            laneMeshes: null,
            dragging: false, dragX0: 0, dragW0: 0,
            draggingDepth: false, dragY0: 0, dragD0: 0,
            animId: null, animatingCamera: false,
            movingItem: null, moveStartClient: { x: 0, y: 0 },
            moveLastX: null, moveCommitted: false,
        };
        this._onMouseDown = this._onMouseDown.bind(this);
        this._onMouseMove = this._onMouseMove.bind(this);
        this._onMouseUp   = this._onMouseUp.bind(this);
        this._onMouseOver = this._onMouseOver.bind(this);
        this._onWheel     = this._onWheel.bind(this);

        onMounted(async () => {
            // TRIPWIRE:kitchen_canvas_mount_24c
            const mount = this.canvasRef.el;
            if (!mount) return;
            const THREE = await loadThreeJS();
            this.T.THREE = THREE;
            this.T.raycaster = new THREE.Raycaster();
            Object.assign(this.T, initScene(THREE, mount, P));
            installPbrEnvMap(THREE, this.T.scene, this.T.renderer);

            const tick = () => {
                this.T.animId = requestAnimationFrame(tick);
                if (this.T.orbit && this.T.orbit.enabled) this.T.orbit.update();
                this.T.renderer.render(this.T.scene, this.T.activeCamera);
            };
            tick();

            this._resizeObserver = new ResizeObserver(() => {
                const nw = mount.clientWidth, nh = mount.clientHeight;
                if (!nw || !nh) return;
                this.T.cameras.persp.aspect = nw / nh;
                this.T.cameras.persp.updateProjectionMatrix();
                this.T.renderer.setSize(nw, nh);
                this._applyOrthoFrustum();
            });
            this._resizeObserver.observe(mount);

            mount.addEventListener("mousedown",  this._onMouseDown, { capture: true });
            mount.addEventListener("mousemove",  this._onMouseMove);
            mount.addEventListener("mouseup",    this._onMouseUp);
            mount.addEventListener("mouseleave", this._onMouseUp);
            mount.addEventListener("mousemove",  this._onMouseOver);
            mount.addEventListener("wheel",      this._onWheel, { passive: false });

            this._buildScene(this.props);

            if (this.props.onReady) {
                this.props.onReady({
                    setView: (key) => this._setView(key),
                    zoomBy:  (k)   => this._zoomBy(k),
                    computeDropX: (ev) => this._computeDropX(ev),
                });
            }
        });

        onWillUpdateProps((next) => {
            if (!this.T.scene) return;
            // In-flight drag: child is source of truth; ignore
            // prop echos from parent to avoid a re-render loop.
            if (this.T.dragging || this.T.draggingDepth || this.T.movingItem) return;

            const roomChanged = next.room !== this.props.room ||
                (next.room && this.props.room && (
                    next.room.width_in  !== this.props.room.width_in  ||
                    next.room.depth_in  !== this.props.room.depth_in  ||
                    next.room.height_in !== this.props.room.height_in));
            const itemsChanged  = next.items !== this.props.items ||
                (next.items && this.props.items &&
                 next.items.length !== this.props.items.length);
            const selChanged    = next.selected !== this.props.selected;
            const dragUiChanged = next.dragHover !== this.props.dragHover ||
                                  next.draggedProduct !== this.props.draggedProduct;
            const viewChanged   = next.view !== this._currentView;

            if (roomChanged || itemsChanged) {
                this._buildScene(next);
            } else if (selChanged) {
                highlightSelected(this.T.cabObjs, next.selected, P);
            }
            if (dragUiChanged) this._updateLaneVisibility(next);
            if (viewChanged) {
                this._currentView = next.view;
                this._setView(next.view, /*instant=*/false, /*skipCallback=*/true);
            }
        });

        onWillUnmount(() => {
            if (this.T.animId) cancelAnimationFrame(this.T.animId);
            if (this._resizeObserver) this._resizeObserver.disconnect();
            const mount = this.canvasRef.el;
            if (mount) {
                mount.removeEventListener("mousedown",  this._onMouseDown, { capture: true });
                mount.removeEventListener("mousemove",  this._onMouseMove);
                mount.removeEventListener("mouseup",    this._onMouseUp);
                mount.removeEventListener("mouseleave", this._onMouseUp);
                mount.removeEventListener("mousemove",  this._onMouseOver);
                mount.removeEventListener("wheel",      this._onWheel);
            }
            destroyScene(this.T, mount);
        });
    }

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
        this.T.arrowMeshes.forEach(m => { scene.remove(m); dispose(m); });
        if (this.T.depthHandleMesh) { scene.remove(this.T.depthHandleMesh); dispose(this.T.depthHandleMesh); }
        this.T.depthArrowMeshes.forEach(m => { scene.remove(m); dispose(m); });
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
        this.T.depthHandleMesh = null; this.T.depthArrowMeshes = [];

        const mk = (geo, color, pos, rotE, opts) =>
            makeMesh(THREE, scene, geo, color, pos, rotE, opts);

        const { objects: shellObjects } =
            buildRoomShell(THREE, scene, mk, P, rw, rh, rd);
        this.T.roomObjs.push(...shellObjects);

        const items = props.items || [];
        const knownTypes = new Set(["base", "wall", "filler", "panel"]);
        const push = ({ objects, clickable }) => {
            this.T.cabObjs.push(...objects);
            if (clickable) this.T.clickable.push(...clickable);
        };
        items.filter(it => it.cabinet_type === "base").forEach(it => push(buildBaseCabinet(THREE, mk, P, it)));
        items.filter(it => it.cabinet_type === "wall").forEach(it => push(buildWallCabinet(THREE, mk, P, it)));
        items.filter(it => !knownTypes.has(it.cabinet_type)).forEach(it => push(buildOtherCabinet(THREE, mk, P, it)));
        items.filter(it => it.cabinet_type === "filler").forEach(it => {
            this.T.cabObjs.push(buildFillerPanel(THREE, mk, P, it));
        });
        items.filter(it => it.cabinet_type === "panel").forEach(it => push(buildEndCapPanel(THREE, mk, P, it)));

        const { handleMesh, arrowMeshes } =
            buildDragHandle(THREE, scene, P, rw, rd);
        this.T.handleMesh = handleMesh;
        this.T.arrowMeshes.push(...arrowMeshes);
        const { depthHandleMesh, depthArrowMeshes } =
            buildDepthHandle(THREE, scene, P, rw, rd);
        this.T.depthHandleMesh = depthHandleMesh;
        this.T.depthArrowMeshes.push(...depthArrowMeshes);
        this.T.laneMeshes = buildDropLanes(THREE, scene, rw, rh);
        this._updateLaneVisibility(props);

        this._recomputeViews(rw, rh, rd);
        this._setView(props.view || this._currentView, /*instant=*/true, /*skipCallback=*/true);
        if (props.selected) highlightSelected(this.T.cabObjs, props.selected, P);
    }

    _updateLaneVisibility(props) {
        const lanes = this.T.laneMeshes;
        if (!lanes) return;
        const show = !!(props.dragHover && props.draggedProduct);
        const type = (props.draggedProduct && props.draggedProduct.cabinet_type) || "";
        const baseHi = (type === "base" || type === "filler");
        const wallHi = (type === "wall");
        const tallHi = (type === "tall" || type === "corner" || type === "panel");
        lanes.base.visible = show;
        lanes.wall.visible = show;
        lanes.tall.visible = show;
        if (show) {
            lanes.base.material.opacity = baseHi ? 0.42 : 0.14;
            lanes.wall.material.opacity = wallHi ? 0.42 : 0.14;
            lanes.tall.material.opacity = tallHi ? 0.42 : 0.14;
        }
    }

    _recomputeViews(rw, rh, rd) {
        this.T.viewSpecs = computeViewSpecs(this.T.THREE, rw, rh, rd);
    }

    _applyOrthoFrustum() {
        const t = this.T;
        const cam = t.cameras?.ortho;
        if (!cam || !t.renderer) return;
        const spec = t.viewSpecs?.[this._currentView];
        const f = computeOrthoFrustum(
            spec && spec.vs, t.vsScale,
            t.renderer.domElement.width,
            t.renderer.domElement.height,
        );
        cam.left = f.left; cam.right = f.right;
        cam.top  = f.top;  cam.bottom = f.bottom;
        cam.near = f.near; cam.far    = f.far;
        cam.updateProjectionMatrix();
    }

    _setView(key, instant = false, skipCallback = false) {
        if (!this.T.viewSpecs || !this.T.viewSpecs[key]) return;
        this._currentView = key;
        const ok = setViewShared(this.T, key, {
            instant,
            applyOrthoFrustum: () => this._applyOrthoFrustum(),
            animateCamera: (p, tgt, up, ms) => this._animateCamera(p, tgt, up, ms),
        });
        if (ok && !skipCallback && this.props.onViewChange) {
            this.props.onViewChange(key);
        }
    }

    _animateCamera(toPos, toTarget, toUp, ms = 400) {
        animateCameraShared(
            this.T, toPos, toTarget, toUp, ms,
            easeInOutCubic, requestAnimationFrame,
        );
    }

    _onWheel(e) { onWheelShared(this.T, e, () => this._applyOrthoFrustum()); }

    _zoomBy(k) {
        this.T.vsScale = Math.max(0.3, Math.min(3.0, (this.T.vsScale || 1) * k));
        this._applyOrthoFrustum();
    }

    _ndcFromEvent(ev) { return ndcFromEvent(ev, this.canvasRef.el); }

    _computeDropX(ev) {
        return computeDropXIn(
            this.T.THREE, this.T.activeCamera, this.T.raycaster,
            this._ndcFromEvent(ev),
            (this.props.room && this.props.room.width_in) || 0,
        );
    }

    _onMouseDown(e) {
        const { activeCamera, raycaster, handleMesh, depthHandleMesh, clickable } = this.T;
        if (!activeCamera || !raycaster) return;
        raycaster.setFromCamera(this._ndcFromEvent(e), activeCamera);

        const handleActive = isHandleActiveView(this._currentView);
        if (handleActive && handleMesh && raycaster.intersectObject(handleMesh).length) {
            this.T.dragging = true;
            this.T.dragX0   = e.clientX;
            this.T.dragW0   = (this.props.room && this.props.room.width_in) || 0;
            this._lastResizeWidth = null;
            e.preventDefault();
            return;
        }
        if (handleActive && depthHandleMesh && raycaster.intersectObject(depthHandleMesh).length) {
            this.T.draggingDepth = true;
            this.T.dragY0   = e.clientY;
            this.T.dragD0   = (this.props.room && this.props.room.depth_in) || 0;
            this._lastResizeDepth = null;
            e.preventDefault();
            return;
        }

        const hits = raycaster.intersectObjects(clickable, false);
        if (hits.length) {
            const h = hits[0].object;
            if (h.userData?.item) {
                if (this.props.onSelectItem) this.props.onSelectItem(h.userData.item);
                if (h.userData.item.cabinet_type !== "filler") {
                    this.T.movingItem      = h.userData.item;
                    this.T.moveStartClient = { x: e.clientX, y: e.clientY };
                    this.T.moveLastX       = h.userData.item.x_position_in;
                    this.T.moveCommitted   = false;
                    e.preventDefault();
                    e.stopPropagation();
                }
            }
        }
    }

    _onMouseMove(e) {
        if (this.T.dragging) {
            const nw = resolveRoomWidthFromDrag(e.clientX, this.T.dragX0, this.T.dragW0);
            if (nw !== this._lastResizeWidth) {
                this._lastResizeWidth = nw;
                if (this.props.onResizeRoom) this.props.onResizeRoom(nw, /*inFlight=*/true);
            }
            return;
        }

        if (this.T.draggingDepth) {
            const nd = resolveRoomDepthFromDrag(e.clientY, this.T.dragY0, this.T.dragD0);
            if (nd !== this._lastResizeDepth) {
                this._lastResizeDepth = nd;
                if (this.props.onResizeRoomDepth) this.props.onResizeRoomDepth(nd, /*inFlight=*/true);
            }
            return;
        }

        if (this.T.movingItem) {
            if (!this.T.moveCommitted &&
                !isCabinetDragCommitted(this.T.moveStartClient, e)) return;
            if (!this.T.moveCommitted) {
                this.T.moveCommitted = true;
                const cvs = this.T.renderer && this.T.renderer.domElement;
                if (cvs) cvs.style.cursor = "move";
            }
            const targetX = this._computeDropX(e);
            if (targetX == null) return;
            if (this.T.movingItem.x_position_in === targetX) return;
            this.T.movingItem.x_position_in = targetX;
            this.T.moveLastX = targetX;
            this._buildScene(this.props);
        }
    }

    _onMouseUp() {
        if (this.T.dragging) {
            this.T.dragging = false;
            const finalNw = this._lastResizeWidth ??
                ((this.props.room && this.props.room.width_in) || 0);
            this._lastResizeWidth = null;
            if (this.props.onResizeRoom) this.props.onResizeRoom(finalNw, /*inFlight=*/false);
        }
        if (this.T.draggingDepth) {
            this.T.draggingDepth = false;
            const finalNd = this._lastResizeDepth ??
                ((this.props.room && this.props.room.depth_in) || 0);
            this._lastResizeDepth = null;
            if (this.props.onResizeRoomDepth) this.props.onResizeRoomDepth(finalNd, /*inFlight=*/false);
        }
        if (this.T.movingItem) {
            const item = this.T.movingItem;
            const wasCommitted = this.T.moveCommitted;
            this.T.movingItem    = null;
            this.T.moveCommitted = false;
            const cvs = this.T.renderer && this.T.renderer.domElement;
            if (cvs) cvs.style.cursor = "";
            if (wasCommitted && this.props.onMoveItem) {
                this.props.onMoveItem({
                    item,
                    x_position_in: item.x_position_in,
                    pinnable:      isPinnable(item.cabinet_type),
                });
            }
        }
    }

    _onMouseOver(e) {
        const mount = this.canvasRef.el;
        if (!mount || !this.T.activeCamera || !this.T.raycaster) return;
        if (this.T.movingItem && this.T.moveCommitted) return;
        this.T.raycaster.setFromCamera(this._ndcFromEvent(e), this.T.activeCamera);
        const handleActive = isHandleActiveView(this._currentView);
        const onHandle = handleActive && this.T.handleMesh &&
            this.T.raycaster.intersectObject(this.T.handleMesh).length > 0;
        const onDepthHandle = !onHandle && handleActive && this.T.depthHandleMesh &&
            this.T.raycaster.intersectObject(this.T.depthHandleMesh).length > 0;
        const onCabinet = !onHandle && !onDepthHandle &&
            this.T.raycaster.intersectObjects(this.T.clickable, false).length > 0;
        const cvs = this.T.renderer?.domElement;
        if (cvs) cvs.style.cursor = cursorForPointerState({
            dragging: this.T.dragging, draggingDepth: this.T.draggingDepth,
            onHandle, onDepthHandle, onCabinet,
        });
    }
}
