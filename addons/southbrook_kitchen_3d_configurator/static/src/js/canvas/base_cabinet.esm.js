/** @odoo-module **/
/**
 * Southbrook Kitchen 3D Configurator — base cabinet mesh builder.
 *
 * Rec D · Sprint 2d · Step 15 · closure-body extraction.
 *
 * Extracted verbatim from kitchen_configurator.js:1301-1377 —
 * the `baseItems.forEach` block. Builds every mesh that composes
 * a single base cabinet at world position (x_position_in): toe
 * kick, carcass body, shaker door, drawer face, door handle,
 * drawer handle, countertop, drip edge, and the v4.24.0 pin
 * indicator sphere (when item.pinned).
 *
 * Returns two flat arrays:
 *   - objects: every mesh created (cabObjs push target)
 *   - clickable: subset the raycaster should hit (currently: body)
 *
 * Zero behaviour change from the pre-2d inline block.
 */

import { IN, CTR } from "@southbrook_kitchen_3d_configurator/js/canvas/constants";

/**
 * @param {typeof THREE} THREE
 * @param {(geo:any, color:number, pos:any, rotE:any, opts?:object) => THREE.Mesh} mk
 * @param {object} palette — hex colors {toekick, cab, cabDark, handle, counter}
 * @param {object} item — southbrook.kitchen.design.line dict
 * @returns {{ objects: THREE.Mesh[], clickable: THREE.Mesh[] }}
 */
export function buildBaseCabinet(THREE, mk, palette, item) {
    const x   = item.x_position_in * IN;
    const cbW = item.width_in  * IN;
    const cbH = item.height_in * IN;
    const cbD = item.depth_in  * IN;

    const objects = [];
    const clickable = [];

    // Toe kick — flat black/matte
    objects.push(mk(
        new THREE.BoxGeometry(cbW - 0.01, 3.5 * IN, cbD - 0.01), palette.toekick,
        [x + cbW/2, 3.5*IN/2, cbD/2], null, { cs: true, rough: 0.95, metal: 0.0 },
    ));

    // Cabinet body — satin-lacquer carcass
    const body = mk(
        new THREE.BoxGeometry(cbW - 0.02, cbH - 3.5*IN, cbD - 0.02), palette.cab,
        [x + cbW/2, 3.5*IN + (cbH - 3.5*IN)/2, cbD/2], null,
        { cs: true, rs: true, rough: 0.55, metal: 0.0,
          ud: { cab: true, cabType: "base", item } },
    );
    objects.push(body);
    clickable.push(body);

    // Shaker door upper inset — slightly glossier than carcass
    const dH = (cbH - 3.5*IN) * 0.60;
    objects.push(mk(
        new THREE.BoxGeometry(cbW - 0.10, dH, 0.016), palette.cabDark,
        [x + cbW/2, 3.5*IN + (cbH - 3.5*IN) * 0.72 - dH/2, cbD - 0.001], null,
        { rough: 0.6, metal: 0.05, ud: { cab: true, cabType: "base", item } },
    ));

    // Drawer face
    objects.push(mk(
        new THREE.BoxGeometry(cbW - 0.10, (cbH - 3.5*IN) * 0.21, 0.016), palette.cab,
        [x + cbW/2, 3.5*IN + (cbH - 3.5*IN) * 0.13, cbD - 0.001], null,
        { rough: 0.55, metal: 0.0, ud: { cab: true, cabType: "base", item } },
    ));

    // Door handle — brushed metal
    objects.push(mk(
        new THREE.BoxGeometry(cbW * 0.44, 0.025, 0.040), palette.handle,
        [x + cbW/2, 3.5*IN + (cbH - 3.5*IN) * 0.42, cbD + 0.018], null,
        { rough: 0.35, metal: 0.85 },
    ));
    // Drawer handle — same brushed metal
    objects.push(mk(
        new THREE.BoxGeometry(cbW * 0.30, 0.025, 0.038), palette.handle,
        [x + cbW/2, 3.5*IN + (cbH - 3.5*IN) * 0.13, cbD + 0.018], null,
        { rough: 0.35, metal: 0.85 },
    ));

    // Countertop — quartz/stone
    objects.push(mk(
        new THREE.BoxGeometry(cbW + 0.005, CTR, cbD + 0.07), palette.counter,
        [x + cbW/2, cbH + CTR/2, cbD/2 + 0.03], null,
        { cs: true, rough: 0.4, metal: 0.05 },
    ));
    // Countertop drip edge
    objects.push(mk(
        new THREE.BoxGeometry(cbW + 0.005, CTR * 0.6, 0.022), palette.cabDark,
        [x + cbW/2, cbH + CTR * 0.3, cbD + 0.07], null,
        { rough: 0.5, metal: 0.05 },
    ));

    // v19.0.4.24.0 P0#1 Stage 2 — Visual pin indicator. Small teal
    // sphere hovering just above the countertop's back-right corner
    // marks the cabinet as manually placed. Gated behind item.pinned
    // so a fresh page render adds zero geometry.
    if (item.pinned) {
        objects.push(mk(
            new THREE.SphereGeometry(0.06, 14, 14), 0x18B4A6,
            [x + cbW - 0.10, cbH + CTR + 0.16, cbD - 0.10], null,
            { rough: 0.3, metal: 0.5 },
        ));
    }

    return { objects, clickable };
}
