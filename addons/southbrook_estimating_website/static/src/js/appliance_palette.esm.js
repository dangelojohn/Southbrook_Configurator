/** @odoo-module **/
/*
 * SPDX-License-Identifier: LGPL-3.0-only
 *
 * AppliancePalette — Stage C (2026-06-28). Docked sidebar component
 * that lists the kitchen appliance placeholder catalog + standard
 * window / door sizes as drag-able thumbnails. The designer drags
 * a thumbnail onto FloorPlanSVG and the parent (RoomLayoutTab /
 * OrderBuilder) handles the wall-snap + RPC create.
 *
 * Component lives in its own file (rather than tacked onto the
 * already-large room_layout.esm.js) for two reasons: (a) blast-radius
 * — a bug in palette JS can't crash the floor-plan render, and (b)
 * future asset-bundle splitting — only pages that need the palette
 * pull in this module.
 *
 * Drag protocol (pointer events for mouse+touch+pen parity):
 *
 *   pointerdown on .sb-palette-item
 *     ↳ state.dragState = { template, constraintType, ghostX, ghostY }
 *     ↳ document captures pointermove + pointerup
 *
 *   pointermove (anywhere on document)
 *     ↳ update state.dragState.ghostX/Y so the ghost preview tracks
 *       the cursor.
 *
 *   pointerup (anywhere on document)
 *     ↳ hit-test via document.elementFromPoint → look for an ancestor
 *       SVG carrying `sb-room-plan-svg`. If found, emit onTemplateDrop
 *       with the SVG-local px coords. Parent translates px → mm →
 *       wall + offset and dispatches the RPC.
 *
 * Standard openings (windows + doors) are hardcoded synthetic records.
 * They look like product.template records to the consumer but carry no
 * `id` — the parent recognises this and creates a constraint without
 * setting appliance_template_id (just constraint_type + width + height).
 */
