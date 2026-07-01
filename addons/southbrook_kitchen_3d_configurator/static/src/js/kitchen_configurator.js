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

// Rec D · Sprint 2d · Step 1 · shared canvas constants.
// Values are identical to the pre-2d inline block (kept verbatim);
// the file just moved so future <KitchenCanvas> can import the
// same palette + sizing without duplicating.
import {
    IN, BW, BH, BD, WW, WH, WD, CTR, GAP, WBY, P,
} from "@southbrook_kitchen_3d_configurator/js/canvas/constants.esm";
import { loadThreeJS } from "@southbrook_kitchen_3d_configurator/js/canvas/three_loader.esm";
import { ndcFromEvent } from "@southbrook_kitchen_3d_configurator/js/canvas/pointer_helpers.esm";
import { computeViewSpecs } from "@southbrook_kitchen_3d_configurator/js/canvas/view_specs.esm";
import { makeMesh } from "@southbrook_kitchen_3d_configurator/js/canvas/mesh_factory.esm";
import { packRow } from "@southbrook_kitchen_3d_configurator/js/canvas/pack_row.esm";
import { easeInOutCubic } from "@southbrook_kitchen_3d_configurator/js/canvas/easing.esm";
import { computeOrthoFrustum } from "@southbrook_kitchen_3d_configurator/js/canvas/ortho_frustum.esm";
import { highlightSelected } from "@southbrook_kitchen_3d_configurator/js/canvas/selection.esm";
import { computeDropXIn } from "@southbrook_kitchen_3d_configurator/js/canvas/drop_raycaster.esm";
import { buildRoomShell } from "@southbrook_kitchen_3d_configurator/js/canvas/room_shell.esm";
import { buildDragHandle } from "@southbrook_kitchen_3d_configurator/js/canvas/drag_handle.esm";
import { buildDropLanes } from "@southbrook_kitchen_3d_configurator/js/canvas/drop_lanes.esm";
import { installPbrEnvMap } from "@southbrook_kitchen_3d_configurator/js/canvas/pbr_env_map.esm";
import { buildBaseCabinet } from "@southbrook_kitchen_3d_configurator/js/canvas/base_cabinet.esm";
import { buildWallCabinet } from "@southbrook_kitchen_3d_configurator/js/canvas/wall_cabinet.esm";
import {
    buildOtherCabinet, buildFillerPanel, buildEndCapPanel,
} from "@southbrook_kitchen_3d_configurator/js/canvas/other_cabinets.esm";
import { initScene } from "@southbrook_kitchen_3d_configurator/js/canvas/scene_init.esm";
import { destroyScene } from "@southbrook_kitchen_3d_configurator/js/canvas/scene_dispose.esm";
import {
    setView as setViewShared,
    animateCamera as animateCameraShared,
    onWheel as onWheelShared,
} from "@southbrook_kitchen_3d_configurator/js/canvas/camera_controller.esm";
import {
    isHandleActiveView,
    resolveRoomWidthFromDrag,
    isCabinetDragCommitted,
    isPinnable,
    cursorForPointerState,
} from "@southbrook_kitchen_3d_configurator/js/canvas/pointer_pipeline.esm";

