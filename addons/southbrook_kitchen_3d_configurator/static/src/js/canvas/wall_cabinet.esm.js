/** @odoo-module **/
/**
 * Southbrook Kitchen 3D Configurator — wall cabinet mesh builder.
 *
 * Rec D · Sprint 2d · Step 16 · closure-body extraction.
 *
 * Extracted verbatim from kitchen_configurator.js:1312-1361
 * (the `wallItems.forEach` block). Builds each wall cabinet: body
 * carcass, shaker door, wall handle, bottom rail, and the pin
 * indicator sphere (when item.pinned).
 *
 * D8 follow-up — respects the per-item z_position_in the controller
 * computed (varies by wall_cab_top_alignment: fixed_gap /
 * to_ceiling / to_soffit). Falls back to WBY for items that pre-
 * date D8.
 *
 * Zero behaviour change from the pre-2d inline block.
 */

import { IN, WBY } from "@southbrook_kitchen_3d_configurator/js/canvas/constants";

/**
 * @param {typeof THREE} THREE
 * @param {(geo:any, color:number, pos:any, rotE:any, opts?:object) => THREE.Mesh} mk
 * @param {object} palette
 * @param {object} item
 * @returns {{ objects: THREE.Mesh[], clickable: THREE.Mesh[] }}
 */
export function buildWallCabinet(THREE, mk, palette, item) {
    const x   = item.x_position_in * IN;
    const wbW = item.width_in  * IN;
    const wbH = item.height_in * IN;
    const wbD = item.depth_in  * IN;
    const wbY = (item.z_position_in != null && item.z_position_in !== 0)
                ? item.z_position_in * IN
                : WBY;

    const objects = [];
    const clickable = [];

    // Wall body — satin-lacquer carcass
    const wbody = mk(
        new THREE.BoxGeometry(wbW - 0.02, wbH, wbD - 0.02), palette.cab,
        [x + wbW/2, wbY + wbH/2, wbD/2], null,
        { cs: true, rs: true, rough: 0.55, metal: 0.0,
          ud: { cab: true, cabType: "wall", item } },
    );
    objects.push(wbody);
    clickable.push(wbody);

    // Shaker door
    objects.push(mk(
        new THREE.BoxGeometry(wbW - 0.10, wbH - 0.10, 0.016), palette.cabDark,
        [x + wbW/2, wbY + wbH/2, wbD - 0.001], null,
        { rough: 0.6, metal: 0.05, ud: { cab: true, cabType: "wall", item } },
    ));
    // Wall handle — brushed metal
    objects.push(mk(
        new THREE.BoxGeometry(wbW * 0.38, 0.025, 0.038), palette.handle,
        [x + wbW/2, wbY + wbH * 0.60, wbD + 0.018], null,
        { rough: 0.35, metal: 0.85 },
    ));
    // Bottom rail — matches the countertop sheen
    objects.push(mk(
        new THREE.BoxGeometry(wbW - 0.02, 0.025, wbD - 0.02), palette.counter,
        [x + wbW/2, wbY - 0.010, wbD/2], null,
        { rough: 0.4, metal: 0.05 },
    ));

    // Pin indicator
    if (item.pinned) {
        objects.push(mk(
            new THREE.SphereGeometry(0.06, 14, 14), 0x18B4A6,
            [x + wbW - 0.10, wbY + wbH - 0.10, wbD - 0.10], null,
            { rough: 0.3, metal: 0.5 },
        ));
    }

    return { objects, clickable };
}