import { Component, onWillStart, useExternalListener, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

// Standard NA window sizes (inches × inches → mm). Sill height is
// kitchen-typical 900mm; over-sink windows often sit at 1100mm sill
// — the designer can adjust after placement.
const WINDOW_STD = [
    ["24\" × 24\" Window (over-sink)", 610, 610, 1100],
    ["24\" × 36\" Window", 610, 914, 900],
    ["36\" × 36\" Window", 914, 914, 900],
    ["36\" × 48\" Window", 914, 1219, 900],
    ["48\" × 36\" Window", 1219, 914, 900],
    ["48\" × 48\" Window", 1219, 1219, 900],
    ["60\" × 48\" Window", 1524, 1219, 900],
    ["72\" × 48\" Window (picture)", 1829, 1219, 900],
].map(([name, w, h, sill], idx) => ({
    synthetic: true,
    syntheticKey: `window-${idx}`,
    name,
    default_code: `WIN-${Math.round(w / 25.4)}x${Math.round(h / 25.4)}`,
    kitchen_appliance_type: "window",
    kitchen_appliance_width_mm: w,
    kitchen_appliance_depth_mm: 100,
    kitchen_appliance_height_mm: h,
    kitchen_appliance_sill_mm: sill,
}));

// Standard NA door sizes (interior + exterior). The swing column is
// the default swing_direction the constraint gets created with;
// designer can flip in the constraint form.
const DOOR_STD = [
    ["30\" × 80\" Interior Door (RH)", 762, 2030, "right"],
    ["30\" × 80\" Interior Door (LH)", 762, 2030, "left"],
    ["32\" × 80\" Interior Door (RH)", 813, 2030, "right"],
    ["32\" × 80\" Interior Door (LH)", 813, 2030, "left"],
    ["36\" × 80\" Door (RH)", 914, 2030, "right"],
    ["36\" × 80\" Door (LH)", 914, 2030, "left"],
    ["36\" × 84\" Door (RH, tall)", 914, 2134, "right"],
    ["32\" × 80\" Pocket Door", 813, 2030, "pocket"],
    ["36\" × 80\" Pocket Door", 914, 2030, "pocket"],
    ["48\" × 80\" Sliding Door", 1219, 2030, "sliding"],
    ["60\" × 80\" Sliding Door", 1524, 2030, "sliding"],
    ["48\" × 80\" Bifold Door", 1219, 2030, "bifold"],
    ["60\" × 80\" Bifold Door", 1524, 2030, "bifold"],
].map(([name, w, h, swing], idx) => ({
    synthetic: true,
    syntheticKey: `door-${idx}`,
    name,
    default_code: `DOOR-${Math.round(w / 25.4)}-${swing.toUpperCase().slice(0, 3)}`,
    kitchen_appliance_type: "door",
    kitchen_appliance_width_mm: w,
    kitchen_appliance_depth_mm: 100,
    kitchen_appliance_height_mm: h,
    swing_direction: swing,
}));

// Mapping appliance_type → constraint_type for synthetic windows/doors
// and template-backed appliances. Mirrors LEGACY_TYPE_MAP server-side
// in sb_kitchen_appliance.py + the _TEMPLATE_TYPE_MAP in
// southbrook_room_constraint.py. Kept here so the palette can pass
// the constraint_type to the parent for an immediate create RPC
// without round-tripping through the server.
const TEMPLATE_TYPE_TO_CONSTRAINT = {
    window: "window",
    door: "door",
    range: "range",
    cooktop: "cooktop",
    wall_oven: "oven",
    wall_oven_double: "oven",
    microwave: "microwave",
    steam_oven: "oven",
    speed_oven: "oven",
    warming_drawer: "warming_drawer",
    range_hood: "rangehood",
    refrigerator: "fridge_space",
    freezer: "freezer",
    refrigerator_drawer: "fridge_space",
    wine_fridge: "wine_fridge",
    beverage_center: "beverage_center",
    ice_maker: "ice_maker",
    dishwasher: "dishwasher",
    sink: "sink",
    disposal: "other",
    trash_compactor: "trash_compactor",
    coffee_built_in: "coffee_built_in",
    other: "other",
};

// Group display order — drives the section ordering in the palette
// so designers always find the same category in the same spot.
//
// NOTE — `_grouped` (below) keys sections by the RAW
// `kitchen_appliance_type` field on product.template (e.g. wall_oven,
// refrigerator, range_hood), NOT by constraint_type (oven,
// fridge_space, rangehood…). Both vocabularies are listed here so
// every real-world key gets a stable slot instead of falling through
// to the unmapped catch-loop in `_grouped`.
const GROUP_ORDER = [
    "window", "door",
    "range", "cooktop",
    "wall_oven", "wall_oven_double", "steam_oven", "speed_oven",
    "oven", "microwave", "warming_drawer",
    "sink", "dishwasher",
    "fridge_space", "refrigerator", "refrigerator_drawer",
    "freezer", "wine_fridge", "beverage_center", "ice_maker",
    "rangehood", "range_hood",
    "coffee_built_in", "trash_compactor", "disposal",
    "other",
];

// Human labels for the section headers — kept in this file (not derived
// from the constraint_type selection at runtime) so the palette is
// self-contained. Covers both the constraint_type keys (oven,
// fridge_space, rangehood…) and the raw kitchen_appliance_type keys
// (wall_oven, refrigerator, range_hood…) that `_grouped` actually
// buckets on. Any key not listed here falls back to `_humanizeKey()`
// rather than rendering raw (e.g. "wall_oven_double").
const GROUP_LABELS = {
    window: "Windows",
    door: "Doors",
    range: "Ranges",
    cooktop: "Cooktops",
    oven: "Wall Ovens",
    wall_oven: "Wall Ovens",
    wall_oven_double: "Double Wall Ovens",
    steam_oven: "Steam Ovens",
    speed_oven: "Speed Ovens",
    microwave: "Microwaves",
    warming_drawer: "Warming Drawers",
    sink: "Sinks",
    dishwasher: "Dishwashers",
    fridge_space: "Refrigerators",
    refrigerator: "Refrigerators",
    refrigerator_drawer: "Refrigerator Drawers",
    freezer: "Freezers",
    wine_fridge: "Wine Fridges",
    beverage_center: "Beverage Centers",
    ice_maker: "Ice Makers",
    rangehood: "Range Hoods",
    range_hood: "Range Hoods",
    coffee_built_in: "Built-In Coffee",
    trash_compactor: "Trash Compactors",
    disposal: "Disposals",
    other: "Other",
};


export class AppliancePalette extends Component {
    static template = "southbrook_estimating_website.AppliancePalette";
    static props = {
        roomId: { type: [Number, Boolean], optional: true },
        onTemplateDrop: { type: Function, optional: true },
        onDragStateChange: { type: Function, optional: true },
        unitPreference: { type: String, optional: true },
        // Stage D — parent supplies a probe that resolves a client
        // coord to a {wallId, wallName, offsetMm, wallLengthMm} hit
        // info (or null when the cursor isn't over any wall). The
        // palette calls this on every pointermove during drag so the
        // ghost preview can show "→ Wall A @ 850mm" feedback in
        // real time. Optional — when absent, ghost shows only the
        // template name + dimensions (Stage C behavior).
        getDropTarget: { type: Function, optional: true },
        // Click-to-place (2026-07-03) — parent-supplied callback fired
        // whenever an item is armed/disarmed via the per-item "Place"
        // button or Enter/Space/Escape on the focused <li>. Mirrors
        // onDragStateChange's { active, item, constraintType } shape
        // so RoomLayoutTab can reuse one mental model for "something
        // is about to be placed" regardless of which path triggered it.
        onArmChange: { type: Function, optional: true },
        // Click-to-place — the currently-armed item key (id or
        // syntheticKey), owned by the PARENT (RoomLayoutTab). The
        // palette derives its highlight from this prop rather than a
        // local state so a parent-side disarm (Escape at the document
        // level, or after a canvas / wall-row placement) reliably
        // clears the highlight — otherwise the placed item would stay
        // visually armed until its next click.
        armedKey: { type: [Number, String, Boolean], optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            templates: [],
            loading: true,
            search: "",
            collapsedGroups: {},
            dragState: null,
        });
        onWillStart(async () => {
            await this._loadTemplates();
        });
        // Document-level listeners — captured globally so a pointer up
        // outside the palette still resolves the drag (the user dragged
        // ONTO the canvas, which is necessarily outside .sb-palette).
        useExternalListener(document, "pointermove", this._onDragMove);
        useExternalListener(document, "pointerup", this._onDragEnd);
        useExternalListener(document, "pointercancel", this._onDragCancel);
    }

    async _loadTemplates() {
        try {
            const records = await this.orm.searchRead(
                "product.template",
                [["is_kitchen_appliance", "=", true]],
                [
                    "id", "name", "default_code",
                    "kitchen_appliance_type",
                    "kitchen_appliance_install_type",
                    "kitchen_appliance_fuel_type",
                    "kitchen_appliance_width_mm",
                    "kitchen_appliance_depth_mm",
                    "kitchen_appliance_height_mm",
                    "kitchen_appliance_clearance_mm",
                ],
                { order: "kitchen_appliance_type, kitchen_appliance_width_mm" },
            );
            this.state.templates = records;
        } catch (err) {
            // Read may fail when the database hasn't applied Stage A
            // yet (fields missing). Degrade gracefully — palette
            // still shows windows + doors from the hardcoded list.
            console.warn("AppliancePalette: template load failed", err);
            this.state.templates = [];
        }
        this.state.loading = false;
    }

    get _filteredItems() {
        const search = (this.state.search || "").trim().toLowerCase();
        const all = [
            ...WINDOW_STD,
            ...DOOR_STD,
            ...this.state.templates,
        ];
        if (!search) return all;
        return all.filter((t) =>
            (t.name || "").toLowerCase().includes(search) ||
            (t.default_code || "").toLowerCase().includes(search)
        );
    }

    get _grouped() {
        const groups = {};
        for (const t of this._filteredItems) {
            const k = t.kitchen_appliance_type || "other";
            if (!groups[k]) groups[k] = [];
            groups[k].push(t);
        }
        // Return ordered (group, items) pairs so the template can
        // render with stable section ordering.
        const ordered = [];
        for (const k of GROUP_ORDER) {
            if (groups[k] && groups[k].length) {
                ordered.push({
                    key: k,
                    label: GROUP_LABELS[k] || this._humanizeKey(k),
                    items: groups[k],
                    collapsed: !!this.state.collapsedGroups[k],
                });
            }
        }
        // Catch any unmapped group keys. GROUP_LABELS/GROUP_ORDER above
        // should cover every real kitchen_appliance_type, but this stays
        // as a safety net for future catalog values — humanized, never
        // raw, so a new type never shows a bare snake_case key.
        for (const k of Object.keys(groups)) {
            if (!GROUP_ORDER.includes(k)) {
                ordered.push({
                    key: k,
                    label: GROUP_LABELS[k] || this._humanizeKey(k),
                    items: groups[k],
                    collapsed: !!this.state.collapsedGroups[k],
                });
            }
        }
        return ordered;
    }

    // Fallback label formatter for any group key not covered by
    // GROUP_LABELS — "refrigerator_drawer" → "Refrigerator Drawer".
    // Never returns the raw snake_case key.
    _humanizeKey(k) {
        return (k || "")
            .split("_")
            .filter((word) => word)
            .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
            .join(" ");
    }

    _toggleGroup(groupKey) {
        this.state.collapsedGroups[groupKey] =
            !this.state.collapsedGroups[groupKey];
    }

    // Click-to-place — is this specific item the currently armed one?
    // Returns the modifier class (or "") so the template can compose
    // it additively alongside the static "sb-palette-item" class.
    _itemArmedClass(item) {
        const key = item.id || item.syntheticKey;
        return (this.props.armedKey && this.props.armedKey === key)
            ? "sb-palette-item--armed" : "";
    }

    _itemDisplaySize(item) {
        // Render the W×D in the unit the parent prefers.
        const w = Math.round(item.kitchen_appliance_width_mm || 0);
        const d = Math.round(item.kitchen_appliance_depth_mm || 0);
        if (!w) return "";
        if ((this.props.unitPreference || "mm") === "imperial") {
            const wi = Math.round(w / 25.4);
            const di = Math.round(d / 25.4);
            return d ? `${wi}\" × ${di}\"` : `${wi}\"`;
        }
        return d ? `${w} × ${d} mm` : `${w} mm`;
    }

    _ghostStatusClass(snapInfo) {
        // Stage D5 — pick the ghost-preview modifier class from the
        // snap info's status: ok → green border; tight → amber; overlap
        // → red. Null (off-wall) leaves the ghost neutral.
        if (!snapInfo) return "";
        if (snapInfo.status === "overlap") return "sb-palette-ghost--overlap";
        if (snapInfo.status === "tight") return "sb-palette-ghost--tight";
        return "sb-palette-ghost--targeting";
    }

    _onItemPointerDown(item, ev) {
        // Pointerdown begins drag; we DO NOT setPointerCapture here —
        // the document-level pointermove + pointerup do the tracking.
        // setPointerCapture would lock events to the source element
        // and break the hit-test on pointerup (which needs to find
        // the SVG under the cursor).
        if (ev.button !== undefined && ev.button !== 0) return;  // left-click / primary touch only
        ev.preventDefault();
        const constraintType =
            TEMPLATE_TYPE_TO_CONSTRAINT[item.kitchen_appliance_type] || "other";
        this.state.dragState = {
            template: item,
            constraintType,
            ghostX: ev.clientX,
            ghostY: ev.clientY,
            snapInfo: null,  // Stage D — populated on each pointermove
        };
        if (this.props.onDragStateChange) {
            this.props.onDragStateChange({ active: true, item, constraintType });
        }
    }

    // Click-to-place (2026-07-03) — "arm then click a wall" path,
    // additive alongside pointer-drag. Toggles the armed state for
    // this item: arming a second item implicitly disarms whatever was
    // armed before (only one at a time makes sense — the designer is
    // placing one thing). Called from the per-item "Place" button
    // (t-on-click, already stops its own pointerdown from bubbling)
    // and from _onItemKeydown (Enter/Space). ev is optional — Escape
    // disarming goes through _disarmItem() instead, which has no event.
    _onArmItem(item, ev) {
        if (ev) ev.stopPropagation();
        const key = item.id || item.syntheticKey;
        // Toggle against the parent-owned armedKey — arming the already-
        // armed item disarms it; arming a different item re-arms. The
        // parent flips its state in onArmChange and the new armedKey
        // flows back down as a prop.
        const nextActive = this.props.armedKey !== key;
        if (this.props.onArmChange) {
            const constraintType = nextActive
                ? (TEMPLATE_TYPE_TO_CONSTRAINT[item.kitchen_appliance_type] || "other")
                : null;
            this.props.onArmChange({
                active: nextActive,
                item: nextActive ? item : null,
                constraintType,
            });
        }
    }

    // Escape (from _onItemKeydown) or an external disarm request —
    // clears the armed state without toggling (Escape always cancels,
    // it never re-arms).
    _disarmItem() {
        if (!this.props.armedKey) return;
        if (this.props.onArmChange) {
            this.props.onArmChange({ active: false, item: null, constraintType: null });
        }
    }

    // Keyboard path for the focusable <li> (tabindex="0"): Enter/Space
    // arms (mirrors clicking "Place"); Escape disarms. Any other key
    // is left alone (no interference with normal tab/arrow navigation).
    _onItemKeydown(item, ev) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this._onArmItem(item, ev);
        } else if (ev.key === "Escape") {
            if (this.props.armedKey) {
                ev.preventDefault();
                this._disarmItem();
            }
        }
    }

    _onDragMove = (ev) => {
        if (!this.state.dragState) return;
        this.state.dragState.ghostX = ev.clientX;
        this.state.dragState.ghostY = ev.clientY;
        // Stage D — ask the parent to resolve where this would land.
        // null when off-wall. Reactive state update re-renders the
        // ghost with the new snap chip.
        if (typeof this.props.getDropTarget === "function") {
            const tmpl = this.state.dragState.template;
            const itemW = tmpl.kitchen_appliance_width_mm || 600;
            try {
                this.state.dragState.snapInfo =
                    this.props.getDropTarget(ev.clientX, ev.clientY, itemW)
                    || null;
            } catch (e) {
                this.state.dragState.snapInfo = null;
            }
        }
    };

    _onDragEnd = (ev) => {
        if (!this.state.dragState) return;
        const finalState = this.state.dragState;
        this.state.dragState = null;
        if (this.props.onDragStateChange) {
            this.props.onDragStateChange({ active: false });
        }
        // Hit-test: is pointer over a FloorPlanSVG?
        const target = document.elementFromPoint(ev.clientX, ev.clientY);
        const svg = target ? target.closest("svg.sb-room-plan-svg") : null;
        if (!svg) return;
        if (!this.props.onTemplateDrop) return;
        const rect = svg.getBoundingClientRect();
        this.props.onTemplateDrop({
            template: finalState.template,
            constraintType: finalState.constraintType,
            clientX: ev.clientX,
            clientY: ev.clientY,
            svgX: ev.clientX - rect.left,
            svgY: ev.clientY - rect.top,
            svgWidth: rect.width,
            svgHeight: rect.height,
        });
    };

    _onDragCancel = () => {
        if (!this.state.dragState) return;
        this.state.dragState = null;
        if (this.props.onDragStateChange) {
            this.props.onDragStateChange({ active: false });
        }
    };
}
