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
    // Case-insensitive filter across name / SKU / cabinet type / material.
    // Returns the full catalog when the search box is empty.
    _filteredProducts() {
        const q = (this.state.inventorySearch || "").toLowerCase().trim();
        const list = this.state.products || [];
        if (!q) return list;
        return list.filter(p =>
            (p.name && p.name.toLowerCase().includes(q)) ||
            (p.sku && p.sku.toLowerCase().includes(q)) ||
            (p.cabinet_type && p.cabinet_type.toLowerCase().includes(q)) ||
            (p.material && p.material.toLowerCase().includes(q)) ||
            (p.door_style && p.door_style.toLowerCase().includes(q))
        );
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
    _computeDropX(ev) {
        const t = this.T;
        if (!t.activeCamera || !t.raycaster || !t.THREE) return null;
        t.raycaster.setFromCamera(this._ndcFromEvent(ev), t.activeCamera);
        const floor  = new t.THREE.Plane(new t.THREE.Vector3(0, 1, 0), 0);
        const hit    = new t.THREE.Vector3();
        const result = t.raycaster.ray.intersectPlane(floor, hit);
        if (!result) return null;
        // hit.x is in scene-feet (IN = 1/12). Multiply by 12 to get inches.
        let xIn = hit.x * 12;
        // Clamp inside the room, leave at least 6" headroom on the right
        // for the cabinet to fit, then snap to the 6" grid.
        const maxX = Math.max(0, this.state.room.width_in - 6);
        xIn = Math.max(0, Math.min(maxX, xIn));
        return Math.round(xIn / 6) * 6;
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
        const sortX = (typeof targetX === "number" && !Number.isNaN(targetX))
                      ? targetX : 1e6;
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
        this._queueAutoSave();    // D5
    }

    // Cascade x positions inside each cabinet group.
    //  - Bases pack left-to-right contiguously on the floor row.
    //  - Walls track their own left-to-right order on the upper row.
    //  - Tall / corner / filler / panel pack at the right end of the
    //    base run (so a drag-dropped tall cab lands after the bases).
    //  - Summary price excludes fillers per the existing convention.
    _recomputeLayoutFromItems() {
        const items = this.state.items || [];
        const sortX = (a, b) => (a.x_position_in || 0) - (b.x_position_in || 0);

        const bases   = items.filter(it => it.cabinet_type === "base").sort(sortX);
        const walls   = items.filter(it => it.cabinet_type === "wall").sort(sortX);
        const tails   = items.filter(it =>
            ["tall", "corner", "filler", "panel"].includes(it.cabinet_type)
        ).sort(sortX);

        let bx = 0;
        for (const b of bases) { b.x_position_in = bx; bx += (b.width_in || 0); }
        let wx = 0;
        for (const w of walls) { w.x_position_in = wx; wx += (w.width_in || 0); }
        for (const t of tails) { t.x_position_in = bx; bx += (t.width_in || 0); }

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

        this.T.cameras = { ortho, persp };
        this.T.activeCamera = ortho;
        this.T.currentTarget = new THREE.Vector3(4, 2.5, 1.5);

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

        // D1 — OrbitControls on the persp camera, disabled until persp
        // view is activated. Defensive: skip if THREE.OrbitControls
        // didn't load (e.g. asset bundle didn't include the UMD shim).
        if (THREE.OrbitControls) {
            const oc = new THREE.OrbitControls(persp, renderer.domElement);
            oc.enableDamping = true;
            oc.dampingFactor = 0.08;
            oc.minDistance   = 4;
            oc.maxDistance   = 80;
            oc.maxPolarAngle = Math.PI / 2 - 0.05;   // never under floor
            oc.enabled       = false;
            this.T.orbit = oc;
        }

        // Render loop — render activeCamera, advance orbit damping when
        // the persp orbit is active.
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
        // of mount) sees it. Lets us cancel orbit when arming a
        // cabinet move via stopPropagation.
        mount.addEventListener("mousedown",  this._onMouseDown, { capture: true });
        mount.addEventListener("mousemove",  this._onMouseMove);
        mount.addEventListener("mouseup",    this._onMouseUp);
        mount.addEventListener("mouseleave", this._onMouseUp);
        mount.addEventListener("mousemove",  this._onMouseOver);
        // D1 — wheel zoom (Ortho frustum scale / Persp dolly via orbit)
        // and view-switch hotkeys (1-6 + R + +/-).
        mount.addEventListener("wheel", this._onWheel, { passive: false });
        window.addEventListener("keydown", this._onKeyDown);
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

    // ─── D1 — Multi-view camera system ──────────────────────────────────────────
    // Compute view specs from current room dimensions. Each entry =
    // { pos: Vector3, target: Vector3, up: Vector3, cam: 'ortho'|'persp',
    //   vs?: number (ortho frustum half-height in scene-feet) }.
    _recomputeViews(rw, rh, rd) {
        const THREE = this.T.THREE;
        const max3  = Math.max(rw, rd, rh);
        const max2  = Math.max(rw, rd);
        const wallH = Math.max(rw, rh);
        const sideH = Math.max(rd, rh);
        this.T.viewSpecs = {
            iso:   { cam: "ortho",
                     pos:    new THREE.Vector3(rw + 12, rh * 0.7 + 6, rd + 12),
                     target: new THREE.Vector3(rw / 2, rh * 0.28, rd / 2),
                     up:     new THREE.Vector3(0, 1, 0),
                     vs:     max3  * 0.68 + 4.5 },
            top:   { cam: "ortho",
                     pos:    new THREE.Vector3(rw / 2, rh + 20, rd / 2),
                     target: new THREE.Vector3(rw / 2, 0, rd / 2),
                     up:     new THREE.Vector3(0, 0, -1),
                     vs:     max2  * 0.60 + 3.0 },
            front: { cam: "ortho",
                     pos:    new THREE.Vector3(rw / 2, rh / 2, rd + 18),
                     target: new THREE.Vector3(rw / 2, rh / 2, 0),
                     up:     new THREE.Vector3(0, 1, 0),
                     vs:     wallH * 0.60 + 2.0 },
            left:  { cam: "ortho",
                     pos:    new THREE.Vector3(-18, rh / 2, rd / 2),
                     target: new THREE.Vector3(0, rh / 2, rd / 2),
                     up:     new THREE.Vector3(0, 1, 0),
                     vs:     sideH * 0.60 + 2.0 },
            right: { cam: "ortho",
                     pos:    new THREE.Vector3(rw + 18, rh / 2, rd / 2),
                     target: new THREE.Vector3(rw, rh / 2, rd / 2),
                     up:     new THREE.Vector3(0, 1, 0),
                     vs:     sideH * 0.60 + 2.0 },
            persp: { cam: "persp",
                     pos:    new THREE.Vector3(rw + 10, rh * 0.9, rd + 10),
                     target: new THREE.Vector3(rw / 2, rh * 0.35, rd / 2),
                     up:     new THREE.Vector3(0, 1, 0) },
        };
    }

    // Apply the current view's ortho frustum + the wheel-zoom multiplier.
    // Safe to call even when the active camera is perspective (no-op).
    _applyOrthoFrustum() {
        const t = this.T;
        const cam = t.cameras?.ortho;
        if (!cam || !t.renderer) return;
        const spec = t.viewSpecs?.[this.state.view];
        const baseVs = (spec && spec.vs) || 9;
        const vs = baseVs * (t.vsScale || 1);
        const W = t.renderer.domElement.width;
        const H = t.renderer.domElement.height;
        const asp = (W && H) ? W / H : 1;
        cam.left  = -vs * asp;  cam.right  = vs * asp;
        cam.top   =  vs;        cam.bottom = -vs;
        cam.near  = 0.1;        cam.far    = 300;
        cam.updateProjectionMatrix();
    }

    // Swap to a named view. instant=true jumps; otherwise lerps over ms.
    _setView(key, instant = false) {
        const t = this.T;
        if (!t.viewSpecs || !t.viewSpecs[key]) return;
        const spec = t.viewSpecs[key];
        this.state.view = key;
        // Reset wheel-zoom on view change for a predictable starting frame.
        t.vsScale = 1;
        // Swap active camera; orbit only enabled in persp.
        if (spec.cam === "ortho") {
            t.activeCamera = t.cameras.ortho;
            if (t.orbit) t.orbit.enabled = false;
        } else {
            t.activeCamera = t.cameras.persp;
            if (t.orbit) {
                t.orbit.enabled = true;
                t.orbit.target.copy(spec.target);
            }
        }
        // Hide/show the drag handle + arrow cones per view (only iso + top
        // expose room-width resize; in other views the right edge isn't
        // visible or doesn't map intuitively to room width).
        const handleVisible = (key === "iso" || key === "top");
        if (t.handleMesh)  t.handleMesh.visible  = handleVisible;
        if (t.arrowMeshes) t.arrowMeshes.forEach(m => { m.visible = handleVisible; });
        if (instant) {
            t.activeCamera.position.copy(spec.pos);
            t.activeCamera.up.copy(spec.up);
            t.activeCamera.lookAt(spec.target);
            t.currentTarget.copy(spec.target);
            this._applyOrthoFrustum();
        } else {
            this._animateCamera(spec.pos, spec.target, spec.up, 400);
            this._applyOrthoFrustum();
        }
    }

    // Lerp the active camera from its current pos+target to the new ones.
    _animateCamera(toPos, toTarget, toUp, ms = 400) {
        const t = this.T;
        const cam = t.activeCamera;
        if (!cam) return;
        const fromPos = cam.position.clone();
        const fromTgt = t.currentTarget.clone();
        const t0 = performance.now();
        const ease = (x) => x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2;
        t.animatingCamera = true;
        const step = () => {
            if (!this.T.activeCamera || this.T.activeCamera !== cam) {
                t.animatingCamera = false;
                return;
            }
            const dt = Math.min(1, (performance.now() - t0) / ms);
            const k  = ease(dt);
            cam.position.lerpVectors(fromPos, toPos, k);
            const tgt = fromTgt.clone().lerp(toTarget, k);
            cam.up.copy(toUp);
            cam.lookAt(tgt);
            t.currentTarget.copy(tgt);
            if (t.orbit && t.orbit.enabled) t.orbit.target.copy(tgt);
            if (dt < 1) requestAnimationFrame(step);
            else        t.animatingCamera = false;
        };
        step();
    }

    _onWheel(e) {
        e.preventDefault();
        const t = this.T;
        const k = e.deltaY > 0 ? 1.1 : 0.9;
        if (t.activeCamera === t.cameras.persp && t.orbit) {
            // Persp dolly via OrbitControls; mirror wheel direction.
            // OrbitControls handles its own wheel internally if enabled,
            // but we keep an explicit fallback for parity in case it
            // gets disabled mid-session.
            return;   // OrbitControls already wired to wheel when enabled
        }
        t.vsScale = Math.max(0.3, Math.min(3.0, (t.vsScale || 1) * k));
        this._applyOrthoFrustum();
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

        // D6 — Esc clears the cabinet selection.
        if (k === "Escape") {
            if (this.state.selected) {
                this.state.selected = null;
                this._highlightSelected(null);
                e.preventDefault();
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

    _destroyScene() {
        const t = this.T;
        // D5 — clear any pending auto-save so we don't fire after the
        // component unmounts (would leak network and warn the console).
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
        if (t.orbit) {
            try { t.orbit.dispose(); } catch (_) { /* noop */ }
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
        const { THREE, scene, renderer } = this.T;
        if (!scene || !renderer) return;

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
            // D8 follow-up — respect the per-item z_position_in the
            // controller computed (varies by wall_cab_top_alignment:
            // fixed_gap / to_ceiling / to_soffit). Falls back to WBY
            // for items that pre-date D8.
            const wbY = (item.z_position_in != null && item.z_position_in !== 0)
                        ? item.z_position_in * IN
                        : WBY;

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

        // D13 — Generic-type fallback: tall / corner / panel cabinets
        // dropped via the inventory drag-and-drop. Renders as a simple
        // PBR box at the item's reported (x, z, dims) so the cabinet
        // becomes visible immediately instead of silently dropping out
        // of the scene. Detailed per-type geometry can layer on top later.
        const knownTypes = new Set(["base", "wall", "filler"]);
        const otherItems = items.filter(it => !knownTypes.has(it.cabinet_type));
        otherItems.forEach(item => {
            const x  = (item.x_position_in || 0) * IN;
            const w  = (item.width_in  || 24) * IN;
            const h  = (item.height_in || 34.5) * IN;
            const d  = (item.depth_in  || 24) * IN;
            const z0 = (item.z_position_in || 0) * IN;

            // Toe-kick for floor-standing types (tall / corner); panels
            // sit flush, no toe-kick.
            if (item.cabinet_type === "tall" || item.cabinet_type === "corner") {
                this.T.cabObjs.push(mk(
                    new THREE.BoxGeometry(w - 0.01, 3.5 * IN, d - 0.01), P.toekick,
                    [x + w/2, z0 + 3.5*IN/2, d/2], null, { cs: true, rough: 0.95, metal: 0.0 }
                ));
                const body = mk(
                    new THREE.BoxGeometry(w - 0.02, h - 3.5*IN, d - 0.02), P.cab,
                    [x + w/2, z0 + 3.5*IN + (h - 3.5*IN)/2, d/2], null,
                    { cs: true, rs: true, rough: 0.55, metal: 0.0,
                      ud: { cab: true, cabType: item.cabinet_type, item } }
                );
                this.T.cabObjs.push(body);
                this.T.clickable.push(body);
            } else {
                // Panel / corner-without-toekick / anything else.
                const body = mk(
                    new THREE.BoxGeometry(w - 0.02, h, d - 0.02), P.cab,
                    [x + w/2, z0 + h/2, d/2], null,
                    { cs: true, rs: true, rough: 0.55, metal: 0.0,
                      ud: { cab: true, cabType: item.cabinet_type, item } }
                );
                this.T.cabObjs.push(body);
                this.T.clickable.push(body);
            }
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
            this.T.arrowMeshes.push(arr);
        });

        // ── D16 — Per-zone drop lanes (visible during drag-from-inventory).
        // BASE lane: thin floor band 24" deep along the back wall.
        // WALL lane: tall band on the back wall sitting at the
        //   configured wall_z (D8 alignment-aware).
        // TALL_END lane: full-height band at the right end of the
        //   base run, where dropped tall / corner / panel land.
        const wallH    = 30 * IN;
        const baseD    = 24 * IN;
        const wallBotZ = WBY;                 // bottom of wall cabinet
        // BASE lane — floor band along back wall, full room width
        const baseLane = new THREE.Mesh(
            new THREE.PlaneGeometry(rw, baseD),
            new THREE.MeshBasicMaterial({
                color: 0x1866d4, transparent: true, opacity: 0.0,
                side: THREE.DoubleSide, depthWrite: false,
            }),
        );
        baseLane.rotation.x = -Math.PI / 2;
        baseLane.position.set(rw / 2, 0.004, baseD / 2);
        baseLane.visible = false;
        scene.add(baseLane);
        // WALL lane — vertical band on the back wall at wall cab z
        const wallLane = new THREE.Mesh(
            new THREE.PlaneGeometry(rw, wallH),
            new THREE.MeshBasicMaterial({
                color: 0x1e9e6a, transparent: true, opacity: 0.0,
                side: THREE.DoubleSide, depthWrite: false,
            }),
        );
        wallLane.position.set(rw / 2, wallBotZ + wallH / 2, 0.004);
        wallLane.visible = false;
        scene.add(wallLane);
        // TALL_END lane — full-height band at the right end of base run,
        //   24" wide × room_height × cabinet depth. Caps at room height.
        const tallH = Math.max(rh - 3.5 * IN, 60 * IN);
        const tallW = 24 * IN;
        const tallLane = new THREE.Mesh(
            new THREE.BoxGeometry(tallW, tallH, baseD),
            new THREE.MeshBasicMaterial({
                color: 0xc89b5a, transparent: true, opacity: 0.0,
                depthWrite: false,
            }),
        );
        // Position at the right edge of current room width
        tallLane.position.set(rw - tallW / 2, 3.5 * IN + tallH / 2, baseD / 2);
        tallLane.visible = false;
        scene.add(tallLane);
        this.T.laneMeshes = { base: baseLane, wall: wallLane, tall: tallLane };
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

    _highlightSelected(item) {
        // Reset all cabinet colours (always — needed for the deselect
        // path so Esc/arrow-cycle visibly clears the previous highlight).
        this.T.cabObjs.forEach(m => {
            if (m.userData?.cab) m.material.color.setHex(P.cab);
        });
        if (!item) return;
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
        const { activeCamera, raycaster, handleMesh, clickable } = this.T;
        if (!activeCamera || !raycaster) return;

        raycaster.setFromCamera(this._ndcFromEvent(e), activeCamera);

        // D1 — drag handle is only sensible in iso/top (where the right
        //      edge of the room is visible + maps to width). In other
        //      views, fall through to cabinet selection.
        const handleActive = (this.state.view === "iso" || this.state.view === "top");
        if (handleActive && handleMesh && raycaster.intersectObject(handleMesh).length) {
            this.T.dragging = true;
            this.T.dragX0   = e.clientX;
            this.T.dragW0   = this.state.room.width_in;
            e.preventDefault();
            return;
        }

        // Cabinet selection — works in every view. D15 — also arms a
        // potential move: actual move only commits if the cursor
        // travels >5px before mouseup (otherwise this stays a click +
        // select).
        const hits = raycaster.intersectObjects(clickable, false);
        if (hits.length) {
            const h = hits[0].object;
            if (h.userData?.item) {
                this._selectCabinet(h.userData.item);
                // D15 — arm move on this item. Skip fillers (their
                // position is computed; manual moves don't make sense).
                if (h.userData.item.cabinet_type !== "filler") {
                    this.T.movingItem      = h.userData.item;
                    this.T.moveStartClient = { x: e.clientX, y: e.clientY };
                    this.T.moveLastX       = h.userData.item.x_position_in;
                    this.T.moveCommitted   = false;
                    // D15 — Stop propagation so OrbitControls (capture-
                    // bound on canvas below) doesn't also start an
                    // orbit gesture on the same mousedown. Empty-space
                    // clicks fall through to OrbitControls normally.
                    e.preventDefault();
                    e.stopPropagation();
                }
            }
        }
    }

    _onMouseMove(e) {
        // Room-width drag handle (existing).
        if (this.T.dragging) {
            const dx = e.clientX - this.T.dragX0;
            // ~55 px ≈ 1 ft at typical zoom
            const nw = Math.max(12, Math.min(288, this.T.dragW0 + dx * (12 / 55)));
            this.state.room.width_in = Math.round(nw / 6) * 6; // snap to 6-inch grid
            return;
        }

        // D15 — Cabinet drag-to-reposition. Disambiguate from a plain
        // click by requiring >5px of cursor travel before committing
        // to a move. Once committed, snap to the 6" grid via the
        // floor-plane raycast and rebuild only when the snapped slot
        // actually changes (naturally throttles _buildScene to ~once
        // per grid step, not once per pixel).
        if (this.T.movingItem) {
            const dx = e.clientX - this.T.moveStartClient.x;
            const dy = e.clientY - this.T.moveStartClient.y;
            if (!this.T.moveCommitted && Math.hypot(dx, dy) < 5) return;
            if (!this.T.moveCommitted) {
                this.T.moveCommitted = true;
                const cvs = this.T.renderer && this.T.renderer.domElement;
                if (cvs) cvs.style.cursor = "move";
            }
            const targetX = this._computeDropX(e);
            // Null = floor not intersected (side views with orthographic
            // rays parallel to the floor). Silent no-op; user can
            // switch to Iso/Top/Persp to move.
            if (targetX == null) return;
            if (this.T.movingItem.x_position_in === targetX) return;
            this.T.movingItem.x_position_in = targetX;
            this.T.moveLastX = targetX;
            // Live preview: rebuild scene with the moving cabinet at
            // its new x. Other items stay in their current packed
            // positions until mouseup runs the full cascade.
            if (this.T.scene) this._buildScene();
        }
    }

    _onMouseUp() {
        if (this.T.dragging) {
            this.T.dragging = false;
            this._refreshLayout().then(() => this._queueAutoSave());   // D5
        }

        // D15 — Finalize cabinet move. If the user dragged (committed),
        // run the cascade so neighbours pack contiguously, rebuild
        // the scene, and queue an auto-save. If they only clicked
        // (no move committed), the selection from mousedown was
        // already applied — just clear the move-arm state.
        if (this.T.movingItem) {
            const item = this.T.movingItem;
            const wasCommitted = this.T.moveCommitted;
            this.T.movingItem    = null;
            this.T.moveCommitted = false;
            const cvs = this.T.renderer && this.T.renderer.domElement;
            if (cvs) cvs.style.cursor = "";
            if (wasCommitted) {
                this._recomputeLayoutFromItems();
                if (this.T.scene) this._buildScene();
                this.notification.add(
                    `Moved ${item.name} to ${item.x_position_in}″`,
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
        // set it to "move"); the move-commit/finalize path resets it.
        if (this.T.movingItem && this.T.moveCommitted) return;
        this.T.raycaster.setFromCamera(this._ndcFromEvent(e), this.T.activeCamera);
        const handleActive = (this.state.view === "iso" || this.state.view === "top");
        const onH = handleActive && this.T.handleMesh &&
            this.T.raycaster.intersectObject(this.T.handleMesh).length > 0;
        const onC = !onH &&
            this.T.raycaster.intersectObjects(this.T.clickable, false).length > 0;
        const cvs = this.T.renderer?.domElement;
        // D15 — grab cursor over cabinets to hint they're draggable.
        if (cvs) cvs.style.cursor = this.T.dragging ? "ew-resize"
                                  : onH ? "ew-resize"
                                  : onC ? "grab"
                                        : "default";
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
