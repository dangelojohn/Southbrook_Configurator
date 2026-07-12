/** @odoo-module **/
/**
 * Southbrook Kitchen 3D Configurator — room-shell mesh builder.
 *
 * Rec D · Sprint 2d · Step 11 · closure-body extraction.
 *
 * Builds the fixed room geometry: floor plane, back + left walls,
 * wainscoting rail on the back wall, and the floor grid. Extracted
 * from kitchen_configurator.js:1303-1322 verbatim.
 *
 * The caller passes:
 *   - THREE (vendored module) — needed for PlaneGeometry/BoxGeometry/
 *     GridHelper constructors
 *   - scene — the target Three.js scene (grid is added directly;
 *     the four PBR meshes go through `mk`)
 *   - mk — the closure that maps to the shared makeMesh factory in
 *     canvas/mesh_factory.esm.js
 *   - palette — hex colors {floor, wall1, wall2, cabDark, grid}
 *   - {rw, rh, rd} — room dimensions in scene units
 *
 * Returns the objects array the caller pushes into roomObjs, so the
 * dispose pass at the top of _buildScene can walk them uniformly.
 */

import { IN } from "@southbrook_kitchen_3d_configurator/js/canvas/constants.esm";

/**
 * @param {typeof THREE} THREE
 * @param {THREE.Scene} scene
 * @param {(geo:any, color:number, pos:any, rotE:any, opts?:object) => THREE.Mesh} mk
 * @param {{ floor: number, wall1: number, wall2: number, cabDark: number, grid: number }} palette
 * @param {number} rw
 * @param {number} rh
 * @param {number} rd
 * @returns {{ objects: THREE.Object3D[], grid: THREE.GridHelper }}
 */
export function buildRoomShell(THREE, scene, mk, palette, rw, rh, rd) {
    const floor = mk(
        new THREE.PlaneGeometry(rw, rd), palette.floor,
        [rw/2, 0, rd/2], [-Math.PI/2, 0, 0],
        { rs: true, rough: 0.95, metal: 0.0 },
    );
    // Room walls carry a `wall` tag so the canvas can raycast + select them
    // (Phase 1 interactive walls). Only back + left are rendered today (open
    // cutaway); right + front arrive with U-shape + dynamic wall visibility.
    const bwall = mk(
        new THREE.PlaneGeometry(rw, rh), palette.wall1,
        [rw/2, rh/2, 0], null,
        { rs: true, rough: 0.9, metal: 0.0,
          ud: { isRoomWall: true, wall: "back" } },
    );
    const lwall = mk(
        new THREE.PlaneGeometry(rd, rh), palette.wall2,
        [0, rh/2, rd/2], [0, Math.PI/2, 0],
        { rs: true, rough: 0.9, metal: 0.0,
          ud: { isRoomWall: true, wall: "left" } },
    );

    // Wainscoting rail on back wall — semi-gloss wood trim
    const railY = 36 * IN;
    const rail = mk(
        new THREE.BoxGeometry(rw, 0.012, 0.02), palette.cabDark,
        [rw/2, railY, 0.01], null,
        { rough: 0.55, metal: 0.0 },
    );

    // Floor grid
    const gSz = Math.max(rw, rd) + 6;
    const grid = new THREE.GridHelper(gSz, Math.ceil(gSz * 2), palette.grid, palette.grid);
    grid.position.set(rw/2, 0.002, rd/2);
    grid.material.transparent = true;
    grid.material.opacity     = 0.18;
    scene.add(grid);

    return { objects: [floor, bwall, lwall, rail, grid], grid,
             walls: { back: bwall, left: lwall } };
}