const actionRegistry = registry.category("actions");

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
            error:     "",
            errorCode: "",
            errorCta:  null,
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
            // D1 — multi-view camera system. 'iso' default; switchable
            // among iso/top/front/left/right/persp. Hotkeys 1-6 + R reset.
            view:      "iso",
            // D3 — partner-driven channel pricelist. partnerId is set
            // from props (when opened from a design with a customer)
            // or stays null (configurator opened standalone). channel
            // meta is populated by the first /products + /layout RPC
            // response and drives the topbar badge.
            partnerId: this.props.partner_id || null,
            channel:   {
                partner_name:    "",
                channel:         "retail",
                channel_label:   "Retail",
                pricelist_name:  "",
                currency_symbol: "$",
            },
            // D5 — debounced auto-save state. autoSaving renders the
            // tiny "Saving..." pill; lastAutoSaveAt feeds the "Saved
            // <Xs> ago" hint.
            autoSaving:      false,
            lastAutoSaveAt:  0,
            // D7 — filler placement strategy. Drives /layout on each
            // refresh; default matches the controller default ("split"
            // — half-width fillers at both ends, most common spec).
            fillerStrategy:  this.props.filler_strategy || "split",
            // D8 — wall-cab Z alignment + soffit height. Defaults match
            // the model defaults so an unsaved design still computes
            // sensible wall-cab positions.
            wallCabTopAlignment: this.props.wall_cab_top_alignment || "fixed_gap",
            soffitHeightIn:      this.props.soffit_height_in       || 84.0,
            warnings:            [],
            // D13 — searchable inventory + drag-and-drop add.
            inventorySearch: "",
            // Category filter pill selection. Values: "all" |
            // "base" | "wall" | "tall" | "panels". Tab click toggles
            // this; _filteredProducts() applies it BEFORE the search
            // filter so users can narrow to "wall" then type a size.
            inventoryCategory: "all",
            dragHover:       false,
            // D16 — Track which product is being dragged from the
            // inventory so the canvas can highlight the matching
            // drop-lane. HTML5 dragover events don't expose
            // dataTransfer payloads (only types) for security, so we
            // stash the product on dragstart / clear on dragend|drop.
            draggedProduct:  null,
        });
        // Auto-save debounce timer (not reactive; managed imperatively).
        this._autoSaveTimer = null;

        // ── Three.js scene state (not reactive — managed imperatively) ────────
        // D1 — `camera` is now `activeCamera`, swapped between the two
        // instances on `cameras`. `currentTarget` is the live lookAt
        // point so view transitions can lerp from where we are.
        this.T = {
            THREE: null, scene: null, renderer: null,
            cameras: { ortho: null, persp: null },
            activeCamera: null,
            currentTarget: null,
            viewSpecs: null,    // dict of {iso, top, front, left, right, persp} → {pos, target, up}
            vsScale:   1,       // ortho zoom multiplier (wheel)
            orbit:     null,    // OrbitControls instance (persp only)
            raycaster: null,
            roomObjs: [], cabObjs: [], clickable: [],
            handleMesh: null, arrowMeshes: [],
            // D16 — Per-zone drop lanes (visible during drag)
            laneMeshes: null,
            dragging: false, dragX0: 0, dragW0: 0,
            animId: null,
            animatingCamera: false,
            // D15 — Drag-to-reposition existing cabinets
            movingItem:      null,
            moveStartClient: { x: 0, y: 0 },
            moveLastX:       null,
            moveCommitted:   false,
        };

        this._onMouseDown = this._onMouseDown.bind(this);
        this._onMouseMove = this._onMouseMove.bind(this);
        this._onMouseUp   = this._onMouseUp.bind(this);
        this._onMouseOver = this._onMouseOver.bind(this);
        this._onWheel     = this._onWheel.bind(this);
        this._onKeyDown   = this._onKeyDown.bind(this);

        // ── Lifecycle ─────────────────────────────────────────────────────────
        onWillStart(async () => {
            const [THREE] = await Promise.all([
                loadThreeJS(),
                this._loadProducts(),
                this._loadUserDefaults(),
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
    // ─── D4 — sticky per-user room defaults ─────────────────────────────────────
    // Reads the user's saved defaults. If the configurator was opened
    // without a design_id or pre-set room dims, prefill the room
    // inputs so the rep doesn't retype 192/144/96 on every new design.
    async _loadUserDefaults() {
        try {
            const d = await rpc("/southbrook_kitchen/configurator/user_defaults", {
                save: false,
            });
            this._userDefaults = d;
            const hasExplicitProps = !!(this.props.room_width_in
                                    || this.props.room_depth_in
                                    || this.props.room_height_in
                                    || this.props.design_id);
            if (!hasExplicitProps && d) {
                if (d.width  > 0) this.state.room.width_in  = d.width;
                if (d.depth  > 0) this.state.room.depth_in  = d.depth;
                if (d.height > 0) this.state.room.height_in = d.height;
            }
        } catch (_) {
            this._userDefaults = null;
        }
    }

    async _saveAsMyDefault() {
        try {
            await rpc("/southbrook_kitchen/configurator/user_defaults", {
                save:   true,
                width:  this.state.room.width_in,
                depth:  this.state.room.depth_in,
                height: this.state.room.height_in,
            });
            this.notification.add("Saved as your default room size.", { type: "success" });
        } catch (e) {
            this.notification.add("Couldn't save default: " + (e.message || e), { type: "danger" });
        }
    }

    async _loadProducts() {
        try {
            const resp = await rpc("/southbrook_kitchen/configurator/products", {
                partner_id: this.state.partnerId || false,
            });
            // D3 — response is now {channel, products}; handle the
            // legacy bare-array shape too for forward-compat.
            if (Array.isArray(resp)) {
                this.state.products = resp;
            } else {
                this.state.products = resp.products || [];
                if (resp.channel) this.state.channel = resp.channel;
            }
        } catch (_) {
            this.state.products = [];
        }
    }

    async _refreshLayout() {
        try {
            const result = await rpc("/southbrook_kitchen/configurator/layout", {
                room_width_in:           this.state.room.width_in,
                room_depth_in:           this.state.room.depth_in,
                room_height_in:          this.state.room.height_in,
                partner_id:              this.state.partnerId || false,
                filler_strategy:         this.state.fillerStrategy || "split",
                wall_cab_top_alignment:  this.state.wallCabTopAlignment || "fixed_gap",
                soffit_height_in:        this.state.soffitHeightIn || 84.0,
            });
            this.state.error      = result.error || "";
            this.state.errorCode  = result.error_code || "";
            this.state.errorCta   = result.error_cta || null;
            this.state.items      = result.items  || [];
            this.state.summary    = result.summary || this.state.summary;
            this.state.warnings   = result.warnings || [];
            if (result.channel) this.state.channel = result.channel;
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
        this._queueAutoSave();    // D5
    }

    async _stretchWidth(delta) {
        this.state.room.width_in = Math.max(12, this.state.room.width_in + delta);
        await this._refreshLayout();
        this._queueAutoSave();    // D5
    }

    // D7 — Change the filler placement strategy + re-emit the layout.
    async _changeFillerStrategy(value) {
        const allowed = ["split", "left", "right", "scribe"];
        const v = (value || "").toLowerCase();
        if (!allowed.includes(v)) return;
        this.state.fillerStrategy = v;
        await this._refreshLayout();
        this._queueAutoSave();
    }

    // D8 — Wall-cab top alignment selector. Re-runs layout so the
    // wall cabinets snap to the chosen mode immediately.
    async _changeWallAlignment(value) {
        const allowed = ["fixed_gap", "to_ceiling", "to_soffit"];
        const v = (value || "").toLowerCase();
        if (!allowed.includes(v)) return;
        this.state.wallCabTopAlignment = v;
        await this._refreshLayout();
        this._queueAutoSave();
    }

    async _changeSoffit(rawValue) {
        const v = parseFloat(rawValue);
        if (!Number.isFinite(v) || v < 36 || v > 144) return;
        this.state.soffitHeightIn = v;
        // Only re-emit if the alignment actually consults soffit.
        if (this.state.wallCabTopAlignment === "to_soffit") {
            await this._refreshLayout();
        }
        this._queueAutoSave();
    }

    // D7 — Apply the server's snap hint: round room width to the
    // nearest module-clean value to eliminate the filler.
    async _applySnapHint() {
        const hint = this.state.summary && this.state.summary.snap_hint;
        if (!hint || !hint.target_width) return;
        this.state.room.width_in = hint.target_width;
        await this._refreshLayout();
        this._queueAutoSave();
    }

    _selectCabinet(item) {
        this.state.selected = item;
        this._highlightSelected(item);
    }

    // ─── D13 — Searchable inventory + drag-and-drop add ─────────────────────────
    // Category tabs first, then case-insensitive text search across
    // name / SKU / cabinet type / material / door-style. Both empty →
    // full catalog. INVENTORY_CATEGORY_MAP maps each tab key to the
    // cabinet_type values it should include; keeping the map next to
    // the filter keeps the tab UI and the data contract in one place.
    _inventoryCategoryTypes(key) {
        return ({
            all:      null,   // null = passthrough (no cabinet_type filter)
            base:     ["base"],
            wall:     ["wall"],
            tall:     ["tall", "corner"],
            panels:   ["filler", "panel"],
        })[key] || null;
    }

    _productsByCategory(key) {
        const types = this._inventoryCategoryTypes(key);
        const list = this.state.products || [];
        if (!types) return list;
        return list.filter(p => types.includes(p.cabinet_type));
    }

    _filteredProducts() {
        const q = (this.state.inventorySearch || "").toLowerCase().trim();
        const list = this._productsByCategory(this.state.inventoryCategory || "all");
        if (!q) return list;
        return list.filter(p =>
            (p.name && p.name.toLowerCase().includes(q)) ||
            (p.sku && p.sku.toLowerCase().includes(q)) ||
            (p.cabinet_type && p.cabinet_type.toLowerCase().includes(q)) ||
            (p.material && p.material.toLowerCase().includes(q)) ||
            (p.door_style && p.door_style.toLowerCase().includes(q))
        );
    }

    // Tab count badges — only compute against the raw catalog so a
    // typed search doesn't shrink the visible tab counts.
    _categoryCount(key) {
        return this._productsByCategory(key).length;
    }

    _setInventoryCategory(key) {
        this.state.inventoryCategory = key;
    }

    _onSearchInput(ev) {
        this.state.inventorySearch = ev.target.value || "";
    }

    _clearSearch() {
        this.state.inventorySearch = "";
    }

    // Drag-from-inventory: stash the product_id in dataTransfer so the
    // canvas drop handler can resolve it. text/plain mirror for older
    // browsers + Safari quirks. D16 — also stash the full product on
    // component state so the lane-highlight code knows which type is
    // mid-drag (dataTransfer.getData isn't readable during dragover).
    _onProductDragStart(ev, product) {
        if (!ev.dataTransfer) return;
        ev.dataTransfer.effectAllowed = "copy";
        ev.dataTransfer.setData(
            "application/x-sbk-product",
            JSON.stringify({ product_id: product.product_id })
        );
        ev.dataTransfer.setData("text/plain", String(product.product_id));
        this.state.draggedProduct = product;
        this._updateLaneVisibility();
    }

    // D16 — Clear the dragged-product state when the gesture ends
    // (drop succeeded OR user released outside any drop target).
    _onProductDragEnd(_ev) {
        this.state.draggedProduct = null;
        this.state.dragHover      = false;
        this._updateLaneVisibility();
    }

    // Allow drop on the canvas wrapper. preventDefault is mandatory or
    // browsers default to "no-drop".
    _onCanvasDragOver(ev) {
        if (!ev.dataTransfer) return;
        ev.preventDefault();
        ev.dataTransfer.dropEffect = "copy";
        if (!this.state.dragHover) {
            this.state.dragHover = true;
            this._updateLaneVisibility();
        }
    }

    _onCanvasDragLeave(ev) {
        // Only clear when the cursor truly leaves the canvas wrapper
        // (children fire dragleave when crossing internal elements).
        if (ev.currentTarget && ev.currentTarget.contains(ev.relatedTarget)) return;
        this.state.dragHover = false;
        this._updateLaneVisibility();
    }

    _onCanvasDrop(ev) {
        ev.preventDefault();
        this.state.dragHover     = false;
        this.state.draggedProduct = null;
        this._updateLaneVisibility();
        let pid = null;
        try {
            const raw = ev.dataTransfer.getData("application/x-sbk-product");
            if (raw) pid = JSON.parse(raw).product_id;
            else     pid = parseInt(ev.dataTransfer.getData("text/plain"), 10);
        } catch (_) {
            return;
        }
        if (!Number.isFinite(pid) || pid <= 0) return;
        const product = (this.state.products || []).find(p => p.product_id === pid);
        if (!product) return;
        // D14 — raycast the drop point to the floor plane so the new
        // cabinet lands where the user dropped it (not always at the
        // end of the run). Falls back to end-of-run if the ray misses
        // the floor (e.g. dropping in empty sky area of perspective view).
        const dropX = this._computeDropX(ev);
        this._addCabinetFromProduct(product, dropX);
    }

    // D16 — Show / hide the per-zone drop lanes and brighten the lane
    // matching the dragged product's cabinet_type. Called from each
    // drag-state mutation; no requestAnimationFrame needed because
    // the scene's tick loop redraws every frame regardless.
    _updateLaneVisibility() {
        const lanes = this.T.laneMeshes;
        if (!lanes) return;
        const show  = !!(this.state.dragHover && this.state.draggedProduct);
        const type  = (this.state.draggedProduct && this.state.draggedProduct.cabinet_type) || "";
        // Bright opacity for the matching lane, dim for the others
        // so the rep gets immediate "this goes here" feedback even
        // before they release.
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

    // D14 — Cast a ray from the active camera through the drop point
    // and intersect the floor plane (Y=0) in world space, then convert
    // back to inches and snap to the 6" grid. Returns null when the
    // ray doesn't hit the floor (e.g. the cursor was over the sky in
    // a perspective view tilted upward).
    // Rec D · Sprint 2d step 10 — thin wrapper delegating to the
    // shared raycast helper so <KitchenCanvas> can compute drop-X
    // from any camera + raycaster + ndc + room-width pair.
    _computeDropX(ev) {
        const t = this.T;
        return computeDropXIn(
            t.THREE, t.activeCamera, t.raycaster,
            this._ndcFromEvent(ev),
            this.state.room.width_in,
        );
    }

    // Generic add — used by drop AND by a future "click to add" button.
    // D14 — `targetX` (inches) sets the new item's sort-key so it
    // slots in at the dropped position. _recomputeLayoutFromItems
    // then sorts-by-x and re-packs contiguously: visual semantic is
    // "where in the run order does this go". `null` = append at end.
    _addCabinetFromProduct(product, targetX = null) {
        const type = product.cabinet_type || "base";
        // Default Z: walls track the configured wall Z; everything
        // else sits on the floor.
        let z = 0;
        if (type === "wall") {
            // Use the most recent z_position_in we saw from the server
            // so the wall cab tracks D8's alignment mode without
            // re-running /layout.
            const walls = (this.state.items || []).filter(it => it.cabinet_type === "wall");
            z = (walls.length && walls[0].z_position_in) || (34.5 + 1.5 + 18.0);
        }
        // Unique layout_key (timestamp + random tail = collision-free).
        const layoutKey = `${type}-add-${Date.now()}-${Math.floor((performance.now() % 1) * 10000)}`;
        // D14 — when a targetX is supplied, use it as the cascade
        // sort-key so the new cabinet lands at that ordered position.
        // No-target case retains the 1e6 sentinel so the cabinet
        // appends at the end of its group.
        let sortX = (typeof targetX === "number" && !Number.isNaN(targetX))
                    ? targetX : 1e6;

        // Panel-placement rule (2026-07-01): end cap decorative panels
        // (cabinet_type === "panel") must snap to the exposed side face
        // of an existing cabinet, NEVER land at the wall edge that the
        // tails-loop sentinel would place them at. Default: right side
        // of the rightmost base cabinet (fallback to wall cabinet, then
        // 0 if no cabinets yet).
        if (type === "panel"
                && (typeof targetX !== "number" || Number.isNaN(targetX))) {
            const hosts = (this.state.items || []).filter(
                it => it.cabinet_type === "base"
                   || it.cabinet_type === "wall");
            if (hosts.length) {
                const sorted = hosts.slice().sort(
                    (a, b) => (a.x_position_in || 0) - (b.x_position_in || 0));
                const last = sorted[sorted.length - 1];
                sortX = (last.x_position_in || 0) + (last.width_in || 0);
            } else {
                sortX = 0;   // no host cabinet yet — start at left origin
            }
            // Base end caps sit on the floor; wall end caps track wall Z.
            // Product data drives z via product.z_position_in when set.
        }
        const newItem = {
            ...product,
            layout_key:    layoutKey,
            x_position_in: sortX,
            y_position_in: 0,
            z_position_in: z,
            width_in:      product.width_in || 24,
            height_in:     product.height_in || (type === "wall" ? 30 : 34.5),
            depth_in:      product.depth_in  || (type === "wall" ? 12 : 24),
        };
        this.state.items = [...(this.state.items || []), newItem];
        this.state.selected = newItem;
        this._recomputeLayoutFromItems();
        // Room width may now be short. Auto-extend so the new cabinet
        // is visible (no scrolling around an off-canvas insert).
        const required = this._currentRunWidthIn();
        if (required > this.state.room.width_in) {
            this.state.room.width_in = Math.ceil(required / 6) * 6;
        }
        if (this.T.scene) this._buildScene();
        // D14 — Drop UX feedback: tell the rep WHERE it landed when
        // they used drop-positioning (vs the bare "Added X" toast).
        if (typeof targetX === "number" && !Number.isNaN(targetX)) {
            const finalX = newItem.x_position_in;
            this.notification.add(
                `Added ${product.name} at ${finalX}″`,
                { type: "success" }
            );
        } else {
            this.notification.add(`Added ${product.name}`, { type: "success" });
        }
        this._queueAutoSave();
    }

    // Total inches consumed by the longest cabinet row (max of base
    // run / wall run / extras). Used to auto-extend room width on add.
    _currentRunWidthIn() {
        const items = this.state.items || [];
        const by = {};
        for (const it of items) {
            const t = it.cabinet_type || "other";
            by[t] = (by[t] || 0) + (it.width_in || 0);
        }
        // Bases + extras pack on the floor row; walls pack on the upper row.
        const floorRow = (by.base || 0) + (by.filler || 0) + (by.tall || 0)
                       + (by.panel || 0) + (by.corner || 0) + (by.other || 0);
        const wallRow  = (by.wall || 0);
        return Math.max(floorRow, wallRow);
    }

    // ─── D2 — Inline cabinet edit drawer ────────────────────────────────────────
    // Filter the loaded product catalog by cabinet_type so the swap
    // dropdown only shows compatible substitutes (a wall cab can't
    // replace a base cab — different mount Z, different depth).
    _sameTypeProducts(cabinetType) {
        return (this.state.products || []).filter(
            p => p.cabinet_type === cabinetType
        );
    }

    // Width edit: validate, mutate item, cascade x positions, rebuild.
    _updateSelectedWidth(rawValue) {
        const v = parseFloat(rawValue);
        if (!Number.isFinite(v) || v < 6 || v > 48) return;
        const sel = this.state.selected;
        if (!sel) return;
        const idx = this.state.items.findIndex(it => it.layout_key === sel.layout_key);
        if (idx < 0) return;
        this.state.items[idx].width_in = v;
        sel.width_in = v;
        this._recomputeLayoutFromItems();
        if (this.T.scene) this._buildScene();
        this._queueAutoSave();    // D5
    }

    // Product swap: replace cabinet at the same position with the
    // new product's payload, keeping position + layout_key + dimensions.
    _swapSelectedProduct(rawProductId) {
        const pid = parseInt(rawProductId, 10);
        if (!Number.isFinite(pid)) return;
        const product = (this.state.products || []).find(p => p.product_id === pid);
        if (!product) return;
        const sel = this.state.selected;
        if (!sel) return;
        const idx = this.state.items.findIndex(it => it.layout_key === sel.layout_key);
        if (idx < 0) return;
        const oldItem = this.state.items[idx];
        // Preserve position + layout_key + current width (user may have
        // dialed in a custom width; swapping product shouldn't reset it).
        const merged = {
            ...product,
            layout_key:    oldItem.layout_key,
            x_position_in: oldItem.x_position_in,
            y_position_in: oldItem.y_position_in,
            z_position_in: oldItem.z_position_in,
            width_in:      oldItem.width_in,
        };
        this.state.items[idx] = merged;
        this.state.selected = merged;
        this._recomputeLayoutFromItems();
        if (this.T.scene) this._buildScene();
        this._queueAutoSave();    // D5
    }

    // Remove the selected cabinet entirely.
    _removeSelectedCabinet() {
        const sel = this.state.selected;
        if (!sel) return;
        const idx = this.state.items.findIndex(it => it.layout_key === sel.layout_key);
        if (idx < 0) return;
        this.state.items.splice(idx, 1);
        // Pick a neighbour as the new selection (or null if empty).
        this.state.selected = this.state.items[idx] || this.state.items[idx - 1] || null;
        this._recomputeLayoutFromItems();
        if (this.T.scene) this._buildScene();
        // v19.0.4.24.0 P0#1 Stage 1 — sync delete server-side so
        // pinned-line rows don't resurrect on next load. Fire-and-
        // forget; the debounced /save is the fallback. Skipped when
        // designId isn't set yet (nothing server-side to delete).
        if (this.state.designId && sel.layout_key) {
            rpc("/southbrook_kitchen/configurator/delete_line", {
                design_id:  this.state.designId,
                layout_key: sel.layout_key,
            }).catch(() => { /* non-fatal — auto-save reconciles */ });
        }
        this._queueAutoSave();    // D5
    }

    // Cascade x positions inside each cabinet group.
    //  - Bases pack left-to-right contiguously on the floor row.
    //  - Walls track their own left-to-right order on the upper row.
    //  - Tall / corner / filler / panel pack at the right end of the
    //    base run (so a drag-dropped tall cab lands after the bases).
    //  - Summary price excludes fillers per the existing convention.
    _recomputeLayoutFromItems() {
        // Panel-placement rule (Southbrook domain, 2026-07-01):
        //   Panels come in TWO shapes, both of which must NEVER attach to a
        //   room wall.
        //   1. Filler ("filler")  — plain spacers, sit between cabinets, may
        //      touch a wall only as a consequence of filling the gap between
        //      the last cabinet and the wall. Server /layout drives their X.
        //   2. End cap ("panel")  — decorative panels that finish the exposed
        //      left/right SIDE FACE of a base or wall cabinet. Their X is
        //      relative to the cabinet they cap and MUST NOT be overwritten
        //      by the tails-loop that packs tall/corner items after the base
        //      run (packing there placed them against the room wall — the
        //      visual bug this fix corrects).
        const items = this.state.items || [];
        const sortX = (a, b) => (a.x_position_in || 0) - (b.x_position_in || 0);

        const bases   = items.filter(it => it.cabinet_type === "base").sort(sortX);
        const walls   = items.filter(it => it.cabinet_type === "wall").sort(sortX);
        // Only tall + corner items pack after the base run; filler + panel
        // carry their own X and must not be repositioned here.
        const tailItems = items.filter(it =>
            ["tall", "corner"].includes(it.cabinet_type)
        ).sort(sortX);

        // v19.0.4.24.0 P0#1 Stage 1 — Pin-aware row packer. Pinned
        // items keep their stored x_position_in; unpinned items fit
        // into the free gaps between pinned ones (left-to-right),
        // and any overflow extends past the rightmost pinned. When
        // no item in a row is pinned, behaviour is identical to the
        // pre-4.23 cascade (pack from x=0), so existing designs
        // render exactly as before until the user drags a cabinet.
        // Rec D · Sprint 2d step 6 — the packRow closure moved to
        // canvas/pack_row.esm.js as a pure exported function; the
        // three call sites keep the same signature so scene-diff
        // rebuild timings are unchanged.
        packRow(bases);
        packRow(walls);
        packRow(tailItems);
        // NOTE: filler items get X from server /layout; end-cap panels get X
        //       relative to their host cabinet (set by _addCabinetFromProduct
        //       or downstream). Both are left untouched here on purpose.

        let price = 0;
        for (const it of items) {
            if (it.cabinet_type !== "filler") price += (it.price || 0);
        }
        this.state.summary = {
            ...(this.state.summary || {}),
            base_count: bases.length,
            wall_count: walls.length,
            total: bases.length + walls.length,
            price: price,
        };

        // Runtime validation — surface a warning if any end-cap panel would
        // end up flush against or beyond a room wall. End caps must attach
        // ONLY to the left/right side face of a base or wall cabinet; a
        // panel whose X pushes it past the room boundary means the anchor
        // logic upstream lost track of its host cabinet.
        this._validateEndCapPlacement(
            items.filter(it => it.cabinet_type === "panel"),
        );
    }

    _validateEndCapPlacement(endCapItems) {
        const rw = (this.state.room && this.state.room.width_in) || 0;
        const warnings = [];
        for (const item of endCapItems) {
            const x = item.x_position_in || 0;
            const w = item.width_in || 0;
            const rightEdge = x + w;
            if (x < 0 || (rw && rightEdge > rw + 0.01)) {
                console.warn(
                    "[SBK] End cap panel " +
                    (item.product_name || item.layout_key || item.id) +
                    " is positioned at x=" + x + "\" (width " + w + "\"), " +
                    "which places it against or beyond the room wall. " +
                    "End cap panels must attach ONLY to the left or right " +
                    "side face of a base or wall cabinet — never to a room wall."
                );
                warnings.push({
                    code:     "PANEL_WALL_ATTACH",
                    severity: "error",
                    message:  "End cap panel \"" +
                              (item.product_name || item.layout_key || "") +
                              "\" cannot be placed against a wall. Attach " +
                              "it to the side of a cabinet instead.",
                });
            }
        }
        if (warnings.length) {
            const existing = (this.state.warnings || []).filter(
                w => w.code !== "PANEL_WALL_ATTACH");
            this.state.warnings = existing.concat(warnings);
        } else if (this.state.warnings) {
            // Clear stale PANEL_WALL_ATTACH warnings once fixed.
            this.state.warnings = this.state.warnings.filter(
                w => w.code !== "PANEL_WALL_ATTACH");
        }
    }

    // ─── Three.js initialisation ────────────────────────────────────────────────
    _initScene() {
        const THREE  = this.T.THREE;
        const mount  = this.canvas3dRef.el;
        if (!mount) return;

        // Rec D · Sprint 2d step 20 — scene + cameras + renderer +
        // lighting rig + orbit setup moved to canvas/scene_init.esm.js.
        // Class-scope wiring (animation loop, resize observer, event
        // listeners) stays here since it needs `this`.
        const core = initScene(THREE, mount, P);
        Object.assign(this.T, core);

        // PBR env map — async, non-blocking. Falls back silently if
        // the PMREM step fails on the user's GL stack.
        this._installPbrEnvMap();

        // Render loop — render activeCamera, advance orbit damping
        // when the persp orbit is active.
        const scene = this.T.scene;
        const renderer = this.T.renderer;
        const { persp } = this.T.cameras;
        const tick = () => {
            this.T.animId = requestAnimationFrame(tick);
            if (this.T.orbit && this.T.orbit.enabled) this.T.orbit.update();
            renderer.render(scene, this.T.activeCamera);
        };
        tick();

        // Resize observer — update BOTH cameras so a swap doesn't pop.
        this._resizeObserver = new ResizeObserver(() => {
            const nw = mount.clientWidth, nh = mount.clientHeight;
            if (!nw || !nh) return;
            persp.aspect = nw / nh;
            persp.updateProjectionMatrix();
            renderer.setSize(nw, nh);
            this._applyOrthoFrustum();
        });
        this._resizeObserver.observe(mount);

        // Events — D15: mousedown in capture phase so we intercept
        // before OrbitControls (bound to renderer.domElement, child
        // of mount) sees it.
        mount.addEventListener("mousedown",  this._onMouseDown, { capture: true });
        mount.addEventListener("mousemove",  this._onMouseMove);
        mount.addEventListener("mouseup",    this._onMouseUp);
        mount.addEventListener("mouseleave", this._onMouseUp);
        mount.addEventListener("mousemove",  this._onMouseOver);
        mount.addEventListener("wheel", this._onWheel, { passive: false });
        window.addEventListener("keydown", this._onKeyDown);
    }

    // Rec D · Sprint 2d step 14 — PBR env map install moved to
    // canvas/pbr_env_map.esm.js. Same 512×256 gradient studio HDR
    // + PMREM install path; identical rendering.
    _installPbrEnvMap() {
        const { THREE, scene, renderer } = this.T;
        installPbrEnvMap(THREE, scene, renderer);
    }

    // ─── D1 — Multi-view camera system ──────────────────────────────────────────
    // Rec D · Sprint 2d step 4 — thin wrapper delegating to the
    // shared pure function so <KitchenCanvas> can compute its own
    // view specs. Same dict shape assigned to the same class ref.
    _recomputeViews(rw, rh, rd) {
        this.T.viewSpecs = computeViewSpecs(this.T.THREE, rw, rh, rd);
    }

    // Apply the current view's ortho frustum + the wheel-zoom multiplier.
    // Safe to call even when the active camera is perspective (no-op).
    // Rec D · Sprint 2d step 8 — frustum math moved to
    // canvas/ortho_frustum.esm.js so <KitchenCanvas> can share it.
    _applyOrthoFrustum() {
        const t = this.T;
        const cam = t.cameras?.ortho;
        if (!cam || !t.renderer) return;
        const spec = t.viewSpecs?.[this.state.view];
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

    // Swap to a named view. instant=true jumps; otherwise lerps over ms.
    // Rec D · Sprint 2d step 22 — camera controller (setView +
    // animateCamera + onWheel) moved to canvas/camera_controller.
    // esm.js. Class-side wrappers still write this.state.view
    // (OWL reactive) before delegating.
    _setView(key, instant = false) {
        this.state.view = key;
        setViewShared(this.T, key, {
            instant,
            applyOrthoFrustum: () => this._applyOrthoFrustum(),
            animateCamera: (p, tgt, up, ms) => this._animateCamera(p, tgt, up, ms),
        });
    }

    _animateCamera(toPos, toTarget, toUp, ms = 400) {
        animateCameraShared(
            this.T, toPos, toTarget, toUp, ms,
            easeInOutCubic, requestAnimationFrame,
        );
    }

    _onWheel(e) {
        onWheelShared(this.T, e, () => this._applyOrthoFrustum());
    }

    _onKeyDown(e) {
        // Ignore when typing in form inputs.
        const tag = (e.target && e.target.tagName) || "";
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" ||
            e.target?.isContentEditable) return;
        const k = e.key;
        const ctrl = e.metaKey || e.ctrlKey;

        // D6 — Cmd/Ctrl+S manual save (debounced auto-save also covers
        // this, but power users expect the muscle-memory shortcut).
        if (ctrl && (k === "s" || k === "S")) {
            e.preventDefault();
            this._saveDesign();
            return;
        }

        const map = { "1": "iso", "2": "top", "3": "front",
                       "4": "left", "5": "right", "6": "persp" };
        if (!ctrl && map[k]) { e.preventDefault(); this._setView(map[k]); return; }
        if (!ctrl && (k === "r" || k === "R")) { e.preventDefault(); this._setView("iso"); return; }
        if (!ctrl && (k === "+" || k === "=")) {
            e.preventDefault();
            this.T.vsScale = Math.max(0.3, (this.T.vsScale || 1) * 0.9);
            this._applyOrthoFrustum();
            return;
        }
        if (!ctrl && (k === "-" || k === "_")) {
            e.preventDefault();
            this.T.vsScale = Math.min(3.0, (this.T.vsScale || 1) * 1.1);
            this._applyOrthoFrustum();
            return;
        }

        // D6 — Arrow keys cycle selection through cabinets in x-position
        // order (bases first, then walls). Skips fillers since they're
        // not user-editable.
        if (!ctrl && (k === "ArrowLeft" || k === "ArrowRight")) {
            e.preventDefault();
            this._cycleSelection(k === "ArrowRight" ? 1 : -1);
            return;
        }

        // v19.0.4.25.0 P0#1 Stage 3 — Q rotates selected cabinet 90°
        // counter-clockwise, E rotates 90° clockwise. Both flip
        // pinned=true so the pack cascade leaves the cabinet in place.
        // Y-axis only (kitchen cabinets don't tumble). Persistence
        // happens via _savePinnedPosition. Visual rotation of the
        // mesh is deferred; the rotation_deg is stored + toasted so
        // reps can reason about door direction even before Stage 3.5
        // ships the visual layer.
        //
        // Q/E chosen (not R) to avoid clobbering the existing R
        // "reset view to iso" muscle memory.
        if (!ctrl && (k === "q" || k === "Q" || k === "e" || k === "E")) {
            e.preventDefault();
            const delta = (k === "e" || k === "E") ? 90 : -90;
            this._rotateSelected(delta);
            return;
        }

        // D6 — Esc clears the cabinet selection.
        if (k === "Escape") {
            if (this.state.selected) {
                this.state.selected = null;
                this._highlightSelected(null);
                e.preventDefault();
            }
            return;
        }

        // Delete / Backspace — remove the selected item (any type: base,
        // wall, tall, corner, filler, panel) from the layout AND the
        // quote. _removeSelectedCabinet already splices the item out of
        // state.items and calls _queueAutoSave which persists the design
        // to the server (drives southbrook.kitchen.design.line records —
        // the quote source). Standard 3D-editor UX (Blender / SketchUp /
        // Fusion keybinding).
        //
        // Guarded against firing when the user is typing in a text
        // input, textarea, or contentEditable region so we don't hijack
        // Backspace inside inline edits (width entry, notes, room name,
        // inventory search).
        if (k === "Delete" || k === "Backspace") {
            const t = e.target;
            const inEditable = t && (
                t.tagName === "INPUT"
                || t.tagName === "TEXTAREA"
                || t.tagName === "SELECT"
                || t.isContentEditable
            );
            if (inEditable) return;
            if (!this.state.selected) return;
            const doomed = this.state.selected;
            const doomedName = doomed.product_name || doomed.name
                || doomed.layout_key || "item";
            const doomedType = doomed.cabinet_type || "item";
            e.preventDefault();
            this._removeSelectedCabinet();
            if (this.notification && this.notification.add) {
                this.notification.add(
                    "Removed " + doomedName + " (" + doomedType +
                    ") from the layout and quote.",
                    { type: "info" }
                );
            }
            return;
        }
    }

    // D6 — cycle selection through selectable items (bases then walls,
    // each sorted left-to-right). +1 = next, -1 = previous; wraps.
    _cycleSelection(dir) {
        const items = this.state.items || [];
        const selectable = items
            .filter(it => it.cabinet_type === "base" || it.cabinet_type === "wall")
            .sort((a, b) => {
                if (a.cabinet_type !== b.cabinet_type) {
                    return a.cabinet_type === "base" ? -1 : 1;
                }
                return (a.x_position_in || 0) - (b.x_position_in || 0);
            });
        if (!selectable.length) return;
        let idx = -1;
        if (this.state.selected) {
            idx = selectable.findIndex(
                it => it.layout_key === this.state.selected.layout_key
            );
        }
        idx = (idx + dir + selectable.length) % selectable.length;
        if (idx < 0) idx += selectable.length;
        this._selectCabinet(selectable[idx]);
    }

    // v19.0.4.25.0 P0#1 Stage 3 — Rotate the selected cabinet by
    // deltaDeg (±90) and persist. Sets item.rotation_deg (mod 360),
    // flips pinned=true so the pack cascade leaves the cabinet
    // where the user put it, and fires _savePinnedPosition to sync
    // the new rotation to the DB. Fillers + panels don't rotate
    // (their orientation is host-relative).
    //
    // Visual rotation of the mesh is DEFERRED to a follow-up patch —
    // rotation_deg is stored and displayed via toast so the sales
    // rep can reason about door direction, but the 3D scene keeps
    // meshes at their un-rotated pose. Wrapping cabinet meshes in
    // THREE.Groups is what broke the WebClient at 4.20.0; that
    // refactor is staged separately (see audit §P0#1 recovery plan).
    _rotateSelected(deltaDeg) {
        const item = this.state.selected;
        if (!item) return;
        if (item.cabinet_type === "filler" || item.cabinet_type === "panel") {
            return;
        }
        const cur = ((item.rotation_deg || 0) + deltaDeg) % 360;
        item.rotation_deg = (cur + 360) % 360;
        item.pinned = true;
        this._savePinnedPosition(item);
        if (this.notification && this.notification.add) {
            this.notification.add(
                `Rotated ${item.product_name || item.name || "cabinet"} to ${item.rotation_deg}°`,
                { type: "success" }
            );
        }
        this._queueAutoSave();
    }

    // Rec D · Sprint 2d step 21 — orbit + renderer disposal moved to
    // canvas/scene_dispose.esm.js. Class-scope cleanup (autoSave
    // timer, resize observer, event listener removal) stays here
    // since it needs `this` bindings.
    _destroyScene() {
        const t = this.T;
        // D5 — clear any pending auto-save so we don't fire after
        // the component unmounts.
        if (this._autoSaveTimer) {
            clearTimeout(this._autoSaveTimer);
            this._autoSaveTimer = null;
        }
        if (t.animId) cancelAnimationFrame(t.animId);
        if (this._resizeObserver) this._resizeObserver.disconnect();
        const mount = this.canvas3dRef.el;
        if (mount) {
            // D15 — mousedown must match the capture-phase add.
            mount.removeEventListener("mousedown",  this._onMouseDown, { capture: true });
            mount.removeEventListener("mousemove",  this._onMouseMove);
            mount.removeEventListener("mouseup",    this._onMouseUp);
            mount.removeEventListener("mouseleave", this._onMouseUp);
            mount.removeEventListener("mousemove",  this._onMouseOver);
            mount.removeEventListener("wheel",      this._onWheel);
        }
        window.removeEventListener("keydown", this._onKeyDown);
        destroyScene(t, mount);
    }

    // ─── Scene builder ──────────────────────────────────────────────────────────
    _buildScene() {
        const { THREE, scene, renderer } = this.T;
        if (!scene || !renderer) return;

        const rw = this.state.room.width_in  * IN;
        const rd = this.state.room.depth_in  * IN;
        const rh = this.state.room.height_in * IN;

        // Dispose previous geometry.
        // v19.0.4.25.0 P0#1 Stage 3 — cabObjs may now include
        // THREE.Group wrappers per rotated cabinet (see rotationGroup
        // helper). Groups have no .geometry / .material of their own,
        // so a bare `if (m.geometry) m.geometry.dispose()` silently
        // leaks the child meshes' resources. We `.traverse()` every
        // node — Meshes get their geometry + material disposed,
        // Groups just visit their descendants. Post-mortem of 4.20.0
        // (see audit §P0#1) identified this as the WebGL context loss
        // that follows ~10 refreshes once grouping is introduced.
        const disposeNode = (n) => {
            if (!n) return;
            if (n.geometry) n.geometry.dispose();
            if (n.material) {
                if (Array.isArray(n.material)) n.material.forEach(x => x.dispose());
                else n.material.dispose();
            }
        };
        [...this.T.roomObjs, ...this.T.cabObjs].forEach(m => {
            if (m && typeof m.traverse === "function") {
                m.traverse(disposeNode);
            } else {
                disposeNode(m);
            }
            scene.remove(m);
        });
        if (this.T.handleMesh) {
            scene.remove(this.T.handleMesh);
            this.T.handleMesh.geometry?.dispose();
            this.T.handleMesh.material?.dispose();
        }
        // D16 — Dispose lane meshes from the previous build.
        if (this.T.laneMeshes) {
            for (const k of ["base", "wall", "tall"]) {
                const m = this.T.laneMeshes[k];
                if (!m) continue;
                scene.remove(m);
                m.geometry?.dispose();
                m.material?.dispose();
            }
            this.T.laneMeshes = null;
        }
        this.T.roomObjs = []; this.T.cabObjs = []; this.T.clickable = []; this.T.handleMesh = null;
        this.T.arrowMeshes = [];

        // Rec D · Sprint 2d step 5 — thin closure over the shared
        // makeMesh factory so the ~40 call sites below stay
        // signature-compatible with the pre-2d code (`mk(geo, color,
        // pos, rotE, opts)`) while the actual mesh construction lives
        // in canvas/mesh_factory.esm.js for future <KitchenCanvas>
        // reuse.
        const mk = (geo, color, pos, rotE, opts) =>
            makeMesh(THREE, scene, geo, color, pos, rotE, opts);

        // Rec D · Sprint 2d step 11 — room shell (floor + 2 walls +
        // wainscoting rail + floor grid) moved to canvas/room_shell.
        // esm.js. Returns the objects list; we push into roomObjs so
        // the dispose loop at the top of _buildScene handles them.
        const { objects: shellObjects } = buildRoomShell(
            THREE, scene, mk, P, rw, rh, rd,
        );
        this.T.roomObjs.push(...shellObjects);

        // ── Cabinet fill ──
        const items = this.state.items;
        // Group base and wall items for geometry creation
        const baseItems = items.filter(it => it.cabinet_type === "base");
        const wallItems = items.filter(it => it.cabinet_type === "wall");
        const fillerItems = items.filter(it => it.cabinet_type === "filler");
        // End-cap decorative panels — anchored to a cabinet's exposed left
        // or right side face. Rendered as a thin vertical panel matching
        // the host cabinet's H×D at the pre-set x_position_in (do NOT
        // reposition here; see _recomputeLayoutFromItems for the rule).
        const endCapItems = items.filter(it => it.cabinet_type === "panel");

        // Rec D · Sprint 2d step 15 — base cabinet mesh builder moved
        // to canvas/base_cabinet.esm.js. Same toe-kick + carcass + door
        // + drawer + handles + countertop + drip edge + pin indicator
        // set, gated behind item.pinned as before.
        baseItems.forEach(item => {
            const { objects, clickable } = buildBaseCabinet(THREE, mk, P, item);
            this.T.cabObjs.push(...objects);
            this.T.clickable.push(...clickable);
        });

        // Rec D · Sprint 2d step 16 — wall cabinet mesh builder moved
        // to canvas/wall_cabinet.esm.js. Same body + door + handle +
        // bottom rail + pin indicator set; D8 z_position_in honoured.
        wallItems.forEach(item => {
            const { objects, clickable } = buildWallCabinet(THREE, mk, P, item);
            this.T.cabObjs.push(...objects);
            this.T.clickable.push(...clickable);
        });

        // D13 — Generic-type fallback: tall / corner / panel cabinets
        // dropped via the inventory drag-and-drop. Renders as a simple
        // PBR box at the item's reported (x, z, dims) so the cabinet
        // becomes visible immediately instead of silently dropping out
        // of the scene. Detailed per-type geometry can layer on top later.
        // Rec D · Sprint 2d steps 17-19 — tall/corner/panel/filler/
        // end-cap mesh builders moved to canvas/other_cabinets.esm.js.
        const knownTypes = new Set(["base", "wall", "filler"]);
        const otherItems = items.filter(it => !knownTypes.has(it.cabinet_type));

        otherItems.forEach(item => {
            const { objects, clickable } = buildOtherCabinet(THREE, mk, P, item);
            this.T.cabObjs.push(...objects);
            this.T.clickable.push(...clickable);
        });

        // Filler panels
        fillerItems.forEach(item => {
            this.T.cabObjs.push(buildFillerPanel(THREE, mk, P, item));
        });

        // End-cap decorative panels
        endCapItems.forEach(item => {
            const { objects, clickable } = buildEndCapPanel(THREE, mk, P, item);
            this.T.cabObjs.push(...objects);
            this.T.clickable.push(...clickable);
        });

        // Rec D · Sprint 2d step 12 — drag handle + arrow cones
        // moved to canvas/drag_handle.esm.js.
        const { handleMesh, arrowMeshes } = buildDragHandle(
            THREE, scene, P, rw, rd,
        );
        this.T.handleMesh = handleMesh;
        this.T.arrowMeshes.push(...arrowMeshes);

        // Rec D · Sprint 2d step 13 — three drop lanes moved to
        // canvas/drop_lanes.esm.js.
        this.T.laneMeshes = buildDropLanes(THREE, scene, rw, rh);
        this._updateLaneVisibility();

        // ── D1 — Re-compute view specs from current room dims and
        //         re-apply the active view. instant=true on rebuild so
        //         the camera doesn't lerp every time a cabinet is added.
        this._recomputeViews(rw, rh, rd);
        this._setView(this.state.view || "iso", true);

        // Re-apply selection highlight after rebuild
        if (this.state.selected) {
            this._highlightSelected(this.state.selected);
        }
    }

    // Rec D · Sprint 2d step 9 — thin wrapper delegating to the
    // shared selection helper so <KitchenCanvas> can highlight its
    // own cabObjs with the same reset+paint cycle.
    _highlightSelected(item) {
        highlightSelected(this.T.cabObjs, item, P);
    }

    // ─── Mouse events ────────────────────────────────────────────────────────────
    // Rec D · Sprint 2d step 3 — thin wrapper delegating to the
    // shared pure function so future <KitchenCanvas> can reuse the
    // same math with its own canvas element.
    _ndcFromEvent(e) {
        return ndcFromEvent(e, this.canvas3dRef.el);
    }

    // Rec D · Sprint 2d step 23 — pointer pipeline helpers moved to
    // canvas/pointer_pipeline.esm.js. The handlers keep their `this`-
    // scoped orchestration (state writes, RPC fire-and-forget, cursor
    // sets, notification.add) but delegate testable geometry math +
    // threshold checks + cursor decision to the shared module.
    _onMouseDown(e) {
        const { activeCamera, raycaster, handleMesh, clickable } = this.T;
        if (!activeCamera || !raycaster) return;

        raycaster.setFromCamera(this._ndcFromEvent(e), activeCamera);

        // D1 — drag handle is only sensible in iso/top views.
        const handleActive = isHandleActiveView(this.state.view);
        if (handleActive && handleMesh && raycaster.intersectObject(handleMesh).length) {
            this.T.dragging = true;
            this.T.dragX0   = e.clientX;
            this.T.dragW0   = this.state.room.width_in;
            e.preventDefault();
            return;
        }

        // Cabinet selection — works in every view. D15 — also arms
        // a potential move (commits only on >5px cursor travel).
        const hits = raycaster.intersectObjects(clickable, false);
        if (hits.length) {
            const h = hits[0].object;
            if (h.userData?.item) {
                this._selectCabinet(h.userData.item);
                if (h.userData.item.cabinet_type !== "filler") {
                    this.T.movingItem      = h.userData.item;
                    this.T.moveStartClient = { x: e.clientX, y: e.clientY };
                    this.T.moveLastX       = h.userData.item.x_position_in;
                    this.T.moveCommitted   = false;
                    // D15 — stopPropagation gates OrbitControls off
                    // this drag; empty-space clicks fall through.
                    e.preventDefault();
                    e.stopPropagation();
                }
            }
        }
    }

    _onMouseMove(e) {
        if (this.T.dragging) {
            this.state.room.width_in = resolveRoomWidthFromDrag(
                e.clientX, this.T.dragX0, this.T.dragW0,
            );
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
            if (this.T.scene) this._buildScene();
        }
    }

    _onMouseUp() {
        if (this.T.dragging) {
            this.T.dragging = false;
            this._refreshLayout().then(() => this._queueAutoSave());   // D5
        }
        if (this.T.movingItem) {
            const item = this.T.movingItem;
            const wasCommitted = this.T.moveCommitted;
            this.T.movingItem    = null;
            this.T.moveCommitted = false;
            const cvs = this.T.renderer && this.T.renderer.domElement;
            if (cvs) cvs.style.cursor = "";
            if (wasCommitted) {
                if (isPinnable(item.cabinet_type)) {
                    item.pinned = true;
                    this._savePinnedPosition(item);
                }
                this._recomputeLayoutFromItems();
                if (this.T.scene) this._buildScene();
                this.notification.add(
                    `Moved ${item.product_name || item.name || "cabinet"} to ${Math.round(item.x_position_in)}″`,
                    { type: "success" }
                );
                this._queueAutoSave();
            }
        }
    }

    _onMouseOver(e) {
        const mount = this.canvas3dRef.el;
        if (!mount || !this.T.activeCamera || !this.T.raycaster) return;
        // D15 — Don't override cursor mid-move (_onMouseMove already
        // set it to "move").
        if (this.T.movingItem && this.T.moveCommitted) return;
        this.T.raycaster.setFromCamera(this._ndcFromEvent(e), this.T.activeCamera);
        const handleActive = isHandleActiveView(this.state.view);
        const onHandle = handleActive && this.T.handleMesh &&
            this.T.raycaster.intersectObject(this.T.handleMesh).length > 0;
        const onCabinet = !onHandle &&
            this.T.raycaster.intersectObjects(this.T.clickable, false).length > 0;
        const cvs = this.T.renderer?.domElement;
        if (cvs) cvs.style.cursor = cursorForPointerState({
            dragging: this.T.dragging, onHandle, onCabinet,
        });
    }

    // ─── Save ─────────────────────────────────────────────────────────────────────
    async _saveDesign() {
        this.state.saving = true;
        try {
            const result = await rpc("/southbrook_kitchen/configurator/save", {
                name:       this.state.designName ||
                            `Kitchen ${this.state.room.width_in}"`,
                room:       this.state.room,
                items:      this.state.items,
                design_id:  this.state.designId || false,
                partner_id: this.state.partnerId || false,
            });
            this.state.designId       = result.id;
            this.state.designName     = result.name;
            this.state.lastAutoSaveAt = Date.now();
            this.notification.add(`Saved: ${result.name}`, { type: "success" });
        } catch (e) {
            this.notification.add("Save failed: " + (e.message || e), { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    // v19.0.4.24.0 P0#1 Stage 1 — Persist a single pinned drop
    // position. Fire-and-forget — silent on failure so the debounced
    // /save reconciles the whole design later. Skipped when designId
    // isn't set yet (unsaved design, nothing server-side to update).
    //
    // IMPORTANT: this must NEVER be awaited by onWillStart or any
    // lifecycle hook. It's a side-channel write; any lifecycle
    // dependency will silently hang the WebClient mount if the RPC
    // hits a routing miss (see post-mortem of 4.20.0 in
    // docs/southbrook_kitchen_audit_2026-07-01.md §P0#1).
    async _savePinnedPosition(item) {
        if (!this.state.designId || !item || !item.layout_key) return;
        try {
            await rpc("/southbrook_kitchen/configurator/save_position", {
                design_id:      this.state.designId,
                layout_key:     item.layout_key,
                x_position_in:  item.x_position_in || 0,
                y_position_in:  item.y_position_in || 0,
                z_position_in:  item.z_position_in || 0,
                rotation_deg:   item.rotation_deg  || 0,
                pinned:         true,
            });
        } catch (_) {
            // Non-fatal — pin stays on the client until the next
            // full /save.
        }
    }

    // ─── D5 — Debounced auto-save ───────────────────────────────────────────────
    // Called from every mutation path (room change, drag-resize end,
    // cabinet edit drawer ops). 3s after the last edit, fires a silent
    // save against /save. Skipped when state.items is empty (nothing
    // to persist) or a manual save is in flight.
    _queueAutoSave() {
        if (this._autoSaveTimer) {
            clearTimeout(this._autoSaveTimer);
            this._autoSaveTimer = null;
        }
        if (!this.state.items || !this.state.items.length) return;
        this._autoSaveTimer = setTimeout(() => {
            this._autoSaveTimer = null;
            this._autoSave();
        }, 3000);
    }

    async _autoSave() {
        if (this.state.saving) return;       // manual save in flight - skip
        if (this.state.autoSaving) return;   // another auto-save in flight
        this.state.autoSaving = true;
        try {
            const result = await rpc("/southbrook_kitchen/configurator/save", {
                name:       this.state.designName || "Untitled Kitchen",
                room:       this.state.room,
                items:      this.state.items,
                design_id:  this.state.designId || false,
                partner_id: this.state.partnerId || false,
            });
            this.state.designId       = result.id;
            this.state.designName     = result.name;
            this.state.lastAutoSaveAt = Date.now();
        } catch (e) {
            // Silent on auto-save: manual save will surface errors. Log
            // for diagnostics only.
            console.warn("[SouthbrookKitchenConfigurator] auto-save failed:", e);
        } finally {
            this.state.autoSaving = false;
        }
    }

    async _openDesigns() {
        return this.action.doAction(
            "southbrook_kitchen_3d_configurator.action_sbk_kitchen_designs"
        );
    }

    // D10 — Run the controller-supplied CTA action (typically opens
    // the Cabinet Products list filtered by southbrook_is_cabinet).
    async _runErrorCta() {
        const cta = this.state.errorCta;
        if (!cta || !cta.action) return;
        try {
            return this.action.doAction(cta.action);
        } catch (e) {
            this.notification.add(
                "Couldn't open the cabinet catalog: " + (e.message || e),
                { type: "danger" }
            );
        }
    }

    // D10 — Open the BOM list for the currently-selected product so
    // the rep can add a BoM and unblock manufacturing in one click.
    async _openSelectedProductBom() {
        const sel = this.state.selected;
        if (!sel || !sel.template_id) return;
        return this.action.doAction({
            type:      "ir.actions.act_window",
            name:      "Bill of Materials",
            res_model: "mrp.bom",
            view_mode: "list,form",
            views:     [[false, "list"], [false, "form"]],
            domain:    [["product_tmpl_id", "=", sel.template_id]],
            context:   {
                default_product_tmpl_id: sel.template_id,
                default_type:            "normal",
            },
            target:    "current",
        });
    }

    // ─── Formatting helpers ───────────────────────────────────────────────────────
    _money(v) {
        const sym = (this.state.channel && this.state.channel.currency_symbol) || "$";
        return `${sym}${Number(v || 0).toFixed(2)}`;
    }

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
    <!-- Room dimensions moved into the topbar (2026-06-30) so the
         left aside is dedicated to setup/preferences, not spatial
         inputs. margin-right:auto (in SCSS) keeps this group flush
         against the brand block; actions stay right-aligned. -->
    <div class="o_sbk_room_dims">
      <label class="o_sbk_room_dim">
        <span class="o_sbk_room_dim_label">Width</span>
        <div class="o_sbk_room_dim_input_row">
          <input type="number" min="12" step="6"
                 t-att-value="state.room.width_in"
                 t-on-change="(ev) => this._changeRoom('width_in', ev.target.value)"/>
          <span class="o_sbk_room_dim_ft"><t t-esc="(state.room.width_in / 12).toFixed(1)"/>′</span>
        </div>
      </label>
      <label class="o_sbk_room_dim">
        <span class="o_sbk_room_dim_label">Depth</span>
        <input type="number" min="12" step="6"
               t-att-value="state.room.depth_in"
               t-on-change="(ev) => this._changeRoom('depth_in', ev.target.value)"/>
      </label>
      <label class="o_sbk_room_dim">
        <span class="o_sbk_room_dim_label">Height</span>
        <input type="number" min="84" step="6"
               t-att-value="state.room.height_in"
               t-on-change="(ev) => this._changeRoom('height_in', ev.target.value)"/>
      </label>
    </div>
    <!-- D3 — Channel pricing badge. Shows the partner-resolved
         pricelist so every price the user sees in the configurator
         is the one the quote will use. Suppressed for the default
         retail/no-partner case so it doesn't clutter the topbar. -->
    <div t-if="state.channel.channel !== 'retail'" class="o_sbk_channel_badge"
         t-att-title="'Pricelist: ' + state.channel.pricelist_name + (state.channel.partner_name ? ' (' + state.channel.partner_name + ')' : '')">
      <span class="o_sbk_channel_dot"
            t-att-class="'o_sbk_channel_dot o_sbk_ch_' + state.channel.channel"/>
      <span class="o_sbk_channel_label" t-esc="state.channel.channel_label"/>
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
      <!-- D5 — Background auto-save status pill. Quiet by default;
           pops "Saving..." during a debounced save and a green
           checkmark for ~3s after success. -->
      <span t-if="state.autoSaving" class="o_sbk_autosave">Saving…</span>
      <span t-elif="state.lastAutoSaveAt &gt; 0" class="o_sbk_autosave is-ok">✓ Auto-saved</span>
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

      <!-- Width/Depth/Height moved to the topbar (2026-06-30). -->

      <!-- D4 — Save current room dims as this user's default. -->
      <button class="o_sbk_save_default_link"
              t-on-click="_saveAsMyDefault"
              title="Use these room dimensions as the prefill for every new design you open">
        Save as my default
      </button>

      <!-- D7 — Filler placement strategy. -->
      <label class="o_sbk_field">
        <span>Filler strategy</span>
        <select class="o_sbk_edit_select"
                t-att-value="state.fillerStrategy"
                t-on-change="(ev) => this._changeFillerStrategy(ev.target.value)">
          <option value="split"  t-att-selected="state.fillerStrategy === 'split'  ? 'selected' : ''">Split — both ends</option>
          <option value="right"  t-att-selected="state.fillerStrategy === 'right'  ? 'selected' : ''">Right end only</option>
          <option value="left"   t-att-selected="state.fillerStrategy === 'left'   ? 'selected' : ''">Left end only</option>
          <option value="scribe" t-att-selected="state.fillerStrategy === 'scribe' ? 'selected' : ''">Scribe — no filler</option>
        </select>
      </label>

      <!-- D8 — Wall cabinet top alignment + soffit height. -->
      <label class="o_sbk_field">
        <span>Wall cab top</span>
        <select class="o_sbk_edit_select"
                t-att-value="state.wallCabTopAlignment"
                t-on-change="(ev) => this._changeWallAlignment(ev.target.value)">
          <option value="fixed_gap"  t-att-selected="state.wallCabTopAlignment === 'fixed_gap'  ? 'selected' : ''">18″ gap above counter</option>
          <option value="to_ceiling" t-att-selected="state.wallCabTopAlignment === 'to_ceiling' ? 'selected' : ''">Up to ceiling</option>
          <option value="to_soffit"  t-att-selected="state.wallCabTopAlignment === 'to_soffit'  ? 'selected' : ''">Up to soffit</option>
        </select>
      </label>
      <label t-if="state.wallCabTopAlignment === 'to_soffit'" class="o_sbk_field">
        <span>Soffit height (in)</span>
        <input type="number" min="36" max="144" step="1"
               class="o_sbk_edit_input"
               t-att-value="state.soffitHeightIn"
               t-on-change="(ev) => this._changeSoffit(ev.target.value)"/>
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
        cabinets
      </div>

      <!-- D7 — Filler price as a separate breakdown row when present -->
      <div t-if="state.summary.filler_price &gt; 0" class="o_sbk_metric o_sbk_metric_filler">
        <strong>+ <t t-esc="_money(state.summary.filler_price)"/></strong>
        filler
      </div>

      <div t-if="state.summary.remainder_in > 0" class="o_sbk_remainder">
        <span class="o_sbk_remainder_icon">▤</span>
        <t t-esc="state.summary.remainder_in.toFixed(1)"/> in filler
        <span class="o_sbk_remainder_strategy"> (<t t-esc="state.fillerStrategy"/>)</span>
      </div>

      <!-- D7 — Snap-to-clean-width CTA when room is a few inches off
           a module-clean total. One click eliminates the filler. -->
      <div t-if="state.summary.snap_hint" class="o_sbk_snap_hint">
        <button class="o_sbk_snap_btn"
                t-on-click="_applySnapHint"
                t-att-title="'Round room to ' + state.summary.snap_hint.target_width + &quot; in to eliminate filler&quot;">
          <t t-if="state.summary.snap_hint.direction === 'expand'">
            ↗ Stretch to <t t-esc="state.summary.snap_hint.target_width"/>″ (no filler)
          </t>
          <t t-else="">
            ↙ Shrink to <t t-esc="state.summary.snap_hint.target_width"/>″ (no filler)
          </t>
        </button>
      </div>

      <!-- D10 — Structured onboarding nudge when no cabinet products
           are configured (NO_CABINETS). Falls back to the bare error
           string for any other error. -->
      <div t-if="state.error &amp;&amp; state.errorCode === 'NO_CABINETS'" class="o_sbk_onboard">
        <strong class="o_sbk_onboard_title">Catalog is empty</strong>
        <p class="o_sbk_onboard_body" t-esc="state.error"/>
        <button t-if="state.errorCta" class="o_sbk_onboard_cta" t-on-click="_runErrorCta">
          <t t-esc="state.errorCta.label"/> →
        </button>
      </div>
      <div t-elif="state.error" class="o_sbk_error" t-esc="state.error"/>

      <!-- D8 (and forward-compat for D12) — layout validation warnings -->
      <div t-if="state.warnings &amp;&amp; state.warnings.length" class="o_sbk_warnings">
        <div t-foreach="state.warnings" t-as="w" t-key="w.code"
             t-att-class="'o_sbk_warning o_sbk_warning_' + (w.severity || 'info')">
          <strong class="o_sbk_warning_icon">⚠</strong>
          <span class="o_sbk_warning_text" t-esc="w.message"/>
        </div>
      </div>
    </aside>

    <!-- 3D Scene panel -->
    <!-- D13 — Wrapper carries the drag-and-drop handlers; the canvas3d
         div stays clean for Three.js. dragHover toggles a brand-blue
         outline so the rep gets immediate "drop here" feedback. -->
    <main t-att-class="'o_sbk_scene_panel' + (state.dragHover ? ' is-drag-hover' : '')"
          t-on-dragover="_onCanvasDragOver"
          t-on-dragleave="_onCanvasDragLeave"
          t-on-drop="_onCanvasDrop">
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
      <!-- D1 — View switcher toolbar. 6 cameras + reset + zoom. -->
      <div class="o_sbk_viewbar" role="toolbar" aria-label="Camera view">
        <button class="o_sbk_viewbtn" t-att-class="'o_sbk_viewbtn' + (state.view === 'iso' ? ' is-active' : '')"
                t-att-aria-pressed="state.view === 'iso'"
                aria-label="Isometric view (1)"
                title="Isometric (1)"
                t-on-click="() => this._setView('iso')">
          <span class="o_sbk_viewicon">⬡</span><span class="o_sbk_viewkey">1</span>
        </button>
        <button class="o_sbk_viewbtn" t-att-class="'o_sbk_viewbtn' + (state.view === 'top' ? ' is-active' : '')"
                t-att-aria-pressed="state.view === 'top'"
                aria-label="Top / Plan view (2)"
                title="Top / Plan (2)"
                t-on-click="() => this._setView('top')">
          <span class="o_sbk_viewicon">▦</span><span class="o_sbk_viewkey">2</span>
        </button>
        <button class="o_sbk_viewbtn" t-att-class="'o_sbk_viewbtn' + (state.view === 'front' ? ' is-active' : '')"
                t-att-aria-pressed="state.view === 'front'"
                aria-label="Front view (3)"
                title="Front (3)"
                t-on-click="() => this._setView('front')">
          <span class="o_sbk_viewicon">▮</span><span class="o_sbk_viewkey">3</span>
        </button>
        <button class="o_sbk_viewbtn" t-att-class="'o_sbk_viewbtn' + (state.view === 'left' ? ' is-active' : '')"
                t-att-aria-pressed="state.view === 'left'"
                aria-label="Left view (4)"
                title="Left side (4)"
                t-on-click="() => this._setView('left')">
          <span class="o_sbk_viewicon">◧</span><span class="o_sbk_viewkey">4</span>
        </button>
        <button class="o_sbk_viewbtn" t-att-class="'o_sbk_viewbtn' + (state.view === 'right' ? ' is-active' : '')"
                t-att-aria-pressed="state.view === 'right'"
                aria-label="Right view (5)"
                title="Right side (5)"
                t-on-click="() => this._setView('right')">
          <span class="o_sbk_viewicon">◨</span><span class="o_sbk_viewkey">5</span>
        </button>
        <button class="o_sbk_viewbtn" t-att-class="'o_sbk_viewbtn' + (state.view === 'persp' ? ' is-active' : '')"
                t-att-aria-pressed="state.view === 'persp'"
                aria-label="Perspective / free orbit (6)"
                title="Perspective / orbit (6)"
                t-on-click="() => this._setView('persp')">
          <span class="o_sbk_viewicon">◉</span><span class="o_sbk_viewkey">6</span>
        </button>
        <div class="o_sbk_viewsep"/>
        <button class="o_sbk_viewbtn"
                aria-label="Reset view (R)"
                title="Reset to Isometric (R)"
                t-on-click="() => this._setView('iso')">
          <span class="o_sbk_viewicon">⌂</span><span class="o_sbk_viewkey">R</span>
        </button>
      </div>
      <div class="o_sbk_draghint">
        <t t-if="state.view === 'iso' || state.view === 'top'">Drag cabinet to move • Drag ● to resize room • Click select • ←/→ cycle • 1-6 views • ⌘S save</t>
        <t t-elif="state.view === 'persp'">Drag cabinet to move • Drag empty space to orbit • Wheel zoom • ←/→ cycle • R reset</t>
        <t t-else="">+/- zoom • Click select • ←/→ cycle • Switch to Iso/Top/Persp to move cabinets</t>
      </div>
    </main>

    <!-- Right inventory + detail panel -->
    <aside class="o_sbk_inventory">

      <div class="o_sbk_inv_head">
        <h3>Cabinet Inventory</h3>
        <span class="o_sbk_inv_count">
          <t t-esc="_filteredProducts().length"/> / <t t-esc="state.products.length"/>
        </span>
      </div>

      <!-- Category filter dropdown. Options with zero matching
           products auto-hide so the menu stays tight as SKUs grow
           into new categories (Appliances etc. will surface here
           automatically when their data lands, no template edit
           needed). Count next to each label so users see at a
           glance how many items are in each group. -->
      <label class="o_sbk_inv_cat_field">
        <span class="o_sbk_inv_cat_label">Filter by type</span>
        <select class="o_sbk_inv_cat_select"
                t-att-value="state.inventoryCategory"
                t-on-change="(ev) => this._setInventoryCategory(ev.target.value)"
                aria-label="Filter cabinet inventory by product category">
          <option value="all" t-att-selected="state.inventoryCategory === 'all' ? 'selected' : ''">
            All (<t t-esc="_categoryCount('all')"/>)
          </option>
          <option t-if="_categoryCount('base') &gt; 0" value="base"
                  t-att-selected="state.inventoryCategory === 'base' ? 'selected' : ''">
            Base (<t t-esc="_categoryCount('base')"/>)
          </option>
          <option t-if="_categoryCount('wall') &gt; 0" value="wall"
                  t-att-selected="state.inventoryCategory === 'wall' ? 'selected' : ''">
            Wall (<t t-esc="_categoryCount('wall')"/>)
          </option>
          <option t-if="_categoryCount('tall') &gt; 0" value="tall"
                  t-att-selected="state.inventoryCategory === 'tall' ? 'selected' : ''">
            Tall (<t t-esc="_categoryCount('tall')"/>)
          </option>
          <option t-if="_categoryCount('panels') &gt; 0" value="panels"
                  t-att-selected="state.inventoryCategory === 'panels' ? 'selected' : ''">
            Panels (<t t-esc="_categoryCount('panels')"/>)
          </option>
        </select>
      </label>

      <!-- D13 — Searchable inventory. Filters by name, SKU, cabinet
           type, material, door style. Empty = full catalog. -->
      <div class="o_sbk_inv_search">
        <input type="search" class="o_sbk_inv_search_input"
               placeholder="Search by name, SKU, type, material…"
               t-att-value="state.inventorySearch"
               t-on-input="_onSearchInput"
               aria-label="Search cabinet inventory"/>
        <button t-if="state.inventorySearch" class="o_sbk_inv_search_clear"
                t-on-click="_clearSearch" aria-label="Clear search">×</button>
      </div>

      <!-- D13 — Drag hint pill. Only shown when search has results so it
           doesn't clutter the empty state. -->
      <div t-if="_filteredProducts().length" class="o_sbk_inv_draghint">
        ↔ Drag any product into the scene to add it
      </div>

      <!-- Column header -->
      <div class="o_sbk_inv_header">
        <span>Product</span><span>SKU</span><span>Width</span><span>Qty</span><span>Price</span>
      </div>

      <!-- Product rows -->
      <div class="o_sbk_product_list">
        <button t-foreach="_filteredProducts()" t-as="product" t-key="product.product_id"
            t-att-class="'o_sbk_product_row o_sbk_prod_draggable' + (state.selected &amp;&amp; state.selected.product_id === product.product_id ? ' is-selected' : '')"
            draggable="true"
            t-on-dragstart="(ev) => this._onProductDragStart(ev, product)"
            t-on-dragend="(ev) => this._onProductDragEnd(ev)"
            t-on-click="() => this._selectCabinet(product)"
            t-att-title="'Click to select · Drag onto scene to add ' + product.name">
          <div class="o_sbk_prod_thumb">
            <img t-att-src="product.image_url" alt="" loading="lazy"/>
          </div>
          <div class="o_sbk_prod_info">
            <strong t-esc="product.name"/>
            <small><t t-esc="product.cabinet_type"/> | <t t-esc="product.material"/></small>
            <!-- D17 — Archetype taxonomy badge when the template is
                 mapped to a Southbrook cabinet archetype. -->
            <span t-if="product.archetype_code" class="o_sbk_arch_badge"
                  t-att-title="'Archetype: ' + product.archetype_code + (product.archetype_collection ? ' (' + product.archetype_collection + ')' : '')">
              <t t-esc="product.archetype_body_class || product.archetype_code"/>
            </span>
          </div>
          <span class="o_sbk_prod_sku"  t-esc="product.sku"/>
          <span class="o_sbk_prod_dim"  t-esc="product.width_in + '&quot;'"/>
          <span t-att-class="'o_sbk_prod_qty' + (product.available_qty > 50 ? ' ok' : ' low')"
                t-esc="product.available_qty"/>
          <span class="o_sbk_prod_price" t-esc="_money(product.price)"/>
        </button>
        <!-- D13 — Empty-state when search yields zero matches. -->
        <div t-if="!_filteredProducts().length &amp;&amp; state.products.length"
             class="o_sbk_inv_empty">
          No products match "<t t-esc="state.inventorySearch"/>".
          <button class="o_sbk_inv_empty_clear" t-on-click="_clearSearch">Clear search</button>
        </div>
      </div>

      <!-- D2 — Selected cabinet inline-edit drawer.
           Width / product swap / remove are now first-class edits;
           the scene rebuilds locally on every change. Save Design
           still persists the result; D5 will add debounced auto-save. -->
      <div t-if="state.selected" class="o_sbk_detail">
        <div class="o_sbk_detail_head">
          <h4>Selected Cabinet</h4>
          <button class="o_sbk_detail_remove"
                  aria-label="Remove this cabinet from the layout"
                  title="Remove cabinet"
                  t-on-click="_removeSelectedCabinet">✕</button>
        </div>
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

        <!-- D10 — BOM warning banner: red bar with one-click jump to
             the BoM form pre-filtered to this product. Without a BoM
             the MO can't be generated even though the quote will save. -->
        <div t-if="state.selected.bom_available === false" class="o_sbk_bom_warn">
          <strong>⚠ No BOM defined</strong>
          <span> — this product can't be manufactured until a Bill of Materials exists.</span>
          <button class="o_sbk_bom_warn_btn" t-on-click="_openSelectedProductBom">Open BoM →</button>
        </div>

        <!-- Inline edit controls -->
        <div class="o_sbk_edit_grid">
          <label class="o_sbk_edit_field">
            <span>Product</span>
            <select class="o_sbk_edit_select"
                    t-att-value="state.selected.product_id"
                    t-on-change="(ev) => this._swapSelectedProduct(ev.target.value)">
              <option t-foreach="_sameTypeProducts(state.selected.cabinet_type)"
                      t-as="p" t-key="p.product_id"
                      t-att-value="p.product_id"
                      t-att-selected="p.product_id === state.selected.product_id ? 'selected' : ''"
                      t-esc="p.name + ' — ' + p.width_in + ' in'"/>
            </select>
          </label>
          <label class="o_sbk_edit_field">
            <span>Width (in)</span>
            <input type="number" min="6" max="48" step="3" class="o_sbk_edit_input"
                   t-att-value="state.selected.width_in"
                   t-on-change="(ev) => this._updateSelectedWidth(ev.target.value)"/>
          </label>
        </div>

        <dl class="o_sbk_spec_grid">
          <dt>SKU</dt>      <dd><t t-esc="state.selected.sku || '—'"/></dd>
          <dt>Height</dt>   <dd><t t-esc="state.selected.height_in"/> in</dd>
          <dt>Depth</dt>    <dd><t t-esc="state.selected.depth_in"/> in</dd>
          <dt>Material</dt> <dd><t t-esc="_materialLabel(state.selected.material)"/></dd>
          <!-- D17 — Archetype taxonomy rows (only when mapped). -->
          <t t-if="state.selected.archetype_code">
            <dt>Archetype</dt>
            <dd>
              <strong t-esc="state.selected.archetype_code"/>
              <span t-if="state.selected.archetype_body_class"> · <t t-esc="state.selected.archetype_body_class"/></span>
            </dd>
            <t t-if="state.selected.archetype_collection">
              <dt>Collection</dt>
              <dd t-esc="state.selected.archetype_collection"/>
            </t>
          </t>
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
    // D3 — partner for channel pricelist resolution.
    partner_id:     { type: Number, optional: true },
    "*":            true,
};
SouthbrookKitchenConfigurator.defaultProps = {};

actionRegistry.add("southbrook_kitchen_configurator", SouthbrookKitchenConfigurator);
