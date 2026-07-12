/** @odoo-module **/
/**
 * Southbrook Kitchen 3D Configurator — tall / corner / panel / filler
 * / end-cap cabinet mesh builders.
 *
 * Rec D · Sprint 2d · Steps 17-19 · closure-body extraction.
 *
 * Extracted verbatim from kitchen_configurator.js:1327-1412. Three
 * exports covering the remaining cabinet shapes:
 *
 *   buildOtherCabinet(THREE, mk, palette, item) — tall / corner
 *     (with toe-kick) and generic panel-shaped items (no toe-kick).
 *     Also handles the pin indicator for tall + corner only.
 *
 *   buildFillerPanel(THREE, mk, palette, item) — the thin BH-height
 *     filler panel that bridges gaps between cabinets.
 *
 *   buildEndCapPanel(THREE, mk, palette, item) — decorative end-cap
 *     panel: full-height, full-depth of the host cabinet, panel-
 *     width thick (default 3/4"). x_position_in is authoritative.
 *
 * Zero behaviour change from the pre-2d inline blocks.
 */

import { IN, BH } from "@southbrook_kitchen_3d_configurator/js/canvas/constants.esm";

/**
 * @param {typeof THREE} THREE
 * @param {(geo:any, color:number, pos:any, rotE:any, opts?:object) => THREE.Mesh} mk
 * @param {object} palette
 * @param {object} item
 * @returns {{ objects: THREE.Mesh[], clickable: THREE.Mesh[] }}
 */
export function buildOtherCabinet(THREE, mk, palette, item) {
    const x  = (item.x_position_in || 0) * IN;
    const w  = (item.width_in  || 24) * IN;
    const h  = (item.height_in || 34.5) * IN;
    const d  = (item.depth_in  || 24) * IN;
    // Local-frame build (side-wall group render): z comes from the enclosing
    // group, so build at local z=0; otherwise use the item's own Z offset.
    const z0 = item.__localFrame ? 0 : (item.z_position_in || 0) * IN;

    const objects = [];
    const clickable = [];

    // Toe-kick for floor-standing types (tall / corner); panels sit
    // flush, no toe-kick.
    if (item.cabinet_type === "tall" || item.cabinet_type === "corner") {
        objects.push(mk(
            new THREE.BoxGeometry(w - 0.01, 3.5 * IN, d - 0.01), palette.toekick,
            [x + w/2, z0 + 3.5*IN/2, d/2], null,
            { cs: true, rough: 0.95, metal: 0.0 },
        ));
        const body = mk(
            new THREE.BoxGeometry(w - 0.02, h - 3.5*IN, d - 0.02), palette.cab,
            [x + w/2, z0 + 3.5*IN + (h - 3.5*IN)/2, d/2], null,
            { cs: true, rs: true, rough: 0.55, metal: 0.0,
              ud: { cab: true, cabType: item.cabinet_type, item } },
        );
        objects.push(body);
        clickable.push(body);
    } else {
        // Panel / corner-without-toekick / anything else.
        const body = mk(
            new THREE.BoxGeometry(w - 0.02, h, d - 0.02), palette.cab,
            [x + w/2, z0 + h/2, d/2], null,
            { cs: true, rs: true, rough: 0.55, metal: 0.0,
              ud: { cab: true, cabType: item.cabinet_type, item } },
        );
        objects.push(body);
        clickable.push(body);
    }

    // Pin indicator on tall / corner only (skip panels — end-caps
    // aren't user-pinnable per Stage 1's _onMouseUp filter).
    if (item.pinned
        && (item.cabinet_type === "tall"
            || item.cabinet_type === "corner")) {
        objects.push(mk(
            new THREE.SphereGeometry(0.06, 14, 14), 0x18B4A6,
            [x + w - 0.10, z0 + h + 0.16, d - 0.10], null,
            { rough: 0.3, metal: 0.5 },
        ));
    }

    return { objects, clickable };
}

/**
 * Filler panel — matte/satin, matches the door style. Sits between
 * cabinets to bridge non-modular gaps.
 *
 * @param {typeof THREE} THREE
 * @param {(geo:any, color:number, pos:any, rotE:any, opts?:object) => THREE.Mesh} mk
 * @param {object} palette
 * @param {object} item
 * @returns {THREE.Mesh}
 */
export function buildFillerPanel(THREE, mk, palette, item) {
    const x   = item.x_position_in * IN;
    const fpW = item.width_in * IN;
    return mk(
        new THREE.BoxGeometry(fpW, BH, 0.042), palette.cabDark,
        [x + fpW/2, BH/2, 0.021], null,
        { rough: 0.55, metal: 0.0 },
    );
}

/**
 * End-cap decorative panel — thin vertical panel: full height, full
 * depth of the host cabinet, panel-width thick (default 3/4").
 * x_position_in is authoritative and must NOT be recomputed at
 * layout time.
 *
 * @param {typeof THREE} THREE
 * @param {(geo:any, color:number, pos:any, rotE:any, opts?:object) => THREE.Mesh} mk
 * @param {object} palette
 * @param {object} item
 * @returns {{ objects: THREE.Mesh[], clickable: THREE.Mesh[] }}
 */
export function buildEndCapPanel(THREE, mk, palette, item) {
    const x  = (item.x_position_in || 0) * IN;
    const w  = (item.width_in  || 0.75) * IN;
    const h  = (item.height_in || 34.5) * IN;
    const d  = (item.depth_in  || 24)   * IN;
    // Local-frame build (side-wall group render): z comes from the enclosing
    // group, so build at local z=0; otherwise use the item's own Z offset.
    const z0 = item.__localFrame ? 0 : (item.z_position_in || 0) * IN;

    const body = mk(
        new THREE.BoxGeometry(w - 0.01, h, d - 0.01), palette.cab,
        [x + w/2, z0 + h/2, d/2], null,
        { cs: true, rs: true, rough: 0.45, metal: 0.0,
          ud: { cab: true, cabType: "panel", item } },
    );

    return { objects: [body], clickable: [body] };
}
